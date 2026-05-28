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

            closed_chain_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerClosedChain",
                    }
                ),
                "worker_closed_chain_sketch_create",
            )
            if closed_chain_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
                raise RuntimeError(f"worker closed chain sketch create failed: {closed_chain_sketch}")

            arc_method_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerArcMethods",
                    }
                ),
                "worker_arc_method_sketch_create",
            )
            if arc_method_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
                raise RuntimeError(f"worker arc method sketch create failed: {arc_method_sketch}")
            arc_methods = worker_result(
                service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerArcMethods",
                        "geometry": [
                            {"type": "arc_3_point", "start": [0, -8, 0], "mid": [2, -6, 0], "end": [4, -8, 0]},
                            {"type": "arc_start_end_radius", "start": [6, -8, 0], "end": [12, -8, 0], "radius": 5, "side": "left", "sweep": "minor"},
                            {"type": "arc_center_angles", "center": [18, -8, 0], "radius": 3, "start_angle": 0, "end_angle": {"degrees": 90}, "direction": "ccw"},
                        ],
                    }
                ),
                "worker_arc_methods_add_geometry",
            )
            if len(arc_methods["geometry_reports"]) != 3:
                raise RuntimeError(f"worker arc methods did not report every circular arc: {arc_methods}")
            center_angle_report = next((report for report in arc_methods["geometry_reports"] if report.get("input_type") == "arc_center_angles"), None)
            if not center_angle_report or not 89.0 <= center_angle_report["sweep_deg"] <= 91.0:
                raise RuntimeError(f"worker center-angle arc report did not preserve requested sweep: {arc_methods}")

            closed_chain = worker_result(
                service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerClosedChain",
                        "geometry": [
                            {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                            {"type": "bspline", "poles": [[10, 0, 0], [12, 5, 0], [10, 10, 0]]},
                            {"type": "arc", "center": [5, 10, 0], "radius": 5, "start_angle": 0, "end_angle": 3.141592653589793},
                            {"type": "line", "start": [0, 10, 0], "end": [0, 0, 0]},
                        ],
                        "connect_sequence": True,
                        "close_sequence": True,
                        "require_closed": True,
                    }
                ),
                "worker_closed_chain_sketch_add_geometry",
            )
            if len(closed_chain["added_indices"]) != 4 or len(closed_chain["constraint_indices"]) != 4:
                raise RuntimeError(f"worker closed chain did not add expected geometry/constraints: {closed_chain}")
            if closed_chain.get("closed_validation", {}).get("open_vertices"):
                raise RuntimeError(f"worker closed chain is not closed: {closed_chain}")

            worker_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerProfileBuilder",
                        "loops": [
                            {
                                "name": "spline_arc_loop",
                                "segments": [
                                    {"type": "line", "start": [0, 20, 0], "end": [10, 20, 0]},
                                    {
                                        "type": "bspline",
                                        "expected_type": "bspline",
                                        "fallback_policy": "fail",
                                        "reason": "variable curvature trace",
                                        "poles": [[10, 20, 0], [12, 25, 0], [10, 30, 0]],
                                    },
                                    {
                                        "type": "arc",
                                        "expected_type": "arc",
                                        "fallback_policy": "fail",
                                        "reason": "constant-radius round end",
                                        "center": [5, 30, 0],
                                        "radius": 5,
                                        "start_angle": 0,
                                        "end_angle": 3.141592653589793,
                                    },
                                    {"type": "line", "start": [0, 30, 0], "end": [0, 20, 0]},
                                ],
                            }
                        ],
                        "lock_mode": "block",
                        "required_segment_types": ["bspline", "arc"],
                        "minimum_curve_segments": 2,
                        "forbid_polyline_fallback": True,
                        "require_fully_constrained": True,
                    }
                ),
                "worker_sketch_profile_create",
            )
            if not worker_profile["validation"]["ok"] or not worker_profile["validation"]["pad_ready"]:
                raise RuntimeError(f"worker profile builder did not produce pad-ready profile: {worker_profile}")
            if worker_profile["validation"]["degrees_of_freedom"] != 0:
                raise RuntimeError(f"worker profile builder did not fully constrain profile: {worker_profile}")
            if worker_profile["loops"][0]["curve_contract"]["curve_segment_count"] != 2:
                raise RuntimeError(f"worker profile builder did not preserve curve segment count: {worker_profile}")
            if worker_profile["loops"][0]["segment_intent_mismatches"]:
                raise RuntimeError(f"worker profile builder reported unexpected intent mismatch: {worker_profile}")
            if len(worker_profile.get("geometry_reports", [])) != 1 or worker_profile["geometry_reports"][0]["input_type"] != "arc":
                raise RuntimeError(f"worker profile builder did not report its arc geometry: {worker_profile}")
            worker_profile_indices = worker_profile["loops"][0]["added_indices"]
            worker_profile_validation = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_validate"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerProfileBuilder",
                        "require_fully_constrained": True,
                        "required_segment_types": ["bspline", "arc"],
                        "minimum_curve_segments": 2,
                        "forbid_all_line_loops": True,
                        "expected_geometry": [
                            {"geometry_index": worker_profile_indices[1], "expected_type": "bspline", "fallback_policy": "fail"},
                            {"geometry_index": worker_profile_indices[2], "expected_type": "arc", "fallback_policy": "fail"},
                        ],
                    }
                ),
                "worker_sketch_profile_validate",
            )
            if not worker_profile_validation["validation"]["ok"]:
                raise RuntimeError(f"worker profile validation mismatch: {worker_profile_validation}")
            if worker_profile_validation["validation"]["geometry_type_counts"].get("bspline") != 1 or worker_profile_validation["validation"]["geometry_type_counts"].get("arc") != 1:
                raise RuntimeError(f"worker profile validation did not report native curve types: {worker_profile_validation}")

            partdesign_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerPartDesignSmoke",
                    }
                ),
                "worker_partdesign_document_new",
            )
            partdesign_document_id = partdesign_document["document"]["document_id"]
            worker_body_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "sketch_name": "WorkerBodySketch",
                        "body_name": "WorkerBody",
                        "attachment_plane": "XY",
                        "loops": [
                            {
                                "segments": [
                                    {"type": "line", "start": [0, 70, 0], "end": [8, 70, 0]},
                                    {"type": "line", "start": [8, 70, 0], "end": [8, 74, 0]},
                                    {"type": "line", "start": [8, 74, 0], "end": [0, 74, 0]},
                                    {"type": "line", "start": [0, 74, 0], "end": [0, 70, 0]},
                                ],
                            }
                        ],
                        "lock_mode": "block",
                        "require_fully_constrained": True,
                    }
                ),
                "worker_partdesign_profile_create",
            )
            if not worker_body_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker body profile did not attach to PartDesign body: {worker_body_profile}")
            worker_pad = worker_result(
                service.definition_map()["freecad_worker_partdesign_pad"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "body_name": "WorkerBody",
                        "sketch_name": "WorkerBodySketch",
                        "attachment_plane": "XY",
                        "pad_name": "WorkerPad",
                        "length": 6,
                    }
                ),
                "worker_partdesign_pad",
            )
            if worker_pad["pad"]["shape"]["solids"] != 1 or worker_pad["body"]["partdesign"]["tip"] != "WorkerPad":
                raise RuntimeError(f"worker PartDesign Pad did not produce a body solid: {worker_pad}")
            closed_partdesign_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": partdesign_document_id}
                ),
                "worker_partdesign_document_close",
            )
            if closed_partdesign_doc["document_count"] != 1:
                raise RuntimeError(f"worker PartDesign document close failed: {closed_partdesign_doc}")

            worker_line_fallback = service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "WorkerLineFallback",
                    "loops": [
                        {
                            "segments": [
                                {"type": "line", "start": [0, 40, 0], "end": [10, 40, 0]},
                                {"type": "line", "start": [10, 40, 0], "end": [10, 50, 0]},
                                {"type": "line", "start": [10, 50, 0], "end": [0, 50, 0]},
                                {"type": "line", "start": [0, 50, 0], "end": [0, 40, 0]},
                            ],
                        }
                    ],
                    "forbid_all_line_loops": True,
                    "minimum_curve_segments": 1,
                }
            )
            if worker_line_fallback.get("ok") and worker_line_fallback.get("worker", {}).get("ok"):
                raise RuntimeError(f"worker profile builder allowed line fallback: {worker_line_fallback}")
            worker_line_error = str(worker_line_fallback.get("worker", {}).get("error") or worker_line_fallback.get("error") or worker_line_fallback)
            if "all-line fallback" not in worker_line_error:
                raise RuntimeError(f"worker profile builder did not reject line fallback: {worker_line_fallback}")
            worker_intent_mismatch = service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "WorkerIntentFallback",
                    "loops": [
                        {
                            "segments": [
                                {
                                    "type": "line",
                                    "expected_type": "bspline",
                                    "fallback_policy": "fail",
                                    "start": [0, 60, 0],
                                    "end": [10, 60, 0],
                                },
                                {"type": "line", "start": [10, 60, 0], "end": [0, 60, 0]},
                            ],
                        }
                    ],
                }
            )
            if worker_intent_mismatch.get("ok") and worker_intent_mismatch.get("worker", {}).get("ok"):
                raise RuntimeError(f"worker profile builder allowed intent mismatch: {worker_intent_mismatch}")
            worker_intent_error = str(worker_intent_mismatch.get("worker", {}).get("error") or worker_intent_mismatch.get("error") or worker_intent_mismatch)
            if "intent mismatch" not in worker_intent_error:
                raise RuntimeError(f"worker profile builder did not reject intent mismatch: {worker_intent_mismatch}")

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

            profile_alias = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "profile": {
                            "type": "slot_start_end_radius",
                            "start": [8, 0, 0],
                            "end": [14, 2, 0],
                            "radius": 1,
                            "constrain": True,
                        },
                    }
                ),
                "worker_sketch_add_profile_alias",
            )
            if profile_alias["profile_type"] != "slot_start_end_radius" or len(profile_alias["added_indices"]) != 4:
                raise RuntimeError(f"worker sketch profile alias mismatch: {profile_alias}")

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

            blocked_group = service.definition_map()["freecad_worker_sketch_add_constraint"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "WorkerSketch",
                    "constraints": [{"type": "Group", "values": [[0, 1]]}],
                }
            )
            if blocked_group.get("ok") is not False or "Group/Text" not in blocked_group["worker"].get("error", ""):
                raise RuntimeError(f"worker Sketcher Group constraint did not fail safely: {blocked_group}")

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
                        "actions": ["unsupported_smoke_action"],
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
