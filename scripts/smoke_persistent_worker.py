#!/usr/bin/env python3
"""Real FreeCAD smoke for persistent FreeCADCmd worker MCP tools."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_mcp.persistent_tools import PersistentToolService


def worker_result(result: dict, label: str) -> dict:
    if not result.get("ok"):
        raise RuntimeError(f"{label} failed: {result}")
    worker = result["worker"]
    if not worker.get("ok"):
        raise RuntimeError(f"{label} worker failed: {result}")
    return worker["result"]


def main() -> int:
    if not os.environ.get("FREECAD_MCP_FREECAD_HOME") and not os.environ.get("FREECAD_MCP_FREECAD_CMD"):
        message = "persistent worker smoke SKIPPED: FreeCAD runtime env not configured"
        if os.environ.get("FREECAD_MCP_REQUIRE_RUNTIME") == "1":
            raise RuntimeError(message)
        print(message)
        return 0

    with tempfile.TemporaryDirectory(prefix="freecad-mcp-worker-") as temp_dir:
        temp = Path(temp_dir)
        os.environ["FREECAD_MCP_WORKSPACE_ROOT"] = str(temp)
        service = PersistentToolService(workspace_root=temp)
        session_id = None
        try:
            started = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = started["session"]["session_id"]
            if not started["session"]["running"]:
                raise RuntimeError(f"worker did not start: {started}")

            listed = service.definition_map()["freecad_worker_session_list"].handler({})
            if listed["count"] != 1:
                raise RuntimeError(f"worker session list mismatch: {listed}")

            document_path = temp / "worker.FCStd"
            document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerSmoke",
                        "output_path": str(document_path),
                        "overwrite": True,
                    }
                ),
                "worker_document_new",
            )
            document_id = document["document"]["document_id"]
            if not document_id:
                raise RuntimeError(f"missing document_id: {document}")

            sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                    }
                ),
                "worker_sketch_create",
            )
            if sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
                raise RuntimeError(f"worker sketch create failed: {sketch}")

            profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "profile": {
                            "type": "rectangle",
                            "origin": [0, 0, 0],
                            "width": 4,
                            "height": 2,
                            "constrain": True,
                        },
                    }
                ),
                "worker_sketch_add_profile",
            )
            if profile["sketch"]["sketch"]["geometry_count"] != 4:
                raise RuntimeError(f"worker sketch profile mismatch: {profile}")

            sketch_extrude = worker_result(
                service.definition_map()["freecad_worker_part_extrude"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "source_object": "WorkerSketch",
                        "vector": [0, 0, 4],
                        "result_name": "WorkerSketchExtrude",
                    }
                ),
                "worker_sketch_part_extrude",
            )
            if sketch_extrude["mode"] != "face_from_closed_wire" or sketch_extrude["object"]["shape"]["solids"] != 1:
                raise RuntimeError(f"worker sketch extrude is not a solid: {sketch_extrude}")

            sketch_shell = worker_result(
                service.definition_map()["freecad_worker_part_extrude"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "source_object": "WorkerSketch",
                        "vector": [0, 0, 2],
                        "extrude_mode": "feature",
                        "solid": False,
                        "result_name": "WorkerSketchShell",
                    }
                ),
                "worker_sketch_part_shell_extrude",
            )
            if sketch_shell["mode"] != "feature" or sketch_shell["object"]["shape"]["solids"] != 0:
                raise RuntimeError(f"worker feature shell extrude did not stay shell-only: {sketch_shell}")

            line = worker_result(
                service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "geometry": [{"type": "line", "start": [6, 0, 0], "end": [9, 0, 0]}],
                    }
                ),
                "worker_sketch_add_geometry",
            )
            line_index = line["added_indices"][0]
            constraint = worker_result(
                service.definition_map()["freecad_worker_sketch_add_constraint"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "constraints": [{"type": "Horizontal", "first": line_index}],
                    }
                ),
                "worker_sketch_add_constraint",
            )
            if not constraint["added_indices"]:
                raise RuntimeError(f"worker sketch constraint missing: {constraint}")

            edit_geometry = worker_result(
                service.definition_map()["freecad_worker_sketch_edit_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "operations": [{"operation": "set_construction", "geometry_index": line_index, "construction": True}],
                    }
                ),
                "worker_sketch_edit_geometry",
            )
            if not edit_geometry["reports"] or not edit_geometry["reports"][0]["construction"]:
                raise RuntimeError(f"worker sketch edit geometry failed: {edit_geometry}")

            transform = worker_result(
                service.definition_map()["freecad_worker_sketch_transform"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "operations": [{"operation": "copy", "geometry_indices": [line_index], "vector": [0, 1, 0]}],
                    }
                ),
                "worker_sketch_transform",
            )
            if not transform["reports"] or not transform["reports"][0].get("added_indices"):
                raise RuntimeError(f"worker sketch transform failed: {transform}")

            edit_constraints = worker_result(
                service.definition_map()["freecad_worker_sketch_edit_constraints"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "operations": [
                            {
                                "operation": "rename",
                                "constraint_index": constraint["added_indices"][0],
                                "name": "worker_horizontal",
                            }
                        ],
                    }
                ),
                "worker_sketch_edit_constraints",
            )
            if not edit_constraints["reports"]:
                raise RuntimeError(f"worker sketch edit constraints failed: {edit_constraints}")

            auto = worker_result(
                service.definition_map()["freecad_worker_sketch_auto_constrain"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "operations": [{"operation": "detect_vertical_horizontal"}],
                    }
                ),
                "worker_sketch_auto_constrain",
            )
            if "count" not in auto["reports"][0]:
                raise RuntimeError(f"worker sketch auto-constrain report mismatch: {auto}")

            validation = worker_result(
                service.definition_map()["freecad_worker_sketch_validate"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "detect_missing": True,
                        "include_constraint_errors": True,
                    }
                ),
                "worker_sketch_validate",
            )
            if validation["geometry_count"] < 4:
                raise RuntimeError(f"worker sketch validation mismatch: {validation}")

            created = worker_result(
                service.definition_map()["freecad_worker_part_create_primitive"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "primitive": "box",
                        "object_name": "WorkerBox",
                        "properties": {"Length": 7.0, "Width": 5.0, "Height": 3.0},
                    }
                ),
                "worker_part_create_primitive",
            )
            if created["object"]["shape"]["solids"] != 1:
                raise RuntimeError(f"worker primitive is not a solid: {created}")

            updated = worker_result(
                service.definition_map()["freecad_worker_object_set_properties"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_name": "WorkerBox",
                        "properties": {"Length": 8.0},
                    }
                ),
                "worker_object_set_properties",
            )
            updated_bbox = updated["object"]["shape"]["bound_box"]
            if updated_bbox["xmax"] != 8.0:
                raise RuntimeError(f"worker object property update failed: {updated}")

            second = worker_result(
                service.definition_map()["freecad_worker_part_create_primitive"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "primitive": "box",
                        "object_name": "WorkerBox2",
                        "properties": {"Length": 2.0, "Width": 2.0, "Height": 2.0},
                    }
                ),
                "worker_part_create_second_primitive",
            )
            if second["object"]["shape"]["solids"] != 1:
                raise RuntimeError(f"worker second primitive is not a solid: {second}")

            boolean = worker_result(
                service.definition_map()["freecad_worker_part_boolean"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_names": ["WorkerBox", "WorkerBox2"],
                        "operation": "fuse",
                        "result_name": "WorkerFuse",
                    }
                ),
                "worker_part_boolean",
            )
            if boolean["object"]["shape"]["solids"] != 1:
                raise RuntimeError(f"worker boolean fuse is not a solid: {boolean}")

            checks = worker_result(
                service.definition_map()["freecad_worker_part_check_geometry"].handler(
                    {"session_id": session_id, "document_id": document_id, "object_names": ["WorkerFuse"]}
                ),
                "worker_part_check_geometry",
            )
            if not checks["checks"] or not checks["checks"][0]["is_valid"]:
                raise RuntimeError(f"worker geometry check failed: {checks}")

            mesh_source = temp / "worker-fuse.stl"
            mesh_source_export = worker_result(
                service.definition_map()["freecad_worker_document_export"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_names": ["WorkerFuse"],
                        "output_path": str(mesh_source),
                        "overwrite": True,
                    }
                ),
                "worker_document_export_stl",
            )
            if not Path(mesh_source_export["exported_path"]).exists():
                raise RuntimeError(f"worker STL export missing: {mesh_source_export}")

            mesh_import = worker_result(
                service.definition_map()["freecad_worker_mesh_import"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "input_path": str(mesh_source),
                    }
                ),
                "worker_mesh_import",
            )
            if not mesh_import["imported"] or not mesh_import["imported"][0]["mesh"]:
                raise RuntimeError(f"worker mesh import failed: {mesh_import}")
            mesh_name = mesh_import["imported"][0]["name"]

            mesh_eval = worker_result(
                service.definition_map()["freecad_worker_mesh_evaluate"].handler(
                    {"session_id": session_id, "document_id": document_id, "object_names": [mesh_name]}
                ),
                "worker_mesh_evaluate",
            )
            if not mesh_eval["meshes"] or mesh_eval["meshes"][0]["mesh"]["facets"] <= 0:
                raise RuntimeError(f"worker mesh evaluate failed: {mesh_eval}")

            mesh_repair = worker_result(
                service.definition_map()["freecad_worker_mesh_repair"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_names": [mesh_name],
                        "actions": ["harmonize_normals", "unsupported_smoke_action"],
                    }
                ),
                "worker_mesh_repair",
            )
            if not mesh_repair["reports"] or not mesh_repair["reports"][0]["errors"]:
                raise RuntimeError(f"worker mesh repair unsupported-action report missing: {mesh_repair}")

            exported = temp / "worker-fuse.step"
            export = worker_result(
                service.definition_map()["freecad_worker_document_export"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_names": ["WorkerFuse"],
                        "output_path": str(exported),
                        "overwrite": True,
                    }
                ),
                "worker_document_export",
            )
            if not Path(export["exported_path"]).exists():
                raise RuntimeError(f"worker exported path missing: {export}")

            deleted = worker_result(
                service.definition_map()["freecad_worker_object_delete"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_name": "WorkerBox2",
                    }
                ),
                "worker_object_delete",
            )
            if any(obj["name"] == "WorkerBox2" for obj in deleted["document"]["objects"]):
                raise RuntimeError(f"worker object delete failed: {deleted}")

            objects = worker_result(
                service.definition_map()["freecad_worker_object_list"].handler(
                    {"session_id": session_id, "document_id": document_id}
                ),
                "worker_object_list",
            )
            if objects["document"]["object_count"] < 2:
                raise RuntimeError(f"worker object count mismatch: {objects}")

            obj = worker_result(
                service.definition_map()["freecad_worker_object_get"].handler(
                    {"session_id": session_id, "document_id": document_id, "object_name": "WorkerBox"}
                ),
                "worker_object_get",
            )
            bbox = obj["object"]["shape"]["bound_box"]
            if [bbox["xmax"], bbox["ymax"], bbox["zmax"]] != [8.0, 5.0, 3.0]:
                raise RuntimeError(f"worker bbox mismatch: {obj}")

            assembly = worker_result(
                service.definition_map()["freecad_worker_assembly_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "assembly_name": "WorkerAssembly",
                    }
                ),
                "worker_assembly_create",
            )
            if assembly["assembly"]["type_id"] != "Assembly::AssemblyObject":
                raise RuntimeError(f"worker assembly create failed: {assembly}")

            link = worker_result(
                service.definition_map()["freecad_worker_assembly_insert"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "assembly_name": "WorkerAssembly",
                        "object_name": "WorkerBox",
                        "link_name": "WorkerBoxLink",
                    }
                ),
                "worker_assembly_insert",
            )
            if link["link"]["type_id"] != "App::Link":
                raise RuntimeError(f"worker assembly insert failed: {link}")

            joint = worker_result(
                service.definition_map()["freecad_worker_assembly_create_joint"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "assembly_name": "WorkerAssembly",
                        "joint_name": "WorkerFixedJoint",
                        "joint_type": "Fixed",
                    }
                ),
                "worker_assembly_create_joint",
            )
            if not joint["joint_fields"]["has_proxy"] or joint["joint_fields"]["joint_type"] != "Fixed":
                raise RuntimeError(f"worker assembly joint failed: {joint}")

            bom = worker_result(
                service.definition_map()["freecad_worker_assembly_bom"].handler(
                    {"session_id": session_id, "document_id": document_id, "assembly_name": "WorkerAssembly"}
                ),
                "worker_assembly_bom",
            )
            if bom["count"] < 1:
                raise RuntimeError(f"worker assembly BOM failed: {bom}")

            solved = worker_result(
                service.definition_map()["freecad_worker_assembly_solve"].handler(
                    {"session_id": session_id, "document_id": document_id}
                ),
                "worker_assembly_solve",
            )
            if solved["document"]["object_count"] < objects["document"]["object_count"]:
                raise RuntimeError(f"worker assembly solve/recompute changed object count unexpectedly: {solved}")

            saved = worker_result(
                service.definition_map()["freecad_worker_document_save"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "output_path": str(document_path),
                        "overwrite": True,
                    }
                ),
                "worker_document_save",
            )
            if not Path(saved["saved_path"]).exists():
                raise RuntimeError(f"worker saved path missing: {saved}")

            status = service.definition_map()["freecad_worker_session_status"].handler(
                {"session_id": session_id, "timeout_sec": 30}
            )
            if status["worker"]["document_count"] != 1:
                raise RuntimeError(f"worker status document count mismatch: {status}")

            closed_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": document_id}
                ),
                "worker_document_close",
            )
            if closed_doc["document_count"] != 0:
                raise RuntimeError(f"worker document close failed: {closed_doc}")
        finally:
            if session_id:
                service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id})

    print("persistent worker smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
