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
        imported = temp / "mesh.FCStd"

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

        assembly_doc = temp / "assembly.FCStd"
        assembly = assert_ok(
            service.definition_map()["freecad_assembly_create"].handler(
                {"document_name": "AssemblySmoke", "output_path": str(assembly_doc), "overwrite": True}
            ),
            "assembly_create",
        )
        if assembly["assembly"]["type_id"] != "Assembly::AssemblyObject":
            raise RuntimeError(f"assembly type mismatch: {assembly}")

    print("typed CAD smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
