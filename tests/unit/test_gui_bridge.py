from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from freecad_mcp.gui_bridge import GuiBridgeClient, GuiBridgeManager
from freecad_mcp.gui_tools import GuiToolService
from freecad_mcp.tooling import ToolInputError


class FakeBridgeHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        FakeBridgeHandler.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "payload": payload,
            }
        )

        method = payload.get("method")
        if self.path != "/rpc":
            self.send_payload({"ok": False, "error": "unknown path"}, status=404)
            return
        if method == "fail":
            self.send_payload({"ok": False, "error": "bridge rejected request"}, status=200)
            return
        if method == "status":
            result = {"bridge": "ok", "active_document": {"name": "Doc"}}
        elif method == "selection_get":
            result = {
                "selection": [
                    {"document_name": "Doc", "object_name": "Box", "subelement_names": ["Face1"]}
                ],
                "count": 1,
            }
        elif method == "sketch_state":
            result = {"active_sketch": {"object": {"name": "Sketch"}}, "params": payload.get("params") or {}}
        elif method == "partdesign_state":
            result = {"active_body": {"object": {"name": "Body"}}, "params": payload.get("params") or {}}
        else:
            result = {"method": method, "params": payload.get("params") or {}}
        self.send_payload({"ok": True, "result": result})

    def send_payload(self, payload: dict[str, Any], *, status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


class GuiBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeBridgeHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeBridgeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_manager_attaches_with_probe_and_token_then_calls(self) -> None:
        manager = GuiBridgeManager(GuiBridgeClient())

        attached = manager.attach(url=self.url, token="secret", probe=True)
        session_id = attached["session"]["session_id"]
        selected = manager.call(session_id, "selection_get", {"document_name": "Doc"})

        self.assertEqual(attached["status"]["bridge"], "ok")
        self.assertEqual(selected["gui"]["count"], 1)
        self.assertEqual(selected["session"]["request_count"], 2)
        self.assertEqual(FakeBridgeHandler.requests[0]["authorization"], "Bearer secret")
        self.assertEqual(FakeBridgeHandler.requests[1]["payload"]["params"]["document_name"], "Doc")

    def test_manager_reports_unknown_session_and_safe_detach(self) -> None:
        manager = GuiBridgeManager()

        with self.assertRaisesRegex(ToolInputError, "unknown GUI bridge session"):
            manager.call("missing", "status")

        detached = manager.detach("missing")
        self.assertTrue(detached["already_detached"])

    def test_client_converts_bridge_errors_to_tool_input_errors(self) -> None:
        client = GuiBridgeClient()

        with self.assertRaisesRegex(ToolInputError, "bridge rejected request"):
            client.call(url=self.url, method="fail")

    def test_gui_tool_service_delegates_to_manager(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url, "token": "secret"})
        session_id = attached["session"]["session_id"]
        status = tools["freecad_gui_status"].handler({"session_id": session_id})

        self.assertEqual(status["gui"]["bridge"], "ok")
        self.assertIn("freecad_gui_selection_get", tools)
        self.assertIn("freecad_gui_primitive_create", tools)
        self.assertIn("freecad_gui_sketch_state", tools)
        self.assertIn("freecad_gui_partdesign_state", tools)

    def test_gui_primitive_create_delegates_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        created = tools["freecad_gui_primitive_create"].handler(
            {
                "session_id": session_id,
                "primitive": "cylinder",
                "object_name": "GuiCylinder",
                "radius": 4,
                "height": 12,
                "select": True,
                "fit_view": True,
            }
        )

        self.assertEqual(created["gui"]["method"], "primitive_create")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["params"]["object_name"], "GuiCylinder")

    def test_gui_sketch_and_partdesign_state_delegate_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        sketch = tools["freecad_gui_sketch_state"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "sketch_name": "Sketch",
                "include_constraints": True,
            }
        )
        partdesign = tools["freecad_gui_partdesign_state"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "body_name": "Body",
            }
        )

        self.assertEqual(sketch["gui"]["active_sketch"]["object"]["name"], "Sketch")
        self.assertEqual(partdesign["gui"]["active_body"]["object"]["name"], "Body")
        self.assertEqual(FakeBridgeHandler.requests[-2]["payload"]["method"], "sketch_state")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "partdesign_state")


if __name__ == "__main__":
    unittest.main()
