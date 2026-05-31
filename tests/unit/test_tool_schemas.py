from __future__ import annotations

import unittest
from pathlib import Path

from freecad_mcp.cad_tools import CadToolService
from freecad_mcp.gui_tools import GuiToolService
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
            GuiToolService(),
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
            "freecad_worker_partdesign_body_create",
            "freecad_worker_partdesign_pad",
            "freecad_worker_partdesign_pocket",
            "freecad_worker_part_check_geometry",
            "freecad_worker_sketch_create",
            "freecad_worker_sketch_add_profile",
            "freecad_worker_sketch_profile_create",
            "freecad_worker_sketch_profile_validate",
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
            "freecad_worker_object_rename_label",
            "freecad_worker_object_delete",
        ]:
            self.assertIn(name, tools)

        validate_props = tools["freecad_worker_sketch_profile_validate"].to_mcp()["inputSchema"]["properties"]
        self.assertIn("expected_geometry", validate_props)
        self.assertIn("required_segment_types", validate_props)

    def test_gui_attach_tools_are_exposed(self) -> None:
        tools = GuiToolService().definition_map()

        for name in [
            "freecad_gui_attach",
            "freecad_gui_list",
            "freecad_gui_detach",
            "freecad_gui_status",
            "freecad_gui_active_document_get",
            "freecad_gui_active_view_get",
            "freecad_gui_selection_get",
            "freecad_gui_preselection_get",
            "freecad_gui_selection_set",
            "freecad_gui_view_fit",
            "freecad_gui_primitive_create",
            "freecad_gui_object_label_set",
            "freecad_gui_sketch_state",
            "freecad_gui_sketch_enter",
            "freecad_gui_sketch_leave",
            "freecad_gui_partdesign_state",
            "freecad_gui_body_activate",
            "freecad_gui_feature_task_state",
        ]:
            self.assertIn(name, tools)

    def test_techdraw_tools_are_exposed(self) -> None:
        tools = CadToolService().definition_map()

        for name in [
            "freecad_techdraw_page_create",
            "freecad_techdraw_view_create",
            "freecad_techdraw_inspect",
            "freecad_techdraw_page_export",
        ]:
            self.assertIn(name, tools)

    def test_cam_and_fem_tools_are_exposed(self) -> None:
        tools = CadToolService().definition_map()

        for name in [
            "freecad_cam_path_create",
            "freecad_cam_path_inspect",
            "freecad_cam_path_export",
            "freecad_fem_analysis_create",
            "freecad_fem_material_create",
            "freecad_fem_constraint_create",
            "freecad_fem_inspect",
        ]:
            self.assertIn(name, tools)

    def test_partdesign_tools_are_exposed(self) -> None:
        tools = CadToolService().definition_map()

        for name in [
            "freecad_partdesign_body_create",
            "freecad_partdesign_pad",
            "freecad_partdesign_pocket",
        ]:
            self.assertIn(name, tools)
        sketch_props = tools["freecad_sketch_create"].to_mcp()["inputSchema"]["properties"]
        self.assertIn("body_name", sketch_props)
        self.assertIn("attachment_plane", sketch_props)

    def test_object_label_rename_tool_is_exposed(self) -> None:
        tools = CadToolService().definition_map()

        self.assertIn("freecad_object_rename_label", tools)
        props = tools["freecad_object_rename_label"].to_mcp()["inputSchema"]["properties"]
        self.assertIn("label", props)
        self.assertIn("require_unique", props)

    def test_sketch_profile_tools_are_exposed(self) -> None:
        tools = CadToolService().definition_map()

        for name in [
            "freecad_sketch_profile_create",
            "freecad_sketch_profile_validate",
            "freecad_curve_fit_analyze",
            "freecad_sketch_geometry_method_catalog",
        ]:
            self.assertIn(name, tools)

        props = tools["freecad_sketch_profile_create"].to_mcp()["inputSchema"]["properties"]
        for name in [
            "required_segment_types",
            "minimum_curve_segments",
            "forbid_polyline_fallback",
            "forbid_all_line_loops",
        ]:
            self.assertIn(name, props)
        validate_props = tools["freecad_sketch_profile_validate"].to_mcp()["inputSchema"]["properties"]
        for name in [
            "expected_geometry",
            "required_segment_types",
            "minimum_curve_segments",
            "forbid_intent_mismatch",
        ]:
            self.assertIn(name, validate_props)
        self.assertIn("points", tools["freecad_curve_fit_analyze"].to_mcp()["inputSchema"]["properties"])


if __name__ == "__main__":
    unittest.main()
