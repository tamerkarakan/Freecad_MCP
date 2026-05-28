"""Persistent FreeCADCmd worker bridge."""

from __future__ import annotations

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
from freecad_mcp.tooling import JsonObject, ToolInputError


WORKER_PREFIX = "__FREECAD_MCP_WORKER__"
MAX_WORKER_STREAM_CHARS = 12_000


FREECAD_WORKER_SCRIPT = r'''
import json
import math
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


def angle_radians(value, default=0.0):
    if value is None:
        return float(default)
    if isinstance(value, dict):
        if "radians" in value:
            return float(value["radians"])
        if "degrees" in value:
            return math.radians(float(value["degrees"]))
        if "value" in value:
            return angle_radians(value["value"], default)
    return float(value)


def angle_degrees(value, default=0.0):
    if value is None:
        return float(default)
    if isinstance(value, dict):
        if "degrees" in value:
            return float(value["degrees"])
        if "radians" in value:
            return math.degrees(float(value["radians"]))
        if "value" in value:
            return angle_degrees(value["value"], default)
    return float(value)


def sketch_arg(value):
    if isinstance(value, dict):
        if "quantity" in value:
            return App.Units.Quantity(str(value["quantity"]))
        if "degrees" in value:
            return App.Units.Quantity(str(value["degrees"]) + " deg")
        if "radians" in value:
            return float(value["radians"])
        if "value" in value:
            return sketch_arg(value["value"])
    return value


def quantity_summary(value):
    if value is None:
        return None
    return {
        "value": float(getattr(value, "Value", value)),
        "unit": str(getattr(value, "Unit", "")),
        "user_string": value.UserString if hasattr(value, "UserString") else str(value),
    }


def point_list(value):
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return [value.x, value.y, value.z]
    return list(value)


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


def mesh_summary(obj):
    mesh = getattr(obj, "Mesh", None)
    if mesh is None:
        return None
    return {
        "facets": int(getattr(mesh, "CountFacets", 0)),
        "points": int(getattr(mesh, "CountPoints", 0)),
        "is_solid": bool(mesh.isSolid()) if hasattr(mesh, "isSolid") else None,
    }


def constraint_summary(constraint, index=None):
    return {
        "index": index,
        "type": str(getattr(constraint, "Type", "")),
        "first": int(getattr(constraint, "First", -2000)),
        "first_pos": int(getattr(constraint, "FirstPos", 0)),
        "second": int(getattr(constraint, "Second", -2000)),
        "second_pos": int(getattr(constraint, "SecondPos", 0)),
        "third": int(getattr(constraint, "Third", -2000)),
        "third_pos": int(getattr(constraint, "ThirdPos", 0)),
        "value": float(getattr(constraint, "Value", 0.0)),
        "name": str(getattr(constraint, "Name", "")),
        "driving": bool(getattr(constraint, "Driving", False)),
        "active": bool(getattr(constraint, "IsActive", True)),
        "virtual_space": bool(getattr(constraint, "InVirtualSpace", False)),
        "label_distance": float(getattr(constraint, "LabelDistance", 0.0)),
        "label_position": float(getattr(constraint, "LabelPosition", 0.0)),
    }


def geometry_summary(sketch, geometry, index):
    try:
        construction = bool(sketch.getConstruction(index))
    except Exception:
        construction = None
    return {
        "index": index,
        "type_id": geometry.getTypeId().getName() if hasattr(geometry, "getTypeId") else type(geometry).__name__,
        "construction": construction,
        "repr": repr(geometry),
    }


def sketch_summary(obj):
    if getattr(obj, "TypeId", "") != "Sketcher::SketchObject":
        return None
    geometry = list(getattr(obj, "Geometry", []))
    constraints = list(getattr(obj, "Constraints", []))
    return {
        "geometry_count": len(geometry),
        "constraint_count": len(constraints),
        "degrees_of_freedom": getattr(obj, "DoF", getattr(obj, "DegreesOfFreedom", None)),
        "open_vertices": [point_list(v) for v in getattr(obj, "OpenVertices", [])],
        "conflicting_constraints": list(getattr(obj, "ConflictingConstraints", [])),
        "redundant_constraints": list(getattr(obj, "RedundantConstraints", [])),
        "partially_redundant_constraints": list(getattr(obj, "PartiallyRedundantConstraints", [])),
        "malformed_constraints": list(getattr(obj, "MalformedConstraints", [])),
        "geometry": [geometry_summary(obj, geo, idx) for idx, geo in enumerate(geometry)],
        "constraints": [constraint_summary(constraint, idx) for idx, constraint in enumerate(constraints)],
    }


def object_summary(obj):
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "visibility": bool(getattr(obj, "Visibility", False)),
        "placement": placement_summary(obj),
        "shape": shape_summary(obj),
        "mesh": mesh_summary(obj),
        "sketch": sketch_summary(obj),
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


def export_objects(objects, output_path, params):
    output_path = safe_output_path(output_path, params)
    ext = os.path.splitext(output_path)[1].lower()
    if os.path.exists(output_path) and not bool(params.get("overwrite", False)):
        raise ValueError("output exists; pass overwrite=true: " + output_path)
    if ext in {".stl", ".obj", ".ply", ".off"}:
        import Mesh

        Mesh.export(objects, output_path)
    else:
        import Import

        Import.export(objects, output_path)
    return output_path


def planar_face_from_closed_wires(shape):
    import Part

    wires = list(getattr(shape, "Wires", []) or [])
    if not wires or len(getattr(shape, "Faces", []) or []) > 0:
        return None
    if any(not wire.isClosed() for wire in wires):
        return None
    try:
        if len(wires) == 1:
            return Part.Face(wires[0])
        return Part.Face(wires)
    except Exception:
        return None


FEATURE_EXTRUDE_KEYS = {
    "solid",
    "symmetric",
    "length_fwd",
    "length_rev",
    "taper_angle",
    "taper_angle_rev",
    "reversed",
    "dir_mode",
    "face_maker_mode",
    "inner_wire_taper",
}


def uses_feature_extrude(params):
    mode = params.get("extrude_mode", "auto")
    if mode not in {"auto", "shape", "feature"}:
        raise ValueError("unsupported extrude_mode: " + str(mode))
    return mode == "feature" or any(key in params for key in FEATURE_EXTRUDE_KEYS)


def action_part_extrude_feature(doc, source, params):
    base_shape = source.Shape
    auto_solid = planar_face_from_closed_wires(base_shape) is not None
    result = doc.addObject("Part::Extrusion", params.get("result_name") or "Extrude")
    result.Base = source
    result.Dir = vector(params.get("vector"), [0, 0, 10])
    if params.get("dir_mode") is not None:
        result.DirMode = str(params["dir_mode"])
    if params.get("length_fwd") is not None:
        result.LengthFwd = float(params["length_fwd"])
    if params.get("length_rev") is not None:
        result.LengthRev = float(params["length_rev"])
    result.Solid = bool(params["solid"]) if "solid" in params else auto_solid
    if params.get("reversed") is not None:
        result.Reversed = bool(params["reversed"])
    if params.get("symmetric") is not None:
        result.Symmetric = bool(params["symmetric"])
    if params.get("taper_angle") is not None:
        result.TaperAngle = angle_degrees(params["taper_angle"])
    if params.get("taper_angle_rev") is not None:
        result.TaperAngleRev = angle_degrees(params["taper_angle_rev"])
    if params.get("face_maker_mode") is not None:
        result.FaceMakerMode = str(params["face_maker_mode"])
    if params.get("inner_wire_taper") is not None:
        result.InnerWireTaper = str(params["inner_wire_taper"])
    return result, {
        "extrude_mode": "feature",
        "solid": bool(result.Solid),
        "symmetric": bool(result.Symmetric),
        "dir_mode": str(result.DirMode),
        "length_fwd": quantity_summary(result.LengthFwd),
        "length_rev": quantity_summary(result.LengthRev),
        "taper_angle": quantity_summary(result.TaperAngle),
        "taper_angle_rev": quantity_summary(result.TaperAngleRev),
    }


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


def action_document_export(params):
    doc = get_doc(params)
    output_path = params.get("output_path")
    if not output_path:
        raise ValueError("output_path is required")
    names = params.get("object_names") or [obj.Name for obj in doc.Objects]
    objects = [get_object(doc, name) for name in names]
    exported = export_objects(objects, output_path, params)
    return {"exported_path": exported, "objects": [object_summary(obj) for obj in objects]}


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


def action_object_set_properties(params):
    doc = get_doc(params)
    obj = get_object(doc, params.get("object_name") or "")
    changed = {}
    doc.openTransaction("MCP worker set object properties")
    try:
        for key, value in (params.get("properties") or {}).items():
            if key not in obj.PropertiesList and not hasattr(obj, key):
                raise ValueError("unknown property: " + key)
            setattr(obj, key, value)
            changed[key] = value
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "changed": changed, "object": object_summary(obj), "document": document_summary(doc)}


def action_object_delete(params):
    doc = get_doc(params)
    names = params.get("object_names") or ([params["object_name"]] if params.get("object_name") else [])
    if not names:
        raise ValueError("object_name or object_names is required")
    doc.openTransaction("MCP worker delete objects")
    try:
        for name in names:
            obj = get_object(doc, name)
            doc.removeObject(obj.Name)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "deleted": names, "document": document_summary(doc)}


def action_part_boolean(params):
    doc = get_doc(params)
    objs = [get_object(doc, name) for name in params.get("object_names", [])]
    if len(objs) < 2:
        raise ValueError("object_names must contain at least two objects")
    operation = params.get("operation", "fuse")
    shape = objs[0].Shape
    for obj in objs[1:]:
        if operation == "fuse":
            shape = shape.fuse(obj.Shape)
        elif operation == "cut":
            shape = shape.cut(obj.Shape)
        elif operation == "common":
            shape = shape.common(obj.Shape)
        else:
            raise ValueError("unsupported boolean operation: " + str(operation))
    doc.openTransaction("MCP worker part boolean")
    try:
        result = doc.addObject("Part::Feature", params.get("result_name") or operation.title())
        result.Shape = shape
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_part_extrude(params):
    doc = get_doc(params)
    source = get_object(doc, params.get("source_object") or "")
    doc.openTransaction("MCP worker part extrude")
    try:
        if uses_feature_extrude(params):
            result, feature_parameters = action_part_extrude_feature(doc, source, params)
            mode = "feature"
        else:
            base_shape = source.Shape
            face = planar_face_from_closed_wires(base_shape)
            extrude_source = face if face is not None else base_shape
            mode = "face_from_closed_wire" if face is not None else "shape"
            shape = extrude_source.extrude(vector(params.get("vector"), [0, 0, 10]))
            result = doc.addObject("Part::Feature", params.get("result_name") or "Extrude")
            result.Shape = shape
            feature_parameters = None
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "mode": mode,
        "feature_parameters": feature_parameters,
        "object": object_summary(result),
        "document": document_summary(doc),
    }


def action_part_revolve(params):
    doc = get_doc(params)
    source = get_object(doc, params.get("source_object") or "")
    shape = source.Shape.revolve(
        vector(params.get("base"), [0, 0, 0]),
        vector(params.get("axis"), [0, 0, 1]),
        float(params.get("angle", 360)),
    )
    doc.openTransaction("MCP worker part revolve")
    try:
        result = doc.addObject("Part::Feature", params.get("result_name") or "Revolve")
        result.Shape = shape
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_part_check_geometry(params):
    doc = get_doc(params)
    names = params.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Shape")]
    checks = []
    for name in names:
        obj = get_object(doc, name)
        shape = obj.Shape
        check_error = None
        try:
            shape.check(bool(params.get("run_bop_check", False)))
        except Exception as exc:
            check_error = str(exc)
        checks.append({"object": object_summary(obj), "is_valid": bool(shape.isValid()), "check_error": check_error})
    return {"checks": checks}


def make_sketch_geometries(item):
    import Part

    kind = item.get("type")
    if kind in {"line", "line_segment"}:
        return [Part.LineSegment(vector(item["start"]), vector(item["end"]))]
    if kind == "point":
        return [Part.Point(vector(item.get("point") or item.get("position")))]
    if kind in {"circle", "circle_3_point"}:
        if kind == "circle_3_point" or item.get("points"):
            points = item.get("points") or [item["point1"], item["point2"], item["point3"]]
            return [Part.Circle(vector(points[0]), vector(points[1]), vector(points[2]))]
        return [Part.Circle(vector(item.get("center"), [0, 0, 0]), vector(item.get("normal"), [0, 0, 1]), float(item["radius"]))]
    if kind in {"arc", "arc_of_circle"}:
        circle = Part.Circle(vector(item.get("center"), [0, 0, 0]), vector(item.get("normal"), [0, 0, 1]), float(item["radius"]))
        return [Part.ArcOfCircle(circle, angle_radians(item["start_angle"]), angle_radians(item["end_angle"]))]
    if kind == "ellipse":
        center = vector(item.get("center"), [0, 0, 0])
        if item.get("major_point") and item.get("minor_point"):
            return [Part.Ellipse(vector(item["major_point"]), vector(item["minor_point"]), center)]
        return [Part.Ellipse(center, float(item.get("major_radius", item.get("radius_x", 2))), float(item.get("minor_radius", item.get("radius_y", 1))))]
    if kind in {"arc_of_ellipse", "ellipse_arc"}:
        center = vector(item.get("center"), [0, 0, 0])
        if item.get("major_point") and item.get("minor_point"):
            ellipse = Part.Ellipse(vector(item["major_point"]), vector(item["minor_point"]), center)
        else:
            ellipse = Part.Ellipse(center, float(item.get("major_radius", item.get("radius_x", 2))), float(item.get("minor_radius", item.get("radius_y", 1))))
        return [Part.ArcOfEllipse(ellipse, angle_radians(item["start_angle"]), angle_radians(item["end_angle"]))]
    if kind in {"arc_of_hyperbola", "hyperbola_arc"}:
        center = vector(item.get("center"), [0, 0, 0])
        if item.get("major_point") and item.get("minor_point"):
            hyperbola = Part.Hyperbola(vector(item["major_point"]), vector(item["minor_point"]), center)
        else:
            hyperbola = Part.Hyperbola(center, float(item.get("major_radius", 2)), float(item.get("minor_radius", 1)))
        return [Part.ArcOfHyperbola(hyperbola, angle_radians(item["start_angle"]), angle_radians(item["end_angle"]))]
    if kind in {"arc_of_parabola", "parabola_arc"}:
        if item.get("point1") and item.get("point2") and item.get("center"):
            parabola = Part.Parabola(vector(item["point1"]), vector(item["point2"]), vector(item["center"]))
        else:
            parabola = Part.Parabola()
        return [Part.ArcOfParabola(parabola, angle_radians(item["start_angle"]), angle_radians(item["end_angle"]))]
    if kind in {"bspline", "b_spline"}:
        poles = [vector(point) for point in (item.get("poles") or item.get("points") or [])]
        if len(poles) < 2:
            raise ValueError("bspline requires at least two poles/points")
        curve = Part.BSplineCurve()
        periodic = bool(item.get("periodic", False))
        if item.get("interpolate", False):
            if periodic:
                curve.interpolate(poles, True)
            else:
                curve.interpolate(poles)
        else:
            if periodic:
                curve.buildFromPoles(poles, True)
            else:
                curve.buildFromPoles(poles)
        return [curve]
    if kind == "polyline":
        points = [vector(point) for point in item["points"]]
        if len(points) < 2:
            raise ValueError("polyline requires at least two points")
        closed = bool(item.get("closed", False))
        segments = [Part.LineSegment(points[idx], points[idx + 1]) for idx in range(len(points) - 1)]
        if closed:
            segments.append(Part.LineSegment(points[-1], points[0]))
        return segments
    raise ValueError("unsupported sketch geometry: " + str(kind))


def sketch_geometry_has_endpoints(geom):
    return hasattr(geom, "StartPoint") and hasattr(geom, "EndPoint")


def sketch_closed_validation(sketch):
    solve_code = sketch.solve()
    return {
        "solve_code": solve_code,
        "open_vertices": [point_list(vertex) for vertex in getattr(sketch, "OpenVertices", [])],
        "conflicting_constraints": list(getattr(sketch, "ConflictingConstraints", [])),
        "redundant_constraints": list(getattr(sketch, "RedundantConstraints", [])),
        "malformed_constraints": list(getattr(sketch, "MalformedConstraints", [])),
    }


def add_sketch_geometry_batch(sketch, items, *, connect_sequence=False, close_sequence=False):
    import Sketcher

    added = []
    constraint_indices = []
    chain_indices = []
    previous_index = None
    for item in items:
        for geom in make_sketch_geometries(item):
            index = sketch.addGeometry(geom, bool(item.get("construction", False)))
            added.append(index)
            if sketch_geometry_has_endpoints(geom):
                if connect_sequence and previous_index is not None:
                    constraint_indices.append(sketch.addConstraint(Sketcher.Constraint("Coincident", previous_index, 2, index, 1)))
                previous_index = index
                chain_indices.append(index)
    if close_sequence and len(chain_indices) > 1:
        constraint_indices.append(sketch.addConstraint(Sketcher.Constraint("Coincident", chain_indices[-1], 2, chain_indices[0], 1)))
    return added, constraint_indices


def make_constraint(spec):
    import Sketcher

    if spec.get("type") in {"Group", "Text"}:
        raise ValueError("Sketcher Group/Text constraints are blocked until stable FreeCAD 1.1.1 fixtures exist")
    values = spec.get("values")
    if values is None:
        values = []
        for key in ("first", "first_pos", "second", "second_pos", "third", "third_pos", "value"):
            if key in spec:
                values.append(spec[key])
    return Sketcher.Constraint(spec["type"], *[sketch_arg(value) for value in values])


def apply_constraint_metadata(sketch, index, spec):
    if spec.get("name") is not None:
        sketch.renameConstraint(index, str(spec.get("name") or ""))
    if spec.get("datum") is not None:
        sketch.setDatum(index, sketch_arg(spec["datum"]))
    if spec.get("driving") is not None:
        sketch.setDriving(index, bool(spec["driving"]))
    if spec.get("active") is not None:
        sketch.setActive(index, bool(spec["active"]))
    if spec.get("virtual_space") is not None:
        sketch.setVirtualSpace(index, bool(spec["virtual_space"]))
    if spec.get("visible") is not None:
        sketch.setVisibility(index, bool(spec["visible"]))
    if spec.get("label_position") is not None:
        sketch.setLabelPosition(index, float(spec["label_position"]))
    if spec.get("label_distance") is not None:
        sketch.setLabelDistance(index, float(spec["label_distance"]))


def add_profile_geometry(sketch, profile):
    import Part
    import Sketcher

    kind = profile.get("type")
    construction = bool(profile.get("construction", False))
    constrain = bool(profile.get("constrain", True))
    added = []
    constraints = []

    def add_lines(points, closed=True):
        local = []
        for idx in range(len(points) - 1):
            local.append(sketch.addGeometry(Part.LineSegment(points[idx], points[idx + 1]), construction))
        if closed:
            local.append(sketch.addGeometry(Part.LineSegment(points[-1], points[0]), construction))
        if constrain:
            for idx in range(len(local) - 1):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[idx], 2, local[idx + 1], 1)))
            if closed and local:
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[-1], 2, local[0], 1)))
        added.extend(local)
        return local

    if kind == "rectangle":
        if profile.get("corner1") and profile.get("corner2"):
            c1 = vector(profile["corner1"])
            c2 = vector(profile["corner2"])
        else:
            c1 = vector(profile.get("origin"), [0, 0, 0])
            c2 = App.Vector(c1.x + float(profile["width"]), c1.y + float(profile["height"]), c1.z)
        points = [c1, App.Vector(c2.x, c1.y, c1.z), c2, App.Vector(c1.x, c2.y, c1.z)]
        local = add_lines(points, True)
        if constrain:
            constraints.extend(
                [
                    sketch.addConstraint(Sketcher.Constraint("Horizontal", local[0])),
                    sketch.addConstraint(Sketcher.Constraint("Vertical", local[1])),
                    sketch.addConstraint(Sketcher.Constraint("Horizontal", local[2])),
                    sketch.addConstraint(Sketcher.Constraint("Vertical", local[3])),
                ]
            )
        if bool(profile.get("dimension_constraints", False)):
            constraints.append(sketch.addConstraint(Sketcher.Constraint("DistanceX", local[0], 1, local[0], 2, abs(c2.x - c1.x))))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("DistanceY", local[1], 1, local[1], 2, abs(c2.y - c1.y))))
    elif kind == "polyline":
        added.extend(add_lines([vector(point) for point in profile["points"]], bool(profile.get("closed", True))))
    elif kind == "regular_polygon":
        sides = int(profile["sides"])
        if sides < 3:
            raise ValueError("regular_polygon requires sides >= 3")
        center = vector(profile.get("center"), [0, 0, 0])
        radius = float(profile["radius"])
        start = angle_radians(profile.get("start_angle"), 0.0)
        points = [
            App.Vector(center.x + radius * math.cos(start + (2 * math.pi * idx / sides)), center.y + radius * math.sin(start + (2 * math.pi * idx / sides)), center.z)
            for idx in range(sides)
        ]
        local = add_lines(points, True)
        if constrain and bool(profile.get("equal_edges", True)):
            for idx in range(1, len(local)):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Equal", local[0], local[idx])))
    elif kind in {"circle", "circle_profile"}:
        center = vector(profile.get("center"), [0, 0, 0])
        geom = Part.Circle(center, vector(profile.get("normal"), [0, 0, 1]), float(profile["radius"]))
        idx = sketch.addGeometry(geom, construction)
        added.append(idx)
        if bool(profile.get("radius_constraint", constrain)):
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Radius", idx, float(profile["radius"]))))
    elif kind == "slot":
        center = vector(profile.get("center"), [0, 0, 0])
        radius = float(profile["radius"])
        length = float(profile["length"])
        left = App.Vector(center.x - length / 2, center.y, center.z)
        right = App.Vector(center.x + length / 2, center.y, center.z)
        top_left = App.Vector(left.x, left.y + radius, left.z)
        top_right = App.Vector(right.x, right.y + radius, right.z)
        bottom_right = App.Vector(right.x, right.y - radius, right.z)
        bottom_left = App.Vector(left.x, left.y - radius, left.z)
        local = [
            sketch.addGeometry(Part.LineSegment(top_left, top_right), construction),
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(right, App.Vector(0, 0, 1), radius), math.pi / 2, -math.pi / 2), construction),
            sketch.addGeometry(Part.LineSegment(bottom_right, bottom_left), construction),
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(left, App.Vector(0, 0, 1), radius), -math.pi / 2, math.pi / 2), construction),
        ]
        added.extend(local)
        if constrain:
            for idx in range(len(local) - 1):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[idx], 2, local[idx + 1], 1)))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[-1], 2, local[0], 1)))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Horizontal", local[0])))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Horizontal", local[2])))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Equal", local[1], local[3])))
    else:
        raise ValueError("unsupported sketch profile: " + str(kind))

    return added, constraints


def action_sketch_create(params):
    doc = get_doc(params)
    doc.openTransaction("MCP worker create sketch")
    try:
        sketch = doc.addObject("Sketcher::SketchObject", params.get("sketch_name") or "Sketch")
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_add_geometry(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    connect_sequence = bool(params.get("connect_sequence", False))
    close_sequence = bool(params.get("close_sequence", False))
    require_closed = bool(params.get("require_closed", False))
    closed_validation = None
    doc.openTransaction("MCP worker add sketch geometry")
    try:
        added, constraint_indices = add_sketch_geometry_batch(
            sketch,
            params.get("geometry") or [],
            connect_sequence=connect_sequence,
            close_sequence=close_sequence,
        )
        if require_closed:
            closed_validation = sketch_closed_validation(sketch)
            if closed_validation["open_vertices"]:
                raise ValueError("sketch geometry sequence is not closed; open vertices: " + str(closed_validation["open_vertices"]))
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    result = {
        "saved_path": saved,
        "added_indices": added,
        "constraint_indices": constraint_indices,
        "sketch": object_summary(sketch),
        "document": document_summary(doc),
    }
    if closed_validation is not None:
        result["closed_validation"] = closed_validation
    return result


def action_sketch_add_constraint(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    added = []
    doc.openTransaction("MCP worker add sketch constraints")
    try:
        for item in params.get("constraints") or []:
            index = sketch.addConstraint(make_constraint(item))
            apply_constraint_metadata(sketch, index, item)
            added.append(index)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "added_indices": added, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_add_profile(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    doc.openTransaction("MCP worker add sketch profile")
    try:
        added, constraints = add_profile_geometry(sketch, params["profile"])
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "profile_type": params["profile"].get("type"),
        "added_indices": added,
        "constraint_indices": constraints,
        "sketch": object_summary(sketch),
        "document": document_summary(doc),
    }


def action_sketch_edit_geometry(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    reports = []
    doc.openTransaction("MCP worker edit sketch geometry")
    try:
        for op in params.get("operations") or []:
            kind = op.get("operation") or op.get("type")
            report = {"operation": kind}
            if kind == "delete":
                sketch.delGeometry(int(op["geometry_index"]), bool(op.get("no_solve", False)))
                report["geometry_index"] = int(op["geometry_index"])
            elif kind == "delete_many":
                ids = [int(value) for value in op.get("geometry_indices", [])]
                if hasattr(sketch, "delGeometries"):
                    sketch.delGeometries(ids, bool(op.get("no_solve", False)))
                else:
                    for geo_id in sorted(ids, reverse=True):
                        sketch.delGeometry(geo_id, bool(op.get("no_solve", False)))
                report["geometry_indices"] = ids
            elif kind == "delete_all":
                sketch.deleteAllGeometry(bool(op.get("no_solve", False)))
            elif kind == "set_construction":
                sketch.setConstruction(int(op["geometry_index"]), bool(op["construction"]))
                report["construction"] = bool(op["construction"])
            elif kind == "toggle_construction":
                sketch.toggleConstruction(int(op["geometry_index"]))
            elif kind == "add_external":
                sketch.addExternal(str(op["object_name"]), str(op["sub_name"]), bool(op.get("defining", False)), bool(op.get("intersection", False)))
                report["object_name"] = op["object_name"]
                report["sub_name"] = op["sub_name"]
            elif kind == "delete_external":
                sketch.delExternal(int(op["external_index"]))
                report["external_index"] = int(op["external_index"])
            elif kind == "delete_externals":
                ids = [int(value) for value in op.get("external_indices", [])]
                sketch.delExternals(ids)
                report["external_indices"] = ids
            elif kind == "carbon_copy":
                sketch.carbonCopy(str(op["object_name"]), bool(op.get("as_construction", True)))
                report["object_name"] = op["object_name"]
            elif kind == "move_geometry":
                sketch.moveGeometry(int(op["geometry_index"]), int(op.get("point_pos", 0)), vector(op["vector"]), bool(op.get("relative", False)))
            elif kind == "move_geometries":
                pairs = [(int(pair[0]), int(pair[1])) for pair in op.get("geometry_points", [])]
                sketch.moveGeometries(pairs, vector(op["vector"]), bool(op.get("relative", False)))
                report["geometry_points"] = pairs
            elif kind == "expose_internal_geometry":
                sketch.exposeInternalGeometry(int(op["geometry_index"]))
            elif kind == "delete_unused_internal_geometry":
                sketch.deleteUnusedInternalGeometry(int(op["geometry_index"]))
            elif kind == "detect_degenerated":
                report["count"] = int(sketch.detectDegeneratedGeometries(float(op.get("tolerance", 1e-7))))
            elif kind == "remove_degenerated":
                report["count"] = int(sketch.removeDegeneratedGeometries(float(op.get("tolerance", 1e-7))))
            else:
                raise ValueError("unsupported sketch geometry edit operation: " + str(kind))
            reports.append(report)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_edit_constraints(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    reports = []
    doc.openTransaction("MCP worker edit sketch constraints")
    try:
        for op in params.get("operations") or []:
            kind = op.get("operation") or op.get("type")
            report = {"operation": kind}
            if kind == "delete":
                sketch.delConstraint(int(op["constraint_index"]), bool(op.get("no_solve", False)))
                report["constraint_index"] = int(op["constraint_index"])
            elif kind == "delete_many":
                ids = [int(value) for value in op.get("constraint_indices", [])]
                if hasattr(sketch, "delConstraints"):
                    sketch.delConstraints(ids, bool(op.get("update_geometry", True)), bool(op.get("no_solve", False)))
                else:
                    for constraint_id in sorted(ids, reverse=True):
                        sketch.delConstraint(constraint_id, bool(op.get("no_solve", False)))
                report["constraint_indices"] = ids
            elif kind == "delete_all":
                sketch.deleteAllConstraints()
            elif kind == "rename":
                sketch.renameConstraint(int(op["constraint_index"]), str(op.get("name") or ""))
            elif kind == "set_datum":
                target = op.get("constraint_name") if op.get("constraint_name") is not None else int(op["constraint_index"])
                sketch.setDatum(target, sketch_arg(op["value"]))
                report["datum"] = quantity_summary(sketch.getDatum(target))
            elif kind == "get_datum":
                target = op.get("constraint_name") if op.get("constraint_name") is not None else int(op["constraint_index"])
                report["datum"] = quantity_summary(sketch.getDatum(target))
            elif kind == "set_driving":
                sketch.setDriving(int(op["constraint_index"]), bool(op["driving"]))
            elif kind == "toggle_driving":
                sketch.toggleDriving(int(op["constraint_index"]))
                report["driving"] = bool(sketch.getDriving(int(op["constraint_index"])))
            elif kind == "set_datums_driving":
                sketch.setDatumsDriving(bool(op["driving"]))
            elif kind == "move_datums_to_end":
                sketch.moveDatumsToEnd()
            elif kind == "set_active":
                sketch.setActive(int(op["constraint_index"]), bool(op["active"]))
            elif kind == "toggle_active":
                sketch.toggleActive(int(op["constraint_index"]))
                report["active"] = bool(sketch.getActive(int(op["constraint_index"])))
            elif kind == "set_virtual_space":
                sketch.setVirtualSpace(int(op["constraint_index"]), bool(op["virtual_space"]))
            elif kind == "toggle_virtual_space":
                sketch.toggleVirtualSpace(int(op["constraint_index"]))
                report["virtual_space"] = bool(sketch.getVirtualSpace(int(op["constraint_index"])))
            elif kind == "set_visibility":
                sketch.setVisibility(int(op["constraint_index"]), bool(op["visible"]))
            elif kind == "set_label_position":
                sketch.setLabelPosition(int(op["constraint_index"]), float(op["position"]))
            elif kind == "set_label_distance":
                sketch.setLabelDistance(int(op["constraint_index"]), float(op["distance"]))
            elif kind == "delete_on_point":
                if op.get("vertex_index") is not None:
                    sketch.delConstraintOnPoint(int(op["vertex_index"]))
                else:
                    sketch.delConstraintOnPoint(int(op["geometry_index"]), int(op["point_pos"]))
            elif kind == "delete_to_external":
                sketch.delConstraintsToExternal()
            elif kind == "auto_remove_redundants":
                sketch.autoRemoveRedundants(bool(op.get("update_geometry", True)))
            elif kind == "change_locking":
                report["affected"] = int(sketch.changeConstraintsLocking(bool(op.get("lock", True))))
            elif kind == "validate_constraints":
                sketch.validateConstraints()
            elif kind == "evaluate_constraints":
                report["invalid_found"] = bool(sketch.evaluateConstraints())
            else:
                raise ValueError("unsupported sketch constraint edit operation: " + str(kind))
            reports.append(report)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_transform(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    reports = []
    doc.openTransaction("MCP worker transform sketch")
    try:
        for op in params.get("operations") or []:
            kind = op.get("operation") or op.get("type")
            report = {"operation": kind}
            if kind == "fillet":
                if op.get("point_mode", False):
                    sketch.fillet(int(op["geometry_index"]), int(op["point_pos"]), float(op["radius"]), int(op.get("trim", True)), bool(op.get("create_corner", False)), bool(op.get("chamfer", False)))
                else:
                    sketch.fillet(int(op["geometry_index1"]), int(op["geometry_index2"]), vector(op["point1"]), vector(op["point2"]), float(op["radius"]), int(op.get("trim", True)), bool(op.get("create_corner", False)), bool(op.get("chamfer", False)))
            elif kind == "trim":
                sketch.trim(int(op["geometry_index"]), vector(op["point"]))
            elif kind == "extend":
                sketch.extend(int(op["geometry_index"]), float(op["increment"]), int(op["point_pos"]))
            elif kind == "split":
                sketch.split(int(op["geometry_index"]), vector(op["point"]))
            elif kind == "join":
                sketch.join(int(op["geometry_index1"]), int(op["point_pos1"]), int(op["geometry_index2"]), int(op["point_pos2"]), int(op.get("continuity", 0)))
            elif kind == "copy":
                report["added_indices"] = list(sketch.addCopy([int(value) for value in op["geometry_indices"]], vector(op["vector"]), bool(op.get("clone", False))))
            elif kind == "move":
                sketch.addMove([int(value) for value in op["geometry_indices"]], vector(op["vector"]))
            elif kind == "symmetric":
                report["added_indices"] = list(sketch.addSymmetric([int(value) for value in op["geometry_indices"]], int(op["reference_geometry"]), int(op.get("reference_point_pos", 0))))
            elif kind == "rectangular_array":
                sketch.addRectangularArray([int(value) for value in op["geometry_indices"]], vector(op["vector"]), bool(op.get("clone", False)), int(op["rows"]), int(op["cols"]), bool(op.get("constrain_displacement", False)), float(op.get("perpendicular_scale", 1.0)))
            elif kind == "remove_axes_alignment":
                sketch.removeAxesAlignment([int(value) for value in op["geometry_indices"]])
            elif kind == "convert_to_nurbs":
                sketch.convertToNURBS(int(op["geometry_index"]))
            elif kind == "increase_bspline_degree":
                sketch.increaseBSplineDegree(int(op["geometry_index"]), int(op.get("increment", 1)))
            elif kind == "decrease_bspline_degree":
                report["ok"] = bool(sketch.decreaseBSplineDegree(int(op["geometry_index"]), int(op.get("decrement", 1))))
            elif kind == "modify_bspline_knot":
                sketch.modifyBSplineKnotMultiplicity(int(op["geometry_index"]), int(op["knot_index"]), int(op.get("multiplicity", 1)))
            elif kind == "insert_bspline_knot":
                sketch.insertBSplineKnot(int(op["geometry_index"]), float(op["parameter"]), int(op.get("multiplicity", 1)))
            else:
                raise ValueError("unsupported sketch transform operation: " + str(kind))
            reports.append(report)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_auto_constrain(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    reports = []
    doc.openTransaction("MCP worker auto constrain sketch")
    try:
        for op in params.get("operations") or [{"operation": "autoconstraint"}]:
            kind = op.get("operation") or op.get("type")
            report = {"operation": kind}
            if kind == "autoconstraint":
                sketch.autoconstraint(float(op.get("precision", 1e-4)), angle_radians(op.get("angle_precision"), math.pi / 8), bool(op.get("include_construction", True)))
            elif kind == "detect_point_on_point":
                report["count"] = int(sketch.detectMissingPointOnPointConstraints(float(op.get("precision", 1e-4)), bool(op.get("include_construction", True))))
                report["missing"] = list(getattr(sketch, "MissingPointOnPointConstraints", []))
            elif kind == "analyse_point_on_point":
                sketch.analyseMissingPointOnPointCoincident(angle_radians(op.get("angle_precision"), math.pi / 8))
                report["missing"] = list(getattr(sketch, "MissingPointOnPointConstraints", []))
            elif kind == "detect_vertical_horizontal":
                report["count"] = int(sketch.detectMissingVerticalHorizontalConstraints(angle_radians(op.get("angle_precision"), math.pi / 8)))
                report["missing"] = list(getattr(sketch, "MissingVerticalHorizontalConstraints", []))
            elif kind == "detect_equality":
                report["count"] = int(sketch.detectMissingEqualityConstraints(float(op.get("precision", 1e-4))))
                report["missing_line_equality"] = list(getattr(sketch, "MissingLineEqualityConstraints", []))
                report["missing_radius"] = list(getattr(sketch, "MissingRadiusConstraints", []))
            elif kind == "make_point_on_point":
                sketch.makeMissingPointOnPointCoincident(bool(op.get("one_by_one", False)))
            elif kind == "make_vertical_horizontal":
                sketch.makeMissingVerticalHorizontal(bool(op.get("one_by_one", False)))
            elif kind == "make_equality":
                sketch.makeMissingEquality(bool(op.get("one_by_one", True)))
            elif kind == "validate_constraints":
                sketch.validateConstraints()
            elif kind == "auto_remove_redundants":
                sketch.autoRemoveRedundants(bool(op.get("update_geometry", True)))
            else:
                raise ValueError("unsupported sketch auto constraint operation: " + str(kind))
            reports.append(report)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_validate(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    solve_code = sketch.solve() if bool(params.get("solve", True)) else None
    if bool(params.get("detect_missing", False)):
        sketch.detectMissingPointOnPointConstraints(float(params.get("precision", 1e-4)), bool(params.get("include_construction", True)))
        sketch.analyseMissingPointOnPointCoincident(angle_radians(params.get("angle_precision"), math.pi / 8))
        sketch.detectMissingVerticalHorizontalConstraints(angle_radians(params.get("angle_precision"), math.pi / 8))
        sketch.detectMissingEqualityConstraints(float(params.get("precision", 1e-4)))
    doc.recompute()
    constraint_errors = []
    if bool(params.get("include_constraint_errors", False)):
        for index in range(len(sketch.Constraints)):
            try:
                constraint_errors.append({"index": index, "error": float(sketch.calculateConstraintError(index))})
            except Exception as exc:
                constraint_errors.append({"index": index, "error": None, "message": str(exc)})
    return {
        "sketch": object_summary(sketch),
        "geometry_count": len(sketch.Geometry),
        "constraint_count": len(sketch.Constraints),
        "degrees_of_freedom": getattr(sketch, "DoF", getattr(sketch, "DegreesOfFreedom", None)),
        "solve_code": solve_code,
        "evaluate_constraints_invalid_found": bool(sketch.evaluateConstraints()),
        "open_vertices": [point_list(v) for v in getattr(sketch, "OpenVertices", [])],
        "conflicting_constraints": list(getattr(sketch, "ConflictingConstraints", [])),
        "redundant_constraints": list(getattr(sketch, "RedundantConstraints", [])),
        "partially_redundant_constraints": list(getattr(sketch, "PartiallyRedundantConstraints", [])),
        "malformed_constraints": list(getattr(sketch, "MalformedConstraints", [])),
        "missing_point_on_point": list(getattr(sketch, "MissingPointOnPointConstraints", [])),
        "missing_vertical_horizontal": list(getattr(sketch, "MissingVerticalHorizontalConstraints", [])),
        "missing_line_equality": list(getattr(sketch, "MissingLineEqualityConstraints", [])),
        "missing_radius": list(getattr(sketch, "MissingRadiusConstraints", [])),
        "dependent_geometry": [list(pair) for pair in sketch.getGeometryWithDependentParameters()],
        "constraint_errors": constraint_errors,
    }


def action_mesh_import(params):
    import Mesh

    doc = get_doc(params)
    before = {obj.Name for obj in doc.Objects}
    Mesh.insert(params["input_path"], doc.Name)
    doc.recompute()
    imported = [object_summary(obj) for obj in doc.Objects if obj.Name not in before]
    saved = save_doc(doc, params)
    return {"saved_path": saved, "imported": imported, "document": document_summary(doc)}


def action_mesh_export(params):
    import Mesh

    doc = get_doc(params)
    output_path = safe_output_path(params.get("output_path"), params)
    if os.path.exists(output_path) and not bool(params.get("overwrite", False)):
        raise ValueError("output exists; pass overwrite=true: " + output_path)
    names = params.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Mesh")]
    objects = [get_object(doc, name) for name in names]
    Mesh.export(objects, output_path)
    return {"exported_path": output_path, "objects": [object_summary(obj) for obj in objects]}


def action_mesh_evaluate(params):
    doc = get_doc(params)
    names = params.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Mesh")]
    return {"meshes": [object_summary(get_object(doc, name)) for name in names]}


def action_mesh_repair(params):
    doc = get_doc(params)
    names = params.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Mesh")]
    actions = params.get("actions") or ["harmonize_normals"]
    reports = []
    doc.openTransaction("MCP worker mesh repair")
    try:
        for name in names:
            obj = get_object(doc, name)
            mesh = obj.Mesh.copy()
            done = []
            errors = []
            for action in actions:
                if action == "harmonize_normals" and hasattr(mesh, "harmonizeNormals"):
                    try:
                        mesh.harmonizeNormals()
                        done.append(action)
                    except Exception as exc:
                        errors.append({"action": action, "error": str(exc)})
                elif action == "remove_duplicated_points" and hasattr(mesh, "removeDuplicatedPoints"):
                    try:
                        mesh.removeDuplicatedPoints()
                        done.append(action)
                    except Exception as exc:
                        errors.append({"action": action, "error": str(exc)})
                else:
                    errors.append({"action": action, "error": "unsupported action"})
            assigned_to = obj.Name
            try:
                obj.Mesh = mesh
            except Exception:
                replacement = doc.addObject("Mesh::Feature", params.get("result_name") or (obj.Name + "_Repaired"))
                replacement.Mesh = mesh
                assigned_to = replacement.Name
            reports.append({"object": obj.Name, "assigned_to": assigned_to, "actions": done, "errors": errors})
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "reports": reports, "document": document_summary(doc)}


def action_mesh_boolean(params):
    doc = get_doc(params)
    objs = [get_object(doc, name) for name in params.get("object_names", [])]
    if len(objs) < 2:
        raise ValueError("object_names must contain at least two mesh objects")
    operation = params.get("operation", "union")
    mesh = objs[0].Mesh.copy()
    for obj in objs[1:]:
        other = obj.Mesh
        if operation == "union" and hasattr(mesh, "unite"):
            mesh = mesh.unite(other)
        elif operation == "difference" and hasattr(mesh, "difference"):
            mesh = mesh.difference(other)
        elif operation == "intersection" and hasattr(mesh, "intersect"):
            mesh = mesh.intersect(other)
        else:
            raise ValueError("mesh boolean operation is not supported by this FreeCAD build: " + str(operation))
    doc.openTransaction("MCP worker mesh boolean")
    try:
        result = doc.addObject("Mesh::Feature", params.get("result_name") or operation.title())
        result.Mesh = mesh
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_assembly_create(params):
    doc = get_doc(params)
    doc.openTransaction("MCP worker create assembly")
    try:
        assembly = doc.addObject("Assembly::AssemblyObject", params.get("assembly_name") or "Assembly")
        assembly.Type = "Assembly"
        assembly.newObject("Assembly::JointGroup", "Joints")
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "assembly": object_summary(assembly), "document": document_summary(doc)}


def action_assembly_insert(params):
    doc = get_doc(params)
    assembly = get_object(doc, params.get("assembly_name") or "")
    target = get_object(doc, params.get("object_name") or "")
    doc.openTransaction("MCP worker assembly insert")
    try:
        link = assembly.newObject("App::Link", params.get("link_name") or target.Label)
        link.LinkedObject = target
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "link": object_summary(link), "document": document_summary(doc)}


def action_assembly_create_joint(params):
    try:
        import JointObject
        import UtilsAssembly
    except ImportError:
        assembly_mod = os.path.join(App.getResourceDir(), "Mod", "Assembly")
        if assembly_mod not in sys.path:
            sys.path.append(assembly_mod)
        import JointObject
        import UtilsAssembly

    doc = get_doc(params)
    assembly = get_object(doc, params.get("assembly_name") or "")
    joint_type = params.get("joint_type", "Fixed")
    if joint_type not in JointObject.JointTypes:
        raise ValueError("unsupported joint_type: " + str(joint_type))
    refs = []
    for ref in params.get("references") or []:
        obj = get_object(doc, ref["object_name"])
        sub = ref.get("sub_element") or ""
        vertex = ref.get("vertex") or sub
        refs.append([obj, [sub, vertex]])
    if refs and len(refs) != 2:
        raise ValueError("references must contain exactly two connector references")
    doc.openTransaction("MCP worker assembly joint")
    try:
        joint_group = UtilsAssembly.getJointGroup(assembly)
        joint = joint_group.newObject("App::FeaturePython", params.get("joint_name") or "Joint")
        JointObject.Joint(joint, JointObject.JointTypes.index(joint_type))
        if refs:
            joint.Proxy.setJointConnectors(joint, refs)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "joint": object_summary(joint),
        "joint_fields": {
            "joint_type": joint.JointType,
            "has_proxy": joint.Proxy is not None,
            "has_reference1": hasattr(joint, "Reference1") and joint.Reference1 is not None,
            "has_reference2": hasattr(joint, "Reference2") and joint.Reference2 is not None,
        },
        "document": document_summary(doc),
        "note": "Created a native Assembly JointObject proxy. Connector-aware solving still depends on valid Assembly references and GUI/workbench workflows.",
    }


def action_assembly_solve(params):
    doc = get_doc(params)
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "document": document_summary(doc), "note": "Persistent worker recomputed the assembly document."}


def action_assembly_bom(params):
    doc = get_doc(params)
    assembly = get_object(doc, params["assembly_name"]) if params.get("assembly_name") else None
    root = assembly.Group if assembly is not None else doc.Objects
    rows = []
    for obj in root:
        rows.append({"name": obj.Name, "label": obj.Label, "type_id": obj.TypeId})
    return {"rows": rows, "count": len(rows)}


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
    "document_export": action_document_export,
    "part_create_primitive": action_part_create_primitive,
    "part_boolean": action_part_boolean,
    "part_extrude": action_part_extrude,
    "part_revolve": action_part_revolve,
    "part_check_geometry": action_part_check_geometry,
    "sketch_create": action_sketch_create,
    "sketch_add_geometry": action_sketch_add_geometry,
    "sketch_add_constraint": action_sketch_add_constraint,
    "sketch_add_profile": action_sketch_add_profile,
    "sketch_edit_geometry": action_sketch_edit_geometry,
    "sketch_edit_constraints": action_sketch_edit_constraints,
    "sketch_transform": action_sketch_transform,
    "sketch_auto_constrain": action_sketch_auto_constrain,
    "sketch_validate": action_sketch_validate,
    "mesh_import": action_mesh_import,
    "mesh_export": action_mesh_export,
    "mesh_evaluate": action_mesh_evaluate,
    "mesh_repair": action_mesh_repair,
    "mesh_boolean": action_mesh_boolean,
    "assembly_create": action_assembly_create,
    "assembly_insert": action_assembly_insert,
    "assembly_create_joint": action_assembly_create_joint,
    "assembly_solve": action_assembly_solve,
    "assembly_bom": action_assembly_bom,
    "object_list": action_object_list,
    "object_get": action_object_get,
    "object_set_properties": action_object_set_properties,
    "object_delete": action_object_delete,
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
        try:
            response = session.request("status", {}, timeout_sec=timeout_sec)
        except ToolInputError:
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
        except ToolInputError:
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

    def _drop_if_stopped(self, session_id: str, session: FreeCadWorkerSession) -> None:
        if session.is_running:
            return
        session.close(timeout_sec=1)
        self.sessions.pop(session_id, None)


def discovery_summary(discovery: FreeCadDiscoveryResult) -> JsonObject:
    return discovery.to_dict()
