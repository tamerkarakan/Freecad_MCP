
import base64
import json
import math
import os
import re
import traceback

import FreeCAD as App

PREFIX = "__FREECAD_MCP_JSON__"
ARGS = json.loads(base64.b64decode("__ARGS_B64__").decode("utf-8"))


def emit(payload):
    print(PREFIX + json.dumps(payload, default=str))


def vector(value, default=None):
    if value is None:
        value = default if default is not None else [0, 0, 0]
    if hasattr(value, "x") and hasattr(value, "y"):
        return App.Vector(float(value.x), float(value.y), float(getattr(value, "z", 0.0)))
    if isinstance(value, dict):
        if "value" in value:
            return vector(value["value"], default)
        if "x" in value and "y" in value:
            return App.Vector(float(value["x"]), float(value["y"]), float(value.get("z", 0.0)))
    if len(value) == 2:
        return App.Vector(float(value[0]), float(value[1]), 0.0)
    if len(value) >= 3:
        return App.Vector(float(value[0]), float(value[1]), float(value[2]))
    raise ValueError("vector values must contain at least x/y coordinates")


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


def point_attr(value, name):
    try:
        point = getattr(value, name)
    except Exception:
        return None
    try:
        return point_list(point)
    except Exception:
        return None


def float_attr(value, name):
    try:
        raw = getattr(value, name)
    except Exception:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def fully_constrained_from_dof(dof):
    if dof is None:
        return None
    try:
        return abs(float(dof)) < 1e-9
    except Exception:
        return None


def point_pos_name(pos):
    return {1: "start", 2: "end", 3: "center"}.get(int(pos), str(pos))


def constraint_ref(role, geometry_index, point_pos):
    ref = {"role": role, "geometry_index": int(geometry_index)}
    if int(point_pos):
        ref["point_pos"] = int(point_pos)
        ref["point"] = point_pos_name(point_pos)
    if int(geometry_index) < 0:
        ref["special_reference"] = {
            -1: "sketch_horizontal_axis",
            -2: "sketch_vertical_axis",
        }.get(int(geometry_index), "external_or_internal_reference")
    return ref


def constraint_refs(constraint):
    refs = []
    for role, geo_attr, pos_attr in (
        ("first", "First", "FirstPos"),
        ("second", "Second", "SecondPos"),
        ("third", "Third", "ThirdPos"),
    ):
        geometry_index = int(getattr(constraint, geo_attr, -2000))
        point_pos = int(getattr(constraint, pos_attr, 0))
        if geometry_index != -2000:
            refs.append(constraint_ref(role, geometry_index, point_pos))
    return refs


def grouped_components(edges):
    parent = {}

    def find(value):
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, right in edges:
        union(int(left), int(right))
    groups = {}
    for value in list(parent):
        groups.setdefault(find(value), set()).add(value)
    return [sorted(group) for group in groups.values() if len(group) > 1]


def sketch_semantic_groups(sketch):
    constraints = list(getattr(sketch, "Constraints", []) or [])
    tangent_edges = []
    equal_edges = []
    coincident_pairs = []
    dimensional_constraints = []
    radius_constraints = []
    for index, constraint in enumerate(constraints):
        constraint_type = str(getattr(constraint, "Type", ""))
        first = int(getattr(constraint, "First", -2000))
        second = int(getattr(constraint, "Second", -2000))
        first_pos = int(getattr(constraint, "FirstPos", 0))
        second_pos = int(getattr(constraint, "SecondPos", 0))
        if constraint_type == "Tangent" and first >= 0 and second >= 0:
            tangent_edges.append((first, second))
        elif constraint_type == "Equal" and first >= 0 and second >= 0:
            equal_edges.append((first, second))
        elif constraint_type == "Coincident":
            coincident_pairs.append(
                {
                    "index": index,
                    "refs": [
                        constraint_ref("first", first, first_pos),
                        constraint_ref("second", second, second_pos),
                    ],
                }
            )
        if constraint_type in {"Distance", "DistanceX", "DistanceY", "Angle", "Radius", "Diameter"}:
            item = constraint_summary(constraint, index)
            dimensional_constraints.append(item)
            if constraint_type in {"Radius", "Diameter"}:
                radius_constraints.append(item)
    construction_geometry = []
    for geometry_index, _geometry in enumerate(list(getattr(sketch, "Geometry", []) or [])):
        try:
            if bool(sketch.getConstruction(geometry_index)):
                construction_geometry.append(geometry_index)
        except Exception:
            pass
    return {
        "construction_geometry": construction_geometry,
        "coincident_pairs": coincident_pairs,
        "tangent_pairs": [
            {"geometry": [int(left), int(right)]}
            for left, right in tangent_edges
        ],
        "tangent_chains": grouped_components(tangent_edges),
        "equal_pairs": [
            {"geometry": [int(left), int(right)]}
            for left, right in equal_edges
        ],
        "equal_groups": grouped_components(equal_edges),
        "dimensional_constraints": dimensional_constraints,
        "radius_constraints": radius_constraints,
    }


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


def cam_summary(obj):
    type_id = getattr(obj, "TypeId", "")
    if not str(type_id).startswith("Path::"):
        return None
    summary = {"type": type_id}
    path = getattr(obj, "Path", None)
    if path is not None:
        commands = list(getattr(path, "Commands", []) or [])
        gcode = path.toGCode() if hasattr(path, "toGCode") else ""
        summary["command_count"] = len(commands)
        summary["commands"] = [
            {
                "name": str(getattr(command, "Name", "")),
                "parameters": dict(getattr(command, "Parameters", {}) or {}),
            }
            for command in commands[:50]
        ]
        summary["gcode_preview"] = gcode[:1000]
        summary["gcode_truncated"] = len(gcode) > 1000
    return summary


def fem_reference_summary(refs):
    rows = []
    for ref in refs or []:
        try:
            obj, subelements = ref
        except Exception:
            rows.append({"repr": repr(ref)})
            continue
        if isinstance(subelements, str):
            subelements = [subelements]
        rows.append(
            {
                "object_name": getattr(obj, "Name", str(obj)),
                "subelements": list(subelements or []),
            }
        )
    return rows


def fem_summary(obj):
    type_id = getattr(obj, "TypeId", "")
    if not (str(type_id).startswith("Fem::") or str(type_id) == "App::MaterialObjectPython"):
        return None
    summary = {"type": type_id}
    if type_id == "Fem::FemAnalysis":
        summary["members"] = [getattr(member, "Name", str(member)) for member in getattr(obj, "Group", [])]
        summary["member_count"] = len(summary["members"])
    if hasattr(obj, "References"):
        summary["references"] = fem_reference_summary(getattr(obj, "References", []))
    if hasattr(obj, "Material"):
        try:
            summary["material"] = dict(obj.Material)
        except Exception:
            summary["material"] = str(obj.Material)
    if hasattr(obj, "Force"):
        summary["force"] = quantity_summary(obj.Force)
    if hasattr(obj, "Direction"):
        try:
            direction_obj, direction_subs = obj.Direction
            summary["direction"] = {
                "object_name": getattr(direction_obj, "Name", str(direction_obj)),
                "subelements": list(direction_subs or []),
            }
        except Exception:
            summary["direction"] = str(obj.Direction)
    return summary


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
    summary["refs"] = constraint_refs(constraint)
    return summary


def geometry_summary(sketch, geometry, index):
    try:
        construction = bool(sketch.getConstruction(index))
    except Exception:
        construction = None
    summary = {
        "index": index,
        "type_id": geometry.getTypeId().getName() if hasattr(geometry, "getTypeId") else type(geometry).__name__,
        "construction": construction,
        "repr": repr(geometry),
    }
    for key, attr in (
        ("start", "StartPoint"),
        ("end", "EndPoint"),
        ("center", "Center"),
        ("location", "Location"),
    ):
        point = point_attr(geometry, attr)
        if point is not None:
            summary[key] = point
    for key, attr in (
        ("radius", "Radius"),
        ("major_radius", "MajorRadius"),
        ("minor_radius", "MinorRadius"),
        ("first_parameter", "FirstParameter"),
        ("last_parameter", "LastParameter"),
    ):
        value = float_attr(geometry, attr)
        if value is not None:
            summary[key] = value
    if "center" not in summary and "location" in summary:
        summary["center"] = summary["location"]
    circle = getattr(geometry, "Circle", None)
    if circle is not None:
        if "center" not in summary:
            center = point_attr(circle, "Center")
            if center is not None:
                summary["center"] = center
        if "radius" not in summary:
            radius = float_attr(circle, "Radius")
            if radius is not None:
                summary["radius"] = radius
        axis = point_attr(circle, "Axis")
        if axis is not None:
            summary["axis"] = axis
    axis = point_attr(geometry, "Axis")
    if axis is not None:
        summary["axis"] = axis
    return summary


def sketch_summary(obj):
    if getattr(obj, "TypeId", "") != "Sketcher::SketchObject":
        return None
    geometry = list(getattr(obj, "Geometry", []))
    constraints = list(getattr(obj, "Constraints", []))
    dof = getattr(obj, "DoF", getattr(obj, "DegreesOfFreedom", None))
    return {
        "geometry_count": len(geometry),
        "constraint_count": len(constraints),
        "degrees_of_freedom": dof,
        "fully_constrained": fully_constrained_from_dof(dof),
        "open_vertices": [point_list(v) for v in getattr(obj, "OpenVertices", [])],
        "conflicting_constraints": list(getattr(obj, "ConflictingConstraints", [])),
        "redundant_constraints": list(getattr(obj, "RedundantConstraints", [])),
        "partially_redundant_constraints": list(getattr(obj, "PartiallyRedundantConstraints", [])),
        "malformed_constraints": list(getattr(obj, "MalformedConstraints", [])),
        "geometry": [geometry_summary(obj, geo, idx) for idx, geo in enumerate(geometry)],
        "constraints": [constraint_summary(constraint, idx) for idx, constraint in enumerate(constraints)],
        "semantic_groups": sketch_semantic_groups(obj),
    }


def techdraw_summary(obj):
    type_id = getattr(obj, "TypeId", "")
    if not str(type_id).startswith("TechDraw::"):
        return None
    summary = {"type": type_id}
    if type_id == "TechDraw::DrawPage":
        try:
            views = obj.getViews()
        except Exception:
            views = []
        summary["views"] = [getattr(view, "Name", str(view)) for view in views]
        summary["view_count"] = len(views)
        for method, key in [
            ("getPageWidth", "page_width"),
            ("getPageHeight", "page_height"),
            ("getPageOrientation", "page_orientation"),
        ]:
            try:
                summary[key] = getattr(obj, method)()
            except Exception:
                summary[key] = None
        template = getattr(obj, "Template", None)
        summary["template"] = getattr(template, "Name", None) if template is not None else None
    elif type_id == "TechDraw::DrawViewPart":
        sources = getattr(obj, "Source", []) or []
        summary["source_names"] = [getattr(source, "Name", str(source)) for source in sources]
        summary["state"] = list(getattr(obj, "State", []) or [])
        summary["direction"] = point_list(getattr(obj, "Direction", [0, 0, 1]))
        summary["x_direction"] = point_list(getattr(obj, "XDirection", [1, 0, 0]))
        summary["scale"] = float(getattr(obj, "Scale", 1.0))
        summary["x"] = float(getattr(obj, "X", 0.0))
        summary["y"] = float(getattr(obj, "Y", 0.0))
    elif type_id == "TechDraw::DrawSVGTemplate":
        summary["template_path"] = str(getattr(obj, "Template", ""))
    return summary


def object_summary(obj):
    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "visibility": bool(getattr(obj, "Visibility", False)),
        "placement": placement_summary(obj),
        "shape": shape_summary(obj),
        "mesh": mesh_summary(obj),
        "cam": cam_summary(obj),
        "fem": fem_summary(obj),
        "sketch": sketch_summary(obj),
        "techdraw": techdraw_summary(obj),
        "partdesign": partdesign_summary(obj),
        "expressions": expression_summary(obj),
    }


def expression_summary(obj):
    rows = []
    try:
        engine = list(getattr(obj, "ExpressionEngine", []) or [])
    except Exception:
        engine = []
    for item in engine:
        try:
            path, expression = item
        except Exception:
            rows.append({"repr": repr(item)})
            continue
        rows.append({"path": str(path), "expression": str(expression)})
    return rows


CELL_RE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NUMERIC_TEXT = r"[+-]?\s*(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
BARE_NUMERIC_TEXT_RE = re.compile(r"^" + NUMERIC_TEXT + r"$")
QUANTITY_TEXT_RE = re.compile(r"^(" + NUMERIC_TEXT + r")\s*([A-Za-z_][A-Za-z0-9_*/^.-]*)$")
NEGATIVE_NUMERIC_TEXT_RE = re.compile(r"^-\s*(?:\d+(?:\.\d*)?|\.\d+)(?:\s*[A-Za-z_][A-Za-z0-9_*/^.-]*)?$")
UNIT_TEXT_RE = re.compile(r"^[A-Za-z0-9_./*^()-]+$")


def normalize_cell(value):
    cell = str(value or "").strip().upper()
    if not CELL_RE.match(cell):
        raise ValueError("invalid spreadsheet cell: " + str(value))
    return cell


def normalize_column(value, default):
    column = str(value or default).strip().upper()
    if not re.match(r"^[A-Z]{1,3}$", column):
        raise ValueError("invalid spreadsheet column: " + str(value))
    return column


def normalize_alias(value):
    alias = str(value or "").strip()
    if not alias:
        return ""
    if not ALIAS_RE.match(alias):
        raise ValueError("invalid spreadsheet alias: " + alias)
    return alias


def normalize_unit(value, *, field_name="unit"):
    unit = str(value or "").strip()
    if not unit:
        return ""
    if not UNIT_TEXT_RE.match(unit):
        raise ValueError(f"invalid spreadsheet {field_name}: {unit}")
    return unit


def numeric_text(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("spreadsheet numeric value must be finite")
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if BARE_NUMERIC_TEXT_RE.match(text):
            return text
    return None


def simple_quantity_parts(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = QUANTITY_TEXT_RE.match(text)
    if not match:
        return None
    return match.group(1).strip(), normalize_unit(match.group(2))


def spreadsheet_value_text(value, *, coerce_negative_numeric=False):
    if value is None:
        return ""
    if isinstance(value, dict):
        if "quantity" in value:
            return spreadsheet_value_text(value["quantity"], coerce_negative_numeric=True)
        if "formula" in value:
            formula = str(value["formula"])
            return formula if formula.startswith("=") else "=" + formula
        if "value" in value:
            return spreadsheet_value_text(value["value"], coerce_negative_numeric=coerce_negative_numeric)
    text = str(value).strip()
    if coerce_negative_numeric and text and not text.startswith(("=", "'")) and NEGATIVE_NUMERIC_TEXT_RE.match(text):
        return "=" + text
    return text


def spreadsheet_cell_value_result(value, *, default_unit="", require_units=False, spec=None, context="spreadsheet value"):
    spec = spec or {}
    unit = normalize_unit(spec.get("unit") or spec.get("display_unit") or default_unit)
    unitless = bool(spec.get("unitless") or spec.get("dimensionless"))
    warning = None

    if isinstance(value, dict):
        nested_spec = {
            "unit": value.get("unit") or value.get("display_unit") or unit,
            "unitless": unitless or bool(value.get("unitless") or value.get("dimensionless")),
        }
        if "formula" in value:
            formula = str(value["formula"]).strip()
            text = formula if formula.startswith("=") else "=" + formula
            display_unit = normalize_unit(value.get("display_unit") or unit)
            return {"text": text, "display_unit": display_unit, "warning": None}
        if "quantity" in value:
            return spreadsheet_cell_value_result(
                value["quantity"],
                default_unit=default_unit,
                require_units=True,
                spec=nested_spec,
                context=context,
            )
        if "value" in value:
            return spreadsheet_cell_value_result(
                value["value"],
                default_unit=default_unit,
                require_units=require_units,
                spec=nested_spec,
                context=context,
            )

    bare_number = numeric_text(value)
    if bare_number is not None:
        if unitless:
            return {"text": bare_number, "display_unit": "", "warning": None}
        if unit:
            return {"text": f"={bare_number} {unit}", "display_unit": unit, "warning": None}
        message = (
            f"{context} is a bare numeric value without a unit. "
            "Ask the user which unit to use, pass unit/default_unit such as 'mm', "
            "or set unitless=true for counts and ratios."
        )
        if require_units:
            raise ValueError(message)
        warning = message

    raw_quantity = simple_quantity_parts(value)
    text = spreadsheet_value_text(value, coerce_negative_numeric=True)
    display_unit = normalize_unit(spec.get("display_unit") or "")
    quantity = simple_quantity_parts(text) or raw_quantity
    if quantity:
        _, detected_unit = quantity
        display_unit = display_unit or detected_unit
        if not text.startswith(("=", "'")):
            text = "=" + text
    elif unit and not display_unit:
        display_unit = unit
    return {"text": text, "display_unit": display_unit, "warning": warning}


def get_spreadsheet(doc, sheet_name):
    sheet = get_object(doc, sheet_name)
    if getattr(sheet, "TypeId", "") != "Spreadsheet::Sheet":
        raise ValueError("object is not a Spreadsheet::Sheet: " + sheet_name)
    return sheet


def spreadsheet_cell_value(sheet, cell):
    try:
        return sheet.get(cell)
    except Exception as exc:
        return "<error: %s>" % exc


def spreadsheet_summary(sheet, cells=None, aliases=None, include_known_aliases=False):
    result = {
        "name": sheet.Name,
        "label": sheet.Label,
        "type_id": sheet.TypeId,
        "cells": {},
        "aliases": {},
    }
    for cell in cells or []:
        normalized = normalize_cell(cell)
        result["cells"][normalized] = spreadsheet_cell_value(sheet, normalized)
    alias_names = []
    for alias in aliases or []:
        normalized_alias = normalize_alias(alias)
        if normalized_alias:
            alias_names.append(normalized_alias)
    if include_known_aliases:
        try:
            known = sheet.getAliases()
        except Exception:
            known = []
        if isinstance(known, dict):
            alias_names.extend(str(alias) for alias in known)
        elif isinstance(known, (list, tuple, set)):
            alias_names.extend(str(alias) for alias in known)
    for alias in sorted(set(alias_names)):
        try:
            cell = sheet.getCellFromAlias(alias)
            result["aliases"][alias] = {"cell": cell, "value": spreadsheet_cell_value(sheet, cell)}
        except Exception as exc:
            result["aliases"][alias] = {"error": str(exc)}
    return result


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


def property_status_tokens(obj, property_name):
    getter = getattr(obj, "getPropertyStatus", None)
    if getter is None:
        return []
    try:
        status = getter(property_name)
    except Exception:
        return []
    if status is None:
        return []
    if isinstance(status, str):
        values = [status]
    else:
        try:
            values = list(status)
        except TypeError:
            values = [status]
    return [str(item) for item in values if str(item)]


def normalized_property_status(value):
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def ensure_settable_property(obj, property_name):
    prop = str(property_name or "").strip()
    if not prop:
        raise ValueError("invalid property name: " + str(property_name))
    if prop.startswith("_"):
        raise ValueError("invalid property name: " + prop)
    if prop not in list(getattr(obj, "PropertiesList", []) or []):
        raise ValueError("unknown FreeCAD property: " + prop)
    statuses = property_status_tokens(obj, prop)
    blocked = {"readonly", "immutable"}
    blocked_statuses = [status for status in statuses if normalized_property_status(status) in blocked]
    if blocked_statuses:
        raise ValueError("property is not writable: " + prop + " status=" + ",".join(blocked_statuses))
    return prop


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


def resolve_partdesign_attachment_support(doc, body, args):
    support_name = (
        args.get("attachment_object")
        or args.get("attachment_object_name")
        or args.get("support_object")
        or args.get("support_object_name")
        or args.get("datum_plane_name")
    )
    if support_name:
        support = get_object(doc, support_name)
        subname = args.get("attachment_subname") or args.get("support_subname") or ""
        return support, str(subname), {
            "support_type": "object",
            "support_object": getattr(support, "Name", None),
            "support_label": getattr(support, "Label", None),
            "support_type_id": getattr(support, "TypeId", None),
            "support_subname": str(subname),
        }
    plane_name = normalize_partdesign_plane(args.get("attachment_plane") or args.get("plane") or "XY")
    plane = find_body_origin_plane(body, plane_name)
    return plane, "", {
        "support_type": "origin_plane",
        "plane": plane_name,
        "plane_object": plane.Name,
        "support_object": plane.Name,
        "support_subname": "",
    }


def attachment_support_name(args):
    return (
        args.get("attachment_object")
        or args.get("attachment_object_name")
        or args.get("support_object")
        or args.get("support_object_name")
        or args.get("datum_plane_name")
    )


def attachment_requested(args):
    return any(
        key in args
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


def attachment_target_requested(args):
    return any(
        key in args
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


def apply_attachment_offset(obj, args):
    raw_vector = args.get("attachment_offset_vector") or args.get("offset_vector")
    if raw_vector is None and (args.get("attachment_offset") is not None or args.get("offset") is not None):
        offset = args.get("attachment_offset")
        if offset is None:
            offset = args.get("offset")
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


def apply_hole_parameters(hole, args):
    if hasattr(hole, "Diameter"):
        hole.Diameter = float(args["diameter"])
    if hasattr(hole, "Depth"):
        hole.Depth = float(args.get("depth", 10.0))
    if hasattr(hole, "DepthType"):
        hole.DepthType = enum_index(args.get("depth_type"), {"dimension": 0, "blind": 0, "through_all": 1, "through": 1}, "dimension", "depth_type")
    if hasattr(hole, "ThreadType"):
        thread_type = args.get("thread_type", 0)
        hole.ThreadType = 0 if str(thread_type).strip().lower() in {"", "none"} else int(thread_type)
    if hasattr(hole, "HoleCutType"):
        hole.HoleCutType = enum_index(args.get("hole_cut_type"), {"none": 0, "counterbore": 1, "countersink": 2}, "none", "hole_cut_type")
    if hasattr(hole, "DrillPoint"):
        hole.DrillPoint = enum_index(args.get("drill_point"), {"flat": 0, "none": 0, "angled": 1}, "flat", "drill_point")
    if hasattr(hole, "Tapered"):
        hole.Tapered = bool(args.get("tapered", False))
    optional_lengths = {
        "drill_point_angle": "DrillPointAngle",
        "tapered_angle": "TaperedAngle",
        "hole_cut_diameter": "HoleCutDiameter",
        "hole_cut_depth": "HoleCutDepth",
        "hole_cut_countersink_angle": "HoleCutCountersinkAngle",
    }
    for key, prop in optional_lengths.items():
        if args.get(key) is not None and hasattr(hole, prop):
            setattr(hole, prop, float(args[key]))


def resolve_partdesign_reference_axis(doc, sketch, args):
    object_name = args.get("reference_axis_object") or args.get("axis_object_name")
    if object_name:
        axis_obj = get_object(doc, object_name)
        subname = args.get("reference_axis_subname") or args.get("axis_subname") or ""
        return (axis_obj, [str(subname)] if subname else [""])
    raw = str(args.get("reference_axis") or args.get("axis") or "sketch_v_axis").strip().lower().replace("-", "_").replace(" ", "_")
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


def apply_revolved_parameters(doc, sketch, feature, args, *, is_groove):
    if hasattr(feature, "ReferenceAxis"):
        feature.ReferenceAxis = resolve_partdesign_reference_axis(doc, sketch, args)
    if hasattr(feature, "Type"):
        feature.Type = revolved_mode_index(args.get("mode") or args.get("revolution_type") or args.get("groove_type"), is_groove=is_groove)
    if hasattr(feature, "Angle"):
        feature.Angle = float(args.get("angle", 360.0))
    if args.get("angle2") is not None and hasattr(feature, "Angle2"):
        feature.Angle2 = float(args["angle2"])
    if args.get("midplane") is not None and hasattr(feature, "Midplane"):
        feature.Midplane = bool(args["midplane"])
    if args.get("reversed") is not None and hasattr(feature, "Reversed"):
        feature.Reversed = bool(args["reversed"])
    if args.get("up_to_face_object") is not None and hasattr(feature, "UpToFace"):
        face_obj = get_object(doc, args["up_to_face_object"])
        subname = args.get("up_to_face_subname") or ""
        feature.UpToFace = (face_obj, [str(subname)] if subname else [""])
    if args.get("fuse_order") is not None and hasattr(feature, "FuseOrder"):
        feature.FuseOrder = enum_index(args.get("fuse_order"), {"base_first": 0, "feature_first": 1}, "base_first", "fuse_order")


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


def resolve_partdesign_profile_link(doc, args):
    profile_name = args.get("profile_name") or args.get("profile_sketch") or args.get("sketch_name")
    if profile_name:
        subnames = args.get("profile_subnames")
        if subnames is None:
            subname = args.get("profile_subname")
            subnames = [subname] if subname else []
        if isinstance(subnames, str):
            subnames = [subnames] if subnames else []
        obj = get_object(doc, str(profile_name))
        return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj
    return partdesign_link_sub_value(doc, args.get("profile"))


def subnames_from_args(args, *, default_empty=False):
    for key in ("base_subnames", "subnames", "edge_names", "face_names"):
        value = args.get(key)
        if value is not None:
            if isinstance(value, str):
                return [value] if value else []
            return [str(item) for item in value if item]
    if args.get("edge_indices") is not None:
        return ["Edge" + str(int(index) + 1) for index in args.get("edge_indices") or []]
    if args.get("face_indices") is not None:
        return ["Face" + str(int(index) + 1) for index in args.get("face_indices") or []]
    for key in ("base_subname", "subname", "edge_name", "face_name"):
        value = args.get(key)
        if value:
            return [str(value)]
    return [""] if default_empty else []


def resolve_partdesign_base_link(doc, args, *, body=None, require_subnames=True, default_empty=False):
    base_name = args.get("base_feature_name") or args.get("base_name") or args.get("source_object") or args.get("feature_name")
    base_obj = object_or_doc_attr(doc, base_name) if base_name else None
    if body is None and base_obj is not None:
        body = find_body_for_object(base_obj)
    if body is None:
        body = find_single_partdesign_body(doc)
    if base_obj is None and body is not None:
        base_obj = find_body_solid_tip(body)
    if base_obj is None:
        raise ValueError("base_feature_name/base_name or a Body with a solid Tip is required")
    subnames = subnames_from_args(args, default_empty=default_empty)
    if require_subnames and not subnames:
        raise ValueError("base_subnames/edge_names/face_names, edge_indices/face_indices, or use_all_edges is required")
    return ((base_obj, subnames) if subnames else base_obj), base_obj, body


def resolve_doc_link(doc, args, *, keys, subname_keys=()):
    name = None
    for key in keys:
        if args.get(key):
            name = args.get(key)
            break
    if name is None:
        raise ValueError(keys[0] + " is required")
    obj = object_or_doc_attr(doc, name)
    subname = ""
    for key in subname_keys:
        if args.get(key):
            subname = str(args.get(key))
            break
    return (obj, [subname] if subname else [""])


def resolve_partdesign_section_links(doc, args):
    sections = args.get("sections")
    if sections is None:
        sections = args.get("section_names")
    if not sections:
        raise ValueError("sections or section_names is required")
    return [partdesign_link_sub_value(doc, item) for item in sections]


def resolve_partdesign_optional_section_links(doc, args):
    sections = args.get("sections")
    if sections is None:
        sections = args.get("section_names")
    if not sections:
        return []
    return [partdesign_link_sub_value(doc, item) for item in sections]


def resolve_partdesign_spine_link(doc, args):
    spine_name = args.get("spine_name") or args.get("spine_sketch") or args.get("path_name") or args.get("path_sketch")
    if spine_name:
        subnames = args.get("spine_subnames")
        if subnames is None:
            subname = args.get("spine_subname") or args.get("path_subname")
            subnames = [subname] if subname else []
        if isinstance(subnames, str):
            subnames = [subnames] if subnames else []
        obj = get_object(doc, str(spine_name))
        return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj
    spine = args.get("spine") or args.get("path")
    if spine is None:
        raise ValueError("spine_name, spine_sketch, path_name, or spine is required")
    return partdesign_link_sub_value(doc, spine)


def resolve_partdesign_auxiliary_spine_link(doc, args):
    spine_name = (
        args.get("auxiliary_spine_name")
        or args.get("auxiliary_spine_sketch")
        or args.get("aux_spine_name")
        or args.get("aux_spine_sketch")
        or args.get("auxiliary_path_name")
        or args.get("auxiliary_path_sketch")
    )
    if spine_name:
        subnames = args.get("auxiliary_spine_subnames") or args.get("aux_spine_subnames")
        if subnames is None:
            subname = args.get("auxiliary_spine_subname") or args.get("aux_spine_subname") or args.get("auxiliary_path_subname")
            subnames = [subname] if subname else []
        if isinstance(subnames, str):
            subnames = [subnames] if subnames else []
        obj = get_object(doc, str(spine_name))
        return (obj, [str(sub) for sub in subnames if sub]) if subnames else obj
    spine = args.get("auxiliary_spine") or args.get("auxiliary_path")
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


def pipe_arg(args, primary, *aliases):
    for key in (primary, *aliases):
        if args.get(key) is not None:
            return args.get(key)
    return None


def apply_pipe_parameters(pipe, args, *, has_auxiliary_spine=False, section_count=0):
    if args.get("spine_tangent") is not None and hasattr(pipe, "SpineTangent"):
        pipe.SpineTangent = bool(args["spine_tangent"])
    if pipe_arg(args, "auxiliary_spine_tangent", "aux_spine_tangent") is not None and hasattr(pipe, "AuxiliarySpineTangent"):
        pipe.AuxiliarySpineTangent = bool(pipe_arg(args, "auxiliary_spine_tangent", "aux_spine_tangent"))
    if pipe_arg(args, "auxiliary_curvilinear", "aux_curvilinear") is not None and hasattr(pipe, "AuxiliaryCurvilinear"):
        pipe.AuxiliaryCurvilinear = bool(pipe_arg(args, "auxiliary_curvilinear", "aux_curvilinear"))
    mode_value = pipe_arg(args, "mode", "orientation_mode")
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
    if args.get("transition") is not None and hasattr(pipe, "Transition"):
        pipe.Transition = partdesign_pipe_enum(
            args.get("transition"),
            {"transformed": 0, "right_corner": 1, "right": 1, "round_corner": 2, "round": 2},
            "transformed",
            "transition",
        )
    transformation_value = pipe_arg(args, "transformation", "scaling_mode")
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
    if args.get("binormal") is not None and hasattr(pipe, "Binormal"):
        pipe.Binormal = vector(args["binormal"])


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


def get_or_create_partdesign_body(doc, args, *, default_if_requested=True):
    requested = args.get("body_name")
    requested_partdesign = attachment_requested(args)
    if not requested and not requested_partdesign and not default_if_requested:
        return None, False
    body_name = str(requested or "Body")
    body = find_partdesign_body(doc, body_name)
    created = False
    create_if_missing = bool(args.get("create_body_if_missing", True))
    if body is None:
        if not create_if_missing:
            raise ValueError("PartDesign Body not found: " + body_name)
        body = doc.addObject("PartDesign::Body", body_name)
        created = True
    return body, created


def attach_sketch_to_partdesign_body(doc, sketch, args, *, body=None):
    requested = attachment_requested(args)
    target_requested = attachment_target_requested(args)
    if body is None:
        body = find_body_for_object(sketch)
    support_name = attachment_support_name(args)
    if body is None and support_name:
        support = get_object(doc, support_name)
        body = find_body_for_object(support)
    if body is None:
        if not requested:
            return {"attached": False, "body_created": False}
        body, created = get_or_create_partdesign_body(doc, args)
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
    support, subname, support_info = resolve_partdesign_attachment_support(doc, body, args)
    sketch.AttachmentSupport = [(support, subname)]
    sketch.MapMode = str(args.get("attachment_map_mode") or args.get("map_mode") or "FlatFace")
    offset_base = apply_attachment_offset(sketch, args)
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
    try:
        for key, value in (args.get("properties") or {}).items():
            prop = ensure_settable_property(obj, key)
            resolved = resolve_property_value(doc, value)
            setattr(obj, prop, resolved)
            changed[prop] = property_value_summary(resolved)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "changed": changed, "object": object_summary(obj), "document": document_summary(doc)}


def action_spreadsheet_create(args):
    doc = open_or_new(args)
    sheet_name = str(args.get("sheet_name") or "params")
    existing = doc.getObject(sheet_name)
    created = False
    if existing is None:
        doc.openTransaction("MCP create spreadsheet")
        try:
            sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
            created = True
            doc.commitTransaction()
        except Exception:
            doc.abortTransaction()
            raise
    else:
        sheet = existing
        if getattr(sheet, "TypeId", "") != "Spreadsheet::Sheet":
            raise ValueError("object exists but is not a Spreadsheet::Sheet: " + sheet_name)

    start_row = int(args.get("start_row") or 1)
    label_column = normalize_column(args.get("label_column"), "A")
    value_column = normalize_column(args.get("value_column"), "B")
    default_unit = normalize_unit(args.get("default_unit"), field_name="default_unit")
    require_units = bool(args.get("require_units", False))
    changed = []
    aliases = {}
    warnings = []
    doc.openTransaction("MCP update spreadsheet")
    try:
        for index, row in enumerate(args.get("rows") or []):
            row_number = int(row.get("row") or (start_row + index))
            label_cell = normalize_cell(row.get("label_cell") or (label_column + str(row_number)))
            value_cell = normalize_cell(row.get("value_cell") or row.get("cell") or (value_column + str(row_number)))
            if "label" in row:
                label_text = spreadsheet_value_text(row.get("label"))
                sheet.set(label_cell, label_text)
                changed.append({"cell": label_cell, "value": label_text})
            value_result = spreadsheet_cell_value_result(
                row.get("value"),
                default_unit=default_unit,
                require_units=require_units,
                spec=row,
                context=f"Spreadsheet row {row_number} value cell {value_cell}",
            )
            value_text = value_result["text"]
            sheet.set(value_cell, value_text)
            changed_item = {"cell": value_cell, "value": value_text}
            if value_result.get("display_unit"):
                sheet.setDisplayUnit(value_cell, value_result["display_unit"])
                changed_item["display_unit"] = value_result["display_unit"]
            if value_result.get("warning"):
                warnings.append(value_result["warning"])
            changed.append(changed_item)
            alias = normalize_alias(row.get("alias"))
            if alias:
                sheet.setAlias(value_cell, alias)
                aliases[alias] = value_cell
        for cell_spec in args.get("cells") or []:
            cell = normalize_cell(cell_spec.get("cell"))
            value_result = spreadsheet_cell_value_result(
                cell_spec.get("value"),
                default_unit=default_unit,
                require_units=require_units,
                spec=cell_spec,
                context=f"Spreadsheet cell {cell}",
            )
            value_text = value_result["text"]
            sheet.set(cell, value_text)
            changed_item = {"cell": cell, "value": value_text}
            if value_result.get("display_unit"):
                sheet.setDisplayUnit(cell, value_result["display_unit"])
                changed_item["display_unit"] = value_result["display_unit"]
            if value_result.get("warning"):
                warnings.append(value_result["warning"])
            changed.append(changed_item)
            alias = normalize_alias(cell_spec.get("alias"))
            if alias:
                sheet.setAlias(cell, alias)
                aliases[alias] = cell
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "created": created,
        "changed": changed,
        "aliases": aliases,
        "warnings": warnings,
        "sheet": spreadsheet_summary(sheet, cells=[item["cell"] for item in changed], aliases=list(aliases)),
        "document": document_summary(doc),
    }


def action_spreadsheet_get(args):
    doc = App.openDocument(args["document_path"])
    sheet = get_spreadsheet(doc, args["sheet_name"])
    return {
        "sheet": spreadsheet_summary(
            sheet,
            cells=args.get("cells") or [],
            aliases=args.get("aliases") or [],
            include_known_aliases=bool(args.get("include_known_aliases", True)),
        ),
        "document": {"name": doc.Name, "label": doc.Label, "file_name": doc.FileName},
    }


def action_object_expression_set(args):
    doc = App.openDocument(args["document_path"])
    obj = get_object(doc, args["object_name"])
    expressions = args.get("expressions") or {}
    if not isinstance(expressions, dict) or not expressions:
        raise ValueError("expressions must be a non-empty object")
    before = expression_summary(obj)
    applied = []
    doc.openTransaction("MCP set object expressions")
    try:
        for path, expression in expressions.items():
            path_text = str(path or "").strip()
            if not path_text or "\n" in path_text or "\r" in path_text:
                raise ValueError("invalid expression path: " + str(path))
            if expression is None or str(expression).strip() == "":
                obj.setExpression(path_text, None)
                applied.append({"path": path_text, "expression": None})
            else:
                obj.setExpression(path_text, str(expression))
                applied.append({"path": path_text, "expression": str(expression)})
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "object": object_summary(obj),
        "before": before,
        "after": expression_summary(obj),
        "applied": applied,
        "document": document_summary(doc),
    }


def action_object_expression_list(args):
    doc = App.openDocument(args["document_path"])
    if args.get("object_name"):
        objects = [get_object(doc, args["object_name"])]
    elif args.get("object_names"):
        objects = [get_object(doc, name) for name in args.get("object_names") or []]
    else:
        objects = list(doc.Objects)
    return {
        "objects": [
            {
                "object": {"name": obj.Name, "label": obj.Label, "type_id": obj.TypeId},
                "expressions": expression_summary(obj),
            }
            for obj in objects
        ],
        "document": {"name": doc.Name, "label": doc.Label, "file_name": doc.FileName},
    }


def action_object_rename_label(args):
    doc = App.openDocument(args["document_path"])
    obj = get_object_for_label_update(doc, args["object_name"])
    label = str(args.get("label") or "").strip()
    if not label:
        raise ValueError("label is required")
    if bool(args.get("require_unique", True)):
        ensure_unique_label(doc, obj, label)
    before = {"name": obj.Name, "label": obj.Label}
    doc.openTransaction("MCP rename object label")
    obj.Label = label
    doc.commitTransaction()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "before": before,
        "after": {"name": obj.Name, "label": obj.Label},
        "object": object_summary(obj),
        "document": document_summary(doc),
    }


def action_object_delete(args):
    doc = App.openDocument(args["document_path"])
    names = args.get("object_names") or [args["object_name"]]
    doc.openTransaction("MCP delete objects")
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
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "deleted": deleted, "tip_restorations": tip_restorations, "document": document_summary(doc)}


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


def uses_feature_extrude(args):
    mode = args.get("extrude_mode", "auto")
    if mode not in {"auto", "shape", "feature"}:
        raise ValueError("unsupported extrude_mode: " + str(mode))
    return mode == "feature" or any(key in args for key in FEATURE_EXTRUDE_KEYS)


def action_part_extrude_feature(doc, source, args):
    base_shape = source.Shape
    auto_solid = planar_face_from_closed_wires(base_shape) is not None
    result = doc.addObject("Part::Extrusion", args.get("result_name") or "Extrude")
    result.Base = source
    result.Dir = vector(args.get("vector"), [0, 0, 10])
    if args.get("dir_mode") is not None:
        result.DirMode = str(args["dir_mode"])
    if args.get("length_fwd") is not None:
        result.LengthFwd = float(args["length_fwd"])
    if args.get("length_rev") is not None:
        result.LengthRev = float(args["length_rev"])
    result.Solid = bool(args["solid"]) if "solid" in args else auto_solid
    if args.get("reversed") is not None:
        result.Reversed = bool(args["reversed"])
    if args.get("symmetric") is not None:
        result.Symmetric = bool(args["symmetric"])
    if args.get("taper_angle") is not None:
        result.TaperAngle = angle_degrees(args["taper_angle"])
    if args.get("taper_angle_rev") is not None:
        result.TaperAngleRev = angle_degrees(args["taper_angle_rev"])
    if args.get("face_maker_mode") is not None:
        result.FaceMakerMode = str(args["face_maker_mode"])
    if args.get("inner_wire_taper") is not None:
        result.InnerWireTaper = str(args["inner_wire_taper"])
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


def action_part_extrude(args):
    doc = App.openDocument(args["document_path"])
    source = get_object(doc, args["source_object"])
    doc.openTransaction("MCP part extrude")
    try:
        if uses_feature_extrude(args):
            result, feature_parameters = action_part_extrude_feature(doc, source, args)
            mode = "feature"
        else:
            base_shape = source.Shape
            face = planar_face_from_closed_wires(base_shape)
            extrude_source = face if face is not None else base_shape
            mode = "face_from_closed_wire" if face is not None else "shape"
            shape = extrude_source.extrude(vector(args.get("vector"), [0, 0, 10]))
            result = doc.addObject("Part::Feature", args.get("result_name") or "Extrude")
            result.Shape = shape
            feature_parameters = None
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "mode": mode,
        "feature_parameters": feature_parameters,
        "object": object_summary(result),
        "document": document_summary(doc),
    }


def action_partdesign_body_create(args):
    doc = open_or_new(args)
    doc.openTransaction("MCP create PartDesign body")
    try:
        body, created = get_or_create_partdesign_body(doc, args)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "created": created,
        "body": object_summary(body),
        "document": document_summary(doc),
    }


def action_partdesign_datum_plane_create(args):
    doc = open_or_new(args)
    doc.openTransaction("MCP create PartDesign datum plane")
    try:
        body, body_created = get_or_create_partdesign_body(doc, args)
        previous_tip = getattr(body, "Tip", None)
        datum = doc.addObject("PartDesign::Plane", args.get("datum_plane_name") or args.get("plane_name") or args.get("result_name") or "DatumPlane")
        body.addObject(datum)
        support_args = dict(args)
        support_args.pop("datum_plane_name", None)
        support, subname, attachment = resolve_partdesign_attachment_support(doc, body, support_args)
        datum.AttachmentSupport = [(support, subname)]
        datum.MapMode = str(args.get("attachment_map_mode") or args.get("map_mode") or "FlatFace")
        offset_base = apply_attachment_offset(datum, args)
        if previous_tip is not None and getattr(previous_tip, "Name", None) != getattr(datum, "Name", None):
            body.Tip = previous_tip
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_valid", True)) and "Invalid" in list(getattr(datum, "State", []) or []):
        raise ValueError("PartDesign datum plane is invalid: " + str(getattr(datum, "State", [])))
    saved = save_if_requested(doc, args)
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


def action_partdesign_pad(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(sketch)
    attachment = None
    doc.openTransaction("MCP create PartDesign pad")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, args)
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args, body=body)
        pad = doc.addObject("PartDesign::Pad", args.get("pad_name") or args.get("result_name") or "Pad")
        body.addObject(pad)
        pad.Profile = sketch
        if hasattr(pad, "Length"):
            pad.Length = float(args.get("length", args.get("length_fwd", 10.0)))
        if args.get("length2") is not None and hasattr(pad, "Length2"):
            pad.Length2 = float(args["length2"])
        if args.get("midplane") is not None and hasattr(pad, "Midplane"):
            pad.Midplane = bool(args["midplane"])
        if args.get("reversed") is not None and hasattr(pad, "Reversed"):
            pad.Reversed = bool(args["reversed"])
        body.Tip = pad
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(pad, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Pad did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "pad": object_summary(pad),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_pocket(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(sketch)
    attachment = None
    doc.openTransaction("MCP create PartDesign pocket")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, args)
        # Pocket removes material, so the Body must already contain a solid
        # feature (e.g. a Pad) for it to cut into.
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError("PartDesign Pocket requires an existing solid feature in the Body (create a Pad first)")
        body.Tip = solid_tip
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args, body=body)
        pocket = doc.addObject("PartDesign::Pocket", args.get("pocket_name") or args.get("result_name") or "Pocket")
        body.addObject(pocket)
        pocket.Profile = sketch
        if hasattr(pocket, "Length"):
            pocket.Length = float(args.get("length", args.get("length_fwd", 10.0)))
        if args.get("length2") is not None and hasattr(pocket, "Length2"):
            pocket.Length2 = float(args["length2"])
        if args.get("midplane") is not None and hasattr(pocket, "Midplane"):
            pocket.Midplane = bool(args["midplane"])
        if args.get("reversed") is not None and hasattr(pocket, "Reversed"):
            pocket.Reversed = bool(args["reversed"])
        body.Tip = pocket
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(pocket, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Pocket did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "pocket": object_summary(pocket),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_hole(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(sketch)
    attachment = None
    doc.openTransaction("MCP create PartDesign hole")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, args)
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError("PartDesign Hole requires an existing solid feature in the Body (create a Pad first)")
        body.Tip = solid_tip
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args, body=body)
        hole = doc.addObject("PartDesign::Hole", args.get("hole_name") or args.get("result_name") or "Hole")
        body.addObject(hole)
        hole.Profile = sketch
        apply_hole_parameters(hole, args)
        body.Tip = hole
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(hole, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Hole did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "hole": object_summary(hole),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_revolution(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(sketch)
    attachment = None
    doc.openTransaction("MCP create PartDesign revolution")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, args)
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args, body=body)
        revolution = doc.addObject("PartDesign::Revolution", args.get("revolution_name") or args.get("result_name") or "Revolution")
        body.addObject(revolution)
        revolution.Profile = sketch
        apply_revolved_parameters(doc, sketch, revolution, args, is_groove=False)
        body.Tip = revolution
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(revolution, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Revolution did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "revolution": object_summary(revolution),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_groove(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    if getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("sketch_name must reference a Sketcher::SketchObject")
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(sketch)
    attachment = None
    doc.openTransaction("MCP create PartDesign groove")
    try:
        if body is None:
            body, _ = get_or_create_partdesign_body(doc, args)
        solid_tip = find_body_solid_tip(body)
        if solid_tip is None:
            raise ValueError("PartDesign Groove requires an existing solid feature in the Body (create a Pad first)")
        body.Tip = solid_tip
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args, body=body)
        groove = doc.addObject("PartDesign::Groove", args.get("groove_name") or args.get("result_name") or "Groove")
        body.addObject(groove)
        groove.Profile = sketch
        apply_revolved_parameters(doc, sketch, groove, args, is_groove=True)
        body.Tip = groove
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(groove, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError("PartDesign Groove did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "sketch": object_summary(sketch),
        "groove": object_summary(groove),
        "attachment": attachment,
        "document": document_summary(doc),
    }


def action_partdesign_loft(doc, args, *, feature_type, default_name, transaction_name, require_base_solid=False):
    profile_link = resolve_partdesign_profile_link(doc, args)
    section_links = resolve_partdesign_section_links(doc, args)
    profile_obj = link_target_object(profile_link)
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(profile_obj)
    doc.openTransaction(transaction_name)
    try:
        if body is None:
            if require_base_solid:
                raise ValueError("PartDesign Subtractive Loft requires an existing Body solid")
            body, _ = get_or_create_partdesign_body(doc, args)
        ensure_partdesign_body_member(body, profile_obj)
        for section_link in section_links:
            ensure_partdesign_body_member(body, link_target_object(section_link))
        if require_base_solid:
            solid_tip = find_body_solid_tip(body)
            if solid_tip is None:
                raise ValueError("PartDesign Subtractive Loft requires an existing Body solid")
            body.Tip = solid_tip
        loft = doc.addObject(feature_type, args.get("loft_name") or args.get("result_name") or default_name)
        body.addObject(loft)
        loft.Profile = profile_link
        loft.Sections = section_links
        if args.get("ruled") is not None and hasattr(loft, "Ruled"):
            loft.Ruled = bool(args["ruled"])
        if args.get("closed") is not None and hasattr(loft, "Closed"):
            loft.Closed = bool(args["closed"])
        body.Tip = loft
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(loft, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "profile": object_summary(profile_obj),
        "sections": [object_summary(link_target_object(item)) for item in section_links],
        "loft": object_summary(loft),
        "document": document_summary(doc),
    }


def action_partdesign_additive_loft(args):
    doc = App.openDocument(args["document_path"])
    return action_partdesign_loft(
        doc,
        args,
        feature_type="PartDesign::AdditiveLoft",
        default_name="AdditiveLoft",
        transaction_name="MCP create PartDesign additive loft",
    )


def action_partdesign_subtractive_loft(args):
    doc = App.openDocument(args["document_path"])
    return action_partdesign_loft(
        doc,
        args,
        feature_type="PartDesign::SubtractiveLoft",
        default_name="SubtractiveLoft",
        transaction_name="MCP create PartDesign subtractive loft",
        require_base_solid=True,
    )


def action_partdesign_pipe(doc, args, *, feature_type, default_name, transaction_name, require_base_solid=False):
    profile_link = resolve_partdesign_profile_link(doc, args)
    spine_link = resolve_partdesign_spine_link(doc, args)
    auxiliary_spine_link = resolve_partdesign_auxiliary_spine_link(doc, args)
    section_links = resolve_partdesign_optional_section_links(doc, args)
    profile_obj = link_target_object(profile_link)
    spine_obj = link_target_object(spine_link)
    auxiliary_spine_obj = link_target_object(auxiliary_spine_link) if auxiliary_spine_link is not None else None
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else find_body_for_object(profile_obj)
    doc.openTransaction(transaction_name)
    try:
        if body is None:
            if require_base_solid:
                raise ValueError(f"{default_name} requires an existing Body solid")
            body, _ = get_or_create_partdesign_body(doc, args)
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
        pipe = doc.addObject(feature_type, args.get("pipe_name") or args.get("result_name") or default_name)
        body.addObject(pipe)
        pipe.Profile = profile_link
        pipe.Spine = spine_link
        if auxiliary_spine_link is not None:
            pipe.AuxiliarySpine = auxiliary_spine_link
        if section_links:
            pipe.Sections = section_links
        apply_pipe_parameters(pipe, args, has_auxiliary_spine=auxiliary_spine_link is not None, section_count=len(section_links))
        body.Tip = pipe
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(pipe, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_if_requested(doc, args)
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


def action_partdesign_additive_pipe(args):
    doc = App.openDocument(args["document_path"])
    return action_partdesign_pipe(
        doc,
        args,
        feature_type="PartDesign::AdditivePipe",
        default_name="AdditivePipe",
        transaction_name="MCP create PartDesign additive pipe",
    )


def action_partdesign_subtractive_pipe(args):
    doc = App.openDocument(args["document_path"])
    return action_partdesign_pipe(
        doc,
        args,
        feature_type="PartDesign::SubtractivePipe",
        default_name="SubtractivePipe",
        transaction_name="MCP create PartDesign subtractive pipe",
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


def action_partdesign_dressup(doc, args, *, feature_type, default_name, transaction_name, apply_parameters, use_all_edges=False, require_subnames=True):
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else None
    base_link, base_obj, body = resolve_partdesign_base_link(
        doc,
        args,
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
        feature = doc.addObject(feature_type, args.get("dressup_name") or args.get("result_name") or args.get(default_name.lower() + "_name") or default_name)
        feature.Base = base_link
        apply_parameters(feature, args)
        body.addObject(feature)
        body.Tip = feature
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(feature, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "base": object_summary(base_obj),
        "dressup": object_summary(feature),
        "document": document_summary(doc),
    }


def action_partdesign_fillet(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "Radius"):
            feature.Radius = float(params.get("radius", 1.0))
        if hasattr(feature, "UseAllEdges"):
            feature.UseAllEdges = bool(params.get("use_all_edges", False))
        if params.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(params["support_transform"])

    return action_partdesign_dressup(
        doc,
        args,
        feature_type="PartDesign::Fillet",
        default_name="Fillet",
        transaction_name="MCP create PartDesign fillet",
        apply_parameters=apply,
        use_all_edges=bool(args.get("use_all_edges", False)),
    )


def action_partdesign_chamfer(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "ChamferType"):
            feature.ChamferType = chamfer_type_index(params.get("chamfer_type"))
        if hasattr(feature, "Size"):
            feature.Size = float(params.get("size", params.get("distance", 1.0)))
        if params.get("size2") is not None and hasattr(feature, "Size2"):
            feature.Size2 = float(params["size2"])
        if params.get("angle") is not None and hasattr(feature, "Angle"):
            feature.Angle = float(params["angle"])
        if params.get("flip_direction") is not None and hasattr(feature, "FlipDirection"):
            feature.FlipDirection = bool(params["flip_direction"])
        if hasattr(feature, "UseAllEdges"):
            feature.UseAllEdges = bool(params.get("use_all_edges", False))
        if params.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(params["support_transform"])

    return action_partdesign_dressup(
        doc,
        args,
        feature_type="PartDesign::Chamfer",
        default_name="Chamfer",
        transaction_name="MCP create PartDesign chamfer",
        apply_parameters=apply,
        use_all_edges=bool(args.get("use_all_edges", False)),
    )


def action_partdesign_thickness(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "Value"):
            feature.Value = float(params.get("value", params.get("thickness", 1.0)))
        if hasattr(feature, "Mode"):
            feature.Mode = thickness_mode_index(params.get("mode"))
        if hasattr(feature, "Join"):
            feature.Join = thickness_join_index(params.get("join"))
        if params.get("reversed") is not None and hasattr(feature, "Reversed"):
            feature.Reversed = bool(params["reversed"])
        if params.get("intersection") is not None and hasattr(feature, "Intersection"):
            feature.Intersection = bool(params["intersection"])
        if params.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(params["support_transform"])

    return action_partdesign_dressup(
        doc,
        args,
        feature_type="PartDesign::Thickness",
        default_name="Thickness",
        transaction_name="MCP create PartDesign thickness",
        apply_parameters=apply,
    )


def action_partdesign_draft(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "NeutralPlane"):
            feature.NeutralPlane = resolve_doc_link(
                doc,
                params,
                keys=("neutral_plane_name", "neutral_plane_object", "neutral_plane"),
                subname_keys=("neutral_plane_subname",),
            )
        if hasattr(feature, "PullDirection"):
            feature.PullDirection = resolve_doc_link(
                doc,
                params,
                keys=("pull_direction_name", "pull_direction_object", "pull_direction"),
                subname_keys=("pull_direction_subname",),
            )
        if hasattr(feature, "Angle"):
            feature.Angle = float(params.get("angle", 5.0))
        if params.get("reversed") is not None and hasattr(feature, "Reversed"):
            feature.Reversed = bool(params["reversed"])
        if params.get("support_transform") is not None and hasattr(feature, "SupportTransform"):
            feature.SupportTransform = bool(params["support_transform"])

    return action_partdesign_dressup(
        doc,
        args,
        feature_type="PartDesign::Draft",
        default_name="Draft",
        transaction_name="MCP create PartDesign draft",
        apply_parameters=apply,
    )


def first_present(args, *keys):
    for key in keys:
        value = args.get(key)
        if value is not None and value != "":
            return value
    return None


def list_arg(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(item) for item in value if item]


def transform_original_names(args):
    for key in ("original_names", "feature_names", "features", "originals"):
        values = list_arg(args.get(key))
        if values:
            return values
    name = first_present(args, "original_feature_name", "feature_name", "base_feature_name", "source_object")
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


def resolve_transform_link(doc, args, *, keys, subname_keys=(), default_name=None, default_subname=""):
    name = first_present(args, *keys)
    if name is None:
        if default_name is None:
            return None
        name = default_name
    name = canonical_reference_name(name, default_name or name)
    obj = object_or_doc_attr(doc, name)
    subname = first_present(args, *subname_keys) or default_subname
    return (obj, [str(subname)] if subname else [""])


def pattern_mode_index(value):
    return enum_index(value, {"extent": 0, "overall_length": 0, "length": 0, "spacing": 1, "offset": 1}, "extent", "mode")


def action_partdesign_transform(doc, args, *, feature_type, default_name, transaction_name, apply_parameters, name_keys):
    whole_shape = bool(args.get("whole_shape", False) or str(args.get("transform_mode", "")).strip().lower().replace("-", "_").replace(" ", "_") in {"whole_shape", "whole"})
    body = find_partdesign_body(doc, args.get("body_name")) if args.get("body_name") else None
    originals = []
    if not whole_shape:
        original_names = transform_original_names(args)
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
        transform = doc.addObject(feature_type, first_present(args, *name_keys, "result_name") or default_name)
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
        apply_parameters(transform, args)
        body.Tip = transform
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    if bool(args.get("require_solid", True)):
        shape = getattr(transform, "Shape", None)
        solid_count = len(shape.Solids) if shape is not None and not shape.isNull() else 0
        if solid_count < 1:
            raise ValueError(f"{default_name} did not produce a solid")
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "body": object_summary(body),
        "originals": [object_summary(item) for item in originals],
        "transform": object_summary(transform),
        "document": document_summary(doc),
    }


def action_partdesign_linear_pattern(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "Direction"):
            feature.Direction = resolve_transform_link(
                doc,
                params,
                keys=("direction_name", "direction_object", "direction_axis"),
                subname_keys=("direction_subname",),
                default_name="X_Axis",
            )
        if hasattr(feature, "Reversed") and params.get("reversed") is not None:
            feature.Reversed = bool(params["reversed"])
        if hasattr(feature, "Mode"):
            feature.Mode = pattern_mode_index(params.get("mode"))
        if hasattr(feature, "Length"):
            feature.Length = float(params.get("length", 10.0))
        if params.get("offset") is not None and hasattr(feature, "Offset"):
            feature.Offset = float(params["offset"])
        if hasattr(feature, "Occurrences"):
            feature.Occurrences = int(params.get("occurrences", 2))
        occurrences2 = int(params.get("occurrences2", 1))
        second_direction = resolve_transform_link(
            doc,
            params,
            keys=("direction2_name", "direction2_object", "direction2_axis", "second_direction_name", "second_direction_object", "second_direction_axis"),
            subname_keys=("direction2_subname", "second_direction_subname"),
            default_name="Y_Axis" if occurrences2 > 1 else None,
        )
        if second_direction is not None and hasattr(feature, "Direction2"):
            feature.Direction2 = second_direction
        if hasattr(feature, "Reversed2") and params.get("reversed2") is not None:
            feature.Reversed2 = bool(params["reversed2"])
        if hasattr(feature, "Mode2"):
            feature.Mode2 = pattern_mode_index(params.get("mode2"))
        if hasattr(feature, "Length2"):
            feature.Length2 = float(params.get("length2", 10.0))
        if params.get("offset2") is not None and hasattr(feature, "Offset2"):
            feature.Offset2 = float(params["offset2"])
        if hasattr(feature, "Occurrences2"):
            feature.Occurrences2 = occurrences2

    return action_partdesign_transform(
        doc,
        args,
        feature_type="PartDesign::LinearPattern",
        default_name="LinearPattern",
        transaction_name="MCP create PartDesign linear pattern",
        apply_parameters=apply,
        name_keys=("linear_pattern_name", "pattern_name", "transform_name"),
    )


def action_partdesign_polar_pattern(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "Axis"):
            feature.Axis = resolve_transform_link(
                doc,
                params,
                keys=("axis_name", "axis_object", "axis"),
                subname_keys=("axis_subname",),
                default_name="Z_Axis",
            )
        if hasattr(feature, "Reversed") and params.get("reversed") is not None:
            feature.Reversed = bool(params["reversed"])
        if hasattr(feature, "Mode"):
            feature.Mode = pattern_mode_index(params.get("mode"))
        if hasattr(feature, "Angle"):
            feature.Angle = float(params.get("angle", 360.0))
        if params.get("offset") is not None and hasattr(feature, "Offset"):
            feature.Offset = float(params["offset"])
        if hasattr(feature, "Occurrences"):
            feature.Occurrences = int(params.get("occurrences", 3))

    return action_partdesign_transform(
        doc,
        args,
        feature_type="PartDesign::PolarPattern",
        default_name="PolarPattern",
        transaction_name="MCP create PartDesign polar pattern",
        apply_parameters=apply,
        name_keys=("polar_pattern_name", "pattern_name", "transform_name"),
    )


def action_partdesign_mirrored(args):
    doc = App.openDocument(args["document_path"])

    def apply(feature, params):
        if hasattr(feature, "MirrorPlane"):
            feature.MirrorPlane = resolve_transform_link(
                doc,
                params,
                keys=("mirror_plane_name", "mirror_plane_object", "mirror_plane"),
                subname_keys=("mirror_plane_subname",),
                default_name="XY_Plane",
            )

    return action_partdesign_transform(
        doc,
        args,
        feature_type="PartDesign::Mirrored",
        default_name="Mirrored",
        transaction_name="MCP create PartDesign mirrored",
        apply_parameters=apply,
        name_keys=("mirrored_name", "mirror_name", "transform_name"),
    )


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
    try:
        sketch = doc.addObject("Sketcher::SketchObject", args.get("sketch_name") or "Sketch")
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "sketch": object_summary(sketch), "attachment": attachment, "document": document_summary(doc)}


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


def validate_sketch_profile(sketch, args):
    precision = int(args.get("endpoint_key_precision", 6))
    micro_offset_tolerance = float(args.get("micro_offset_tolerance", 0.05))
    forbid_isolated_points = bool(args.get("forbid_isolated_points", True))
    forbid_branch_points = bool(args.get("forbid_branch_points", True))
    forbid_micro_offsets = bool(args.get("forbid_micro_offsets", True))
    require_pad_ready = bool(args.get("require_pad_ready", True))
    require_fully_constrained = bool(args.get("require_fully_constrained", False))
    forbid_block_constraints = bool(args.get("forbid_block_constraints", False)) or profile_constraint_policy({}, args) == "semantic"
    include_construction = bool(args.get("include_construction", False))

    solve_code = sketch.solve()
    try:
        sketch.Document.recompute()
    except Exception:
        pass
    face_validation = wire_face_validation(sketch.Shape)
    geometry_summary = sketch_geometry_type_summary(sketch, include_construction=include_construction)
    geometry_counts = geometry_summary["counts"]
    required_types = normalized_profile_segment_set(args.get("required_segment_types")) | normalized_profile_segment_set(args.get("required_curve_types"))
    minimum_curve_segments = int(args.get("minimum_curve_segments", 0) or 0)
    forbid_all_line_loops = bool(args.get("forbid_all_line_loops", False))
    forbid_polyline_fallback = bool(args.get("forbid_polyline_fallback", False))
    expected_geometry_reports, intent_mismatches = validate_expected_geometry_intents(sketch, args)
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
    block_constraints = [
        constraint_summary(constraint, index)
        for index, constraint in enumerate(getattr(sketch, "Constraints", []) or [])
        if str(getattr(constraint, "Type", "")) == "Block"
    ]
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
    if forbid_block_constraints and block_constraints:
        issues.append({"code": "block_constraints_forbidden", "indices": [item["index"] for item in block_constraints]})
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
    failing_intent_mismatches = [item for item in intent_mismatches if item.get("fallback_policy") == "fail" or bool(args.get("forbid_intent_mismatch", False))]
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
        "block_constraints": block_constraints,
        "face_validation": face_validation,
    }


PROFILE_RECTANGLE_TYPES = {
    "rectangle",
    "rectangle_corner",
    "rectangle_corners",
    "rectangle_2_point",
    "rectangle_two_points",
    "rectangle_center",
    "center_rectangle",
    "rectangle_3_point",
    "rectangle_three_points",
}

NAMED_POLYGON_SIDES = {
    "triangle": 3,
    "equilateral_triangle": 3,
    "square": 4,
    "pentagon": 5,
    "hexagon": 6,
    "heptagon": 7,
    "octagon": 8,
}


def line_segments_from_points(points, *, closed=True):
    segments = []
    for index in range(len(points) - 1):
        segments.append({"type": "line", "start": point_list(points[index]), "end": point_list(points[index + 1])})
    if closed and points:
        segments.append({"type": "line", "start": point_list(points[-1]), "end": point_list(points[0])})
    return segments


def rectangle_loop_points(loop):
    kind = str(loop.get("type") or "").lower()
    if kind in {"rectangle_center", "center_rectangle"} or loop.get("center") is not None:
        center = vector(loop.get("center"), [0, 0, 0])
        width = float(loop["width"])
        height = float(loop["height"])
        c1 = App.Vector(center.x - width / 2.0, center.y - height / 2.0, center.z)
        c2 = App.Vector(center.x + width / 2.0, center.y + height / 2.0, center.z)
        return [c1, App.Vector(c2.x, c1.y, c1.z), c2, App.Vector(c1.x, c2.y, c1.z)]
    if kind in {"rectangle_3_point", "rectangle_three_points"}:
        points_input = loop.get("points") or [loop["point1"], loop["point2"], loop["point3"]]
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
        return [p1, p2, p2 + normal * height, p1 + normal * height]
    if loop.get("corner1") is not None and loop.get("corner2") is not None:
        c1 = vector(loop["corner1"])
        c2 = vector(loop["corner2"])
    else:
        c1 = vector(loop.get("origin"), [0, 0, 0])
        c2 = App.Vector(c1.x + float(loop["width"]), c1.y + float(loop["height"]), c1.z)
    return [c1, App.Vector(c2.x, c1.y, c1.z), c2, App.Vector(c1.x, c2.y, c1.z)]


def regular_polygon_loop_info(loop):
    kind = str(loop.get("type") or "").lower()
    if kind in NAMED_POLYGON_SIDES:
        sides = NAMED_POLYGON_SIDES[kind]
    else:
        sides = int(loop["sides"])
    if sides < 3:
        raise ValueError("regular_polygon requires sides >= 3")
    center = vector(loop.get("center"), [0, 0, 0])
    corner_value = None
    for corner_key in ("corner", "first_corner", "firstCornerPoint", "first_corner_point", "corner_point"):
        if loop.get(corner_key) is not None:
            corner_value = loop[corner_key]
            break
    if corner_value is not None:
        first_corner = vector(corner_value)
        diff = App.Vector(first_corner.x - center.x, first_corner.y - center.y, 0)
        radius = float(diff.Length)
        if radius <= 1e-12:
            raise ValueError("regular_polygon requires distinct center and corner")
    else:
        radius = float(loop["radius"])
        if radius <= 1e-12:
            raise ValueError("regular_polygon requires radius > 0")
        start = angle_radians(loop.get("start_angle"), 0.0)
        diff = App.Vector(radius * math.cos(start), radius * math.sin(start), 0)
    points = [
        App.Vector(
            center.x + math.cos(2 * math.pi * idx / sides) * diff.x - math.sin(2 * math.pi * idx / sides) * diff.y,
            center.y + math.cos(2 * math.pi * idx / sides) * diff.y + math.sin(2 * math.pi * idx / sides) * diff.x,
            center.z,
        )
        for idx in range(sides)
    ]
    return {"sides": sides, "center": center, "radius": radius, "points": points}


def slot_loop_segments(loop):
    radius = float(loop["radius"])
    kind = str(loop.get("type") or "").lower()
    if kind in {"slot_start_end_radius", "slot_2_point", "slot_two_points"} or loop.get("start"):
        left = vector(loop.get("start") or loop.get("point1"))
        right = vector(loop.get("end") or loop.get("point2"))
    else:
        center = vector(loop.get("center"), [0, 0, 0])
        length = float(loop["length"])
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
    return [
        {"type": "line", "start": point_list(top_left), "end": point_list(top_right)},
        {"type": "arc_3_point", "start": point_list(top_right), "mid": point_list(right + unit * radius), "end": point_list(bottom_right)},
        {"type": "line", "start": point_list(bottom_right), "end": point_list(bottom_left)},
        {"type": "arc_3_point", "start": point_list(bottom_left), "mid": point_list(left - unit * radius), "end": point_list(top_left)},
    ]


def keyhole_loop_info(loop):
    center = vector(loop.get("circle_center") or loop.get("center"), [0, 0, 0])
    circle_radius = float(loop.get("circle_radius", loop.get("head_radius", loop.get("radius"))))
    if loop.get("slot_radius") is not None:
        slot_radius = float(loop["slot_radius"])
    elif loop.get("neck_radius") is not None:
        slot_radius = float(loop["neck_radius"])
    elif loop.get("slot_width") is not None:
        slot_radius = float(loop["slot_width"]) / 2.0
    elif loop.get("width") is not None:
        slot_radius = float(loop["width"]) / 2.0
    else:
        raise ValueError("keyhole requires slot_radius or slot_width")
    slot_end = vector(loop.get("slot_end") or loop.get("end"))
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
    return {
        "center": center,
        "circle_radius": circle_radius,
        "slot_radius": slot_radius,
        "slot_end": slot_end,
        "unit": unit,
        "normal": normal,
        "transition": transition,
    }


def keyhole_loop_segments(loop):
    info = keyhole_loop_info(loop)
    center = info["center"]
    circle_radius = info["circle_radius"]
    slot_radius = info["slot_radius"]
    slot_end = info["slot_end"]
    unit = info["unit"]
    normal = info["normal"]
    transition = info["transition"]
    top_near = center + unit * transition + normal * slot_radius
    bottom_near = center + unit * transition - normal * slot_radius
    top_far = slot_end + normal * slot_radius
    bottom_far = slot_end - normal * slot_radius
    far_mid = slot_end + unit * slot_radius
    circle_mid = center - unit * circle_radius
    return [
        {"type": "line", "start": point_list(top_near), "end": point_list(top_far)},
        {"type": "arc_3_point", "start": point_list(top_far), "mid": point_list(far_mid), "end": point_list(bottom_far)},
        {"type": "line", "start": point_list(bottom_far), "end": point_list(bottom_near)},
        {"type": "arc_3_point", "start": point_list(bottom_near), "mid": point_list(circle_mid), "end": point_list(top_near)},
    ]


def profile_loop_segments(loop):
    segments = loop.get("segments") or loop.get("geometry") or []
    if segments:
        return segments
    kind = str(loop.get("type") or "").lower()
    if kind in PROFILE_RECTANGLE_TYPES:
        return line_segments_from_points(rectangle_loop_points(loop), closed=True)
    if kind == "polyline" and loop.get("points"):
        return line_segments_from_points([vector(point) for point in loop["points"]], closed=bool(loop.get("closed", True)))
    if kind in NAMED_POLYGON_SIDES or kind == "regular_polygon":
        return line_segments_from_points(regular_polygon_loop_info(loop)["points"], closed=True)
    if kind in {"circle", "circle_profile"}:
        center = vector(loop.get("center"), [0, 0, 0])
        return [
            {
                "type": "circle",
                "center": point_list(center),
                "normal": loop.get("normal", [0, 0, 1]),
                "radius": float(loop["radius"]),
            }
        ]
    if kind in {"slot", "slot_center_length_radius", "slot_start_end_radius", "slot_2_point", "slot_two_points"}:
        return slot_loop_segments(loop)
    if kind in {"keyhole", "circle_slot_union", "slot_circle_union"}:
        return keyhole_loop_segments(loop)
    return []


def profile_constraint_policy(loop, params):
    if bool(loop.get("semantic_constraints", False)) or bool(params.get("semantic_constraints", False)):
        return "semantic"
    value = loop.get("constraint_policy", params.get("constraint_policy", "none"))
    if value is None:
        return "none"
    normalized = str(value).lower().replace("-", "_")
    aliases = {
        "off": "none",
        "false": "none",
        "minimal": "none",
        "shape_only": "shape",
        "parametric": "semantic",
        "strict": "semantic",
        "strict_parametric": "semantic",
        "semantic_parametric": "semantic",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"none", "shape", "semantic"}:
        raise ValueError("unsupported constraint_policy: " + str(value))
    return normalized


def sanitized_constraint_name(value):
    text = re.sub(r"[^0-9A-Za-z_]+", "_", str(value or "")).strip("_")
    if not text:
        return ""
    if text[0].isdigit():
        text = "_" + text
    return text


def semantic_constraint_name(loop, role, default_loop_name):
    for key in (role + "_constraint_name", role + "_name"):
        if loop.get(key):
            return sanitized_constraint_name(loop[key])
    prefix = sanitized_constraint_name(loop.get("name") or default_loop_name or "loop")
    return sanitized_constraint_name(prefix + "_" + role)


def add_semantic_constraint(sketch, constraint, *, role, loop, loop_name, expression=None):
    index = sketch.addConstraint(constraint)
    name = semantic_constraint_name(loop, role, loop_name)
    if name:
        try:
            sketch.renameConstraint(index, name)
        except Exception:
            name = ""
    report = {
        "index": index,
        "type": str(getattr(constraint, "Type", "")),
        "role": role,
    }
    if name:
        report["name"] = name
    if expression:
        report["expression"] = str(expression)
    return index, report


def add_rectangle_semantic_constraints(sketch, loop, params, *, loop_name, added):
    import Sketcher

    policy = profile_constraint_policy(loop, params)
    if policy == "none":
        return []
    if len(added) < 4:
        return []
    kind = str(loop.get("type") or "").lower()
    if kind not in PROFILE_RECTANGLE_TYPES:
        return []

    semantic = []
    axis_aligned = kind not in {"rectangle_3_point", "rectangle_three_points"}
    if axis_aligned:
        for role, constraint in (
            ("horizontal_bottom", Sketcher.Constraint("Horizontal", added[0])),
            ("vertical_right", Sketcher.Constraint("Vertical", added[1])),
            ("horizontal_top", Sketcher.Constraint("Horizontal", added[2])),
            ("vertical_left", Sketcher.Constraint("Vertical", added[3])),
        ):
            _, report = add_semantic_constraint(sketch, constraint, role=role, loop=loop, loop_name=loop_name)
            semantic.append(report)
    else:
        for role, constraint in (
            ("parallel_width", Sketcher.Constraint("Parallel", added[0], added[2])),
            ("parallel_height", Sketcher.Constraint("Parallel", added[1], added[3])),
            ("perpendicular_corner", Sketcher.Constraint("Perpendicular", added[0], added[1])),
        ):
            _, report = add_semantic_constraint(sketch, constraint, role=role, loop=loop, loop_name=loop_name)
            semantic.append(report)

    if policy != "semantic" or not axis_aligned:
        return semantic

    points = rectangle_loop_points(loop)
    width = abs(points[1].x - points[0].x)
    height = abs(points[2].y - points[1].y)
    for role, expression, constraint in (
        ("width", loop.get("width_expression"), Sketcher.Constraint("DistanceX", added[0], 1, added[0], 2, width)),
        ("height", loop.get("height_expression"), Sketcher.Constraint("DistanceY", added[1], 1, added[1], 2, height)),
    ):
        _, report = add_semantic_constraint(
            sketch,
            constraint,
            role=role,
            loop=loop,
            loop_name=loop_name,
            expression=expression,
        )
        semantic.append(report)

    anchor_default = loop.get("origin") is not None or loop.get("corner1") is not None
    anchor = bool(loop.get("anchor", params.get("anchor", anchor_default)))
    if anchor:
        origin = points[0]
        for role, expression, constraint in (
            ("origin_x", loop.get("origin_x_expression"), Sketcher.Constraint("DistanceX", added[0], 1, -2, 1, -float(origin.x))),
            ("origin_y", loop.get("origin_y_expression"), Sketcher.Constraint("DistanceY", added[0], 1, -1, 1, -float(origin.y))),
        ):
            _, report = add_semantic_constraint(
                sketch,
                constraint,
                role=role,
                loop=loop,
                loop_name=loop_name,
                expression=expression,
            )
            semantic.append(report)
    return semantic


def transformed_expression(expression, transform):
    if expression is None or str(expression).strip() == "":
        return None
    text = str(expression)
    if transform == "diameter_to_radius":
        return "(" + text + ") / 2"
    if transform == "hex_across_flats_to_radius":
        return "(" + text + ") / sqrt(3)"
    return text


def loop_expression(loop, keys):
    for key, transform in keys:
        if loop.get(key) is not None:
            return transformed_expression(loop.get(key), transform)
    return None


def add_regular_polygon_semantic_constraints(sketch, loop, params, *, loop_name, added):
    import Part
    import Sketcher

    policy = profile_constraint_policy(loop, params)
    if policy == "none":
        return []
    kind = str(loop.get("type") or "").lower()
    if kind not in NAMED_POLYGON_SIDES and kind != "regular_polygon":
        return []
    info = regular_polygon_loop_info(loop)
    sides = int(info["sides"])
    line_indices = list(added[:sides])
    if len(line_indices) < sides:
        return []

    semantic = []
    if bool(loop.get("equal_edges", True)):
        for idx in range(1, len(line_indices)):
            _, report = add_semantic_constraint(
                sketch,
                Sketcher.Constraint("Equal", line_indices[0], line_indices[idx]),
                role="equal_edge_" + str(idx),
                loop=loop,
                loop_name=loop_name,
            )
            semantic.append(report)

    expression_keys = [
        ("radius_expression", None),
        ("corner_radius_expression", None),
        ("diameter_expression", "diameter_to_radius"),
    ]
    if sides == 6:
        expression_keys.append(("across_flats_expression", "hex_across_flats_to_radius"))
    radius_expression = loop_expression(loop, expression_keys)
    need_circle = bool(loop.get("construction_circle", True)) or policy == "semantic" or radius_expression is not None
    circle_idx = None
    if need_circle:
        circle_idx = sketch.addGeometry(Part.Circle(info["center"], vector(loop.get("normal"), [0, 0, 1]), float(info["radius"])), True)
        added.append(circle_idx)
        if bool(loop.get("point_on_circle", True)):
            for line_idx in line_indices:
                _, report = add_semantic_constraint(
                    sketch,
                    Sketcher.Constraint("PointOnObject", line_idx, 2, circle_idx),
                    role="vertex_on_circle",
                    loop=loop,
                    loop_name=loop_name,
                )
                semantic.append(report)

    if policy == "semantic":
        if circle_idx is None:
            circle_idx = sketch.addGeometry(Part.Circle(info["center"], vector(loop.get("normal"), [0, 0, 1]), float(info["radius"])), True)
            added.append(circle_idx)
        _, report = add_semantic_constraint(
            sketch,
            Sketcher.Constraint("Radius", circle_idx, float(info["radius"])),
            role="radius",
            loop=loop,
            loop_name=loop_name,
            expression=radius_expression,
        )
        semantic.append(report)

        anchor_default = loop.get("center") is not None
        anchor = bool(loop.get("anchor", params.get("anchor", anchor_default)))
        if anchor:
            center = info["center"]
            for role, expression, constraint in (
                ("center_x", loop.get("center_x_expression"), Sketcher.Constraint("DistanceX", circle_idx, 3, -2, 1, -float(center.x))),
                ("center_y", loop.get("center_y_expression"), Sketcher.Constraint("DistanceY", circle_idx, 3, -1, 1, -float(center.y))),
            ):
                _, report = add_semantic_constraint(
                    sketch,
                    constraint,
                    role=role,
                    loop=loop,
                    loop_name=loop_name,
                    expression=expression,
                )
                semantic.append(report)

        if bool(loop.get("fix_orientation", True)) and line_indices:
            p0 = info["points"][0]
            p1 = info["points"][1]
            edge_angle = math.atan2(float(p1.y - p0.y), float(p1.x - p0.x))
            _, report = add_semantic_constraint(
                sketch,
                Sketcher.Constraint("Angle", line_indices[0], edge_angle),
                role="orientation",
                loop=loop,
                loop_name=loop_name,
                expression=loop.get("orientation_expression") or loop.get("angle_expression"),
            )
            semantic.append(report)

    return semantic


def add_circle_semantic_constraints(sketch, loop, params, *, loop_name, added):
    import Sketcher

    policy = profile_constraint_policy(loop, params)
    if policy == "none":
        return []
    kind = str(loop.get("type") or "").lower()
    if kind not in {"circle", "circle_profile"} or not added:
        return []
    radius = float(loop["radius"])
    expression = loop_expression(
        loop,
        [
            ("radius_expression", None),
            ("diameter_expression", "diameter_to_radius"),
        ],
    )
    semantic = []
    _, report = add_semantic_constraint(
        sketch,
        Sketcher.Constraint("Radius", added[0], radius),
        role="radius",
        loop=loop,
        loop_name=loop_name,
        expression=expression if policy == "semantic" else None,
    )
    semantic.append(report)
    if policy == "semantic" and (loop.get("center") is not None or bool(loop.get("anchor", False))):
        center = vector(loop.get("center"), [0, 0, 0])
        for role, expression, constraint in (
            ("center_x", loop.get("center_x_expression"), Sketcher.Constraint("DistanceX", added[0], 3, -2, 1, -float(center.x))),
            ("center_y", loop.get("center_y_expression"), Sketcher.Constraint("DistanceY", added[0], 3, -1, 1, -float(center.y))),
        ):
            _, report = add_semantic_constraint(
                sketch,
                constraint,
                role=role,
                loop=loop,
                loop_name=loop_name,
                expression=expression,
            )
            semantic.append(report)
    return semantic


def add_slot_semantic_constraints(sketch, loop, params, *, loop_name, added):
    import Sketcher

    policy = profile_constraint_policy(loop, params)
    if policy == "none":
        return []
    kind = str(loop.get("type") or "").lower()
    if kind not in {"slot", "slot_center_length_radius", "slot_start_end_radius", "slot_2_point", "slot_two_points"} or len(added) < 4:
        return []
    radius = float(loop["radius"])
    expression = loop_expression(loop, [("radius_expression", None), ("slot_radius_expression", None), ("slot_width_expression", "diameter_to_radius")])
    semantic = []
    for role, geometry_index in (("slot_radius_1", added[1]), ("slot_radius_2", added[3])):
        _, report = add_semantic_constraint(
            sketch,
            Sketcher.Constraint("Radius", geometry_index, radius),
            role=role,
            loop=loop,
            loop_name=loop_name,
            expression=expression if policy == "semantic" and role == "slot_radius_1" else None,
        )
        semantic.append(report)
    return semantic


def add_keyhole_semantic_constraints(sketch, loop, params, *, loop_name, added):
    import Sketcher

    policy = profile_constraint_policy(loop, params)
    if policy == "none":
        return []
    kind = str(loop.get("type") or "").lower()
    if kind not in {"keyhole", "circle_slot_union", "slot_circle_union"} or len(added) < 4:
        return []
    info = keyhole_loop_info(loop)
    slot_expression = loop_expression(loop, [("slot_radius_expression", None), ("neck_radius_expression", None), ("slot_width_expression", "diameter_to_radius")])
    circle_expression = loop_expression(loop, [("circle_radius_expression", None), ("head_radius_expression", None), ("radius_expression", None), ("circle_diameter_expression", "diameter_to_radius")])
    semantic = []
    for role, geometry_index, radius, expression in (
        ("slot_radius", added[1], float(info["slot_radius"]), slot_expression),
        ("circle_radius", added[3], float(info["circle_radius"]), circle_expression),
    ):
        _, report = add_semantic_constraint(
            sketch,
            Sketcher.Constraint("Radius", geometry_index, radius),
            role=role,
            loop=loop,
            loop_name=loop_name,
            expression=expression if policy == "semantic" else None,
        )
        semantic.append(report)
    return semantic


def add_profile_helper_semantic_constraints(sketch, loop, params, *, loop_name, added):
    semantic = []
    for helper in (
        add_rectangle_semantic_constraints,
        add_regular_polygon_semantic_constraints,
        add_circle_semantic_constraints,
        add_slot_semantic_constraints,
        add_keyhole_semantic_constraints,
    ):
        semantic.extend(helper(sketch, loop, params, loop_name=loop_name, added=added))
    return semantic


def make_sketch_profile_loop(sketch, loop, params, *, loop_index, endpoint_tolerance):
    import Sketcher

    name = str(loop.get("name") or ("loop_" + str(loop_index)))
    construction = bool(loop.get("construction", False))
    segments = profile_loop_segments(loop)
    if not segments:
        raise ValueError("profile loop has no segments or supported profile type: " + name)
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
    semantic_constraints = add_profile_helper_semantic_constraints(sketch, loop, params, loop_name=name, added=added)
    constraint_indices.extend([item["index"] for item in semantic_constraints])
    return {
        "name": name,
        "added_indices": added,
        "constraint_indices": constraint_indices,
        "semantic_constraints": semantic_constraints,
        "segment_count": len(flat),
        "curve_contract": curve_contract,
        "segment_intents": segment_intents,
        "segment_intent_mismatches": segment_intent_mismatches,
        "geometry_reports": geometry_reports,
    }


def gaussian_solve_3x3(matrix, vector_values):
    rows = [list(matrix[index]) + [float(vector_values[index])] for index in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(rows[row][col]))
        if abs(rows[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        for item in range(col, 4):
            rows[col][item] /= divisor
        for row in range(3):
            if row == col:
                continue
            factor = rows[row][col]
            for item in range(col, 4):
                rows[row][item] -= factor * rows[col][item]
    return [rows[index][3] for index in range(3)]


def point2d_list(points):
    values = []
    for point in points:
        if len(point) < 2:
            raise ValueError("points must contain at least x/y values")
        values.append((float(point[0]), float(point[1])))
    if len(values) < 2:
        raise ValueError("at least two points are required")
    return values


def error_stats(errors):
    if not errors:
        return {"rms_error": None, "max_error": None}
    rms = math.sqrt(sum(error * error for error in errors) / len(errors))
    return {"rms_error": rms, "max_error": max(abs(error) for error in errors)}


def fit_line_2d(points):
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    xx = sum((point[0] - cx) * (point[0] - cx) for point in points)
    xy = sum((point[0] - cx) * (point[1] - cy) for point in points)
    yy = sum((point[1] - cy) * (point[1] - cy) for point in points)
    angle = 0.5 * math.atan2(2 * xy, xx - yy) if (xx or yy or xy) else 0.0
    dx = math.cos(angle)
    dy = math.sin(angle)
    errors = [abs(dx * (point[1] - cy) - dy * (point[0] - cx)) for point in points]
    result = {
        "ok": True,
        "point": [cx, cy],
        "direction": [dx, dy],
    }
    result.update(error_stats(errors))
    return result


def fit_arc_2d(points):
    if len(points) < 3:
        return {"ok": False, "error": "at least three points are required for arc fit"}
    sx = sum(point[0] for point in points)
    sy = sum(point[1] for point in points)
    s1 = float(len(points))
    sxx = sum(point[0] * point[0] for point in points)
    syy = sum(point[1] * point[1] for point in points)
    sxy = sum(point[0] * point[1] for point in points)
    rhs = [-(sum((point[0] * point[0] + point[1] * point[1]) * point[0] for point in points)), -(sum((point[0] * point[0] + point[1] * point[1]) * point[1] for point in points)), -(sxx + syy)]
    solution = gaussian_solve_3x3([[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, s1]], rhs)
    if solution is None:
        return {"ok": False, "error": "circle fit matrix is singular"}
    a, b, c = solution
    center_x = -a / 2.0
    center_y = -b / 2.0
    radius_sq = center_x * center_x + center_y * center_y - c
    if radius_sq <= 0:
        return {"ok": False, "error": "circle fit produced a non-positive radius"}
    radius = math.sqrt(radius_sq)
    radial_errors = [abs(math.hypot(point[0] - center_x, point[1] - center_y) - radius) for point in points]
    angles = [math.atan2(point[1] - center_y, point[0] - center_x) for point in points]
    unwrapped = [angles[0]]
    for angle in angles[1:]:
        previous = unwrapped[-1]
        while angle - previous > math.pi:
            angle -= 2 * math.pi
        while angle - previous < -math.pi:
            angle += 2 * math.pi
        unwrapped.append(angle)
    result = {
        "ok": True,
        "center": [center_x, center_y],
        "radius": radius,
        "angle_span_degrees": abs(math.degrees(unwrapped[-1] - unwrapped[0])),
    }
    result.update(error_stats(radial_errors))
    return result


def analyze_curve_fit(args):
    points = point2d_list(args.get("points") or [])
    tolerance = float(args.get("tolerance", args.get("fit_tolerance", 0.1)))
    line = fit_line_2d(points)
    arc = fit_arc_2d(points)
    if line["max_error"] is not None and line["max_error"] <= tolerance:
        recommendation = "line"
        reason = "line fit is within tolerance"
    elif arc.get("ok") and arc.get("max_error") is not None and arc["max_error"] <= tolerance:
        recommendation = "arc"
        reason = "arc fit is within tolerance and preserves native circular geometry"
    else:
        recommendation = "bspline"
        reason = "line/arc fits exceed tolerance; use a freeform curve instead of pretending it is circular"

    # Image-to-sketch guidance: rather than silently committing to one curve type,
    # flag when the trace is genuinely ambiguous so the caller can ask the user or
    # request a tighter reference instead of degrading curve intent.
    line_error = line.get("max_error")
    arc_error = arc.get("max_error") if arc.get("ok") else None
    candidates = []
    if line_error is not None and line_error <= tolerance:
        candidates.append("line")
    if arc_error is not None and arc_error <= tolerance:
        candidates.append("arc")
    fit_errors = [error for error in (line_error, arc_error) if error is not None]
    best_error = min(fit_errors) if fit_errors else None

    ambiguous = False
    ambiguity_reasons = []
    if (
        recommendation == "line"
        and line_error is not None
        and arc_error is not None
        and arc_error < line_error * 0.5
        and line_error > tolerance * 0.5
    ):
        ambiguous = True
        ambiguity_reasons.append("line only just fits but a circular arc fits markedly better; the trace may be a gentle arc")
    if recommendation == "bspline" and arc_error is not None and arc_error <= tolerance * 2.0:
        ambiguous = True
        ambiguity_reasons.append("no fit is within tolerance but a circular arc is close; could be an arc or a freeform B-spline")
    if best_error is not None and tolerance * 0.5 < best_error <= tolerance:
        ambiguous = True
        ambiguity_reasons.append("best fit error is near the tolerance; the curve type is borderline")

    if ambiguous:
        confidence = "low"
    elif best_error is not None and best_error <= tolerance * 0.5:
        confidence = "high"
    else:
        confidence = "medium"

    decision = {
        "action": "ask_user" if ambiguous else "use_recommendation",
        "recommended": recommendation,
    }
    if ambiguous:
        options = list(dict.fromkeys(candidates + [recommendation, "arc", "bspline"]))
        decision["options"] = options
        decision["reasons"] = ambiguity_reasons
        decision["question"] = (
            "The traced curve is ambiguous between "
            + "/".join(options)
            + ". Which native geometry should be used? Choose to preserve curve "
            "intent instead of falling back silently."
        )

    return {
        "point_count": len(points),
        "tolerance": tolerance,
        "recommendation": recommendation,
        "reason": reason,
        "line_fit": line,
        "arc_fit": arc,
        "candidates": candidates,
        "best_error": best_error,
        "ambiguous": ambiguous,
        "confidence": confidence,
        "decision": decision,
        "bspline_interpolation": {
            "ok": len(points) >= 2,
            "interpolation_residual": 0.0,
            "note": "B-spline can interpolate the submitted trace points; prefer line/arc when their fit error is inside tolerance.",
        },
    }


def sketch_geometry_method_catalog():
    return {
        "geometry_methods": [
            {
                "geometry": "point",
                "native_type": "Part.Point",
                "methods": [
                    {"type": "point", "fields": ["point"]},
                    {"type": "point", "fields": ["position"]},
                ],
            },
            {
                "geometry": "line",
                "native_type": "Part.LineSegment",
                "methods": [
                    {"type": "line", "fields": ["start", "end"]},
                    {"type": "line_start_end", "fields": ["start", "end"]},
                    {"type": "line_angle_length", "fields": ["start", "angle", "length"]},
                ],
            },
            {
                "geometry": "circle",
                "native_type": "Part.Circle",
                "methods": [
                    {"type": "circle", "fields": ["center", "radius"], "optional": ["normal"]},
                    {"type": "circle_center_radius", "fields": ["center", "radius"], "optional": ["normal"]},
                    {"type": "circle_3_point", "fields": ["points"]},
                    {"type": "circle_by_3_points", "fields": ["point1", "point2", "point3"]},
                ],
            },
            {
                "geometry": "arc",
                "native_type": "Part.ArcOfCircle",
                "result_report": ["actual_start", "actual_end", "center", "radius", "sweep_deg", "normal"],
                "methods": [
                    {"type": "arc", "fields": ["center", "radius", "start_angle", "end_angle"], "optional": ["normal", "direction", "sweep"]},
                    {"type": "arc_of_circle", "fields": ["center", "radius", "start_angle", "end_angle"], "optional": ["normal", "direction", "sweep"]},
                    {"type": "arc_center_angles", "fields": ["center", "radius", "start_angle", "end_angle"], "optional": ["direction"]},
                    {"type": "arc_3_point", "fields": ["start", "mid", "end"]},
                    {"type": "arc_3_point", "fields": ["points"]},
                    {"type": "arc_start_mid_end", "fields": ["start", "mid", "end"]},
                    {"type": "arc_start_end_radius", "fields": ["start", "end", "radius", "side", "sweep"], "side_semantics": "arc midpoint side relative to directed start-end chord"},
                ],
            },
            {
                "geometry": "ellipse",
                "native_type": "Part.Ellipse",
                "methods": [
                    {"type": "ellipse", "fields": ["center", "major_radius", "minor_radius"]},
                    {"type": "ellipse", "fields": ["major_point", "minor_point", "center"]},
                ],
            },
            {
                "geometry": "ellipse_arc",
                "native_type": "Part.ArcOfEllipse",
                "methods": [
                    {"type": "ellipse_arc", "fields": ["center", "major_radius", "minor_radius", "start_angle", "end_angle"]},
                    {"type": "arc_of_ellipse", "fields": ["major_point", "minor_point", "center", "start_angle", "end_angle"]},
                ],
            },
            {
                "geometry": "conic_arc",
                "native_type": "Part.ArcOfHyperbola / Part.ArcOfParabola",
                "methods": [
                    {"type": "hyperbola_arc", "fields": ["center", "major_radius", "minor_radius", "start_angle", "end_angle"]},
                    {"type": "arc_of_hyperbola", "fields": ["major_point", "minor_point", "center", "start_angle", "end_angle"]},
                    {"type": "parabola_arc", "fields": ["start_angle", "end_angle"], "optional": ["point1", "point2", "center"]},
                    {"type": "arc_of_parabola", "fields": ["start_angle", "end_angle"], "optional": ["point1", "point2", "center"]},
                ],
            },
            {
                "geometry": "bspline",
                "native_type": "Part.BSplineCurve",
                "methods": [
                    {"type": "bspline", "fields": ["poles"], "optional": ["periodic"]},
                    {"type": "bspline", "fields": ["points", "interpolate"], "optional": ["periodic"]},
                    {"type": "b_spline", "fields": ["poles"], "optional": ["periodic"]},
                ],
            },
            {
                "geometry": "polyline",
                "native_type": "Part.LineSegment list",
                "methods": [
                    {"type": "polyline", "fields": ["points"], "optional": ["closed"]},
                ],
            },
        ],
        "profile_methods": [
            {
                "profile": "rectangle",
                "methods": [
                    {"type": "rectangle", "fields": ["origin", "width", "height"]},
                    {"type": "rectangle", "fields": ["corner1", "corner2"]},
                    {"type": "rectangle_center", "fields": ["center", "width", "height"]},
                    {"type": "rectangle_3_point", "fields": ["point1", "point2", "point3"]},
                ],
            },
            {
                "profile": "regular_polygon",
                "methods": [
                    {"type": "regular_polygon", "fields": ["center", "corner", "sides"], "optional": ["construction_circle"]},
                    {"type": "regular_polygon", "fields": ["center", "radius", "sides"], "optional": ["start_angle", "construction_circle"]},
                    {"type": "triangle", "fields": ["center", "corner"], "optional": ["construction_circle"]},
                    {"type": "triangle", "fields": ["center", "radius"], "optional": ["start_angle", "construction_circle"]},
                    {"type": "square", "fields": ["center", "corner"], "optional": ["construction_circle"]},
                    {"type": "square", "fields": ["center", "radius"], "optional": ["start_angle", "construction_circle"]},
                    {"type": "pentagon", "fields": ["center", "corner"], "optional": ["construction_circle"]},
                    {"type": "pentagon", "fields": ["center", "radius"], "optional": ["start_angle", "construction_circle"]},
                    {"type": "hexagon", "fields": ["center", "corner"], "optional": ["construction_circle"]},
                    {"type": "hexagon", "fields": ["center", "radius"], "optional": ["start_angle", "construction_circle"]},
                    {"type": "heptagon", "fields": ["center", "corner"], "optional": ["construction_circle"]},
                    {"type": "heptagon", "fields": ["center", "radius"], "optional": ["start_angle", "construction_circle"]},
                    {"type": "octagon", "fields": ["center", "corner"], "optional": ["construction_circle"]},
                    {"type": "octagon", "fields": ["center", "radius"], "optional": ["start_angle", "construction_circle"]},
                ],
            },
            {"profile": "circle", "methods": [{"fields": ["center", "radius"], "optional": ["radius_constraint"]}]},
            {
                "profile": "slot",
                "methods": [
                    {"type": "slot", "fields": ["center", "length", "radius"]},
                    {"type": "slot_start_end_radius", "fields": ["start", "end", "radius"]},
                    {"type": "arc_slot", "fields": ["center", "radius", "width", "start_angle", "end_angle"], "optional": ["direction", "sweep"]},
                    {"type": "keyhole", "fields": ["circle_center", "circle_radius", "slot_end", "slot_radius"]},
                ],
            },
            {"profile": "polyline", "methods": [{"fields": ["points"], "optional": ["closed"]}]},
        ],
        "constraint_methods": [
            {
                "constraint": "coincident",
                "type": "Coincident",
                "fields": ["first", "first_pos", "second", "second_pos"],
                "use": "Connect two geometry endpoints or points.",
            },
            {
                "constraint": "point_on_object",
                "type": "PointOnObject",
                "fields": ["first", "first_pos", "second"],
                "use": "Constrain a point to lie on another sketch geometry.",
            },
            {"constraint": "horizontal", "type": "Horizontal", "fields": ["first"], "use": "Make a line or point pair horizontal."},
            {"constraint": "vertical", "type": "Vertical", "fields": ["first"], "use": "Make a line or point pair vertical."},
            {"constraint": "parallel", "type": "Parallel", "fields": ["first", "second"], "use": "Keep two lines parallel."},
            {"constraint": "perpendicular", "type": "Perpendicular", "fields": ["first", "second"], "use": "Keep two geometries perpendicular."},
            {
                "constraint": "tangent",
                "type": "Tangent",
                "fields": ["first", "first_pos", "second", "second_pos"],
                "alternate_fields": ["first", "second"],
                "use": "Keep arcs/circles/lines tangent; endpoint positions may be provided when needed.",
            },
            {"constraint": "equal", "type": "Equal", "fields": ["first", "second"], "use": "Make lengths or radii equal."},
            {
                "constraint": "symmetric",
                "type": "Symmetric",
                "fields": ["first", "first_pos", "second", "second_pos", "third"],
                "use": "Constrain two points symmetric about a line or reference geometry.",
            },
            {"constraint": "distance", "type": "Distance", "fields": ["first", "value"], "metadata": ["name", "datum", "driving"]},
            {"constraint": "distance_x", "type": "DistanceX", "fields": ["first", "first_pos", "second", "second_pos", "value"], "metadata": ["name", "datum", "driving"]},
            {"constraint": "distance_y", "type": "DistanceY", "fields": ["first", "first_pos", "second", "second_pos", "value"], "metadata": ["name", "datum", "driving"]},
            {"constraint": "radius", "type": "Radius", "fields": ["first", "value"], "metadata": ["name", "datum", "driving"]},
            {"constraint": "diameter", "type": "Diameter", "fields": ["first", "value"], "metadata": ["name", "datum", "driving"]},
            {"constraint": "angle", "type": "Angle", "fields": ["first", "value"], "metadata": ["name", "datum", "driving"]},
            {"constraint": "lock", "type": "Lock", "fields": ["first"], "use": "Lock a geometry point/position when explicitly requested."},
            {"constraint": "block", "type": "Block", "fields": ["first"], "use": "Available but discouraged for parametric profiles; semantic policy rejects Block shortcuts."},
        ],
        "constraint_constructor": {
            "tool": "freecad_sketch_add_constraint",
            "call_shape": "Sketcher.Constraint(type, *values)",
            "constructor_passthrough": True,
            "value_fields_order": ["first", "first_pos", "second", "second_pos", "third", "third_pos", "value"],
            "metadata_fields": ["name", "datum", "driving", "active", "virtual_space", "visible", "label_position"],
            "blocked_types": ["Group", "Text"],
            "note": "The typed tool passes the provided type string to FreeCAD's Sketcher.Constraint constructor except for blocked unsafe/crashy types. The catalog lists the common CAD-safe constructor strings agents should prefer.",
        },
        "transform_generated_geometry": [
            {"operation": "fillet", "creates": "arc", "fields": ["radius"], "note": "Creates circular fillet/chamfer geometry between existing sketch elements."},
            {"operation": "convert_to_nurbs", "creates": "bspline", "note": "Converts supported geometry to NURBS/B-spline representation."},
        ],
        "analysis_tools": [
            {"tool": "freecad_curve_fit_analyze", "use": "Choose line, arc, or B-spline from traced points before creating geometry."},
            {"tool": "freecad_sketch_profile_validate", "use": "Verify native geometry type counts and declared intent after creation."},
        ],
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


def action_sketch_add_geometry(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    items = args.get("geometry") or []
    connect_sequence = bool(args.get("connect_sequence", False))
    close_sequence = bool(args.get("close_sequence", False))
    require_closed = bool(args.get("require_closed", False))
    closed_validation = None
    doc.openTransaction("MCP add sketch geometry")
    added, constraint_indices, geometry_reports = add_sketch_geometry_batch(
        sketch,
        items,
        connect_sequence=connect_sequence,
        close_sequence=close_sequence,
    )
    if require_closed:
        closed_validation = sketch_closed_validation(sketch)
        if closed_validation["open_vertices"]:
            doc.abortTransaction()
            raise ValueError("sketch geometry sequence is not closed; open vertices: " + str(closed_validation["open_vertices"]))
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
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


def action_sketch_profile_create(args):
    import Sketcher

    doc = open_or_new(args)
    sketch_name = args.get("sketch_name") or "ProfileSketch"
    sketch = doc.getObject(sketch_name)
    doc.openTransaction("MCP create sketch profile")
    try:
        if sketch is None:
            sketch = doc.addObject("Sketcher::SketchObject", sketch_name)
        elif bool(args.get("replace_existing", False)):
            sketch.deleteAllConstraints()
            sketch.deleteAllGeometry()
        attachment = attach_sketch_to_partdesign_body(doc, sketch, args)
        loops = args.get("loops") or []
        if not loops:
            raise ValueError("loops is required")
        endpoint_tolerance = float(args.get("endpoint_tolerance", 1e-6))
        loop_reports = []
        all_added = []
        all_constraints = []
        all_geometry_reports = []
        for index, loop in enumerate(loops):
            report = make_sketch_profile_loop(sketch, loop, args, loop_index=index, endpoint_tolerance=endpoint_tolerance)
            loop_reports.append(report)
            all_added.extend(report["added_indices"])
            all_constraints.extend(report["constraint_indices"])
            all_geometry_reports.extend(report["geometry_reports"])
        block_indices = []
        lock_mode = str(args.get("lock_mode", "none"))
        if lock_mode not in {"none", "block"}:
            raise ValueError("unsupported lock_mode: " + lock_mode)
        if lock_mode == "block":
            for geometry_index in all_added:
                block_indices.append(sketch.addConstraint(Sketcher.Constraint("Block", geometry_index)))
        doc.recompute()
        validation = validate_sketch_profile(sketch, args)
        if bool(args.get("require_valid", True)) and not validation["ok"]:
            raise ValueError("sketch profile validation failed: " + str(validation["issues"]))
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
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


def action_sketch_profile_validate(args):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    validation = validate_sketch_profile(sketch, args)
    return {"sketch": object_summary(sketch), "validation": validation, "document": document_summary(doc)}


def action_curve_fit_analyze(args):
    return {"analysis": analyze_curve_fit(args)}


def action_sketch_geometry_method_catalog(args):
    return sketch_geometry_method_catalog()


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


def sketch_external_references(args):
    references = []
    for item in args.get("references") or []:
        object_name = item.get("object_name") or args.get("object_name")
        sub_name = item.get("sub_name") or item.get("subname")
        if not object_name or not sub_name:
            raise ValueError("each external reference requires object_name and sub_name")
        references.append({"object_name": str(object_name), "sub_name": str(sub_name)})

    object_name = args.get("object_name")
    sub_names = list(args.get("sub_names") or [])
    if args.get("sub_name") is not None:
        sub_names.append(args.get("sub_name"))
    for sub_name in sub_names:
        if not object_name:
            raise ValueError("object_name is required when using sub_name/sub_names")
        references.append({"object_name": str(object_name), "sub_name": str(sub_name)})

    if not references:
        raise ValueError("at least one external reference is required")
    return references


def action_sketch_external_reference(args, *, intersection):
    doc = App.openDocument(args["document_path"])
    sketch = get_object(doc, args["sketch_name"])
    references = sketch_external_references(args)
    reports = []
    doc.openTransaction("MCP add sketch external reference")
    for reference in references:
        sketch.addExternal(
            reference["object_name"],
            reference["sub_name"],
            bool(args.get("defining", False)),
            bool(intersection),
        )
        reports.append({"object_name": reference["object_name"], "sub_name": reference["sub_name"]})
    doc.commitTransaction()
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "mode": "intersection" if intersection else "projection",
        "reports": reports,
        "sketch": object_summary(sketch),
        "document": document_summary(doc),
    }


def action_sketch_external_projection(args):
    return action_sketch_external_reference(args, intersection=False)


def action_sketch_external_intersection(args):
    return action_sketch_external_reference(args, intersection=True)


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
    dof = getattr(sketch, "DoF", getattr(sketch, "DegreesOfFreedom", None))
    result = {
        "sketch": object_summary(sketch),
        "geometry_count": len(sketch.Geometry),
        "constraint_count": len(sketch.Constraints),
        "degrees_of_freedom": dof,
        "fully_constrained": fully_constrained_from_dof(dof),
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
    if bool(args.get("include_geometry", True)):
        result["geometry"] = [geometry_summary(sketch, geo, idx) for idx, geo in enumerate(sketch.Geometry)]
    if bool(args.get("include_constraints", True)):
        result["constraints"] = [constraint_summary(constraint, idx) for idx, constraint in enumerate(sketch.Constraints)]
    if bool(args.get("include_semantic_groups", True)):
        result["semantic_groups"] = sketch_semantic_groups(sketch)
    result["evidence_source"] = "native_sketcher"
    return result


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
        "techdraw_page_export": [".dxf"],
        "cam_path_export": [".gcode", ".nc", ".ngc", ".tap", ".txt"],
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
        saved = save_if_requested(doc, args)
        return {"saved_path": saved, "reports": reports, "document": document_summary(doc)}
    doc.openTransaction("MCP mesh repair")
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
                replacement = doc.addObject("Mesh::Feature", args.get("result_name") or (obj.Name + "_Repaired"))
                replacement.Mesh = mesh
                assigned_to = replacement.Name
        reports.append({"object": obj.Name, "assigned_to": assigned_to, "actions": done, "errors": errors, "mutated": bool(done)})
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


def action_techdraw_page_create(args):
    doc = open_or_new(args)
    page_name = args.get("page_name") or "Page"
    template_name = args.get("template_name") or (page_name + "Template")
    doc.openTransaction("MCP create TechDraw page")
    try:
        page = doc.addObject("TechDraw::DrawPage", page_name)
        template = doc.addObject("TechDraw::DrawSVGTemplate", template_name)
        if args.get("template_path"):
            template.Template = args["template_path"]
        page.Template = template
        if args.get("scale") is not None:
            page.Scale = float(args["scale"])
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "page": object_summary(page),
        "template": object_summary(template),
        "document": document_summary(doc),
    }


def action_techdraw_view_create(args):
    doc = App.openDocument(args["document_path"])
    page = get_object(doc, args["page_name"])
    source_names = args.get("source_objects") or args.get("object_names") or []
    if not source_names:
        raise ValueError("source_objects must contain at least one object")
    sources = [get_object(doc, name) for name in source_names]
    view_name = args.get("view_name") or "View"
    doc.openTransaction("MCP create TechDraw view")
    try:
        view = doc.addObject("TechDraw::DrawViewPart", view_name)
        view.Source = sources
        if args.get("direction") is not None:
            view.Direction = vector(args["direction"])
        if args.get("x_direction") is not None:
            view.XDirection = vector(args["x_direction"])
        if args.get("scale") is not None:
            view.Scale = float(args["scale"])
        if args.get("x") is not None:
            view.X = float(args["x"])
        if args.get("y") is not None:
            view.Y = float(args["y"])
        page.addView(view)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "page": object_summary(page),
        "view": object_summary(view),
        "document": document_summary(doc),
    }


def action_techdraw_inspect(args):
    doc = App.openDocument(args["document_path"])
    pages = [
        obj
        for obj in doc.Objects
        if getattr(obj, "TypeId", "") == "TechDraw::DrawPage"
        and (not args.get("page_name") or obj.Name == args.get("page_name") or obj.Label == args.get("page_name"))
    ]
    views = [obj for obj in doc.Objects if str(getattr(obj, "TypeId", "")).startswith("TechDraw::DrawView")]
    return {
        "pages": [object_summary(page) for page in pages],
        "views": [object_summary(view) for view in views],
        "page_count": len(pages),
        "view_count": len(views),
        "document": document_summary(doc),
    }


def action_techdraw_page_export(args):
    import TechDraw

    doc = App.openDocument(args["document_path"])
    page = get_object(doc, args["page_name"])
    output = safe_output_path(args["output_path"], args)
    if os.path.exists(output) and not bool(args.get("overwrite", False)):
        raise ValueError("output exists; pass overwrite=true: " + output)
    export_format = (args.get("format") or os.path.splitext(output)[1].lstrip(".") or "dxf").lower()
    if export_format != "dxf" or os.path.splitext(output)[1].lower() != ".dxf":
        raise ValueError("headless TechDraw page export currently supports DXF output only")
    TechDraw.writeDXFPage(page, output)
    return {
        "exported_path": output,
        "format": "dxf",
        "page": object_summary(page),
        "bytes": os.path.getsize(output) if os.path.exists(output) else 0,
    }


def make_path_command(spec):
    import Path

    if isinstance(spec, str):
        return Path.Command(spec)
    if not isinstance(spec, dict):
        raise ValueError("CAM command must be a string or object")
    name = spec.get("name") or spec.get("command")
    if not name:
        raise ValueError("CAM command object requires name")
    parameters = spec.get("parameters")
    if parameters is None:
        return Path.Command(str(name))
    return Path.Command(str(name), {str(key): float(value) for key, value in parameters.items()})


def action_cam_path_create(args):
    import Path

    doc = open_or_new(args)
    commands = [make_path_command(command) for command in args.get("commands") or []]
    if not commands:
        raise ValueError("commands must contain at least one CAM command")
    doc.openTransaction("MCP create CAM path")
    try:
        obj = doc.addObject("Path::Feature", args.get("path_name") or "Toolpath")
        obj.Path = Path.Path(commands)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "path": object_summary(obj), "document": document_summary(doc)}


def action_cam_path_inspect(args):
    doc = App.openDocument(args["document_path"])
    paths = [
        obj
        for obj in doc.Objects
        if str(getattr(obj, "TypeId", "")).startswith("Path::")
        and (not args.get("path_name") or obj.Name == args.get("path_name") or obj.Label == args.get("path_name"))
    ]
    return {"paths": [object_summary(path) for path in paths], "count": len(paths), "document": document_summary(doc)}


def action_cam_path_export(args):
    doc = App.openDocument(args["document_path"])
    path_obj = get_object(doc, args["path_name"])
    output = safe_output_path(args["output_path"], args)
    if os.path.exists(output) and not bool(args.get("overwrite", False)):
        raise ValueError("output exists; pass overwrite=true: " + output)
    path = getattr(path_obj, "Path", None)
    if path is None or not hasattr(path, "toGCode"):
        raise ValueError("object is not a CAM Path feature: " + args["path_name"])
    gcode = path.toGCode()
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(gcode)
        if gcode and not gcode.endswith("\n"):
            handle.write("\n")
    return {"exported_path": output, "path": object_summary(path_obj), "bytes": os.path.getsize(output)}


def get_or_create_fem_analysis(doc, name):
    if name:
        try:
            return get_object(doc, name)
        except ValueError:
            pass
    for obj in doc.Objects:
        if getattr(obj, "TypeId", "") == "Fem::FemAnalysis":
            return obj
    import ObjectsFem

    return ObjectsFem.makeAnalysis(doc, name or "Analysis")


def fem_refs(doc, specs):
    refs = []
    for spec in specs or []:
        obj = get_object(doc, spec["object_name"])
        subelements = spec.get("subelements")
        if subelements is None:
            subelements = [spec.get("sub_element") or spec.get("subelement") or ""]
        if isinstance(subelements, str):
            subelements = [subelements]
        refs.append((obj, tuple(str(sub) for sub in subelements if sub)))
    return refs


def action_fem_analysis_create(args):
    import ObjectsFem

    doc = open_or_new(args)
    doc.openTransaction("MCP create FEM analysis")
    try:
        analysis = ObjectsFem.makeAnalysis(doc, args.get("analysis_name") or "Analysis")
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "analysis": object_summary(analysis), "document": document_summary(doc)}


def action_fem_material_create(args):
    import ObjectsFem

    doc = App.openDocument(args["document_path"])
    analysis = get_or_create_fem_analysis(doc, args.get("analysis_name"))
    material_data = args.get("material") or {}
    doc.openTransaction("MCP create FEM material")
    try:
        material = ObjectsFem.makeMaterialSolid(doc, args.get("material_name") or "FemMaterial")
        if material_data:
            material.Material = {str(key): str(value) for key, value in material_data.items()}
        if args.get("references"):
            material.References = fem_refs(doc, args.get("references"))
        analysis.addObject(material)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {"saved_path": saved, "analysis": object_summary(analysis), "material": object_summary(material), "document": document_summary(doc)}


def action_fem_constraint_create(args):
    import ObjectsFem

    doc = App.openDocument(args["document_path"])
    analysis = get_or_create_fem_analysis(doc, args.get("analysis_name"))
    constraint_type = (args.get("constraint_type") or "fixed").lower()
    doc.openTransaction("MCP create FEM constraint")
    try:
        if constraint_type == "fixed":
            constraint = ObjectsFem.makeConstraintFixed(doc, args.get("constraint_name") or "ConstraintFixed")
        elif constraint_type == "force":
            constraint = ObjectsFem.makeConstraintForce(doc, args.get("constraint_name") or "ConstraintForce")
            if args.get("force") is not None:
                constraint.Force = str(args["force"])
            if args.get("direction_reference"):
                direction_spec = args["direction_reference"]
                direction_obj = get_object(doc, direction_spec["object_name"])
                direction_subs = direction_spec.get("subelements") or [direction_spec.get("sub_element") or ""]
                if isinstance(direction_subs, str):
                    direction_subs = [direction_subs]
                constraint.Direction = (direction_obj, [str(sub) for sub in direction_subs if sub])
            elif args.get("direction_vector") is not None and hasattr(constraint, "DirectionVector"):
                constraint.DirectionVector = vector(args["direction_vector"])
        else:
            raise ValueError("unsupported constraint_type: " + str(constraint_type))
        if args.get("references"):
            constraint.References = fem_refs(doc, args.get("references"))
        analysis.addObject(constraint)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()
    saved = save_if_requested(doc, args)
    return {
        "saved_path": saved,
        "analysis": object_summary(analysis),
        "constraint": object_summary(constraint),
        "document": document_summary(doc),
    }


def action_fem_inspect(args):
    doc = App.openDocument(args["document_path"])
    fem_objects = [
        obj
        for obj in doc.Objects
        if str(getattr(obj, "TypeId", "")).startswith("Fem::") or str(getattr(obj, "TypeId", "")) == "App::MaterialObjectPython"
    ]
    analyses = [obj for obj in fem_objects if getattr(obj, "TypeId", "") == "Fem::FemAnalysis"]
    return {
        "analyses": [object_summary(analysis) for analysis in analyses],
        "fem_objects": [object_summary(obj) for obj in fem_objects],
        "analysis_count": len(analyses),
        "object_count": len(fem_objects),
        "document": document_summary(doc),
    }


DISPATCH = {
    "document_new": action_document_new,
    "document_open": action_document_open,
    "document_save": action_document_save,
    "document_recompute": action_document_recompute,
    "document_export": action_document_export,
    "object_list": action_object_list,
    "object_get": action_object_get,
    "object_set_properties": action_object_set_properties,
    "spreadsheet_create": action_spreadsheet_create,
    "spreadsheet_get": action_spreadsheet_get,
    "object_expression_set": action_object_expression_set,
    "object_expression_list": action_object_expression_list,
    "object_rename_label": action_object_rename_label,
    "object_delete": action_object_delete,
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
    "part_fillet": action_part_fillet,
    "part_chamfer": action_part_chamfer,
    "part_check_geometry": action_part_check_geometry,
    "sketch_create": action_sketch_create,
    "sketch_add_geometry": action_sketch_add_geometry,
    "sketch_add_constraint": action_sketch_add_constraint,
    "sketch_add_profile": action_sketch_add_profile,
    "sketch_profile_create": action_sketch_profile_create,
    "sketch_profile_validate": action_sketch_profile_validate,
    "curve_fit_analyze": action_curve_fit_analyze,
    "sketch_geometry_method_catalog": action_sketch_geometry_method_catalog,
    "sketch_edit_geometry": action_sketch_edit_geometry,
    "sketch_external_projection": action_sketch_external_projection,
    "sketch_external_intersection": action_sketch_external_intersection,
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
    "techdraw_page_create": action_techdraw_page_create,
    "techdraw_view_create": action_techdraw_view_create,
    "techdraw_inspect": action_techdraw_inspect,
    "techdraw_page_export": action_techdraw_page_export,
    "cam_path_create": action_cam_path_create,
    "cam_path_inspect": action_cam_path_inspect,
    "cam_path_export": action_cam_path_export,
    "fem_analysis_create": action_fem_analysis_create,
    "fem_material_create": action_fem_material_create,
    "fem_constraint_create": action_fem_constraint_create,
    "fem_inspect": action_fem_inspect,
}


try:
    payload = DISPATCH[ARGS["action"]](ARGS)
    payload["ok"] = True
    payload["action"] = ARGS["action"]
    emit(payload)
except Exception as exc:
    emit({"ok": False, "action": ARGS.get("action"), "error": str(exc), "traceback": traceback.format_exc()})
    raise
