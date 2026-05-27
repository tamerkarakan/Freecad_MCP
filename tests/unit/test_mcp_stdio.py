from __future__ import annotations

import json
import unittest
from io import StringIO

from freecad_mcp.mcp_stdio import McpServer, serve_stdio
from freecad_mcp.tooling import ToolDefinition


class McpStdioTests(unittest.TestCase):
    def test_initialize_and_tools_list_shape(self) -> None:
        server = McpServer(FakeToolService())

        initialized = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            }
        )
        tools = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

        self.assertEqual(initialized["result"]["capabilities"]["tools"]["listChanged"], False)
        self.assertEqual(tools["result"]["tools"][0]["name"], "demo")
        self.assertIn("inputSchema", tools["result"]["tools"][0])

    def test_tool_call_returns_structured_content_and_text_fallback(self) -> None:
        server = McpServer(FakeToolService())

        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "demo", "arguments": {"value": "spark"}},
            }
        )

        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["echo"], "spark")
        self.assertEqual(json.loads(result["content"][0]["text"])["echo"], "spark")

    def test_resources_and_prompts_are_listed(self) -> None:
        server = McpServer(FakeToolService())

        resources = server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
        resource_templates = server.handle_message(
            {"jsonrpc": "2.0", "id": 5, "method": "resources/templates/list"}
        )
        prompts = server.handle_message({"jsonrpc": "2.0", "id": 6, "method": "prompts/list"})
        prompt = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "prompts/get",
                "params": {"name": "freecad_design_task", "arguments": {"task": "make a cube"}},
            }
        )

        self.assertIn("resources", resources["result"])
        self.assertEqual(resource_templates["result"]["resourceTemplates"], [])
        self.assertIn("prompts", prompts["result"])
        self.assertIn("make a cube", prompt["result"]["messages"][0]["content"]["text"])

    def test_serve_stdio_falls_back_when_response_is_not_serializable(self) -> None:
        server = BrokenResponseServer()
        stdin = StringIO('{"jsonrpc":"2.0","id":9,"method":"ping"}\n')
        stdout = StringIO()

        exit_code = serve_stdio(server, stdin=stdin, stdout=stdout)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue().strip())
        self.assertEqual(payload["error"]["code"], -32603)
        self.assertIn("failed to encode response", payload["error"]["data"]["detail"])


class FakeToolService:
    def definitions(self):
        return [
            ToolDefinition(
                name="demo",
                title="Demo",
                description="Demo tool",
                input_schema={"type": "object", "properties": {"value": {"type": "string"}}},
                handler=lambda args: {"echo": args["value"]},
            )
        ]

    def definition_map(self):
        return {definition.name: definition for definition in self.definitions()}


class BrokenResponseServer:
    def handle_message(self, message):
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": {"bad": {1, 2, 3}}}
