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


def write_tiny_ascii_stl(path: Path) -> None:
    path.write_text(
        """solid freecad_mcp_worker_fixture
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 0 10 0
    endloop
  endfacet
endsolid freecad_mcp_worker_fixture
""",
        encoding="utf-8",
    )


def create_worker_rect_pad(
    service: PersistentToolService,
    *,
    session_id: str,
    document_name: str,
    body_name: str,
    sketch_name: str,
    pad_name: str,
) -> str:
    document = worker_result(
        service.definition_map()["freecad_worker_document_new"].handler(
            {"session_id": session_id, "document_name": document_name, "timeout_sec": 90}
        ),
        f"{document_name}_document_new",
    )
    document_id = document["document"]["document_id"]
    profile = worker_result(
        service.definition_map()["freecad_worker_sketch_profile_create"].handler(
            {
                "session_id": session_id,
                "document_id": document_id,
                "sketch_name": sketch_name,
                "body_name": body_name,
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
                "timeout_sec": 90,
            }
        ),
        f"{document_name}_profile_create",
    )
    if not profile["attachment"]["attached"]:
        raise RuntimeError(f"worker dress-up profile did not attach to PartDesign body: {profile}")
    pad = worker_result(
        service.definition_map()["freecad_worker_partdesign_pad"].handler(
            {
                "session_id": session_id,
                "document_id": document_id,
                "body_name": body_name,
                "sketch_name": sketch_name,
                "attachment_plane": "XY",
                "pad_name": pad_name,
                "length": 10,
                "timeout_sec": 90,
            }
        ),
        f"{document_name}_partdesign_pad",
    )
    if pad["pad"]["shape"]["solids"] != 1 or pad["body"]["partdesign"]["tip"] != pad_name:
        raise RuntimeError(f"worker dress-up base Pad did not produce a body solid: {pad}")
    return document_id


def smoke_worker_sketch_input_ergonomics(service: PersistentToolService) -> None:
    """Exercise agent-friendly Sketcher inputs in a short isolated worker."""
    started = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
    session_id = started["session"]["session_id"]
    try:
        document = worker_result(
            service.definition_map()["freecad_worker_document_new"].handler(
                {"session_id": session_id, "document_name": "WorkerSketchInputErgonomics", "timeout_sec": 30}
            ),
            "worker_sketch_input_document_new",
        )
        document_id = document["document"]["document_id"]
        coordinates_2d_sketch = worker_result(
            service.definition_map()["freecad_worker_sketch_create"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "Worker2DCoordinates",
                    "timeout_sec": 30,
                }
            ),
            "worker_2d_coordinate_sketch_create",
        )
        if coordinates_2d_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
            raise RuntimeError(f"worker 2d coordinate sketch create failed: {coordinates_2d_sketch}")
        coordinates_2d = worker_result(
            service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "Worker2DCoordinates",
                    "geometry": [
                        {"type": "line", "start": [0, 0], "end": [6, 0]},
                        {"type": "line", "start": [6, 0], "end": [6, 4]},
                        {"type": "line", "start": [6, 4], "end": [0, 4]},
                        {"type": "line", "start": [0, 4], "end": [0, 0]},
                    ],
                    "connect_sequence": True,
                    "close_sequence": True,
                    "require_closed": True,
                    "timeout_sec": 30,
                }
            ),
            "worker_2d_coordinate_sketch_add_geometry",
        )
        if coordinates_2d.get("closed_validation", {}).get("open_vertices"):
            raise RuntimeError(f"worker 2d coordinate sketch is not closed: {coordinates_2d}")

        worker_rectangle_loop = worker_result(
            service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "WorkerRectangleLoop",
                    "loops": [{"type": "rectangle", "origin": [0, 10], "width": 6, "height": 4}],
                    "lock_mode": "block",
                    "require_fully_constrained": True,
                    "timeout_sec": 30,
                }
            ),
            "worker_rectangle_loop_profile_create",
        )
        if not worker_rectangle_loop["validation"]["ok"] or not worker_rectangle_loop["validation"]["pad_ready"]:
            raise RuntimeError(f"worker rectangle loop profile was not pad-ready: {worker_rectangle_loop}")
        if len(worker_rectangle_loop["loops"][0]["added_indices"]) != 4:
            raise RuntimeError(f"worker rectangle loop did not expand to four lines: {worker_rectangle_loop}")

        worker_semantic_rectangle = worker_result(
            service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "WorkerSemanticRectangle",
                    "loops": [{"name": "outer", "type": "rectangle", "origin": [0, 20], "width": 6, "height": 4}],
                    "constraint_policy": "semantic",
                    "require_fully_constrained": True,
                    "timeout_sec": 30,
                }
            ),
            "worker_semantic_rectangle_profile_create",
        )
        semantic_roles = {item["role"] for item in worker_semantic_rectangle["loops"][0].get("semantic_constraints", [])}
        if worker_semantic_rectangle["validation"]["degrees_of_freedom"] != 0 or worker_semantic_rectangle["validation"]["block_constraints"]:
            raise RuntimeError(f"worker semantic rectangle did not fully constrain without Block: {worker_semantic_rectangle}")
        for role in ("width", "height", "origin_x", "origin_y"):
            if role not in semantic_roles:
                raise RuntimeError(f"worker semantic rectangle missing {role} constraint: {worker_semantic_rectangle}")

        worker_semantic_hexagon = worker_result(
            service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                {
                    "session_id": session_id,
                    "document_id": document_id,
                    "sketch_name": "WorkerSemanticHexagon",
                    "loops": [{"name": "socket", "type": "hexagon", "center": [0, 30], "radius": 4}],
                    "constraint_policy": "semantic",
                    "require_fully_constrained": True,
                    "timeout_sec": 30,
                }
            ),
            "worker_semantic_hexagon_profile_create",
        )
        hex_roles = {item["role"] for item in worker_semantic_hexagon["loops"][0].get("semantic_constraints", [])}
        if worker_semantic_hexagon["validation"]["degrees_of_freedom"] != 0 or worker_semantic_hexagon["validation"]["block_constraints"]:
            raise RuntimeError(f"worker semantic hexagon did not fully constrain without Block: {worker_semantic_hexagon}")
        for role in ("radius", "center_x", "center_y", "orientation"):
            if role not in hex_roles:
                raise RuntimeError(f"worker semantic hexagon missing {role} constraint: {worker_semantic_hexagon}")
        if len(worker_semantic_hexagon["loops"][0]["added_indices"]) != 7:
            raise RuntimeError(f"worker semantic hexagon did not include construction circle: {worker_semantic_hexagon}")

        closed = worker_result(
            service.definition_map()["freecad_worker_document_close"].handler(
                {"session_id": session_id, "document_id": document_id, "timeout_sec": 30}
            ),
            "worker_sketch_input_document_close",
        )
        if closed["document_count"] != 0:
            raise RuntimeError(f"worker sketch input document close failed: {closed}")
    finally:
        service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})


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
            worker_pocket_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "sketch_name": "WorkerPocketSketch",
                        "body_name": "WorkerBody",
                        "attachment_plane": "XY",
                        "loops": [
                            {
                                "segments": [
                                    {"type": "line", "start": [2, 71, 0], "end": [6, 71, 0]},
                                    {"type": "line", "start": [6, 71, 0], "end": [6, 73, 0]},
                                    {"type": "line", "start": [6, 73, 0], "end": [2, 73, 0]},
                                    {"type": "line", "start": [2, 73, 0], "end": [2, 71, 0]},
                                ],
                            }
                        ],
                        "lock_mode": "block",
                        "require_fully_constrained": True,
                    }
                ),
                "worker_partdesign_pocket_profile_create",
            )
            if not worker_pocket_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker pocket profile did not attach to PartDesign body: {worker_pocket_profile}")
            worker_pocket = worker_result(
                service.definition_map()["freecad_worker_partdesign_pocket"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "body_name": "WorkerBody",
                        "sketch_name": "WorkerPocketSketch",
                        "attachment_plane": "XY",
                        "pocket_name": "WorkerPocket",
                        "length": 3,
                    }
                ),
                "worker_partdesign_pocket",
            )
            if worker_pocket["pocket"]["shape"]["solids"] != 1 or worker_pocket["body"]["partdesign"]["tip"] != "WorkerPocket":
                raise RuntimeError(f"worker PartDesign Pocket did not preserve a body solid: {worker_pocket}")
            worker_hole_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "sketch_name": "WorkerHoleSketch",
                        "body_name": "WorkerBody",
                        "attachment_plane": "XY",
                    }
                ),
                "worker_partdesign_hole_sketch_create",
            )
            if not worker_hole_sketch["attachment"]["attached"]:
                raise RuntimeError(f"worker hole sketch did not attach to PartDesign body: {worker_hole_sketch}")
            worker_hole_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "sketch_name": "WorkerHoleSketch",
                        "profile": {"type": "circle", "center": [1, 72, 0], "radius": 0.5},
                    }
                ),
                "worker_partdesign_hole_circle_profile",
            )
            if worker_hole_profile["profile_type"] != "circle":
                raise RuntimeError(f"worker hole profile was not a circle: {worker_hole_profile}")
            worker_hole = worker_result(
                service.definition_map()["freecad_worker_partdesign_hole"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "body_name": "WorkerBody",
                        "sketch_name": "WorkerHoleSketch",
                        "attachment_plane": "XY",
                        "hole_name": "WorkerHole",
                        "diameter": 1.0,
                        "depth": 6,
                    }
                ),
                "worker_partdesign_hole",
            )
            if worker_hole["hole"]["shape"]["solids"] != 1 or worker_hole["body"]["partdesign"]["tip"] != "WorkerHole":
                raise RuntimeError(f"worker PartDesign Hole did not preserve a body solid: {worker_hole}")
            worker_datum = worker_result(
                service.definition_map()["freecad_worker_partdesign_datum_plane_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "body_name": "WorkerBody",
                        "datum_plane_name": "WorkerOffsetPlane",
                        "attachment_plane": "XY",
                        "attachment_offset": 8,
                    }
                ),
                "worker_partdesign_datum_plane",
            )
            if worker_datum["datum_plane"]["type_id"] != "PartDesign::Plane":
                raise RuntimeError(f"worker PartDesign datum plane was not created: {worker_datum}")
            if worker_datum["body"]["partdesign"]["tip"] != "WorkerHole":
                raise RuntimeError(f"worker PartDesign datum plane should not steal Body Tip: {worker_datum}")
            worker_offset_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": partdesign_document_id,
                        "sketch_name": "WorkerOffsetSketch",
                        "body_name": "WorkerBody",
                        "attachment_object": "WorkerOffsetPlane",
                        "loops": [
                            {
                                "segments": [
                                    {"type": "line", "start": [0, 70, 0], "end": [4, 70, 0]},
                                    {"type": "line", "start": [4, 70, 0], "end": [4, 72, 0]},
                                    {"type": "line", "start": [4, 72, 0], "end": [0, 72, 0]},
                                    {"type": "line", "start": [0, 72, 0], "end": [0, 70, 0]},
                                ],
                            }
                        ],
                        "lock_mode": "block",
                        "require_fully_constrained": True,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_datum_attached_profile",
            )
            if worker_offset_profile["attachment"].get("support_object") != "WorkerOffsetPlane":
                raise RuntimeError(f"worker offset sketch did not attach to datum plane: {worker_offset_profile}")
            closed_partdesign_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": partdesign_document_id}
                ),
                "worker_partdesign_document_close",
            )
            if closed_partdesign_doc["document_count"] != 1:
                raise RuntimeError(f"worker PartDesign document close failed: {closed_partdesign_doc}")

            closed_initial_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": document_id}
                ),
                "worker_initial_sketch_document_close",
            )
            if closed_initial_doc["document_count"] != 0:
                raise RuntimeError(f"worker initial sketch document close failed: {closed_initial_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None

            smoke_worker_sketch_input_ergonomics(service)

            restarted_dressup = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_dressup["session"]["session_id"]
            if not restarted_dressup["session"]["running"]:
                raise RuntimeError(f"dress-up worker did not start: {restarted_dressup}")

            fillet_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerFilletSmoke",
                body_name="WorkerFilletBody",
                sketch_name="WorkerFilletBaseSketch",
                pad_name="WorkerFilletBasePad",
            )
            worker_fillet = worker_result(
                service.definition_map()["freecad_worker_partdesign_fillet"].handler(
                    {
                        "session_id": session_id,
                        "document_id": fillet_document_id,
                        "body_name": "WorkerFilletBody",
                        "base_feature_name": "WorkerFilletBasePad",
                        "use_all_edges": True,
                        "radius": 0.5,
                        "fillet_name": "WorkerFillet",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_fillet",
            )
            if worker_fillet["dressup"]["shape"]["solids"] != 1 or worker_fillet["body"]["partdesign"]["tip"] != "WorkerFillet":
                raise RuntimeError(f"worker PartDesign Fillet did not produce a body solid: {worker_fillet}")
            if not worker_fillet["dressup"]["partdesign"]["use_all_edges"]:
                raise RuntimeError(f"worker PartDesign Fillet did not keep UseAllEdges: {worker_fillet}")
            closed_fillet_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": fillet_document_id}
                ),
                "worker_partdesign_fillet_document_close",
            )
            if closed_fillet_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign Fillet document close failed: {closed_fillet_doc}")

            chamfer_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerChamferSmoke",
                body_name="WorkerChamferBody",
                sketch_name="WorkerChamferBaseSketch",
                pad_name="WorkerChamferBasePad",
            )
            worker_chamfer = worker_result(
                service.definition_map()["freecad_worker_partdesign_chamfer"].handler(
                    {
                        "session_id": session_id,
                        "document_id": chamfer_document_id,
                        "body_name": "WorkerChamferBody",
                        "base_feature_name": "WorkerChamferBasePad",
                        "use_all_edges": True,
                        "distance": 0.5,
                        "chamfer_name": "WorkerChamfer",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_chamfer",
            )
            if worker_chamfer["dressup"]["shape"]["solids"] != 1 or worker_chamfer["body"]["partdesign"]["tip"] != "WorkerChamfer":
                raise RuntimeError(f"worker PartDesign Chamfer did not produce a body solid: {worker_chamfer}")
            if not worker_chamfer["dressup"]["partdesign"]["use_all_edges"]:
                raise RuntimeError(f"worker PartDesign Chamfer did not keep UseAllEdges: {worker_chamfer}")
            closed_chamfer_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": chamfer_document_id}
                ),
                "worker_partdesign_chamfer_document_close",
            )
            if closed_chamfer_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign Chamfer document close failed: {closed_chamfer_doc}")

            thickness_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerThicknessSmoke",
                body_name="WorkerThicknessBody",
                sketch_name="WorkerThicknessBaseSketch",
                pad_name="WorkerThicknessBasePad",
            )
            worker_thickness = worker_result(
                service.definition_map()["freecad_worker_partdesign_thickness"].handler(
                    {
                        "session_id": session_id,
                        "document_id": thickness_document_id,
                        "body_name": "WorkerThicknessBody",
                        "base_feature_name": "WorkerThicknessBasePad",
                        "face_name": "Face1",
                        "thickness": 0.5,
                        "reversed": True,
                        "thickness_name": "WorkerThickness",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_thickness",
            )
            if worker_thickness["dressup"]["shape"]["solids"] != 1 or worker_thickness["body"]["partdesign"]["tip"] != "WorkerThickness":
                raise RuntimeError(f"worker PartDesign Thickness did not produce a body solid: {worker_thickness}")
            if not worker_thickness["dressup"]["partdesign"]["reversed"]:
                raise RuntimeError(f"worker PartDesign Thickness did not keep reversed flag: {worker_thickness}")
            closed_thickness_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": thickness_document_id}
                ),
                "worker_partdesign_thickness_document_close",
            )
            if closed_thickness_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign Thickness document close failed: {closed_thickness_doc}")

            draft_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerDraftSmoke",
                body_name="WorkerDraftBody",
                sketch_name="WorkerDraftBaseSketch",
                pad_name="WorkerDraftBasePad",
            )
            worker_draft = worker_result(
                service.definition_map()["freecad_worker_partdesign_draft"].handler(
                    {
                        "session_id": session_id,
                        "document_id": draft_document_id,
                        "body_name": "WorkerDraftBody",
                        "base_feature_name": "WorkerDraftBasePad",
                        "face_name": "Face6",
                        "neutral_plane_name": "YZ_Plane",
                        "pull_direction_name": "X_Axis",
                        "angle": 5,
                        "reversed": False,
                        "draft_name": "WorkerDraft",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_draft",
            )
            if worker_draft["dressup"]["shape"]["solids"] != 1 or worker_draft["body"]["partdesign"]["tip"] != "WorkerDraft":
                raise RuntimeError(f"worker PartDesign Draft did not produce a body solid: {worker_draft}")
            if worker_draft["dressup"]["partdesign"]["neutral_plane"]["object"] != "YZ_Plane":
                raise RuntimeError(f"worker PartDesign Draft did not keep neutral plane: {worker_draft}")
            closed_draft_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": draft_document_id}
                ),
                "worker_partdesign_draft_document_close",
            )
            if closed_draft_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign Draft document close failed: {closed_draft_doc}")

            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_transform = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_transform["session"]["session_id"]
            if not restarted_transform["session"]["running"]:
                raise RuntimeError(f"transform worker did not start: {restarted_transform}")

            linear_pattern_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerLinearPatternSmoke",
                body_name="WorkerLinearPatternBody",
                sketch_name="WorkerLinearPatternBaseSketch",
                pad_name="WorkerLinearPatternBasePad",
            )
            worker_linear_pattern = worker_result(
                service.definition_map()["freecad_worker_partdesign_linear_pattern"].handler(
                    {
                        "session_id": session_id,
                        "document_id": linear_pattern_document_id,
                        "body_name": "WorkerLinearPatternBody",
                        "original_feature_name": "WorkerLinearPatternBasePad",
                        "direction_axis": "x_axis",
                        "length": 2,
                        "occurrences": 2,
                        "linear_pattern_name": "WorkerLinearPattern",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_linear_pattern",
            )
            if worker_linear_pattern["transform"]["shape"]["solids"] != 1 or worker_linear_pattern["body"]["partdesign"]["tip"] != "WorkerLinearPattern":
                raise RuntimeError(f"worker PartDesign LinearPattern did not produce a body solid: {worker_linear_pattern}")
            if worker_linear_pattern["transform"]["partdesign"]["direction"]["object"] != "X_Axis":
                raise RuntimeError(f"worker PartDesign LinearPattern did not keep X direction: {worker_linear_pattern}")
            linear_pattern_2d_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerLinearPattern2DSmoke",
                body_name="WorkerLinearPattern2DBody",
                sketch_name="WorkerLinearPattern2DBaseSketch",
                pad_name="WorkerLinearPattern2DBasePad",
            )
            worker_linear_pattern_2d = worker_result(
                service.definition_map()["freecad_worker_partdesign_linear_pattern"].handler(
                    {
                        "session_id": session_id,
                        "document_id": linear_pattern_2d_document_id,
                        "body_name": "WorkerLinearPattern2DBody",
                        "original_feature_name": "WorkerLinearPattern2DBasePad",
                        "direction_axis": "x_axis",
                        "direction2_axis": "y_axis",
                        "length": 20,
                        "length2": 20,
                        "occurrences": 2,
                        "occurrences2": 2,
                        "linear_pattern_name": "WorkerLinearPattern2D",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_2d_linear_pattern",
            )
            worker_linear_pattern_2d_shape = worker_linear_pattern_2d["transform"]["shape"]
            worker_linear_pattern_2d_pd = worker_linear_pattern_2d["transform"]["partdesign"]
            worker_linear_pattern_2d_box = worker_linear_pattern_2d_shape["bound_box"]
            if worker_linear_pattern_2d_shape["solids"] != 4 or worker_linear_pattern_2d["body"]["partdesign"]["tip"] != "WorkerLinearPattern2D":
                raise RuntimeError(f"worker PartDesign 2D LinearPattern did not create a 2x2 transform: {worker_linear_pattern_2d}")
            if worker_linear_pattern_2d_pd["direction2"]["object"] != "Y_Axis" or worker_linear_pattern_2d_pd["occurrences2"] != 2:
                raise RuntimeError(f"worker PartDesign 2D LinearPattern did not keep second direction: {worker_linear_pattern_2d}")
            if worker_linear_pattern_2d_box["xmax"] < 24.9 or worker_linear_pattern_2d_box["ymax"] < 24.9:
                raise RuntimeError(f"worker PartDesign 2D LinearPattern did not expand in both directions: {worker_linear_pattern_2d}")
            closed_linear_pattern_2d_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": linear_pattern_2d_document_id}
                ),
                "worker_partdesign_2d_linear_pattern_document_close",
            )
            if closed_linear_pattern_2d_doc["document_count"] != 1:
                raise RuntimeError(f"worker PartDesign 2D LinearPattern document close failed: {closed_linear_pattern_2d_doc}")
            closed_linear_pattern_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": linear_pattern_document_id}
                ),
                "worker_partdesign_linear_pattern_document_close",
            )
            if closed_linear_pattern_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign LinearPattern document close failed: {closed_linear_pattern_doc}")

            polar_pattern_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerPolarPatternSmoke",
                body_name="WorkerPolarPatternBody",
                sketch_name="WorkerPolarPatternBaseSketch",
                pad_name="WorkerPolarPatternBasePad",
            )
            worker_polar_pattern = worker_result(
                service.definition_map()["freecad_worker_partdesign_polar_pattern"].handler(
                    {
                        "session_id": session_id,
                        "document_id": polar_pattern_document_id,
                        "body_name": "WorkerPolarPatternBody",
                        "original_feature_name": "WorkerPolarPatternBasePad",
                        "axis": "z_axis",
                        "angle": 30,
                        "occurrences": 2,
                        "polar_pattern_name": "WorkerPolarPattern",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_polar_pattern",
            )
            if worker_polar_pattern["transform"]["shape"]["solids"] != 1 or worker_polar_pattern["body"]["partdesign"]["tip"] != "WorkerPolarPattern":
                raise RuntimeError(f"worker PartDesign PolarPattern did not produce a body solid: {worker_polar_pattern}")
            if worker_polar_pattern["transform"]["partdesign"]["axis"]["object"] != "Z_Axis":
                raise RuntimeError(f"worker PartDesign PolarPattern did not keep Z axis: {worker_polar_pattern}")
            closed_polar_pattern_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": polar_pattern_document_id}
                ),
                "worker_partdesign_polar_pattern_document_close",
            )
            if closed_polar_pattern_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign PolarPattern document close failed: {closed_polar_pattern_doc}")

            mirrored_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerMirroredSmoke",
                body_name="WorkerMirroredBody",
                sketch_name="WorkerMirroredBaseSketch",
                pad_name="WorkerMirroredBasePad",
            )
            worker_mirrored = worker_result(
                service.definition_map()["freecad_worker_partdesign_mirrored"].handler(
                    {
                        "session_id": session_id,
                        "document_id": mirrored_document_id,
                        "body_name": "WorkerMirroredBody",
                        "original_feature_name": "WorkerMirroredBasePad",
                        "mirror_plane": "xy_plane",
                        "mirrored_name": "WorkerMirrored",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_mirrored",
            )
            if worker_mirrored["transform"]["shape"]["solids"] != 1 or worker_mirrored["body"]["partdesign"]["tip"] != "WorkerMirrored":
                raise RuntimeError(f"worker PartDesign Mirrored did not produce a body solid: {worker_mirrored}")
            if worker_mirrored["transform"]["partdesign"]["mirror_plane"]["object"] != "XY_Plane":
                raise RuntimeError(f"worker PartDesign Mirrored did not keep mirror plane: {worker_mirrored}")
            closed_mirrored_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": mirrored_document_id}
                ),
                "worker_partdesign_mirrored_document_close",
            )
            if closed_mirrored_doc["document_count"] != 0:
                raise RuntimeError(f"worker PartDesign Mirrored document close failed: {closed_mirrored_doc}")

            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_sketch = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_sketch["session"]["session_id"]
            if not restarted_sketch["session"]["running"]:
                raise RuntimeError(f"second worker did not start: {restarted_sketch}")
            revolved_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerRevolvedSmoke",
                    }
                ),
                "worker_revolved_document_new",
            )
            revolved_document_id = revolved_document["document"]["document_id"]
            worker_revolution_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": revolved_document_id,
                        "sketch_name": "WorkerRevolutionSketch",
                        "body_name": "WorkerRevolveBody",
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
                    }
                ),
                "worker_partdesign_revolution_profile_create",
            )
            if not worker_revolution_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker revolution profile did not attach to PartDesign body: {worker_revolution_profile}")
            worker_revolution = worker_result(
                service.definition_map()["freecad_worker_partdesign_revolution"].handler(
                    {
                        "session_id": session_id,
                        "document_id": revolved_document_id,
                        "body_name": "WorkerRevolveBody",
                        "sketch_name": "WorkerRevolutionSketch",
                        "attachment_plane": "XY",
                        "revolution_name": "WorkerRevolution",
                        "reference_axis": "sketch_v_axis",
                        "angle": 180,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_revolution",
            )
            if worker_revolution["revolution"]["shape"]["solids"] != 1 or worker_revolution["body"]["partdesign"]["tip"] != "WorkerRevolution":
                raise RuntimeError(f"worker PartDesign Revolution did not produce a body solid: {worker_revolution}")
            worker_groove_body_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": revolved_document_id,
                        "sketch_name": "WorkerGrooveBodySketch",
                        "body_name": "WorkerGrooveBody",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_groove_body_profile_create",
            )
            if not worker_groove_body_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker groove body profile did not attach to PartDesign body: {worker_groove_body_profile}")
            worker_groove_pad = worker_result(
                service.definition_map()["freecad_worker_partdesign_pad"].handler(
                    {
                        "session_id": session_id,
                        "document_id": revolved_document_id,
                        "body_name": "WorkerGrooveBody",
                        "sketch_name": "WorkerGrooveBodySketch",
                        "attachment_plane": "XY",
                        "pad_name": "WorkerGroovePad",
                        "length": 6,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_groove_pad",
            )
            if worker_groove_pad["pad"]["shape"]["solids"] != 1 or worker_groove_pad["body"]["partdesign"]["tip"] != "WorkerGroovePad":
                raise RuntimeError(f"worker PartDesign Groove pad did not produce a body solid: {worker_groove_pad}")
            worker_groove_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": revolved_document_id,
                        "sketch_name": "WorkerGrooveSketch",
                        "body_name": "WorkerGrooveBody",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_groove_profile_create",
            )
            if not worker_groove_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker groove profile did not attach to PartDesign body: {worker_groove_profile}")
            worker_groove = worker_result(
                service.definition_map()["freecad_worker_partdesign_groove"].handler(
                    {
                        "session_id": session_id,
                        "document_id": revolved_document_id,
                        "body_name": "WorkerGrooveBody",
                        "sketch_name": "WorkerGrooveSketch",
                        "attachment_plane": "XY",
                        "groove_name": "WorkerGroove",
                        "reference_axis": "sketch_v_axis",
                        "angle": 180,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_groove",
            )
            if worker_groove["groove"]["shape"]["solids"] != 1 or worker_groove["body"]["partdesign"]["tip"] != "WorkerGroove":
                raise RuntimeError(f"worker PartDesign Groove did not preserve a body solid: {worker_groove}")
            closed_revolved_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": revolved_document_id}
                ),
                "worker_revolved_document_close",
            )
            if closed_revolved_doc["document_count"] != 0:
                raise RuntimeError(f"worker revolved document close failed: {closed_revolved_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_loft = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_loft["session"]["session_id"]
            if not restarted_loft["session"]["running"]:
                raise RuntimeError(f"third worker did not start: {restarted_loft}")
            loft_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerLoftSmoke",
                    }
                ),
                "worker_loft_document_new",
            )
            loft_document_id = loft_document["document"]["document_id"]
            worker_loft_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "sketch_name": "WorkerLoftProfileSketch",
                        "body_name": "WorkerLoftBody",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_loft_profile_create",
            )
            if not worker_loft_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker loft profile did not attach to PartDesign body: {worker_loft_profile}")
            worker_loft_plane = worker_result(
                service.definition_map()["freecad_worker_partdesign_datum_plane_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "body_name": "WorkerLoftBody",
                        "datum_plane_name": "WorkerLoftSectionPlane",
                        "attachment_plane": "XY",
                        "attachment_offset": 6,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_loft_datum_plane",
            )
            if worker_loft_plane["datum_plane"]["type_id"] != "PartDesign::Plane":
                raise RuntimeError(f"worker loft datum plane was not created: {worker_loft_plane}")
            worker_loft_section = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "sketch_name": "WorkerLoftSectionSketch",
                        "body_name": "WorkerLoftBody",
                        "attachment_object": "WorkerLoftSectionPlane",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_loft_section_create",
            )
            if worker_loft_section["attachment"].get("support_object") != "WorkerLoftSectionPlane":
                raise RuntimeError(f"worker loft section did not attach to datum plane: {worker_loft_section}")
            worker_additive_loft = worker_result(
                service.definition_map()["freecad_worker_partdesign_additive_loft"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "body_name": "WorkerLoftBody",
                        "profile_name": "WorkerLoftProfileSketch",
                        "sections": ["WorkerLoftSectionSketch"],
                        "loft_name": "WorkerAdditiveLoft",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_loft",
            )
            if worker_additive_loft["loft"]["shape"]["solids"] != 1 or worker_additive_loft["body"]["partdesign"]["tip"] != "WorkerAdditiveLoft":
                raise RuntimeError(f"worker PartDesign Additive Loft did not produce a body solid: {worker_additive_loft}")
            closed_additive_loft_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": loft_document_id}
                ),
                "worker_additive_loft_document_close",
            )
            if closed_additive_loft_doc["document_count"] != 0:
                raise RuntimeError(f"worker additive loft document close failed: {closed_additive_loft_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_subtractive_loft = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_subtractive_loft["session"]["session_id"]
            if not restarted_subtractive_loft["session"]["running"]:
                raise RuntimeError(f"subtractive loft worker did not start: {restarted_subtractive_loft}")
            subtractive_loft_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerSubtractiveLoftSmoke",
                    }
                ),
                "worker_subtractive_loft_document_new",
            )
            loft_document_id = subtractive_loft_document["document"]["document_id"]
            worker_subtractive_loft_base_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "sketch_name": "WorkerSubtractiveLoftBaseSketch",
                        "body_name": "WorkerSubtractiveLoftBody",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_loft_base_profile",
            )
            if not worker_subtractive_loft_base_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker subtractive loft base profile did not attach to PartDesign body: {worker_subtractive_loft_base_profile}")
            worker_subtractive_loft_pad = worker_result(
                service.definition_map()["freecad_worker_partdesign_pad"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "body_name": "WorkerSubtractiveLoftBody",
                        "sketch_name": "WorkerSubtractiveLoftBaseSketch",
                        "attachment_plane": "XY",
                        "pad_name": "WorkerSubtractiveLoftPad",
                        "length": 6,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_loft_pad",
            )
            if worker_subtractive_loft_pad["pad"]["shape"]["solids"] != 1 or worker_subtractive_loft_pad["body"]["partdesign"]["tip"] != "WorkerSubtractiveLoftPad":
                raise RuntimeError(f"worker subtractive loft base pad did not produce a body solid: {worker_subtractive_loft_pad}")
            worker_subtractive_loft_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "sketch_name": "WorkerSubtractiveLoftProfileSketch",
                        "body_name": "WorkerSubtractiveLoftBody",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_loft_profile",
            )
            if not worker_subtractive_loft_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker subtractive loft profile did not attach to PartDesign body: {worker_subtractive_loft_profile}")
            worker_subtractive_loft_plane = worker_result(
                service.definition_map()["freecad_worker_partdesign_datum_plane_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "body_name": "WorkerSubtractiveLoftBody",
                        "datum_plane_name": "WorkerSubtractiveLoftSectionPlane",
                        "attachment_plane": "XY",
                        "attachment_offset": 5,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_loft_datum_plane",
            )
            if worker_subtractive_loft_plane["datum_plane"]["type_id"] != "PartDesign::Plane":
                raise RuntimeError(f"worker subtractive loft datum plane was not created: {worker_subtractive_loft_plane}")
            worker_subtractive_loft_section = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "sketch_name": "WorkerSubtractiveLoftSectionSketch",
                        "body_name": "WorkerSubtractiveLoftBody",
                        "attachment_object": "WorkerSubtractiveLoftSectionPlane",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_loft_section",
            )
            if worker_subtractive_loft_section["attachment"].get("support_object") != "WorkerSubtractiveLoftSectionPlane":
                raise RuntimeError(f"worker subtractive loft section did not attach to datum plane: {worker_subtractive_loft_section}")
            worker_subtractive_loft = worker_result(
                service.definition_map()["freecad_worker_partdesign_subtractive_loft"].handler(
                    {
                        "session_id": session_id,
                        "document_id": loft_document_id,
                        "body_name": "WorkerSubtractiveLoftBody",
                        "profile_name": "WorkerSubtractiveLoftProfileSketch",
                        "sections": ["WorkerSubtractiveLoftSectionSketch"],
                        "loft_name": "WorkerSubtractiveLoft",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_loft",
            )
            if worker_subtractive_loft["loft"]["shape"]["solids"] != 1 or worker_subtractive_loft["body"]["partdesign"]["tip"] != "WorkerSubtractiveLoft":
                raise RuntimeError(f"worker PartDesign Subtractive Loft did not preserve a body solid: {worker_subtractive_loft}")
            closed_loft_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": loft_document_id}
                ),
                "worker_subtractive_loft_document_close",
            )
            if closed_loft_doc["document_count"] != 0:
                raise RuntimeError(f"worker subtractive loft document close failed: {closed_loft_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_additive_pipe = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_additive_pipe["session"]["session_id"]
            if not restarted_additive_pipe["session"]["running"]:
                raise RuntimeError(f"additive pipe worker did not start: {restarted_additive_pipe}")
            additive_pipe_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerAdditivePipeSmoke",
                    }
                ),
                "worker_additive_pipe_document_new",
            )
            additive_pipe_document_id = additive_pipe_document["document"]["document_id"]
            worker_additive_pipe_profile_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeProfileSketch",
                        "body_name": "WorkerAdditivePipeBody",
                        "attachment_plane": "XY",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_profile_sketch",
            )
            if not worker_additive_pipe_profile_sketch["attachment"]["attached"]:
                raise RuntimeError(f"worker additive pipe profile sketch did not attach: {worker_additive_pipe_profile_sketch}")
            worker_additive_pipe_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeProfileSketch",
                        "profile": {"type": "circle", "center": [0, 0, 0], "radius": 1},
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_profile",
            )
            if worker_additive_pipe_profile["profile_type"] != "circle":
                raise RuntimeError(f"worker additive pipe profile was not a circle: {worker_additive_pipe_profile}")
            worker_additive_pipe_spine_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeSpineSketch",
                        "body_name": "WorkerAdditivePipeBody",
                        "attachment_plane": "XZ",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_spine_sketch",
            )
            if not worker_additive_pipe_spine_sketch["attachment"]["attached"]:
                raise RuntimeError(f"worker additive pipe spine sketch did not attach: {worker_additive_pipe_spine_sketch}")
            worker_additive_pipe_spine = worker_result(
                service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeSpineSketch",
                        "geometry": [{"type": "line", "start": [0, 0, 0], "end": [0, 2, 0]}],
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_spine",
            )
            if len(worker_additive_pipe_spine["added_indices"]) != 1:
                raise RuntimeError(f"worker additive pipe spine line was not added: {worker_additive_pipe_spine}")
            worker_additive_pipe_spine_constraints = worker_result(
                service.definition_map()["freecad_worker_sketch_add_constraint"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeSpineSketch",
                        "constraints": [
                            {"type": "Coincident", "values": [0, 1, -1, 1]},
                            {"type": "PointOnObject", "values": [0, 2, -2]},
                            {"type": "DistanceY", "values": [0, 1, 0, 2, 2]},
                        ],
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_spine_constraints",
            )
            if len(worker_additive_pipe_spine_constraints["added_indices"]) != 3:
                raise RuntimeError(f"worker additive pipe spine constraints were not added: {worker_additive_pipe_spine_constraints}")
            worker_additive_pipe_aux_spine_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeAuxSpineSketch",
                        "body_name": "WorkerAdditivePipeBody",
                        "attachment_plane": "XZ",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_aux_spine_sketch",
            )
            if not worker_additive_pipe_aux_spine_sketch["attachment"]["attached"]:
                raise RuntimeError(f"worker additive pipe auxiliary spine sketch did not attach: {worker_additive_pipe_aux_spine_sketch}")
            worker_additive_pipe_aux_spine = worker_result(
                service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "sketch_name": "WorkerAdditivePipeAuxSpineSketch",
                        "geometry": [{"type": "line", "start": [1, 0, 0], "end": [1, 2, 0]}],
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe_aux_spine",
            )
            if len(worker_additive_pipe_aux_spine["added_indices"]) != 1:
                raise RuntimeError(f"worker additive pipe auxiliary spine line was not added: {worker_additive_pipe_aux_spine}")
            worker_additive_pipe = worker_result(
                service.definition_map()["freecad_worker_partdesign_additive_pipe"].handler(
                    {
                        "session_id": session_id,
                        "document_id": additive_pipe_document_id,
                        "body_name": "WorkerAdditivePipeBody",
                        "profile_name": "WorkerAdditivePipeProfileSketch",
                        "spine_name": "WorkerAdditivePipeSpineSketch",
                        "auxiliary_spine_name": "WorkerAdditivePipeAuxSpineSketch",
                        "pipe_name": "WorkerAdditivePipe",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_additive_pipe",
            )
            if worker_additive_pipe["pipe"]["shape"]["solids"] != 1 or worker_additive_pipe["body"]["partdesign"]["tip"] != "WorkerAdditivePipe":
                raise RuntimeError(f"worker PartDesign Additive Pipe did not produce a body solid: {worker_additive_pipe}")
            worker_additive_pipe_partdesign = worker_additive_pipe["pipe"]["partdesign"]
            if worker_additive_pipe_partdesign["mode"] != "Auxiliary" or worker_additive_pipe_partdesign["auxiliary_spine"]["object"] != "WorkerAdditivePipeAuxSpineSketch":
                raise RuntimeError(f"worker PartDesign Additive Pipe did not keep auxiliary orientation: {worker_additive_pipe}")
            closed_additive_pipe_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": additive_pipe_document_id}
                ),
                "worker_additive_pipe_document_close",
            )
            if closed_additive_pipe_doc["document_count"] != 0:
                raise RuntimeError(f"worker additive pipe document close failed: {closed_additive_pipe_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_subtractive_pipe = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_subtractive_pipe["session"]["session_id"]
            if not restarted_subtractive_pipe["session"]["running"]:
                raise RuntimeError(f"subtractive pipe worker did not start: {restarted_subtractive_pipe}")
            subtractive_pipe_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerSubtractivePipeSmoke",
                    }
                ),
                "worker_subtractive_pipe_document_new",
            )
            subtractive_pipe_document_id = subtractive_pipe_document["document"]["document_id"]
            worker_subtractive_pipe_base_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "sketch_name": "WorkerSubtractivePipeBaseSketch",
                        "body_name": "WorkerSubtractivePipeBody",
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
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_base_profile",
            )
            if not worker_subtractive_pipe_base_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker subtractive pipe base profile did not attach: {worker_subtractive_pipe_base_profile}")
            worker_subtractive_pipe_pad = worker_result(
                service.definition_map()["freecad_worker_partdesign_pad"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "body_name": "WorkerSubtractivePipeBody",
                        "sketch_name": "WorkerSubtractivePipeBaseSketch",
                        "attachment_plane": "XY",
                        "pad_name": "WorkerSubtractivePipePad",
                        "length": 2,
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_pad",
            )
            if worker_subtractive_pipe_pad["pad"]["shape"]["solids"] != 1 or worker_subtractive_pipe_pad["body"]["partdesign"]["tip"] != "WorkerSubtractivePipePad":
                raise RuntimeError(f"worker subtractive pipe base pad did not produce a body solid: {worker_subtractive_pipe_pad}")
            worker_subtractive_pipe_profile_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "sketch_name": "WorkerSubtractivePipeProfileSketch",
                        "body_name": "WorkerSubtractivePipeBody",
                        "attachment_plane": "XY",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_profile_sketch",
            )
            if not worker_subtractive_pipe_profile_sketch["attachment"]["attached"]:
                raise RuntimeError(f"worker subtractive pipe profile sketch did not attach: {worker_subtractive_pipe_profile_sketch}")
            worker_subtractive_pipe_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "sketch_name": "WorkerSubtractivePipeProfileSketch",
                        "profile": {"type": "circle", "center": [0, 0, 0], "radius": 1},
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_profile",
            )
            if worker_subtractive_pipe_profile["profile_type"] != "circle":
                raise RuntimeError(f"worker subtractive pipe profile was not a circle: {worker_subtractive_pipe_profile}")
            worker_subtractive_pipe_spine_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "sketch_name": "WorkerSubtractivePipeSpineSketch",
                        "body_name": "WorkerSubtractivePipeBody",
                        "attachment_plane": "XZ",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_spine_sketch",
            )
            if not worker_subtractive_pipe_spine_sketch["attachment"]["attached"]:
                raise RuntimeError(f"worker subtractive pipe spine sketch did not attach: {worker_subtractive_pipe_spine_sketch}")
            worker_subtractive_pipe_spine = worker_result(
                service.definition_map()["freecad_worker_sketch_add_geometry"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "sketch_name": "WorkerSubtractivePipeSpineSketch",
                        "geometry": [{"type": "line", "start": [0, 0, 0], "end": [0, 2, 0]}],
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_spine",
            )
            if len(worker_subtractive_pipe_spine["added_indices"]) != 1:
                raise RuntimeError(f"worker subtractive pipe spine line was not added: {worker_subtractive_pipe_spine}")
            worker_subtractive_pipe_spine_constraints = worker_result(
                service.definition_map()["freecad_worker_sketch_add_constraint"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "sketch_name": "WorkerSubtractivePipeSpineSketch",
                        "constraints": [
                            {"type": "Coincident", "values": [0, 1, -1, 1]},
                            {"type": "PointOnObject", "values": [0, 2, -2]},
                            {"type": "DistanceY", "values": [0, 1, 0, 2, 2]},
                        ],
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe_spine_constraints",
            )
            if len(worker_subtractive_pipe_spine_constraints["added_indices"]) != 3:
                raise RuntimeError(f"worker subtractive pipe spine constraints were not added: {worker_subtractive_pipe_spine_constraints}")
            worker_subtractive_pipe = worker_result(
                service.definition_map()["freecad_worker_partdesign_subtractive_pipe"].handler(
                    {
                        "session_id": session_id,
                        "document_id": subtractive_pipe_document_id,
                        "body_name": "WorkerSubtractivePipeBody",
                        "profile_name": "WorkerSubtractivePipeProfileSketch",
                        "spine_name": "WorkerSubtractivePipeSpineSketch",
                        "pipe_name": "WorkerSubtractivePipe",
                        "timeout_sec": 90,
                    }
                ),
                "worker_partdesign_subtractive_pipe",
            )
            if worker_subtractive_pipe["pipe"]["shape"]["solids"] != 1 or worker_subtractive_pipe["body"]["partdesign"]["tip"] != "WorkerSubtractivePipe":
                raise RuntimeError(f"worker PartDesign Subtractive Pipe did not preserve a body solid: {worker_subtractive_pipe}")
            closed_subtractive_pipe_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": subtractive_pipe_document_id}
                ),
                "worker_subtractive_pipe_document_close",
            )
            if closed_subtractive_pipe_doc["document_count"] != 0:
                raise RuntimeError(f"worker subtractive pipe document close failed: {closed_subtractive_pipe_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted_sketch = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted_sketch["session"]["session_id"]
            if not restarted_sketch["session"]["running"]:
                raise RuntimeError(f"next sketch worker did not start: {restarted_sketch}")
            edit_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerEditSmoke",
                    }
                ),
                "worker_edit_document_new",
            )
            document_id = edit_document["document"]["document_id"]
            sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                    }
                ),
                "worker_edit_sketch_create",
            )
            if sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
                raise RuntimeError(f"worker edit sketch create failed: {sketch}")

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

            worker_hexagon_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "profile": {
                            "type": "hexagon",
                            "center": [18, 0, 0],
                            "corner": [21, 0, 0],
                            "constrain": True,
                        },
                    }
                ),
                "worker_sketch_add_profile_hexagon",
            )
            if worker_hexagon_profile["profile_type"] != "hexagon" or len(worker_hexagon_profile["added_indices"]) != 7:
                raise RuntimeError(f"worker sketch hexagon profile mismatch: {worker_hexagon_profile}")

            worker_keyhole_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerSketch",
                        "profile": {
                            "type": "keyhole",
                            "circle_center": [26, 0, 0],
                            "circle_radius": 3,
                            "slot_end": [32, 0, 0],
                            "slot_radius": 1,
                            "constrain": True,
                        },
                    }
                ),
                "worker_sketch_add_profile_keyhole",
            )
            if worker_keyhole_profile["profile_type"] != "keyhole" or len(worker_keyhole_profile["added_indices"]) != 4:
                raise RuntimeError(f"worker sketch keyhole profile mismatch: {worker_keyhole_profile}")

            worker_extrude_sketch = worker_result(
                service.definition_map()["freecad_worker_sketch_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerExtrudeSketch",
                    }
                ),
                "worker_extrude_sketch_create",
            )
            if worker_extrude_sketch["sketch"]["type_id"] != "Sketcher::SketchObject":
                raise RuntimeError(f"worker extrude sketch create failed: {worker_extrude_sketch}")
            worker_extrude_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_add_profile"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "sketch_name": "WorkerExtrudeSketch",
                        "profile": {
                            "type": "rectangle",
                            "origin": [0, 0, 0],
                            "width": 4,
                            "height": 2,
                            "constrain": True,
                        },
                    }
                ),
                "worker_extrude_sketch_profile",
            )
            if worker_extrude_profile["sketch"]["sketch"]["geometry_count"] != 4:
                raise RuntimeError(f"worker extrude sketch profile mismatch: {worker_extrude_profile}")

            sketch_extrude = worker_result(
                service.definition_map()["freecad_worker_part_extrude"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "source_object": "WorkerExtrudeSketch",
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
                        "source_object": "WorkerExtrudeSketch",
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

            closed_sketch_doc = worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": document_id}
                ),
                "worker_sketch_document_close",
            )
            if closed_sketch_doc["document_count"] != 0:
                raise RuntimeError(f"worker sketch document close failed: {closed_sketch_doc}")
            service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})
            session_id = None
            restarted = service.definition_map()["freecad_worker_session_start"].handler({"timeout_sec": 30})
            session_id = restarted["session"]["session_id"]
            if not restarted["session"]["running"]:
                raise RuntimeError(f"second worker did not start: {restarted}")
            solid_document = worker_result(
                service.definition_map()["freecad_worker_document_new"].handler(
                    {
                        "session_id": session_id,
                        "document_name": "WorkerSolidSmoke",
                        "output_path": str(document_path),
                        "overwrite": True,
                    }
                ),
                "worker_solid_document_new",
            )
            document_id = solid_document["document"]["document_id"]

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

            renamed = worker_result(
                service.definition_map()["freecad_worker_object_rename_label"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_name": "WorkerBox",
                        "label": "Worker Main Box",
                    }
                ),
                "worker_object_rename_label",
            )
            if renamed["after"]["name"] != "WorkerBox" or renamed["after"]["label"] != "Worker Main Box":
                raise RuntimeError(f"worker object label rename changed the wrong fields: {renamed}")
            renamed_lookup = worker_result(
                service.definition_map()["freecad_worker_object_get"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_name": "Worker Main Box",
                    }
                ),
                "worker_object_get renamed label",
            )
            if renamed_lookup["object"]["name"] != "WorkerBox":
                raise RuntimeError(f"worker renamed label lookup failed: {renamed_lookup}")

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
                service.definition_map()["freecad_worker_geometry_check"].handler(
                    {"session_id": session_id, "document_id": document_id, "object_names": ["WorkerFuse"]}
                ),
                "worker_geometry_check",
            )
            if not checks["checks"] or not checks["checks"][0]["is_valid"]:
                raise RuntimeError(f"worker geometry check failed: {checks}")

            exported_mesh_source = temp / "worker-box-export.stl"
            mesh_source_export = worker_result(
                service.definition_map()["freecad_worker_document_export"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_names": ["WorkerBox"],
                        "output_path": str(exported_mesh_source),
                        "overwrite": True,
                        "timeout_sec": 90,
                    }
                ),
                "worker_document_export_stl",
            )
            if not Path(mesh_source_export["exported_path"]).exists():
                raise RuntimeError(f"worker STL export missing: {mesh_source_export}")

            mesh_source = temp / "worker-import-fixture.stl"
            write_tiny_ascii_stl(mesh_source)
            mesh_import = worker_result(
                service.definition_map()["freecad_worker_mesh_import"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "input_path": str(mesh_source),
                        "timeout_sec": 90,
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

            exported = temp / "worker-box.step"
            export = worker_result(
                service.definition_map()["freecad_worker_document_export"].handler(
                    {
                        "session_id": session_id,
                        "document_id": document_id,
                        "object_names": ["WorkerBox"],
                        "output_path": str(exported),
                        "overwrite": True,
                        "timeout_sec": 90,
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
            compact_objects = service.definition_map()["freecad_worker_object_list"].handler(
                {"session_id": session_id, "document_id": document_id, "compact_response": True}
            )
            if not compact_objects.get("compact_response") or "objects" in compact_objects["worker"]["result"]["document"]:
                raise RuntimeError(f"worker compact response did not omit document object dump: {compact_objects}")

            obj = worker_result(
                service.definition_map()["freecad_worker_object_get"].handler(
                    {"session_id": session_id, "document_id": document_id, "object_name": "WorkerBox"}
                ),
                "worker_object_get",
            )
            bbox = obj["object"]["shape"]["bound_box"]
            if [bbox["xmax"], bbox["ymax"], bbox["zmax"]] != [8.0, 5.0, 3.0]:
                raise RuntimeError(f"worker bbox mismatch: {obj}")

            tip_document_id = create_worker_rect_pad(
                service,
                session_id=session_id,
                document_name="WorkerTipSmoke",
                body_name="WorkerTipBody",
                sketch_name="WorkerTipBaseSketch",
                pad_name="WorkerTipPad",
            )
            worker_tip_pocket_profile = worker_result(
                service.definition_map()["freecad_worker_sketch_profile_create"].handler(
                    {
                        "session_id": session_id,
                        "document_id": tip_document_id,
                        "sketch_name": "WorkerTipPocketSketch",
                        "body_name": "WorkerTipBody",
                        "attachment_plane": "XY",
                        "loops": [
                            {
                                "segments": [
                                    {"type": "line", "start": [-2, -2, 0], "end": [2, -2, 0]},
                                    {"type": "line", "start": [2, -2, 0], "end": [2, 2, 0]},
                                    {"type": "line", "start": [2, 2, 0], "end": [-2, 2, 0]},
                                    {"type": "line", "start": [-2, 2, 0], "end": [-2, -2, 0]},
                                ],
                            }
                        ],
                        "lock_mode": "block",
                        "require_fully_constrained": True,
                        "timeout_sec": 90,
                    }
                ),
                "worker_tip_pocket_profile",
            )
            if not worker_tip_pocket_profile["attachment"]["attached"]:
                raise RuntimeError(f"worker Tip pocket profile did not attach: {worker_tip_pocket_profile}")
            worker_tip_pocket = worker_result(
                service.definition_map()["freecad_worker_partdesign_pocket"].handler(
                    {
                        "session_id": session_id,
                        "document_id": tip_document_id,
                        "body_name": "WorkerTipBody",
                        "sketch_name": "WorkerTipPocketSketch",
                        "pocket_name": "WorkerTipPocket",
                        "length": 4,
                        "timeout_sec": 90,
                    }
                ),
                "worker_tip_pocket",
            )
            if worker_tip_pocket["body"]["partdesign"]["tip"] != "WorkerTipPocket":
                raise RuntimeError(f"worker Tip pocket did not become Body Tip: {worker_tip_pocket}")
            worker_tip_to_pad = worker_result(
                service.definition_map()["freecad_worker_object_set_properties"].handler(
                    {
                        "session_id": session_id,
                        "document_id": tip_document_id,
                        "object_name": "WorkerTipBody",
                        "properties": {"Tip": {"$ref": "WorkerTipPad"}},
                    }
                ),
                "worker_tip_body_tip_set_to_pad",
            )
            if worker_tip_to_pad["changed"]["Tip"]["$ref"] != "WorkerTipPad" or worker_tip_to_pad["object"]["partdesign"]["tip"] != "WorkerTipPad":
                raise RuntimeError(f"worker Body Tip $ref property set failed: {worker_tip_to_pad}")
            worker_tip_to_pocket = worker_result(
                service.definition_map()["freecad_worker_object_set_properties"].handler(
                    {
                        "session_id": session_id,
                        "document_id": tip_document_id,
                        "object_name": "WorkerTipBody",
                        "properties": {"Tip": {"$ref": "WorkerTipPocket"}},
                    }
                ),
                "worker_tip_body_tip_set_to_pocket",
            )
            if worker_tip_to_pocket["object"]["partdesign"]["tip"] != "WorkerTipPocket":
                raise RuntimeError(f"worker Body Tip restore to Pocket failed: {worker_tip_to_pocket}")
            worker_deleted_tip = worker_result(
                service.definition_map()["freecad_worker_object_delete"].handler(
                    {
                        "session_id": session_id,
                        "document_id": tip_document_id,
                        "object_name": "WorkerTipPocket",
                    }
                ),
                "worker_tip_current_tip_delete",
            )
            if worker_deleted_tip["tip_restorations"] != [{"body": "WorkerTipBody", "before_tip": "WorkerTipPocket", "after_tip": "WorkerTipPad", "restored": True}]:
                raise RuntimeError(f"worker Body Tip was not restored before deleting current Tip: {worker_deleted_tip}")
            worker_tip_body_after_delete = next(obj for obj in worker_deleted_tip["document"]["objects"] if obj["name"] == "WorkerTipBody")
            if worker_tip_body_after_delete["partdesign"]["tip"] != "WorkerTipPad":
                raise RuntimeError(f"worker Body Tip after delete is not WorkerTipPad: {worker_deleted_tip}")
            worker_result(
                service.definition_map()["freecad_worker_document_close"].handler(
                    {"session_id": session_id, "document_id": tip_document_id}
                ),
                "worker_tip_document_close",
            )

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
                service.definition_map()["freecad_worker_session_close"].handler({"session_id": session_id, "timeout_sec": 30})

    print("persistent worker smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
