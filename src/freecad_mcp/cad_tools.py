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
    "allow_external_paths": {
        "type": "boolean",
        "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace.",
    },
}


CAD_ACTION_SCRIPT = r"""
import base64
import json
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


def object_summary(obj):
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "visibility": bool(getattr(obj, "Visibility", False)),
        "placement": placement_summary(obj),
        "shape": shape_summary(obj),
        "mesh": mesh_summary(obj),
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


def action_sketch_add_geometry(args):
    import Part

    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    items = args.get("geometry") or []
    added = []
    doc.openTransaction("MCP add sketch geometry")
    for item in items:
        kind = item.get("type")
        if kind == "line":
            geom = Part.LineSegment(vector(item["start"]), vector(item["end"]))
        elif kind == "circle":
            geom = Part.Circle(vector(item.get("center"), [0, 0, 0]), vector(item.get("normal"), [0, 0, 1]), float(item["radius"]))
        elif kind == "arc":
            geom = Part.ArcOfCircle(
                Part.Circle(vector(item.get("center"), [0, 0, 0]), vector(item.get("normal"), [0, 0, 1]), float(item["radius"])),
                float(item["start_angle"]),
                float(item["end_angle"]),
            )
        else:
            raise ValueError("unsupported sketch geometry: " + str(kind))
        added.append(sketch.addGeometry(geom, bool(item.get("construction", False))))
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "added_indices": added, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_add_constraint(args):
    import Sketcher

    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    constraints = args.get("constraints") or []
    added = []
    doc.openTransaction("MCP add sketch constraints")
    for item in constraints:
        kind = item.get("type")
        values = item.get("values") or []
        added.append(sketch.addConstraint(Sketcher.Constraint(kind, *values)))
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "added_indices": added, "sketch": object_summary(sketch), "document": document_summary(doc)}


def action_sketch_validate(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    doc.recompute()
    return {
        "sketch": object_summary(sketch),
        "geometry_count": len(sketch.Geometry),
        "constraint_count": len(sketch.Constraints),
        "degrees_of_freedom": getattr(sketch, "DegreesOfFreedom", None),
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
    doc = App.openDocument(args["document_path"])
    assembly = get_object(doc, args["assembly_name"])
    joint_group = None
    for child in assembly.Group:
        if child.TypeId == "Assembly::JointGroup":
            joint_group = child
            break
    if joint_group is None:
        joint_group = assembly.newObject("Assembly::JointGroup", "Joints")
    doc.openTransaction("MCP assembly joint placeholder")
    joint = joint_group.newObject("App::FeaturePython", args.get("joint_name") or "Joint")
    joint.addProperty("App::PropertyString", "JointType", "Joint")
    joint.JointType = args.get("joint_type", "Fixed")
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "joint": object_summary(joint), "document": document_summary(doc), "note": "Placeholder joint metadata; full connector solving requires GUI/workbench bridge."}


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
            self._tool("freecad_sketch_add_geometry", "Add Sketch Geometry", "Add line/circle/arc geometry to a sketch.", {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "geometry": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name", "geometry"], "sketch_add_geometry"),
            self._tool("freecad_sketch_add_constraint", "Add Sketch Constraint", "Add Sketcher constraints.", {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name", "constraints"], "sketch_add_constraint"),
            self._tool("freecad_sketch_validate", "Validate Sketch", "Summarize sketch geometry and constraints.", {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}}, ["document_path", "sketch_name"], "sketch_validate"),
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
            self._tool("freecad_assembly_create_joint", "Create Assembly Joint", "Create placeholder joint metadata under an assembly joint group.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "joint_type": {"type": "string"}, "joint_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name"], "assembly_create_joint"),
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
        discovery = self.discovery.discover(executable=executable_arg, freecad_home=freecad_home)
        if discovery.executable is None:
            raise ToolInputError(
                "FreeCADCmd not found. Set FREECAD_MCP_FREECAD_HOME, FREECAD_MCP_FREECAD_CMD, "
                "or pass freecad_home/executable."
            )

        action_args = {key: value for key, value in args.items() if key not in {"executable", "freecad_home", "timeout_sec"}}
        action_args["_workspace_root"] = os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or str(Path.cwd())
        action_args["action"] = action
        if action == "object_delete" and not action_args.get("object_name") and not action_args.get("object_names"):
            raise ToolInputError("object_name or object_names is required")
        encoded_args = base64.b64encode(json.dumps(action_args).encode("utf-8")).decode("ascii")
        code = CAD_ACTION_SCRIPT.replace("__ARGS_B64__", encoded_args)
        result = FreeCadCmdBridge(Path(discovery.executable)).execute_python(code, timeout_sec=timeout_sec)
        payload = parse_prefixed_json(result.stdout)
        return {
            "discovery": discovery.to_dict(),
            "execution": result.to_dict(),
            "freecad": payload,
        }
