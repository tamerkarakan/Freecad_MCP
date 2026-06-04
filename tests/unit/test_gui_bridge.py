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
        if method == "stale_bridge":
            self.send_payload({"ok": False, "error": "unknown method: document_open"}, status=500)
            return
        if method == "status":
            result = {
                "bridge": {
                    "running": True,
                    "api_version": 4,
                    "methods": ["active_document_get", "document_open", "status", "view_orientation_set", "visibility_ensure"],
                    "rpc_count": len(FakeBridgeHandler.requests),
                    "in_flight": 1,
                },
                "active_document": {"name": "Doc"},
            }
        elif method == "selection_get":
            result = {
                "selection": [
                    {"document_name": "Doc", "object_name": "Box", "subelement_names": ["Face1"]}
                ],
                "count": 1,
            }
        elif method == "sketch_state":
            result = {"active_sketch": {"object": {"name": "Sketch"}}, "params": payload.get("params") or {}}
        elif method == "sketch_enter":
            result = {"entered": True, "sketch": {"object": {"name": "Sketch"}}, "params": payload.get("params") or {}}
        elif method == "sketch_leave":
            result = {"left": True, "sketch": {"object": {"name": "Sketch"}}, "params": payload.get("params") or {}}
        elif method == "partdesign_state":
            result = {"active_body": {"object": {"name": "Body"}}, "params": payload.get("params") or {}}
        elif method == "body_activate":
            result = {"activated": {"name": "Body"}, "params": payload.get("params") or {}}
        elif method == "feature_task_state":
            result = {"control": {"has_active_dialog": True}, "params": payload.get("params") or {}}
        elif method == "object_label_set":
            result = {"object": {"name": "Box", "label": payload.get("params", {}).get("label")}, "params": payload.get("params") or {}}
        elif method == "document_open":
            params = payload.get("params") or {}
            result = {
                "opened": True,
                "already_open": False,
                "document_path": params.get("document_path"),
                "document": {"name": "OpenedDoc", "file_name": params.get("document_path")},
                "active_document": {"name": "OpenedDoc"},
                "visibility": {
                    "requested": params.get("ensure_visible", True),
                    "scope": params.get("visibility_scope", "final"),
                    "visible_count": 2,
                },
                "fit": {"requested": params.get("fit_view", True), "fit": "all"},
                "params": params,
            }
        elif method == "visibility_ensure":
            params = payload.get("params") or {}
            result = {
                "visibility": {
                    "requested": True,
                    "scope": params.get("scope", "final"),
                    "target_count": 2,
                    "visible_count": 2,
                },
                "params": params,
            }
        elif method == "view_orientation_set":
            params = payload.get("params") or {}
            result = {
                "orientation": params.get("orientation", "isometric"),
                "view_method": "viewIsometric",
                "fit": {"requested": params.get("fit_view", True), "fit": "all"},
                "params": params,
            }
        elif method == "view_snapshot":
            params = payload.get("params") or {}
            result = {
                "snapshot": {
                    "path": params.get("output_path"),
                    "width": params.get("width", 1280),
                    "height": params.get("height", 720),
                    "format": params.get("format", "png"),
                    "bytes": 1234,
                },
                "params": params,
            }
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

        self.assertEqual(attached["status"]["bridge"]["api_version"], 4)
        self.assertIn("document_open", attached["status"]["bridge"]["methods"])
        self.assertEqual(selected["gui"]["count"], 1)
        self.assertEqual(selected["session"]["request_count"], 2)
        self.assertTrue(selected["session"]["watchdog"]["healthy"])
        self.assertEqual(FakeBridgeHandler.requests[0]["authorization"], "Bearer secret")
        self.assertEqual(FakeBridgeHandler.requests[1]["payload"]["params"]["document_name"], "Doc")
        self.assertEqual(FakeBridgeHandler.requests[1]["payload"]["timeout_sec"], 10)

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

    def test_manager_marks_session_unhealthy_after_call_failure(self) -> None:
        manager = GuiBridgeManager(GuiBridgeClient())

        attached = manager.attach(url=self.url)
        session_id = attached["session"]["session_id"]
        with self.assertRaisesRegex(ToolInputError, "marked unhealthy"):
            manager.call(session_id, "fail")
        watchdog = manager.watchdog_status(session_id)

        self.assertFalse(watchdog["ok"])
        self.assertEqual(watchdog["session"]["watchdog"]["consecutive_failures"], 1)
        self.assertIn("restart FreeCAD", watchdog["session"]["watchdog"]["recovery"])

    def test_watchdog_probe_refreshes_status(self) -> None:
        manager = GuiBridgeManager(GuiBridgeClient())

        attached = manager.attach(url=self.url)
        session_id = attached["session"]["session_id"]
        probed = manager.watchdog_status(session_id, probe=True, timeout_sec=2)

        self.assertTrue(probed["ok"])
        self.assertTrue(probed["session"]["watchdog"]["healthy"])
        self.assertEqual(probed["gui"]["bridge"]["api_version"], 4)

    def test_client_reports_stale_bridge_for_unknown_method(self) -> None:
        client = GuiBridgeClient()

        with self.assertRaisesRegex(ToolInputError, "restart FreeCAD"):
            client.call(url=self.url, method="stale_bridge")

    def test_gui_tool_service_delegates_to_manager(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url, "token": "secret"})
        session_id = attached["session"]["session_id"]
        status = tools["freecad_gui_status"].handler({"session_id": session_id})

        self.assertEqual(status["gui"]["bridge"]["api_version"], 4)
        self.assertIn("freecad_gui_selection_get", tools)
        self.assertIn("freecad_gui_watchdog_status", tools)
        self.assertIn("freecad_gui_document_open", tools)
        self.assertIn("freecad_gui_view_snapshot", tools)
        self.assertIn("freecad_gui_view_orientation_set", tools)
        self.assertIn("freecad_gui_primitive_create", tools)
        self.assertIn("freecad_gui_object_label_set", tools)
        self.assertIn("freecad_gui_sketch_state", tools)
        self.assertIn("freecad_gui_sketch_enter", tools)
        self.assertIn("freecad_gui_sketch_leave", tools)
        self.assertIn("freecad_gui_partdesign_state", tools)
        self.assertIn("freecad_gui_body_activate", tools)
        self.assertIn("freecad_gui_feature_task_state", tools)

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

    def test_gui_document_open_delegates_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        opened = tools["freecad_gui_document_open"].handler(
            {
                "session_id": session_id,
                "document_path": "C:/tmp/generated-model.FCStd",
                "activate": True,
                "fit_view": True,
                "ensure_visible": True,
                "visibility_scope": "final",
            }
        )

        self.assertTrue(opened["gui"]["opened"])
        self.assertEqual(opened["gui"]["document"]["file_name"], "C:/tmp/generated-model.FCStd")
        self.assertEqual(opened["gui"]["visibility"]["visible_count"], 2)
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "document_open")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["params"]["document_path"], "C:/tmp/generated-model.FCStd")
        self.assertTrue(FakeBridgeHandler.requests[-1]["payload"]["params"]["ensure_visible"])

    def test_gui_visibility_ensure_delegates_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        visibility = tools["freecad_gui_visibility_ensure"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "object_name": "Body",
                "scope": "final",
                "fit_view": True,
            }
        )

        self.assertEqual(visibility["gui"]["visibility"]["visible_count"], 2)
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "visibility_ensure")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["params"]["object_name"], "Body")

    def test_gui_view_orientation_set_delegates_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        oriented = tools["freecad_gui_view_orientation_set"].handler(
            {
                "session_id": session_id,
                "orientation": "isometric",
                "fit_view": True,
                "selection_only": False,
            }
        )

        self.assertEqual(oriented["gui"]["orientation"], "isometric")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "view_orientation_set")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["params"]["orientation"], "isometric")

    def test_gui_view_snapshot_delegates_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        snapshot = tools["freecad_gui_view_snapshot"].handler(
            {
                "session_id": session_id,
                "output_path": "C:/tmp/freecad-view.png",
                "width": 1024,
                "height": 768,
                "format": "png",
                "background": "Current",
                "fit_view": True,
                "overwrite": True,
            }
        )

        self.assertEqual(snapshot["gui"]["snapshot"]["path"], "C:/tmp/freecad-view.png")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "view_snapshot")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["params"]["width"], 1024)

    def test_gui_object_label_set_delegates_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        renamed = tools["freecad_gui_object_label_set"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "object_name": "Box",
                "label": "Main Housing",
                "require_unique": True,
            }
        )

        self.assertEqual(renamed["gui"]["object"]["label"], "Main Housing")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "object_label_set")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["params"]["label"], "Main Housing")

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

    def test_gui_sketch_edit_and_body_activate_delegate_to_bridge(self) -> None:
        service = GuiToolService()
        tools = service.definition_map()

        attached = tools["freecad_gui_attach"].handler({"url": self.url})
        session_id = attached["session"]["session_id"]
        entered = tools["freecad_gui_sketch_enter"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "sketch_name": "Sketch",
                "reset_existing": True,
            }
        )
        left = tools["freecad_gui_sketch_leave"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "sketch_name": "Sketch",
                "recompute": True,
            }
        )
        activated = tools["freecad_gui_body_activate"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "body_name": "Body",
                "set_active_view_object": True,
            }
        )
        task_state = tools["freecad_gui_feature_task_state"].handler(
            {
                "session_id": session_id,
                "document_name": "Doc",
                "include_widget_tree": False,
            }
        )

        self.assertTrue(entered["gui"]["entered"])
        self.assertTrue(left["gui"]["left"])
        self.assertEqual(activated["gui"]["activated"]["name"], "Body")
        self.assertTrue(task_state["gui"]["control"]["has_active_dialog"])
        self.assertEqual(FakeBridgeHandler.requests[-4]["payload"]["method"], "sketch_enter")
        self.assertEqual(FakeBridgeHandler.requests[-3]["payload"]["method"], "sketch_leave")
        self.assertEqual(FakeBridgeHandler.requests[-2]["payload"]["method"], "body_activate")
        self.assertEqual(FakeBridgeHandler.requests[-1]["payload"]["method"], "feature_task_state")


if __name__ == "__main__":
    unittest.main()
