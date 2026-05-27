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

    print("typed CAD smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
