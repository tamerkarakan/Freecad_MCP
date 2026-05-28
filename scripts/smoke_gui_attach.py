#!/usr/bin/env python3
"""Opt-in smoke test for the FreeCAD GUI attach bridge.

This test launches FreeCAD GUI with a temporary macro, starts the local GUI
bridge inside that process, selects a box face, then reads the selection through
the MCP GUI attach tools.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_mcp.gui_tools import GuiToolService


def discover_freecad_gui() -> Path:
    explicit = os.environ.get("FREECAD_MCP_FREECAD_GUI")
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    home = os.environ.get("FREECAD_MCP_FREECAD_HOME")
    if home:
        base = Path(home)
        candidates.extend([base / "bin" / "FreeCAD.exe", base / "bin" / "freecad.exe", base / "FreeCAD.exe"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError("FreeCAD GUI executable not found; set FREECAD_MCP_FREECAD_GUI or FREECAD_MCP_FREECAD_HOME")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_ready(ready_path: Path, process: subprocess.Popen[bytes], timeout_sec: int = 45) -> dict[str, object]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if ready_path.exists():
            payload = json.loads(ready_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("GUI smoke ready file did not contain a JSON object")
            return payload
        if process.poll() is not None:
            raise RuntimeError(f"FreeCAD GUI exited before bridge was ready: {process.returncode}")
        time.sleep(0.2)
    raise RuntimeError("timed out waiting for FreeCAD GUI bridge readiness")


def terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    gui_exe = discover_freecad_gui()
    port = free_port()
    token_seed = f"{time.time()}:{port}:{ROOT}".encode("utf-8")
    token = hashlib.sha256(token_seed).hexdigest()[:24]
    run_id = time.strftime("gui-%Y%m%d-%H%M%S")
    run_dir = ROOT / "runs" / "gui-smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    ready_path = run_dir / "ready.json"
    stop_path = run_dir / "stop.txt"
    report_path = run_dir / f"gui-smoke-report-{run_id}.json"
    macro_path = run_dir / "freecad_gui_smoke_macro.py"
    bridge_path = ROOT / "scripts" / "freecad_gui_bridge_server.py"

    macro_path.write_text(
        f"""
from __future__ import annotations

import json
import pathlib
import time
import traceback

READY_PATH = pathlib.Path({str(ready_path)!r})
STOP_PATH = pathlib.Path({str(stop_path)!r})
BRIDGE_PATH = pathlib.Path({str(bridge_path)!r})

try:
    import FreeCAD as App
    import FreeCADGui as Gui

    bridge_ns = {{}}
    exec(BRIDGE_PATH.read_text(encoding="utf-8"), bridge_ns)

    doc = App.newDocument("GuiSmoke")
    box = doc.addObject("Part::Box", "Box")
    box.Length = 10
    box.Width = 8
    box.Height = 6
    doc.recompute()

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, box.Name, "Face1", 0.0, 0.0, 0.0)
    try:
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
    except Exception:
        pass

    bridge_status = bridge_ns["start_bridge"](host="127.0.0.1", port={port}, token={token!r})
    READY_PATH.write_text(
        json.dumps(
            {{
                "ok": True,
                "document_name": doc.Name,
                "object_name": box.Name,
                "selection": "Face1",
                "bridge": bridge_status,
            }},
            indent=2,
        ),
        encoding="utf-8",
    )

    deadline = time.time() + 60
    while not STOP_PATH.exists() and time.time() < deadline:
        try:
            Gui.updateGui()
        except Exception:
            pass
        time.sleep(0.05)

    bridge_ns["stop_bridge"]()
    App.closeDocument(doc.Name)
except Exception as exc:
    READY_PATH.write_text(
        json.dumps({{"ok": False, "error": str(exc), "traceback": traceback.format_exc()}}, indent=2),
        encoding="utf-8",
    )
""",
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [str(gui_exe), str(macro_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        ready = wait_for_ready(ready_path, process)
        if not ready.get("ok"):
            raise RuntimeError(f"FreeCAD GUI macro failed: {ready}")

        service = GuiToolService()
        tools = service.definition_map()
        attach = tools["freecad_gui_attach"].handler(
            {"url": f"http://127.0.0.1:{port}", "token": token, "timeout_sec": 10}
        )
        session_id = str(attach["session"]["session_id"])
        status = tools["freecad_gui_status"].handler({"session_id": session_id, "timeout_sec": 10})
        selection = tools["freecad_gui_selection_get"].handler(
            {"session_id": session_id, "document_name": str(ready["document_name"]), "resolve": 0}
        )
        records = selection["gui"]["selection"]
        if not records:
            raise RuntimeError("GUI selection was empty")
        first = records[0]
        if first.get("object_name") != ready["object_name"] or "Face1" not in first.get("subelement_names", []):
            raise RuntimeError(f"unexpected GUI selection record: {first}")

        fit = tools["freecad_gui_view_fit"].handler({"session_id": session_id, "selection_only": True})
        tools["freecad_gui_detach"].handler({"session_id": session_id})
        report = {
            "status": "OK",
            "freecad_gui": str(gui_exe),
            "run_dir": str(run_dir),
            "ready": ready,
            "attach": attach,
            "status_result": status,
            "selection_result": selection,
            "fit_result": fit,
        }
        write_report(report_path, report)
        print(f"GUI attach smoke OK: {report_path}")
        return 0
    finally:
        stop_path.write_text("stop\n", encoding="utf-8")
        terminate(process)


if __name__ == "__main__":
    raise SystemExit(main())
