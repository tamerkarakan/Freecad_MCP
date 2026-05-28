"""Typed CAD tools backed by process-per-call FreeCADCmd."""

from __future__ import annotations

import json
import base64
import os
from pathlib import Path

from freecad_mcp.runtime_bridge import (
    FREECAD_JSON_PREFIX,
    FreeCadCmdBridge,
    FreeCadDiscovery,
    parse_prefixed_json,
)
from freecad_mcp.tooling import (
    JsonObject,
    ToolDefinition,
    ToolInputError,
    bounded_int,
    optional_string,
    required_string,
)


COMMON_RUNTIME_PROPS: JsonObject = {
    "executable": {"type": "string", "description": "Optional explicit FreeCADCmd path."},
    "freecad_home": {"type": "string", "description": "Optional portable FreeCAD directory."},
    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 180},
    "compact_execution": {
        "type": "boolean",
        "description": "Return compact execution metadata without stdout/stderr/argv text.",
    },
    "allow_external_paths": {
        "type": "boolean",
        "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace.",
    },
}


CAD_ACTION_SCRIPT = r"""
import base64
import json
import math
import os
import traceback

import FreeCAD as App

PREFIX = "__FREECAD_MCP_JSON__"
ARGS = json.loads(base64.b64decode("__ARGS_B64__").decode("utf-8"))


def emit(payload):
    print(PREFIX + json.dumps(payload, default=str))


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
    summary = {
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
    return summary


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


def document_summary(doc):
    return {
        "name": doc.Name,
        "label": doc.Label,
        "file_name": doc.FileName,
        "object_count": len(doc.Objects),
        "objects": [object_summary(obj) for obj in doc.Objects],
    }


def open_or_new(args):
    path = args.get("document_path")
    name = args.get("document_name") or "McpDocument"
    if path:
        return App.openDocument(path)
    return App.newDocument(name)


def get_object(doc, name):
    obj = doc.getObject(name)
    if obj is None:
        for candidate in doc.Objects:
            if candidate.Label == name:
                return candidate
        raise ValueError("object not found: " + name)
    return obj


def safe_output_path(path, args):
    if not os.path.isabs(path):
        raise ValueError("output_path must be absolute")
    resolved = os.path.abspath(path)
    if bool(args.get("allow_external_paths", False)):
        return resolved
    root = os.path.abspath(args.get("_workspace_root") or os.getcwd())
    try:
        common = os.path.commonpath([root, resolved])
    except ValueError:
        common = ""
    if common != root:
        raise ValueError("output_path escapes workspace root; pass allow_external_paths=true if intentional")
    return resolved


def save_if_requested(doc, args):
    output = args.get("output_path")
    overwrite = bool(args.get("overwrite", False))
    if output:
        output = safe_output_path(output, args)
        if os.path.exists(output) and not overwrite:
            raise ValueError("output exists; pass overwrite=true: " + output)
        doc.saveAs(output)
        return output
    if args.get("save", False):
        if not doc.FileName:
            raise ValueError("document has no FileName; pass output_path")
        doc.save()
        return doc.FileName
    return None


def export_objects(objects, output_path, args):
    output_path = safe_output_path(output_path, args)
    ext = os.path.splitext(output_path)[1].lower()
    if ext in {".stl", ".obj", ".ply", ".off"}:
        import Mesh

        Mesh.export(objects, output_path)
    else:
        import Import

        Import.export(objects, output_path)


def import_file(doc, input_path):
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".fcstd":
        imported = App.openDocument(input_path)
        return imported
    if ext in {".stl", ".obj", ".ply", ".off"}:
        import Mesh

        Mesh.insert(input_path, doc.Name)
    else:
        import Import

        Import.insert(input_path, doc.Name)
    return doc


def action_document_new(args):
    doc = App.newDocument(args.get("document_name") or "McpDocument")
    doc.Label = args.get("label") or doc.Label
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "document": document_summary(doc)}


def action_document_open(args):
    doc = App.openDocument(args["document_path"])
    return {"document": document_summary(doc)}


def action_document_save(args):
    doc = App.openDocument(args["document_path"])
    doc.recompute()
    saved = save_if_requested(doc, {**args, "save": True})
    return {"saved_path": saved, "document": document_summary(doc)}


def action_document_recompute(args):
    doc = open_or_new(args)
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "document": document_summary(doc)}


def action_document_export(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [obj.Name for obj in doc.Objects]
    objects = [get_object(doc, name) for name in names]
    output = safe_output_path(args["output_path"], args)
    if os.path.exists(output) and not bool(args.get("overwrite", False)):
        raise ValueError("output exists; pass overwrite=true: " + output)
    export_objects(objects, output, args)
    return {"exported_path": output, "objects": [object_summary(obj) for obj in objects]}


def action_object_list(args):
    doc = App.openDocument(args["document_path"])
    return {"document": document_summary(doc)}


def action_object_get(args):
    doc = App.openDocument(args["document_path"])
    obj = get_object(doc, args["object_name"])
    properties = {}
    if args.get("include_properties", True):
        for prop in obj.PropertiesList:
            try:
                value = getattr(obj, prop)
                if isinstance(value, (str, int, float, bool)) or value is None:
                    properties[prop] = value
                else:
                    properties[prop] = str(value)
            except Exception as exc:
                properties[prop] = "<error: %s>" % exc
    return {"object": object_summary(obj), "properties": properties}


def action_object_set_properties(args):
    doc = App.openDocument(args["document_path"])
    obj = get_object(doc, args["object_name"])
    doc.openTransaction("MCP set object properties")
    changed = {}
    for key, value in (args.get("properties") or {}).items():
        if key not in obj.PropertiesList and not hasattr(obj, key):
            raise ValueError("unknown property: " + key)
        setattr(obj, key, value)
        changed[key] = value
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "changed": changed, "object": object_summary(obj), "document": document_summary(doc)}


def action_object_delete(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [args["object_name"]]
    doc.openTransaction("MCP delete objects")
    for name in names:
        obj = get_object(doc, name)
        doc.removeObject(obj.Name)
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "deleted": names, "document": document_summary(doc)}


def action_part_create_primitive(args):
    doc = open_or_new(args)
    primitive = args.get("primitive", "box")
    type_map = {
        "box": "Part::Box",
        "cylinder": "Part::Cylinder",
        "sphere": "Part::Sphere",
        "cone": "Part::Cone",
        "torus": "Part::Torus",
    }
    if primitive not in type_map:
        raise ValueError("unsupported primitive: " + primitive)
    doc.openTransaction("MCP create primitive")
    obj = doc.addObject(type_map[primitive], args.get("object_name") or primitive.title())
    for key, value in (args.get("properties") or {}).items():
        setattr(obj, key, value)
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "object": object_summary(obj), "document": document_summary(doc)}


def action_part_boolean(args):
    import Part

    doc = App.openDocument(args["document_path"])
    objs = [get_object(doc, name) for name in args["object_names"]]
    if len(objs) < 2:
        raise ValueError("object_names must contain at least two objects")
    operation = args.get("operation", "fuse")
    shape = objs[0].Shape
    for obj in objs[1:]:
        if operation == "fuse":
            shape = shape.fuse(obj.Shape)
        elif operation == "cut":
            shape = shape.cut(obj.Shape)
        elif operation == "common":
            shape = shape.common(obj.Shape)
        else:
            raise ValueError("unsupported boolean operation: " + operation)
    doc.openTransaction("MCP part boolean")
    result = doc.addObject("Part::Feature", args.get("result_name") or operation.title())
    result.Shape = shape
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


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


def action_part_extrude(args):
    doc = App.openDocument(args["document_path"])
    source = get_object(doc, args["source_object"])
    base_shape = source.Shape
    face = planar_face_from_closed_wires(base_shape)
    extrude_source = face if face is not None else base_shape
    mode = "face_from_closed_wire" if face is not None else "shape"
    shape = extrude_source.extrude(vector(args.get("vector"), [0, 0, 10]))
    doc.openTransaction("MCP part extrude")
    result = doc.addObject("Part::Feature", args.get("result_name") or "Extrude")
    result.Shape = shape
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "mode": mode, "object": object_summary(result), "document": document_summary(doc)}


def action_part_revolve(args):
    doc = App.openDocument(args["document_path"])
    source = get_object(doc, args["source_object"])
    shape = source.Shape.revolve(
        vector(args.get("base"), [0, 0, 0]),
        vector(args.get("axis"), [0, 0, 1]),
        float(args.get("angle", 360)),
    )
    doc.openTransaction("MCP part revolve")
    result = doc.addObject("Part::Feature", args.get("result_name") or "Revolve")
    result.Shape = shape
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_part_fillet(args):
    doc = App.openDocument(args["document_path"])
    source = get_object(doc, args["source_object"])
    edges = args.get("edge_indices") or list(range(1, len(source.Shape.Edges) + 1))
    edge_objs = [source.Shape.Edges[int(i) - 1] for i in edges]
    shape = source.Shape.makeFillet(float(args["radius"]), edge_objs)
    doc.openTransaction("MCP part fillet")
    result = doc.addObject("Part::Feature", args.get("result_name") or "Fillet")
    result.Shape = shape
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_part_chamfer(args):
    doc = App.openDocument(args["document_path"])
    source = get_object(doc, args["source_object"])
    edges = args.get("edge_indices") or list(range(1, len(source.Shape.Edges) + 1))
    edge_objs = [source.Shape.Edges[int(i) - 1] for i in edges]
    shape = source.Shape.makeChamfer(float(args["distance"]), edge_objs)
    doc.openTransaction("MCP part chamfer")
    result = doc.addObject("Part::Feature", args.get("result_name") or "Chamfer")
    result.Shape = shape
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_part_check_geometry(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Shape")]
    checks = []
    for name in names:
        obj = get_object(doc, name)
        shape = obj.Shape
        check_error = None
        try:
            shape.check(bool(args.get("run_bop_check", False)))
        except Exception as exc:
            check_error = str(exc)
        checks.append({"object": object_summary(obj), "is_valid": bool(shape.isValid()), "check_error": check_error})
    return {"checks": checks}


def action_sketch_create(args):
    doc = open_or_new(args)
    doc.openTransaction("MCP create sketch")
    sketch = doc.addObject("Sketcher::SketchObject", args.get("sketch_name") or "Sketch")
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "sketch": object_summary(sketch), "document": document_summary(doc)}


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


def make_constraint(spec):
    import Sketcher

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


def action_sketch_add_geometry(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    items = args.get("geometry") or []
    added = []
    doc.openTransaction("MCP add sketch geometry")
    for item in items:
        for geom in make_sketch_geometries(item):
            added.append(sketch.addGeometry(geom, bool(item.get("construction", False))))
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "added_indices": added, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_add_constraint(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    constraints = args.get("constraints") or []
    added = []
    doc.openTransaction("MCP add sketch constraints")
    for item in constraints:
        index = sketch.addConstraint(make_constraint(item))
        apply_constraint_metadata(sketch, index, item)
        added.append(index)
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "added_indices": added, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_add_profile(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    doc.openTransaction("MCP add sketch profile")
    added, constraints = add_profile_geometry(sketch, args["profile"])
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "profile_type": args["profile"].get("type"),
        "added_indices": added,
        "constraint_indices": constraints,
        "sketch": object_summary(sketch),
        "document": document_summary(doc),
    }


def action_sketch_edit_geometry(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    operations = args.get("operations") or []
    reports = []
    doc.openTransaction("MCP edit sketch geometry")
    for op in operations:
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
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_edit_constraints(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    operations = args.get("operations") or []
    reports = []
    doc.openTransaction("MCP edit sketch constraints")
    for op in operations:
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
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_transform(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    operations = args.get("operations") or []
    reports = []
    doc.openTransaction("MCP transform sketch")
    for op in operations:
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
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_auto_constrain(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    operations = args.get("operations") or [{"operation": "autoconstraint"}]
    reports = []
    doc.openTransaction("MCP auto constrain sketch")
    for op in operations:
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
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "reports": reports, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_validate(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    solve_code = sketch.solve() if bool(args.get("solve", True)) else None
    if bool(args.get("detect_missing", False)):
        sketch.detectMissingPointOnPointConstraints(float(args.get("precision", 1e-4)), bool(args.get("include_construction", True)))
        sketch.analyseMissingPointOnPointCoincident(angle_radians(args.get("angle_precision"), math.pi / 8))
        sketch.detectMissingVerticalHorizontalConstraints(angle_radians(args.get("angle_precision"), math.pi / 8))
        sketch.detectMissingEqualityConstraints(float(args.get("precision", 1e-4)))
    doc.recompute()
    constraint_errors = []
    if bool(args.get("include_constraint_errors", False)):
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


def action_import_file(args):
    doc = App.newDocument(args.get("document_name") or "Imported")
    doc = import_file(doc, args["input_path"])
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "document": document_summary(doc)}


def action_export_file(args):
    return action_document_export(args)


def action_supported_formats(args):
    return {
        "import": [".FCStd", ".step", ".stp", ".iges", ".igs", ".brep", ".brp", ".stl", ".obj", ".ply", ".off"],
        "export": [".FCStd", ".step", ".stp", ".iges", ".igs", ".brep", ".brp", ".stl", ".obj", ".ply", ".off"],
        "notes": "Formats depend on the actual FreeCAD build and installed modules.",
    }


def action_mesh_import(args):
    import Mesh

    doc = App.newDocument(args.get("document_name") or "MeshImport")
    Mesh.insert(args["input_path"], doc.Name)
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "document": document_summary(doc)}


def action_mesh_export(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Mesh")]
    objects = [get_object(doc, name) for name in names]
    output = safe_output_path(args["output_path"], args)
    if os.path.exists(output) and not bool(args.get("overwrite", False)):
        raise ValueError("output exists; pass overwrite=true: " + output)
    import Mesh

    Mesh.export(objects, output)
    return {"exported_path": output, "objects": [object_summary(obj) for obj in objects]}


def action_mesh_evaluate(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Mesh")]
    return {"meshes": [object_summary(get_object(doc, name)) for name in names]}


def action_mesh_repair(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [obj.Name for obj in doc.Objects if hasattr(obj, "Mesh")]
    actions = args.get("actions") or ["harmonize_normals"]
    reports = []
    doc.openTransaction("MCP mesh repair")
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
            replacement = doc.addObject("Mesh::Feature", args.get("result_name") or (obj.Name + "_Repaired"))
            replacement.Mesh = mesh
            assigned_to = replacement.Name
        reports.append({"object": obj.Name, "assigned_to": assigned_to, "actions": done, "errors": errors})
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "reports": reports, "document": document_summary(doc)}


def action_mesh_boolean(args):
    doc = App.openDocument(args["document_path"])
    objs = [get_object(doc, name) for name in args["object_names"]]
    operation = args.get("operation", "union")
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
            raise ValueError("mesh boolean operation is not supported by this FreeCAD build: " + operation)
    doc.openTransaction("MCP mesh boolean")
    result = doc.addObject("Mesh::Feature", args.get("result_name") or operation.title())
    result.Mesh = mesh
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "object": object_summary(result), "document": document_summary(doc)}


def action_assembly_create(args):
    doc = open_or_new(args)
    doc.openTransaction("MCP create assembly")
    assembly = doc.addObject("Assembly::AssemblyObject", args.get("assembly_name") or "Assembly")
    assembly.Type = "Assembly"
    assembly.newObject("Assembly::JointGroup", "Joints")
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "assembly": object_summary(assembly), "document": document_summary(doc)}


def action_assembly_insert(args):
    doc = App.openDocument(args["document_path"])
    assembly = get_object(doc, args["assembly_name"])
    target = get_object(doc, args["object_name"])
    doc.openTransaction("MCP assembly insert")
    link = assembly.newObject("App::Link", args.get("link_name") or target.Label)
    link.LinkedObject = target
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "link": object_summary(link), "document": document_summary(doc)}


def action_assembly_create_joint(args):
    import sys

    doc = App.openDocument(args["document_path"])
    assembly = get_object(doc, args["assembly_name"])
    try:
        import JointObject
        import UtilsAssembly
    except ImportError:
        assembly_mod = os.path.join(App.getResourceDir(), "Mod", "Assembly")
        if assembly_mod not in sys.path:
            sys.path.append(assembly_mod)
        import JointObject
        import UtilsAssembly

    joint_type = args.get("joint_type", "Fixed")
    if joint_type not in JointObject.JointTypes:
        raise ValueError("unsupported joint_type: " + str(joint_type))
    refs = []
    for ref in args.get("references") or []:
        obj = get_object(doc, ref["object_name"])
        sub = ref.get("sub_element") or ""
        vertex = ref.get("vertex") or sub
        refs.append([obj, [sub, vertex]])
    if refs and len(refs) != 2:
        raise ValueError("references must contain exactly two connector references")
    doc.openTransaction("MCP assembly joint")
    try:
        joint_group = UtilsAssembly.getJointGroup(assembly)
        joint = joint_group.newObject("App::FeaturePython", args.get("joint_name") or "Joint")
        JointObject.Joint(joint, JointObject.JointTypes.index(joint_type))
        if refs:
            joint.Proxy.setJointConnectors(joint, refs)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
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
        "note": "Created a native Assembly JointObject proxy. Connector-aware solving still depends on valid Assembly references and persistent GUI/workbench workflows.",
    }


def action_assembly_solve(args):
    doc = App.openDocument(args["document_path"])
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "document": document_summary(doc), "note": "Process-per-call bridge recomputed the assembly document; dedicated solver invocation is reserved for persistent bridge mode."}


def action_assembly_bom(args):
    doc = App.openDocument(args["document_path"])
    assembly = get_object(doc, args["assembly_name"]) if args.get("assembly_name") else None
    root = assembly.Group if assembly is not None else doc.Objects
    rows = []
    for obj in root:
        rows.append({"name": obj.Name, "label": obj.Label, "type_id": obj.TypeId})
    return {"rows": rows, "count": len(rows)}


DISPATCH = {
    "document_new": action_document_new,
    "document_open": action_document_open,
    "document_save": action_document_save,
    "document_recompute": action_document_recompute,
    "document_export": action_document_export,
    "object_list": action_object_list,
    "object_get": action_object_get,
    "object_set_properties": action_object_set_properties,
    "object_delete": action_object_delete,
    "part_create_primitive": action_part_create_primitive,
    "part_boolean": action_part_boolean,
    "part_extrude": action_part_extrude,
    "part_revolve": action_part_revolve,
    "part_fillet": action_part_fillet,
    "part_chamfer": action_part_chamfer,
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
    "import_file": action_import_file,
    "export_file": action_export_file,
    "supported_formats": action_supported_formats,
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
}


try:
    payload = DISPATCH[ARGS["action"]](ARGS)
    payload["ok"] = True
    payload["action"] = ARGS["action"]
    emit(payload)
except Exception as exc:
    emit({"ok": False, "action": ARGS.get("action"), "error": str(exc), "traceback": traceback.format_exc()})
    raise
"""


class CadToolService:
    """Typed document/object/geometry tools."""

    def __init__(self, discovery: FreeCadDiscovery | None = None):
        self.discovery = discovery or FreeCadDiscovery()

    def definitions(self) -> list[ToolDefinition]:
        return [
            self._tool("freecad_document_new", "Create FreeCAD Document", "Create a new FreeCAD document.", {"document_name": {"type": "string"}, "label": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "document_new"),
            self._tool("freecad_document_open", "Open FreeCAD Document", "Open a FreeCAD document and return a summary.", {"document_path": {"type": "string"}}, ["document_path"], "document_open"),
            self._tool("freecad_document_save", "Save FreeCAD Document", "Open and save a FreeCAD document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["document_path"], "document_save"),
            self._tool("freecad_document_recompute", "Recompute FreeCAD Document", "Open/recompute a document and optionally save it.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "document_recompute"),
            self._tool("freecad_document_export", "Export FreeCAD Document", "Export selected or all document objects.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "document_export"),
            self._tool("freecad_object_list", "List FreeCAD Objects", "List document objects.", {"document_path": {"type": "string"}}, ["document_path"], "object_list"),
            self._tool("freecad_object_get", "Get FreeCAD Object", "Inspect one document object.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "include_properties": {"type": "boolean"}}, ["document_path", "object_name"], "object_get"),
            self._tool("freecad_object_set_properties", "Set FreeCAD Object Properties", "Set simple object properties and save optionally.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "properties": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_name", "properties"], "object_set_properties"),
            self._tool("freecad_object_delete", "Delete FreeCAD Objects", "Delete object(s) by name/label.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "object_delete"),
            self._tool("freecad_part_create_primitive", "Create Part Primitive", "Create a Part primitive.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "primitive": {"type": "string", "enum": ["box", "cylinder", "sphere", "cone", "torus"]}, "object_name": {"type": "string"}, "properties": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "part_create_primitive"),
            self._tool("freecad_part_boolean", "Part Boolean", "Fuse/cut/common Part shapes.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "operation": {"type": "string", "enum": ["fuse", "cut", "common"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_names"], "part_boolean"),
            self._tool("freecad_part_extrude", "Part Extrude", "Extrude a source shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "vector": {"type": "array", "items": {"type": "number"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object"], "part_extrude"),
            self._tool("freecad_part_revolve", "Part Revolve", "Revolve a source shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "base": {"type": "array", "items": {"type": "number"}}, "axis": {"type": "array", "items": {"type": "number"}}, "angle": {"type": "number"}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object"], "part_revolve"),
            self._tool("freecad_part_fillet", "Part Fillet", "Create a filleted copy of a shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "radius": {"type": "number"}, "edge_indices": {"type": "array", "items": {"type": "integer"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object", "radius"], "part_fillet"),
            self._tool("freecad_part_chamfer", "Part Chamfer", "Create a chamfered copy of a shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "distance": {"type": "number"}, "edge_indices": {"type": "array", "items": {"type": "integer"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object", "distance"], "part_chamfer"),
            self._tool("freecad_part_check_geometry", "Check Part Geometry", "Run shape validity checks.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "run_bop_check": {"type": "boolean"}}, ["document_path"], "part_check_geometry"),
            self._tool("freecad_sketch_create", "Create Sketch", "Create a Sketcher object.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "sketch_create"),
            self._tool(
                "freecad_sketch_add_geometry",
                "Add Sketch Geometry",
                "Add point, line, circle, arc, ellipse, conic arc, B-spline, or polyline geometry to a sketch.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "geometry": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "geometry"],
                "sketch_add_geometry",
            ),
            self._tool(
                "freecad_sketch_add_constraint",
                "Add Sketch Constraint",
                "Add raw or named Sketcher constraints with optional metadata such as datum, driving, active, visibility, and label placement.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "constraints"],
                "sketch_add_constraint",
            ),
            self._tool(
                "freecad_sketch_add_profile",
                "Add Sketch Profile",
                "Add common closed/open Sketcher profiles such as rectangle, polyline, regular polygon, circle, and slot.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "profile": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "profile"],
                "sketch_add_profile",
            ),
            self._tool(
                "freecad_sketch_edit_geometry",
                "Edit Sketch Geometry",
                "Delete, move, toggle construction state, add external geometry, carbon-copy, and maintain internal/degenerated Sketcher geometry.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_edit_geometry",
            ),
            self._tool(
                "freecad_sketch_edit_constraints",
                "Edit Sketch Constraints",
                "Delete, rename, set datum/driving/active/visibility/virtual-space state, validate, and auto-remove redundant Sketcher constraints.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_edit_constraints",
            ),
            self._tool(
                "freecad_sketch_transform",
                "Transform Sketch Geometry",
                "Run headless Sketcher transform operations such as fillet, trim, extend, split, join, copy, move, symmetry, rectangular array, and B-spline edits.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_transform",
            ),
            self._tool(
                "freecad_sketch_auto_constrain",
                "Auto Constrain Sketch",
                "Detect/apply missing Sketcher coincident, vertical/horizontal, equality constraints, run autoconstraint, and validate/clean constraints.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_auto_constrain",
            ),
            self._tool(
                "freecad_sketch_validate",
                "Validate Sketch",
                "Solve and summarize sketch geometry, constraints, solver diagnostics, missing constraints, open vertices, and per-constraint errors.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "solve": {"type": "boolean"}, "detect_missing": {"type": "boolean"}, "include_constraint_errors": {"type": "boolean"}, "precision": {"type": "number"}, "angle_precision": {"type": "number"}, "include_construction": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_validate",
            ),
            self._tool("freecad_import_file", "Import File", "Import a CAD/mesh file into a document.", {"input_path": {"type": "string"}, "document_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["input_path"], "import_file"),
            self._tool("freecad_export_file", "Export File", "Export selected/all objects from a document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "export_file"),
            self._tool("freecad_supported_formats", "Supported Formats", "Return common import/export formats.", {}, [], "supported_formats"),
            self._tool("freecad_mesh_import", "Import Mesh", "Import a mesh file into a document.", {"input_path": {"type": "string"}, "document_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["input_path"], "mesh_import"),
            self._tool("freecad_mesh_export", "Export Mesh", "Export mesh objects.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "mesh_export"),
            self._tool("freecad_mesh_evaluate", "Evaluate Mesh", "Summarize mesh object health.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}}, ["document_path"], "mesh_evaluate"),
            self._tool("freecad_mesh_repair", "Repair Mesh", "Run conservative mesh repair actions.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "actions": {"type": "array", "items": {"type": "string", "enum": ["harmonize_normals", "remove_duplicated_points"]}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "mesh_repair"),
            self._tool("freecad_mesh_boolean", "Mesh Boolean", "Run mesh boolean operation when supported by FreeCAD build.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "operation": {"type": "string", "enum": ["union", "difference", "intersection"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_names"], "mesh_boolean"),
            self._tool("freecad_assembly_create", "Create Assembly", "Create an Assembly object.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "assembly_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "assembly_create"),
            self._tool("freecad_assembly_insert", "Insert Assembly Link", "Insert an existing object into an assembly as an App::Link.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "object_name": {"type": "string"}, "link_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name", "object_name"], "assembly_insert"),
            self._tool("freecad_assembly_create_joint", "Create Assembly Joint", "Create a native Assembly JointObject proxy under an assembly joint group.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "joint_type": {"type": "string", "enum": ["Fixed", "Revolute", "Cylindrical", "Slider", "Ball", "Distance", "Parallel", "Perpendicular", "Angle", "RackPinion", "Screw", "Gears", "Belt"]}, "joint_name": {"type": "string"}, "references": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name"], "assembly_create_joint"),
            self._tool("freecad_assembly_solve", "Solve Assembly", "Recompute an assembly document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "assembly_solve"),
            self._tool("freecad_assembly_bom", "Assembly BOM", "Return a simple assembly bill of materials.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}}, ["document_path"], "assembly_bom"),
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def _tool(
        self,
        name: str,
        title: str,
        description: str,
        properties: JsonObject,
        required: list[str],
        action: str,
    ) -> ToolDefinition:
        schema = {"type": "object", "properties": {**properties, **COMMON_RUNTIME_PROPS}}
        if required:
            schema["required"] = required
        return ToolDefinition(
            name,
            title,
            description,
            schema,
            lambda args, action=action, required=required: self._run(action, args, required),
        )

    def _run(self, action: str, args: JsonObject, required: list[str]) -> JsonObject:
        for key in required:
            if key not in args or args[key] in (None, ""):
                raise ToolInputError(f"{key} is required")
        executable_arg = optional_string(args, "executable")
        freecad_home = optional_string(args, "freecad_home")
        timeout_sec = bounded_int(args, "timeout_sec", default=60, minimum=1, maximum=180)
        compact_execution = args.get("compact_execution", False)
        if not isinstance(compact_execution, bool):
            raise ToolInputError("compact_execution must be a boolean")
        discovery = self.discovery.discover(executable=executable_arg, freecad_home=freecad_home)
        if discovery.executable is None:
            raise ToolInputError(
                "FreeCADCmd not found. Set FREECAD_MCP_FREECAD_HOME, FREECAD_MCP_FREECAD_CMD, "
                "or pass freecad_home/executable."
            )

        action_args = {
            key: value
            for key, value in args.items()
            if key not in {"executable", "freecad_home", "timeout_sec", "compact_execution"}
        }
        action_args["_workspace_root"] = os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or str(Path.cwd())
        action_args["action"] = action
        if action == "object_delete" and not action_args.get("object_name") and not action_args.get("object_names"):
            raise ToolInputError("object_name or object_names is required")
        encoded_args = base64.b64encode(json.dumps(action_args).encode("utf-8")).decode("ascii")
        code = CAD_ACTION_SCRIPT.replace("__ARGS_B64__", encoded_args)
        result = FreeCadCmdBridge(Path(discovery.executable)).execute_python(code, timeout_sec=timeout_sec)
        payload = parse_prefixed_json(result.stdout)
        if result.ok and payload is None:
            raise ToolInputError("FreeCAD response did not include a valid MCP JSON payload")
        return {
            "discovery": discovery.to_dict(),
            "execution": result.to_compact_dict() if compact_execution else result.to_dict(),
            "freecad": payload,
        }
