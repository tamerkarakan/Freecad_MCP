"""Small loopback JSON bridge to run inside FreeCAD GUI.

Usage from FreeCAD GUI Python console:

    ns = {}
    exec(open("C:/path/to/Freecad_MCP/scripts/freecad_gui_bridge_server.py").read(), ns)
    ns["start_bridge"](token="choose-a-local-token")

The bridge binds to 127.0.0.1 by default and exposes only a tiny RPC surface
for active document, active view, selection, and fit-view workflows.
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 48777

_SERVER: ThreadingHTTPServer | None = None
_TOKEN: str | None = None
_GUI_INVOKER: Any | None = None


def qt_core() -> Any:
    try:
        from PySide6 import QtCore
    except Exception:
        from PySide2 import QtCore
    return QtCore


def queued_connection(QtCore: Any) -> Any:
    connection_type = getattr(QtCore.Qt, "ConnectionType", QtCore.Qt)
    return getattr(connection_type, "QueuedConnection")


def gui_invoker(QtCore: Any) -> Any:
    global _GUI_INVOKER
    if _GUI_INVOKER is not None:
        return _GUI_INVOKER

    class GuiThreadInvoker(QtCore.QObject):
        invoke = QtCore.Signal(object)

        def __init__(self) -> None:
            super().__init__()
            self.invoke.connect(self.run_payload, queued_connection(QtCore))

        def run_payload(self, payload: tuple[Any, tuple[Any, ...], queue.Queue]) -> None:
            func, args, result_queue = payload
            try:
                result_queue.put((True, func(*args)))
            except Exception as exc:
                result_queue.put((False, exc))

    _GUI_INVOKER = GuiThreadInvoker()
    app = QtCore.QCoreApplication.instance()
    if app is not None:
        _GUI_INVOKER.moveToThread(app.thread())
    return _GUI_INVOKER


def run_on_gui_thread(func: Any, *args: Any) -> Any:
    """Run FreeCADGui calls on the Qt main thread when PySide is available."""
    try:
        QtCore = qt_core()
    except Exception:
        return func(*args)

    app = QtCore.QCoreApplication.instance()
    if app is None or QtCore.QThread.currentThread() == app.thread():
        return func(*args)

    result_queue: queue.Queue = queue.Queue(maxsize=1)
    gui_invoker(QtCore).invoke.emit((func, args, result_queue))
    ok, result = result_queue.get(timeout=30)
    if ok:
        return result
    raise result


def vector_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return [float(value.x), float(value.y), float(value.z)]
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except Exception:
        return None


def active_document_summary() -> dict[str, Any] | None:
    import FreeCAD as App
    import FreeCADGui as Gui

    gui_doc = Gui.activeDocument()
    app_doc = App.activeDocument()
    if gui_doc is None and app_doc is None:
        return None
    doc = app_doc or getattr(gui_doc, "Document", None)
    if doc is None:
        return {"gui_document": str(gui_doc), "document": None}
    return {
        "name": doc.Name,
        "label": doc.Label,
        "file_name": doc.FileName,
        "object_count": len(doc.Objects),
        "active_object": doc.ActiveObject.Name if getattr(doc, "ActiveObject", None) else None,
    }


def active_view_summary() -> dict[str, Any] | None:
    import FreeCADGui as Gui

    gui_doc = Gui.activeDocument()
    if gui_doc is None:
        return None
    view = gui_doc.activeView()
    if view is None:
        return None
    camera = None
    try:
        camera = view.getCamera()
    except Exception:
        camera = None
    return {
        "type": type(view).__name__,
        "repr": repr(view),
        "camera": camera,
    }


def active_workbench_summary() -> dict[str, Any] | None:
    import FreeCADGui as Gui

    try:
        workbench = Gui.activeWorkbench()
    except Exception:
        return None
    if workbench is None:
        return None
    name_attr = getattr(workbench, "name", None)
    try:
        name = name_attr() if callable(name_attr) else str(workbench)
    except Exception:
        name = str(workbench)
    return {"name": name, "type": type(workbench).__name__}


def selection_record(sel: Any) -> dict[str, Any]:
    obj = getattr(sel, "Object", None)
    subelement_names = list(getattr(sel, "SubElementNames", ()) or ())
    picked_points = [vector_list(point) for point in (getattr(sel, "PickedPoints", ()) or ())]
    picked_points = [point for point in picked_points if point is not None]
    resolved = []
    if obj is not None:
        for subname in subelement_names:
            try:
                subobj = obj.getSubObject(subname)
                resolved.append({"subelement_name": subname, "type": type(subobj).__name__, "repr": repr(subobj)})
            except Exception as exc:
                resolved.append({"subelement_name": subname, "error": str(exc)})
    return {
        "document_name": getattr(sel, "DocumentName", None),
        "object_name": getattr(sel, "ObjectName", None),
        "object_label": getattr(obj, "Label", None) if obj is not None else None,
        "type_id": getattr(obj, "TypeId", None) if obj is not None else None,
        "subelement_names": subelement_names,
        "full_name": getattr(sel, "FullName", None),
        "picked_points": picked_points,
        "resolved": resolved,
    }


def rpc_status(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCAD as App

    bridge = {"running": _SERVER is not None, "token_configured": _TOKEN is not None}
    if _SERVER is not None:
        bridge["server_address"] = list(_SERVER.server_address)
    return {
        "bridge": bridge,
        "version": App.Version(),
        "active_document": active_document_summary(),
        "active_view": active_view_summary(),
        "active_workbench": active_workbench_summary(),
    }


def rpc_active_document_get(params: dict[str, Any]) -> dict[str, Any]:
    return {"active_document": active_document_summary()}


def rpc_active_view_get(params: dict[str, Any]) -> dict[str, Any]:
    return {"active_view": active_view_summary()}


def rpc_selection_get(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc_name = params.get("document_name")
    if not doc_name:
        doc_name = ""
    resolve = int(params.get("resolve", 0))
    selection = Gui.Selection.getSelectionEx(doc_name, resolve)
    return {"selection": [selection_record(sel) for sel in selection], "count": len(selection)}


def rpc_preselection_get(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    try:
        preselection = Gui.Selection.getPreselection()
    except Exception:
        preselection = None
    if preselection is None:
        return {"preselection": None}
    return {"preselection": selection_record(preselection)}


def rpc_selection_set(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    if bool(params.get("clear", True)):
        Gui.Selection.clearSelection()
    records = params.get("records") or []
    applied = []
    for record in records:
        doc_name = record.get("document_name")
        object_name = record.get("object_name")
        subelements = record.get("subelement_names") or [record.get("subelement_name") or ""]
        if not doc_name or not object_name:
            raise ValueError("selection records require document_name and object_name")
        for subelement in subelements:
            Gui.Selection.addSelection(str(doc_name), str(object_name), str(subelement or ""))
            applied.append({"document_name": doc_name, "object_name": object_name, "subelement_name": subelement or ""})
    return {"applied": applied, "count": len(applied)}


def rpc_view_fit(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    gui_doc = Gui.activeDocument()
    if gui_doc is None:
        raise ValueError("no active GUI document")
    view = gui_doc.activeView()
    if view is None:
        raise ValueError("no active GUI view")
    if bool(params.get("selection_only", False)) and hasattr(view, "fitSelection"):
        view.fitSelection()
        mode = "selection"
    else:
        view.fitAll()
        mode = "all"
    return {"fit": mode}


RPC_METHODS = {
    "status": rpc_status,
    "active_document_get": rpc_active_document_get,
    "active_view_get": rpc_active_view_get,
    "selection_get": rpc_selection_get,
    "preselection_get": rpc_preselection_get,
    "selection_set": rpc_selection_set,
    "view_fit": rpc_view_fit,
}


class BridgeHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/rpc":
            self.send_json({"ok": False, "error": "unknown path"}, status=404)
            return
        if _TOKEN:
            expected = "Bearer " + _TOKEN
            if self.headers.get("Authorization") != expected:
                self.send_json({"ok": False, "error": "unauthorized"}, status=401)
                return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            method = payload.get("method")
            params = payload.get("params") or {}
            if method not in RPC_METHODS:
                raise ValueError("unknown method: " + str(method))
            result = run_on_gui_thread(RPC_METHODS[method], params)
            self.send_json({"ok": True, "result": result})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        encoded = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def start_bridge(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, token: str | None = None) -> dict[str, Any]:
    global _SERVER, _TOKEN
    if _SERVER is not None:
        return {"running": True, "host": host, "port": port, "token_configured": _TOKEN is not None}
    _TOKEN = token
    _SERVER = ThreadingHTTPServer((host, int(port)), BridgeHandler)
    thread = threading.Thread(target=_SERVER.serve_forever, name="FreeCAD MCP GUI Bridge", daemon=True)
    thread.start()
    return {"running": True, "host": host, "port": port, "token_configured": token is not None}


def stop_bridge() -> dict[str, Any]:
    global _SERVER
    if _SERVER is None:
        return {"running": False}
    _SERVER.shutdown()
    _SERVER.server_close()
    _SERVER = None
    return {"running": False}


if __name__ == "__main__":
    print(start_bridge())
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        print(stop_bridge())
