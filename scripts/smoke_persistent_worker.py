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
