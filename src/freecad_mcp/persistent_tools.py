"""MCP tools for persistent FreeCADCmd worker sessions."""

from __future__ import annotations

from pathlib import Path

from freecad_mcp.persistent_bridge import PersistentBridgeManager
from freecad_mcp.runtime_bridge import FreeCadDiscovery
from freecad_mcp.tooling import JsonObject, ToolDefinition, ToolInputError, bounded_int, optional_string, required_string


RUNTIME_PROPS: JsonObject = {
    "executable": {"type": "string", "description": "Optional explicit FreeCADCmd path."},
    "freecad_home": {"type": "string", "description": "Optional portable FreeCAD directory."},
    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 180},
}

SESSION_PROPS: JsonObject = {
    "session_id": {"type": "string", "description": "Persistent FreeCAD worker session id."},
    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 180},
}

SAVE_PROPS: JsonObject = {
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
    "allow_external_paths": {
        "type": "boolean",
        "description": "Allow writes outside FREECAD_MCP_WORKSPACE_ROOT/server workspace.",
    },
}


class PersistentToolService:
    """Stateful FreeCADCmd worker tools.

    The existing typed CAD tools remain process-per-call. These tools add a
    session/document id layer for workflows that benefit from in-memory state.
    """

    def __init__(
        self,
        discovery: FreeCadDiscovery | None = None,
        manager: PersistentBridgeManager | None = None,
        workspace_root: Path | None = None,
    ):
        self.manager = manager or PersistentBridgeManager(discovery=discovery, workspace_root=workspace_root)

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="freecad_session_start",
                title="Start Persistent FreeCAD Session",
                description="Alias for starting a long-lived FreeCADCmd worker session.",
                input_schema={"type": "object", "properties": dict(RUNTIME_PROPS)},
                handler=self.session_start,
            ),
            ToolDefinition(
                name="freecad_session_list",
                title="List Persistent FreeCAD Sessions",
                description="Alias for listing persistent FreeCADCmd worker sessions.",
                input_schema={"type": "object", "properties": {}},
                handler=self.session_list,
            ),
            ToolDefinition(
                name="freecad_session_close",
                title="Close Persistent FreeCAD Session",
                description="Alias for closing a persistent FreeCADCmd worker session.",
                input_schema={"type": "object", "properties": dict(SESSION_PROPS), "required": ["session_id"]},
                handler=self.session_close,
            ),
            ToolDefinition(
                name="freecad_worker_session_start",
                title="Start FreeCAD Worker Session",
                description="Start a long-lived FreeCADCmd worker process and return a session id.",
                input_schema={"type": "object", "properties": dict(RUNTIME_PROPS)},
                handler=self.session_start,
            ),
            ToolDefinition(
                name="freecad_worker_session_list",
                title="List FreeCAD Worker Sessions",
                description="List running persistent FreeCADCmd worker sessions.",
                input_schema={"type": "object", "properties": {}},
                handler=self.session_list,
            ),
            ToolDefinition(
                name="freecad_worker_session_status",
                title="FreeCAD Worker Session Status",
                description="Return worker process state and in-memory document summaries.",
                input_schema={"type": "object", "properties": dict(SESSION_PROPS), "required": ["session_id"]},
                handler=self.session_status,
            ),
            ToolDefinition(
                name="freecad_worker_session_close",
                title="Close FreeCAD Worker Session",
                description="Close a persistent FreeCADCmd worker session and clean up the process.",
                input_schema={"type": "object", "properties": dict(SESSION_PROPS), "required": ["session_id"]},
                handler=self.session_close,
            ),
            self._worker_tool(
                "freecad_worker_document_new",
                "Worker Create Document",
                "Create a document inside a persistent worker session.",
                {"document_name": {"type": "string"}, "label": {"type": "string"}, **SAVE_PROPS},
                [],
                "document_new",
            ),
            self._worker_tool(
                "freecad_worker_document_open",
                "Worker Open Document",
                "Open a FreeCAD document inside a persistent worker session.",
                {"document_path": {"type": "string"}},
                ["document_path"],
                "document_open",
            ),
            self._worker_tool(
                "freecad_worker_document_save",
                "Worker Save Document",
                "Save a worker document by document id.",
                {"document_id": {"type": "string"}, **SAVE_PROPS},
                ["document_id"],
                "document_save",
            ),
            self._worker_tool(
                "freecad_worker_document_recompute",
                "Worker Recompute Document",
                "Recompute a worker document by document id.",
                {"document_id": {"type": "string"}, **SAVE_PROPS},
                ["document_id"],
                "document_recompute",
            ),
            self._worker_tool(
                "freecad_worker_document_close",
                "Worker Close Document",
                "Close an in-memory worker document by document id.",
                {"document_id": {"type": "string"}},
                ["document_id"],
                "document_close",
            ),
            self._worker_tool(
                "freecad_worker_document_export",
                "Worker Export Document",
                "Export selected/all objects from an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "output_path": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    "overwrite": {"type": "boolean"},
                    "allow_external_paths": SAVE_PROPS["allow_external_paths"],
                },
                ["document_id", "output_path"],
                "document_export",
            ),
            self._worker_tool(
                "freecad_worker_part_create_primitive",
                "Worker Create Part Primitive",
                "Create a Part primitive in an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "primitive": {"type": "string", "enum": ["box", "cylinder", "sphere", "cone", "torus"]},
                    "object_name": {"type": "string"},
                    "properties": {"type": "object"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "part_create_primitive",
            ),
            self._worker_tool(
                "freecad_worker_part_boolean",
                "Worker Part Boolean",
                "Fuse/cut/common Part shapes inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    "operation": {"type": "string", "enum": ["fuse", "cut", "common"]},
                    "result_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "object_names"],
                "part_boolean",
            ),
            self._worker_tool(
                "freecad_worker_part_extrude",
                "Worker Part Extrude",
                "Extrude a source shape inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "source_object": {"type": "string"},
                    "vector": {"type": "array", "items": {"type": "number"}},
                    "result_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "source_object"],
                "part_extrude",
            ),
            self._worker_tool(
                "freecad_worker_part_revolve",
                "Worker Part Revolve",
                "Revolve a source shape inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "source_object": {"type": "string"},
                    "base": {"type": "array", "items": {"type": "number"}},
                    "axis": {"type": "array", "items": {"type": "number"}},
                    "angle": {"type": "number"},
                    "result_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "source_object"],
                "part_revolve",
            ),
            self._worker_tool(
                "freecad_worker_part_check_geometry",
                "Worker Check Part Geometry",
                "Run shape validity checks inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    "run_bop_check": {"type": "boolean"},
                },
                ["document_id"],
                "part_check_geometry",
            ),
            self._worker_tool(
                "freecad_worker_object_list",
                "Worker List Objects",
                "List objects from an in-memory worker document.",
                {"document_id": {"type": "string"}},
                ["document_id"],
                "object_list",
            ),
            self._worker_tool(
                "freecad_worker_object_get",
                "Worker Get Object",
                "Inspect an object from an in-memory worker document.",
                {"document_id": {"type": "string"}, "object_name": {"type": "string"}},
                ["document_id", "object_name"],
                "object_get",
            ),
            self._worker_tool(
                "freecad_worker_object_set_properties",
                "Worker Set Object Properties",
                "Set simple object properties inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_name": {"type": "string"},
                    "properties": {"type": "object"},
                    **SAVE_PROPS,
                },
                ["document_id", "object_name", "properties"],
                "object_set_properties",
            ),
            self._worker_tool(
                "freecad_worker_object_delete",
                "Worker Delete Objects",
                "Delete object(s) inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_name": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "object_delete",
            ),
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def shutdown(self) -> None:
        self.manager.shutdown_all()

    def session_start(self, args: JsonObject) -> JsonObject:
        executable_arg = optional_string(args, "executable")
        freecad_home = optional_string(args, "freecad_home")
        timeout_sec = bounded_int(args, "timeout_sec", default=30, minimum=1, maximum=180)
        return self.manager.start_session(
            executable=executable_arg,
            freecad_home=freecad_home,
            timeout_sec=timeout_sec,
        )

    def session_list(self, args: JsonObject) -> JsonObject:
        return self.manager.list_sessions()

    def session_status(self, args: JsonObject) -> JsonObject:
        session_id = required_string(args, "session_id")
        timeout_sec = bounded_int(args, "timeout_sec", default=30, minimum=1, maximum=180)
        return self.manager.status(session_id, timeout_sec=timeout_sec)

    def session_close(self, args: JsonObject) -> JsonObject:
        session_id = required_string(args, "session_id")
        timeout_sec = bounded_int(args, "timeout_sec", default=5, minimum=1, maximum=180)
        return self.manager.close(session_id, timeout_sec=timeout_sec)

    def _worker_tool(
        self,
        name: str,
        title: str,
        description: str,
        properties: JsonObject,
        required: list[str],
        method: str,
    ) -> ToolDefinition:
        schema = {"type": "object", "properties": {**SESSION_PROPS, **properties}}
        schema["required"] = ["session_id", *required]
        return ToolDefinition(name, title, description, schema, lambda args, method=method, required=required: self._request(method, args, required))

    def _request(self, method: str, args: JsonObject, required: list[str]) -> JsonObject:
        session_id = required_string(args, "session_id")
        for key in required:
            if key not in args or args[key] in (None, ""):
                raise ToolInputError(f"{key} is required")
        timeout_sec = bounded_int(args, "timeout_sec", default=30, minimum=1, maximum=180)
        params = {key: value for key, value in args.items() if key not in {"session_id", "timeout_sec"}}
        return self.manager.request(session_id, method, params, timeout_sec=timeout_sec)
