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
)
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
            "freecad_partdesign_pad",
        ):
            self.assertIn(name, tools)


class ResourceTests(unittest.TestCase):
    def test_descriptors_include_known_uris(self) -> None:
        uris = {descriptor["uri"] for descriptor in RESOURCE_DESCRIPTORS}

        self.assertIn("freecad://docs/roadmap-status", uris)
        self.assertIn("freecad://docs/workbench-bridge", uris)
        self.assertIn("freecad://schemas/tools", uris)

    def test_read_known_resource_returns_content(self) -> None:
        contents = read_resource(ROOT, "freecad://docs/architecture")

        self.assertIsNotNone(contents)
        self.assertEqual(contents["mimeType"], "text/markdown")
        self.assertIn("Architecture", contents["text"])

    def test_read_unknown_resource_returns_none(self) -> None:
        self.assertIsNone(read_resource(ROOT, "freecad://docs/does-not-exist"))


class PromptTests(unittest.TestCase):
    def test_descriptors_list_both_prompts(self) -> None:
        names = {descriptor["name"] for descriptor in PROMPT_DESCRIPTORS}

        self.assertEqual(names, {"freecad_design_task", "freecad_phase_gate"})

    def test_render_design_task_includes_task(self) -> None:
        rendered = render_prompt("freecad_design_task", {"task": "make a cube"})

        self.assertIn("make a cube", rendered["messages"][0]["content"]["text"])

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
