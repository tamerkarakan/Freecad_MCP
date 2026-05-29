"""Shared host-side plumbing for typed FreeCADCmd CAD tools."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from freecad_mcp.runtime_bridge import FreeCadCmdBridge, FreeCadDiscovery, parse_prefixed_json
from freecad_mcp.tooling import (
    JsonObject,
    ToolDefinition,
    ToolInputError,
    bounded_int,
    load_runtime_script,
    optional_string,
)


COMMON_RUNTIME_PROPS: JsonObject = {
    "executable": {"type": "string", "description": "Optional explicit FreeCADCmd path."},
    "freecad_home": {"type": "string", "description": "Optional portable FreeCAD directory."},
    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 180},
    "compact_execution": {
        "type": "boolean",
        "description": "Return compact execution metadata without stdout/stderr/argv text.",
    },
    "allow_external_paths": {
        "type": "boolean",
        "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace.",
    },
}


CAD_ACTION_SCRIPT = load_runtime_script("cad_action.py")


@dataclass(frozen=True)
class CadToolSpec:
    """Declarative metadata for one typed FreeCADCmd action."""

    name: str
    title: str
    description: str
    properties: JsonObject
    required: Sequence[str]
    action: str


class CadCommandRunner:
    """Runs typed CAD actions in a process-per-call FreeCADCmd bridge."""

    def __init__(self, discovery: FreeCadDiscovery | None = None):
        self.discovery = discovery or FreeCadDiscovery()

    def run(self, action: str, args: JsonObject, required: Sequence[str]) -> JsonObject:
        for key in required:
            if key not in args or args[key] in (None, ""):
                raise ToolInputError(f"{key} is required")
        executable_arg = optional_string(args, "executable")
        freecad_home = optional_string(args, "freecad_home")
        timeout_sec = bounded_int(args, "timeout_sec", default=60, minimum=1, maximum=180)
        compact_execution = args.get("compact_execution", False)
        if not isinstance(compact_execution, bool):
            raise ToolInputError("compact_execution must be a boolean")
        discovery = self.discovery.discover(executable=executable_arg, freecad_home=freecad_home)
        if discovery.executable is None:
            raise ToolInputError(
                "FreeCADCmd not found. Set FREECAD_MCP_FREECAD_HOME, FREECAD_MCP_FREECAD_CMD, "
                "or pass freecad_home/executable."
            )

        action_args = {
            key: value
            for key, value in args.items()
            if key not in {"executable", "freecad_home", "timeout_sec", "compact_execution"}
        }
        action_args["_workspace_root"] = os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or str(Path.cwd())
        action_args["action"] = action
        if action == "object_delete" and not action_args.get("object_name") and not action_args.get("object_names"):
            raise ToolInputError("object_name or object_names is required")
        encoded_args = base64.b64encode(json.dumps(action_args).encode("utf-8")).decode("ascii")
        code = CAD_ACTION_SCRIPT.replace("__ARGS_B64__", encoded_args)
        result = FreeCadCmdBridge(Path(discovery.executable)).execute_python(code, timeout_sec=timeout_sec)
        payload = parse_prefixed_json(result.stdout)
        if result.ok and payload is None:
            raise ToolInputError("FreeCAD response did not include a valid MCP JSON payload")
        return {
            "discovery": discovery.to_dict(),
            "execution": result.to_compact_dict() if compact_execution else result.to_dict(),
            "freecad": payload,
        }


class CadDomainToolService:
    """Base class for cohesive CAD domain tool groups."""

    domain = "cad"

    def __init__(self, runner: CadCommandRunner):
        self.runner = runner

    def specs(self) -> list[CadToolSpec]:
        raise NotImplementedError

    def definitions(self) -> list[ToolDefinition]:
        return [self._tool(spec) for spec in self.specs()]

    def _tool(self, spec: CadToolSpec) -> ToolDefinition:
        schema = {"type": "object", "properties": {**spec.properties, **COMMON_RUNTIME_PROPS}}
        if spec.required:
            schema["required"] = list(spec.required)
        return ToolDefinition(
            spec.name,
            spec.title,
            spec.description,
            schema,
            lambda args, spec=spec: self.runner.run(spec.action, args, spec.required),
        )
