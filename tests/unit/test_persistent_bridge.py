from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from freecad_mcp.persistent_bridge import (
    FREECAD_WORKER_SCRIPT,
    WORKER_PREFIX,
    FreeCadWorkerSession,
    PersistentBridgeManager,
)
from freecad_mcp.persistent_tools import PersistentToolService
from freecad_mcp.runtime_bridge import MAX_INLINE_CODE_CHARS
from freecad_mcp.tooling import ToolInputError


FAKE_WORKER_SCRIPT = r'''
import json
import sys

PREFIX = "__FREECAD_MCP_WORKER__"


def emit(payload):
    sys.stdout.write(PREFIX + json.dumps(payload) + "\n")
    sys.stdout.flush()


emit({"type": "ready", "version": ["fake"], "pid": 1})
for raw in sys.stdin:
    request = json.loads(raw)
    method = request.get("method")
    if method == "shutdown":
        emit({"id": request.get("id"), "ok": True, "result": {"closed": True}})
        break
    if method == "fail":
        emit({"id": request.get("id"), "ok": False, "error": "planned failure", "traceback": "trace"})
        continue
    if method == "crash":
        sys.stderr.write("planned crash\n")
        sys.stderr.flush()
        raise SystemExit(7)
    if method == "console":
        sys.stdout.write("FreeCAD console hello\n")
        sys.stdout.flush()
        sys.stderr.write("a warning line\n")
        sys.stderr.flush()
        emit({"id": request.get("id"), "ok": True, "result": {"printed": True}})
        continue
    emit({"id": request.get("id"), "ok": True, "result": {"method": method, "params": request.get("params") or {}}})
'''


class WorkerScriptTests(unittest.TestCase):
    def test_worker_script_is_valid_python_with_protocol_markers(self) -> None:
        # Guards the embedded worker-script contract after it moved to an external
        # file: it must stay valid Python and keep the stdout framing prefix and
        # the action dispatch table the host relies on.
        self.assertGreater(len(FREECAD_WORKER_SCRIPT), 1000)
        self.assertIn(WORKER_PREFIX, FREECAD_WORKER_SCRIPT)
        self.assertIn("ACTIONS", FREECAD_WORKER_SCRIPT)
        compile(FREECAD_WORKER_SCRIPT, "<worker_script>", "exec")


class PersistentBridgeTests(unittest.TestCase):
    def test_worker_session_request_and_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = FreeCadWorkerSession(
                session_id="test",
                executable=Path(sys.executable),
                workspace_root=Path(temp_dir),
                worker_script=FAKE_WORKER_SCRIPT,
            )

            started = session.start(timeout_sec=10)
            response = session.request("ping", {"value": "ok"}, timeout_sec=10)
            closed = session.close(timeout_sec=10)

        self.assertEqual(started["ready"]["type"], "ready")
        self.assertTrue(response.ok)
        self.assertEqual(response.result["method"], "ping")
        self.assertEqual(response.result["params"]["value"], "ok")
        self.assertFalse(closed["session"]["running"])

    def test_worker_session_uses_temp_script_for_long_worker_code(self) -> None:
        long_worker_script = FAKE_WORKER_SCRIPT + ("\n# filler" * (MAX_INLINE_CODE_CHARS // 4))
        with tempfile.TemporaryDirectory() as temp_dir:
            session = FreeCadWorkerSession(
                session_id="test",
                executable=Path(sys.executable),
                workspace_root=Path(temp_dir),
                worker_script=long_worker_script,
            )

            started = session.start(timeout_sec=10)
            script_path = session._script_path
            response = session.request("ping", {"value": "ok"}, timeout_sec=10)
            closed = session.close(timeout_sec=10)

        self.assertEqual(started["ready"]["type"], "ready")
        self.assertIsNotNone(script_path)
        self.assertFalse(script_path.exists())
        self.assertIsNone(session._script_path)
        self.assertTrue(response.ok)
        self.assertEqual(response.result["method"], "ping")
        self.assertFalse(closed["session"]["running"])

    def test_worker_failure_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = FreeCadWorkerSession(
                session_id="test",
                executable=Path(sys.executable),
                workspace_root=Path(temp_dir),
                worker_script=FAKE_WORKER_SCRIPT,
            )
            session.start(timeout_sec=10)
            response = session.request("fail", {}, timeout_sec=10)
            session.close(timeout_sec=10)

        self.assertFalse(response.ok)
        self.assertEqual(response.error, "planned failure")
        self.assertEqual(response.to_dict()["traceback"], "trace")

    def test_manager_drops_closed_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistentBridgeManager(workspace_root=Path(temp_dir), worker_script=FAKE_WORKER_SCRIPT)
            started = manager.start_session(executable=sys.executable, timeout_sec=10)
            session_id = started["session"]["session_id"]

            listed = manager.list_sessions()
            closed = manager.close(session_id, timeout_sec=10)
            closed_again = manager.close(session_id, timeout_sec=10)

        self.assertEqual(listed["count"], 1)
        self.assertEqual(closed["session"]["session_id"], session_id)
        self.assertTrue(closed_again["already_closed"])
        self.assertEqual(manager.list_sessions()["count"], 0)

    def test_manager_drops_crashed_session_after_request_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistentBridgeManager(workspace_root=Path(temp_dir), worker_script=FAKE_WORKER_SCRIPT)
            started = manager.start_session(executable=sys.executable, timeout_sec=10)
            session_id = started["session"]["session_id"]

            with self.assertRaisesRegex(ToolInputError, "worker exited"):
                manager.request(session_id, "crash", {}, timeout_sec=10)

        self.assertEqual(manager.list_sessions()["count"], 0)
        self.assertTrue(manager.close(session_id)["already_closed"])

    def test_manager_enforces_max_session_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistentBridgeManager(
                workspace_root=Path(temp_dir),
                worker_script=FAKE_WORKER_SCRIPT,
                max_sessions=1,
            )
            started = manager.start_session(executable=sys.executable, timeout_sec=10)
            session_id = started["session"]["session_id"]
            try:
                with self.assertRaisesRegex(ToolInputError, "session limit"):
                    manager.start_session(executable=sys.executable, timeout_sec=10)
            finally:
                manager.close(session_id, timeout_sec=10)

            self.assertEqual(manager.list_sessions()["count"], 0)
            # A freed slot lets a new session start again.
            reopened = manager.start_session(executable=sys.executable, timeout_sec=10)
            manager.close(reopened["session"]["session_id"], timeout_sec=10)

    def test_console_captures_non_protocol_stdout_and_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistentBridgeManager(workspace_root=Path(temp_dir), worker_script=FAKE_WORKER_SCRIPT)
            started = manager.start_session(executable=sys.executable, timeout_sec=10)
            session_id = started["session"]["session_id"]
            try:
                response = manager.request(session_id, "console", {}, timeout_sec=10)
                self.assertTrue(response["ok"])
                console = manager.console(session_id, max_lines=50)["console"]
            finally:
                manager.close(session_id, timeout_sec=10)

        # Non-protocol stdout (FreeCAD console) is captured, not dropped, and the
        # protocol reply is NOT misfiled as console output.
        self.assertIn("FreeCAD console hello", console["stdout_console"])
        self.assertFalse(any(WORKER_PREFIX in line for line in console["stdout_console"]))
        self.assertIn("a warning line", console["stderr"])

    def test_unknown_session_raises_tool_error(self) -> None:
        manager = PersistentBridgeManager(worker_script=FAKE_WORKER_SCRIPT)

        with self.assertRaises(ToolInputError):
            manager.status("missing", timeout_sec=1)

    def _started_service(self, temp_dir: str):
        # Real worker session so manager.get(session_id) succeeds: the selector
        # guard becomes the ONLY thing that can raise. If a guard is removed, the
        # request reaches the live fake worker and returns ok, so the test fails
        # (the old session_id="missing" form passed even with the guard deleted).
        manager = PersistentBridgeManager(workspace_root=Path(temp_dir), worker_script=FAKE_WORKER_SCRIPT)
        service = PersistentToolService(manager=manager)
        started = manager.start_session(executable=sys.executable, timeout_sec=10)
        return service, manager, started["session"]["session_id"]

    def test_object_delete_requires_object_selector_before_worker_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, manager, session_id = self._started_service(temp_dir)
            try:
                with self.assertRaisesRegex(ToolInputError, "object_name or object_names"):
                    service.definition_map()["freecad_worker_object_delete"].handler(
                        {"session_id": session_id, "document_id": "Doc"}
                    )
            finally:
                manager.close(session_id, timeout_sec=10)

    def test_worker_boolean_requires_two_objects_before_worker_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, manager, session_id = self._started_service(temp_dir)
            try:
                with self.assertRaisesRegex(ToolInputError, "at least two objects"):
                    service.definition_map()["freecad_worker_mesh_boolean"].handler(
                        {"session_id": session_id, "document_id": "Doc", "object_names": ["Mesh"]}
                    )
            finally:
                manager.close(session_id, timeout_sec=10)

    def test_worker_assembly_joint_requires_reference_pair_before_worker_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, manager, session_id = self._started_service(temp_dir)
            try:
                with self.assertRaisesRegex(ToolInputError, "exactly two connector references"):
                    service.definition_map()["freecad_worker_assembly_create_joint"].handler(
                        {
                            "session_id": session_id,
                            "document_id": "Doc",
                            "assembly_name": "Assembly",
                            "references": [{"object_name": "Box", "sub_element": "Face1"}],
                        }
                    )
            finally:
                manager.close(session_id, timeout_sec=10)


if __name__ == "__main__":
    unittest.main()
