"""Persistent FreeCADCmd worker bridge."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from freecad_mcp.runtime_bridge import FreeCadDiscovery, FreeCadDiscoveryResult, truncate_text
from freecad_mcp.tooling import JsonObject, ToolInputError


WORKER_PREFIX = "__FREECAD_MCP_WORKER__"
MAX_WORKER_STREAM_CHARS = 12_000


FREECAD_WORKER_SCRIPT = r'''
import json
import os
import sys
import traceback

import FreeCAD as App

PREFIX = "__FREECAD_MCP_WORKER__"
DOCUMENTS = {}


def emit(payload):
    sys.stdout.write(PREFIX + json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()


def vector(value, default=None):
    if value is None:
        value = default if default is not None else [0, 0, 0]
    return App.Vector(float(value[0]), float(value[1]), float(value[2]))


def placement_summary(obj):
    if not hasattr(obj, "Placement"):
        return None
    plc = obj.Placement
    return {
        "base": [plc.Base.x, plc.Base.y, plc.Base.z],
        "rotation_axis": [plc.Rotation.Axis.x, plc.Rotation.Axis.y, plc.Rotation.Axis.z],
        "rotation_angle": plc.Rotation.Angle,
    }


def shape_summary(obj):
    if not hasattr(obj, "Shape"):
        return None
    shape = obj.Shape
    if shape is None or shape.isNull():
        return None
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "shells": len(shape.Shells),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "vertices": len(shape.Vertexes),
        "bound_box": {
            "xmin": box.XMin,
            "ymin": box.YMin,
            "zmin": box.ZMin,
            "xmax": box.XMax,
            "ymax": box.YMax,
            "zmax": box.ZMax,
        },
    }


def object_summary(obj):
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "visibility": bool(getattr(obj, "Visibility", False)),
        "placement": placement_summary(obj),
        "shape": shape_summary(obj),
    }


def document_id(doc):
    DOCUMENTS[doc.Name] = doc.Name
    return doc.Name


def document_summary(doc):
    return {
        "document_id": document_id(doc),
        "name": doc.Name,
        "label": doc.Label,
        "file_name": doc.FileName,
        "object_count": len(doc.Objects),
        "objects": [object_summary(obj) for obj in doc.Objects],
    }


def get_doc(params):
    doc_id = params.get("document_id")
    if not doc_id:
        raise ValueError("document_id is required")
    doc_name = DOCUMENTS.get(doc_id, doc_id)
    doc = App.getDocument(doc_name)
    if doc is None:
        raise ValueError("document not found: " + str(doc_id))
    return doc


def get_object(doc, name):
    obj = doc.getObject(name)
    if obj is not None:
        return obj
    for candidate in doc.Objects:
        if candidate.Label == name:
            return candidate
    raise ValueError("object not found: " + name)


def safe_output_path(path, params):
    if not path:
        return None
    if not os.path.isabs(path):
        raise ValueError("output_path must be absolute")
    resolved = os.path.abspath(path)
    if bool(params.get("allow_external_paths", False)):
        return resolved
    root = os.path.abspath(params.get("workspace_root") or os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or os.getcwd())
    try:
        common = os.path.commonpath([root, resolved])
    except ValueError:
        common = ""
    if common != root:
        raise ValueError("output_path escapes workspace root; pass allow_external_paths=true if intentional")
    return resolved


def save_doc(doc, params):
    output = safe_output_path(params.get("output_path"), params)
    if output:
        if os.path.exists(output) and not bool(params.get("overwrite", False)):
            raise ValueError("output exists; pass overwrite=true: " + output)
        doc.saveAs(output)
        return output
    if bool(params.get("save", False)):
        if not doc.FileName:
            raise ValueError("document has no FileName; pass output_path")
        doc.save()
        return doc.FileName
    return None


def action_ping(params):
    return {"version": App.Version(), "document_count": len(App.listDocuments())}


def action_status(params):
    docs = App.listDocuments()
    return {
        "version": App.Version(),
        "documents": [document_summary(doc) for doc in docs.values()],
        "document_count": len(docs),
    }


def action_document_new(params):
    doc = App.newDocument(params.get("document_name") or "McpWorkerDocument")
    if params.get("label"):
        doc.Label = params["label"]
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "document": document_summary(doc)}


def action_document_open(params):
    path = params.get("document_path")
    if not path:
        raise ValueError("document_path is required")
    doc = App.openDocument(path)
    return {"document": document_summary(doc)}


def action_document_save(params):
    doc = get_doc(params)
    doc.recompute()
    saved = save_doc(doc, {**params, "save": True})
    return {"saved_path": saved, "document": document_summary(doc)}


def action_document_recompute(params):
    doc = get_doc(params)
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "document": document_summary(doc)}


def action_document_close(params):
    doc = get_doc(params)
    doc_id = document_id(doc)
    App.closeDocument(doc.Name)
    DOCUMENTS.pop(doc_id, None)
    return {"closed": doc_id, "document_count": len(App.listDocuments())}


def action_part_create_primitive(params):
    doc = get_doc(params)
    primitive = params.get("primitive", "box")
    type_map = {
        "box": "Part::Box",
        "cylinder": "Part::Cylinder",
        "sphere": "Part::Sphere",
        "cone": "Part::Cone",
        "torus": "Part::Torus",
    }
    if primitive not in type_map:
        raise ValueError("unsupported primitive: " + str(primitive))
    doc.openTransaction("MCP worker create primitive")
    try:
        obj = doc.addObject(type_map[primitive], params.get("object_name") or primitive.title())
        for key, value in (params.get("properties") or {}).items():
            setattr(obj, key, value)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "object": object_summary(obj), "document": document_summary(doc)}


def action_object_list(params):
    doc = get_doc(params)
    return {"document": document_summary(doc)}


def action_object_get(params):
    doc = get_doc(params)
    obj = get_object(doc, params.get("object_name") or "")
    return {"object": object_summary(obj)}


ACTIONS = {
    "ping": action_ping,
    "status": action_status,
    "document_new": action_document_new,
    "document_open": action_document_open,
    "document_save": action_document_save,
    "document_recompute": action_document_recompute,
    "document_close": action_document_close,
    "part_create_primitive": action_part_create_primitive,
    "object_list": action_object_list,
    "object_get": action_object_get,
}


emit({"type": "ready", "version": App.Version(), "pid": os.getpid()})
for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    try:
        request = json.loads(line)
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if method == "shutdown":
            emit({"id": request_id, "ok": True, "result": {"closed": True}})
            break
        if method not in ACTIONS:
            raise ValueError("unknown worker method: " + str(method))
        result = ACTIONS[method](params)
        emit({"id": request_id, "ok": True, "result": result})
    except Exception as exc:
        emit({
            "id": locals().get("request_id", None),
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
'''


@dataclass
class WorkerResponse:
    ok: bool
    result: JsonObject | None = None
    error: str | None = None
    traceback: str | None = None
    raw: JsonObject | None = None

    def to_dict(self) -> JsonObject:
        payload: JsonObject = {"ok": self.ok}
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        if self.traceback is not None:
            clipped, truncated = truncate_text(self.traceback, MAX_WORKER_STREAM_CHARS)
            payload["traceback"] = clipped
            payload["traceback_truncated"] = truncated
        return payload


@dataclass
class FreeCadWorkerSession:
    session_id: str
    executable: Path
    workspace_root: Path
    worker_script: str = FREECAD_WORKER_SCRIPT
    started_at: float = field(default_factory=time.time)
    request_count: int = 0
    process: subprocess.Popen[str] | None = None
    _stdout_queue: queue.Queue[str] = field(default_factory=queue.Queue, init=False)
    _stderr_lines: deque[str] = field(default_factory=lambda: deque(maxlen=200), init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _next_request_id: int = 0

    def start(self, *, timeout_sec: int = 30) -> JsonObject:
        if self.process is not None and self.is_running:
            return self.to_dict()
        env = os.environ.copy()
        env["FREECAD_MCP_WORKSPACE_ROOT"] = str(self.workspace_root)
        self.process = subprocess.Popen(
            [str(self.executable), "-c", self.worker_script],
            cwd=str(self.executable.parent),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self.process.stdout is not None:
            threading.Thread(target=self._drain_stdout, daemon=True).start()
        if self.process.stderr is not None:
            threading.Thread(target=self._drain_stderr, daemon=True).start()
        ready = self._wait_for_message(timeout_sec=timeout_sec, expected_id=None, expected_type="ready")
        return {"session": self.to_dict(), "ready": ready}

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def request(self, method: str, params: JsonObject | None = None, *, timeout_sec: int = 30) -> WorkerResponse:
        if not self.is_running or self.process is None or self.process.stdin is None:
            raise ToolInputError(f"worker session is not running: {self.session_id}")
        with self._lock:
            self._next_request_id += 1
            request_id = str(self._next_request_id)
            payload = {"id": request_id, "method": method, "params": params or {}}
            self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            self.request_count += 1
            raw = self._wait_for_message(timeout_sec=timeout_sec, expected_id=request_id)
        ok = bool(raw.get("ok"))
        result = raw.get("result") if isinstance(raw.get("result"), dict) else None
        return WorkerResponse(
            ok=ok,
            result=result,
            error=str(raw.get("error")) if raw.get("error") is not None else None,
            traceback=str(raw.get("traceback")) if raw.get("traceback") is not None else None,
            raw=raw,
        )

    def close(self, *, timeout_sec: int = 5) -> JsonObject:
        response: JsonObject | None = None
        if self.is_running:
            try:
                response = self.request("shutdown", {}, timeout_sec=timeout_sec).to_dict()
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            if self.process is not None:
                try:
                    self.process.wait(timeout=timeout_sec)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=timeout_sec)
        self._close_pipes()
        return {"session": self.to_dict(), "shutdown": response}

    def to_dict(self) -> JsonObject:
        stderr, stderr_truncated = truncate_text("\n".join(self._stderr_lines), MAX_WORKER_STREAM_CHARS)
        return {
            "session_id": self.session_id,
            "mode": "freecadcmd-worker",
            "pid": self.process.pid if self.process is not None else None,
            "running": self.is_running,
            "executable": str(self.executable),
            "workspace_root": str(self.workspace_root),
            "started_at": self.started_at,
            "request_count": self.request_count,
            "stderr": stderr,
            "stderr_truncated": stderr_truncated,
        }

    def _drain_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            self._stdout_queue.put(line)

    def _drain_stderr(self) -> None:
        assert self.process is not None and self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr_lines.append(line.rstrip("\n"))

    def _close_pipes(self) -> None:
        if self.process is None:
            return
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            try:
                if stream is not None and not stream.closed:
                    stream.close()
            except Exception:
                pass

    def _wait_for_message(
        self,
        *,
        timeout_sec: int,
        expected_id: str | None,
        expected_type: str | None = None,
    ) -> JsonObject:
        deadline = time.monotonic() + timeout_sec
        while True:
            if self.process is not None and self.process.poll() is not None and self._stdout_queue.empty():
                raise ToolInputError(f"worker exited with code {self.process.returncode}: {self.to_dict()['stderr']}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ToolInputError(f"worker request timed out after {timeout_sec}s")
            try:
                line = self._stdout_queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if not line.startswith(WORKER_PREFIX):
                continue
            try:
                payload = json.loads(line[len(WORKER_PREFIX) :])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if expected_type is not None and payload.get("type") == expected_type:
                return payload
            if expected_id is not None and str(payload.get("id")) == expected_id:
                return payload


class PersistentBridgeManager:
    """Owns FreeCAD worker sessions for one MCP server process."""

    def __init__(
        self,
        discovery: FreeCadDiscovery | None = None,
        workspace_root: Path | None = None,
        worker_script: str = FREECAD_WORKER_SCRIPT,
    ):
        self.discovery = discovery or FreeCadDiscovery()
        self.workspace_root = (workspace_root or Path(os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or Path.cwd())).resolve()
        self.worker_script = worker_script
        self.sessions: dict[str, FreeCadWorkerSession] = {}

    def start_session(
        self,
        *,
        executable: str | None = None,
        freecad_home: str | None = None,
        timeout_sec: int = 30,
    ) -> JsonObject:
        discovery = self.discovery.discover(executable=executable, freecad_home=freecad_home)
        if discovery.executable is None:
            raise ToolInputError(
                "FreeCADCmd not found. Set FREECAD_MCP_FREECAD_HOME, FREECAD_MCP_FREECAD_CMD, "
                "or pass freecad_home/executable."
            )
        session_id = uuid.uuid4().hex[:12]
        session = FreeCadWorkerSession(
            session_id=session_id,
            executable=Path(discovery.executable),
            workspace_root=self.workspace_root,
            worker_script=self.worker_script,
        )
        try:
            started = session.start(timeout_sec=timeout_sec)
        except Exception:
            session.close(timeout_sec=1)
            raise
        self.sessions[session_id] = session
        return {"discovery": discovery.to_dict(), **started}

    def list_sessions(self) -> JsonObject:
        self._drop_stopped()
        return {"sessions": [session.to_dict() for session in self.sessions.values()], "count": len(self.sessions)}

    def status(self, session_id: str, *, timeout_sec: int = 30) -> JsonObject:
        session = self.get(session_id)
        response = session.request("status", {}, timeout_sec=timeout_sec)
        if not response.ok:
            raise ToolInputError(response.error or "worker status failed")
        return {"session": session.to_dict(), "worker": response.result}

    def close(self, session_id: str, *, timeout_sec: int = 5) -> JsonObject:
        session = self.sessions.get(session_id)
        if session is None:
            return {
                "session": {"session_id": session_id, "mode": "freecadcmd-worker", "running": False},
                "shutdown": None,
                "already_closed": True,
            }
        if not session.is_running:
            self.sessions.pop(session_id, None)
            return {
                "session": session.to_dict(),
                "shutdown": None,
                "already_closed": True,
            }
        payload = session.close(timeout_sec=timeout_sec)
        self.sessions.pop(session_id, None)
        return payload

    def request(self, session_id: str, method: str, params: JsonObject, *, timeout_sec: int = 30) -> JsonObject:
        session = self.get(session_id)
        response = session.request(method, {**params, "workspace_root": str(self.workspace_root)}, timeout_sec=timeout_sec)
        if not response.ok:
            return {"session": session.to_dict(), "worker": response.to_dict(), "ok": False}
        return {"session": session.to_dict(), "worker": response.to_dict(), "ok": True}

    def get(self, session_id: str) -> FreeCadWorkerSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise ToolInputError(f"unknown worker session: {session_id}")
        if not session.is_running:
            self.sessions.pop(session_id, None)
            raise ToolInputError(f"worker session is not running: {session_id}")
        return session

    def shutdown_all(self) -> None:
        for session_id in list(self.sessions):
            try:
                self.close(session_id)
            except Exception:
                self.sessions.pop(session_id, None)

    def _drop_stopped(self) -> None:
        for session_id, session in list(self.sessions.items()):
            if not session.is_running:
                session.close(timeout_sec=1)
                self.sessions.pop(session_id, None)


def discovery_summary(discovery: FreeCadDiscoveryResult) -> JsonObject:
    return discovery.to_dict()
