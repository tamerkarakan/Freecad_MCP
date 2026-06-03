
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


def requested_arc_sweep(start_angle, end_angle, *, direction=None, sweep=None):
    two_pi = 2.0 * math.pi
    delta_ccw = (float(end_angle) - float(start_angle)) % two_pi
    if abs(delta_ccw) < 1e-12:
        raise ValueError("arc start and end resolve to the same point; use circle geometry for full circles")
    delta_cw = delta_ccw - two_pi
    direction_value = str(direction or "").lower()
    if direction_value:
        if direction_value == "ccw":
            return delta_ccw
        if direction_value == "cw":
            return delta_cw
        raise ValueError("unsupported arc direction: " + str(direction))
    sweep_value = str(sweep or "minor").lower()
    if sweep_value == "minor":
        return delta_ccw if delta_ccw <= math.pi else delta_cw
    if sweep_value == "major":
        return delta_ccw if delta_ccw > math.pi else delta_cw
    raise ValueError("unsupported arc sweep: " + str(sweep))


def arc_point(center, radius, angle):
    return App.Vector(center.x + radius * math.cos(angle), center.y + radius * math.sin(angle), center.z)


def make_center_angle_arc(item):
    import Part

    center = vector(item.get("center"), [0, 0, 0])
    radius = float(item["radius"])
    start_angle = angle_radians(item["start_angle"])
    end_angle = angle_radians(item["end_angle"])
    if item.get("direction") or item.get("sweep"):
        sweep = requested_arc_sweep(start_angle, end_angle, direction=item.get("direction"), sweep=item.get("sweep"))
        return Part.ArcOfCircle(
            arc_point(center, radius, start_angle),
            arc_point(center, radius, start_angle + sweep / 2.0),
            arc_point(center, radius, start_angle + sweep),
        )
    circle = Part.Circle(center, vector(item.get("normal"), [0, 0, 1]), radius)
    return Part.ArcOfCircle(circle, start_angle, end_angle)


def make_start_end_radius_arc(item):
    import Part

    start = vector(item["start"])
    end = vector(item["end"])
    radius = float(item["radius"])
    side = str(item.get("side", "left")).lower()
    if side not in {"left", "right"}:
        raise ValueError("arc_start_end_radius side must be left or right")
    sweep_mode = str(item.get("sweep", "minor")).lower()
    if sweep_mode not in {"minor", "major"}:
        raise ValueError("arc_start_end_radius sweep must be minor or major")
    dx = end.x - start.x
    dy = end.y - start.y
    chord = math.hypot(dx, dy)
    if chord <= 1e-12:
        raise ValueError("arc_start_end_radius requires distinct start and end points")
    if radius < chord / 2.0 - 1e-9:
        raise ValueError("arc_start_end_radius radius is smaller than half the chord")
    midpoint = App.Vector((start.x + end.x) / 2.0, (start.y + end.y) / 2.0, (start.z + end.z) / 2.0)
    normal_left = App.Vector(-dy / chord, dx / chord, 0)
    height = math.sqrt(max(radius * radius - (chord / 2.0) * (chord / 2.0), 0.0))
    candidates = [midpoint + normal_left * height, midpoint - normal_left * height]
    selected = None
    selected_mid = None
    for center in candidates:
        start_angle = math.atan2(start.y - center.y, start.x - center.x)
        end_angle = math.atan2(end.y - center.y, end.x - center.x)
        sweep = requested_arc_sweep(start_angle, end_angle, sweep=sweep_mode)
        midpoint_on_arc = arc_point(center, radius, start_angle + sweep / 2.0)
        side_value = "left" if dx * (midpoint_on_arc.y - start.y) - dy * (midpoint_on_arc.x - start.x) >= 0 else "right"
        if side_value == side or height <= 1e-12:
            selected = center
            selected_mid = midpoint_on_arc
            break
    if selected is None or selected_mid is None:
        raise ValueError("arc_start_end_radius could not satisfy requested side and sweep")
    return Part.ArcOfCircle(start, selected_mid, end)


def sketch_arc_geometry_report(geom, geometry_index, input_type):
    if normalized_profile_segment_type(input_type) != "arc":
        return None
    try:
        center = getattr(geom, "Center", getattr(getattr(geom, "Circle", None), "Center", None))
        radius = getattr(geom, "Radius", getattr(getattr(geom, "Circle", None), "Radius", None))
        normal = getattr(geom, "Axis", getattr(getattr(geom, "Circle", None), "Axis", None))
        first = float(getattr(geom, "FirstParameter"))
        last = float(getattr(geom, "LastParameter"))
        return {
            "geometry_index": int(geometry_index),
            "input_type": input_type,
            "native_type": type(geom).__name__,
            "actual_start": point_list(geom.StartPoint),
            "actual_end": point_list(geom.EndPoint),
            "center": point_list(center) if center is not None else None,
            "radius": float(radius) if radius is not None else None,
            "sweep_deg": abs(math.degrees(last - first)),
            "normal": point_list(normal) if normal is not None else None,
        }
    except Exception as exc:
        return {
            "geometry_index": int(geometry_index),
            "input_type": input_type,
            "native_type": type(geom).__name__,
            "report_error": str(exc),
        }


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
    if shape is None:
        return None
    if shape.isNull():
        return {
            "valid": False,
            "is_null": True,
            "solids": 0,
            "shells": 0,
            "faces": 0,
            "edges": 0,
            "vertices": 0,
            "bound_box": None,
        }
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "is_null": False,
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


def partdesign_summary(obj):
    type_id = getattr(obj, "TypeId", "")
    if not str(type_id).startswith("PartDesign::"):
        return None
    summary = {"type": type_id}
    if type_id == "PartDesign::Body":
        summary["members"] = [getattr(member, "Name", str(member)) for member in getattr(obj, "Group", [])]
        summary["tip"] = getattr(getattr(obj, "Tip", None), "Name", None)
        origin = getattr(obj, "Origin", None)
        summary["origin"] = getattr(origin, "Name", None)
        planes = []
        if origin is not None:
            for item in getattr(origin, "OutList", []) or []:
                if getattr(item, "TypeId", "") == "App::Plane":
                    planes.append({"name": item.Name, "label": item.Label})
        summary["planes"] = planes
    elif type_id.startswith("PartDesign::Pad") or type_id.startswith("PartDesign::Pocket"):
        profile = getattr(obj, "Profile", None)
        summary["profile"] = getattr(profile, "Name", None)
        if hasattr(obj, "Length"):
            summary["length"] = quantity_summary(obj.Length)
        if hasattr(obj, "Length2"):
            summary["length2"] = quantity_summary(obj.Length2)
        if hasattr(obj, "Midplane"):
            summary["midplane"] = bool(obj.Midplane)
        if hasattr(obj, "Reversed"):
            summary["reversed"] = bool(obj.Reversed)
    elif type_id.startswith("PartDesign::Hole"):
        profile = getattr(obj, "Profile", None)
        summary["profile"] = getattr(profile, "Name", None)
        for prop in ("Diameter", "Depth", "DrillPointAngle", "TaperedAngle", "HoleCutDiameter", "HoleCutDepth", "HoleCutCountersinkAngle"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = quantity_summary(getattr(obj, prop))
        for prop in ("DepthType", "DrillPoint", "Tapered", "ThreadType", "HoleCutType"):
            if hasattr(obj, prop):
                value = getattr(obj, prop)
                summary[prop[0].lower() + prop[1:]] = value if isinstance(value, (str, int, float, bool)) else str(value)
    elif type_id.startswith("PartDesign::Revolution") or type_id.startswith("PartDesign::Groove"):
        profile = getattr(obj, "Profile", None)
        summary["profile"] = getattr(profile, "Name", None)
        for prop in ("Angle", "Angle2"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = quantity_summary(getattr(obj, prop))
        for prop in ("Type", "Midplane", "Reversed", "FuseOrder"):
            if hasattr(obj, prop):
                value = getattr(obj, prop)
                summary[prop[0].lower() + prop[1:]] = value if isinstance(value, (str, int, float, bool)) else str(value)
        axis = getattr(obj, "ReferenceAxis", None)
        if axis:
            try:
                axis_obj, axis_subs = axis
                summary["referenceAxis"] = {
                    "object": getattr(axis_obj, "Name", None),
                    "subnames": list(axis_subs or []),
                }
            except Exception:
                summary["referenceAxis"] = str(axis)
    elif type_id.startswith("PartDesign::AdditiveLoft") or type_id.startswith("PartDesign::SubtractiveLoft"):
        profile = getattr(obj, "Profile", None)
        summary["profile"] = link_item_summary(profile)
        summary["sections"] = link_list_summary(getattr(obj, "Sections", []))
        if hasattr(obj, "Ruled"):
            summary["ruled"] = bool(obj.Ruled)
        if hasattr(obj, "Closed"):
            summary["closed"] = bool(obj.Closed)
    elif type_id.startswith("PartDesign::AdditivePipe") or type_id.startswith("PartDesign::SubtractivePipe"):
        summary["profile"] = link_item_summary(getattr(obj, "Profile", None))
        summary["spine"] = link_item_summary(getattr(obj, "Spine", None))
        summary["auxiliary_spine"] = link_item_summary(getattr(obj, "AuxiliarySpine", None))
        summary["sections"] = link_list_summary(getattr(obj, "Sections", []))
        if hasattr(obj, "SpineTangent"):
            summary["spine_tangent"] = bool(obj.SpineTangent)
        if hasattr(obj, "AuxiliarySpineTangent"):
            summary["auxiliary_spine_tangent"] = bool(obj.AuxiliarySpineTangent)
        if hasattr(obj, "AuxiliaryCurvilinear"):
            summary["auxiliary_curvilinear"] = bool(obj.AuxiliaryCurvilinear)
        if hasattr(obj, "Mode"):
            summary["mode"] = str(obj.Mode)
        if hasattr(obj, "Binormal"):
            summary["binormal"] = point_list(obj.Binormal)
        if hasattr(obj, "Transition"):
            summary["transition"] = str(obj.Transition)
        if hasattr(obj, "Transformation"):
            summary["transformation"] = str(obj.Transformation)
    elif (
        type_id.startswith("PartDesign::LinearPattern")
        or type_id.startswith("PartDesign::PolarPattern")
        or type_id.startswith("PartDesign::Mirrored")
    ):
        summary["originals"] = link_list_summary(getattr(obj, "Originals", []))
        if hasattr(obj, "TransformMode"):
            summary["transform_mode"] = str(obj.TransformMode)
        if hasattr(obj, "Direction"):
            summary["direction"] = link_item_summary(getattr(obj, "Direction", None))
        if hasattr(obj, "Direction2"):
            summary["direction2"] = link_item_summary(getattr(obj, "Direction2", None))
        if hasattr(obj, "Axis"):
            summary["axis"] = link_item_summary(getattr(obj, "Axis", None))
        if hasattr(obj, "MirrorPlane"):
            summary["mirror_plane"] = link_item_summary(getattr(obj, "MirrorPlane", None))
        for prop in ("Length", "Offset", "Length2", "Offset2", "Angle"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = quantity_summary(getattr(obj, prop))
        for prop in ("Occurrences", "Occurrences2", "Mode", "Mode2"):
            if hasattr(obj, prop):
                value = getattr(obj, prop)
                summary[prop[0].lower() + prop[1:]] = value if isinstance(value, (str, int, float, bool)) else str(value)
        for prop in ("Reversed", "Reversed2"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = bool(getattr(obj, prop))
    elif (
        type_id.startswith("PartDesign::Fillet")
        or type_id.startswith("PartDesign::Chamfer")
        or type_id.startswith("PartDesign::Thickness")
        or type_id.startswith("PartDesign::Draft")
    ):
        summary["base"] = link_item_summary(getattr(obj, "Base", None))
        if hasattr(obj, "SupportTransform"):
            summary["support_transform"] = bool(obj.SupportTransform)
        if hasattr(obj, "UseAllEdges"):
            summary["use_all_edges"] = bool(obj.UseAllEdges)
        if hasattr(obj, "Radius"):
            summary["radius"] = quantity_summary(obj.Radius)
        if hasattr(obj, "ChamferType"):
            summary["chamfer_type"] = str(obj.ChamferType)
        for prop in ("Size", "Size2", "Value", "Angle"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = quantity_summary(getattr(obj, prop))
        for prop in ("FlipDirection", "Reversed", "Intersection"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = bool(getattr(obj, prop))
        for prop in ("Mode", "Join"):
            if hasattr(obj, prop):
                summary[prop[0].lower() + prop[1:]] = str(getattr(obj, prop))
        if hasattr(obj, "NeutralPlane"):
            summary["neutral_plane"] = link_item_summary(getattr(obj, "NeutralPlane", None))
        if hasattr(obj, "PullDirection"):
            summary["pull_direction"] = link_item_summary(getattr(obj, "PullDirection", None))
    elif type_id in {"PartDesign::Plane", "PartDesign::Line", "PartDesign::Point", "PartDesign::CoordinateSystem"}:
        summary["attachment"] = attachment_summary(obj)
    return summary


def link_item_summary(item):
    if isinstance(item, (list, tuple)):
        target = item[0] if item else None
        subnames = item[1] if len(item) > 1 else []
    else:
        target = item
        subnames = []
    if isinstance(subnames, str):
        subnames = [subnames] if subnames else []
    return {
        "object": getattr(target, "Name", None),
        "label": getattr(target, "Label", None),
        "type_id": getattr(target, "TypeId", None),
        "subnames": list(subnames or []),
    }


def link_list_summary(values):
    try:
        return [link_item_summary(item) for item in list(values or [])]
    except Exception:
        return [{"raw": str(values)}]


def attachment_summary(obj):
    supports = []
    try:
        for item in getattr(obj, "AttachmentSupport", []) or []:
            if isinstance(item, (list, tuple)):
                support_obj = item[0] if item else None
                subnames = item[1] if len(item) > 1 else []
            else:
                support_obj = item
                subnames = []
            if isinstance(subnames, str):
                subnames = [subnames] if subnames else []
            supports.append(
                {
                    "object": getattr(support_obj, "Name", None),
                    "label": getattr(support_obj, "Label", None),
                    "type_id": getattr(support_obj, "TypeId", None),
                    "subnames": list(subnames or []),
                }
            )
    except Exception:
        supports = [{"raw": str(getattr(obj, "AttachmentSupport", ""))}]
    offset = getattr(obj, "AttachmentOffset", None)
    return {
        "support": supports,
        "map_mode": str(getattr(obj, "MapMode", "")),
        "offset_base": point_list(offset.Base) if offset is not None and hasattr(offset, "Base") else None,
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
        "partdesign": partdesign_summary(obj),
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


def get_object_for_label_update(doc, selector):
    obj = doc.getObject(selector)
    if obj is not None:
        return obj
    matches = [candidate for candidate in doc.Objects if candidate.Label == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError("object label is ambiguous: " + str(selector))
    raise ValueError("object not found: " + str(selector))


def ensure_unique_label(doc, obj, label):
    obj_name = getattr(obj, "Name", None)
    for candidate in doc.Objects:
        if getattr(candidate, "Name", None) != obj_name and candidate.Label == label:
            raise ValueError("label already exists on object: " + candidate.Name)


def property_value_summary(value):
    if hasattr(value, "Name") and hasattr(value, "TypeId"):
        return {"$ref": value.Name, "label": value.Label, "type_id": value.TypeId}
    if isinstance(value, (list, tuple)):
        return [property_value_summary(item) for item in value]
    if isinstance(value, dict):
        return {str(key): property_value_summary(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def resolve_property_value(doc, value):
    if isinstance(value, dict):
        if "$ref" in value:
            return get_object(doc, str(value["$ref"]))
        if "$refs" in value:
            return [get_object(doc, str(name)) for name in (value.get("$refs") or [])]
        if "$link" in value:
            return get_object(doc, str(value["$link"]))
        if "$links" in value:
            return [get_object(doc, str(name)) for name in (value.get("$links") or [])]
        return {key: resolve_property_value(doc, item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_property_value(doc, item) for item in value]
    return value


def normalize_partdesign_plane(value):
    raw = str(value or "XY").upper().replace("_PLANE", "").replace("-PLANE", "").replace(" PLANE", "")
    if raw not in {"XY", "XZ", "YZ"}:
        raise ValueError("attachment_plane must be one of XY, XZ, or YZ")
    return raw


def find_body_origin_plane(body, plane_name):
    plane = normalize_partdesign_plane(plane_name)
    origin = getattr(body, "Origin", None)
    for item in getattr(origin, "OutList", []) or []:
        if getattr(item, "TypeId", "") == "App::Plane" and (item.Name.startswith(plane + "_Plane") or item.Label.startswith(plane + "-plane")):
            return item
    raise ValueError("origin plane not found for body " + body.Name + ": " + plane)


def resolve_partdesign_attachment_support(doc, body, params):
    support_name = (
        params.get("attachment_object")
        or params.get("attachment_object_name")
        or params.get("support_object")
        or params.get("support_object_name")
        or params.get("datum_plane_name")
    )
    if support_name:
        support = get_object(doc, support_name)
        subname = params.get("attachment_subname") or params.get("support_subname") or ""
        return support, str(subname), {
            "support_type": "object",
            "support_object": getattr(support, "Name", None),
            "support_label": getattr(support, "Label", None),
            "support_type_id": getattr(support, "TypeId", None),
            "support_subname": str(subname),
        }
    plane_name = normalize_partdesign_plane(params.get("attachment_plane") or params.get("plane") or "XY")
    plane = find_body_origin_plane(body, plane_name)
    return plane, "", {
        "support_type": "origin_plane",
        "plane": plane_name,
        "plane_object": plane.Name,
        "support_object": plane.Name,
        "support_subname": "",
    }


def attachment_support_name(params):
    return (
        params.get("attachment_object")
        or params.get("attachment_object_name")
        or params.get("support_object")
        or params.get("support_object_name")
        or params.get("datum_plane_name")
    )


def attachment_requested(params):
    return any(
        key in params
        for key in (
            "body_name",
            "attachment_plane",
            "plane",
            "attachment_object",
            "attachment_object_name",
            "support_object",
            "support_object_name",
            "datum_plane_name",
            "attachment_subname",
            "support_subname",
            "attachment_map_mode",
            "map_mode",
            "attachment_offset",
            "offset",
            "attachment_offset_vector",
            "offset_vector",
            "create_body_if_missing",
        )
    )


def attachment_target_requested(params):
    return any(
        key in params
        for key in (
            "attachment_plane",
            "plane",
            "attachment_object",
            "attachment_object_name",
            "support_object",
            "support_object_name",
            "datum_plane_name",
            "attachment_subname",
            "support_subname",
            "attachment_map_mode",
            "map_mode",
            "attachment_offset",
            "offset",
            "attachment_offset_vector",
            "offset_vector",
        )
    )


def apply_attachment_offset(obj, params):
    raw_vector = params.get("attachment_offset_vector") or params.get("offset_vector")
    if raw_vector is None and (params.get("attachment_offset") is not None or params.get("offset") is not None):
        offset = params.get("attachment_offset")
        if offset is None:
            offset = params.get("offset")
        raw_vector = [0, 0, float(offset)]
    if raw_vector is None:
        return None
    placement = App.Placement(vector(raw_vector), App.Rotation())
    obj.AttachmentOffset = placement
    return point_list(placement.Base)


def object_solid_count(obj):
    shape = getattr(obj, "Shape", None) if obj is not None else None
    return len(shape.Solids) if shape is not None and not shape.isNull() else 0


def find_body_solid_tip(body):
    tip = getattr(body, "Tip", None)
    if object_solid_count(tip) > 0:
        return tip
    for candidate in reversed(list(getattr(body, "Group", []) or [])):
        if object_solid_count(candidate) > 0:
            return candidate
    return None


def enum_index(value, mapping, default_key, field_name):
    if value is None:
        return mapping[default_key]
    if isinstance(value, (int, float)):
        return int(value)
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if raw in mapping:
        return mapping[raw]
    raise ValueError(field_name + " must be one of: " + ", ".join(sorted(mapping)))


def apply_hole_parameters(hole, params):
    if hasattr(hole, "Diameter"):
        hole.Diameter = float(params["diameter"])
    if hasattr(hole, "Depth"):
        hole.Depth = float(params.get("depth", 10.0))
    if hasattr(hole, "DepthType"):
        hole.DepthType = enum_index(params.get("depth_type"), {"dimension": 0, "blind": 0, "through_all": 1, "through": 1}, "dimension", "depth_type")
    if hasattr(hole, "ThreadType"):
        thread_type = params.get("thread_type", 0)
        hole.ThreadType = 0 if str(thread_type).strip().lower() in {"", "none"} else int(thread_type)
    if hasattr(hole, "HoleCutType"):
        hole.HoleCutType = enum_index(params.get("hole_cut_type"), {"none": 0, "counterbore": 1, "countersink": 2}, "none", "hole_cut_type")
    if hasattr(hole, "DrillPoint"):
        hole.DrillPoint = enum_index(params.get("drill_point"), {"flat": 0, "none": 0, "angled": 1}, "flat", "drill_point")
    if hasattr(hole, "Tapered"):
        hole.Tapered = bool(params.get("tapered", False))
    optional_lengths = {
        "drill_point_angle": "DrillPointAngle",
        "tapered_angle": "TaperedAngle",
        "hole_cut_diameter": "HoleCutDiameter",
        "hole_cut_depth": "HoleCutDepth",
        "hole_cut_countersink_angle": "HoleCutCountersinkAngle",
    }
    for key, prop in optional_lengths.items():
        if params.get(key) is not None and hasattr(hole, prop):
            setattr(hole, prop, float(params[key]))


def resolve_partdesign_reference_axis(doc, sketch, params):
    object_name = params.get("reference_axis_object") or params.get("axis_object_name")
    if object_name:
        axis_obj = get_object(doc, object_name)
        subname = params.get("reference_axis_subname") or params.get("axis_subname") or ""
        return (axis_obj, [str(subname)] if subname else [""])
    raw = str(params.get("reference_axis") or params.get("axis") or "sketch_v_axis").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"sketch_v_axis", "v_axis", "vertical", "sketch_vertical"}:
        return (sketch, ["V_Axis"])
    if raw in {"sketch_h_axis", "h_axis", "horizontal", "sketch_horizontal"}:
        return (sketch, ["H_Axis"])
    doc_axes = {
        "x_axis": "X_Axis",
        "x": "X_Axis",
        "global_x": "X_Axis",
        "y_axis": "Y_Axis",
        "y": "Y_Axis",
        "global_y": "Y_Axis",
        "z_axis": "Z_Axis",
        "z": "Z_Axis",
        "global_z": "Z_Axis",
    }
    if raw in doc_axes and hasattr(doc, doc_axes[raw]):
        return (getattr(doc, doc_axes[raw]), [""])
    raise ValueError("reference_axis must be one of: sketch_v_axis, sketch_h_axis, x_axis, y_axis, z_axis")


def revolved_mode_index(value, *, is_groove):
    mapping = {
        "angle": 0,
        "dimension": 0,
        "up_to_last": 1,
        "through_all": 1,
        "to_last": 1,
        "up_to_first": 2,
        "to_first": 2,
        "up_to_face": 3,
        "to_face": 3,
        "two_angles": 4,
    }
    if value is None:
        return mapping["angle"]
    if isinstance(value, (int, float)):
        return int(value)
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if raw == "through_all" and not is_groove:
        raw = "up_to_last"
    if raw in mapping:
        return mapping[raw]
    raise ValueError("mode must be one of: angle, through_all/up_to_last, up_to_first, up_to_face, two_angles")


def apply_revolved_parameters(doc, sketch, feature, params, *, is_groove):
    if hasattr(feature, "ReferenceAxis"):
        feature.ReferenceAxis = resolve_partdesign_reference_axis(doc, sketch, params)
    if hasattr(feature, "Type"):
        feature.Type = revolved_mode_index(params.get("mode") or params.get("revolution_type") or params.get("groove_type"), is_groove=is_groove)
    if hasattr(feature, "Angle"):
        feature.Angle = float(params.get("angle", 360.0))
    if params.get("angle2") is not None and hasattr(feature, "Angle2"):
        feature.Angle2 = float(params["angle2"])
    if params.get("midplane") is not None and hasattr(feature, "Midplane"):
        feature.Midplane = bool(params["midplane"])
    if params.get("reversed") is not None and hasattr(feature, "Reversed"):
        feature.Reversed = bool(params["reversed"])
    if params.get("up_to_face_object") is not None and hasattr(feature, "UpToFace"):
        face_obj = get_object(doc, params["up_to_face_object"])
        subname = params.get("up_to_face_subname") or ""
        feature.UpToFace = (face_obj, [str(subname)] if subname else [""])
    if params.get("fuse_order") is not None and hasattr(feature, "FuseOrder"):
        feature.FuseOrder = enum_index(params.get("fuse_order"), {"base_first": 0, "feature_first": 1}, "base_first", "fuse_order")


def partdesign_link_sub_value(doc, spec):
    if isinstance(spec, str):
        obj = get_object(doc, spec)
        return obj
    if not isinstance(spec, dict):
        raise ValueError("link target must be an object name or object spec")
    name = spec.get("object_name") or spec.get("name") or spec.get("sketch_name") or spec.get("profile_name")
    if not name:
        raise ValueError("link target spec requires object_name/name/sketch_name")
    obj = get_object(doc, str(name))
    subnames = spec.get("subnames")
    if subnames is None:
        subname = spec.get("subname") or spec.get("sub_element")
        subnames = [subname] if subname else []
    if isinstance(subnames, str):
        subnames = [subnames] if subnames else []
    return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj


def link_target_object(value):
    return value[0] if isinstance(value, (list, tuple)) else value


def object_or_doc_attr(doc, name):
    obj = doc.getObject(str(name))
    if obj is not None:
        return obj
    if hasattr(doc, str(name)):
        return getattr(doc, str(name))
    for candidate in doc.Objects:
        if candidate.Label == name:
            return candidate
    raise ValueError("object not found: " + str(name))


def resolve_partdesign_profile_link(doc, params):
    profile_name = params.get("profile_name") or params.get("profile_sketch") or params.get("sketch_name")
    if profile_name:
        subnames = params.get("profile_subnames")
        if subnames is None:
            subname = params.get("profile_subname")
            subnames = [subname] if subname else []
        if isinstance(subnames, str):
            subnames = [subnames] if subnames else []
        obj = get_object(doc, str(profile_name))
        return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj
    return partdesign_link_sub_value(doc, params.get("profile"))


def subnames_from_args(params, *, default_empty=False):
    for key in ("base_subnames", "subnames", "edge_names", "face_names"):
        value = params.get(key)
        if value is not None:
            if isinstance(value, str):
                return [value] if value else []
            return [str(item) for item in value if item]
    if params.get("edge_indices") is not None:
        return ["Edge" + str(int(index) + 1) for index in params.get("edge_indices") or []]
    if params.get("face_indices") is not None:
        return ["Face" + str(int(index) + 1) for index in params.get("face_indices") or []]
    for key in ("base_subname", "subname", "edge_name", "face_name"):
        value = params.get(key)
        if value:
            return [str(value)]
    return [""] if default_empty else []


def resolve_partdesign_base_link(doc, params, *, body=None, require_subnames=True, default_empty=False):
    base_name = params.get("base_feature_name") or params.get("base_name") or params.get("source_object") or params.get("feature_name")
    base_obj = object_or_doc_attr(doc, base_name) if base_name else None
    if body is None and base_obj is not None:
        body = find_body_for_object(base_obj)
    if body is None:
        body = find_single_partdesign_body(doc)
    if base_obj is None and body is not None:
        base_obj = find_body_solid_tip(body)
    if base_obj is None:
        raise ValueError("base_feature_name/base_name or a Body with a solid Tip is required")
    subnames = subnames_from_args(params, default_empty=default_empty)
    if require_subnames and not subnames:
        raise ValueError("base_subnames/edge_names/face_names, edge_indices/face_indices, or use_all_edges is required")
    return ((base_obj, subnames) if subnames else base_obj), base_obj, body


def resolve_doc_link(doc, params, *, keys, subname_keys=()):
    name = None
    for key in keys:
        if params.get(key):
            name = params.get(key)
            break
    if name is None:
        raise ValueError(keys[0] + " is required")
    obj = object_or_doc_attr(doc, name)
    subname = ""
    for key in subname_keys:
        if params.get(key):
            subname = str(params.get(key))
            break
    return (obj, [subname] if subname else [""])


def resolve_partdesign_section_links(doc, params):
    sections = params.get("sections")
    if sections is None:
        sections = params.get("section_names")
    if not sections:
        raise ValueError("sections or section_names is required")
    return [partdesign_link_sub_value(doc, item) for item in sections]


def resolve_partdesign_optional_section_links(doc, params):
    sections = params.get("sections")
    if sections is None:
        sections = params.get("section_names")
    if not sections:
        return []
    return [partdesign_link_sub_value(doc, item) for item in sections]


def resolve_partdesign_spine_link(doc, params):
    spine_name = params.get("spine_name") or params.get("spine_sketch") or params.get("path_name") or params.get("path_sketch")
    if spine_name:
        subnames = params.get("spine_subnames")
        if subnames is None:
            subname = params.get("spine_subname") or params.get("path_subname")
            subnames = [subname] if subname else []
        if isinstance(subnames, str):
            subnames = [subnames] if subnames else []
        obj = get_object(doc, str(spine_name))
        return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj
    spine = params.get("spine") or params.get("path")
    if spine is None:
        raise ValueError("spine_name, spine_sketch, path_name, or spine is required")
    return partdesign_link_sub_value(doc, spine)


def resolve_partdesign_auxiliary_spine_link(doc, params):
    spine_name = (
        params.get("auxiliary_spine_name")
        or params.get("auxiliary_spine_sketch")
        or params.get("aux_spine_name")
        or params.get("aux_spine_sketch")
        or params.get("auxiliary_path_name")
        or params.get("auxiliary_path_sketch")
    )
    if spine_name:
        subnames = params.get("auxiliary_spine_subnames") or params.get("aux_spine_subnames")
        if subnames is None:
            subname = params.get("auxiliary_spine_subname") or params.get("aux_spine_subname") or params.get("auxiliary_path_subname")
            subnames = [subname] if subname else []
        if isinstance(subnames, str):
            subnames = [subnames] if subnames else []
        obj = get_object(doc, str(spine_name))
        return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj
    spine = params.get("auxiliary_spine") or params.get("auxiliary_path")
    if spine is None:
        return None
    return partdesign_link_sub_value(doc, spine)


def ensure_partdesign_body_member(body, obj):
    previous_tip = getattr(body, "Tip", None)
    if obj not in getattr(body, "Group", []):
        body.addObject(obj)
    if previous_tip is not None and getattr(previous_tip, "Name", None) != getattr(obj, "Name", None):
        body.Tip = previous_tip


def partdesign_pipe_enum(value, mapping, default_key, field_name):
    return enum_index(value, mapping, default_key, field_name)


def pipe_arg(params, primary, *aliases):
    for key in (primary, *aliases):
        if params.get(key) is not None:
            return params.get(key)
    return None


def apply_pipe_parameters(pipe, params, *, has_auxiliary_spine=False, section_count=0):
    if params.get("spine_tangent") is not None and hasattr(pipe, "SpineTangent"):
        pipe.SpineTangent = bool(params["spine_tangent"])
    if pipe_arg(params, "auxiliary_spine_tangent", "aux_spine_tangent") is not None and hasattr(pipe, "AuxiliarySpineTangent"):
        pipe.AuxiliarySpineTangent = bool(pipe_arg(params, "auxiliary_spine_tangent", "aux_spine_tangent"))
    if pipe_arg(params, "auxiliary_curvilinear", "aux_curvilinear") is not None and hasattr(pipe, "AuxiliaryCurvilinear"):
        pipe.AuxiliaryCurvilinear = bool(pipe_arg(params, "auxiliary_curvilinear", "aux_curvilinear"))
    mode_value = pipe_arg(params, "mode", "orientation_mode")
    if has_auxiliary_spine and mode_value is None:
        mode_value = "auxiliary"
    mode_index = None
    if mode_value is not None:
        mode_index = partdesign_pipe_enum(
            mode_value,
            {"standard": 0, "fixed": 1, "frenet": 2, "auxiliary": 3, "binormal": 4},
            "standard",
            "mode/orientation_mode",
        )
    if has_auxiliary_spine and mode_index != 3:
        raise ValueError("auxiliary_spine requires mode/orientation_mode='auxiliary'")
    if mode_index == 3 and not has_auxiliary_spine:
        raise ValueError("mode/orientation_mode='auxiliary' requires auxiliary_spine_name or auxiliary_spine")
    if mode_index is not None and hasattr(pipe, "Mode"):
        pipe.Mode = mode_index
    if params.get("transition") is not None and hasattr(pipe, "Transition"):
        pipe.Transition = partdesign_pipe_enum(
            params.get("transition"),
            {"transformed": 0, "right_corner": 1, "right": 1, "round_corner": 2, "round": 2},
            "transformed",
            "transition",
        )
    transformation_value = pipe_arg(params, "transformation", "scaling_mode")
    if section_count and transformation_value is None:
        transformation_value = "multisection"
    transformation_index = None
    if transformation_value is not None:
        transformation_index = partdesign_pipe_enum(
            transformation_value,
            {"constant": 0, "multisection": 1, "multi_section": 1, "linear": 2, "s_shape": 3, "interpolation": 4},
            "constant",
            "transformation/scaling_mode",
        )
    if section_count and transformation_index != 1:
        raise ValueError("sections require transformation/scaling_mode='multisection'")
    if transformation_index is not None and hasattr(pipe, "Transformation"):
        pipe.Transformation = transformation_index
    if params.get("binormal") is not None and hasattr(pipe, "Binormal"):
        pipe.Binormal = vector(params["binormal"])


def find_partdesign_body(doc, name):
    obj = doc.getObject(name) if name else None
    if obj is None and name:
        for candidate in doc.Objects:
            if candidate.Label == name:
                obj = candidate
                break
    if obj is not None and getattr(obj, "TypeId", "") != "PartDesign::Body":
        raise ValueError("object is not a PartDesign Body: " + name)
    return obj


def find_body_for_object(obj):
    for parent in getattr(obj, "InList", []) or []:
        if getattr(parent, "TypeId", "") == "PartDesign::Body":
            return parent
    return None


def find_single_partdesign_body(doc):
    bodies = [obj for obj in doc.Objects if getattr(obj, "TypeId", "") == "PartDesign::Body"]
    if len(bodies) == 1:
        return bodies[0]
    if len(bodies) > 1:
        raise ValueError("body_name is required when the document has multiple PartDesign Bodies")
    return None


def find_body_tip_fallback(body, deleted_names):
    for candidate in reversed(list(getattr(body, "Group", []) or [])):
        if getattr(candidate, "Name", None) in deleted_names:
            continue
        if object_solid_count(candidate) > 0:
            return candidate
    return None


def restore_body_tips_before_delete(doc, objects):
    deleted_names = {obj.Name for obj in objects}
    reports = []
    for body in [obj for obj in doc.Objects if getattr(obj, "TypeId", "") == "PartDesign::Body"]:
        tip = getattr(body, "Tip", None)
        if tip is None or getattr(tip, "Name", None) not in deleted_names:
            continue
        fallback = find_body_tip_fallback(body, deleted_names)
        report = {"body": body.Name, "before_tip": getattr(tip, "Name", None), "after_tip": getattr(fallback, "Name", None)}
        if fallback is not None:
            body.Tip = fallback
            report["restored"] = True
        else:
            report["restored"] = False
        reports.append(report)
    return reports


def get_or_create_partdesign_body(doc, params, *, default_if_requested=True):
    requested = params.get("body_name")
    requested_partdesign = attachment_requested(params)
    if not requested and not requested_partdesign and not default_if_requested:
        return None, False
    body_name = str(requested or "Body")
    body = find_partdesign_body(doc, body_name)
    created = False
    create_if_missing = bool(params.get("create_body_if_missing", True))
    if body is None:
        if not create_if_missing:
            raise ValueError("PartDesign Body not found: " + body_name)
        body = doc.addObject("PartDesign::Body", body_name)
        created = True
    return body, created


def attach_sketch_to_partdesign_body(doc, sketch, params, *, body=None):
    requested = attachment_requested(params)
    target_requested = attachment_target_requested(params)
    if body is None:
        body = find_body_for_object(sketch)
    support_name = attachment_support_name(params)
    if body is None and support_name:
        support = get_object(doc, support_name)
        body = find_body_for_object(support)
    if body is None:
        if not requested:
            return {"attached": False, "body_created": False}
        body, created = get_or_create_partdesign_body(doc, params)
    else:
        created = False
    previous_tip = getattr(body, "Tip", None)
    if sketch not in getattr(body, "Group", []):
        body.addObject(sketch)
    if previous_tip is not None and getattr(previous_tip, "Name", None) != getattr(sketch, "Name", None):
        body.Tip = previous_tip
    if not target_requested and getattr(sketch, "AttachmentSupport", None):
        existing = attachment_summary(sketch)
        result = {
            "attached": True,
            "body_created": created,
            "body_name": body.Name,
            "support_type": "existing",
            "map_mode": existing.get("map_mode", ""),
        }
        if existing.get("support"):
            first = existing["support"][0]
            result["support_object"] = first.get("object")
            result["support_label"] = first.get("label")
            result["support_type_id"] = first.get("type_id")
            result["support_subname"] = (first.get("subnames") or [""])[0] if first.get("subnames") else ""
        if existing.get("offset_base") is not None:
            result["offset_base"] = existing["offset_base"]
        return result
    support, subname, support_info = resolve_partdesign_attachment_support(doc, body, params)
    sketch.AttachmentSupport = [(support, subname)]
    sketch.MapMode = str(params.get("attachment_map_mode") or params.get("map_mode") or "FlatFace")
    offset_base = apply_attachment_offset(sketch, params)
    result = {
        "attached": True,
        "body_created": created,
        "body_name": body.Name,
        "map_mode": str(getattr(sketch, "MapMode", "")),
    }
    result.update(support_info)
    if offset_base is not None:
        result["offset_base"] = offset_base
    return result


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


def wire_face_validation(shape):
    import Part

    wires = list(getattr(shape, "Wires", []) or [])
    reports = []
    face_count = 0
    for index, wire in enumerate(wires):
        report = {
            "index": index,
            "closed": bool(wire.isClosed()),
            "edge_count": len(getattr(wire, "Edges", []) or []),
        }
        if report["closed"]:
            try:
                face = Part.Face(wire)
                report["face_valid"] = bool(face.isValid())
                report["area"] = float(getattr(face, "Area", 0.0))
                if report["face_valid"]:
                    face_count += 1
            except Exception as exc:
                report["face_valid"] = False
                report["face_error"] = str(exc)
        else:
            report["face_valid"] = False
        reports.append(report)
    return {
        "wire_count": len(wires),
        "closed_wire_count": sum(1 for report in reports if report["closed"]),
        "face_count": face_count,
        "faces_valid": bool(wires) and face_count == len(wires),
        "wires": reports,
    }


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
            resolved = resolve_property_value(doc, value)
            setattr(obj, key, resolved)
            changed[key] = property_value_summary(resolved)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "changed": changed, "object": object_summary(obj), "document": document_summary(doc)}


def action_object_rename_label(params):
    doc = get_doc(params)
    obj = get_object_for_label_update(doc, params.get("object_name") or "")
    label = str(params.get("label") or "").strip()
    if not label:
        raise ValueError("label is required")
    if bool(params.get("require_unique", True)):
        ensure_unique_label(doc, obj, label)
    before = {"name": obj.Name, "label": obj.Label}
    doc.openTransaction("MCP worker rename object label")
    try:
        obj.Label = label
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "before": before,
        "after": {"name": obj.Name, "label": obj.Label},
        "object": object_summary(obj),
        "document": document_summary(doc),
    }


def action_object_delete(params):
    doc = get_doc(params)
    names = params.get("object_names") or ([params["object_name"]] if params.get("object_name") else [])
    if not names:
        raise ValueError("object_name or object_names is required")
    doc.openTransaction("MCP worker delete objects")
    try:
        objects = [get_object(doc, name) for name in names]
        deleted = [obj.Name for obj in objects]
        tip_restorations = restore_body_tips_before_delete(doc, objects)
        for obj in objects:
            doc.removeObject(obj.Name)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "deleted": deleted, "tip_restorations": tip_restorations, "document": document_summary(doc)}


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


def action_partdesign_body_create(params):
    doc = get_doc(params)
    doc.openTransaction("MCP worker create PartDesign body")
    try:
        body, created = get_or_create_partdesign_body(doc, params)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "created": created,
        "body": object_summary(body),
        "document": document_summary(doc),
    }


def action_partdesign_datum_plane_create(params):
    doc = get_doc(params)
    doc.openTransaction("MCP worker create PartDesign datum plane")
    try:
        body, body_created = get_or_create_partdesign_body(doc, params)
        previous_tip = getattr(body, "Tip", None)
        datum = doc.addObject("PartDesign::Plane", params.get("datum_plane_name") or params.get("plane_name") or params.get("result_name") or "DatumPlane")
        body.addObject(datum)
        support_params = dict(params)
        support_params.pop("datum_plane_name", None)
        support, subname, attachment = resolve_partdesign_attachment_support(doc, body, support_params)
        datum.AttachmentSupport = [(support, subname)]
        datum.MapMode = str(params.get("attachment_map_mode") or params.get("map_mode") or "FlatFace")
        offset_base = apply_attachment_offset(datum, params)
        if previous_tip is not None and getattr(previous_tip, "Name", None) != getattr(datum, "Name", None):
            body.Tip = previous_tip
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_valid", True)) and "Invalid" in list(getattr(datum, "State", []) or []):
        raise ValueError("PartDesign datum plane is invalid: " + str(getattr(datum, "State", [])))
    saved = save_doc(doc, params)
    attachment.update(
        {
            "attached": True,
            "body_created": body_created,
            "body_name": body.Name,
            "map_mode": str(getattr(datum, "MapMode", "")),
        }
    )
    if offset_base is not None:
        attachment["offset_base"] = offset_base
    return {
        "saved_path": saved,
        "created": True,
        "body": object_summary(body),
        "datum_plane": object_summary(datum),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_pad(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(sketch)
    doc.openTransaction("MCP worker create PartDesign pad")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, params)
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params, body=body)
        pad = doc.addObject("PartDesign::Pad", params.get("pad_name") or params.get("result_name") or "Pad")
        body.addObject(pad)
        pad.Profile = sketch
        if hasattr(pad, "Length"):
            pad.Length = float(params.get("length", params.get("length_fwd", 10.0)))
        if params.get("length2") is not None and hasattr(pad, "Length2"):
            pad.Length2 = float(params["length2"])
        if params.get("midplane") is not None and hasattr(pad, "Midplane"):
            pad.Midplane = bool(params["midplane"])
        if params.get("reversed") is not None and hasattr(pad, "Reversed"):
            pad.Reversed = bool(params["reversed"])
        body.Tip = pad
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(pad, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Pad did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "pad": object_summary(pad),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_pocket(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(sketch)
    doc.openTransaction("MCP worker create PartDesign pocket")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, params)
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError("PartDesign Pocket requires an existing solid feature in the Body (create a Pad first)")
        body.Tip = solid_tip
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params, body=body)
        pocket = doc.addObject("PartDesign::Pocket", params.get("pocket_name") or params.get("result_name") or "Pocket")
        body.addObject(pocket)
        pocket.Profile = sketch
        if hasattr(pocket, "Length"):
            pocket.Length = float(params.get("length", params.get("length_fwd", 10.0)))
        if params.get("length2") is not None and hasattr(pocket, "Length2"):
            pocket.Length2 = float(params["length2"])
        if params.get("midplane") is not None and hasattr(pocket, "Midplane"):
            pocket.Midplane = bool(params["midplane"])
        if params.get("reversed") is not None and hasattr(pocket, "Reversed"):
            pocket.Reversed = bool(params["reversed"])
        body.Tip = pocket
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(pocket, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Pocket did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "pocket": object_summary(pocket),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_hole(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(sketch)
    doc.openTransaction("MCP worker create PartDesign hole")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, params)
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError("PartDesign Hole requires an existing solid feature in the Body (create a Pad first)")
        body.Tip = solid_tip
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params, body=body)
        hole = doc.addObject("PartDesign::Hole", params.get("hole_name") or params.get("result_name") or "Hole")
        body.addObject(hole)
        hole.Profile = sketch
        apply_hole_parameters(hole, params)
        body.Tip = hole
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(hole, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Hole did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "hole": object_summary(hole),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_revolution(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(sketch)
    doc.openTransaction("MCP worker create PartDesign revolution")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, params)
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params, body=body)
        revolution = doc.addObject("PartDesign::Revolution", params.get("revolution_name") or params.get("result_name") or "Revolution")
        body.addObject(revolution)
        revolution.Profile = sketch
        apply_revolved_parameters(doc, sketch, revolution, params, is_groove=False)
        body.Tip = revolution
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(revolution, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Revolution did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "revolution": object_summary(revolution),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_groove(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(sketch)
    doc.openTransaction("MCP worker create PartDesign groove")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, params)
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError("PartDesign Groove requires an existing solid feature in the Body (create a Pad first)")
        body.Tip = solid_tip
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params, body=body)
        groove = doc.addObject("PartDesign::Groove", params.get("groove_name") or params.get("result_name") or "Groove")
        body.addObject(groove)
        groove.Profile = sketch
        apply_revolved_parameters(doc, sketch, groove, params, is_groove=True)
        body.Tip = groove
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(groove, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Groove did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "groove": object_summary(groove),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_loft(doc, params, *, feature_type, default_name, transaction_name, require_base_solid=False):
    profile_link = resolve_partdesign_profile_link(doc, params)
    section_links = resolve_partdesign_section_links(doc, params)
    profile_obj = link_target_object(profile_link)
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(profile_obj)
    doc.openTransaction(transaction_name)
    try:
        if body is None:
            if require_base_solid:
                raise ValueError("PartDesign Subtractive Loft requires an existing Body solid")
            body, _ = get_or_create_partdesign_body(doc, params)
        ensure_partdesign_body_member(body, profile_obj)
        for section_link in section_links:
            ensure_partdesign_body_member(body, link_target_object(section_link))
        if require_base_solid:
            solid_tip = find_body_solid_tip(body)
            if solid_tip is None:
                raise ValueError("PartDesign Subtractive Loft requires an existing Body solid")
            body.Tip = solid_tip
        loft = doc.addObject(feature_type, params.get("loft_name") or params.get("result_name") or default_name)
        body.addObject(loft)
        loft.Profile = profile_link
        loft.Sections = section_links
        if params.get("ruled") is not None and hasattr(loft, "Ruled"):
            loft.Ruled = bool(params["ruled"])
        if params.get("closed") is not None and hasattr(loft, "Closed"):
            loft.Closed = bool(params["closed"])
        body.Tip = loft
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(loft, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "profile": object_summary(profile_obj),
        "sections": [object_summary(link_target_object(item)) for item in section_links],
        "loft": object_summary(loft),
        "document": document_summary(doc),
    }


def action_partdesign_additive_loft(params):
    doc = get_doc(params)
    return action_partdesign_loft(
        doc,
        params,
        feature_type="PartDesign::AdditiveLoft",
        default_name="AdditiveLoft",
        transaction_name="MCP worker create PartDesign additive loft",
    )


def action_partdesign_subtractive_loft(params):
    doc = get_doc(params)
    return action_partdesign_loft(
        doc,
        params,
        feature_type="PartDesign::SubtractiveLoft",
        default_name="SubtractiveLoft",
        transaction_name="MCP worker create PartDesign subtractive loft",
        require_base_solid=True,
    )


def action_partdesign_pipe(doc, params, *, feature_type, default_name, transaction_name, require_base_solid=False):
    profile_link = resolve_partdesign_profile_link(doc, params)
    spine_link = resolve_partdesign_spine_link(doc, params)
    auxiliary_spine_link = resolve_partdesign_auxiliary_spine_link(doc, params)
    section_links = resolve_partdesign_optional_section_links(doc, params)
    profile_obj = link_target_object(profile_link)
    spine_obj = link_target_object(spine_link)
    auxiliary_spine_obj = link_target_object(auxiliary_spine_link) if auxiliary_spine_link is not None else None
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else find_body_for_object(profile_obj)
    doc.openTransaction(transaction_name)
    try:
        if body is None:
            if require_base_solid:
                raise ValueError(f"{default_name} requires an existing Body solid")
            body, _ = get_or_create_partdesign_body(doc, params)
        ensure_partdesign_body_member(body, profile_obj)
        ensure_partdesign_body_member(body, spine_obj)
        if auxiliary_spine_obj is not None:
            ensure_partdesign_body_member(body, auxiliary_spine_obj)
        for section_link in section_links:
            ensure_partdesign_body_member(body, link_target_object(section_link))
        if require_base_solid:
            solid_tip = find_body_solid_tip(body)
            if solid_tip is None:
                raise ValueError(f"{default_name} requires an existing Body solid")
            body.Tip = solid_tip
        pipe = doc.addObject(feature_type, params.get("pipe_name") or params.get("result_name") or default_name)
        body.addObject(pipe)
        pipe.Profile = profile_link
        pipe.Spine = spine_link
        if auxiliary_spine_link is not None:
            pipe.AuxiliarySpine = auxiliary_spine_link
        if section_links:
            pipe.Sections = section_links
        apply_pipe_parameters(pipe, params, has_auxiliary_spine=auxiliary_spine_link is not None, section_count=len(section_links))
        body.Tip = pipe
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(pipe, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "profile": object_summary(profile_obj),
        "spine": object_summary(spine_obj),
        "auxiliary_spine": object_summary(auxiliary_spine_obj) if auxiliary_spine_obj is not None else None,
        "sections": [object_summary(link_target_object(item)) for item in section_links],
        "pipe": object_summary(pipe),
        "document": document_summary(doc),
    }


def action_partdesign_additive_pipe(params):
    doc = get_doc(params)
    return action_partdesign_pipe(
        doc,
        params,
        feature_type="PartDesign::AdditivePipe",
        default_name="AdditivePipe",
        transaction_name="MCP worker create PartDesign additive pipe",
    )


def action_partdesign_subtractive_pipe(params):
    doc = get_doc(params)
    return action_partdesign_pipe(
        doc,
        params,
        feature_type="PartDesign::SubtractivePipe",
        default_name="SubtractivePipe",
        transaction_name="MCP worker create PartDesign subtractive pipe",
        require_base_solid=True,
    )


def chamfer_type_index(value):
    return enum_index(
        value,
        {
            "equal_distance": 0,
            "equal": 0,
            "distance": 0,
            "two_distances": 1,
            "two_distance": 1,
            "distance_distance": 1,
            "distance_and_angle": 2,
            "distance_angle": 2,
            "angle": 2,
        },
        "equal_distance",
        "chamfer_type",
    )


def thickness_mode_index(value):
    return enum_index(value, {"skin": 0, "pipe": 1, "recto_verso": 2, "rectoverso": 2}, "skin", "mode")


def thickness_join_index(value):
    return enum_index(value, {"arc": 0, "intersection": 1}, "arc", "join")


def action_partdesign_dressup(doc, params, *, feature_type, default_name, transaction_name, apply_parameters, use_all_edges=False, require_subnames=True):
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else None
    base_link, base_obj, body = resolve_partdesign_base_link(
        doc,
        params,
        body=body,
        require_subnames=require_subnames and not use_all_edges,
        default_empty=use_all_edges,
    )
    if body is None:
        raise ValueError("PartDesign Body not found for base feature")
    doc.openTransaction(transaction_name)
    try:
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError(f"{default_name} requires an existing Body solid")
        body.Tip = solid_tip
        feature = doc.addObject(feature_type, params.get("dressup_name") or params.get("result_name") or params.get(default_name.lower() + "_name") or default_name)
        feature.Base = base_link
        apply_parameters(feature, params)
        body.addObject(feature)
        body.Tip = feature
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(feature, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "base": object_summary(base_obj),
        "dressup": object_summary(feature),
        "document": document_summary(doc),
    }


def action_partdesign_fillet(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "Radius"):
            feature.Radius = float(values.get("radius", 1.0))
        if hasattr(feature, "UseAllEdges"):
            feature.UseAllEdges = bool(values.get("use_all_edges", False))
        if values.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(values["support_transform"])

    return action_partdesign_dressup(
        doc,
        params,
        feature_type="PartDesign::Fillet",
        default_name="Fillet",
        transaction_name="MCP worker create PartDesign fillet",
        apply_parameters=apply,
        use_all_edges=bool(params.get("use_all_edges", False)),
    )


def action_partdesign_chamfer(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "ChamferType"):
            feature.ChamferType = chamfer_type_index(values.get("chamfer_type"))
        if hasattr(feature, "Size"):
            feature.Size = float(values.get("size", values.get("distance", 1.0)))
        if values.get("size2") is not None and hasattr(feature, "Size2"):
            feature.Size2 = float(values["size2"])
        if values.get("angle") is not None and hasattr(feature, "Angle"):
            feature.Angle = float(values["angle"])
        if values.get("flip_direction") is not None and hasattr(feature, "FlipDirection"):
            feature.FlipDirection = bool(values["flip_direction"])
        if hasattr(feature, "UseAllEdges"):
            feature.UseAllEdges = bool(values.get("use_all_edges", False))
        if values.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(values["support_transform"])

    return action_partdesign_dressup(
        doc,
        params,
        feature_type="PartDesign::Chamfer",
        default_name="Chamfer",
        transaction_name="MCP worker create PartDesign chamfer",
        apply_parameters=apply,
        use_all_edges=bool(params.get("use_all_edges", False)),
    )


def action_partdesign_thickness(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "Value"):
            feature.Value = float(values.get("value", values.get("thickness", 1.0)))
        if hasattr(feature, "Mode"):
            feature.Mode = thickness_mode_index(values.get("mode"))
        if hasattr(feature, "Join"):
            feature.Join = thickness_join_index(values.get("join"))
        if values.get("reversed") is not None and hasattr(feature, "Reversed"):
            feature.Reversed = bool(values["reversed"])
        if values.get("intersection") is not None and hasattr(feature, "Intersection"):
            feature.Intersection = bool(values["intersection"])
        if values.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(values["support_transform"])

    return action_partdesign_dressup(
        doc,
        params,
        feature_type="PartDesign::Thickness",
        default_name="Thickness",
        transaction_name="MCP worker create PartDesign thickness",
        apply_parameters=apply,
    )


def action_partdesign_draft(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "NeutralPlane"):
            feature.NeutralPlane = resolve_doc_link(
                doc,
                values,
                keys=("neutral_plane_name", "neutral_plane_object", "neutral_plane"),
                subname_keys=("neutral_plane_subname",),
            )
        if hasattr(feature, "PullDirection"):
            feature.PullDirection = resolve_doc_link(
                doc,
                values,
                keys=("pull_direction_name", "pull_direction_object", "pull_direction"),
                subname_keys=("pull_direction_subname",),
            )
        if hasattr(feature, "Angle"):
            feature.Angle = float(values.get("angle", 5.0))
        if values.get("reversed") is not None and hasattr(feature, "Reversed"):
            feature.Reversed = bool(values["reversed"])
        if values.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(values["support_transform"])

    return action_partdesign_dressup(
        doc,
        params,
        feature_type="PartDesign::Draft",
        default_name="Draft",
        transaction_name="MCP worker create PartDesign draft",
        apply_parameters=apply,
    )


def first_present(params, *keys):
    for key in keys:
        value = params.get(key)
        if value is not None and value != "":
            return value
    return None


def list_arg(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(item) for item in value if item]


def transform_original_names(params):
    for key in ("original_names", "feature_names", "features", "originals"):
        values = list_arg(params.get(key))
        if values:
            return values
    name = first_present(params, "original_feature_name", "feature_name", "base_feature_name", "source_object")
    return [str(name)] if name else []


def canonical_reference_name(name, default_name):
    raw_value = name if name is not None and name != "" else default_name
    raw = str(raw_value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "x": "X_Axis",
        "x_axis": "X_Axis",
        "global_x": "X_Axis",
        "y": "Y_Axis",
        "y_axis": "Y_Axis",
        "global_y": "Y_Axis",
        "z": "Z_Axis",
        "z_axis": "Z_Axis",
        "global_z": "Z_Axis",
        "xy": "XY_Plane",
        "xy_plane": "XY_Plane",
        "xz": "XZ_Plane",
        "xz_plane": "XZ_Plane",
        "yz": "YZ_Plane",
        "yz_plane": "YZ_Plane",
    }
    return aliases.get(raw, str(raw_value))


def resolve_transform_link(doc, params, *, keys, subname_keys=(), default_name=None, default_subname=""):
    name = first_present(params, *keys)
    if name is None:
        if default_name is None:
            return None
        name = default_name
    name = canonical_reference_name(name, default_name or name)
    obj = object_or_doc_attr(doc, name)
    subname = first_present(params, *subname_keys) or default_subname
    return (obj, [str(subname)] if subname else [""])


def pattern_mode_index(value):
    return enum_index(value, {"extent": 0, "overall_length": 0, "length": 0, "spacing": 1, "offset": 1}, "extent", "mode")


def action_partdesign_transform(doc, params, *, feature_type, default_name, transaction_name, apply_parameters, name_keys):
    whole_shape = bool(params.get("whole_shape", False) or str(params.get("transform_mode", "")).strip().lower().replace("-", "_").replace(" ", "_") in {"whole_shape", "whole"})
    body = find_partdesign_body(doc, params.get("body_name")) if params.get("body_name") else None
    originals = []
    if not whole_shape:
        original_names = transform_original_names(params)
        originals = [object_or_doc_attr(doc, name) for name in original_names]
        if body is None and originals:
            body = find_body_for_object(originals[0])
    if body is None:
        body = find_single_partdesign_body(doc)
    if body is None:
        raise ValueError("PartDesign Body not found")
    if not whole_shape and not originals:
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError(f"{default_name} requires original_names or an existing Body solid Tip")
        originals = [solid_tip]
    doc.openTransaction(transaction_name)
    try:
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError(f"{default_name} requires an existing Body solid")
        body.Tip = solid_tip
        transform = doc.addObject(feature_type, first_present(params, *name_keys, "result_name") or default_name)
        body.addObject(transform)
        if whole_shape:
            if hasattr(transform, "TransformMode"):
                transform.TransformMode = "Whole shape"
            if hasattr(transform, "Originals"):
                transform.Originals = []
        else:
            if hasattr(transform, "TransformMode"):
                transform.TransformMode = "Features"
            transform.Originals = originals
        apply_parameters(transform, params)
        body.Tip = transform
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(params.get("require_solid", True)):
        shape = getattr(transform, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "originals": [object_summary(item) for item in originals],
        "transform": object_summary(transform),
        "document": document_summary(doc),
    }


def action_partdesign_linear_pattern(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "Direction"):
            feature.Direction = resolve_transform_link(
                doc,
                values,
                keys=("direction_name", "direction_object", "direction_axis"),
                subname_keys=("direction_subname",),
                default_name="X_Axis",
            )
        if hasattr(feature, "Reversed") and values.get("reversed") is not None:
            feature.Reversed = bool(values["reversed"])
        if hasattr(feature, "Mode"):
            feature.Mode = pattern_mode_index(values.get("mode"))
        if hasattr(feature, "Length"):
            feature.Length = float(values.get("length", 10.0))
        if values.get("offset") is not None and hasattr(feature, "Offset"):
            feature.Offset = float(values["offset"])
        if hasattr(feature, "Occurrences"):
            feature.Occurrences = int(values.get("occurrences", 2))
        occurrences2 = int(values.get("occurrences2", 1))
        second_direction = resolve_transform_link(
            doc,
            values,
            keys=("direction2_name", "direction2_object", "direction2_axis", "second_direction_name", "second_direction_object", "second_direction_axis"),
            subname_keys=("direction2_subname", "second_direction_subname"),
            default_name="Y_Axis" if occurrences2 > 1 else None,
        )
        if second_direction is not None and hasattr(feature, "Direction2"):
            feature.Direction2 = second_direction
        if hasattr(feature, "Reversed2") and values.get("reversed2") is not None:
            feature.Reversed2 = bool(values["reversed2"])
        if hasattr(feature, "Mode2"):
            feature.Mode2 = pattern_mode_index(values.get("mode2"))
        if hasattr(feature, "Length2"):
            feature.Length2 = float(values.get("length2", 10.0))
        if values.get("offset2") is not None and hasattr(feature, "Offset2"):
            feature.Offset2 = float(values["offset2"])
        if hasattr(feature, "Occurrences2"):
            feature.Occurrences2 = occurrences2

    return action_partdesign_transform(
        doc,
        params,
        feature_type="PartDesign::LinearPattern",
        default_name="LinearPattern",
        transaction_name="MCP worker create PartDesign linear pattern",
        apply_parameters=apply,
        name_keys=("linear_pattern_name", "pattern_name", "transform_name"),
    )


def action_partdesign_polar_pattern(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "Axis"):
            feature.Axis = resolve_transform_link(
                doc,
                values,
                keys=("axis_name", "axis_object", "axis"),
                subname_keys=("axis_subname",),
                default_name="Z_Axis",
            )
        if hasattr(feature, "Reversed") and values.get("reversed") is not None:
            feature.Reversed = bool(values["reversed"])
        if hasattr(feature, "Mode"):
            feature.Mode = pattern_mode_index(values.get("mode"))
        if hasattr(feature, "Angle"):
            feature.Angle = float(values.get("angle", 360.0))
        if values.get("offset") is not None and hasattr(feature, "Offset"):
            feature.Offset = float(values["offset"])
        if hasattr(feature, "Occurrences"):
            feature.Occurrences = int(values.get("occurrences", 3))

    return action_partdesign_transform(
        doc,
        params,
        feature_type="PartDesign::PolarPattern",
        default_name="PolarPattern",
        transaction_name="MCP worker create PartDesign polar pattern",
        apply_parameters=apply,
        name_keys=("polar_pattern_name", "pattern_name", "transform_name"),
    )


def action_partdesign_mirrored(params):
    doc = get_doc(params)

    def apply(feature, values):
        if hasattr(feature, "MirrorPlane"):
            feature.MirrorPlane = resolve_transform_link(
                doc,
                values,
                keys=("mirror_plane_name", "mirror_plane_object", "mirror_plane"),
                subname_keys=("mirror_plane_subname",),
                default_name="XY_Plane",
            )

    return action_partdesign_transform(
        doc,
        params,
        feature_type="PartDesign::Mirrored",
        default_name="Mirrored",
        transaction_name="MCP worker create PartDesign mirrored",
        apply_parameters=apply,
        name_keys=("mirrored_name", "mirror_name", "transform_name"),
    )


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
    if kind in {"line", "line_segment", "line_start_end"}:
        return [Part.LineSegment(vector(item["start"]), vector(item["end"]))]
    if kind in {"line_angle_length", "line_by_angle"}:
        start = vector(item["start"])
        length = float(item["length"])
        angle = angle_radians(item["angle"])
        end = App.Vector(start.x + length * math.cos(angle), start.y + length * math.sin(angle), start.z)
        return [Part.LineSegment(start, end)]
    if kind == "point":
        return [Part.Point(vector(item.get("point") or item.get("position")))]
    if kind in {"circle", "circle_center_radius", "circle_3_point", "circle_by_3_points"}:
        if kind in {"circle_3_point", "circle_by_3_points"} or item.get("points"):
            points = item.get("points") or [item["point1"], item["point2"], item["point3"]]
            return [Part.Circle(vector(points[0]), vector(points[1]), vector(points[2]))]
        return [Part.Circle(vector(item.get("center"), [0, 0, 0]), vector(item.get("normal"), [0, 0, 1]), float(item["radius"]))]
    if kind in {"arc", "arc_of_circle", "arc_center_angles"}:
        return [make_center_angle_arc(item)]
    if kind in {"arc_3_point", "arc_by_3_points", "arc_start_mid_end"}:
        points = item.get("points") or [item["start"], item["mid"], item["end"]]
        return [Part.ArcOfCircle(vector(points[0]), vector(points[1]), vector(points[2]))]
    if kind == "arc_start_end_radius":
        return [make_start_end_radius_arc(item)]
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


CURVED_PROFILE_SEGMENT_TYPES = {
    "arc",
    "circle",
    "ellipse",
    "ellipse_arc",
    "conic_arc",
    "bspline",
}


def normalized_profile_segment_type(kind):
    value = str(kind or "").lower()
    if value in {"line", "line_segment", "line_start_end", "line_angle_length", "line_by_angle"}:
        return "line"
    if value == "polyline":
        return "polyline"
    if value in {"bspline", "b_spline"}:
        return "bspline"
    if value in {"arc", "arc_of_circle", "arc_center_angles", "arc_3_point", "arc_by_3_points", "arc_start_mid_end", "arc_start_end_radius"}:
        return "arc"
    if value in {"circle", "circle_center_radius", "circle_3_point", "circle_by_3_points"}:
        return "circle"
    if value == "ellipse":
        return "ellipse"
    if value in {"arc_of_ellipse", "ellipse_arc"}:
        return "ellipse_arc"
    if value in {"arc_of_hyperbola", "hyperbola_arc", "arc_of_parabola", "parabola_arc"}:
        return "conic_arc"
    if value == "point":
        return "point"
    return value


def normalized_profile_segment_set(value):
    if value is None:
        return set()
    if isinstance(value, str):
        return {normalized_profile_segment_type(value)}
    return {normalized_profile_segment_type(item) for item in value}


def loop_contract_value(loop, params, key, default=None):
    if key in loop:
        return loop.get(key)
    return params.get(key, default)


def enforce_profile_loop_curve_contract(loop, params, segments, name):
    segment_types = [normalized_profile_segment_type(segment.get("type")) for segment in segments]
    curve_types = [segment_type for segment_type in segment_types if segment_type in CURVED_PROFILE_SEGMENT_TYPES]
    required_types = normalized_profile_segment_set(params.get("required_segment_types")) | normalized_profile_segment_set(loop.get("required_segment_types"))
    required_types |= normalized_profile_segment_set(params.get("required_curve_types")) | normalized_profile_segment_set(loop.get("required_curve_types"))
    allowed_types = normalized_profile_segment_set(loop_contract_value(loop, params, "allowed_segment_types"))
    minimum_curve_segments = int(loop_contract_value(loop, params, "minimum_curve_segments", 0) or 0)
    forbid_polyline_fallback = bool(loop_contract_value(loop, params, "forbid_polyline_fallback", False))
    forbid_all_line_loops = bool(loop_contract_value(loop, params, "forbid_all_line_loops", False))

    if allowed_types:
        disallowed = sorted({segment_type for segment_type in segment_types if segment_type not in allowed_types})
        if disallowed:
            raise ValueError("profile loop contains disallowed segment types: " + name + " " + str(disallowed))
    missing = sorted(required_types - set(segment_types))
    if missing:
        raise ValueError("profile loop missing required segment types: " + name + " " + str(missing))
    if forbid_polyline_fallback and "polyline" in segment_types:
        raise ValueError("profile loop polyline fallback is forbidden: " + name)
    if forbid_all_line_loops and not curve_types:
        raise ValueError("profile loop all-line fallback is forbidden: " + name)
    if len(curve_types) < minimum_curve_segments:
        raise ValueError(
            "profile loop requires at least "
            + str(minimum_curve_segments)
            + " curve segments: "
            + name
            + " found "
            + str(len(curve_types))
        )
    return {
        "segment_types": segment_types,
        "curve_segment_types": curve_types,
        "curve_segment_count": len(curve_types),
        "required_segment_types": sorted(required_types),
        "minimum_curve_segments": minimum_curve_segments,
        "forbid_polyline_fallback": forbid_polyline_fallback,
        "forbid_all_line_loops": forbid_all_line_loops,
    }


def sketch_geometry_has_endpoints(geom):
    return hasattr(geom, "StartPoint") and hasattr(geom, "EndPoint")


def vector_distance(first, second):
    return float((first - second).Length)


def geometry_endpoint(geom, position):
    if position == 1:
        return geom.StartPoint
    if position == 2:
        return geom.EndPoint
    raise ValueError("unsupported endpoint position: " + str(position))


def geometry_is_self_closed(geom):
    try:
        shape = geom.toShape()
        return bool(shape.isClosed())
    except Exception:
        return False


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
    geometry_reports = []
    chain_indices = []
    previous_index = None
    for item in items:
        for geom in make_sketch_geometries(item):
            index = sketch.addGeometry(geom, bool(item.get("construction", False)))
            added.append(index)
            report = sketch_arc_geometry_report(sketch.Geometry[index], index, item.get("type"))
            if report is not None:
                geometry_reports.append(report)
            if sketch_geometry_has_endpoints(geom):
                if connect_sequence and previous_index is not None:
                    constraint_indices.append(sketch.addConstraint(Sketcher.Constraint("Coincident", previous_index, 2, index, 1)))
                previous_index = index
                chain_indices.append(index)
    if close_sequence and len(chain_indices) > 1:
        constraint_indices.append(sketch.addConstraint(Sketcher.Constraint("Coincident", chain_indices[-1], 2, chain_indices[0], 1)))
    return added, constraint_indices, geometry_reports


def endpoint_key(point, precision):
    return (round(float(point.x), precision), round(float(point.y), precision), round(float(point.z), precision))


def sketch_endpoint_records(sketch, precision=6, include_construction=False):
    records = []
    for index, geom in enumerate(sketch.Geometry):
        try:
            construction = bool(sketch.getConstruction(index))
        except Exception:
            construction = False
        if construction and not include_construction:
            continue
        if sketch_geometry_has_endpoints(geom):
            for position in (1, 2):
                point = geometry_endpoint(geom, position)
                records.append(
                    {
                        "geometry_index": index,
                        "point_pos": position,
                        "point": point_list(point),
                        "key": endpoint_key(point, precision),
                    }
                )
    return records


def sketch_geometry_profile_type(geom):
    name = type(geom).__name__.lower()
    if "linesegment" in name:
        return "line"
    if "bspline" in name:
        return "bspline"
    if "arcofcircle" in name:
        return "arc"
    if "circle" == name:
        return "circle"
    if "arcofellipse" in name:
        return "ellipse_arc"
    if "ellipse" == name:
        return "ellipse"
    if "arcofhyperbola" in name or "arcofparabola" in name:
        return "conic_arc"
    if "point" == name:
        return "point"
    return name


def sketch_geometry_type_summary(sketch, include_construction=False):
    records = []
    counts = {}
    curve_count = 0
    for index, geom in enumerate(sketch.Geometry):
        try:
            construction = bool(sketch.getConstruction(index))
        except Exception:
            construction = False
        if construction and not include_construction:
            continue
        geometry_type = sketch_geometry_profile_type(geom)
        counts[geometry_type] = counts.get(geometry_type, 0) + 1
        if geometry_type in CURVED_PROFILE_SEGMENT_TYPES:
            curve_count += 1
        records.append(
            {
                "geometry_index": index,
                "type": geometry_type,
                "native_type": type(geom).__name__,
                "construction": construction,
            }
        )
    return {
        "counts": counts,
        "records": records,
        "curve_segment_count": curve_count,
        "total": len(records),
    }


def profile_segment_intent_report(segments):
    reports = []
    mismatches = []
    for index, segment in enumerate(segments):
        expected = segment.get("expected_type") or segment.get("intent_type")
        reason = segment.get("reason") or segment.get("intent_reason")
        policy = str(segment.get("fallback_policy", "report"))
        if expected is None and reason is None and "fallback_policy" not in segment:
            continue
        expected_type = normalized_profile_segment_type(expected)
        actual_type = normalized_profile_segment_type(segment.get("type"))
        matches = expected is None or expected_type == actual_type
        report = {
            "segment_index": index,
            "actual_type": actual_type,
            "expected_type": expected_type if expected is not None else None,
            "fallback_policy": policy,
            "reason": reason,
            "matches": matches,
        }
        reports.append(report)
        if not matches:
            mismatches.append(report)
            if policy == "fail":
                raise ValueError("profile segment intent mismatch: segment " + str(index) + " expected " + expected_type + " got " + actual_type)
    return reports, mismatches


def validate_expected_geometry_intents(sketch, params):
    specs = params.get("expected_geometry") or params.get("geometry_intents") or []
    reports = []
    mismatches = []
    for spec in specs:
        index = int(spec["geometry_index"])
        if index < 0 or index >= len(sketch.Geometry):
            report = {
                "geometry_index": index,
                "expected_type": normalized_profile_segment_type(spec.get("expected_type")),
                "actual_type": None,
                "fallback_policy": str(spec.get("fallback_policy", "report")),
                "reason": spec.get("reason"),
                "matches": False,
                "error": "geometry_index out of range",
            }
            reports.append(report)
            mismatches.append(report)
            continue
        expected_type = normalized_profile_segment_type(spec.get("expected_type"))
        actual_type = sketch_geometry_profile_type(sketch.Geometry[index])
        matches = expected_type == actual_type
        report = {
            "geometry_index": index,
            "expected_type": expected_type,
            "actual_type": actual_type,
            "fallback_policy": str(spec.get("fallback_policy", "report")),
            "reason": spec.get("reason"),
            "matches": matches,
        }
        reports.append(report)
        if not matches:
            mismatches.append(report)
    return reports, mismatches


def validate_sketch_profile(sketch, params):
    precision = int(params.get("endpoint_key_precision", 6))
    micro_offset_tolerance = float(params.get("micro_offset_tolerance", 0.05))
    forbid_isolated_points = bool(params.get("forbid_isolated_points", True))
    forbid_branch_points = bool(params.get("forbid_branch_points", True))
    forbid_micro_offsets = bool(params.get("forbid_micro_offsets", True))
    require_pad_ready = bool(params.get("require_pad_ready", True))
    require_fully_constrained = bool(params.get("require_fully_constrained", False))
    include_construction = bool(params.get("include_construction", False))

    solve_code = sketch.solve()
    try:
        sketch.Document.recompute()
    except Exception:
        pass
    face_validation = wire_face_validation(sketch.Shape)
    geometry_summary = sketch_geometry_type_summary(sketch, include_construction=include_construction)
    geometry_counts = geometry_summary["counts"]
    required_types = normalized_profile_segment_set(params.get("required_segment_types")) | normalized_profile_segment_set(params.get("required_curve_types"))
    minimum_curve_segments = int(params.get("minimum_curve_segments", 0) or 0)
    forbid_all_line_loops = bool(params.get("forbid_all_line_loops", False))
    forbid_polyline_fallback = bool(params.get("forbid_polyline_fallback", False))
    expected_geometry_reports, intent_mismatches = validate_expected_geometry_intents(sketch, params)
    open_vertices = [point_list(vertex) for vertex in getattr(sketch, "OpenVertices", [])]
    isolated_points = []
    for index, geom in enumerate(sketch.Geometry):
        try:
            construction = bool(sketch.getConstruction(index))
        except Exception:
            construction = False
        if type(geom).__name__ == "Point" and not construction:
            isolated_points.append(index)
    records = sketch_endpoint_records(sketch, precision=precision)
    clusters = {}
    for record in records:
        clusters.setdefault(record["key"], []).append(record)
    branch_points = [
        {"point": list(key), "endpoint_count": len(value), "endpoints": value}
        for key, value in sorted(clusters.items())
        if len(value) > 2
    ]
    unique_points = [value[0] for value in clusters.values()]
    near_duplicate_vertices = []
    for first_index in range(len(unique_points)):
        for second_index in range(first_index + 1, len(unique_points)):
            first = unique_points[first_index]
            second = unique_points[second_index]
            distance = math.dist(first["point"], second["point"])
            if 1e-9 < distance < micro_offset_tolerance:
                near_duplicate_vertices.append(
                    {
                        "first": first["point"],
                        "second": second["point"],
                        "distance": distance,
                    }
                )
    conflicting = list(getattr(sketch, "ConflictingConstraints", []))
    redundant = list(getattr(sketch, "RedundantConstraints", []))
    malformed = list(getattr(sketch, "MalformedConstraints", []))
    dof = getattr(sketch, "DoF", getattr(sketch, "DegreesOfFreedom", None))
    pad_ready = (
        not open_vertices
        and face_validation["wire_count"] > 0
        and face_validation["closed_wire_count"] == face_validation["wire_count"]
        and face_validation["faces_valid"]
    )
    issues = []
    if open_vertices:
        issues.append({"code": "open_vertices", "count": len(open_vertices)})
    if forbid_isolated_points and isolated_points:
        issues.append({"code": "isolated_points", "indices": isolated_points})
    if forbid_branch_points and branch_points:
        issues.append({"code": "branch_points", "count": len(branch_points)})
    if forbid_micro_offsets and near_duplicate_vertices:
        issues.append({"code": "near_duplicate_vertices", "count": len(near_duplicate_vertices)})
    if conflicting:
        issues.append({"code": "conflicting_constraints", "indices": conflicting})
    if malformed:
        issues.append({"code": "malformed_constraints", "indices": malformed})
    if require_pad_ready and not pad_ready:
        issues.append({"code": "not_pad_ready", "face_validation": face_validation})
    if require_fully_constrained and dof != 0:
        issues.append({"code": "not_fully_constrained", "degrees_of_freedom": dof})
    missing_geometry_types = sorted(required_types - set(geometry_counts.keys()))
    if missing_geometry_types:
        issues.append({"code": "missing_required_geometry_types", "types": missing_geometry_types})
    if geometry_summary["curve_segment_count"] < minimum_curve_segments:
        issues.append(
            {
                "code": "curve_segment_count_below_minimum",
                "minimum": minimum_curve_segments,
                "actual": geometry_summary["curve_segment_count"],
            }
        )
    if forbid_all_line_loops and geometry_summary["total"] > 0 and geometry_summary["curve_segment_count"] == 0:
        issues.append({"code": "all_line_fallback_detected"})
    if forbid_polyline_fallback and geometry_counts.get("polyline", 0):
        issues.append({"code": "polyline_fallback_detected", "count": geometry_counts.get("polyline", 0)})
    failing_intent_mismatches = [item for item in intent_mismatches if item.get("fallback_policy") == "fail" or bool(params.get("forbid_intent_mismatch", False))]
    if failing_intent_mismatches:
        issues.append({"code": "geometry_intent_mismatch", "mismatches": failing_intent_mismatches})
    return {
        "ok": not issues,
        "issues": issues,
        "pad_ready": pad_ready,
        "solve_code": solve_code,
        "degrees_of_freedom": dof,
        "geometry_type_counts": geometry_counts,
        "geometry_type_records": geometry_summary["records"],
        "curve_segment_count": geometry_summary["curve_segment_count"],
        "expected_geometry": expected_geometry_reports,
        "intent_mismatches": intent_mismatches,
        "open_vertices": open_vertices,
        "isolated_points": isolated_points,
        "branch_points": branch_points,
        "near_duplicate_vertices": near_duplicate_vertices,
        "conflicting_constraints": conflicting,
        "redundant_constraints": redundant,
        "malformed_constraints": malformed,
        "face_validation": face_validation,
    }


def make_sketch_profile_loop(sketch, loop, params, *, loop_index, endpoint_tolerance):
    import Sketcher

    name = str(loop.get("name") or ("loop_" + str(loop_index)))
    construction = bool(loop.get("construction", False))
    segments = loop.get("segments") or loop.get("geometry") or []
    if not segments:
        raise ValueError("profile loop has no segments: " + name)
    segment_intents, segment_intent_mismatches = profile_segment_intent_report(segments)
    curve_contract = enforce_profile_loop_curve_contract(loop, params, segments, name)
    flat = []
    for segment in segments:
        for geom in make_sketch_geometries(segment):
            flat.append((geom, bool(segment.get("construction", construction)), segment.get("type")))
    if not flat:
        raise ValueError("profile loop has no generated geometry: " + name)

    if len(flat) == 1 and not sketch_geometry_has_endpoints(flat[0][0]):
        if not geometry_is_self_closed(flat[0][0]):
            raise ValueError("single profile loop segment is not endpoint-capable or self-closed: " + name)
    else:
        for geom, _, segment_type in flat:
            if not sketch_geometry_has_endpoints(geom):
                raise ValueError("profile loop segment must expose endpoints: " + name + " / " + str(segment_type))
        for index in range(len(flat) - 1):
            distance = vector_distance(geometry_endpoint(flat[index][0], 2), geometry_endpoint(flat[index + 1][0], 1))
            if distance > endpoint_tolerance:
                raise ValueError("profile loop endpoints are not colocated before constraining: " + name + " segment " + str(index) + " distance " + str(distance))
        closing_distance = vector_distance(geometry_endpoint(flat[-1][0], 2), geometry_endpoint(flat[0][0], 1))
        if closing_distance > endpoint_tolerance:
            raise ValueError("profile loop does not close before constraining: " + name + " distance " + str(closing_distance))

    added = []
    constraint_indices = []
    geometry_reports = []
    for geom, is_construction, segment_type in flat:
        geometry_index = sketch.addGeometry(geom, is_construction)
        added.append(geometry_index)
        report = sketch_arc_geometry_report(sketch.Geometry[geometry_index], geometry_index, segment_type)
        if report is not None:
            geometry_reports.append(report)
    if len(added) > 1:
        for index in range(len(added) - 1):
            constraint_indices.append(sketch.addConstraint(Sketcher.Constraint("Coincident", added[index], 2, added[index + 1], 1)))
        constraint_indices.append(sketch.addConstraint(Sketcher.Constraint("Coincident", added[-1], 2, added[0], 1)))
    return {
        "name": name,
        "added_indices": added,
        "constraint_indices": constraint_indices,
        "segment_count": len(flat),
        "curve_contract": curve_contract,
        "segment_intents": segment_intents,
        "segment_intent_mismatches": segment_intent_mismatches,
        "geometry_reports": geometry_reports,
    }


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

    kind = str(profile.get("type") or "").lower()
    construction = bool(profile.get("construction", False))
    constrain = bool(profile.get("constrain", True))
    added = []
    constraints = []
    named_polygon_sides = {
        "triangle": 3,
        "equilateral_triangle": 3,
        "square": 4,
        "pentagon": 5,
        "hexagon": 6,
        "heptagon": 7,
        "octagon": 8,
    }
    if kind in named_polygon_sides:
        profile = dict(profile)
        profile["sides"] = named_polygon_sides[kind]
        kind = "regular_polygon"

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

    def add_rectangle_constraints(local, axis_aligned):
        if not constrain:
            return
        if axis_aligned:
            constraints.extend(
                [
                    sketch.addConstraint(Sketcher.Constraint("Horizontal", local[0])),
                    sketch.addConstraint(Sketcher.Constraint("Vertical", local[1])),
                    sketch.addConstraint(Sketcher.Constraint("Horizontal", local[2])),
                    sketch.addConstraint(Sketcher.Constraint("Vertical", local[3])),
                ]
            )
        else:
            constraints.extend(
                [
                    sketch.addConstraint(Sketcher.Constraint("Parallel", local[0], local[2])),
                    sketch.addConstraint(Sketcher.Constraint("Parallel", local[1], local[3])),
                    sketch.addConstraint(Sketcher.Constraint("Perpendicular", local[0], local[1])),
                ]
            )

    if kind in {"rectangle", "rectangle_corner", "rectangle_corners", "rectangle_2_point", "rectangle_two_points", "rectangle_center", "center_rectangle"}:
        axis_aligned = True
        if kind in {"rectangle_center", "center_rectangle"} or profile.get("center"):
            center = vector(profile.get("center"), [0, 0, 0])
            width = float(profile["width"])
            height = float(profile["height"])
            c1 = App.Vector(center.x - width / 2.0, center.y - height / 2.0, center.z)
            c2 = App.Vector(center.x + width / 2.0, center.y + height / 2.0, center.z)
        elif profile.get("corner1") and profile.get("corner2"):
            c1 = vector(profile["corner1"])
            c2 = vector(profile["corner2"])
        else:
            c1 = vector(profile.get("origin"), [0, 0, 0])
            c2 = App.Vector(c1.x + float(profile["width"]), c1.y + float(profile["height"]), c1.z)
        points = [c1, App.Vector(c2.x, c1.y, c1.z), c2, App.Vector(c1.x, c2.y, c1.z)]
        local = add_lines(points, True)
        add_rectangle_constraints(local, axis_aligned)
        if bool(profile.get("dimension_constraints", False)):
            constraints.append(sketch.addConstraint(Sketcher.Constraint("DistanceX", local[0], 1, local[0], 2, abs(c2.x - c1.x))))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("DistanceY", local[1], 1, local[1], 2, abs(c2.y - c1.y))))
    elif kind in {"rectangle_3_point", "rectangle_three_points"}:
        points_input = profile.get("points") or [profile["point1"], profile["point2"], profile["point3"]]
        p1 = vector(points_input[0])
        p2 = vector(points_input[1])
        p3 = vector(points_input[2])
        edge = p2 - p1
        length = float(edge.Length)
        if length <= 1e-12:
            raise ValueError("rectangle_3_point requires distinct point1 and point2")
        normal = App.Vector(-edge.y / length, edge.x / length, 0)
        height = (p3 - p2).dot(normal)
        if abs(height) <= 1e-12:
            raise ValueError("rectangle_3_point requires point3 away from the first edge")
        p3_projected = p2 + normal * height
        p4 = p1 + normal * height
        local = add_lines([p1, p2, p3_projected, p4], True)
        add_rectangle_constraints(local, False)
    elif kind == "polyline":
        added.extend(add_lines([vector(point) for point in profile["points"]], bool(profile.get("closed", True))))
    elif kind == "regular_polygon":
        sides = int(profile["sides"])
        if sides < 3:
            raise ValueError("regular_polygon requires sides >= 3")
        center = vector(profile.get("center"), [0, 0, 0])
        corner_value = None
        for corner_key in ("corner", "first_corner", "firstCornerPoint", "first_corner_point", "corner_point"):
            if profile.get(corner_key) is not None:
                corner_value = profile[corner_key]
                break
        if corner_value is not None:
            first_corner = vector(corner_value)
            diff = App.Vector(first_corner.x - center.x, first_corner.y - center.y, 0)
            radius = float(diff.Length)
            if radius <= 1e-12:
                raise ValueError("regular_polygon requires distinct center and corner")
        else:
            radius = float(profile["radius"])
            if radius <= 1e-12:
                raise ValueError("regular_polygon requires radius > 0")
            start = angle_radians(profile.get("start_angle"), 0.0)
            diff = App.Vector(radius * math.cos(start), radius * math.sin(start), 0)
        points = [
            App.Vector(
                center.x + math.cos(2 * math.pi * idx / sides) * diff.x - math.sin(2 * math.pi * idx / sides) * diff.y,
                center.y + math.cos(2 * math.pi * idx / sides) * diff.y + math.sin(2 * math.pi * idx / sides) * diff.x,
                center.z,
            )
            for idx in range(sides)
        ]
        local = add_lines(points, True)
        circle_idx = None
        if bool(profile.get("construction_circle", True)):
            circle_idx = sketch.addGeometry(Part.Circle(center, vector(profile.get("normal"), [0, 0, 1]), radius), True)
            added.append(circle_idx)
        if constrain and bool(profile.get("equal_edges", True)):
            for idx in range(1, len(local)):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Equal", local[0], local[idx])))
        if constrain and circle_idx is not None and bool(profile.get("point_on_circle", True)):
            for idx in range(len(local)):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("PointOnObject", local[idx], 2, circle_idx)))
    elif kind in {"circle", "circle_profile"}:
        center = vector(profile.get("center"), [0, 0, 0])
        geom = Part.Circle(center, vector(profile.get("normal"), [0, 0, 1]), float(profile["radius"]))
        idx = sketch.addGeometry(geom, construction)
        added.append(idx)
        if bool(profile.get("radius_constraint", constrain)):
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Radius", idx, float(profile["radius"]))))
    elif kind in {"slot", "slot_center_length_radius", "slot_start_end_radius", "slot_2_point", "slot_two_points"}:
        radius = float(profile["radius"])
        if kind in {"slot_start_end_radius", "slot_2_point", "slot_two_points"} or profile.get("start"):
            left = vector(profile.get("start") or profile.get("point1"))
            right = vector(profile.get("end") or profile.get("point2"))
        else:
            center = vector(profile.get("center"), [0, 0, 0])
            length = float(profile["length"])
            left = App.Vector(center.x - length / 2, center.y, center.z)
            right = App.Vector(center.x + length / 2, center.y, center.z)
        axis = right - left
        axis_length = float(axis.Length)
        if axis_length <= 1e-12:
            raise ValueError("slot requires distinct start and end centers")
        unit = App.Vector(axis.x / axis_length, axis.y / axis_length, axis.z / axis_length)
        normal = App.Vector(-unit.y, unit.x, 0)
        top_left = left + normal * radius
        top_right = right + normal * radius
        bottom_right = right - normal * radius
        bottom_left = left - normal * radius
        local = [
            sketch.addGeometry(Part.LineSegment(top_left, top_right), construction),
            sketch.addGeometry(Part.ArcOfCircle(top_right, right + unit * radius, bottom_right), construction),
            sketch.addGeometry(Part.LineSegment(bottom_right, bottom_left), construction),
            sketch.addGeometry(Part.ArcOfCircle(bottom_left, left - unit * radius, top_left), construction),
        ]
        added.extend(local)
        if constrain:
            for idx in range(len(local) - 1):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[idx], 2, local[idx + 1], 1)))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[-1], 2, local[0], 1)))
            if bool(profile.get("tangent_constraints", False)):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[0], 2, local[1], 1)))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[1], 2, local[2], 1)))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[2], 2, local[3], 1)))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[3], 2, local[0], 1)))
            if abs(unit.y) <= 1e-12:
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Horizontal", local[0])))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Horizontal", local[2])))
            else:
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Parallel", local[0], local[2])))
            if bool(profile.get("equal_arcs", False)):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Equal", local[1], local[3])))
    elif kind in {"keyhole", "circle_slot_union", "slot_circle_union"}:
        center = vector(profile.get("circle_center") or profile.get("center"), [0, 0, 0])
        circle_radius = float(profile.get("circle_radius", profile.get("head_radius", profile.get("radius"))))
        if profile.get("slot_radius") is not None:
            slot_radius = float(profile["slot_radius"])
        elif profile.get("neck_radius") is not None:
            slot_radius = float(profile["neck_radius"])
        elif profile.get("slot_width") is not None:
            slot_radius = float(profile["slot_width"]) / 2.0
        elif profile.get("width") is not None:
            slot_radius = float(profile["width"]) / 2.0
        else:
            raise ValueError("keyhole requires slot_radius or slot_width")
        slot_end = vector(profile.get("slot_end") or profile.get("end"))
        axis = App.Vector(slot_end.x - center.x, slot_end.y - center.y, 0)
        axis_length = float(axis.Length)
        if circle_radius <= 0:
            raise ValueError("keyhole requires circle_radius > 0")
        if slot_radius <= 0 or slot_radius >= circle_radius:
            raise ValueError("keyhole requires 0 < slot_radius < circle_radius")
        if axis_length <= 1e-12:
            raise ValueError("keyhole requires distinct circle_center and slot_end")
        unit = App.Vector(axis.x / axis_length, axis.y / axis_length, 0)
        normal = App.Vector(-unit.y, unit.x, 0)
        transition = math.sqrt(max(circle_radius * circle_radius - slot_radius * slot_radius, 0.0))
        if axis_length <= transition + 1e-9:
            raise ValueError("keyhole slot_end must extend beyond the circle/slot transition")
        top_near = center + unit * transition + normal * slot_radius
        bottom_near = center + unit * transition - normal * slot_radius
        top_far = slot_end + normal * slot_radius
        bottom_far = slot_end - normal * slot_radius
        far_mid = slot_end + unit * slot_radius
        circle_mid = center - unit * circle_radius
        local = [
            sketch.addGeometry(Part.LineSegment(top_near, top_far), construction),
            sketch.addGeometry(Part.ArcOfCircle(top_far, far_mid, bottom_far), construction),
            sketch.addGeometry(Part.LineSegment(bottom_far, bottom_near), construction),
            sketch.addGeometry(Part.ArcOfCircle(bottom_near, circle_mid, top_near), construction),
        ]
        added.extend(local)
        if constrain:
            for idx in range(len(local) - 1):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[idx], 2, local[idx + 1], 1)))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[-1], 2, local[0], 1)))
            if bool(profile.get("tangent_constraints", False)):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[0], 2, local[1], 1)))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[1], 2, local[2], 1)))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[2], 2, local[3], 1)))
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Tangent", local[3], 2, local[0], 1)))
    elif kind in {"arc_slot", "slot_arc"}:
        center = vector(profile.get("center"), [0, 0, 0])
        radius = float(profile["radius"])
        width = float(profile.get("width", profile.get("slot_width")))
        inner_radius = radius - width / 2.0
        outer_radius = radius + width / 2.0
        if inner_radius <= 0:
            raise ValueError("arc_slot width must be smaller than twice the radius")
        start = angle_radians(profile["start_angle"])
        end = angle_radians(profile["end_angle"])
        sweep = requested_arc_sweep(start, end, direction=profile.get("direction"), sweep=profile.get("sweep"))
        mid = start + sweep / 2.0
        outer_start = arc_point(center, outer_radius, start)
        outer_mid = arc_point(center, outer_radius, mid)
        outer_end = arc_point(center, outer_radius, start + sweep)
        inner_start = arc_point(center, inner_radius, start)
        inner_mid = arc_point(center, inner_radius, mid)
        inner_end = arc_point(center, inner_radius, start + sweep)
        local = [
            sketch.addGeometry(Part.ArcOfCircle(outer_start, outer_mid, outer_end), construction),
            sketch.addGeometry(Part.LineSegment(outer_end, inner_end), construction),
            sketch.addGeometry(Part.ArcOfCircle(inner_end, inner_mid, inner_start), construction),
            sketch.addGeometry(Part.LineSegment(inner_start, outer_start), construction),
        ]
        added.extend(local)
        if constrain:
            for idx in range(len(local) - 1):
                constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[idx], 2, local[idx + 1], 1)))
            constraints.append(sketch.addConstraint(Sketcher.Constraint("Coincident", local[-1], 2, local[0], 1)))
    else:
        raise ValueError("unsupported sketch profile: " + str(kind))

    return added, constraints


def action_sketch_create(params):
    doc = get_doc(params)
    doc.openTransaction("MCP worker create sketch")
    try:
        sketch = doc.addObject("Sketcher::SketchObject", params.get("sketch_name") or "Sketch")
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {"saved_path": saved, "sketch": object_summary(sketch), "attachment": attachment, "document": document_summary(doc)}


def action_sketch_add_geometry(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    connect_sequence = bool(params.get("connect_sequence", False))
    close_sequence = bool(params.get("close_sequence", False))
    require_closed = bool(params.get("require_closed", False))
    closed_validation = None
    doc.openTransaction("MCP worker add sketch geometry")
    try:
        added, constraint_indices, geometry_reports = add_sketch_geometry_batch(
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
        "geometry_reports": geometry_reports,
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


def action_sketch_profile_create(params):
    import Sketcher

    doc = get_doc(params)
    sketch_name = params.get("sketch_name") or "ProfileSketch"
    sketch = doc.getObject(sketch_name)
    doc.openTransaction("MCP worker create sketch profile")
    try:
        if sketch is None:
            sketch = doc.addObject("Sketcher::SketchObject", sketch_name)
        elif bool(params.get("replace_existing", False)):
            sketch.deleteAllConstraints()
            sketch.deleteAllGeometry()
        attachment = attach_sketch_to_partdesign_body(doc, sketch, params)
        loops = params.get("loops") or []
        if not loops:
            raise ValueError("loops is required")
        endpoint_tolerance = float(params.get("endpoint_tolerance", 1e-6))
        loop_reports = []
        all_added = []
        all_constraints = []
        all_geometry_reports = []
        for index, loop in enumerate(loops):
            report = make_sketch_profile_loop(sketch, loop, params, loop_index=index, endpoint_tolerance=endpoint_tolerance)
            loop_reports.append(report)
            all_added.extend(report["added_indices"])
            all_constraints.extend(report["constraint_indices"])
            all_geometry_reports.extend(report["geometry_reports"])
        block_indices = []
        lock_mode = str(params.get("lock_mode", "none"))
        if lock_mode not in {"none", "block"}:
            raise ValueError("unsupported lock_mode: " + lock_mode)
        if lock_mode == "block":
            for geometry_index in all_added:
                block_indices.append(sketch.addConstraint(Sketcher.Constraint("Block", geometry_index)))
        doc.recompute()
        validation = validate_sketch_profile(sketch, params)
        if bool(params.get("require_valid", True)) and not validation["ok"]:
            raise ValueError("sketch profile validation failed: " + str(validation["issues"]))
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_doc(doc, params)
    return {
        "saved_path": saved,
        "sketch": object_summary(sketch),
        "loops": loop_reports,
        "added_indices": all_added,
        "constraint_indices": all_constraints,
        "geometry_reports": all_geometry_reports,
        "block_constraint_indices": block_indices,
        "validation": validation,
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_sketch_profile_validate(params):
    doc = get_doc(params)
    sketch = get_object(doc, params.get("sketch_name") or "")
    validation = validate_sketch_profile(sketch, params)
    return {"sketch": object_summary(sketch), "validation": validation, "document": document_summary(doc)}


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
    supported_actions = {"harmonize_normals", "remove_duplicated_points"}
    if not any(action in supported_actions for action in actions):
        for name in names:
            obj = get_object(doc, name)
            reports.append(
                {
                    "object": obj.Name,
                    "assigned_to": obj.Name,
                    "actions": [],
                    "errors": [{"action": action, "error": "unsupported action"} for action in actions],
                    "mutated": False,
                }
            )
        saved = save_doc(doc, params)
        return {"saved_path": saved, "reports": reports, "document": document_summary(doc)}
    doc.openTransaction("MCP worker mesh repair")
    try:
        for name in names:
            obj = get_object(doc, name)
            mesh = None
            done = []
            errors = []
            def editable_mesh():
                nonlocal mesh
                if mesh is None:
                    mesh = obj.Mesh.copy()
                return mesh
            for action in actions:
                if action == "harmonize_normals" and hasattr(obj.Mesh, "harmonizeNormals"):
                    try:
                        editable_mesh().harmonizeNormals()
                        done.append(action)
                    except Exception as exc:
                        errors.append({"action": action, "error": str(exc)})
                elif action == "remove_duplicated_points" and hasattr(obj.Mesh, "removeDuplicatedPoints"):
                    try:
                        editable_mesh().removeDuplicatedPoints()
                        done.append(action)
                    except Exception as exc:
                        errors.append({"action": action, "error": str(exc)})
                else:
                    errors.append({"action": action, "error": "unsupported action"})
            assigned_to = obj.Name
            if done and mesh is not None:
                try:
                    obj.Mesh = mesh
                except Exception:
                    replacement = doc.addObject("Mesh::Feature", params.get("result_name") or (obj.Name + "_Repaired"))
                    replacement.Mesh = mesh
                    assigned_to = replacement.Name
            reports.append({"object": obj.Name, "assigned_to": assigned_to, "actions": done, "errors": errors, "mutated": bool(done)})
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
    "partdesign_body_create": action_partdesign_body_create,
    "partdesign_datum_plane_create": action_partdesign_datum_plane_create,
    "partdesign_pad": action_partdesign_pad,
    "partdesign_pocket": action_partdesign_pocket,
    "partdesign_hole": action_partdesign_hole,
    "partdesign_revolution": action_partdesign_revolution,
    "partdesign_groove": action_partdesign_groove,
    "partdesign_additive_loft": action_partdesign_additive_loft,
    "partdesign_subtractive_loft": action_partdesign_subtractive_loft,
    "partdesign_additive_pipe": action_partdesign_additive_pipe,
    "partdesign_subtractive_pipe": action_partdesign_subtractive_pipe,
    "partdesign_fillet": action_partdesign_fillet,
    "partdesign_chamfer": action_partdesign_chamfer,
    "partdesign_thickness": action_partdesign_thickness,
    "partdesign_draft": action_partdesign_draft,
    "partdesign_linear_pattern": action_partdesign_linear_pattern,
    "partdesign_polar_pattern": action_partdesign_polar_pattern,
    "partdesign_mirrored": action_partdesign_mirrored,
    "part_revolve": action_part_revolve,
    "part_check_geometry": action_part_check_geometry,
    "sketch_create": action_sketch_create,
    "sketch_add_geometry": action_sketch_add_geometry,
    "sketch_add_constraint": action_sketch_add_constraint,
    "sketch_add_profile": action_sketch_add_profile,
    "sketch_profile_create": action_sketch_profile_create,
    "sketch_profile_validate": action_sketch_profile_validate,
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
    "object_rename_label": action_object_rename_label,
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
