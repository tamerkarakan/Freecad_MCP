"""Minimal stdio MCP server for FreeCAD hybrid tools."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from freecad_mcp import __version__
from freecad_mcp.cad_tools import CadToolService
from freecad_mcp.gui_tools import GuiToolService
from freecad_mcp.persistent_tools import PersistentToolService
from freecad_mcp.runtime_tools import RuntimeToolService
from freecad_mcp.static_tools import InventoryStore, StaticToolService
from freecad_mcp.tooling import ToolDefinition, ToolInputError


PROTOCOL_VERSION = "2025-06-18"

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class JsonRpcError(Exception):
    code: int
    message: str
    data: Any | None = None


class CompositeToolService:
    """Combine multiple services that expose ToolDefinition objects."""

    def __init__(self, *services: object):
        self.services = services

    def definitions(self) -> list[ToolDefinition]:
        definitions: list[ToolDefinition] = []
        for service in self.services:
            definitions.extend(service.definitions())
        return definitions

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def shutdown(self) -> None:
        for service in self.services:
            shutdown = getattr(service, "shutdown", None)
            if callable(shutdown):
                shutdown()


class McpServer:
    """JSON-RPC request dispatcher for the hybrid tool surface."""

    def __init__(self, tool_service: StaticToolService):
        self.tool_service = tool_service
        self.tools = tool_service.definition_map()

    def handle_message(self, message: JsonObject) -> JsonObject | None:
        request_id = message.get("id")
        method = message.get("method")
        if not method:
            raise JsonRpcError(-32600, "Invalid request: missing method")

        # JSON-RPC notifications do not receive responses.
        is_notification = "id" not in message
        if is_notification:
            self._handle_notification(method)
            return None

        try:
            result = self._handle_request(method, message.get("params") or {})
        except JsonRpcError as exc:
            return error_response(request_id, exc.code, exc.message, exc.data)
        except ToolInputError as exc:
            return error_response(request_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover - defensive protocol guard
            return error_response(request_id, -32603, "Internal error", {"detail": str(exc)})
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _handle_notification(self, method: str) -> None:
        if method in {"notifications/initialized", "notifications/cancelled"}:
            return
        # Unknown notifications are ignored to stay tolerant of client extras.

    def _handle_request(self, method: str, params: JsonObject) -> JsonObject:
        if method == "initialize":
            return self._initialize(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [tool.to_mcp() for tool in self.tools.values()]}
        if method == "tools/call":
            return self._tools_call(params)
        if method == "resources/list":
            return self._resources_list()
        if method == "resources/templates/list":
            return self._resource_templates_list()
        if method == "resources/read":
            return self._resources_read(params)
        if method == "prompts/list":
            return self._prompts_list()
        if method == "prompts/get":
            return self._prompts_get(params)
        raise JsonRpcError(-32601, f"Method not found: {method}")

    def _initialize(self, params: JsonObject) -> JsonObject:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "freecad-hybrid-mcp",
                "title": "FreeCAD Hybrid MCP",
                "version": __version__,
            },
            "instructions": (
                "Exposes static FreeCAD source intelligence, FreeCADCmd runtime tools, "
                "typed process-per-call CAD operations, persistent FreeCADCmd worker sessions, "
                "and opt-in FreeCAD GUI attach tools."
            ),
        }

    def _tools_call(self, params: JsonObject) -> JsonObject:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise JsonRpcError(-32602, "Tool name is required")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise JsonRpcError(-32602, "Tool arguments must be an object")
        tool = self.tools.get(name)
        if not tool:
            raise JsonRpcError(-32602, f"Unknown tool: {name}")

        try:
            structured = tool.handler(arguments)
        except ToolInputError as exc:
            return tool_result({"error": str(exc)}, is_error=True)
        return tool_result(structured, is_error=False)

    def _resources_list(self) -> JsonObject:
        return {
            "resources": [
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
        }

    def _resource_templates_list(self) -> JsonObject:
        return {"resourceTemplates": []}

    def _resources_read(self, params: JsonObject) -> JsonObject:
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            raise JsonRpcError(-32602, "Resource uri is required")
        contents = read_resource(Path.cwd(), uri)
        if contents is None:
            raise JsonRpcError(-32602, f"Unknown resource: {uri}")
        return {"contents": [contents]}

    def _prompts_list(self) -> JsonObject:
        return {
            "prompts": [
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
        }

    def _prompts_get(self, params: JsonObject) -> JsonObject:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            raise JsonRpcError(-32602, "Prompt name is required")
        if not isinstance(arguments, dict):
            raise JsonRpcError(-32602, "Prompt arguments must be an object")
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
        raise JsonRpcError(-32602, f"Unknown prompt: {name}")


def tool_result(payload: JsonObject, *, is_error: bool) -> JsonObject:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": is_error,
    }


def error_response(
    request_id: Any,
    code: int,
    message: str,
    data: Any | None = None,
) -> JsonObject:
    error: JsonObject = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def read_resource(repo_root: Path, uri: str) -> JsonObject | None:
    mapping = {
        "freecad://docs/architecture": repo_root / "docs" / "ARCHITECTURE.md",
        "freecad://docs/session-state": repo_root / "docs" / "SESSION_STATE.md",
        "freecad://docs/testing": repo_root / "docs" / "TESTING.md",
        "freecad://docs/sketcher-capabilities": repo_root / "docs" / "SKETCHER_CAPABILITIES.md",
        "freecad://docs/gui-attach-plan": repo_root / "docs" / "GUI_ATTACH_PLAN.md",
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


def serve_stdio(server: McpServer, stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    try:
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise JsonRpcError(-32600, "Invalid request")
                response = server.handle_message(message)
            except json.JSONDecodeError as exc:
                response = error_response(None, -32700, "Parse error", {"detail": str(exc)})
            except JsonRpcError as exc:
                response = error_response(None, exc.code, exc.message, exc.data)

            if response is not None:
                try:
                    encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
                except Exception as exc:  # pragma: no cover - defensive protocol guard
                    response_id = response.get("id") if isinstance(response, dict) else None
                    fallback = error_response(
                        response_id,
                        -32603,
                        "Internal error",
                        {"detail": f"failed to encode response: {exc}"},
                    )
                    encoded = json.dumps(fallback, ensure_ascii=False, separators=(",", ":"))

                try:
                    output_stream.write(encoded + "\n")
                    output_stream.flush()
                except Exception:  # pragma: no cover - transport already closed
                    return 0
        return 0
    finally:
        tool_service = getattr(server, "tool_service", None)
        shutdown = getattr(tool_service, "shutdown", None)
        if callable(shutdown):
            shutdown()


def build_server(repo_root: Path | None = None) -> McpServer:
    root = (repo_root or Path.cwd()).resolve()
    store = InventoryStore(root)
    tools = CompositeToolService(
        StaticToolService(store),
        RuntimeToolService(),
        PersistentToolService(workspace_root=root),
        CadToolService(),
        GuiToolService(),
    )
    return McpServer(tools)


def main() -> int:
    return serve_stdio(build_server(Path.cwd()))


if __name__ == "__main__":
    raise SystemExit(main())
