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


def create_partdesign_rect_pad(
    service: CadToolService,
    document: Path,
    *,
    document_name: str,
    body_name: str,
    sketch_name: str,
    pad_name: str,
) -> dict:
    profile = assert_ok(
        service.definition_map()["freecad_sketch_profile_create"].handler(
            {
                "document_name": document_name,
                "sketch_name": sketch_name,
                "body_name": body_name,
                "attachment_plane": "XY",
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
                "lock_mode": "block",
                "require_fully_constrained": True,
                "output_path": str(document),
                "overwrite": True,
            }
        ),
        f"{document_name} base profile",
    )
    if not profile["attachment"]["attached"]:
        raise RuntimeError(f"{document_name} base profile was not attached: {profile}")
    pad = assert_ok(
        service.definition_map()["freecad_partdesign_pad"].handler(
            {
                "document_path": str(document),
                "body_name": body_name,
                "sketch_name": sketch_name,
                "pad_name": pad_name,
                "length": 10,
                "output_path": str(document),
                "overwrite": True,
            }
        ),
        f"{document_name} base pad",
    )
    if pad["pad"]["shape"]["solids"] != 1 or pad["body"]["partdesign"]["tip"] != pad_name:
        raise RuntimeError(f"{document_name} base pad did not produce a body solid: {pad}")
    return pad


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
        coordinates_2d_doc = temp / "coordinates_2d.FCStd"
        rectangle_loop_doc = temp / "rectangle_loop.FCStd"
        profile_builder_doc = temp / "profile_builder.FCStd"
        partdesign_doc = temp / "partdesign.FCStd"
        slot_pad_doc = temp / "slot_pad.FCStd"
        keyhole_pocket_doc = temp / "keyhole_pocket.FCStd"
        auto_sketch_doc = temp / "auto_sketch.FCStd"
        transform_sketch_doc = temp / "transform_sketch.FCStd"
        dimension_sketch_doc = temp / "dimension_sketch.FCStd"

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

        box_params = assert_ok(
            service.definition_map()["freecad_spreadsheet_create"].handler(
                {
                    "document_path": str(document),
                    "sheet_name": "params",
                    "rows": [
                        {"label": "box_length", "value": 6.0, "alias": "box_length"},
                        {"label": "box_offset", "value": "-2 mm", "alias": "box_offset"},
                    ],
                    "output_path": str(document),
                    "overwrite": True,
                }
            ),
            "spreadsheet_create box params",
        )
        if box_params["sheet"]["aliases"].get("box_length", {}).get("cell") != "B1":
            raise RuntimeError(f"spreadsheet alias was not created: {box_params}")
        box_expression = assert_ok(
            service.definition_map()["freecad_object_expression_set"].handler(
                {
                    "document_path": str(document),
                    "object_name": "Box",
                    "expressions": {
                        "Length": "params.box_length",
                        "Placement.Base.x": "params.box_offset",
                    },
                    "output_path": str(document),
                    "overwrite": True,
                }
            ),
            "object_expression_set box length",
        )
        box_bound = box_expression["object"]["shape"]["bound_box"]
        if box_bound["xmax"] - box_bound["xmin"] != 6.0:
            raise RuntimeError(f"box expression did not drive Length: {box_expression}")
        if box_expression["object"]["placement"]["base"][0] != -2.0:
            raise RuntimeError(f"negative spreadsheet quantity did not drive Placement.Base.x: {box_expression}")
        box_expressions = {
            item["path"]: item["expression"]
            for item in box_expression["after"]
        }
        if box_expressions.get("Length") != "params.box_length":
            raise RuntimeError(f"box expression was not reported: {box_expression}")

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

        assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "DimensionSketchSmoke",
                    "sketch_name": "DimensionSketch",
                    "output_path": str(dimension_sketch_doc),
                    "overwrite": True,
                }
            ),
            "dimension sketch create",
        )
        assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(dimension_sketch_doc),
                    "sketch_name": "DimensionSketch",
                    "geometry": [{"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]}],
                    "output_path": str(dimension_sketch_doc),
                    "overwrite": True,
                }
            ),
            "dimension sketch add geometry",
        )
        assert_ok(
            service.definition_map()["freecad_sketch_add_constraint"].handler(
                {
                    "document_path": str(dimension_sketch_doc),
                    "sketch_name": "DimensionSketch",
                    "constraints": [{"type": "DistanceX", "values": [0, 1, 0, 2, 10.0], "name": "width"}],
                    "output_path": str(dimension_sketch_doc),
                    "overwrite": True,
                }
            ),
            "dimension sketch distance constraint",
        )
        assert_ok(
            service.definition_map()["freecad_spreadsheet_create"].handler(
                {
                    "document_path": str(dimension_sketch_doc),
                    "sheet_name": "params",
                    "rows": [{"label": "width", "value": 12.5, "alias": "width"}],
                    "output_path": str(dimension_sketch_doc),
                    "overwrite": True,
                }
            ),
            "spreadsheet_create sketch params",
        )
        sketch_expression = assert_ok(
            service.definition_map()["freecad_object_expression_set"].handler(
                {
                    "document_path": str(dimension_sketch_doc),
                    "object_name": "DimensionSketch",
                    "expressions": {"Constraints[0]": "params.width"},
                    "output_path": str(dimension_sketch_doc),
                    "overwrite": True,
                }
            ),
            "object_expression_set sketch dimension",
        )
        sketch_constraints = sketch_expression["object"]["sketch"]["constraints"]
        if sketch_constraints[0]["value"] != 12.5:
            raise RuntimeError(f"sketch dimension expression did not update constraint value: {sketch_expression}")
        sketch_expressions = {
            item["path"]: item["expression"]
            for item in sketch_expression["after"]
        }
        if "params.width" not in {
            sketch_expressions.get("Constraints[0]"),
            sketch_expressions.get(".Constraints.width"),
        }:
            raise RuntimeError(f"sketch dimension expression was not reported: {sketch_expression}")

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
        for expected_type in ["rectangle_center", "rectangle_3_point", "triangle", "square", "hexagon", "slot_start_end_radius", "arc_slot", "keyhole"]:
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
            ({"type": "triangle", "center": [30, -10, 0], "radius": 3}, 4),
            ({"type": "square", "center": [38, -10, 0], "radius": 3}, 5),
            ({"type": "regular_polygon", "center": [32, 0, 0], "radius": 3, "sides": 6}, 7),
            ({"type": "hexagon", "center": [40, 0, 0], "corner": [43, 0, 0]}, 7),
            ({"type": "regular_polygon", "center": [48, 0, 0], "corner": [51, 0, 0], "sides": 6, "construction_circle": False}, 6),
            ({"type": "slot", "center": [45, 0, 0], "length": 8, "radius": 1.5}, 4),
            ({"type": "slot_start_end_radius", "start": [50, -10, 0], "end": [58, -8, 0], "radius": 1.5}, 4),
            ({"type": "arc_slot", "center": [66, -8, 0], "radius": 5, "width": 2, "start_angle": 0, "end_angle": {"degrees": 90}, "direction": "ccw"}, 4),
            ({"type": "keyhole", "circle_center": [72, 0, 0], "circle_radius": 3, "slot_end": [78, 0, 0], "slot_radius": 1}, 4),
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

        coordinates_2d_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "Coordinate2DSmoke",
                    "sketch_name": "Coordinate2DSketch",
                    "output_path": str(coordinates_2d_doc),
                    "overwrite": True,
                }
            ),
            "2d coordinate sketch create",
        )
        if coordinates_2d_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
            raise RuntimeError(f"2d coordinate sketch create failed: {coordinates_2d_sketch}")
        coordinates_2d_geometry = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(coordinates_2d_doc),
                    "sketch_name": "Coordinate2DSketch",
                    "geometry": [
                        {"type": "line", "start": [0, 0], "end": [6, 0]},
                        {"type": "line", "start": [6, 0], "end": [6, 4]},
                        {"type": "line", "start": [6, 4], "end": [0, 4]},
                        {"type": "line", "start": [0, 4], "end": [0, 0]},
                    ],
                    "connect_sequence": True,
                    "close_sequence": True,
                    "require_closed": True,
                    "output_path": str(coordinates_2d_doc),
                    "overwrite": True,
                }
            ),
            "2d coordinate sketch add geometry",
        )
        if coordinates_2d_geometry.get("closed_validation", {}).get("open_vertices"):
            raise RuntimeError(f"2d coordinate sketch is not closed: {coordinates_2d_geometry}")

        rectangle_loop_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "RectangleLoopSmoke",
                    "sketch_name": "RectangleLoopSketch",
                    "loops": [{"type": "rectangle", "origin": [0, 0], "width": 6, "height": 4}],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(rectangle_loop_doc),
                    "overwrite": True,
                }
            ),
            "rectangle loop sketch profile create",
        )
        if not rectangle_loop_profile["validation"]["ok"] or not rectangle_loop_profile["validation"]["pad_ready"]:
            raise RuntimeError(f"rectangle loop profile was not pad-ready: {rectangle_loop_profile}")
        if len(rectangle_loop_profile["loops"][0]["added_indices"]) != 4:
            raise RuntimeError(f"rectangle loop profile did not expand to four lines: {rectangle_loop_profile}")

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
                    "reversed": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign pocket",
        )
        if partdesign_pocket["pocket"]["shape"]["solids"] != 1 or partdesign_pocket["body"]["partdesign"]["tip"] != "Pocket":
            raise RuntimeError(f"partdesign pocket did not preserve a body solid: {partdesign_pocket}")
        if partdesign_pocket["pocket"]["shape"]["faces"] <= partdesign_pad["pad"]["shape"]["faces"]:
            raise RuntimeError(f"partdesign pocket did not cut visible topology: {partdesign_pocket}")
        tip_to_pad = assert_ok(
            service.definition_map()["freecad_object_set_properties"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "object_name": "Body",
                    "properties": {"Tip": {"$ref": "Pad"}},
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign body Tip set to Pad",
        )
        if tip_to_pad["changed"]["Tip"]["$ref"] != "Pad" or tip_to_pad["object"]["partdesign"]["tip"] != "Pad":
            raise RuntimeError(f"body Tip $ref property set failed: {tip_to_pad}")
        tip_to_pocket = assert_ok(
            service.definition_map()["freecad_object_set_properties"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "object_name": "Body",
                    "properties": {"Tip": {"$ref": "Pocket"}},
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign body Tip set to Pocket",
        )
        if tip_to_pocket["object"]["partdesign"]["tip"] != "Pocket":
            raise RuntimeError(f"body Tip restore to Pocket failed: {tip_to_pocket}")
        deleted_tip = assert_ok(
            service.definition_map()["freecad_object_delete"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "object_name": "Pocket",
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign current Tip delete",
        )
        if deleted_tip["tip_restorations"] != [{"body": "Body", "before_tip": "Pocket", "after_tip": "Pad", "restored": True}]:
            raise RuntimeError(f"body Tip was not restored before deleting current Tip: {deleted_tip}")
        body_after_tip_delete = next(obj for obj in deleted_tip["document"]["objects"] if obj["name"] == "Body")
        if body_after_tip_delete["partdesign"]["tip"] != "Pad":
            raise RuntimeError(f"body Tip after delete is not Pad: {deleted_tip}")

        slot_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "SlotPadSmoke",
                    "sketch_name": "SlotPadSketch",
                    "body_name": "SlotBody",
                    "attachment_plane": "XY",
                    "output_path": str(slot_pad_doc),
                    "overwrite": True,
                }
            ),
            "slot pad sketch create",
        )
        if not slot_sketch["attachment"]["attached"]:
            raise RuntimeError(f"slot sketch was not attached: {slot_sketch}")
        slot_profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(slot_pad_doc),
                    "sketch_name": "SlotPadSketch",
                    "profile": {"type": "slot_start_end_radius", "start": [1, 5, 0], "end": [8, 5, 0], "radius": 1.2},
                    "output_path": str(slot_pad_doc),
                    "overwrite": True,
                }
            ),
            "slot_start_end_radius pad profile",
        )
        if slot_profile["sketch"]["sketch"]["redundant_constraints"]:
            raise RuntimeError(f"slot profile produced redundant constraints: {slot_profile}")
        slot_validation = assert_ok(
            service.definition_map()["freecad_sketch_profile_validate"].handler(
                {
                    "document_path": str(slot_pad_doc),
                    "sketch_name": "SlotPadSketch",
                    "require_pad_ready": True,
                }
            ),
            "slot_start_end_radius profile validate",
        )
        if not slot_validation["validation"]["pad_ready"]:
            raise RuntimeError(f"slot_start_end_radius profile is not pad-ready: {slot_validation}")
        slot_pad = assert_ok(
            service.definition_map()["freecad_partdesign_pad"].handler(
                {
                    "document_path": str(slot_pad_doc),
                    "body_name": "SlotBody",
                    "sketch_name": "SlotPadSketch",
                    "attachment_plane": "XY",
                    "pad_name": "SlotPad",
                    "length": 4,
                    "output_path": str(slot_pad_doc),
                    "overwrite": True,
                }
            ),
            "slot_start_end_radius pad",
        )
        if slot_pad["pad"]["shape"]["solids"] != 1 or slot_pad["body"]["partdesign"]["tip"] != "SlotPad":
            raise RuntimeError(f"slot_start_end_radius Pad did not produce a solid: {slot_pad}")

        create_partdesign_rect_pad(
            service,
            keyhole_pocket_doc,
            document_name="KeyholePocketSmoke",
            body_name="KeyholeBody",
            sketch_name="KeyholeBaseSketch",
            pad_name="KeyholeBasePad",
        )
        keyhole_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(keyhole_pocket_doc),
                    "sketch_name": "KeyholeSketch",
                    "body_name": "KeyholeBody",
                    "attachment_plane": "XY",
                    "output_path": str(keyhole_pocket_doc),
                    "overwrite": True,
                }
            ),
            "keyhole sketch create",
        )
        if not keyhole_sketch["attachment"]["attached"]:
            raise RuntimeError(f"keyhole sketch was not attached: {keyhole_sketch}")
        keyhole_profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(keyhole_pocket_doc),
                    "sketch_name": "KeyholeSketch",
                    "profile": {"type": "keyhole", "circle_center": [3, 5, 0], "circle_radius": 1.5, "slot_end": [7, 5, 0], "slot_radius": 0.5},
                    "output_path": str(keyhole_pocket_doc),
                    "overwrite": True,
                }
            ),
            "keyhole profile",
        )
        if keyhole_profile["profile_type"] != "keyhole" or len(keyhole_profile["added_indices"]) != 4:
            raise RuntimeError(f"keyhole profile mismatch: {keyhole_profile}")
        keyhole_validation = assert_ok(
            service.definition_map()["freecad_sketch_profile_validate"].handler(
                {
                    "document_path": str(keyhole_pocket_doc),
                    "sketch_name": "KeyholeSketch",
                    "require_pad_ready": True,
                    "required_curve_types": ["arc"],
                    "minimum_curve_segments": 2,
                    "forbid_all_line_loops": True,
                }
            ),
            "keyhole profile validate",
        )
        if not keyhole_validation["validation"]["pad_ready"]:
            raise RuntimeError(f"keyhole profile is not pad-ready: {keyhole_validation}")
        keyhole_pocket = assert_ok(
            service.definition_map()["freecad_partdesign_pocket"].handler(
                {
                    "document_path": str(keyhole_pocket_doc),
                    "body_name": "KeyholeBody",
                    "sketch_name": "KeyholeSketch",
                    "attachment_plane": "XY",
                    "pocket_name": "KeyholePocket",
                    "length": 6,
                    "output_path": str(keyhole_pocket_doc),
                    "overwrite": True,
                }
            ),
            "keyhole pocket",
        )
        if keyhole_pocket["pocket"]["shape"]["solids"] != 1 or keyhole_pocket["body"]["partdesign"]["tip"] != "KeyholePocket":
            raise RuntimeError(f"keyhole Pocket did not preserve a body solid: {keyhole_pocket}")
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
        datum_plane = assert_ok(
            service.definition_map()["freecad_partdesign_datum_plane_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "Body",
                    "datum_plane_name": "OffsetPlane",
                    "attachment_plane": "XY",
                    "attachment_offset": 8,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign datum plane",
        )
        if datum_plane["datum_plane"]["type_id"] != "PartDesign::Plane":
            raise RuntimeError(f"partdesign datum plane was not created: {datum_plane}")
        if datum_plane["body"]["partdesign"]["tip"] != "Hole":
            raise RuntimeError(f"partdesign datum plane should not steal the solid Body Tip: {datum_plane}")
        offset_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "OffsetSketch",
                    "body_name": "Body",
                    "attachment_object": "OffsetPlane",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0, 0, 0], "end": [4, 0, 0]},
                                {"type": "line", "start": [4, 0, 0], "end": [4, 2, 0]},
                                {"type": "line", "start": [4, 2, 0], "end": [0, 2, 0]},
                                {"type": "line", "start": [0, 2, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign datum-attached sketch profile",
        )
        if offset_profile["attachment"].get("support_object") != "OffsetPlane":
            raise RuntimeError(f"offset sketch was not attached to datum plane: {offset_profile}")
        revolution_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "RevolutionSketch",
                    "body_name": "RevolveBody",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [9, 0, 0], "end": [10, 0, 0]},
                                {"type": "line", "start": [10, 0, 0], "end": [10, 5, 0]},
                                {"type": "line", "start": [10, 5, 0], "end": [9, 5, 0]},
                                {"type": "line", "start": [9, 5, 0], "end": [9, 0, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign revolution sketch profile",
        )
        if not revolution_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign revolution profile was not attached: {revolution_profile}")
        partdesign_revolution = assert_ok(
            service.definition_map()["freecad_partdesign_revolution"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "RevolveBody",
                    "sketch_name": "RevolutionSketch",
                    "attachment_plane": "XY",
                    "revolution_name": "Revolution",
                    "reference_axis": "sketch_v_axis",
                    "angle": 180,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign revolution",
        )
        if partdesign_revolution["revolution"]["shape"]["solids"] != 1 or partdesign_revolution["body"]["partdesign"]["tip"] != "Revolution":
            raise RuntimeError(f"partdesign revolution did not produce a body solid: {partdesign_revolution}")
        recipe_revolution_doc = temp / "partdesign_recipe_revolution.FCStd"
        recipe_revolution = assert_ok(
            service.definition_map()["freecad_partdesign_profile_feature_create"].handler(
                {
                    "document_name": "RecipeRevolutionSmoke",
                    "body_name": "RecipeRevolveBody",
                    "sketch_name": "RecipeRevolveSketch",
                    "feature_kind": "revolution",
                    "feature_name": "RecipeRevolution",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [4, 0, 0], "end": [5, 0, 0]},
                                {"type": "line", "start": [5, 0, 0], "end": [5, 3, 0]},
                                {"type": "line", "start": [5, 3, 0], "end": [4, 3, 0]},
                                {"type": "line", "start": [4, 3, 0], "end": [4, 0, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "reference_axis": "sketch_v_axis",
                    "angle": 180,
                    "output_path": str(recipe_revolution_doc),
                    "overwrite": True,
                }
            ),
            "partdesign profile feature revolution recipe",
        )
        if recipe_revolution["revolution"]["shape"]["solids"] != 1 or recipe_revolution["body"]["partdesign"]["tip"] != "RecipeRevolution":
            raise RuntimeError(f"partdesign profile feature recipe did not create a solid revolution: {recipe_revolution}")
        loft_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "LoftProfileSketch",
                    "body_name": "LoftBody",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0, 0, 0], "end": [4, 0, 0]},
                                {"type": "line", "start": [4, 0, 0], "end": [4, 2, 0]},
                                {"type": "line", "start": [4, 2, 0], "end": [0, 2, 0]},
                                {"type": "line", "start": [0, 2, 0], "end": [0, 0, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign loft profile sketch",
        )
        if not loft_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign loft profile was not attached: {loft_profile}")
        loft_plane = assert_ok(
            service.definition_map()["freecad_partdesign_datum_plane_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "LoftBody",
                    "datum_plane_name": "LoftSectionPlane",
                    "attachment_plane": "XY",
                    "attachment_offset": 6,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign loft datum plane",
        )
        if loft_plane["datum_plane"]["type_id"] != "PartDesign::Plane":
            raise RuntimeError(f"partdesign loft datum plane was not created: {loft_plane}")
        loft_section = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "LoftSectionSketch",
                    "body_name": "LoftBody",
                    "attachment_object": "LoftSectionPlane",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0.5, 0.25, 0], "end": [3.5, 0.25, 0]},
                                {"type": "line", "start": [3.5, 0.25, 0], "end": [3.5, 1.75, 0]},
                                {"type": "line", "start": [3.5, 1.75, 0], "end": [0.5, 1.75, 0]},
                                {"type": "line", "start": [0.5, 1.75, 0], "end": [0.5, 0.25, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign loft section sketch",
        )
        if loft_section["attachment"].get("support_object") != "LoftSectionPlane":
            raise RuntimeError(f"partdesign loft section was not attached to datum plane: {loft_section}")
        additive_loft = assert_ok(
            service.definition_map()["freecad_partdesign_additive_loft"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "LoftBody",
                    "profile_name": "LoftProfileSketch",
                    "sections": ["LoftSectionSketch"],
                    "loft_name": "AdditiveLoft",
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive loft",
        )
        if additive_loft["loft"]["shape"]["solids"] != 1 or additive_loft["body"]["partdesign"]["tip"] != "AdditiveLoft":
            raise RuntimeError(f"partdesign additive loft did not produce a body solid: {additive_loft}")
        subtractive_loft_base_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "SubtractiveLoftBaseSketch",
                    "body_name": "SubtractiveLoftBody",
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
            "partdesign subtractive loft base profile",
        )
        if not subtractive_loft_base_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign subtractive loft base profile was not attached: {subtractive_loft_base_profile}")
        subtractive_loft_pad = assert_ok(
            service.definition_map()["freecad_partdesign_pad"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "SubtractiveLoftBody",
                    "sketch_name": "SubtractiveLoftBaseSketch",
                    "attachment_plane": "XY",
                    "pad_name": "SubtractiveLoftPad",
                    "length": 6,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive loft base pad",
        )
        if subtractive_loft_pad["pad"]["shape"]["solids"] != 1 or subtractive_loft_pad["body"]["partdesign"]["tip"] != "SubtractiveLoftPad":
            raise RuntimeError(f"partdesign subtractive loft base pad did not produce a body solid: {subtractive_loft_pad}")
        subtractive_loft_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "SubtractiveLoftProfileSketch",
                    "body_name": "SubtractiveLoftBody",
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
            "partdesign subtractive loft profile sketch",
        )
        if not subtractive_loft_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign subtractive loft profile was not attached: {subtractive_loft_profile}")
        subtractive_loft_plane = assert_ok(
            service.definition_map()["freecad_partdesign_datum_plane_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "SubtractiveLoftBody",
                    "datum_plane_name": "SubtractiveLoftSectionPlane",
                    "attachment_plane": "XY",
                    "attachment_offset": 5,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive loft datum plane",
        )
        if subtractive_loft_plane["datum_plane"]["type_id"] != "PartDesign::Plane":
            raise RuntimeError(f"partdesign subtractive loft datum plane was not created: {subtractive_loft_plane}")
        subtractive_loft_section = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "SubtractiveLoftSectionSketch",
                    "body_name": "SubtractiveLoftBody",
                    "attachment_object": "SubtractiveLoftSectionPlane",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [3, 1.25, 0], "end": [5, 1.25, 0]},
                                {"type": "line", "start": [5, 1.25, 0], "end": [5, 2.75, 0]},
                                {"type": "line", "start": [5, 2.75, 0], "end": [3, 2.75, 0]},
                                {"type": "line", "start": [3, 2.75, 0], "end": [3, 1.25, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive loft section sketch",
        )
        if subtractive_loft_section["attachment"].get("support_object") != "SubtractiveLoftSectionPlane":
            raise RuntimeError(f"partdesign subtractive loft section was not attached to datum plane: {subtractive_loft_section}")
        subtractive_loft = assert_ok(
            service.definition_map()["freecad_partdesign_subtractive_loft"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "SubtractiveLoftBody",
                    "profile_name": "SubtractiveLoftProfileSketch",
                    "sections": ["SubtractiveLoftSectionSketch"],
                    "loft_name": "SubtractiveLoft",
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive loft",
        )
        if subtractive_loft["loft"]["shape"]["solids"] != 1 or subtractive_loft["body"]["partdesign"]["tip"] != "SubtractiveLoft":
            raise RuntimeError(f"partdesign subtractive loft did not preserve a body solid: {subtractive_loft}")
        additive_pipe_doc = temp / "partdesign_additive_pipe.FCStd"
        auxiliary_pipe_doc = temp / "partdesign_auxiliary_pipe.FCStd"
        subtractive_pipe_doc = temp / "partdesign_subtractive_pipe.FCStd"
        fillet_doc = temp / "partdesign_fillet.FCStd"
        chamfer_doc = temp / "partdesign_chamfer.FCStd"
        thickness_doc = temp / "partdesign_thickness.FCStd"
        draft_doc = temp / "partdesign_draft.FCStd"
        linear_pattern_doc = temp / "partdesign_linear_pattern.FCStd"
        linear_pattern_2d_doc = temp / "partdesign_linear_pattern_2d.FCStd"
        polar_pattern_doc = temp / "partdesign_polar_pattern.FCStd"
        mirrored_doc = temp / "partdesign_mirrored.FCStd"
        additive_pipe_profile_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "AdditivePipeSmoke",
                    "sketch_name": "AdditivePipeProfileSketch",
                    "body_name": "AdditivePipeBody",
                    "attachment_plane": "XY",
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe profile sketch",
        )
        if not additive_pipe_profile_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign additive pipe profile sketch was not attached: {additive_pipe_profile_sketch}")
        additive_pipe_profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "sketch_name": "AdditivePipeProfileSketch",
                    "profile": {"type": "circle", "center": [0, 0, 0], "radius": 1},
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe circle profile",
        )
        if additive_pipe_profile["profile_type"] != "circle":
            raise RuntimeError(f"partdesign additive pipe profile was not a circle: {additive_pipe_profile}")
        additive_pipe_section_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "sketch_name": "AdditivePipeSectionSketch",
                    "body_name": "AdditivePipeBody",
                    "attachment_plane": "XY",
                    "attachment_offset_vector": [0, 0, 2],
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe section sketch",
        )
        if not additive_pipe_section_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign additive pipe section sketch was not attached: {additive_pipe_section_sketch}")
        additive_pipe_section = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "sketch_name": "AdditivePipeSectionSketch",
                    "profile": {"type": "circle", "center": [0, 0, 0], "radius": 0.5},
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe section circle",
        )
        if additive_pipe_section["profile_type"] != "circle":
            raise RuntimeError(f"partdesign additive pipe section was not a circle: {additive_pipe_section}")
        additive_pipe_spine_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "sketch_name": "AdditivePipeSpineSketch",
                    "body_name": "AdditivePipeBody",
                    "attachment_plane": "XZ",
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe spine sketch",
        )
        if not additive_pipe_spine_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign additive pipe spine sketch was not attached: {additive_pipe_spine_sketch}")
        additive_pipe_spine = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "sketch_name": "AdditivePipeSpineSketch",
                    "geometry": [{"type": "line", "start": [0, 0, 0], "end": [0, 2, 0]}],
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe spine line",
        )
        if len(additive_pipe_spine["added_indices"]) != 1:
            raise RuntimeError(f"partdesign additive pipe spine line was not added: {additive_pipe_spine}")
        additive_pipe_spine_constraints = assert_ok(
            service.definition_map()["freecad_sketch_add_constraint"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "sketch_name": "AdditivePipeSpineSketch",
                    "constraints": [
                        {"type": "Coincident", "values": [0, 1, -1, 1]},
                        {"type": "PointOnObject", "values": [0, 2, -2]},
                        {"type": "DistanceY", "values": [0, 1, 0, 2, 2]},
                    ],
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe spine constraints",
        )
        if len(additive_pipe_spine_constraints["added_indices"]) != 3:
            raise RuntimeError(f"partdesign additive pipe spine constraints were not added: {additive_pipe_spine_constraints}")
        additive_pipe = assert_ok(
            service.definition_map()["freecad_partdesign_additive_pipe"].handler(
                {
                    "document_path": str(additive_pipe_doc),
                    "body_name": "AdditivePipeBody",
                    "profile_name": "AdditivePipeProfileSketch",
                    "spine_name": "AdditivePipeSpineSketch",
                    "sections": ["AdditivePipeSectionSketch"],
                    "pipe_name": "AdditivePipe",
                    "output_path": str(additive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign additive pipe",
        )
        if additive_pipe["pipe"]["shape"]["solids"] != 1 or additive_pipe["body"]["partdesign"]["tip"] != "AdditivePipe":
            raise RuntimeError(f"partdesign additive pipe did not produce a body solid: {additive_pipe}")
        additive_pipe_partdesign = additive_pipe["pipe"]["partdesign"]
        if additive_pipe_partdesign["transformation"] != "Multisection" or len(additive_pipe_partdesign["sections"]) != 1:
            raise RuntimeError(f"partdesign additive pipe did not keep multisection scaling: {additive_pipe}")
        recipe_pipe_doc = temp / "partdesign_recipe_pipe.FCStd"
        recipe_pipe = assert_ok(
            service.definition_map()["freecad_partdesign_sweep_feature_create"].handler(
                {
                    "document_name": "RecipePipeSmoke",
                    "body_name": "RecipePipeBody",
                    "feature_kind": "additive_pipe",
                    "profile_sketch_name": "RecipePipeProfile",
                    "profile": {"type": "circle", "center": [0, 0, 0], "radius": 1},
                    "profile_attachment_plane": "XY",
                    "spine_sketch_name": "RecipePipeSpine",
                    "spine_attachment_plane": "XZ",
                    "spine_geometry": [{"type": "line", "start": [0, 0, 0], "end": [0, 3, 0]}],
                    "spine_constraints": [
                        {"type": "Coincident", "values": [0, 1, -1, 1]},
                        {"type": "PointOnObject", "values": [0, 2, -2]},
                        {"type": "DistanceY", "values": [0, 1, 0, 2, 3]},
                    ],
                    "pipe_name": "RecipePipe",
                    "output_path": str(recipe_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign sweep feature recipe",
        )
        if recipe_pipe["pipe"]["shape"]["solids"] != 1 or recipe_pipe["body"]["partdesign"]["tip"] != "RecipePipe":
            raise RuntimeError(f"partdesign sweep recipe did not create a solid pipe: {recipe_pipe}")
        auxiliary_pipe_profile_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_name": "AuxiliaryPipeSmoke",
                    "sketch_name": "AuxiliaryPipeProfileSketch",
                    "body_name": "AuxiliaryPipeBody",
                    "attachment_plane": "XY",
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe profile sketch",
        )
        if not auxiliary_pipe_profile_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign auxiliary pipe profile sketch was not attached: {auxiliary_pipe_profile_sketch}")
        auxiliary_pipe_profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "sketch_name": "AuxiliaryPipeProfileSketch",
                    "profile": {"type": "circle", "center": [0, 0, 0], "radius": 1},
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe circle profile",
        )
        if auxiliary_pipe_profile["profile_type"] != "circle":
            raise RuntimeError(f"partdesign auxiliary pipe profile was not a circle: {auxiliary_pipe_profile}")
        auxiliary_pipe_spine_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "sketch_name": "AuxiliaryPipeSpineSketch",
                    "body_name": "AuxiliaryPipeBody",
                    "attachment_plane": "XZ",
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe spine sketch",
        )
        if not auxiliary_pipe_spine_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign auxiliary pipe spine sketch was not attached: {auxiliary_pipe_spine_sketch}")
        auxiliary_pipe_spine = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "sketch_name": "AuxiliaryPipeSpineSketch",
                    "geometry": [{"type": "line", "start": [0, 0, 0], "end": [0, 2, 0]}],
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe spine line",
        )
        if len(auxiliary_pipe_spine["added_indices"]) != 1:
            raise RuntimeError(f"partdesign auxiliary pipe spine line was not added: {auxiliary_pipe_spine}")
        auxiliary_pipe_spine_constraints = assert_ok(
            service.definition_map()["freecad_sketch_add_constraint"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "sketch_name": "AuxiliaryPipeSpineSketch",
                    "constraints": [
                        {"type": "Coincident", "values": [0, 1, -1, 1]},
                        {"type": "PointOnObject", "values": [0, 2, -2]},
                        {"type": "DistanceY", "values": [0, 1, 0, 2, 2]},
                    ],
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe spine constraints",
        )
        if len(auxiliary_pipe_spine_constraints["added_indices"]) != 3:
            raise RuntimeError(f"partdesign auxiliary pipe spine constraints were not added: {auxiliary_pipe_spine_constraints}")
        auxiliary_pipe_aux_spine_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "sketch_name": "AuxiliaryPipeAuxSpineSketch",
                    "body_name": "AuxiliaryPipeBody",
                    "attachment_plane": "XZ",
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe auxiliary spine sketch",
        )
        if not auxiliary_pipe_aux_spine_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign auxiliary pipe auxiliary spine sketch was not attached: {auxiliary_pipe_aux_spine_sketch}")
        auxiliary_pipe_aux_spine = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "sketch_name": "AuxiliaryPipeAuxSpineSketch",
                    "geometry": [{"type": "line", "start": [1, 0, 0], "end": [1, 2, 0]}],
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe auxiliary spine line",
        )
        if len(auxiliary_pipe_aux_spine["added_indices"]) != 1:
            raise RuntimeError(f"partdesign auxiliary pipe auxiliary spine line was not added: {auxiliary_pipe_aux_spine}")
        auxiliary_pipe = assert_ok(
            service.definition_map()["freecad_partdesign_additive_pipe"].handler(
                {
                    "document_path": str(auxiliary_pipe_doc),
                    "body_name": "AuxiliaryPipeBody",
                    "profile_name": "AuxiliaryPipeProfileSketch",
                    "spine_name": "AuxiliaryPipeSpineSketch",
                    "auxiliary_spine_name": "AuxiliaryPipeAuxSpineSketch",
                    "auxiliary_curvilinear": True,
                    "pipe_name": "AuxiliaryPipe",
                    "output_path": str(auxiliary_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign auxiliary pipe",
        )
        if auxiliary_pipe["pipe"]["shape"]["solids"] != 1 or auxiliary_pipe["body"]["partdesign"]["tip"] != "AuxiliaryPipe":
            raise RuntimeError(f"partdesign auxiliary pipe did not produce a body solid: {auxiliary_pipe}")
        auxiliary_pipe_partdesign = auxiliary_pipe["pipe"]["partdesign"]
        if auxiliary_pipe_partdesign["mode"] != "Auxiliary" or auxiliary_pipe_partdesign["auxiliary_spine"]["object"] != "AuxiliaryPipeAuxSpineSketch":
            raise RuntimeError(f"partdesign auxiliary pipe did not keep auxiliary orientation: {auxiliary_pipe}")
        subtractive_pipe_base_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_name": "SubtractivePipeSmoke",
                    "sketch_name": "SubtractivePipeBaseSketch",
                    "body_name": "SubtractivePipeBody",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [-5, -5, 0], "end": [5, -5, 0]},
                                {"type": "line", "start": [5, -5, 0], "end": [5, 5, 0]},
                                {"type": "line", "start": [5, 5, 0], "end": [-5, 5, 0]},
                                {"type": "line", "start": [-5, 5, 0], "end": [-5, -5, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe base profile",
        )
        if not subtractive_pipe_base_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign subtractive pipe base profile was not attached: {subtractive_pipe_base_profile}")
        subtractive_pipe_pad = assert_ok(
            service.definition_map()["freecad_partdesign_pad"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "body_name": "SubtractivePipeBody",
                    "sketch_name": "SubtractivePipeBaseSketch",
                    "attachment_plane": "XY",
                    "pad_name": "SubtractivePipePad",
                    "length": 2,
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe base pad",
        )
        if subtractive_pipe_pad["pad"]["shape"]["solids"] != 1 or subtractive_pipe_pad["body"]["partdesign"]["tip"] != "SubtractivePipePad":
            raise RuntimeError(f"partdesign subtractive pipe base pad did not produce a body solid: {subtractive_pipe_pad}")
        subtractive_pipe_profile_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "sketch_name": "SubtractivePipeProfileSketch",
                    "body_name": "SubtractivePipeBody",
                    "attachment_plane": "XY",
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe profile sketch",
        )
        if not subtractive_pipe_profile_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign subtractive pipe profile sketch was not attached: {subtractive_pipe_profile_sketch}")
        subtractive_pipe_profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "sketch_name": "SubtractivePipeProfileSketch",
                    "profile": {"type": "circle", "center": [0, 0, 0], "radius": 1},
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe circle profile",
        )
        if subtractive_pipe_profile["profile_type"] != "circle":
            raise RuntimeError(f"partdesign subtractive pipe profile was not a circle: {subtractive_pipe_profile}")
        subtractive_pipe_spine_sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "sketch_name": "SubtractivePipeSpineSketch",
                    "body_name": "SubtractivePipeBody",
                    "attachment_plane": "XZ",
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe spine sketch",
        )
        if not subtractive_pipe_spine_sketch["attachment"]["attached"]:
            raise RuntimeError(f"partdesign subtractive pipe spine sketch was not attached: {subtractive_pipe_spine_sketch}")
        subtractive_pipe_spine = assert_ok(
            service.definition_map()["freecad_sketch_add_geometry"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "sketch_name": "SubtractivePipeSpineSketch",
                    "geometry": [{"type": "line", "start": [0, 0, 0], "end": [0, 2, 0]}],
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe spine line",
        )
        if len(subtractive_pipe_spine["added_indices"]) != 1:
            raise RuntimeError(f"partdesign subtractive pipe spine line was not added: {subtractive_pipe_spine}")
        subtractive_pipe_spine_constraints = assert_ok(
            service.definition_map()["freecad_sketch_add_constraint"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "sketch_name": "SubtractivePipeSpineSketch",
                    "constraints": [
                        {"type": "Coincident", "values": [0, 1, -1, 1]},
                        {"type": "PointOnObject", "values": [0, 2, -2]},
                        {"type": "DistanceY", "values": [0, 1, 0, 2, 2]},
                    ],
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe spine constraints",
        )
        if len(subtractive_pipe_spine_constraints["added_indices"]) != 3:
            raise RuntimeError(f"partdesign subtractive pipe spine constraints were not added: {subtractive_pipe_spine_constraints}")
        subtractive_pipe = assert_ok(
            service.definition_map()["freecad_partdesign_subtractive_pipe"].handler(
                {
                    "document_path": str(subtractive_pipe_doc),
                    "body_name": "SubtractivePipeBody",
                    "profile_name": "SubtractivePipeProfileSketch",
                    "spine_name": "SubtractivePipeSpineSketch",
                    "pipe_name": "SubtractivePipe",
                    "output_path": str(subtractive_pipe_doc),
                    "overwrite": True,
                }
            ),
            "partdesign subtractive pipe",
        )
        if subtractive_pipe["pipe"]["shape"]["solids"] != 1 or subtractive_pipe["body"]["partdesign"]["tip"] != "SubtractivePipe":
            raise RuntimeError(f"partdesign subtractive pipe did not preserve a body solid: {subtractive_pipe}")
        create_partdesign_rect_pad(
            service,
            fillet_doc,
            document_name="FilletSmoke",
            body_name="FilletBody",
            sketch_name="FilletBaseSketch",
            pad_name="FilletBasePad",
        )
        fillet = assert_ok(
            service.definition_map()["freecad_partdesign_fillet"].handler(
                {
                    "document_path": str(fillet_doc),
                    "body_name": "FilletBody",
                    "base_feature_name": "FilletBasePad",
                    "use_all_edges": True,
                    "radius": 0.5,
                    "fillet_name": "Fillet",
                    "output_path": str(fillet_doc),
                    "overwrite": True,
                }
            ),
            "partdesign fillet",
        )
        if fillet["dressup"]["shape"]["solids"] != 1 or fillet["body"]["partdesign"]["tip"] != "Fillet":
            raise RuntimeError(f"partdesign fillet did not produce a body solid: {fillet}")
        if not fillet["dressup"]["partdesign"]["use_all_edges"]:
            raise RuntimeError(f"partdesign fillet did not keep UseAllEdges: {fillet}")
        create_partdesign_rect_pad(
            service,
            chamfer_doc,
            document_name="ChamferSmoke",
            body_name="ChamferBody",
            sketch_name="ChamferBaseSketch",
            pad_name="ChamferBasePad",
        )
        chamfer = assert_ok(
            service.definition_map()["freecad_partdesign_chamfer"].handler(
                {
                    "document_path": str(chamfer_doc),
                    "body_name": "ChamferBody",
                    "base_feature_name": "ChamferBasePad",
                    "use_all_edges": True,
                    "distance": 0.5,
                    "chamfer_name": "Chamfer",
                    "output_path": str(chamfer_doc),
                    "overwrite": True,
                }
            ),
            "partdesign chamfer",
        )
        if chamfer["dressup"]["shape"]["solids"] != 1 or chamfer["body"]["partdesign"]["tip"] != "Chamfer":
            raise RuntimeError(f"partdesign chamfer did not produce a body solid: {chamfer}")
        if not chamfer["dressup"]["partdesign"]["use_all_edges"]:
            raise RuntimeError(f"partdesign chamfer did not keep UseAllEdges: {chamfer}")
        create_partdesign_rect_pad(
            service,
            thickness_doc,
            document_name="ThicknessSmoke",
            body_name="ThicknessBody",
            sketch_name="ThicknessBaseSketch",
            pad_name="ThicknessBasePad",
        )
        thickness = assert_ok(
            service.definition_map()["freecad_partdesign_thickness"].handler(
                {
                    "document_path": str(thickness_doc),
                    "body_name": "ThicknessBody",
                    "base_feature_name": "ThicknessBasePad",
                    "face_name": "Face1",
                    "thickness": 0.5,
                    "reversed": True,
                    "thickness_name": "Thickness",
                    "output_path": str(thickness_doc),
                    "overwrite": True,
                }
            ),
            "partdesign thickness",
        )
        if thickness["dressup"]["shape"]["solids"] != 1 or thickness["body"]["partdesign"]["tip"] != "Thickness":
            raise RuntimeError(f"partdesign thickness did not produce a body solid: {thickness}")
        if not thickness["dressup"]["partdesign"]["reversed"]:
            raise RuntimeError(f"partdesign thickness did not keep reversed flag: {thickness}")
        create_partdesign_rect_pad(
            service,
            draft_doc,
            document_name="DraftSmoke",
            body_name="DraftBody",
            sketch_name="DraftBaseSketch",
            pad_name="DraftBasePad",
        )
        draft = assert_ok(
            service.definition_map()["freecad_partdesign_draft"].handler(
                {
                    "document_path": str(draft_doc),
                    "body_name": "DraftBody",
                    "base_feature_name": "DraftBasePad",
                    "face_name": "Face6",
                    "neutral_plane_name": "YZ_Plane",
                    "pull_direction_name": "X_Axis",
                    "angle": 5,
                    "reversed": False,
                    "draft_name": "Draft",
                    "output_path": str(draft_doc),
                    "overwrite": True,
                }
            ),
            "partdesign draft",
        )
        if draft["dressup"]["shape"]["solids"] != 1 or draft["body"]["partdesign"]["tip"] != "Draft":
            raise RuntimeError(f"partdesign draft did not produce a body solid: {draft}")
        if draft["dressup"]["partdesign"]["neutral_plane"]["object"] != "YZ_Plane":
            raise RuntimeError(f"partdesign draft did not keep neutral plane: {draft}")
        create_partdesign_rect_pad(
            service,
            linear_pattern_doc,
            document_name="LinearPatternSmoke",
            body_name="LinearPatternBody",
            sketch_name="LinearPatternBaseSketch",
            pad_name="LinearPatternBasePad",
        )
        linear_pattern = assert_ok(
            service.definition_map()["freecad_partdesign_linear_pattern"].handler(
                {
                    "document_path": str(linear_pattern_doc),
                    "body_name": "LinearPatternBody",
                    "original_feature_name": "LinearPatternBasePad",
                    "direction_axis": "x_axis",
                    "length": 2,
                    "occurrences": 2,
                    "linear_pattern_name": "LinearPattern",
                    "output_path": str(linear_pattern_doc),
                    "overwrite": True,
                }
            ),
            "partdesign linear pattern",
        )
        if linear_pattern["transform"]["shape"]["solids"] != 1 or linear_pattern["body"]["partdesign"]["tip"] != "LinearPattern":
            raise RuntimeError(f"partdesign linear pattern did not produce a body solid: {linear_pattern}")
        if linear_pattern["transform"]["partdesign"]["direction"]["object"] != "X_Axis":
            raise RuntimeError(f"partdesign linear pattern did not keep X direction: {linear_pattern}")
        if linear_pattern["transform"]["partdesign"]["occurrences"] != 2:
            raise RuntimeError(f"partdesign linear pattern did not keep occurrences: {linear_pattern}")
        create_partdesign_rect_pad(
            service,
            linear_pattern_2d_doc,
            document_name="LinearPattern2DSmoke",
            body_name="LinearPattern2DBody",
            sketch_name="LinearPattern2DBaseSketch",
            pad_name="LinearPattern2DBasePad",
        )
        linear_pattern_2d = assert_ok(
            service.definition_map()["freecad_partdesign_linear_pattern"].handler(
                {
                    "document_path": str(linear_pattern_2d_doc),
                    "body_name": "LinearPattern2DBody",
                    "original_feature_name": "LinearPattern2DBasePad",
                    "direction_axis": "x_axis",
                    "direction2_axis": "y_axis",
                    "length": 20,
                    "length2": 20,
                    "occurrences": 2,
                    "occurrences2": 2,
                    "linear_pattern_name": "LinearPattern2D",
                    "output_path": str(linear_pattern_2d_doc),
                    "overwrite": True,
                }
            ),
            "partdesign 2d linear pattern",
        )
        linear_pattern_2d_shape = linear_pattern_2d["transform"]["shape"]
        linear_pattern_2d_pd = linear_pattern_2d["transform"]["partdesign"]
        linear_pattern_2d_box = linear_pattern_2d_shape["bound_box"]
        if linear_pattern_2d_shape["solids"] != 4 or linear_pattern_2d["body"]["partdesign"]["tip"] != "LinearPattern2D":
            raise RuntimeError(f"partdesign 2d linear pattern did not create a 2x2 transform: {linear_pattern_2d}")
        if linear_pattern_2d_pd["direction2"]["object"] != "Y_Axis" or linear_pattern_2d_pd["occurrences2"] != 2:
            raise RuntimeError(f"partdesign 2d linear pattern did not keep second direction: {linear_pattern_2d}")
        if linear_pattern_2d_box["xmax"] < 29.9 or linear_pattern_2d_box["ymax"] < 29.9:
            raise RuntimeError(f"partdesign 2d linear pattern did not expand in both directions: {linear_pattern_2d}")
        create_partdesign_rect_pad(
            service,
            polar_pattern_doc,
            document_name="PolarPatternSmoke",
            body_name="PolarPatternBody",
            sketch_name="PolarPatternBaseSketch",
            pad_name="PolarPatternBasePad",
        )
        polar_pattern = assert_ok(
            service.definition_map()["freecad_partdesign_polar_pattern"].handler(
                {
                    "document_path": str(polar_pattern_doc),
                    "body_name": "PolarPatternBody",
                    "original_feature_name": "PolarPatternBasePad",
                    "axis": "z_axis",
                    "angle": 30,
                    "occurrences": 2,
                    "polar_pattern_name": "PolarPattern",
                    "output_path": str(polar_pattern_doc),
                    "overwrite": True,
                }
            ),
            "partdesign polar pattern",
        )
        if polar_pattern["transform"]["shape"]["solids"] != 1 or polar_pattern["body"]["partdesign"]["tip"] != "PolarPattern":
            raise RuntimeError(f"partdesign polar pattern did not produce a body solid: {polar_pattern}")
        if polar_pattern["transform"]["partdesign"]["axis"]["object"] != "Z_Axis":
            raise RuntimeError(f"partdesign polar pattern did not keep Z axis: {polar_pattern}")
        if polar_pattern["transform"]["partdesign"]["occurrences"] != 2:
            raise RuntimeError(f"partdesign polar pattern did not keep occurrences: {polar_pattern}")
        create_partdesign_rect_pad(
            service,
            mirrored_doc,
            document_name="MirroredSmoke",
            body_name="MirroredBody",
            sketch_name="MirroredBaseSketch",
            pad_name="MirroredBasePad",
        )
        mirrored = assert_ok(
            service.definition_map()["freecad_partdesign_mirrored"].handler(
                {
                    "document_path": str(mirrored_doc),
                    "body_name": "MirroredBody",
                    "original_feature_name": "MirroredBasePad",
                    "mirror_plane": "xy_plane",
                    "mirrored_name": "Mirrored",
                    "output_path": str(mirrored_doc),
                    "overwrite": True,
                }
            ),
            "partdesign mirrored",
        )
        if mirrored["transform"]["shape"]["solids"] != 1 or mirrored["body"]["partdesign"]["tip"] != "Mirrored":
            raise RuntimeError(f"partdesign mirrored did not produce a body solid: {mirrored}")
        if mirrored["transform"]["partdesign"]["mirror_plane"]["object"] != "XY_Plane":
            raise RuntimeError(f"partdesign mirrored did not keep mirror plane: {mirrored}")
        groove_profile = assert_ok(
            service.definition_map()["freecad_sketch_profile_create"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "sketch_name": "GrooveSketch",
                    "body_name": "Body",
                    "attachment_plane": "XY",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [6.5, 1, 0], "end": [7.5, 1, 0]},
                                {"type": "line", "start": [7.5, 1, 0], "end": [7.5, 3, 0]},
                                {"type": "line", "start": [7.5, 3, 0], "end": [6.5, 3, 0]},
                                {"type": "line", "start": [6.5, 3, 0], "end": [6.5, 1, 0]},
                            ],
                        }
                    ],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign groove sketch profile",
        )
        if not groove_profile["attachment"]["attached"]:
            raise RuntimeError(f"partdesign groove profile was not attached: {groove_profile}")
        partdesign_groove = assert_ok(
            service.definition_map()["freecad_partdesign_groove"].handler(
                {
                    "document_path": str(partdesign_doc),
                    "body_name": "Body",
                    "sketch_name": "GrooveSketch",
                    "attachment_plane": "XY",
                    "groove_name": "Groove",
                    "reference_axis": "sketch_v_axis",
                    "angle": 180,
                    "output_path": str(partdesign_doc),
                    "overwrite": True,
                }
            ),
            "partdesign groove",
        )
        if partdesign_groove["groove"]["shape"]["solids"] != 1 or partdesign_groove["body"]["partdesign"]["tip"] != "Groove":
            raise RuntimeError(f"partdesign groove did not preserve a body solid: {partdesign_groove}")
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
