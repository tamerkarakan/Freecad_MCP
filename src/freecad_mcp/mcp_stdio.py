"""Stdio MCP server for FreeCAD hybrid tools, backed by the official MCP SDK.

The protocol/transport (initialize handshake, capability negotiation, JSON-RPC
framing, notifications) is owned by the `mcp` SDK. This module keeps the FreeCAD
tool surface (CompositeToolService) plus the resource/prompt content as plain,
synchronous, unit-testable helpers, and wires thin async SDK handlers on top.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server

from freecad_mcp import __version__
from freecad_mcp.cad_tools import CadToolService
from freecad_mcp.gui_tools import GuiToolService
from freecad_mcp.persistent_tools import PersistentToolService
from freecad_mcp.runtime_tools import RuntimeToolService
from freecad_mcp.logging_config import configure_logging, log_event, log_tool_call
from freecad_mcp.static_tools import InventoryStore, StaticToolService
from freecad_mcp.tooling import ToolInputError

JsonObject = dict[str, Any]

SERVER_NAME = "freecad-hybrid-mcp"
INSTRUCTIONS = (
    "Exposes static FreeCAD source intelligence, FreeCADCmd runtime tools, "
    "typed process-per-call CAD operations, persistent FreeCADCmd worker sessions, "
    "and opt-in FreeCAD GUI attach tools."
)

RESOURCE_DESCRIPTORS: list[JsonObject] = [
    {
        "uri": "freecad://docs/architecture",
        "name": "architecture",
        "title": "Architecture",
        "description": "Current architecture and bridge policy.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/session-state",
        "name": "session_state",
        "title": "Session State",
        "description": "Cross-session handoff state.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/roadmap-status",
        "name": "roadmap_status",
        "title": "Roadmap Status",
        "description": "Completed, blocked, and future roadmap scope.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/testing",
        "name": "testing",
        "title": "Testing",
        "description": "Verification gates and smoke tests.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/sketcher-capabilities",
        "name": "sketcher_capabilities",
        "title": "Sketcher Capabilities",
        "description": "Headless Sketcher typed-tool coverage and GUI-only boundaries.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/gui-attach-plan",
        "name": "gui_attach_plan",
        "title": "GUI Attach Plan",
        "description": "GUI bridge contract for active document, active view, selection, and subelement reads.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/vision-debug-pipeline",
        "name": "vision_debug_pipeline",
        "title": "Vision Debug Pipeline",
        "description": "Screenshot and vision-model policy for FreeCAD GUI debugging and image-to-sketch ambiguity.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/workbench-bridge",
        "name": "workbench_bridge",
        "title": "Workbench Bridge",
        "description": "FreeCAD Workbench-hosted GUI bridge setup and autostart options.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://docs/techdraw-cam-fem-plan",
        "name": "techdraw_cam_fem_plan",
        "title": "TechDraw CAM FEM Plan",
        "description": "Source-backed typed-wrapper plan for TechDraw, CAM, and FEM.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "freecad://schemas/tools",
        "name": "tool_schemas",
        "title": "MCP Tool Schemas",
        "description": "Generated tool schema snapshot.",
        "mimeType": "application/json",
    },
    {
        "uri": "freecad://inventory/summary",
        "name": "inventory_summary",
        "title": "FreeCAD Inventory Summary",
        "description": "Compact generated inventory summary.",
        "mimeType": "application/json",
    },
]

PROMPT_DESCRIPTORS: list[JsonObject] = [
    {
        "name": "freecad_design_task",
        "title": "FreeCAD Design Task",
        "description": "Plan and execute a FreeCAD design task using typed tools first.",
        "arguments": [
            {"name": "task", "description": "The design or automation task.", "required": True}
        ],
    },
    {
        "name": "freecad_phase_gate",
        "title": "FreeCAD Phase Gate",
        "description": "Review a phase for tests, docs, risks, and runtime evidence.",
        "arguments": [
            {"name": "phase", "description": "Phase name or number.", "required": True}
        ],
    },
]


class CompositeToolService:
    """Combine multiple services that expose ToolDefinition objects."""

    def __init__(self, *services: object):
        self.services = services

    def definitions(self) -> list:
        definitions: list = []
        for service in self.services:
            definitions.extend(service.definitions())
        return definitions

    def definition_map(self) -> dict:
        return {definition.name: definition for definition in self.definitions()}

    def shutdown(self) -> None:
        for service in self.services:
            shutdown = getattr(service, "shutdown", None)
            if callable(shutdown):
                shutdown()


def build_server(repo_root: Path | None = None) -> CompositeToolService:
    """Build the composite FreeCAD tool surface."""
    root = (repo_root or Path.cwd()).resolve()
    return CompositeToolService(
        StaticToolService(InventoryStore(root)),
        RuntimeToolService(),
        PersistentToolService(workspace_root=root),
        CadToolService(),
        GuiToolService(),
    )


def render_prompt(name: str, arguments: JsonObject) -> JsonObject:
    """Render a workflow prompt into MCP message content. Pure and testable."""
    if name == "freecad_design_task":
        task = arguments.get("task", "")
        return {
            "description": "FreeCAD design task workflow",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Use FreeCAD typed MCP tools before low-level Python. "
                            "Inspect available source/tool schemas if needed, create or open the document, "
                            "apply operations with save/output paths, run geometry checks, and report exact files. "
                            f"Task: {task}"
                        ),
                    },
                }
            ],
        }
    if name == "freecad_phase_gate":
        phase = arguments.get("phase", "")
        return {
            "description": "FreeCAD MCP phase gate",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Review the phase for: tool schema drift, path safety, FreeCAD runtime smoke, "
                            "unit tests, docs/session handoff, known risks, and git cleanliness. "
                            f"Phase: {phase}"
                        ),
                    },
                }
            ],
        }
    raise ToolInputError(f"Unknown prompt: {name}")


def read_resource(repo_root: Path, uri: str) -> JsonObject | None:
    """Resolve a freecad:// resource URI to its content payload, or None."""
    mapping = {
        "freecad://docs/architecture": repo_root / "docs" / "ARCHITECTURE.md",
        "freecad://docs/session-state": repo_root / "docs" / "SESSION_STATE.md",
        "freecad://docs/roadmap-status": repo_root / "docs" / "ROADMAP_STATUS.md",
        "freecad://docs/testing": repo_root / "docs" / "TESTING.md",
        "freecad://docs/sketcher-capabilities": repo_root / "docs" / "SKETCHER_CAPABILITIES.md",
        "freecad://docs/gui-attach-plan": repo_root / "docs" / "GUI_ATTACH_PLAN.md",
        "freecad://docs/vision-debug-pipeline": repo_root / "docs" / "VISION_DEBUG_PIPELINE.md",
        "freecad://docs/workbench-bridge": repo_root / "docs" / "WORKBENCH_BRIDGE.md",
        "freecad://docs/techdraw-cam-fem-plan": repo_root / "docs" / "TECHDRAW_CAM_FEM_PLAN.md",
        "freecad://schemas/tools": repo_root / "docs" / "mcp_tool_schemas.json",
    }
    if uri in mapping:
        path = mapping[uri]
        if not path.exists():
            return None
        mime = "application/json" if path.suffix == ".json" else "text/markdown"
        return {"uri": uri, "mimeType": mime, "text": path.read_text(encoding="utf-8")}
    if uri == "freecad://inventory/summary":
        inventory_path = repo_root / "docs" / "freecad_tool_inventory.json"
        if not inventory_path.exists():
            return None
        import json

        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        commands = inventory.get("commands", [])
        modules: dict[str, int] = {}
        for command in commands:
            module = str(command.get("module", "unknown"))
            modules[module] = modules.get(module, 0) + 1
        summary = {
            "scan": inventory.get("scan", {}),
            "command_count": len(commands),
            "module_counts": dict(sorted(modules.items())),
            "workbench_count": len(inventory.get("workbenches", [])),
        }
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(summary, indent=2)}
    return None


def create_mcp_server(repo_root: Path | None = None) -> tuple[Server, CompositeToolService]:
    """Build the SDK Server with handlers delegating to the FreeCAD tool surface."""
    root = (repo_root or Path.cwd()).resolve()
    tool_service = build_server(root)
    tools = tool_service.definition_map()
    server: Server = Server(name=SERVER_NAME, version=__version__, instructions=INSTRUCTIONS)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=definition.name,
                title=definition.title,
                description=definition.description,
                inputSchema=definition.input_schema,
            )
            for definition in tool_service.definitions()
        ]

    # validate_input=False keeps argument validation inside each tool handler, as
    # before the SDK migration, so tool behavior is unchanged.
    @server.call_tool(validate_input=False)
    async def _call_tool(name: str, arguments: JsonObject):
        tool = tools.get(name)
        if tool is None:
            raise ToolInputError(f"Unknown tool: {name}")
        # A returned dict becomes structuredContent + JSON-text content; a raised
        # exception becomes an isError result. Both match MCP semantics. The
        # log_tool_call context times the call and records the outcome without
        # logging any argument values.
        with log_tool_call(name, arguments):
            return tool.handler(arguments or {})

    @server.list_resources()
    async def _list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                uri=descriptor["uri"],
                name=descriptor["name"],
                title=descriptor["title"],
                description=descriptor["description"],
                mimeType=descriptor["mimeType"],
            )
            for descriptor in RESOURCE_DESCRIPTORS
        ]

    @server.list_resource_templates()
    async def _list_resource_templates() -> list:
        return []

    @server.read_resource()
    async def _read_resource(uri) -> list[ReadResourceContents]:
        contents = read_resource(root, str(uri))
        if contents is None:
            raise ToolInputError(f"Unknown resource: {uri}")
        return [ReadResourceContents(content=contents["text"], mime_type=contents["mimeType"])]

    @server.list_prompts()
    async def _list_prompts() -> list[types.Prompt]:
        return [
            types.Prompt(
                name=descriptor["name"],
                title=descriptor["title"],
                description=descriptor["description"],
                arguments=[
                    types.PromptArgument(
                        name=argument["name"],
                        description=argument["description"],
                        required=argument.get("required", False),
                    )
                    for argument in descriptor["arguments"]
                ],
            )
            for descriptor in PROMPT_DESCRIPTORS
        ]

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: JsonObject | None) -> types.GetPromptResult:
        rendered = render_prompt(name, arguments or {})
        return types.GetPromptResult(
            description=rendered["description"],
            messages=[
                types.PromptMessage(
                    role=message["role"],
                    content=types.TextContent(type="text", text=message["content"]["text"]),
                )
                for message in rendered["messages"]
            ],
        )

    return server, tool_service


async def serve(repo_root: Path | None = None) -> None:
    configure_logging()
    server, tool_service = create_mcp_server(repo_root)
    init_options = server.create_initialization_options()
    log_event(logging.INFO, "server_start", tools=len(tool_service.definition_map()))
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, init_options)
    finally:
        log_event(logging.INFO, "server_stop")
        tool_service.shutdown()


def main() -> int:
    anyio.run(serve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
