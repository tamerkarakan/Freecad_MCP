from __future__ import annotations

import json
import unittest

from freecad_mcp.mcp_stdio import McpServer
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
