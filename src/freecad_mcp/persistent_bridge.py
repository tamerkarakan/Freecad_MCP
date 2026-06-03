"""Persistent FreeCADCmd worker bridge."""

from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from freecad_mcp.runtime_bridge import FreeCadDiscovery, FreeCadDiscoveryResult, MAX_INLINE_CODE_CHARS, truncate_text
from freecad_mcp.tooling import JsonObject, ToolInputError, load_runtime_script


WORKER_PREFIX = "__FREECAD_MCP_WORKER__"
MAX_WORKER_STREAM_CHARS = 12_000
DEFAULT_MAX_WORKER_SESSIONS = 8
WORKER_TIMEOUT_PREFIX = "worker request timed out after "


def _resolve_max_worker_sessions(value: int | None) -> int:
    if value is not None:
        return max(1, int(value))
    raw = os.environ.get("FREECAD_MCP_MAX_WORKER_SESSIONS")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return DEFAULT_MAX_WORKER_SESSIONS


FREECAD_WORKER_SCRIPT = load_runtime_script("worker.py")


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
    _console_lines: deque[str] = field(default_factory=lambda: deque(maxlen=500), init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _next_request_id: int = 0
    _script_path: Path | None = field(default=None, init=False)

    def start(self, *, timeout_sec: int = 30) -> JsonObject:
        if self.process is not None and self.is_running:
            return self.to_dict()
        self._cleanup_script_file()
        env = os.environ.copy()
        env["FREECAD_MCP_WORKSPACE_ROOT"] = str(self.workspace_root)
        script_path: Path | None = None
        if len(self.worker_script) > MAX_INLINE_CODE_CHARS:
            handle = tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False)
            try:
                handle.write(self.worker_script)
                script_path = Path(handle.name)
            finally:
                handle.close()
            argv = [str(self.executable), str(script_path)]
        else:
            argv = [str(self.executable), "-c", self.worker_script]
        try:
            self._script_path = script_path
            self.process = subprocess.Popen(
                argv,
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
        except Exception:
            if self.process is not None and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=timeout_sec)
                except Exception:
                    try:
                        self.process.kill()
                        self.process.wait(timeout=timeout_sec)
                    except Exception:
                        pass
            self._close_pipes()
            self._cleanup_script_file()
            raise

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
        self._cleanup_script_file()
        return {"session": self.to_dict(), "shutdown": response}

    def console_snapshot(self, *, max_lines: int = 200) -> JsonObject:
        """Return captured FreeCAD console output without a worker round-trip.

        stderr carries FreeCAD warnings/errors and Python tracebacks; the stdout
        console buffer carries non-protocol stdout (e.g. App.Console.PrintMessage).
        Both are tailed to the most recent ``max_lines`` entries.
        """
        max_lines = max(1, min(int(max_lines), 500))
        return {
            "session_id": self.session_id,
            "running": self.is_running,
            "stderr": list(self._stderr_lines)[-max_lines:],
            "stderr_line_count": len(self._stderr_lines),
            "stdout_console": list(self._console_lines)[-max_lines:],
            "stdout_console_line_count": len(self._console_lines),
            "max_lines": max_lines,
        }

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
            # Protocol replies are prefixed; everything else on stdout is FreeCAD
            # console output (e.g. App.Console.PrintMessage). Capture the latter
            # for freecad_session_console instead of dropping it, while still
            # forwarding protocol lines to the request queue.
            if line.startswith(WORKER_PREFIX):
                self._stdout_queue.put(line)
            else:
                stripped = line.rstrip("\n")
                if stripped:
                    self._console_lines.append(stripped)

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

    def _cleanup_script_file(self) -> None:
        if self._script_path is None:
            return
        try:
            self._script_path.unlink()
        except OSError:
            return
        self._script_path = None

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
        max_sessions: int | None = None,
    ):
        self.discovery = discovery or FreeCadDiscovery()
        self.workspace_root = (workspace_root or Path(os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or Path.cwd())).resolve()
        self.worker_script = worker_script
        self.max_sessions = _resolve_max_worker_sessions(max_sessions)
        self.sessions: dict[str, FreeCadWorkerSession] = {}
        self._atexit_registered = False

    def start_session(
        self,
        *,
        executable: str | None = None,
        freecad_home: str | None = None,
        timeout_sec: int = 30,
    ) -> JsonObject:
        self._drop_stopped()
        if len(self.sessions) >= self.max_sessions:
            raise ToolInputError(
                f"worker session limit reached ({self.max_sessions}); "
                "close an existing worker session before starting another."
            )
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
        self._register_atexit_cleanup()
        return {"discovery": discovery.to_dict(), **started}

    def list_sessions(self) -> JsonObject:
        self._drop_stopped()
        return {"sessions": [session.to_dict() for session in self.sessions.values()], "count": len(self.sessions)}

    def status(self, session_id: str, *, timeout_sec: int = 30) -> JsonObject:
        session = self.get(session_id)
        try:
            response = session.request("status", {}, timeout_sec=timeout_sec)
        except ToolInputError as exc:
            self._terminate_after_timeout(session_id, session, exc)
            self._drop_if_stopped(session_id, session)
            raise
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
        try:
            response = session.request(
                method,
                {**params, "workspace_root": str(self.workspace_root)},
                timeout_sec=timeout_sec,
            )
        except ToolInputError as exc:
            self._terminate_after_timeout(session_id, session, exc)
            self._drop_if_stopped(session_id, session)
            raise
        if not response.ok:
            return {"session": session.to_dict(), "worker": response.to_dict(), "ok": False}
        return {"session": session.to_dict(), "worker": response.to_dict(), "ok": True}

    def get(self, session_id: str) -> FreeCadWorkerSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise ToolInputError(f"unknown worker session: {session_id}")
        if not session.is_running:
            session.close(timeout_sec=1)
            self.sessions.pop(session_id, None)
            raise ToolInputError(f"worker session is not running: {session_id}")
        return session

    def console(self, session_id: str, *, max_lines: int = 200) -> JsonObject:
        # Read buffered console output directly from the session object. Unlike
        # get(), this does not require the worker to be running: console output is
        # most useful for diagnosing a session that just crashed.
        session = self.sessions.get(session_id)
        if session is None:
            raise ToolInputError(f"unknown worker session: {session_id}")
        return {"session": session.to_dict(), "console": session.console_snapshot(max_lines=max_lines)}

    def shutdown_all(self) -> None:
        for session_id in list(self.sessions):
            try:
                self.close(session_id)
            except Exception:
                self.sessions.pop(session_id, None)

    def _register_atexit_cleanup(self) -> None:
        # Guarantee worker subprocesses and their temp scripts are torn down on
        # normal interpreter exit, even if the stdio serve loop's finally is
        # bypassed. Registered lazily so managers that never start a worker
        # (e.g. unit tests) add no global state. shutdown_all is idempotent, so
        # running both here and via the serve loop is safe.
        if not self._atexit_registered:
            atexit.register(self.shutdown_all)
            self._atexit_registered = True

    def _drop_stopped(self) -> None:
        for session_id, session in list(self.sessions.items()):
            if not session.is_running:
                session.close(timeout_sec=1)
                self.sessions.pop(session_id, None)

    def _drop_if_stopped(self, session_id: str, session: FreeCadWorkerSession) -> None:
        if session.is_running:
            return
        session.close(timeout_sec=1)
        self.sessions.pop(session_id, None)

    def _terminate_after_timeout(
        self,
        session_id: str,
        session: FreeCadWorkerSession,
        exc: ToolInputError,
    ) -> None:
        if not str(exc).startswith(WORKER_TIMEOUT_PREFIX):
            return
        try:
            session.close(timeout_sec=1)
        except Exception:
            pass
        self.sessions.pop(session_id, None)
        raise ToolInputError(
            f"{exc}; worker session {session_id} was terminated to avoid continuing "
            "a stale FreeCAD operation. Start a new worker session and retry with a "
            "larger timeout_sec if the operation is expected to take longer."
        ) from exc


def discovery_summary(discovery: FreeCadDiscoveryResult) -> JsonObject:
    return discovery.to_dict()
