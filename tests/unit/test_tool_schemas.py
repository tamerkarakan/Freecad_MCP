from __future__ import annotations

import unittest
from pathlib import Path

from freecad_mcp.cad_tools import CadToolService
from freecad_mcp.mcp_stdio import CompositeToolService
from freecad_mcp.persistent_tools import PersistentToolService
from freecad_mcp.runtime_tools import RuntimeToolService
from freecad_mcp.static_tools import InventoryStore, StaticToolService


class ToolSchemaTests(unittest.TestCase):
    def test_no_duplicate_tool_names_and_all_schemas_are_objects(self) -> None:
        root = Path(__file__).resolve().parents[2]
        service = CompositeToolService(
            StaticToolService(InventoryStore(root)),
            RuntimeToolService(),
            PersistentToolService(workspace_root=root),
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

    def test_persistent_worker_tools_are_exposed(self) -> None:
        tools = PersistentToolService().definition_map()

        for name in [
            "freecad_session_start",
            "freecad_session_list",
            "freecad_session_close",
            "freecad_worker_session_start",
            "freecad_worker_session_status",
            "freecad_worker_document_new",
            "freecad_worker_document_export",
            "freecad_worker_part_create_primitive",
            "freecad_worker_part_boolean",
            "freecad_worker_part_check_geometry",
            "freecad_worker_sketch_create",
            "freecad_worker_sketch_add_profile",
            "freecad_worker_sketch_add_geometry",
            "freecad_worker_sketch_add_constraint",
            "freecad_worker_sketch_validate",
            "freecad_worker_mesh_import",
            "freecad_worker_mesh_repair",
            "freecad_worker_mesh_evaluate",
            "freecad_worker_assembly_create",
            "freecad_worker_assembly_insert",
            "freecad_worker_assembly_create_joint",
            "freecad_worker_object_get",
            "freecad_worker_object_set_properties",
            "freecad_worker_object_delete",
        ]:
            self.assertIn(name, tools)


if __name__ == "__main__":
    unittest.main()
