from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from freecad_mcp.persistent_bridge import FreeCadWorkerSession, PersistentBridgeManager
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
    emit({"id": request.get("id"), "ok": True, "result": {"method": method, "params": request.get("params") or {}}})
'''


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

    def test_unknown_session_raises_tool_error(self) -> None:
        manager = PersistentBridgeManager(worker_script=FAKE_WORKER_SCRIPT)

        with self.assertRaises(ToolInputError):
            manager.status("missing", timeout_sec=1)


if __name__ == "__main__":
    unittest.main()
