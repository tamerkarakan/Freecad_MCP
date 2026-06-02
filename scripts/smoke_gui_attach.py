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

from freecad_mcp.cad_tools import CadToolService
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
    snapshot_path = run_dir / "active-view.png"
    document_path = run_dir / "gui-assembly-connectors.FCStd"
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
DOCUMENT_PATH = pathlib.Path({str(document_path)!r})
BRIDGE_PATH = pathlib.Path({str(bridge_path)!r})

try:
    import FreeCAD as App
    import FreeCADGui as Gui

    bridge_ns = {{}}
    exec(BRIDGE_PATH.read_text(encoding="utf-8"), bridge_ns)

    doc = App.newDocument("GuiAssemblySmoke")
    assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
    assembly.Type = "Assembly"
    assembly.newObject("Assembly::JointGroup", "Joints")

    box_a = doc.addObject("Part::Box", "BoxA")
    box_a.Length = 10
    box_a.Width = 8
    box_a.Height = 6
    box_b = doc.addObject("Part::Box", "BoxB")
    box_b.Length = 7
    box_b.Width = 5
    box_b.Height = 4
    box_b.Placement.Base.x = 16
    sketch = doc.addObject("Sketcher::SketchObject", "GuiSketch")
    body = doc.addObject("PartDesign::Body", "GuiBody")
    doc.recompute()
    doc.saveAs(str(DOCUMENT_PATH))

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, box_a.Name, "Face1", 0.0, 0.0, 0.0, True)
    Gui.Selection.addSelection(doc.Name, box_b.Name, "Face1", 16.0, 0.0, 0.0, False)
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
                "document_path": str(DOCUMENT_PATH),
                "object_names": [box_a.Name, box_b.Name],
                "assembly_name": assembly.Name,
                "sketch_name": sketch.Name,
                "body_name": body.Name,
                "selection": ["Face1", "Face1"],
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
        document_open = tools["freecad_gui_document_open"].handler(
            {
                "session_id": session_id,
                "document_path": str(document_path),
                "activate": True,
                "fit_view": True,
                "timeout_sec": 10,
            }
        )
        opened_file = Path(str(document_open["gui"]["document"]["file_name"]))
        if opened_file.resolve() != document_path.resolve():
            raise RuntimeError(f"GUI document open returned unexpected file: {document_open}")
        status = tools["freecad_gui_status"].handler({"session_id": session_id, "timeout_sec": 10})
        selection = tools["freecad_gui_selection_get"].handler(
            {"session_id": session_id, "document_name": str(ready["document_name"]), "resolve": 0}
        )
        records = selection["gui"]["selection"]
        if len(records) != 2:
            raise RuntimeError(f"expected two GUI selection records, got {records}")
        object_names = list(ready["object_names"])
        for index, record in enumerate(records):
            if record.get("object_name") != object_names[index] or "Face1" not in record.get("subelement_names", []):
                raise RuntimeError(f"unexpected GUI selection record: {record}")
        label_set = tools["freecad_gui_object_label_set"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "object_name": object_names[0],
                "label": "GUI Primary Box",
                "require_unique": True,
                "select": False,
            }
        )
        if label_set["gui"]["object"]["label"] != "GUI Primary Box":
            raise RuntimeError(f"GUI label set failed: {label_set}")
        sketch_state = tools["freecad_gui_sketch_state"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "sketch_name": str(ready["sketch_name"]),
            }
        )
        if sketch_state["gui"]["active_sketch"]["object"]["name"] != str(ready["sketch_name"]):
            raise RuntimeError(f"unexpected GUI sketch state: {sketch_state}")
        sketch_enter = tools["freecad_gui_sketch_enter"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "sketch_name": str(ready["sketch_name"]),
                "reset_existing": True,
                "fit_view": False,
            }
        )
        if sketch_enter["gui"]["after"]["object"]["name"] != str(ready["sketch_name"]):
            raise RuntimeError(f"sketch did not enter edit mode: {sketch_enter}")
        feature_task_state = tools["freecad_gui_feature_task_state"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "include_widget_tree": False,
            }
        )
        if "control" not in feature_task_state["gui"]:
            raise RuntimeError(f"feature task state did not report GUI control metadata: {feature_task_state}")
        sketch_leave = tools["freecad_gui_sketch_leave"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "sketch_name": str(ready["sketch_name"]),
                "recompute": True,
            }
        )
        if sketch_leave["gui"]["after"]["in_edit"]:
            raise RuntimeError(f"sketch did not leave edit mode: {sketch_leave}")
        partdesign_state = tools["freecad_gui_partdesign_state"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "body_name": str(ready["body_name"]),
            }
        )
        if partdesign_state["gui"]["active_body"]["object"]["name"] != str(ready["body_name"]):
            raise RuntimeError(f"unexpected GUI PartDesign state: {partdesign_state}")
        body_activate = tools["freecad_gui_body_activate"].handler(
            {
                "session_id": session_id,
                "document_name": str(ready["document_name"]),
                "body_name": str(ready["body_name"]),
                "fit_view": False,
            }
        )
        if body_activate["gui"]["activated"]["name"] != str(ready["body_name"]):
            raise RuntimeError(f"body did not activate: {body_activate}")
        view_snapshot = tools["freecad_gui_view_snapshot"].handler(
            {
                "session_id": session_id,
                "output_path": str(snapshot_path),
                "width": 1024,
                "height": 768,
                "format": "png",
                "background": "Current",
                "fit_view": True,
                "overwrite": True,
            }
        )
        if not snapshot_path.exists() or snapshot_path.stat().st_size <= 0:
            raise RuntimeError(f"view snapshot was not written: {view_snapshot}")
        restored_selection = tools["freecad_gui_selection_set"].handler(
            {"session_id": session_id, "records": records, "clear": True}
        )
        fit = tools["freecad_gui_view_fit"].handler({"session_id": session_id, "selection_only": True})
        tools["freecad_gui_detach"].handler({"session_id": session_id})

        stop_path.write_text("stop\n", encoding="utf-8")
        terminate(process)

        references = [
            {"object_name": record["object_name"], "sub_element": record["subelement_names"][0]}
            for record in records
        ]
        cad_tools = CadToolService().definition_map()
        joint = cad_tools["freecad_assembly_create_joint"].handler(
            {
                "document_path": str(document_path),
                "assembly_name": str(ready["assembly_name"]),
                "joint_name": "GuiSelectionFixedJoint",
                "joint_type": "Fixed",
                "references": references,
                "output_path": str(document_path),
                "overwrite": True,
            }
        )
        joint_payload = joint.get("freecad")
        if not isinstance(joint_payload, dict) or joint_payload.get("error"):
            raise RuntimeError(f"assembly connector joint failed: {joint}")
        joint_fields = joint_payload["joint_fields"]
        if not joint_fields["has_reference1"] or not joint_fields["has_reference2"]:
            raise RuntimeError(f"assembly connector references were not populated: {joint}")

        report = {
            "status": "OK",
            "freecad_gui": str(gui_exe),
            "run_dir": str(run_dir),
            "document_path": str(document_path),
            "ready": ready,
            "attach": attach,
            "document_open_result": document_open,
            "status_result": status,
            "selection_result": selection,
            "label_set_result": label_set,
            "sketch_state_result": sketch_state,
            "sketch_enter_result": sketch_enter,
            "feature_task_state_result": feature_task_state,
            "sketch_leave_result": sketch_leave,
            "partdesign_state_result": partdesign_state,
            "body_activate_result": body_activate,
            "view_snapshot_result": view_snapshot,
            "restored_selection_result": restored_selection,
            "fit_result": fit,
            "assembly_joint_result": joint,
        }
        write_report(report_path, report)
        print(f"GUI attach and assembly connector smoke OK: {report_path}")
        return 0
    finally:
        stop_path.write_text("stop\n", encoding="utf-8")
        terminate(process)


if __name__ == "__main__":
    raise SystemExit(main())
