"""Minimal stdio MCP server for FreeCAD hybrid tools."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from freecad_mcp import __version__
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
        raise JsonRpcError(-32601, f"Method not found: {method}")

    def _initialize(self, params: JsonObject) -> JsonObject:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "freecad-hybrid-mcp",
                "title": "FreeCAD Hybrid MCP",
                "version": __version__,
            },
            "instructions": (
                "Exposes static FreeCAD source intelligence plus Phase 2 FreeCADCmd runtime tools. "
                "Document and CAD mutation typed tools are intentionally unavailable yet."
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


def serve_stdio(server: McpServer, stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
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
            output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            output_stream.flush()
    return 0


def build_server(repo_root: Path | None = None) -> McpServer:
    root = (repo_root or Path.cwd()).resolve()
    store = InventoryStore(root)
    tools = CompositeToolService(StaticToolService(store), RuntimeToolService())
    return McpServer(tools)


def main() -> int:
    return serve_stdio(build_server(Path.cwd()))


if __name__ == "__main__":
    raise SystemExit(main())
