#!/usr/bin/env python3
"""Real FreeCAD smoke for generated complex document/object fixtures."""

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
        message = "fixture document smoke SKIPPED: FreeCAD runtime env not configured"
        if os.environ.get("FREECAD_MCP_REQUIRE_RUNTIME") == "1":
            raise RuntimeError(message)
        print(message)
        return 0

    service = CadToolService()
    with tempfile.TemporaryDirectory(prefix="freecad-mcp-fixtures-") as temp_dir:
        temp = Path(temp_dir)
        os.environ["FREECAD_MCP_WORKSPACE_ROOT"] = str(temp)
        fixture_doc = temp / "complex-fixture.FCStd"
        fixture_step = temp / "complex-fixture.step"
        fixture_stl = temp / "complex-fixture.stl"

        box = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "primitive": "box",
                    "object_name": "FixtureBox",
                    "properties": {"Length": 10.0, "Width": 6.0, "Height": 4.0},
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture box",
        )
        if box["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"fixture box not solid: {box}")

        cylinder = assert_ok(
            service.definition_map()["freecad_part_create_primitive"].handler(
                {
                    "document_path": str(fixture_doc),
                    "primitive": "cylinder",
                    "object_name": "FixtureCylinder",
                    "properties": {"Radius": 2.0, "Height": 6.0},
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture cylinder",
        )
        if cylinder["document"]["object_count"] < 2:
            raise RuntimeError(f"fixture cylinder did not append to document: {cylinder}")

        hidden = assert_ok(
            service.definition_map()["freecad_object_set_properties"].handler(
                {
                    "document_path": str(fixture_doc),
                    "object_name": "FixtureCylinder",
                    "properties": {"Label": "Fixture Cut Candidate", "Visibility": False},
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture object set properties",
        )
        if hidden["object"]["visibility"] is not False or hidden["object"]["label"] != "Fixture Cut Candidate":
            raise RuntimeError(f"fixture object metadata mismatch: {hidden}")

        boolean = assert_ok(
            service.definition_map()["freecad_part_boolean"].handler(
                {
                    "document_path": str(fixture_doc),
                    "object_names": ["FixtureBox", "FixtureCylinder"],
                    "operation": "fuse",
                    "result_name": "FixtureFuse",
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture boolean",
        )
        if boolean["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"fixture boolean not solid: {boolean}")

        sketch = assert_ok(
            service.definition_map()["freecad_sketch_create"].handler(
                {
                    "document_path": str(fixture_doc),
                    "sketch_name": "FixtureProfile",
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture sketch create",
        )
        if sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
            raise RuntimeError(f"fixture sketch mismatch: {sketch}")

        profile = assert_ok(
            service.definition_map()["freecad_sketch_add_profile"].handler(
                {
                    "document_path": str(fixture_doc),
                    "sketch_name": "FixtureProfile",
                    "profile": {"type": "rectangle", "origin": [0, 0, 0], "width": 6.0, "height": 2.0},
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture sketch profile",
        )
        if profile["sketch"]["sketch"]["geometry_count"] != 4:
            raise RuntimeError(f"fixture rectangle profile mismatch: {profile}")

        extrude = assert_ok(
            service.definition_map()["freecad_part_extrude"].handler(
                {
                    "document_path": str(fixture_doc),
                    "source_object": "FixtureProfile",
                    "vector": [0, 0, 1],
                    "extrude_mode": "feature",
                    "solid": True,
                    "symmetric": True,
                    "length_fwd": 3,
                    "result_name": "FixtureSlotSolid",
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture profile extrude",
        )
        if extrude["object"]["shape"]["solids"] != 1:
            raise RuntimeError(f"fixture profile extrusion not solid: {extrude}")

        assembly = assert_ok(
            service.definition_map()["freecad_assembly_create"].handler(
                {
                    "document_path": str(fixture_doc),
                    "assembly_name": "FixtureAssembly",
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture assembly create",
        )
        if assembly["assembly"]["type_id"] != "Assembly::AssemblyObject":
            raise RuntimeError(f"fixture assembly mismatch: {assembly}")

        link = assert_ok(
            service.definition_map()["freecad_assembly_insert"].handler(
                {
                    "document_path": str(fixture_doc),
                    "assembly_name": "FixtureAssembly",
                    "object_name": "FixtureFuse",
                    "link_name": "FixtureFuseLink",
                    "output_path": str(fixture_doc),
                    "overwrite": True,
                }
            ),
            "fixture assembly insert",
        )
        if link["link"]["type_id"] != "App::Link":
            raise RuntimeError(f"fixture assembly link mismatch: {link}")

        opened = assert_ok(
            service.definition_map()["freecad_document_open"].handler({"document_path": str(fixture_doc)}),
            "fixture document open",
        )
        if opened["document"]["object_count"] < 7:
            raise RuntimeError(f"fixture document did not preserve object graph: {opened}")

        objects = assert_ok(
            service.definition_map()["freecad_object_list"].handler({"document_path": str(fixture_doc)}),
            "fixture object list",
        )
        object_names = {obj["name"] for obj in objects["document"]["objects"]}
        for expected in {"FixtureBox", "FixtureCylinder", "FixtureFuse", "FixtureProfile", "FixtureAssembly"}:
            if expected not in object_names:
                raise RuntimeError(f"fixture object missing {expected}: {objects}")

        obj = assert_ok(
            service.definition_map()["freecad_object_get"].handler(
                {"document_path": str(fixture_doc), "object_name": "FixtureCylinder", "include_properties": True}
            ),
            "fixture object get",
        )
        if obj["object"]["label"] != "Fixture Cut Candidate" or obj["object"]["visibility"] is not False:
            raise RuntimeError(f"fixture object get metadata mismatch: {obj}")

        check = assert_ok(
            service.definition_map()["freecad_geometry_check"].handler(
                {"document_path": str(fixture_doc), "object_names": ["FixtureFuse", "FixtureSlotSolid"]}
            ),
            "fixture geometry check",
        )
        if not all(item["is_valid"] for item in check["checks"]):
            raise RuntimeError(f"fixture geometry check failed: {check}")

        step = assert_ok(
            service.definition_map()["freecad_document_export"].handler(
                {
                    "document_path": str(fixture_doc),
                    "object_names": ["FixtureFuse", "FixtureSlotSolid"],
                    "output_path": str(fixture_step),
                    "overwrite": True,
                }
            ),
            "fixture step export",
        )
        if not Path(step["exported_path"]).exists():
            raise RuntimeError(f"fixture STEP export missing: {step}")

        stl = assert_ok(
            service.definition_map()["freecad_document_export"].handler(
                {
                    "document_path": str(fixture_doc),
                    "object_names": ["FixtureFuse"],
                    "output_path": str(fixture_stl),
                    "overwrite": True,
                }
            ),
            "fixture stl export",
        )
        if not Path(stl["exported_path"]).exists():
            raise RuntimeError(f"fixture STL export missing: {stl}")

    print("fixture document smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
