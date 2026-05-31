#!/usr/bin/env python3
"""Real FreeCAD smoke for typed CAD MCP tools."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_mcp.cad_tools import CadToolService


def assert_ok(result: dict, label: str) -> dict:
    execution = result["execution"]
    payload = result["freecad"]
    if not execution["ok"] or not payload or not payload.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    return payload


def assert_tool_failed(result: dict, label: str) -> dict:
    execution = result["execution"]
    payload = result["freecad"]
    if execution["ok"] and payload and payload.get("ok"):
        raise RuntimeError(f"{label} unexpectedly succeeded: {result}")
    return result


def require_nonempty_list(payload: dict, key: str, label: str) -> list:
    values = payload.get(key)
    if not isinstance(values, list) or not values:
        raise RuntimeError(f"{label} missing non-empty {key}: {payload}")
    return values


def require_report(payload: dict, index: int, label: str) -> dict:
    reports = payload.get("reports")
    if not isinstance(reports, list) or len(reports) <= index:
        raise RuntimeError(f"{label} missing report {index}: {payload}")
    report = reports[index]
    if not isinstance(report, dict):
        raise RuntimeError(f"{label} report {index} is not an object: {payload}")
    return report


def main() -> int:
    if not os.environ.get("FREECAD_MCP_FREECAD_HOME") and not os.environ.get("FREECAD_MCP_FREECAD_CMD"):
        message = "typed CAD smoke SKIPPED: FreeCAD runtime env not configured"
        if os.environ.get("FREECAD_MCP_REQUIRE_RUNTIME") == "1":
            raise RuntimeError(message)
        print(message)
        return 0

    service = CadToolService()
    with tempfile.TemporaryDirectory(prefix="freecad-mcp-smoke-") as temp_dir:
        temp = Path(temp_dir)
        os.environ["FREECAD_MCP_WORKSPACE_ROOT"] = str(temp)
        document = temp / "box.FCStd"
        exported = temp / "box.stl"
        step_exported = temp / "box.step"
        step_roundtrip = temp / "step_roundtrip.FCStd"
        imported = temp / "mesh.FCStd"
        boolean_doc = temp / "boolean.FCStd"
        open_sketch_doc = temp / "open_sketch.FCStd"
        advanced_sketch_doc = temp / "advanced_sketch.FCStd"
        connected_sketch_doc = temp / "connected_sketch.FCStd"
        profile_builder_doc = temp / "profile_builder.FCStd"
        partdesign_doc = temp / "partdesign.FCStd"
        auto_sketch_doc = temp / "auto_sketch.FCStd"
        transform_sketch_doc = temp / "transform_sketch.FCStd"

        create = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "primitive": "box",
                    "object_name": "Box",
                    "properties": {"Length": 4.0, "Width": 3.0, "Height": 2.0},
                    "output_path": str(document),
                    "overwrite": True,
                }
            ),
            "part_create_primitive",
        )
        if create["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"unexpected shape summary: {create}")

        objects = assert_ok(
            service.definition_map()["freecad_object_list"].handler({"document_path": str(document)}),
            "object_list",
        )
        if objects["document"]["object_count"] < 1:
            raise RuntimeError(f"object list empty: {objects}")

        renamed = assert_ok(
            service.definition_map()["freecad_object_rename_label"].handler(
                {
                    "document_path": str(document),
                    "object_name": "Box",
                    "label": "Main Housing",
                    "output_path": str(document),
                    "overwrite": True,
                }
            ),
            "object_rename_label",
        )
        if renamed["after"]["name"] != "Box" or renamed["after"]["label"] != "Main Housing":
            raise RuntimeError(f"object label rename changed the wrong fields: {renamed}")
        renamed_lookup = assert_ok(
            service.definition_map()["freecad_object_get"].handler(
                {"document_path": str(document), "object_name": "Main Housing"}
            ),
            "object_get renamed label",
        )
        if renamed_lookup["object"]["name"] != "Box":
            raise RuntimeError(f"renamed label lookup did not resolve stable object name: {renamed_lookup}")

        export = assert_ok(
            service.definition_map()["freecad_export_file"].handler(
                {"document_path": str(document), "output_path": str(exported), "overwrite": True}
            ),
            "export_file",
        )
        if not Path(export["exported_path"]).exists():
            raise RuntimeError(f"export missing: {export}")

        step_export = assert_ok(
            service.definition_map()["freecad_export_file"].handler(
                {
                    "document_path": str(document),
                    "object_names": ["Box"],
                    "output_path": str(step_exported),
                    "overwrite": True,
                }
            ),
            "step_export_file",
        )
        if not Path(step_export["exported_path"]).exists():
            raise RuntimeError(f"STEP export missing: {step_export}")

        step_import = assert_ok(
            service.definition_map()["freecad_import_file"].handler(
                {
                    "input_path": str(step_exported),
                    "document_name": "StepRoundtrip",
                    "output_path": str(step_roundtrip),
                    "overwrite": True,
                }
            ),
            "step_import_file",
        )
        imported_solids = [
            obj["shape"]["solids"]
            for obj in step_import["document"]["objects"]
            if obj.get("shape")
        ]
        if not imported_solids or max(imported_solids) < 1:
            raise RuntimeError(f"STEP roundtrip did not preserve a solid: {step_import}")

        solid_extrude = assert_tool_failed(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(document),
                    "source_object": "Box",
                    "vector": [0, 0, 1],
                    "result_name": "BoxExtrude",
                    "output_path": str(document),
                    "overwrite": True,
                }
            ),
            "part_extrude solid",
        )
        solid_extrude_payload = solid_extrude.get("freecad") or {}
        if solid_extrude_payload.get("mode") == "face_from_closed_wire":
            raise RuntimeError(f"solid extrude falsely used closed-wire mode: {solid_extrude}")
        if "Solids are not Processed" not in solid_extrude["execution"]["stderr"]:
            raise RuntimeError(f"solid extrude failed in an unexpected way: {solid_extrude}")

        base_box = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "primitive": "box",
                    "object_name": "BooleanBox",
                    "properties": {"Length": 4.0, "Width": 3.0, "Height": 2.0},
                    "output_path": str(boolean_doc),
                    "overwrite": True,
                }
            ),
            "boolean base box",
        )
        if base_box["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"boolean base box is not a solid: {base_box}")

        cylinder = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "document_path": str(boolean_doc),
                    "primitive": "cylinder",
                    "object_name": "BooleanCylinder",
                    "properties": {"Radius": 1.5, "Height": 4.0},
                    "output_path": str(boolean_doc),
                    "overwrite": True,
                }
            ),
            "boolean cylinder",
        )
        if cylinder["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"boolean cylinder is not a solid: {cylinder}")

        boolean = assert_ok(
            service.definition_map()["freecad_part_boolean"].handler(
                {
                    "document_path": str(boolean_doc),
                    "object_names": ["BooleanBox", "BooleanCylinder"],
                    "operation": "fuse",
                    "result_name": "BooleanFuse",
                    "output_path": str(boolean_doc),
                    "overwrite": True,
                }
            ),
            "part_boolean fuse",
        )
        if boolean["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"boolean fuse did not create a single solid: {boolean}")

        boolean_check = assert_ok(
            service.definition_map()["freecad_part_check_geometry"].handler(
                {"document_path": str(boolean_doc), "object_names": ["BooleanFuse"], "run_bop_check": True}
            ),
            "boolean geometry check",
        )
        if not boolean_check["checks"][0]["is_valid"] or boolean_check["checks"][0]["check_error"]:
            raise RuntimeError(f"boolean geometry check failed: {boolean_check}")

        mesh = assert_ok(
            service.definition_map()["freecad_mesh_import"].handler(
                {"input_path": str(exported), "output_path": str(imported), "overwrite": True}
            ),
            "mesh_import",
        )
        if mesh["document"]["object_count"] < 1:
            raise RuntimeError(f"mesh import empty: {mesh}")

        repaired = assert_ok(
            service.definition_map()["freecad_mesh_repair"].handler(
                {
                    "document_path": str(imported),
                    "actions": ["harmonize_normals", "remove_duplicated_points"],
                    "output_path": str(imported),
                    "overwrite": True,
                }
            ),
            "mesh_repair",
        )
        if not repaired["reports"] or repaired["reports"][0]["errors"]:
            raise RuntimeError(f"mesh repair reported errors: {repaired}")

        unsupported_repair = assert_ok(
            service.definition_map()["freecad_mesh_repair"].handler(
                {
                    "document_path": str(imported),
                    "actions": ["unsupported_action"],
                    "output_path": str(imported),
                    "overwrite": True,
                }
            ),
            "mesh_repair unsupported action",
        )
        repair_errors = unsupported_repair["reports"][0]["errors"]
        if not repair_errors or repair_errors[0]["error"] != "unsupported action":
            raise RuntimeError(f"unsupported repair action did not report expected error: {unsupported_repair}")

        sketch_doc = temp / "sketch.FCStd"
        sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {"document_name": "SketchSmoke", "sketch_name": "ProfileSketch", "output_path": str(sketch_doc), "overwrite": True}
            ),
            "sketch_create",
        )
        if sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
            raise RuntimeError(f"sketch type mismatch: {sketch}")

        sketch_geometry = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(sketch_doc),
                    "sketch_name": "ProfileSketch",
                    "geometry": [
                        {"type": "line", "start": [0, 0, 0], "end": [5, 0, 0]},
                        {"type": "line", "start": [5, 0, 0], "end": [5, 3, 0]},
                        {"type": "line", "start": [5, 3, 0], "end": [0, 3, 0]},
                        {"type": "line", "start": [0, 3, 0], "end": [0, 0, 0]},
                    ],
                    "output_path": str(sketch_doc),
                    "overwrite": True,
                }
            ),
            "sketch_add_geometry",
        )
        if sketch_geometry["sketch"]["shape"]["edges"] != 4:
            raise RuntimeError(f"unexpected sketch geometry: {sketch_geometry}")

        extrude = assert_ok(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(sketch_doc),
                    "source_object": "ProfileSketch",
                    "vector": [0, 0, 2],
                    "result_name": "ProfileExtrude",
                    "output_path": str(sketch_doc),
                    "overwrite": True,
                }
            ),
            "part_extrude sketch",
        )
        if extrude["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"sketch extrude did not create a solid: {extrude}")

        shell_extrude = assert_ok(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(sketch_doc),
                    "source_object": "ProfileSketch",
                    "vector": [0, 0, 2],
                    "extrude_mode": "feature",
                    "solid": False,
                    "result_name": "ProfileShellExtrude",
                    "output_path": str(sketch_doc),
                    "overwrite": True,
                }
            ),
            "part_extrude feature shell",
        )
        if shell_extrude["mode"] != "feature" or shell_extrude["object"]["shape"]["solids"] != 0:
            raise RuntimeError(f"feature shell extrude did not stay shell-only: {shell_extrude}")

        symmetric_extrude = assert_ok(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(sketch_doc),
                    "source_object": "ProfileSketch",
                    "vector": [0, 0, 1],
                    "extrude_mode": "feature",
                    "solid": True,
                    "symmetric": True,
                    "length_fwd": 6,
                    "result_name": "ProfileSymmetricExtrude",
                    "output_path": str(sketch_doc),
                    "overwrite": True,
                }
            ),
            "part_extrude feature symmetric",
        )
        sym_box = symmetric_extrude["object"]["shape"]["bound_box"]
        if symmetric_extrude["object"]["shape"]["solids"] != 1 or [sym_box["zmin"], sym_box["zmax"]] != [-3.0, 3.0]:
            raise RuntimeError(f"feature symmetric extrude mismatch: {symmetric_extrude}")

        taper_extrude = assert_ok(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(sketch_doc),
                    "source_object": "ProfileSketch",
                    "vector": [0, 0, 1],
                    "extrude_mode": "feature",
                    "solid": True,
                    "length_fwd": 5,
                    "taper_angle": 5,
                    "result_name": "ProfileTaperExtrude",
                    "output_path": str(sketch_doc),
                    "overwrite": True,
                }
            ),
            "part_extrude feature taper",
        )
        if taper_extrude["object"]["shape"]["solids"] != 1 or not taper_extrude["object"]["shape"]["valid"]:
            raise RuntimeError(f"feature taper extrude invalid: {taper_extrude}")

        for blocked_type in ("Group", "Text"):
            blocked = assert_tool_failed(
                service.definition_map()["freecad_sketch_add_constraint"].handler(
                    {
                        "document_path": str(sketch_doc),
                        "sketch_name": "ProfileSketch",
                        "constraints": [{"type": blocked_type, "values": [[0, 1]]}],
                    }
                ),
                f"sketch {blocked_type} constraint blocked",
            )
            blocked_payload = blocked.get("freecad") or {}
            if "Group/Text" not in blocked_payload.get("error", ""):
                raise RuntimeError(f"Sketcher {blocked_type} constraint did not fail safely: {blocked}")

        open_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "OpenSketchSmoke",
                    "sketch_name": "OpenProfileSketch",
                    "output_path": str(open_sketch_doc),
                    "overwrite": True,
                }
            ),
            "open sketch create",
        )
        if open_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
            raise RuntimeError(f"open sketch type mismatch: {open_sketch}")

        open_geometry = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(open_sketch_doc),
                    "sketch_name": "OpenProfileSketch",
                    "geometry": [{"type": "line", "start": [0, 0, 0], "end": [5, 0, 0]}],
                    "output_path": str(open_sketch_doc),
                    "overwrite": True,
                }
            ),
            "open sketch add geometry",
        )
        if open_geometry["sketch"]["shape"]["edges"] != 1:
            raise RuntimeError(f"unexpected open sketch geometry: {open_geometry}")

        open_extrude = assert_ok(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(open_sketch_doc),
                    "source_object": "OpenProfileSketch",
                    "vector": [0, 0, 2],
                    "result_name": "OpenProfileExtrude",
                    "output_path": str(open_sketch_doc),
                    "overwrite": True,
                }
            ),
            "part_extrude open sketch",
        )
        if open_extrude["mode"] != "shape":
            raise RuntimeError(f"open sketch extrude falsely used closed-wire mode: {open_extrude}")
        if open_extrude["object"]["shape"]["solids"] != 0:
            raise RuntimeError(f"open sketch extrude unexpectedly created a solid: {open_extrude}")

        advanced_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "AdvancedSketchSmoke",
                    "sketch_name": "AdvancedSketch",
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "advanced sketch create",
        )
        if advanced_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
            raise RuntimeError(f"advanced sketch type mismatch: {advanced_sketch}")

        advanced_geometry_items = [
            {"type": "point", "point": [0, 0, 0]},
            {"type": "line_angle_length", "start": [0, -3, 0], "angle": {"degrees": 30}, "length": 5},
            {"type": "circle_3_point", "points": [[0, -8, 0], [2, -6, 0], [4, -8, 0]]},
            {"type": "arc_3_point", "start": [6, -8, 0], "mid": [8, -6, 0], "end": [10, -8, 0]},
            {"type": "arc_start_mid_end", "start": [6, -12, 0], "mid": [8, -10, 0], "end": [10, -12, 0]},
            {"type": "arc_start_end_radius", "start": [12, -8, 0], "end": [18, -8, 0], "radius": 5, "side": "left", "sweep": "minor"},
            {"type": "arc_center_angles", "center": [24, -8, 0], "radius": 3, "start_angle": 0, "end_angle": {"degrees": 90}, "direction": "ccw"},
            {"type": "ellipse", "center": [4, 0, 0], "major_radius": 2, "minor_radius": 1},
            {
                "type": "arc_of_ellipse",
                "center": [9, 0, 0],
                "major_radius": 2,
                "minor_radius": 1,
                "start_angle": {"degrees": 0},
                "end_angle": {"degrees": 90},
            },
            {"type": "arc_of_hyperbola", "center": [14, 0, 0], "major_radius": 2, "minor_radius": 1, "start_angle": -1, "end_angle": 1},
            {"type": "arc_of_parabola", "start_angle": -1, "end_angle": 1},
            {"type": "bspline", "poles": [[0, 5, 0], [1, 6, 0], [2, 5, 0]]},
            {"type": "polyline", "points": [[0, 8, 0], [1, 8, 0], [1, 9, 0]], "closed": False},
        ]
        expected_advanced_geometry = len(advanced_geometry_items) + 1
        advanced_geometry = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "geometry": advanced_geometry_items,
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "advanced sketch add geometry",
        )
        added_advanced_geometry = require_nonempty_list(advanced_geometry, "added_indices", "advanced sketch add geometry")
        if len(added_advanced_geometry) != expected_advanced_geometry:
            raise RuntimeError(f"advanced geometry added count mismatch: {advanced_geometry}")
        if advanced_geometry["sketch"]["sketch"]["geometry_count"] != len(added_advanced_geometry):
            raise RuntimeError(f"unexpected advanced geometry count: {advanced_geometry}")
        arc_reports = advanced_geometry.get("geometry_reports", [])
        if len(arc_reports) < 4:
            raise RuntimeError(f"advanced arc geometry reports missing: {advanced_geometry}")
        for report in arc_reports:
            for field in ["actual_start", "actual_end", "center", "radius", "sweep_deg", "normal"]:
                if field not in report:
                    raise RuntimeError(f"arc report missing {field}: {advanced_geometry}")
        center_angle_report = next((report for report in arc_reports if report.get("input_type") == "arc_center_angles"), None)
        if not center_angle_report or not 89.0 <= center_angle_report["sweep_deg"] <= 91.0:
            raise RuntimeError(f"center-angle arc report did not preserve requested sweep: {advanced_geometry}")
        method_catalog = assert_ok(
            service.definition_map()["freecad_sketch_geometry_method_catalog"].handler({}),
            "sketch geometry method catalog",
        )
        catalog_types = {
            method["type"]
            for item in method_catalog["geometry_methods"]
            for method in item["methods"]
        }
        catalog_types.update(
            method["type"]
            for item in method_catalog["profile_methods"]
            for method in item["methods"]
            if method.get("type")
        )
        for expected_type in ["line_angle_length", "arc_3_point", "arc_start_end_radius", "arc_center_angles", "circle_3_point", "bspline"]:
            if expected_type not in catalog_types:
                raise RuntimeError(f"sketch geometry method catalog missing {expected_type}: {method_catalog}")
        for expected_type in ["rectangle_center", "rectangle_3_point", "triangle", "square", "hexagon", "slot_start_end_radius", "arc_slot"]:
            if expected_type not in catalog_types:
                raise RuntimeError(f"sketch profile method catalog missing {expected_type}: {method_catalog}")

        profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "profile": {"type": "rectangle", "origin": [20, 0, 0], "width": 5, "height": 3},
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "sketch add profile",
        )
        profile_added = require_nonempty_list(profile, "added_indices", "sketch add profile")
        expected_profile_geometry = len(added_advanced_geometry) + len(profile_added)
        expected_profile_constraints = len(profile.get("constraint_indices", []))
        if profile["profile_type"] != "rectangle" or len(profile_added) != 4:
            raise RuntimeError(f"unexpected profile result: {profile}")

        for profile_spec, expected_added in [
            ({"type": "rectangle_center", "center": [26, -8, 0], "width": 5, "height": 3}, 4),
            ({"type": "rectangle_3_point", "point1": [20, -16, 0], "point2": [25, -15, 0], "point3": [24, -10, 0]}, 4),
            ({"type": "triangle", "center": [30, -10, 0], "radius": 3}, 3),
            ({"type": "square", "center": [38, -10, 0], "radius": 3}, 4),
            ({"type": "regular_polygon", "center": [32, 0, 0], "radius": 3, "sides": 6}, 6),
            ({"type": "hexagon", "center": [40, 0, 0], "radius": 3}, 6),
            ({"type": "slot", "center": [45, 0, 0], "length": 8, "radius": 1.5}, 4),
            ({"type": "slot_start_end_radius", "start": [50, -10, 0], "end": [58, -8, 0], "radius": 1.5}, 4),
            ({"type": "arc_slot", "center": [66, -8, 0], "radius": 5, "width": 2, "start_angle": 0, "end_angle": {"degrees": 90}, "direction": "ccw"}, 4),
            ({"type": "circle", "center": [58, 0, 0], "radius": 2}, 1),
        ]:
            helper_profile = assert_ok(
                service.definition_map()["freecad_sketch_add_profile"].handler(
                    {
                        "document_path": str(advanced_sketch_doc),
                        "sketch_name": "AdvancedSketch",
                        "profile": profile_spec,
                        "output_path": str(advanced_sketch_doc),
                        "overwrite": True,
                    }
                ),
                f"sketch add profile {profile_spec['type']}",
            )
            helper_added = require_nonempty_list(helper_profile, "added_indices", f"sketch add profile {profile_spec['type']}")
            expected_profile_geometry += len(helper_added)
            expected_profile_constraints += len(helper_profile.get("constraint_indices", []))
            if helper_profile["profile_type"] != profile_spec["type"] or len(helper_added) != expected_added:
                raise RuntimeError(f"unexpected helper profile result: {helper_profile}")

        radius_constraint = assert_ok(
            service.definition_map()["freecad_sketch_add_constraint"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "constraints": [{"type": "Radius", "values": [1, 2.0], "name": "EllipseRadius", "driving": False}],
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "advanced sketch add constraint",
        )
        radius_constraint_indices = require_nonempty_list(radius_constraint, "added_indices", "advanced sketch add constraint")
        radius_constraint_index = radius_constraint_indices[0]

        edited_constraints = assert_ok(
            service.definition_map()["freecad_sketch_edit_constraints"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "operations": [
                        {"operation": "get_datum", "constraint_index": radius_constraint_index},
                        {"operation": "set_driving", "constraint_index": radius_constraint_index, "driving": True},
                        {"operation": "toggle_active", "constraint_index": radius_constraint_index},
                        {"operation": "toggle_active", "constraint_index": radius_constraint_index},
                        {"operation": "validate_constraints"},
                    ],
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "advanced sketch edit constraints",
        )
        datum_report = require_report(edited_constraints, 0, "advanced sketch edit constraints")
        if datum_report.get("datum", {}).get("value") != 2.0:
            raise RuntimeError(f"unexpected datum report: {edited_constraints}")

        edited_geometry = assert_ok(
            service.definition_map()["freecad_sketch_edit_geometry"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "operations": [{"operation": "set_construction", "geometry_index": 0, "construction": True}],
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "advanced sketch edit geometry",
        )
        edited_geometry_items = edited_geometry["sketch"]["sketch"].get("geometry", [])
        if not edited_geometry_items or not edited_geometry_items[0].get("construction"):
            raise RuntimeError(f"construction state did not change: {edited_geometry}")

        auto_constraints = assert_ok(
            service.definition_map()["freecad_sketch_auto_constrain"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "operations": [{"operation": "detect_point_on_point"}],
                    "output_path": str(advanced_sketch_doc),
                    "overwrite": True,
                }
            ),
            "advanced sketch auto constrain",
        )
        auto_report = require_report(auto_constraints, 0, "advanced sketch auto constrain")
        if "count" not in auto_report:
            raise RuntimeError(f"missing auto constraint report: {auto_constraints}")

        validation = assert_ok(
            service.definition_map()["freecad_sketch_validate"].handler(
                {
                    "document_path": str(advanced_sketch_doc),
                    "sketch_name": "AdvancedSketch",
                    "detect_missing": True,
                    "include_constraint_errors": True,
                }
            ),
            "advanced sketch validate",
        )
        expected_min_constraints = expected_profile_constraints + len(radius_constraint_indices)
        if validation["geometry_count"] < expected_profile_geometry or validation["constraint_count"] < expected_min_constraints:
            raise RuntimeError(f"advanced sketch validation mismatch: {validation}")

        assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "ConnectedSketchSmoke",
                    "sketch_name": "ConnectedSketch",
                    "output_path": str(connected_sketch_doc),
                    "overwrite": True,
                }
            ),
            "connected sketch create",
        )
        connected_geometry = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(connected_sketch_doc),
                    "sketch_name": "ConnectedSketch",
                    "geometry": [
                        {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                        {"type": "bspline", "poles": [[10, 0, 0], [12, 5, 0], [10, 10, 0]]},
                        {"type": "arc", "center": [5, 10, 0], "radius": 5, "start_angle": 0, "end_angle": 3.141592653589793},
                        {"type": "line", "start": [0, 10, 0], "end": [0, 0, 0]},
                    ],
                    "connect_sequence": True,
                    "close_sequence": True,
                    "require_closed": True,
                    "output_path": str(connected_sketch_doc),
                    "overwrite": True,
                }
            ),
            "connected sketch add geometry",
        )
        if len(connected_geometry["added_indices"]) != 4 or len(connected_geometry["constraint_indices"]) != 4:
            raise RuntimeError(f"connected sketch did not add expected geometry/constraints: {connected_geometry}")
        closed_validation = connected_geometry.get("closed_validation", {})
        if closed_validation.get("open_vertices"):
            raise RuntimeError(f"connected sketch is not closed: {connected_geometry}")
        connected_arc_reports = connected_geometry.get("geometry_reports", [])
        if len(connected_arc_reports) != 1 or not 179.0 <= connected_arc_reports[0]["sweep_deg"] <= 181.0:
            raise RuntimeError(f"connected sketch did not report the circular arc correctly: {connected_geometry}")

        profile_builder = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "ProfileBuilderSmoke",
                    "sketch_name": "ProfileBuilderSketch",
                    "loops": [
                        {
                            "name": "spline_arc_loop",
                            "segments": [
                                {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                                {
                                    "type": "bspline",
                                    "expected_type": "bspline",
                                    "fallback_policy": "fail",
                                    "reason": "variable curvature trace",
                                    "poles": [[10, 0, 0], [12, 5, 0], [10, 10, 0]],
                                },
                                {
                                    "type": "arc",
                                    "expected_type": "arc",
                                    "fallback_policy": "fail",
                                    "reason": "constant-radius round end",
                                    "center": [5, 10, 0],
                                    "radius": 5,
                                    "start_angle": 0,
                                    "end_angle": 3.141592653589793,
                                },
                                {"type": "line", "start": [0, 10, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "required_segment_types": ["bspline", "arc"],
                    "minimum_curve_segments": 2,
                    "forbid_polyline_fallback": True,
                    "require_fully_constrained": True,
                    "output_path": str(profile_builder_doc),
                    "overwrite": True,
                }
            ),
            "sketch profile create",
        )
        if not profile_builder["validation"]["ok"] or not profile_builder["validation"]["pad_ready"]:
            raise RuntimeError(f"profile builder did not produce pad-ready profile: {profile_builder}")
        if profile_builder["validation"]["degrees_of_freedom"] != 0:
            raise RuntimeError(f"profile builder did not fully constrain profile: {profile_builder}")
        if profile_builder["loops"][0]["curve_contract"]["curve_segment_count"] != 2:
            raise RuntimeError(f"profile builder did not preserve curve segment count: {profile_builder}")
        if profile_builder["loops"][0]["segment_intent_mismatches"]:
            raise RuntimeError(f"profile builder reported unexpected segment intent mismatch: {profile_builder}")
        if len(profile_builder.get("geometry_reports", [])) != 1 or profile_builder["geometry_reports"][0]["input_type"] != "arc":
            raise RuntimeError(f"profile builder did not report its arc geometry: {profile_builder}")
        profile_indices = profile_builder["loops"][0]["added_indices"]
        profile_validation = assert_ok(
            service.definition_map()["freecad_sketch_profile_validate"].handler(
                {
                    "document_path": str(profile_builder_doc),
                    "sketch_name": "ProfileBuilderSketch",
                    "require_fully_constrained": True,
                    "required_segment_types": ["bspline", "arc"],
                    "minimum_curve_segments": 2,
                    "forbid_all_line_loops": True,
                    "expected_geometry": [
                        {"geometry_index": profile_indices[1], "expected_type": "bspline", "fallback_policy": "fail", "reason": "variable curvature trace"},
                        {"geometry_index": profile_indices[2], "expected_type": "arc", "fallback_policy": "fail", "reason": "constant-radius round end"},
                    ],
                }
            ),
            "sketch profile validate",
        )
        if not profile_validation["validation"]["ok"] or profile_validation["validation"]["face_validation"]["face_count"] != 1:
            raise RuntimeError(f"profile validation mismatch: {profile_validation}")
        if profile_validation["validation"]["geometry_type_counts"].get("bspline") != 1 or profile_validation["validation"]["geometry_type_counts"].get("arc") != 1:
            raise RuntimeError(f"profile validation did not report native curve types: {profile_validation}")
        if profile_validation["validation"]["intent_mismatches"]:
            raise RuntimeError(f"profile validation reported unexpected intent mismatch: {profile_validation}")

        partdesign_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "PartDesignSmoke",
                    "sketch_name": "BodySketch",
                    "body_name": "Body",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0, 0, 0], "end": [8, 0, 0]},
                                {"type": "line", "start": [8, 0, 0], "end": [8, 4, 0]},
                                {"type": "line", "start": [8, 4, 0], "end": [0, 4, 0]},
                                {"type": "line", "start": [0, 4, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign attached sketch profile",
        )
        if not partdesign_profile["attachment"]["attached"] or partdesign_profile["attachment"]["plane"] != "XY":
            raise RuntimeError(f"partdesign profile was not attached to XY plane: {partdesign_profile}")
        partdesign_pad = assert_ok(
            service.definition_map()["freecad_partdesign_pad"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "Body",
                    "sketch_name": "BodySketch",
                    "attachment_plane": "XY",
                    "pad_name": "Pad",
                    "length": 6,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign pad",
        )
        if partdesign_pad["pad"]["shape"]["solids"] != 1 or partdesign_pad["body"]["partdesign"]["tip"] != "Pad":
            raise RuntimeError(f"partdesign pad did not produce a body solid: {partdesign_pad}")
        pocket_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "PocketSketch",
                    "body_name": "Body",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [2, 1, 0], "end": [6, 1, 0]},
                                {"type": "line", "start": [6, 1, 0], "end": [6, 3, 0]},
                                {"type": "line", "start": [6, 3, 0], "end": [2, 3, 0]},
                                {"type": "line", "start": [2, 3, 0], "end": [2, 1, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign pocket sketch profile",
        )
        if not pocket_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign pocket profile was not attached: {pocket_profile}")
        partdesign_pocket = assert_ok(
            service.definition_map()["freecad_partdesign_pocket"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "Body",
                    "sketch_name": "PocketSketch",
                    "attachment_plane": "XY",
                    "pocket_name": "Pocket",
                    "length": 3,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign pocket",
        )
        if partdesign_pocket["pocket"]["shape"]["solids"] != 1 or partdesign_pocket["body"]["partdesign"]["tip"] != "Pocket":
            raise RuntimeError(f"partdesign pocket did not preserve a body solid: {partdesign_pocket}")
        hole_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "HoleSketch",
                    "body_name": "Body",
                    "attachment_plane": "XY",
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign hole sketch create",
        )
        if not hole_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign hole sketch was not attached: {hole_sketch}")
        hole_profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "HoleSketch",
                    "profile": {"type": "circle", "center": [1, 2, 0], "radius": 0.5},
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign hole circle profile",
        )
        if hole_profile["profile_type"] != "circle":
            raise RuntimeError(f"partdesign hole profile was not a circle: {hole_profile}")
        partdesign_hole = assert_ok(
            service.definition_map()["freecad_partdesign_hole"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "Body",
                    "sketch_name": "HoleSketch",
                    "attachment_plane": "XY",
                    "hole_name": "Hole",
                    "diameter": 1.0,
                    "depth": 6,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign hole",
        )
        if partdesign_hole["hole"]["shape"]["solids"] != 1 or partdesign_hole["body"]["partdesign"]["tip"] != "Hole":
            raise RuntimeError(f"partdesign hole did not preserve a body solid: {partdesign_hole}")
        drift_rejected = assert_tool_failed(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "ProfileBuilderRejectSmoke",
                    "sketch_name": "RejectSketch",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                                {"type": "line", "start": [10, 0.5, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "endpoint_tolerance": 1e-6,
                    "output_path": str(temp / "profile_builder_reject.FCStd"),
                    "overwrite": True,
                }
            ),
            "sketch profile endpoint drift rejection",
        )
        if "not colocated" not in drift_rejected["freecad"].get("error", ""):
            raise RuntimeError(f"profile builder did not reject endpoint drift: {drift_rejected}")
        line_fallback_rejected = assert_tool_failed(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "ProfileBuilderLineFallbackSmoke",
                    "sketch_name": "LineFallbackSketch",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                                {"type": "line", "start": [10, 0, 0], "end": [10, 10, 0]},
                                {"type": "line", "start": [10, 10, 0], "end": [0, 10, 0]},
                                {"type": "line", "start": [0, 10, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "forbid_all_line_loops": True,
                    "minimum_curve_segments": 1,
                    "output_path": str(temp / "profile_builder_line_fallback.FCStd"),
                    "overwrite": True,
                }
            ),
            "sketch profile line fallback rejection",
        )
        if "all-line fallback" not in line_fallback_rejected["freecad"].get("error", ""):
            raise RuntimeError(f"profile builder did not reject line fallback: {line_fallback_rejected}")
        intent_mismatch_rejected = assert_tool_failed(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "ProfileBuilderIntentRejectSmoke",
                    "sketch_name": "IntentRejectSketch",
                    "loops": [
                        {
                            "segments": [
                                {
                                    "type": "line",
                                    "expected_type": "bspline",
                                    "fallback_policy": "fail",
                                    "start": [0, 0, 0],
                                    "end": [10, 0, 0],
                                },
                                {"type": "line", "start": [10, 0, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "output_path": str(temp / "profile_builder_intent_reject.FCStd"),
                    "overwrite": True,
                }
            ),
            "sketch profile segment intent mismatch rejection",
        )
        if "intent mismatch" not in intent_mismatch_rejected["freecad"].get("error", ""):
            raise RuntimeError(f"profile builder did not reject segment intent mismatch: {intent_mismatch_rejected}")

        arc_fit = assert_ok(
            service.definition_map()["freecad_curve_fit_analyze"].handler(
                {
                    "points": [[10, 0, 0], [7.0710678119, 7.0710678119, 0], [0, 10, 0]],
                    "tolerance": 0.01,
                }
            ),
            "curve fit arc analyze",
        )
        if arc_fit["analysis"]["recommendation"] != "arc":
            raise RuntimeError(f"curve fit did not recommend arc for circular trace: {arc_fit}")
        spline_fit = assert_ok(
            service.definition_map()["freecad_curve_fit_analyze"].handler(
                {
                    "points": [[0, 0, 0], [2, 1, 0], [4, 0, 0], [6, -1, 0], [8, 0, 0]],
                    "tolerance": 0.1,
                }
            ),
            "curve fit freeform analyze",
        )
        if spline_fit["analysis"]["recommendation"] != "bspline":
            raise RuntimeError(f"curve fit did not recommend bspline for freeform trace: {spline_fit}")

        assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "AutoSketchSmoke",
                    "sketch_name": "AutoSketch",
                    "output_path": str(auto_sketch_doc),
                    "overwrite": True,
                }
            ),
            "auto sketch create",
        )
        assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(auto_sketch_doc),
                    "sketch_name": "AutoSketch",
                    "geometry": [
                        {"type": "line", "start": [0, 0, 0], "end": [5, 0, 0]},
                        {"type": "line", "start": [0, 2, 0], "end": [5, 2, 0]},
                    ],
                    "output_path": str(auto_sketch_doc),
                    "overwrite": True,
                }
            ),
            "auto sketch add geometry",
        )
        auto_applied = assert_ok(
            service.definition_map()["freecad_sketch_auto_constrain"].handler(
                {
                    "document_path": str(auto_sketch_doc),
                    "sketch_name": "AutoSketch",
                    "operations": [
                        {"operation": "detect_vertical_horizontal"},
                        {"operation": "make_vertical_horizontal"},
                        {"operation": "detect_equality"},
                        {"operation": "make_equality"},
                    ],
                    "output_path": str(auto_sketch_doc),
                    "overwrite": True,
                }
            ),
            "auto sketch detect/apply constraints",
        )
        if require_report(auto_applied, 0, "auto sketch detect vertical/horizontal").get("count", 0) < 2:
            raise RuntimeError(f"vertical/horizontal detection missed candidates: {auto_applied}")
        if require_report(auto_applied, 2, "auto sketch detect equality").get("count", 0) < 1:
            raise RuntimeError(f"equality detection missed candidates: {auto_applied}")
        auto_validation = assert_ok(
            service.definition_map()["freecad_sketch_validate"].handler(
                {"document_path": str(auto_sketch_doc), "sketch_name": "AutoSketch"}
            ),
            "auto sketch validate",
        )
        auto_constraint_types = [
            constraint["type"]
            for constraint in auto_validation["sketch"]["sketch"].get("constraints", [])
        ]
        if auto_constraint_types.count("Horizontal") < 2 or "Equal" not in auto_constraint_types:
            raise RuntimeError(f"auto constraints were not applied: {auto_validation}")

        assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "TransformSketchSmoke",
                    "sketch_name": "TransformSketch",
                    "output_path": str(transform_sketch_doc),
                    "overwrite": True,
                }
            ),
            "transform sketch create",
        )
        transform_geometry = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(transform_sketch_doc),
                    "sketch_name": "TransformSketch",
                    "geometry": [
                        {"type": "line", "start": [0, 0, 0], "end": [5, 0, 0]},
                        {"type": "bspline", "poles": [[0, 5, 0], [1, 6, 0], [2, 5, 0], [3, 6, 0]]},
                    ],
                    "output_path": str(transform_sketch_doc),
                    "overwrite": True,
                }
            ),
            "transform sketch add geometry",
        )
        transform_added = require_nonempty_list(transform_geometry, "added_indices", "transform sketch add geometry")
        transformed = assert_ok(
            service.definition_map()["freecad_sketch_transform"].handler(
                {
                    "document_path": str(transform_sketch_doc),
                    "sketch_name": "TransformSketch",
                    "operations": [
                        {"operation": "copy", "geometry_indices": [0], "vector": [0, 2, 0]},
                        {"operation": "move", "geometry_indices": [0], "vector": [1, 0, 0]},
                        {"operation": "increase_bspline_degree", "geometry_index": 1, "increment": 1},
                        {"operation": "insert_bspline_knot", "geometry_index": 1, "parameter": 0.5, "multiplicity": 1},
                    ],
                    "output_path": str(transform_sketch_doc),
                    "overwrite": True,
                }
            ),
            "sketch transform",
        )
        copy_report = require_report(transformed, 0, "sketch transform")
        copied_indices = require_nonempty_list(copy_report, "added_indices", "sketch transform copy")
        expected_transform_geometry = len(transform_added) + len(copied_indices)
        if transformed["sketch"]["sketch"]["geometry_count"] != expected_transform_geometry:
            raise RuntimeError(f"unexpected transform geometry count: {transformed}")

        assembly_doc = temp / "assembly.FCStd"
        assembly = assert_ok(
            service.definition_map()["freecad_assembly_create"].handler(
                {"document_name": "AssemblySmoke", "output_path": str(assembly_doc), "overwrite": True}
            ),
            "assembly_create",
        )
        if assembly["assembly"]["type_id"] != "Assembly::AssemblyObject":
            raise RuntimeError(f"assembly type mismatch: {assembly}")

        joint = assert_ok(
            service.definition_map()["freecad_assembly_create_joint"].handler(
                {
                    "document_path": str(assembly_doc),
                    "assembly_name": "Assembly",
                    "joint_type": "Fixed",
                    "joint_name": "FixedJoint",
                    "output_path": str(assembly_doc),
                    "overwrite": True,
                }
            ),
            "assembly_create_joint",
        )
        if not joint["joint_fields"]["has_proxy"] or joint["joint_fields"]["joint_type"] != "Fixed":
            raise RuntimeError(f"assembly joint proxy mismatch: {joint}")

        techdraw_doc = temp / "techdraw.FCStd"
        techdraw_dxf = temp / "techdraw-page.dxf"
        techdraw_base = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "document_name": "TechDrawSmoke",
                    "primitive": "box",
                    "object_name": "TDBox",
                    "properties": {"Length": 10.0, "Width": 6.0, "Height": 4.0},
                    "output_path": str(techdraw_doc),
                    "overwrite": True,
                }
            ),
            "techdraw base box",
        )
        if techdraw_base["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"TechDraw base box mismatch: {techdraw_base}")
        techdraw_page = assert_ok(
            service.definition_map()["freecad_techdraw_page_create"].handler(
                {
                    "document_path": str(techdraw_doc),
                    "page_name": "TDPage",
                    "template_name": "TDTemplate",
                    "scale": 2.0,
                    "output_path": str(techdraw_doc),
                    "overwrite": True,
                }
            ),
            "techdraw page create",
        )
        if techdraw_page["page"]["type_id"] != "TechDraw::DrawPage":
            raise RuntimeError(f"TechDraw page mismatch: {techdraw_page}")
        techdraw_view = assert_ok(
            service.definition_map()["freecad_techdraw_view_create"].handler(
                {
                    "document_path": str(techdraw_doc),
                    "page_name": "TDPage",
                    "source_objects": ["TDBox"],
                    "view_name": "TDView",
                    "direction": [0, 0, 1],
                    "scale": 1.0,
                    "output_path": str(techdraw_doc),
                    "overwrite": True,
                }
            ),
            "techdraw view create",
        )
        if techdraw_view["view"]["techdraw"]["source_names"] != ["TDBox"]:
            raise RuntimeError(f"TechDraw view source mismatch: {techdraw_view}")
        techdraw_inspect = assert_ok(
            service.definition_map()["freecad_techdraw_inspect"].handler(
                {"document_path": str(techdraw_doc), "page_name": "TDPage"}
            ),
            "techdraw inspect",
        )
        if techdraw_inspect["page_count"] != 1 or techdraw_inspect["view_count"] != 1:
            raise RuntimeError(f"TechDraw inspect mismatch: {techdraw_inspect}")
        techdraw_export = assert_ok(
            service.definition_map()["freecad_techdraw_page_export"].handler(
                {
                    "document_path": str(techdraw_doc),
                    "page_name": "TDPage",
                    "output_path": str(techdraw_dxf),
                    "format": "dxf",
                    "overwrite": True,
                }
            ),
            "techdraw page export",
        )
        if not Path(techdraw_export["exported_path"]).exists() or techdraw_export["bytes"] <= 0:
            raise RuntimeError(f"TechDraw export missing: {techdraw_export}")

        cam_doc = temp / "cam.FCStd"
        cam_gcode = temp / "toolpath.ngc"
        cam_path = assert_ok(
            service.definition_map()["freecad_cam_path_create"].handler(
                {
                    "document_name": "CAMSmoke",
                    "path_name": "Toolpath",
                    "commands": [
                        {"name": "G0", "parameters": {"X": 0.0, "Y": 0.0, "Z": 5.0}},
                        {"name": "G1", "parameters": {"X": 1.0, "Y": 2.0, "Z": -1.0, "F": 100.0}},
                    ],
                    "output_path": str(cam_doc),
                    "overwrite": True,
                }
            ),
            "cam path create",
        )
        if cam_path["path"]["type_id"] != "Path::Feature" or cam_path["path"]["cam"]["command_count"] != 2:
            raise RuntimeError(f"CAM path mismatch: {cam_path}")
        cam_inspect = assert_ok(
            service.definition_map()["freecad_cam_path_inspect"].handler(
                {"document_path": str(cam_doc), "path_name": "Toolpath"}
            ),
            "cam path inspect",
        )
        if cam_inspect["count"] != 1:
            raise RuntimeError(f"CAM inspect mismatch: {cam_inspect}")
        cam_export = assert_ok(
            service.definition_map()["freecad_cam_path_export"].handler(
                {
                    "document_path": str(cam_doc),
                    "path_name": "Toolpath",
                    "output_path": str(cam_gcode),
                    "overwrite": True,
                }
            ),
            "cam path export",
        )
        if not Path(cam_export["exported_path"]).exists() or "G1" not in Path(cam_export["exported_path"]).read_text(encoding="utf-8"):
            raise RuntimeError(f"CAM export mismatch: {cam_export}")

        fem_doc = temp / "fem.FCStd"
        fem_base = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "document_name": "FEMSmoke",
                    "primitive": "box",
                    "object_name": "FemBox",
                    "properties": {"Length": 10.0, "Width": 3.0, "Height": 2.0},
                    "output_path": str(fem_doc),
                    "overwrite": True,
                }
            ),
            "fem base box",
        )
        if fem_base["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"FEM base box mismatch: {fem_base}")
        fem_analysis = assert_ok(
            service.definition_map()["freecad_fem_analysis_create"].handler(
                {
                    "document_path": str(fem_doc),
                    "analysis_name": "Analysis",
                    "output_path": str(fem_doc),
                    "overwrite": True,
                }
            ),
            "fem analysis create",
        )
        if fem_analysis["analysis"]["type_id"] != "Fem::FemAnalysis":
            raise RuntimeError(f"FEM analysis mismatch: {fem_analysis}")
        fem_material = assert_ok(
            service.definition_map()["freecad_fem_material_create"].handler(
                {
                    "document_path": str(fem_doc),
                    "analysis_name": "Analysis",
                    "material_name": "Steel",
                    "material": {
                        "Name": "Steel",
                        "YoungsModulus": "210000 MPa",
                        "PoissonRatio": "0.30",
                        "Density": "7900 kg/m^3",
                    },
                    "output_path": str(fem_doc),
                    "overwrite": True,
                }
            ),
            "fem material create",
        )
        if fem_material["material"]["type_id"] != "App::MaterialObjectPython":
            raise RuntimeError(f"FEM material mismatch: {fem_material}")
        fem_fixed = assert_ok(
            service.definition_map()["freecad_fem_constraint_create"].handler(
                {
                    "document_path": str(fem_doc),
                    "analysis_name": "Analysis",
                    "constraint_type": "fixed",
                    "constraint_name": "FixedFace",
                    "references": [{"object_name": "FemBox", "sub_element": "Face1"}],
                    "output_path": str(fem_doc),
                    "overwrite": True,
                }
            ),
            "fem fixed constraint create",
        )
        if fem_fixed["constraint"]["type_id"] != "Fem::ConstraintFixed":
            raise RuntimeError(f"FEM fixed constraint mismatch: {fem_fixed}")
        fem_force = assert_ok(
            service.definition_map()["freecad_fem_constraint_create"].handler(
                {
                    "document_path": str(fem_doc),
                    "analysis_name": "Analysis",
                    "constraint_type": "force",
                    "constraint_name": "ForceFace",
                    "references": [{"object_name": "FemBox", "sub_element": "Face2"}],
                    "force": "1000 N",
                    "direction_reference": {"object_name": "FemBox", "sub_element": "Edge1"},
                    "output_path": str(fem_doc),
                    "overwrite": True,
                }
            ),
            "fem force constraint create",
        )
        if fem_force["constraint"]["type_id"] != "Fem::ConstraintForce":
            raise RuntimeError(f"FEM force constraint mismatch: {fem_force}")
        fem_inspect = assert_ok(
            service.definition_map()["freecad_fem_inspect"].handler({"document_path": str(fem_doc)}),
            "fem inspect",
        )
        if fem_inspect["analysis_count"] != 1 or fem_inspect["object_count"] < 4:
            raise RuntimeError(f"FEM inspect mismatch: {fem_inspect}")

    print("typed CAD smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
