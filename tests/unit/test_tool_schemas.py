from __future__ import annotations

import unittest
from pathlib import Path

from freecad_mcp.cad_tools import CadToolService
from freecad_mcp.mcp_stdio import CompositeToolService
from freecad_mcp.runtime_tools import RuntimeToolService
from freecad_mcp.static_tools import InventoryStore, StaticToolService


class ToolSchemaTests(unittest.TestCase):
    def test_no_duplicate_tool_names_and_all_schemas_are_objects(self) -> None:
        root = Path(__file__).resolve().parents[2]
        service = CompositeToolService(
            StaticToolService(InventoryStore(root)),
            RuntimeToolService(),
            CadToolService(),
        )

        tools = [definition.to_mcp() for definition in service.definitions()]
        names = [tool["name"] for tool in tools]

        self.assertEqual(len(names), len(set(names)))
        self.assertGreater(len(names), 30)
        for tool in tools:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertIn("properties", tool["inputSchema"])

    def test_unsafe_python_schema_has_opt_in_and_max_length(self) -> None:
        service = RuntimeToolService()
        tool = service.definition_map()["freecad_python_exec"].to_mcp()
        props = tool["inputSchema"]["properties"]

        self.assertEqual(props["code"]["maxLength"], 20000)
        self.assertIn("allow_unsafe", props)


if __name__ == "__main__":
    unittest.main()
