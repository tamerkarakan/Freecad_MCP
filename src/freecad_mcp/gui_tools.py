"""MCP tools for an opt-in FreeCAD GUI attach bridge."""

from __future__ import annotations

from freecad_mcp.gui_bridge import DEFAULT_GUI_BRIDGE_URL, GuiBridgeManager
from freecad_mcp.tooling import JsonObject, ToolDefinition, ToolInputError, bounded_int, optional_string, required_string


SESSION_PROPS: JsonObject = {
    "session_id": {"type": "string", "description": "Attached FreeCAD GUI bridge session id."},
    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 60},
}


class GuiToolService:
    """Tools that talk to a FreeCAD GUI loopback bridge.

    These tools do not start FreeCAD GUI themselves. The user or a future
    Workbench-hosted bridge starts `scripts/freecad_gui_bridge_server.py` inside
    FreeCAD GUI, then `freecad_gui_attach` connects to it.
    """

    def __init__(self, manager: GuiBridgeManager | None = None):
        self.manager = manager or GuiBridgeManager()

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="freecad_gui_attach",
                title="Attach FreeCAD GUI Bridge",
                description="Attach to an already-running FreeCAD GUI loopback bridge.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "default": DEFAULT_GUI_BRIDGE_URL},
                        "token": {"type": "string"},
                        "probe": {"type": "boolean", "description": "Probe bridge status before storing the session."},
                        "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 60},
                    },
                },
                handler=self.attach,
            ),
            ToolDefinition(
                name="freecad_gui_list",
                title="List FreeCAD GUI Attach Sessions",
                description="List GUI bridge sessions held by this MCP server process.",
                input_schema={"type": "object", "properties": {}},
                handler=lambda args: self.manager.list_sessions(),
            ),
            ToolDefinition(
                name="freecad_gui_detach",
                title="Detach FreeCAD GUI Bridge",
                description="Forget a GUI bridge session without closing FreeCAD GUI.",
                input_schema={"type": "object", "properties": dict(SESSION_PROPS), "required": ["session_id"]},
                handler=self.detach,
            ),
            self._gui_tool("freecad_gui_status", "GUI Bridge Status", "Report GUI bridge health, active document, and active view.", {}, [], "status"),
            self._gui_tool("freecad_gui_active_document_get", "Get Active GUI Document", "Return the active GUI document summary.", {}, [], "active_document_get"),
            self._gui_tool("freecad_gui_active_view_get", "Get Active GUI View", "Return active view metadata and camera text when available.", {}, [], "active_view_get"),
            self._gui_tool(
                "freecad_gui_selection_get",
                "Get GUI Selection",
                "Return normalized GUI selection records with object and subelement references.",
                {
                    "document_name": {"type": "string", "description": "Document name, omitted for active document or '*' for all documents."},
                    "resolve": {"type": "integer", "minimum": 0, "maximum": 2},
                },
                [],
                "selection_get",
            ),
            self._gui_tool(
                "freecad_gui_preselection_get",
                "Get GUI Preselection",
                "Return current hover/preselection record when available.",
                {},
                [],
                "preselection_get",
            ),
            self._gui_tool(
                "freecad_gui_selection_set",
                "Set GUI Selection",
                "Set GUI selection from normalized document/object/subelement references.",
                {
                    "records": {"type": "array", "items": {"type": "object"}},
                    "clear": {"type": "boolean"},
                },
                ["records"],
                "selection_set",
            ),
            self._gui_tool(
                "freecad_gui_view_fit",
                "Fit GUI View",
                "Fit all or selected objects in the active GUI view.",
                {"selection_only": {"type": "boolean"}},
                [],
                "view_fit",
            ),
            self._gui_tool(
                "freecad_gui_primitive_create",
                "Create GUI Primitive",
                "Create a typed primitive in the active FreeCAD GUI document.",
                {
                    "primitive": {"type": "string", "enum": ["cylinder"], "default": "cylinder"},
                    "document_name": {"type": "string"},
                    "object_name": {"type": "string"},
                    "label": {"type": "string"},
                    "radius": {"type": "number"},
                    "height": {"type": "number"},
                    "placement": {"type": "object"},
                    "select": {"type": "boolean"},
                    "fit_view": {"type": "boolean"},
                },
                [],
                "primitive_create",
            ),
            self._gui_tool(
                "freecad_gui_sketch_state",
                "Get GUI Sketch State",
                "Inspect active or selected Sketcher state from the live FreeCAD GUI without mutating geometry.",
                {
                    "document_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "include_geometry": {"type": "boolean"},
                    "include_constraints": {"type": "boolean"},
                    "refresh_diagnostics": {"type": "boolean", "description": "Optionally run solver/missing-constraint diagnostics before reading state."},
                    "precision": {"type": "number"},
                    "angle_precision": {"type": "number"},
                    "include_construction": {"type": "boolean"},
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                [],
                "sketch_state",
            ),
            self._gui_tool(
                "freecad_gui_sketch_enter",
                "Enter GUI Sketch Edit",
                "Enter Sketcher edit mode for an explicit, selected, active, or uniquely inferable sketch in the live FreeCAD GUI.",
                {
                    "document_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "reset_existing": {"type": "boolean", "description": "Reset any existing edit object before entering the requested sketch."},
                    "edit_mode": {"type": "integer", "minimum": 0, "maximum": 20},
                    "activate_workbench": {"type": "boolean"},
                    "select": {"type": "boolean"},
                    "fit_view": {"type": "boolean"},
                    "include_geometry": {"type": "boolean"},
                    "include_constraints": {"type": "boolean"},
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                [],
                "sketch_enter",
            ),
            self._gui_tool(
                "freecad_gui_sketch_leave",
                "Leave GUI Sketch Edit",
                "Leave the current Sketcher edit mode, optionally recompute, select the sketch, and return fresh GUI sketch state.",
                {
                    "document_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "recompute": {"type": "boolean"},
                    "select": {"type": "boolean"},
                    "fit_view": {"type": "boolean"},
                    "include_geometry": {"type": "boolean"},
                    "include_constraints": {"type": "boolean"},
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                [],
                "sketch_leave",
            ),
            self._gui_tool(
                "freecad_gui_partdesign_state",
                "Get GUI PartDesign State",
                "Inspect PartDesign Body, Tip, feature chain, edit object, and selection state from the live FreeCAD GUI.",
                {
                    "document_name": {"type": "string"},
                    "body_name": {"type": "string"},
                    "include_features": {"type": "boolean"},
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                [],
                "partdesign_state",
            ),
            self._gui_tool(
                "freecad_gui_body_activate",
                "Activate GUI PartDesign Body",
                "Activate an explicit, selected, active, or uniquely inferable PartDesign Body in the live FreeCAD GUI.",
                {
                    "document_name": {"type": "string"},
                    "body_name": {"type": "string"},
                    "activate_workbench": {"type": "boolean"},
                    "set_active_view_object": {"type": "boolean"},
                    "select": {"type": "boolean"},
                    "fit_view": {"type": "boolean"},
                    "include_features": {"type": "boolean"},
                    "max_items": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                [],
                "body_activate",
            ),
            self._gui_tool(
                "freecad_gui_feature_task_state",
                "Get GUI Feature Task State",
                "Inspect the active FreeCAD GUI task/dialog state around Sketcher and PartDesign feature workflows.",
                {
                    "document_name": {"type": "string"},
                    "include_widget_tree": {"type": "boolean"},
                    "max_widgets": {"type": "integer", "minimum": 1, "maximum": 50},
                    "max_depth": {"type": "integer", "minimum": 0, "maximum": 4},
                    "max_children": {"type": "integer", "minimum": 1, "maximum": 80},
                    "text_max_length": {"type": "integer", "minimum": 20, "maximum": 500},
                },
                [],
                "feature_task_state",
            ),
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def attach(self, args: JsonObject) -> JsonObject:
        url = optional_string(args, "url") or DEFAULT_GUI_BRIDGE_URL
        token = optional_string(args, "token")
        probe = args.get("probe", True)
        if not isinstance(probe, bool):
            raise ToolInputError("probe must be a boolean")
        timeout_sec = bounded_int(args, "timeout_sec", default=10, minimum=1, maximum=60)
        return self.manager.attach(url=url, token=token, probe=probe, timeout_sec=timeout_sec)

    def detach(self, args: JsonObject) -> JsonObject:
        session_id = required_string(args, "session_id")
        return self.manager.detach(session_id)

    def _gui_tool(
        self,
        name: str,
        title: str,
        description: str,
        properties: JsonObject,
        required: list[str],
        method: str,
    ) -> ToolDefinition:
        schema = {"type": "object", "properties": {**SESSION_PROPS, **properties}, "required": ["session_id", *required]}
        return ToolDefinition(name, title, description, schema, lambda args, method=method, required=required: self._call(method, args, required))

    def _call(self, method: str, args: JsonObject, required: list[str]) -> JsonObject:
        session_id = required_string(args, "session_id")
        for key in required:
            if key not in args or args[key] in (None, ""):
                raise ToolInputError(f"{key} is required")
        timeout_sec = bounded_int(args, "timeout_sec", default=10, minimum=1, maximum=60)
        params = {key: value for key, value in args.items() if key not in {"session_id", "timeout_sec"}}
        return self.manager.call(session_id, method, params, timeout_sec=timeout_sec)
