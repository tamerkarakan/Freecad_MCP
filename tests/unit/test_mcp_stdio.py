from __future__ import annotations

import unittest
from pathlib import Path

from freecad_mcp.mcp_stdio import (
    PROMPT_DESCRIPTORS,
    RESOURCE_DESCRIPTORS,
    CompositeToolService,
    build_server,
    create_mcp_server,
    read_resource,
    render_prompt,
    resolve_repo_root,
)
from freecad_mcp.module_registry import is_hidden_mcp_tool, parse_module_selection, tool_modules
from freecad_mcp.tooling import ToolDefinition, ToolInputError


ROOT = Path(__file__).resolve().parents[2]


class CompositeToolServiceTests(unittest.TestCase):
    def test_aggregates_definitions_and_map(self) -> None:
        composite = CompositeToolService(FakeToolService())

        self.assertEqual([d.name for d in composite.definitions()], ["demo"])
        self.assertIn("demo", composite.definition_map())

    def test_shutdown_fans_out_to_services(self) -> None:
        service = FakeToolService()
        composite = CompositeToolService(service)

        composite.shutdown()

        self.assertTrue(service.was_shutdown)


class BuildServerTests(unittest.TestCase):
    def test_exposes_core_tool_surface(self) -> None:
        tools = build_server(ROOT).definition_map()

        for name in (
            "freecad_command_describe",
            "freecad_session_status",
            "freecad_session_start",
            "freecad_gui_attach",
            "freecad_partdesign_datum_plane_create",
            "freecad_partdesign_pad",
            "freecad_partdesign_pocket",
            "freecad_partdesign_hole",
            "freecad_partdesign_revolution",
            "freecad_partdesign_groove",
            "freecad_partdesign_additive_loft",
            "freecad_partdesign_subtractive_loft",
            "freecad_partdesign_additive_pipe",
            "freecad_partdesign_subtractive_pipe",
            "freecad_partdesign_fillet",
            "freecad_partdesign_chamfer",
            "freecad_partdesign_thickness",
            "freecad_partdesign_draft",
            "freecad_partdesign_linear_pattern",
            "freecad_partdesign_polar_pattern",
            "freecad_partdesign_mirrored",
            "freecad_partdesign_profile_feature_create",
            "freecad_partdesign_parametric_profile_feature_create",
            "freecad_partdesign_sweep_feature_create",
            "freecad_spreadsheet_create",
            "freecad_object_expression_set",
            "freecad_geometry_check",
        ):
            self.assertIn(name, tools)
        self.assertNotIn("freecad_part_create_primitive", tools)
        self.assertNotIn("freecad_worker_part_create_primitive", tools)

    def test_module_filter_can_expose_gui_only_surface(self) -> None:
        tools = build_server(ROOT, enabled_modules="gui").definition_map()

        self.assertIn("freecad_gui_attach", tools)
        self.assertIn("freecad_gui_document_open", tools)
        self.assertIn("freecad_gui_primitive_create", tools)
        self.assertIn("freecad_gui_view_snapshot", tools)
        self.assertIn("freecad_gui_view_orientation_set", tools)
        self.assertIn("freecad_gui_visibility_ensure", tools)
        self.assertIn("freecad_gui_object_label_set", tools)
        self.assertIn("freecad_gui_sketch_state", tools)
        self.assertIn("freecad_gui_sketch_enter", tools)
        self.assertIn("freecad_gui_sketch_leave", tools)
        self.assertIn("freecad_gui_partdesign_state", tools)
        self.assertIn("freecad_gui_body_activate", tools)
        self.assertIn("freecad_gui_feature_task_state", tools)
        self.assertNotIn("freecad_part_create_primitive", tools)
        self.assertNotIn("freecad_command_describe", tools)

    def test_product_profile_aliases_expand_to_expected_modules(self) -> None:
        selection = parse_module_selection("pro")
        tools = build_server(ROOT, enabled_modules="pro").definition_map()

        self.assertIn("gui", selection.expanded)
        self.assertIn("partdesign", selection.expanded)
        self.assertIn("freecad_gui_attach", tools)
        self.assertIn("freecad_gui_document_open", tools)
        self.assertIn("freecad_gui_view_orientation_set", tools)
        self.assertIn("freecad_gui_visibility_ensure", tools)
        self.assertIn("freecad_partdesign_datum_plane_create", tools)
        self.assertIn("freecad_partdesign_pad", tools)
        self.assertIn("freecad_partdesign_pocket", tools)
        self.assertIn("freecad_partdesign_hole", tools)
        self.assertIn("freecad_partdesign_revolution", tools)
        self.assertIn("freecad_partdesign_groove", tools)
        self.assertIn("freecad_partdesign_additive_loft", tools)
        self.assertIn("freecad_partdesign_subtractive_loft", tools)
        self.assertIn("freecad_partdesign_additive_pipe", tools)
        self.assertIn("freecad_partdesign_subtractive_pipe", tools)
        self.assertIn("freecad_partdesign_fillet", tools)
        self.assertIn("freecad_partdesign_chamfer", tools)
        self.assertIn("freecad_partdesign_thickness", tools)
        self.assertIn("freecad_partdesign_draft", tools)
        self.assertIn("freecad_partdesign_linear_pattern", tools)
        self.assertIn("freecad_partdesign_polar_pattern", tools)
        self.assertIn("freecad_partdesign_mirrored", tools)
        self.assertIn("freecad_partdesign_profile_feature_create", tools)
        self.assertIn("freecad_partdesign_parametric_profile_feature_create", tools)
        self.assertIn("freecad_partdesign_sweep_feature_create", tools)
        self.assertIn("freecad_object_rename_label", tools)
        self.assertIn("freecad_spreadsheet_create", tools)
        self.assertIn("freecad_object_expression_set", tools)
        self.assertIn("freecad_sketch_profile_create", tools)
        self.assertIn("freecad_geometry_check", tools)
        self.assertNotIn("freecad_part_create_primitive", tools)
        self.assertNotIn("freecad_worker_part_create_primitive", tools)
        self.assertNotIn("freecad_cam_path_create", tools)
        self.assertNotIn("freecad_fem_analysis_create", tools)
        self.assertNotIn("freecad_source_search", tools)
        self.assertNotIn("freecad_worker_document_new", tools)
        self.assertNotIn("freecad_worker_session_start", tools)

    def test_worker_tools_require_worker_module_even_when_domain_tag_matches(self) -> None:
        free_tools = build_server(ROOT, enabled_modules="free").definition_map()
        sketcher_tools = build_server(ROOT, enabled_modules="sketcher").definition_map()
        worker_tools = build_server(ROOT, enabled_modules="worker").definition_map()

        self.assertNotIn("freecad_worker_document_new", free_tools)
        self.assertNotIn("freecad_worker_sketch_profile_create", sketcher_tools)
        self.assertIn("freecad_worker_document_new", worker_tools)
        self.assertIn("freecad_worker_sketch_profile_create", worker_tools)

    def test_source_intelligence_requires_developer_module(self) -> None:
        studio_tools = build_server(ROOT, enabled_modules="studio").definition_map()
        team_tools = build_server(ROOT, enabled_modules="team").definition_map()
        source_tools = build_server(ROOT, enabled_modules="source").definition_map()

        self.assertNotIn("freecad_source_search", studio_tools)
        self.assertIn("freecad_source_search", team_tools)
        self.assertIn("freecad_source_search", source_tools)
        self.assertNotIn("freecad_document_new", source_tools)

    def test_developer_aliases_preserve_full_local_surface(self) -> None:
        all_tools = set(build_server(ROOT, enabled_modules="all").definition_map())

        for alias in ("default", "dev", "developer", "local-dev"):
            with self.subTest(alias=alias):
                alias_tools = set(build_server(ROOT, enabled_modules=alias).definition_map())
                self.assertEqual(alias_tools, all_tools)
                self.assertIn("freecad_python_exec", alias_tools)
                self.assertIn("freecad_worker_document_new", alias_tools)
                self.assertIn("freecad_source_search", alias_tools)

    def test_unsafe_escape_hatch_requires_explicit_module(self) -> None:
        team_tools = build_server(ROOT, enabled_modules="team").definition_map()
        unsafe_tools = build_server(ROOT, enabled_modules="unsafe").definition_map()

        self.assertNotIn("freecad_python_exec", team_tools)
        self.assertIn("freecad_python_exec", unsafe_tools)

    def test_tool_module_tags_cover_worker_domain_tools(self) -> None:
        self.assertIn("sketcher", tool_modules("freecad_worker_sketch_profile_create"))
        self.assertIn("headless", tool_modules("freecad_worker_part_create_primitive"))
        self.assertIn("headless", tool_modules("freecad_geometry_check"))
        self.assertIn("headless", tool_modules("freecad_worker_geometry_check"))
        self.assertIn("headless", tool_modules("freecad_spreadsheet_create"))
        self.assertIn("headless", tool_modules("freecad_object_expression_set"))
        self.assertIn("gui", tool_modules("freecad_gui_status"))
        self.assertTrue(is_hidden_mcp_tool("freecad_part_create_primitive"))
        self.assertTrue(is_hidden_mcp_tool("freecad_worker_part_create_primitive"))
        self.assertFalse(is_hidden_mcp_tool("freecad_geometry_check"))
        self.assertFalse(is_hidden_mcp_tool("freecad_worker_geometry_check"))
        self.assertFalse(is_hidden_mcp_tool("freecad_partdesign_pad"))
        self.assertFalse(is_hidden_mcp_tool("freecad_worker_partdesign_pad"))


class ResourceTests(unittest.TestCase):
    def test_descriptors_include_known_uris(self) -> None:
        uris = {descriptor["uri"] for descriptor in RESOURCE_DESCRIPTORS}

        self.assertIn("freecad://docs/roadmap-status", uris)
        self.assertIn("freecad://docs/workbench-bridge", uris)
        self.assertIn("freecad://docs/gui-1-1-1-research", uris)
        self.assertIn("freecad://docs/partdesign-attachment-policy", uris)
        self.assertIn("freecad://docs/freecad-wiki-research", uris)
        self.assertIn("freecad://docs/product-modules", uris)
        self.assertIn("freecad://docs/product-bundles", uris)
        self.assertIn("freecad://product/bundles", uris)
        self.assertIn("freecad://docs/distribution-profiles", uris)
        self.assertIn("freecad://distribution/profiles", uris)
        self.assertIn("freecad://docs/workbench-artifact", uris)
        self.assertIn("freecad://workbench/artifact", uris)
        self.assertIn("freecad://schemas/tools", uris)

    def test_read_known_resource_returns_content(self) -> None:
        contents = read_resource(ROOT, "freecad://docs/architecture")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "text/markdown")
        self.assertIn("Architecture", contents["text"])

    def test_read_product_bundle_manifest_resource(self) -> None:
        contents = read_resource(ROOT, "freecad://product/bundles")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "application/json")
        self.assertIn('"key": "pro"', contents["text"])

    def test_read_distribution_profile_manifest_resource(self) -> None:
        contents = read_resource(ROOT, "freecad://distribution/profiles")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "application/json")
        self.assertIn('"key": "studio"', contents["text"])

    def test_read_workbench_artifact_manifest_resource(self) -> None:
        contents = read_resource(ROOT, "freecad://workbench/artifact")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "application/json")
        self.assertIn('"artifact_key": "freecad-workbench-module"', contents["text"])

    def test_read_gui_research_resource(self) -> None:
        contents = read_resource(ROOT, "freecad://docs/gui-1-1-1-research")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "text/markdown")
        self.assertIn("GUI Priority Order", contents["text"])

    def test_read_partdesign_attachment_policy_resource(self) -> None:
        contents = read_resource(ROOT, "freecad://docs/partdesign-attachment-policy")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "text/markdown")
        self.assertIn("Planar generated face", contents["text"])
        self.assertIn("add_external", contents["text"])

    def test_read_freecad_wiki_research_resource(self) -> None:
        contents = read_resource(ROOT, "freecad://docs/freecad-wiki-research")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "text/markdown")
        self.assertIn("External Projection", contents["text"])
        self.assertIn("Topological_naming_problem", contents["text"])

    def test_read_unknown_resource_returns_none(self) -> None:
        self.assertIsNone(read_resource(ROOT, "freecad://docs/does-not-exist"))

    def test_resolve_repo_root_uses_explicit_path(self) -> None:
        self.assertEqual(resolve_repo_root(ROOT), ROOT)


class PromptTests(unittest.TestCase):
    def test_descriptors_list_both_prompts(self) -> None:
        names = {descriptor["name"] for descriptor in PROMPT_DESCRIPTORS}

        self.assertEqual(names, {"freecad_design_task", "freecad_phase_gate"})

    def test_render_design_task_includes_task(self) -> None:
        rendered = render_prompt("freecad_design_task", {"task": "make a cube"})

        text = rendered["messages"][0]["content"]["text"]
        self.assertIn("make a cube", text)
        self.assertIn("FaceN", text)
        self.assertIn("Hole or Pocket", text)
        self.assertIn("External Projection", text)
        self.assertIn("add_external", text)

    def test_render_phase_gate_includes_phase(self) -> None:
        rendered = render_prompt("freecad_phase_gate", {"phase": "smoke"})

        self.assertIn("Phase: smoke", rendered["messages"][0]["content"]["text"])

    def test_render_unknown_prompt_raises(self) -> None:
        with self.assertRaises(ToolInputError):
            render_prompt("nope", {})


class SdkServerWiringTests(unittest.TestCase):
    def test_create_mcp_server_builds_with_tool_surface(self) -> None:
        server, tool_service = create_mcp_server(ROOT)
        try:
            self.assertTrue(hasattr(server, "run"))
            self.assertIn("freecad_command_describe", tool_service.definition_map())
        finally:
            tool_service.shutdown()


class FakeToolService:
    def __init__(self) -> None:
        self.was_shutdown = False

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="demo",
                title="Demo",
                description="Demo tool",
                input_schema={"type": "object", "properties": {"value": {"type": "string"}}},
                handler=lambda args: {"echo": args["value"]},
            )
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def shutdown(self) -> None:
        self.was_shutdown = True


if __name__ == "__main__":
    unittest.main()
