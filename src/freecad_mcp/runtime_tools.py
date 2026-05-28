"""Runtime FreeCAD MCP tools backed by FreeCADCmd."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from freecad_mcp.runtime_bridge import FreeCadCmdBridge, FreeCadDiscovery
from freecad_mcp.tooling import (
    JsonObject,
    ToolDefinition,
    ToolInputError,
    bounded_int,
    optional_string,
    required_string,
)


class RuntimeToolService:
    """Phase 2 runtime tools.

    This service currently uses process-per-call FreeCADCmd execution. Later
    phases can replace the bridge with a persistent GUI/workbench connection
    while preserving the same tool contracts.
    """

    def __init__(self, discovery: FreeCadDiscovery | None = None):
        self.discovery = discovery or FreeCadDiscovery()

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="freecad_session_status",
                title="FreeCAD Session Status",
                description="Discover FreeCADCmd and optionally probe the runtime version/config.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "executable": {"type": "string", "description": "Optional explicit FreeCADCmd path."},
                        "freecad_home": {"type": "string", "description": "Optional portable FreeCAD directory."},
                        "probe": {
                            "type": "boolean",
                            "description": "Run a small FreeCAD Python probe when an executable is found.",
                        },
                        "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 120},
                    },
                },
                handler=self.session_status,
            ),
            ToolDefinition(
                name="freecad_python_exec",
                title="Execute FreeCAD Python",
                description="Run a low-level Python snippet through FreeCADCmd and return stdout/stderr.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code passed to FreeCADCmd -c. Prefer typed tools when available.",
                            "maxLength": 20000,
                        },
                        "allow_unsafe": {
                            "type": "boolean",
                            "description": "Must be true unless FREECAD_MCP_ALLOW_UNSAFE_PYTHON=1 is set.",
                        },
                        "executable": {"type": "string", "description": "Optional explicit FreeCADCmd path."},
                        "freecad_home": {"type": "string", "description": "Optional portable FreeCAD directory."},
                        "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 120},
                        "compact_output": {
                            "type": "boolean",
                            "description": "Return compact execution metadata without stdout/stderr/argv text.",
                        },
                    },
                    "required": ["code"],
                },
                handler=self.python_exec,
            ),
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def session_status(self, args: JsonObject) -> JsonObject:
        executable_arg = optional_string(args, "executable")
        freecad_home = optional_string(args, "freecad_home")
        probe = args.get("probe", True)
        if not isinstance(probe, bool):
            raise ToolInputError("probe must be a boolean")
        timeout_sec = bounded_int(args, "timeout_sec", default=30, minimum=1, maximum=120)

        discovery = self.discovery.discover(executable=executable_arg, freecad_home=freecad_home)
        payload: JsonObject = {"discovery": discovery.to_dict(), "mode": "freecadcmd-process-per-call"}
        if discovery.executable and probe:
            payload["probe"] = FreeCadCmdBridge(discovery.executable).probe(timeout_sec=timeout_sec)
        return payload

    def python_exec(self, args: JsonObject) -> JsonObject:
        code = required_string(args, "code")
        if len(code) > 20_000:
            raise ToolInputError("code exceeds 20000 characters")
        allow_unsafe = args.get("allow_unsafe", False)
        env_allowed = os.environ.get("FREECAD_MCP_ALLOW_UNSAFE_PYTHON") == "1"
        if not env_allowed and allow_unsafe is not True:
            raise ToolInputError(
                "freecad_python_exec is unsafe. Pass allow_unsafe=true or set "
                "FREECAD_MCP_ALLOW_UNSAFE_PYTHON=1. Prefer typed CAD tools."
            )
        executable_arg = optional_string(args, "executable")
        freecad_home = optional_string(args, "freecad_home")
        timeout_sec = bounded_int(args, "timeout_sec", default=30, minimum=1, maximum=120)
        compact_output = args.get("compact_output", False)
        if not isinstance(compact_output, bool):
            raise ToolInputError("compact_output must be a boolean")

        discovery = self.discovery.discover(executable=executable_arg, freecad_home=freecad_home)
        if discovery.executable is None:
            raise ToolInputError(
                "FreeCADCmd not found. Set FREECAD_MCP_FREECAD_HOME, FREECAD_MCP_FREECAD_CMD, "
                "or pass freecad_home/executable."
            )

        result = FreeCadCmdBridge(Path(discovery.executable)).execute_python(
            code,
            timeout_sec=timeout_sec,
        )
        return {
            "discovery": discovery.to_dict(),
            "execution": result.to_compact_dict() if compact_output else result.to_dict(),
            "audit": {
                "tool": "freecad_python_exec",
                "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                "unsafe_opt_in": True,
                "compact_output": compact_output,
            },
        }
