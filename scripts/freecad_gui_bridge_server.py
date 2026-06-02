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
from pathlib import Path
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 48777
BRIDGE_API_VERSION = 3

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


def document_summary(doc: Any) -> dict[str, Any] | None:
    if doc is None:
        return None
    return {
        "name": getattr(doc, "Name", None),
        "label": getattr(doc, "Label", None),
        "file_name": getattr(doc, "FileName", None),
        "object_count": len(getattr(doc, "Objects", []) or []),
        "active_object": doc.ActiveObject.Name if getattr(doc, "ActiveObject", None) else None,
    }


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
    return document_summary(doc)


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


def safe_shape_len(shape: Any, attr: str) -> int:
    try:
        return len(getattr(shape, attr, []) or [])
    except Exception:
        return 0


def gui_shape_summary(shape: Any) -> dict[str, Any] | None:
    if shape is None:
        return None
    try:
        is_null = bool(shape.isNull())
    except Exception:
        is_null = False
    valid = None
    try:
        valid = bool(shape.isValid())
    except Exception:
        valid = False if is_null else None
    volume = None
    if not is_null:
        try:
            volume = float(getattr(shape, "Volume", 0.0) or 0.0)
        except Exception:
            volume = None
    return {
        "valid": valid,
        "is_null": is_null,
        "solids": safe_shape_len(shape, "Solids"),
        "shells": safe_shape_len(shape, "Shells"),
        "faces": safe_shape_len(shape, "Faces"),
        "edges": safe_shape_len(shape, "Edges"),
        "vertices": safe_shape_len(shape, "Vertexes"),
        "volume": volume,
    }


def object_summary(obj: Any) -> dict[str, Any]:
    shape = getattr(obj, "Shape", None)
    return {
        "name": getattr(obj, "Name", None),
        "label": getattr(obj, "Label", None),
        "type_id": getattr(obj, "TypeId", None),
        "shape": gui_shape_summary(shape),
    }


def object_ref(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    return {
        "name": getattr(obj, "Name", None),
        "label": getattr(obj, "Label", None),
        "type_id": getattr(obj, "TypeId", None),
    }


def resolve_object_for_label_update(doc: Any, selector: Any) -> Any:
    raw = str(selector or "")
    if not raw:
        raise ValueError("object_name is required")
    obj = doc.getObject(raw)
    if obj is not None:
        return obj
    matches = [candidate for candidate in doc.Objects if getattr(candidate, "Label", None) == raw]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError("object label is ambiguous: " + raw)
    raise ValueError("object not found: " + raw)


def ensure_unique_label(doc: Any, obj: Any, label: str) -> None:
    obj_name = getattr(obj, "Name", None)
    for candidate in doc.Objects:
        if getattr(candidate, "Name", None) != obj_name and getattr(candidate, "Label", None) == label:
            raise ValueError("label already exists on object: " + str(getattr(candidate, "Name", candidate)))


def document_from_params(params: dict[str, Any]) -> Any:
    import FreeCAD as App

    doc_name = params.get("document_name")
    if doc_name:
        doc = App.getDocument(str(doc_name))
        if doc is None:
            raise ValueError("document not found: " + str(doc_name))
        return doc
    return App.activeDocument()


def gui_document_for(doc: Any) -> Any:
    import FreeCADGui as Gui

    if doc is not None:
        try:
            gui_doc = Gui.getDocument(doc.Name)
            if gui_doc is not None:
                return gui_doc
        except Exception:
            pass
    return Gui.activeDocument()


def is_sketch_object(obj: Any) -> bool:
    return str(getattr(obj, "TypeId", "")).startswith("Sketcher::SketchObject")


def is_partdesign_body(obj: Any) -> bool:
    return str(getattr(obj, "TypeId", "")) == "PartDesign::Body"


def active_edit_state(doc: Any) -> dict[str, Any]:
    gui_doc = gui_document_for(doc)
    edit_vp = None
    edit_obj = None
    subname = None
    subelement = None
    mode = None
    if gui_doc is not None:
        try:
            info = getattr(gui_doc, "InEditInfo", None)
            if info:
                edit_obj = info[0] if len(info) > 0 else None
                subname = info[1] if len(info) > 1 else None
                subelement = info[2] if len(info) > 2 else None
                mode = int(info[3]) if len(info) > 3 else None
        except Exception:
            pass
        try:
            edit_vp = gui_doc.getInEdit()
        except Exception:
            edit_vp = None
        if edit_obj is None and edit_vp is not None:
            edit_obj = getattr(edit_vp, "Object", None)
    return {
        "in_edit": edit_obj is not None or edit_vp is not None,
        "object": object_ref(edit_obj),
        "view_provider_type": type(edit_vp).__name__ if edit_vp is not None else None,
        "subname": subname,
        "subelement": subelement,
        "mode": mode,
    }


def safe_int_list(value: Any) -> list[int]:
    try:
        return [int(item) for item in (value or [])]
    except Exception:
        return []


def bounded_max_items(params: dict[str, Any], default: int = 50) -> int:
    try:
        raw = int(params.get("max_items", default))
    except Exception:
        raw = default
    return max(1, min(200, raw))


def constraint_summary(constraint: Any, index: int) -> dict[str, Any]:
    result: dict[str, Any] = {"index": index}
    for attr in ("Type", "Name", "First", "FirstPos", "Second", "SecondPos", "Third", "ThirdPos", "Value", "IsDriving"):
        try:
            value = getattr(constraint, attr)
        except Exception:
            continue
        try:
            json.dumps(value)
            result[attr[0].lower() + attr[1:]] = value
        except Exception:
            result[attr[0].lower() + attr[1:]] = str(value)
    return result


def geometry_summary(geometry: Any, index: int) -> dict[str, Any]:
    result = {"index": index, "type": type(geometry).__name__, "repr": repr(geometry)}
    for attr in ("Construction", "Tag", "Layer"):
        try:
            value = getattr(geometry, attr)
        except Exception:
            continue
        try:
            json.dumps(value)
            result[attr[0].lower() + attr[1:]] = value
        except Exception:
            result[attr[0].lower() + attr[1:]] = str(value)
    return result


def sketch_summary(sketch: Any, params: dict[str, Any]) -> dict[str, Any]:
    max_items = bounded_max_items(params)
    refresh = bool(params.get("refresh_diagnostics", False))
    solve_code = None
    refresh_errors = []
    if refresh:
        for label, call in (
            ("solve", lambda: sketch.solve()),
            ("detectMissingPointOnPointConstraints", lambda: sketch.detectMissingPointOnPointConstraints(float(params.get("precision", 1e-4)), bool(params.get("include_construction", True)))),
            ("analyseMissingPointOnPointCoincident", lambda: sketch.analyseMissingPointOnPointCoincident(float(params.get("angle_precision", 0.3926990817)))),
            ("detectMissingVerticalHorizontalConstraints", lambda: sketch.detectMissingVerticalHorizontalConstraints(float(params.get("angle_precision", 0.3926990817)))),
            ("detectMissingEqualityConstraints", lambda: sketch.detectMissingEqualityConstraints(float(params.get("precision", 1e-4)))),
        ):
            try:
                value = call()
                if label == "solve":
                    solve_code = int(value)
            except Exception as exc:
                refresh_errors.append({"operation": label, "error": str(exc)})

    geometry = list(getattr(sketch, "Geometry", []) or [])
    constraints = list(getattr(sketch, "Constraints", []) or [])
    dof = getattr(sketch, "DoF", getattr(sketch, "DegreesOfFreedom", None))
    try:
        dof = int(dof) if dof is not None else None
    except Exception:
        pass

    result: dict[str, Any] = {
        "object": object_summary(sketch),
        "geometry_count": len(geometry),
        "constraint_count": len(constraints),
        "degrees_of_freedom": dof,
        "fully_constrained": dof == 0 if isinstance(dof, int) else None,
        "open_vertices": [point for point in (vector_list(v) for v in getattr(sketch, "OpenVertices", []) or []) if point is not None],
        "conflicting_constraints": safe_int_list(getattr(sketch, "ConflictingConstraints", [])),
        "redundant_constraints": safe_int_list(getattr(sketch, "RedundantConstraints", [])),
        "partially_redundant_constraints": safe_int_list(getattr(sketch, "PartiallyRedundantConstraints", [])),
        "malformed_constraints": safe_int_list(getattr(sketch, "MalformedConstraints", [])),
        "missing_point_on_point": list(getattr(sketch, "MissingPointOnPointConstraints", []) or []),
        "missing_vertical_horizontal": list(getattr(sketch, "MissingVerticalHorizontalConstraints", []) or []),
        "missing_line_equality": list(getattr(sketch, "MissingLineEqualityConstraints", []) or []),
        "missing_radius": list(getattr(sketch, "MissingRadiusConstraints", []) or []),
        "refresh_diagnostics": refresh,
        "solve_code": solve_code,
        "refresh_errors": refresh_errors,
    }
    try:
        result["dependent_geometry"] = [list(pair) for pair in sketch.getGeometryWithDependentParameters()]
    except Exception:
        result["dependent_geometry"] = []
    if bool(params.get("include_geometry", False)):
        result["geometry"] = [geometry_summary(item, index) for index, item in enumerate(geometry[:max_items])]
        result["geometry_truncated"] = len(geometry) > max_items
    if bool(params.get("include_constraints", False)):
        result["constraints"] = [constraint_summary(item, index) for index, item in enumerate(constraints[:max_items])]
        result["constraints_truncated"] = len(constraints) > max_items
    return result


def body_contains(body: Any, obj: Any) -> bool:
    if body is None or obj is None:
        return False
    try:
        return bool(body.hasObject(obj))
    except Exception:
        pass
    try:
        return obj in (getattr(body, "Group", []) or [])
    except Exception:
        return False


def view_object_for(obj: Any) -> Any:
    try:
        return getattr(obj, "ViewObject", None)
    except Exception:
        return None


def object_visibility(obj: Any) -> bool | None:
    view_obj = view_object_for(obj)
    if view_obj is None or not hasattr(view_obj, "Visibility"):
        return None
    try:
        return bool(view_obj.Visibility)
    except Exception:
        return None


def set_object_visibility(obj: Any, visible: bool) -> dict[str, Any]:
    before = object_visibility(obj)
    result = {
        "object": object_ref(obj),
        "before": before,
        "after": before,
        "changed": False,
        "settable": False,
    }
    view_obj = view_object_for(obj)
    if view_obj is None or not hasattr(view_obj, "Visibility"):
        return result
    result["settable"] = True
    try:
        view_obj.Visibility = bool(visible)
        after = object_visibility(obj)
        result["after"] = after
        result["changed"] = before != after
    except Exception as exc:
        result["error"] = str(exc)
    return result


def is_helper_display_object(obj: Any) -> bool:
    type_id = str(getattr(obj, "TypeId", ""))
    if type_id in {"App::Origin", "App::Line", "App::Plane", "App::Point"}:
        return True
    return type_id.startswith("Sketcher::")


def has_renderable_shape(obj: Any) -> bool:
    summary = gui_shape_summary(getattr(obj, "Shape", None))
    if not summary or summary.get("is_null"):
        return False
    return any(int(summary.get(key) or 0) > 0 for key in ("solids", "shells", "faces", "edges"))


def append_unique_object(objects: list[Any], obj: Any) -> None:
    if obj is None:
        return
    name = getattr(obj, "Name", None)
    if any(getattr(item, "Name", None) == name for item in objects):
        return
    objects.append(obj)


def containing_bodies(doc: Any, obj: Any) -> list[Any]:
    if doc is None or obj is None:
        return []
    return [candidate for candidate in doc.Objects if is_partdesign_body(candidate) and body_contains(candidate, obj)]


def visibility_targets(doc: Any, params: dict[str, Any]) -> list[Any]:
    if doc is None:
        return []
    scope = str(params.get("scope") or params.get("visibility_scope") or "final")
    if scope not in {"final", "all_geometry", "all"}:
        raise ValueError("unsupported visibility scope: " + scope)

    if scope == "all":
        return [obj for obj in doc.Objects if object_visibility(obj) is not None]
    if scope == "all_geometry":
        return [obj for obj in doc.Objects if object_visibility(obj) is not None and has_renderable_shape(obj)]

    targets: list[Any] = []
    object_name = params.get("object_name")
    if object_name:
        target = doc.getObject(str(object_name))
        if target is None:
            raise ValueError("object not found: " + str(object_name))
        append_unique_object(targets, target)
        for body in containing_bodies(doc, target):
            append_unique_object(targets, body)
            append_unique_object(targets, getattr(body, "Tip", None))
        return targets

    active = getattr(doc, "ActiveObject", None)
    if active is not None and not is_helper_display_object(active):
        append_unique_object(targets, active)
        for body in containing_bodies(doc, active):
            append_unique_object(targets, body)
            append_unique_object(targets, getattr(body, "Tip", None))

    for body in [obj for obj in doc.Objects if is_partdesign_body(obj)]:
        append_unique_object(targets, body)
        append_unique_object(targets, getattr(body, "Tip", None))

    if not targets:
        for obj in doc.Objects:
            if not is_helper_display_object(obj) and has_renderable_shape(obj):
                append_unique_object(targets, obj)
    return [obj for obj in targets if object_visibility(obj) is not None]


def ensure_visibility(doc: Any, params: dict[str, Any]) -> dict[str, Any]:
    targets = visibility_targets(doc, params)
    applied = [set_object_visibility(obj, True) for obj in targets]
    visible_count = sum(1 for item in applied if item.get("after") is True)
    try:
        import FreeCADGui as Gui

        Gui.updateGui()
    except Exception:
        pass
    return {
        "requested": True,
        "scope": str(params.get("scope") or params.get("visibility_scope") or "final"),
        "target_count": len(targets),
        "visible_count": visible_count,
        "applied": applied,
    }


def link_summary(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "Name") and hasattr(value, "TypeId"):
        return object_ref(value)
    if isinstance(value, (list, tuple)):
        return [link_summary(item) for item in value[:10]]
    return str(value)


def body_feature_summary(body: Any, feature: Any, tip: Any) -> dict[str, Any]:
    result = object_summary(feature)
    result["is_tip"] = feature is tip
    try:
        result["after_tip"] = bool(body.isAfterInsertPoint(feature))
    except Exception:
        result["after_tip"] = None
    links = {}
    for attr in ("Profile", "BaseFeature", "Base", "Sketch", "Support"):
        try:
            value = getattr(feature, attr)
        except Exception:
            continue
        if value is not None:
            links[attr[0].lower() + attr[1:]] = link_summary(value)
    if links:
        result["links"] = links
    return result


def body_summary(body: Any, params: dict[str, Any]) -> dict[str, Any]:
    max_items = bounded_max_items(params)
    group = list(getattr(body, "Group", []) or [])
    tip = getattr(body, "Tip", None)
    origin = getattr(body, "Origin", None)
    result: dict[str, Any] = {
        "object": object_summary(body),
        "tip": object_ref(tip),
        "base_feature": object_ref(getattr(body, "BaseFeature", None)),
        "feature_count": len(group),
        "origin": object_ref(origin),
    }
    try:
        result["is_solid"] = bool(body.isSolid())
    except Exception:
        result["is_solid"] = None
    if origin is not None:
        origin_group = list(getattr(origin, "Group", []) or getattr(origin, "OriginFeatures", []) or [])
        result["origin_features"] = [object_ref(item) for item in origin_group[:max_items]]
    if bool(params.get("include_features", True)):
        result["features"] = [body_feature_summary(body, feature, tip) for feature in group[:max_items]]
        result["features_truncated"] = len(group) > max_items
    return result


def infer_body_for_object(bodies: list[Any], obj: Any) -> Any:
    if obj is None:
        return None
    if is_partdesign_body(obj):
        return obj
    for body in bodies:
        if body_contains(body, obj):
            return body
    return None


def resolve_sketch(doc: Any, params: dict[str, Any], edit: dict[str, Any] | None = None, selected: list[Any] | None = None) -> Any:
    if doc is None:
        return None
    sketch_name = params.get("sketch_name")
    if sketch_name:
        sketch = doc.getObject(str(sketch_name))
        if sketch is None or not is_sketch_object(sketch):
            raise ValueError("sketch not found: " + str(sketch_name))
        return sketch
    if edit and edit.get("object"):
        edit_name = edit["object"].get("name")
        edit_obj = doc.getObject(str(edit_name)) if edit_name else None
        if is_sketch_object(edit_obj):
            return edit_obj
    for sel in selected or []:
        obj = getattr(sel, "Object", None)
        if is_sketch_object(obj):
            return obj
    active = getattr(doc, "ActiveObject", None)
    if is_sketch_object(active):
        return active
    sketches = [obj for obj in doc.Objects if is_sketch_object(obj)]
    if len(sketches) == 1:
        return sketches[0]
    return None


def resolve_body(
    doc: Any,
    params: dict[str, Any],
    edit: dict[str, Any] | None = None,
    selected: list[Any] | None = None,
    bodies: list[Any] | None = None,
) -> Any:
    if doc is None:
        return None
    body_candidates = bodies if bodies is not None else [obj for obj in doc.Objects if is_partdesign_body(obj)]
    body_name = params.get("body_name")
    if body_name:
        body = doc.getObject(str(body_name))
        if body is None or not is_partdesign_body(body):
            raise ValueError("body not found: " + str(body_name))
        return body
    if edit and edit.get("object"):
        edit_name = edit["object"].get("name")
        edit_obj = doc.getObject(str(edit_name)) if edit_name else None
        body = infer_body_for_object(body_candidates, edit_obj)
        if body is not None:
            return body
    body = infer_body_for_object(body_candidates, getattr(doc, "ActiveObject", None))
    if body is not None:
        return body
    for sel in selected or []:
        body = infer_body_for_object(body_candidates, getattr(sel, "Object", None))
        if body is not None:
            return body
    if len(body_candidates) == 1:
        return body_candidates[0]
    return None


def activate_workbench(name: str, requested: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {"requested": bool(requested), "name": name, "activated": False}
    if not requested:
        return result
    try:
        import FreeCADGui as Gui

        Gui.activateWorkbench(name)
        result["activated"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


def select_object(doc: Any, obj: Any, clear: bool = True) -> dict[str, Any]:
    import FreeCADGui as Gui

    if doc is None or obj is None:
        return {"selected": False}
    if clear:
        Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, obj.Name, "")
    return {"selected": True, "document_name": doc.Name, "object_name": obj.Name}


def fit_view_if_requested(gui_doc: Any, requested: bool, selection_only: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"requested": bool(requested), "fit": None}
    if not requested:
        return result
    if gui_doc is None:
        raise ValueError("no active GUI document")
    view = gui_doc.activeView()
    if view is None:
        raise ValueError("no active GUI view")
    if selection_only and hasattr(view, "fitSelection"):
        view.fitSelection()
        result["fit"] = "selection"
    else:
        view.fitAll()
        result["fit"] = "all"
    return result


def clamped_int(params: dict[str, Any], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(params.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def bounded_text(value: Any, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + "...<truncated>"


def call_noarg(obj: Any, method_name: str) -> Any:
    attr = getattr(obj, method_name, None)
    if not callable(attr):
        return None
    return attr()


def widget_scalar_fields(widget: Any, text_max_length: int) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, method in (
        ("object_name", "objectName"),
        ("window_title", "windowTitle"),
        ("title", "title"),
        ("text", "text"),
        ("tool_tip", "toolTip"),
        ("status_tip", "statusTip"),
        ("placeholder_text", "placeholderText"),
        ("current_text", "currentText"),
    ):
        try:
            value = call_noarg(widget, method)
        except Exception:
            continue
        text = bounded_text(value, text_max_length)
        if text is not None:
            fields[key] = text
    for key, method in (
        ("visible", "isVisible"),
        ("enabled", "isEnabled"),
        ("checked", "isChecked"),
    ):
        try:
            value = call_noarg(widget, method)
        except Exception:
            continue
        if value is not None:
            fields[key] = bool(value)
    for key, method in (("value", "value"), ("minimum", "minimum"), ("maximum", "maximum")):
        try:
            value = call_noarg(widget, method)
        except Exception:
            continue
        if isinstance(value, (int, float)):
            fields[key] = value
    return fields


def widget_summary(
    widget: Any,
    *,
    depth: int,
    max_depth: int,
    max_children: int,
    text_max_length: int,
    seen: set[int] | None = None,
) -> dict[str, Any]:
    seen = seen or set()
    widget_id = id(widget)
    if widget_id in seen:
        return {"type": type(widget).__name__, "recursive": True}
    seen.add(widget_id)

    result: dict[str, Any] = {"type": type(widget).__name__, "repr": bounded_text(repr(widget), text_max_length)}
    result.update(widget_scalar_fields(widget, text_max_length))
    try:
        children = list(call_noarg(widget, "children") or [])
    except Exception:
        children = []
    result["child_count"] = len(children)
    if depth < max_depth and children:
        result["children"] = [
            widget_summary(
                child,
                depth=depth + 1,
                max_depth=max_depth,
                max_children=max_children,
                text_max_length=text_max_length,
                seen=seen,
            )
            for child in children[:max_children]
        ]
        result["children_truncated"] = len(children) > max_children
    return result


def looks_like_task_widget(widget: Any, text_max_length: int) -> bool:
    fields = widget_scalar_fields(widget, text_max_length)
    haystack = " ".join([type(widget).__name__, *(str(value) for value in fields.values())]).lower()
    return "task" in haystack or "combi view" in haystack or "combo view" in haystack


def collect_task_widgets(root: Any, params: dict[str, Any]) -> list[Any]:
    max_widgets = clamped_int(params, "max_widgets", 12, 1, 50)
    text_max_length = clamped_int(params, "text_max_length", 120, 20, 500)
    result = []
    queue_items = [root]
    seen: set[int] = set()
    while queue_items and len(result) < max_widgets:
        widget = queue_items.pop(0)
        widget_id = id(widget)
        if widget_id in seen:
            continue
        seen.add(widget_id)
        if looks_like_task_widget(widget, text_max_length):
            result.append(widget)
        try:
            queue_items.extend(list(call_noarg(widget, "children") or []))
        except Exception:
            pass
    return result


def value_or_widget_summary(value: Any, params: dict[str, Any]) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    max_depth = clamped_int(params, "max_depth", 2, 0, 4)
    max_children = clamped_int(params, "max_children", 16, 1, 80)
    text_max_length = clamped_int(params, "text_max_length", 120, 20, 500)
    if callable(getattr(value, "children", None)) or callable(getattr(value, "objectName", None)):
        return widget_summary(
            value,
            depth=0,
            max_depth=max_depth,
            max_children=max_children,
            text_max_length=text_max_length,
        )
    return {"type": type(value).__name__, "repr": bounded_text(repr(value), text_max_length)}


def rpc_feature_task_state(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    main_window = Gui.getMainWindow()
    max_depth = clamped_int(params, "max_depth", 2, 0, 4)
    max_children = clamped_int(params, "max_children", 16, 1, 80)
    text_max_length = clamped_int(params, "text_max_length", 120, 20, 500)
    include_widget_tree = bool(params.get("include_widget_tree", True))

    control_summary: dict[str, Any] = {"available": hasattr(Gui, "Control")}
    control = getattr(Gui, "Control", None)
    if control is not None:
        control_summary["methods"] = [
            name
            for name in ("activeDialog", "showDialog", "closeDialog")
            if callable(getattr(control, name, None))
        ]
        if callable(getattr(control, "activeDialog", None)):
            try:
                active_dialog = control.activeDialog()
                control_summary["active_dialog"] = value_or_widget_summary(active_dialog, params)
                control_summary["has_active_dialog"] = bool(active_dialog)
            except Exception as exc:
                control_summary["active_dialog_error"] = str(exc)

    task_widgets = collect_task_widgets(main_window, params) if main_window is not None else []
    task_summaries = [
        widget_summary(
            widget,
            depth=0,
            max_depth=max_depth if include_widget_tree else 0,
            max_children=max_children,
            text_max_length=text_max_length,
        )
        for widget in task_widgets
    ]
    return {
        "document": active_document_summary(),
        "edit": active_edit_state(doc),
        "active_workbench": active_workbench_summary(),
        "control": control_summary,
        "main_window": widget_summary(
            main_window,
            depth=0,
            max_depth=0,
            max_children=max_children,
            text_max_length=text_max_length,
        )
        if main_window is not None
        else None,
        "task_widgets": task_summaries,
        "task_widget_count": len(task_summaries),
    }


def rpc_status(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCAD as App

    bridge = {
        "running": _SERVER is not None,
        "token_configured": _TOKEN is not None,
        "api_version": BRIDGE_API_VERSION,
        "methods": sorted(RPC_METHODS) if "RPC_METHODS" in globals() else [],
    }
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


def existing_fcstd_path(raw_path: Any) -> Path:
    text = str(raw_path or "").strip()
    if not text:
        raise ValueError("document_path is required")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise ValueError("document_path must be absolute")
    if path.suffix.lower() != ".fcstd":
        raise ValueError("document_path must point to a .FCStd file")
    if not path.exists():
        raise ValueError("document_path does not exist: " + str(path))
    if not path.is_file():
        raise ValueError("document_path must be a file: " + str(path))
    return path.resolve()


def document_file_matches(doc: Any, path: Path) -> bool:
    file_name = str(getattr(doc, "FileName", "") or "")
    if not file_name:
        return False
    try:
        return Path(file_name).resolve() == path
    except Exception:
        return str(Path(file_name)) == str(path)


def find_open_document_by_file(path: Path) -> Any:
    import FreeCAD as App

    try:
        documents = App.listDocuments()
    except Exception:
        documents = {}
    for doc in (documents.values() if isinstance(documents, dict) else []):
        if document_file_matches(doc, path):
            return doc
    return None


def activate_document(doc: Any) -> Any:
    import FreeCAD as App
    import FreeCADGui as Gui

    if doc is None:
        return Gui.activeDocument()
    try:
        App.setActiveDocument(doc.Name)
    except Exception:
        pass
    try:
        gui_doc = Gui.getDocument(doc.Name)
        if gui_doc is not None:
            Gui.ActiveDocument = gui_doc
            return gui_doc
    except Exception:
        pass
    return gui_document_for(doc)


def rpc_document_open(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCAD as App
    import FreeCADGui as Gui

    path = existing_fcstd_path(params.get("document_path"))
    activate = bool(params.get("activate", True))
    fit_view = bool(params.get("fit_view", True))
    ensure_visible = bool(params.get("ensure_visible", True))

    doc = find_open_document_by_file(path)
    already_open = doc is not None
    if doc is None:
        doc = App.openDocument(str(path))
        if doc is None:
            doc = find_open_document_by_file(path) or App.activeDocument()
    if doc is None:
        raise RuntimeError("FreeCAD did not open document: " + str(path))

    gui_doc = activate_document(doc) if activate else (gui_document_for(doc) or Gui.activeDocument())
    visibility: dict[str, Any] = {"requested": ensure_visible}
    if ensure_visible:
        visibility = ensure_visibility(
            doc,
            {
                "visibility_scope": params.get("visibility_scope", "final"),
                "object_name": params.get("object_name"),
            },
        )
    fit: dict[str, Any] = {"requested": fit_view, "fit": None}
    if fit_view:
        try:
            fit = fit_view_if_requested(gui_doc, True)
        except Exception as exc:
            fit = {"requested": True, "fit": None, "error": str(exc)}

    return {
        "opened": not already_open,
        "already_open": already_open,
        "document_path": str(path),
        "activated": activate,
        "document": document_summary(doc),
        "active_document": active_document_summary(),
        "visibility": visibility,
        "fit": fit,
        "active_view": active_view_summary(),
    }


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


def rpc_view_orientation_set(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    orientation = str(params.get("orientation") or "isometric").lower()
    methods = {
        "isometric": "viewIsometric",
        "front": "viewFront",
        "rear": "viewRear",
        "back": "viewRear",
        "top": "viewTop",
        "bottom": "viewBottom",
        "left": "viewLeft",
        "right": "viewRight",
    }
    method_name = methods.get(orientation)
    if method_name is None:
        raise ValueError("unsupported view orientation: " + orientation)
    gui_doc = Gui.activeDocument()
    if gui_doc is None:
        raise ValueError("no active GUI document")
    view = gui_doc.activeView()
    if view is None:
        raise ValueError("no active GUI view")
    method = getattr(view, method_name, None)
    if not callable(method):
        raise ValueError("active GUI view does not support " + method_name)
    method()
    try:
        Gui.updateGui()
    except Exception:
        pass
    fit = fit_view_if_requested(
        gui_doc,
        bool(params.get("fit_view", True)),
        selection_only=bool(params.get("selection_only", False)),
    )
    return {
        "orientation": orientation,
        "view_method": method_name,
        "fit": fit,
        "active_view": active_view_summary(),
    }


def rpc_visibility_ensure(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        raise ValueError("no active document")
    visibility = ensure_visibility(doc, params)
    selection = {"selected": False}
    targets = visibility_targets(doc, params)
    if targets and bool(params.get("select", False)):
        selection = select_object(doc, targets[0], clear=True)
    gui_doc = gui_document_for(doc) or Gui.activeDocument()
    fit = fit_view_if_requested(gui_doc, bool(params.get("fit_view", True)), selection_only=False)
    return {
        "document": active_document_summary(),
        "visibility": visibility,
        "selection": selection,
        "fit": fit,
        "active_view": active_view_summary(),
    }


def rpc_view_snapshot(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    raw_path = str(params.get("output_path") or "").strip()
    if not raw_path:
        raise ValueError("output_path is required")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError("output_path must be absolute")

    image_format = str(params.get("format") or path.suffix.lstrip(".") or "png").lower()
    if image_format == "jpeg":
        image_format = "jpg"
    if image_format not in {"png", "jpg", "bmp"}:
        raise ValueError("unsupported image format: " + image_format)
    if not path.suffix:
        path = path.with_suffix("." + image_format)
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "jpeg":
        suffix = "jpg"
    if suffix not in {"png", "jpg", "bmp"}:
        raise ValueError("unsupported output_path image extension: " + path.suffix)
    if suffix != image_format:
        raise ValueError("format does not match output_path extension")
    if not path.parent.exists():
        raise ValueError("Directory where to save image doesn't exist")
    existed = path.exists()
    if existed and not bool(params.get("overwrite", False)):
        raise ValueError("output_path already exists; pass overwrite=true")

    gui_doc = Gui.activeDocument()
    if gui_doc is None:
        raise ValueError("no active GUI document")
    view = gui_doc.activeView()
    if view is None:
        raise ValueError("no active GUI view")

    width = clamped_int(params, "width", 1280, 64, 8192)
    height = clamped_int(params, "height", 720, 64, 8192)
    background = str(params.get("background") or "Current")
    if background not in {"Current", "Transparent", "White", "Black"}:
        raise ValueError("unsupported background: " + background)

    fit = fit_view_if_requested(gui_doc, bool(params.get("fit_view", False)), bool(params.get("selection_only", False)))
    view.saveImage(str(path), width, height, background)
    if not path.exists():
        raise RuntimeError("FreeCAD did not create snapshot: " + str(path))
    stat = path.stat()
    return {
        "snapshot": {
            "path": str(path),
            "width": width,
            "height": height,
            "format": image_format,
            "background": background,
            "bytes": int(stat.st_size),
            "overwritten": existed,
        },
        "fit": fit,
        "document": active_document_summary(),
        "active_view": active_view_summary(),
    }


def rpc_primitive_create(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCAD as App
    import FreeCADGui as Gui

    primitive = str(params.get("primitive") or "cylinder").lower()
    if primitive != "cylinder":
        raise ValueError("unsupported GUI primitive: " + primitive)

    doc = App.activeDocument()
    if doc is None:
        doc_name = str(params.get("document_name") or "MCPGuiDocument")
        doc = App.newDocument(doc_name)
        Gui.ActiveDocument = Gui.getDocument(doc.Name)

    object_name = str(params.get("object_name") or "McpCylinder")
    obj = doc.addObject("Part::Cylinder", object_name)
    obj.Radius = float(params.get("radius", 5.0))
    obj.Height = float(params.get("height", 10.0))
    label = params.get("label")
    if label:
        obj.Label = str(label)

    placement = params.get("placement") or {}
    base = placement.get("base") if isinstance(placement, dict) else None
    if isinstance(base, (list, tuple)) and len(base) == 3:
        obj.Placement.Base = App.Vector(float(base[0]), float(base[1]), float(base[2]))

    doc.recompute()
    try:
        gui_doc = Gui.getDocument(doc.Name)
        if gui_doc is not None:
            Gui.ActiveDocument = gui_doc
    except Exception:
        gui_doc = Gui.activeDocument()

    if bool(params.get("select", True)):
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(doc.Name, obj.Name, "")
    if bool(params.get("fit_view", True)):
        gui_doc = Gui.activeDocument()
        view = gui_doc.activeView() if gui_doc is not None else None
        if view is not None:
            view.fitAll()

    return {
        "primitive": primitive,
        "document": active_document_summary(),
        "object": object_summary(obj),
    }


def rpc_object_label_set(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        raise ValueError("no active document")
    obj = resolve_object_for_label_update(doc, params.get("object_name"))
    label = str(params.get("label") or "").strip()
    if not label:
        raise ValueError("label is required")
    if bool(params.get("require_unique", True)):
        ensure_unique_label(doc, obj, label)

    before = {"name": obj.Name, "label": obj.Label}
    doc.openTransaction("MCP GUI set object label")
    try:
        obj.Label = label
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise

    selection = select_object(doc, obj, clear=True) if bool(params.get("select", False)) else {"selected": False}
    gui_doc = gui_document_for(doc) or Gui.activeDocument()
    view = fit_view_if_requested(gui_doc, bool(params.get("fit_view", False)), selection_only=True)
    return {
        "before": before,
        "after": {"name": obj.Name, "label": obj.Label},
        "object": object_summary(obj),
        "selection": selection,
        "view": view,
        "document": active_document_summary(),
    }


def rpc_sketch_state(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        return {"document": None, "edit": active_edit_state(None), "active_sketch": None, "sketches": []}

    edit = active_edit_state(doc)
    sketches = [obj for obj in doc.Objects if is_sketch_object(obj)]
    selected = Gui.Selection.getSelectionEx(doc.Name, 0)
    sketch = resolve_sketch(doc, params, edit, selected)

    return {
        "document": active_document_summary(),
        "edit": edit,
        "active_sketch": sketch_summary(sketch, params) if sketch is not None else None,
        "sketches": [object_summary(item) for item in sketches],
        "selection": [selection_record(sel) for sel in selected],
    }


def rpc_sketch_enter(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        raise ValueError("no active document")
    gui_doc = gui_document_for(doc)
    if gui_doc is None:
        raise ValueError("no active GUI document")

    selected = Gui.Selection.getSelectionEx(doc.Name, 0)
    before = active_edit_state(doc)
    sketch = resolve_sketch(doc, params, before, selected)
    if sketch is None:
        raise ValueError("sketch_name is required when no active, selected, or unique sketch can be inferred")

    before_name = (before.get("object") or {}).get("name")
    already_in_edit = before.get("in_edit") and before_name == getattr(sketch, "Name", None)
    if before.get("in_edit") and not already_in_edit:
        if not bool(params.get("reset_existing", True)):
            raise ValueError("another object is already in edit mode: " + str(before_name))
        gui_doc.resetEdit()

    workbench = activate_workbench("SketcherWorkbench", bool(params.get("activate_workbench", True)))
    if not already_in_edit:
        edit_mode = params.get("edit_mode")
        try:
            if edit_mode is None:
                gui_doc.setEdit(sketch.Name)
            else:
                gui_doc.setEdit(sketch.Name, int(edit_mode))
        except TypeError:
            gui_doc.setEdit(sketch.Name)

    try:
        doc.ActiveObject = sketch
    except Exception:
        pass
    selection = select_object(doc, sketch, clear=True) if bool(params.get("select", True)) else {"selected": False}
    view = fit_view_if_requested(gui_doc, bool(params.get("fit_view", False)), selection_only=True)

    return {
        "entered": not already_in_edit,
        "already_in_edit": bool(already_in_edit),
        "before": before,
        "after": active_edit_state(doc),
        "workbench": workbench,
        "selection": selection,
        "view": view,
        "document": active_document_summary(),
        "sketch": sketch_summary(sketch, params),
    }


def rpc_sketch_leave(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        raise ValueError("no active document")
    gui_doc = gui_document_for(doc)
    if gui_doc is None:
        raise ValueError("no active GUI document")

    selected = Gui.Selection.getSelectionEx(doc.Name, 0)
    before = active_edit_state(doc)
    sketch = resolve_sketch(doc, params, before, selected)
    if params.get("sketch_name") and before.get("in_edit"):
        before_name = (before.get("object") or {}).get("name")
        if before_name and before_name != getattr(sketch, "Name", None):
            raise ValueError("active edit object is not requested sketch: " + str(before_name))

    left = False
    if before.get("in_edit"):
        gui_doc.resetEdit()
        left = True
    if bool(params.get("recompute", True)):
        doc.recompute()
    selection = select_object(doc, sketch, clear=True) if sketch is not None and bool(params.get("select", False)) else {"selected": False}
    view = fit_view_if_requested(gui_doc, bool(params.get("fit_view", False)), selection_only=True)

    return {
        "left": left,
        "before": before,
        "after": active_edit_state(doc),
        "selection": selection,
        "view": view,
        "document": active_document_summary(),
        "sketch": sketch_summary(sketch, params) if sketch is not None else None,
    }


def rpc_partdesign_state(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        return {"document": None, "edit": active_edit_state(None), "active_body": None, "bodies": []}

    edit = active_edit_state(doc)
    bodies = [obj for obj in doc.Objects if is_partdesign_body(obj)]
    selected = Gui.Selection.getSelectionEx(doc.Name, 0)
    active_body = resolve_body(doc, params, edit, selected, bodies)

    return {
        "document": active_document_summary(),
        "edit": edit,
        "active_body": body_summary(active_body, params) if active_body is not None else None,
        "bodies": [body_summary(body, params) for body in bodies],
        "selection": [selection_record(sel) for sel in selected],
    }


def rpc_body_activate(params: dict[str, Any]) -> dict[str, Any]:
    import FreeCADGui as Gui

    doc = document_from_params(params)
    if doc is None:
        raise ValueError("no active document")
    gui_doc = gui_document_for(doc)
    if gui_doc is None:
        raise ValueError("no active GUI document")

    selected = Gui.Selection.getSelectionEx(doc.Name, 0)
    edit = active_edit_state(doc)
    bodies = [obj for obj in doc.Objects if is_partdesign_body(obj)]
    body = resolve_body(doc, params, edit, selected, bodies)
    if body is None:
        raise ValueError("body_name is required when no active, selected, or unique Body can be inferred")

    workbench = activate_workbench("PartDesignWorkbench", bool(params.get("activate_workbench", True)))
    try:
        doc.ActiveObject = body
    except Exception:
        pass

    active_view_object: dict[str, Any] = {"requested": bool(params.get("set_active_view_object", True)), "set": False}
    if active_view_object["requested"]:
        view = gui_doc.activeView()
        if view is None:
            raise ValueError("no active GUI view")
        try:
            view.setActiveObject("pdbody", body)
            active_view_object["set"] = True
            try:
                active_view_object["value"] = object_ref(view.getActiveObject("pdbody"))
            except Exception:
                active_view_object["value"] = object_ref(body)
        except Exception as exc:
            active_view_object["error"] = str(exc)

    selection = select_object(doc, body, clear=True) if bool(params.get("select", True)) else {"selected": False}
    view_state = fit_view_if_requested(gui_doc, bool(params.get("fit_view", False)), selection_only=True)
    state_params = {"document_name": doc.Name, "body_name": body.Name, "include_features": params.get("include_features", True)}

    return {
        "activated": object_ref(body),
        "workbench": workbench,
        "active_view_object": active_view_object,
        "selection": selection,
        "view": view_state,
        "document": active_document_summary(),
        "partdesign": rpc_partdesign_state(state_params),
    }


RPC_METHODS = {
    "status": rpc_status,
    "active_document_get": rpc_active_document_get,
    "document_open": rpc_document_open,
    "active_view_get": rpc_active_view_get,
    "selection_get": rpc_selection_get,
    "preselection_get": rpc_preselection_get,
    "selection_set": rpc_selection_set,
    "view_fit": rpc_view_fit,
    "view_orientation_set": rpc_view_orientation_set,
    "visibility_ensure": rpc_visibility_ensure,
    "view_snapshot": rpc_view_snapshot,
    "primitive_create": rpc_primitive_create,
    "object_label_set": rpc_object_label_set,
    "sketch_state": rpc_sketch_state,
    "sketch_enter": rpc_sketch_enter,
    "sketch_leave": rpc_sketch_leave,
    "partdesign_state": rpc_partdesign_state,
    "body_activate": rpc_body_activate,
    "feature_task_state": rpc_feature_task_state,
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
