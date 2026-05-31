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
            ToolDefinition(
                name="freecad_session_console",
                title="Read FreeCAD Worker Console",
                description="Read captured FreeCAD console output (stdout messages and stderr warnings/errors) for a worker session without running Python.",
                input_schema={"type": "object", "properties": {"session_id": SESSION_PROPS["session_id"], "max_lines": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum recent console lines to return per stream."}}, "required": ["session_id"]},
                handler=self.session_console,
            ),
            ToolDefinition(
                name="freecad_worker_console_read",
                title="Read FreeCAD Worker Console",
                description="Read captured FreeCAD console output (stdout messages and stderr warnings/errors) for a worker session without running Python.",
                input_schema={"type": "object", "properties": {"session_id": SESSION_PROPS["session_id"], "max_lines": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum recent console lines to return per stream."}}, "required": ["session_id"]},
                handler=self.session_console,
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
                    "extrude_mode": {"type": "string", "enum": ["auto", "shape", "feature"]},
                    "solid": {"type": "boolean"},
                    "symmetric": {"type": "boolean"},
                    "length_fwd": {"type": "number"},
                    "length_rev": {"type": "number"},
                    "taper_angle": {"type": "number", "description": "Forward taper angle in degrees."},
                    "taper_angle_rev": {"type": "number", "description": "Reverse taper angle in degrees."},
                    "reversed": {"type": "boolean"},
                    "dir_mode": {"type": "string", "enum": ["Custom", "Normal"]},
                    "face_maker_mode": {"type": "string", "enum": ["Simple", "Cheese", "Extrusion", "Bullseye"]},
                    "inner_wire_taper": {"type": "string", "enum": ["Inverted", "SameAsOuter"]},
                    "result_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "source_object"],
                "part_extrude",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_body_create",
                "Worker Create PartDesign Body",
                "Create or reuse a PartDesign Body with origin planes inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "create_body_if_missing": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "partdesign_body_create",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_datum_plane_create",
                "Worker Create PartDesign Datum Plane",
                "Create a PartDesign datum plane inside a worker Body, attached to a Body origin plane or another support object with optional offset.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "create_body_if_missing": {"type": "boolean"},
                    "datum_plane_name": {"type": "string"},
                    "plane_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "attachment_object": {"type": "string"},
                    "attachment_subname": {"type": "string"},
                    "attachment_map_mode": {"type": "string"},
                    "attachment_offset": {"type": "number"},
                    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}},
                    "require_valid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "partdesign_datum_plane_create",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_pad",
                "Worker Create PartDesign Pad",
                "Create a PartDesign Pad from a worker Sketcher profile inside a Body, attaching the sketch to an origin plane when needed.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "create_body_if_missing": {"type": "boolean"},
                    "pad_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "length": {"type": "number"},
                    "length2": {"type": "number"},
                    "midplane": {"type": "boolean"},
                    "reversed": {"type": "boolean"},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name"],
                "partdesign_pad",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_pocket",
                "Worker Create PartDesign Pocket",
                "Create a PartDesign Pocket that removes material from an existing worker Body solid using a Sketcher profile.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "create_body_if_missing": {"type": "boolean"},
                    "pocket_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "length": {"type": "number"},
                    "length2": {"type": "number"},
                    "midplane": {"type": "boolean"},
                    "reversed": {"type": "boolean"},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name"],
                "partdesign_pocket",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_hole",
                "Worker Create PartDesign Hole",
                "Create a plain PartDesign Hole from a worker Sketcher circle profile inside an existing Body solid.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "create_body_if_missing": {"type": "boolean"},
                    "hole_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "diameter": {"type": "number"},
                    "depth": {"type": "number"},
                    "depth_type": {"type": "string", "enum": ["dimension", "through_all"]},
                    "drill_point": {"type": "string", "enum": ["flat", "angled"]},
                    "drill_point_angle": {"type": "number"},
                    "tapered": {"type": "boolean"},
                    "tapered_angle": {"type": "number"},
                    "hole_cut_type": {"type": "string", "enum": ["none", "counterbore", "countersink"]},
                    "hole_cut_diameter": {"type": "number"},
                    "hole_cut_depth": {"type": "number"},
                    "hole_cut_countersink_angle": {"type": "number"},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "diameter"],
                "partdesign_hole",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_revolution",
                "Worker Create PartDesign Revolution",
                "Create an additive PartDesign Revolution from a worker Sketcher profile around a sketch or document axis.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "create_body_if_missing": {"type": "boolean"},
                    "revolution_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "reference_axis": {"type": "string", "enum": ["sketch_v_axis", "sketch_h_axis", "x_axis", "y_axis", "z_axis"]},
                    "reference_axis_object": {"type": "string"},
                    "reference_axis_subname": {"type": "string"},
                    "mode": {"type": "string", "enum": ["angle", "through_all", "up_to_last", "up_to_first", "up_to_face", "two_angles"]},
                    "angle": {"type": "number"},
                    "angle2": {"type": "number"},
                    "midplane": {"type": "boolean"},
                    "reversed": {"type": "boolean"},
                    "up_to_face_object": {"type": "string"},
                    "up_to_face_subname": {"type": "string"},
                    "fuse_order": {"type": "string", "enum": ["base_first", "feature_first"]},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name"],
                "partdesign_revolution",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_groove",
                "Worker Create PartDesign Groove",
                "Create a subtractive PartDesign Groove from a worker Sketcher profile around a sketch or document axis.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "create_body_if_missing": {"type": "boolean"},
                    "groove_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "reference_axis": {"type": "string", "enum": ["sketch_v_axis", "sketch_h_axis", "x_axis", "y_axis", "z_axis"]},
                    "reference_axis_object": {"type": "string"},
                    "reference_axis_subname": {"type": "string"},
                    "mode": {"type": "string", "enum": ["angle", "through_all", "up_to_first", "up_to_face", "two_angles"]},
                    "angle": {"type": "number"},
                    "angle2": {"type": "number"},
                    "midplane": {"type": "boolean"},
                    "reversed": {"type": "boolean"},
                    "up_to_face_object": {"type": "string"},
                    "up_to_face_subname": {"type": "string"},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name"],
                "partdesign_groove",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_additive_loft",
                "Worker Create PartDesign Additive Loft",
                "Create an additive PartDesign Loft from a worker profile sketch and one or more section sketches inside a Body.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "profile_name": {"type": "string"},
                    "profile_sketch": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "profile_subname": {"type": "string"},
                    "profile_subnames": {"type": "array", "items": {"type": "string"}},
                    "sections": {"type": "array", "items": {"type": ["string", "object"]}},
                    "section_names": {"type": "array", "items": {"type": "string"}},
                    "loft_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "ruled": {"type": "boolean"},
                    "closed": {"type": "boolean"},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "partdesign_additive_loft",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_subtractive_loft",
                "Worker Create PartDesign Subtractive Loft",
                "Create a subtractive PartDesign Loft that removes material from a worker Body solid using a profile sketch and one or more section sketches.",
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "profile_name": {"type": "string"},
                    "profile_sketch": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "profile_subname": {"type": "string"},
                    "profile_subnames": {"type": "array", "items": {"type": "string"}},
                    "sections": {"type": "array", "items": {"type": ["string", "object"]}},
                    "section_names": {"type": "array", "items": {"type": "string"}},
                    "loft_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "ruled": {"type": "boolean"},
                    "closed": {"type": "boolean"},
                    "require_solid": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "partdesign_subtractive_loft",
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
                "freecad_worker_sketch_create",
                "Worker Create Sketch",
                "Create a Sketcher object inside an in-memory worker document, optionally inside a PartDesign Body attached to XY/XZ/YZ origin plane.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "body_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "attachment_object": {"type": "string"},
                    "attachment_subname": {"type": "string"},
                    "attachment_map_mode": {"type": "string"},
                    "attachment_offset": {"type": "number"},
                    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}},
                    "create_body_if_missing": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "sketch_create",
            ),
            self._worker_tool(
                "freecad_worker_sketch_add_geometry",
                "Worker Add Sketch Geometry",
                "Add typed geometry to a worker Sketcher object.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "geometry": {"type": "array", "items": {"type": "object"}},
                    "connect_sequence": {
                        "type": "boolean",
                        "description": "Add Coincident constraints between adjacent endpoint-capable geometry in the submitted order.",
                    },
                    "close_sequence": {
                        "type": "boolean",
                        "description": "Also add a Coincident constraint from the last endpoint-capable geometry back to the first.",
                    },
                    "require_closed": {
                        "type": "boolean",
                        "description": "Fail before saving if the resulting sequence still has open vertices.",
                    },
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "geometry"],
                "sketch_add_geometry",
            ),
            self._worker_tool(
                "freecad_worker_sketch_add_constraint",
                "Worker Add Sketch Constraint",
                "Add typed constraints to a worker Sketcher object.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "constraints": {"type": "array", "items": {"type": "object"}},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "constraints"],
                "sketch_add_constraint",
            ),
            self._worker_tool(
                "freecad_worker_sketch_add_profile",
                "Worker Add Sketch Profile",
                "Add a helper profile such as rectangle variants, named/arbitrary regular polygons, circle, polyline, and straight/oriented/arc slots.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "profile": {"type": "object"},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "profile"],
                "sketch_add_profile",
            ),
            self._worker_tool(
                "freecad_worker_sketch_profile_create",
                "Worker Create Sketch Profile",
                "Create loop-based pad-ready Sketcher profiles from ordered line/arc/B-spline segments with endpoint continuity and curve-preservation guards, optionally attached inside a PartDesign Body.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "body_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                    "attachment_object": {"type": "string"},
                    "attachment_subname": {"type": "string"},
                    "attachment_map_mode": {"type": "string"},
                    "attachment_offset": {"type": "number"},
                    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}},
                    "create_body_if_missing": {"type": "boolean"},
                    "loops": {"type": "array", "items": {"type": "object"}},
                    "replace_existing": {"type": "boolean"},
                    "lock_mode": {"type": "string", "enum": ["none", "block"]},
                    "endpoint_tolerance": {"type": "number"},
                    "required_segment_types": {"type": "array", "items": {"type": "string"}},
                    "required_curve_types": {"type": "array", "items": {"type": "string"}},
                    "allowed_segment_types": {"type": "array", "items": {"type": "string"}},
                    "minimum_curve_segments": {"type": "integer"},
                    "forbid_polyline_fallback": {"type": "boolean"},
                    "forbid_all_line_loops": {"type": "boolean"},
                    "require_valid": {"type": "boolean"},
                    "require_pad_ready": {"type": "boolean"},
                    "require_fully_constrained": {"type": "boolean"},
                    "forbid_isolated_points": {"type": "boolean"},
                    "forbid_branch_points": {"type": "boolean"},
                    "forbid_micro_offsets": {"type": "boolean"},
                    "micro_offset_tolerance": {"type": "number"},
                    **SAVE_PROPS,
                },
                ["document_id", "loops"],
                "sketch_profile_create",
            ),
            self._worker_tool(
                "freecad_worker_sketch_profile_validate",
                "Worker Validate Sketch Profile",
                "Validate whether a worker Sketcher object is pad-ready and whether native geometry types match declared curve intent.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "require_pad_ready": {"type": "boolean"},
                    "require_fully_constrained": {"type": "boolean"},
                    "forbid_isolated_points": {"type": "boolean"},
                    "forbid_branch_points": {"type": "boolean"},
                    "forbid_micro_offsets": {"type": "boolean"},
                    "micro_offset_tolerance": {"type": "number"},
                    "endpoint_key_precision": {"type": "integer"},
                    "include_construction": {"type": "boolean"},
                    "required_segment_types": {"type": "array", "items": {"type": "string"}},
                    "required_curve_types": {"type": "array", "items": {"type": "string"}},
                    "minimum_curve_segments": {"type": "integer"},
                    "forbid_all_line_loops": {"type": "boolean"},
                    "forbid_polyline_fallback": {"type": "boolean"},
                    "forbid_intent_mismatch": {"type": "boolean"},
                    "expected_geometry": {"type": "array", "items": {"type": "object"}},
                },
                ["document_id", "sketch_name"],
                "sketch_profile_validate",
            ),
            self._worker_tool(
                "freecad_worker_sketch_edit_geometry",
                "Worker Edit Sketch Geometry",
                "Delete, move, toggle construction, or manage external Sketcher geometry.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "operations": {"type": "array", "items": {"type": "object"}},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "operations"],
                "sketch_edit_geometry",
            ),
            self._worker_tool(
                "freecad_worker_sketch_edit_constraints",
                "Worker Edit Sketch Constraints",
                "Delete, rename, set datum, toggle driving/active/virtual, and validate constraints.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "operations": {"type": "array", "items": {"type": "object"}},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "operations"],
                "sketch_edit_constraints",
            ),
            self._worker_tool(
                "freecad_worker_sketch_transform",
                "Worker Transform Sketch",
                "Apply Sketcher transform operations such as copy, fillet, trim, array, and B-spline edits.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "operations": {"type": "array", "items": {"type": "object"}},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "operations"],
                "sketch_transform",
            ),
            self._worker_tool(
                "freecad_worker_sketch_auto_constrain",
                "Worker Auto-Constrain Sketch",
                "Detect/apply missing Sketcher coincident, vertical/horizontal, equality, and redundant constraints.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "operations": {"type": "array", "items": {"type": "object"}},
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name"],
                "sketch_auto_constrain",
            ),
            self._worker_tool(
                "freecad_worker_sketch_validate",
                "Worker Validate Sketch",
                "Solve and summarize Sketcher state, constraints, missing constraints, and constraint errors.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "solve": {"type": "boolean"},
                    "detect_missing": {"type": "boolean"},
                    "include_constraint_errors": {"type": "boolean"},
                    "include_construction": {"type": "boolean"},
                    "precision": {"type": "number"},
                    "angle_precision": {"type": "number"},
                },
                ["document_id", "sketch_name"],
                "sketch_validate",
            ),
            self._worker_tool(
                "freecad_worker_mesh_import",
                "Worker Import Mesh",
                "Import a mesh file into an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "input_path": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "input_path"],
                "mesh_import",
            ),
            self._worker_tool(
                "freecad_worker_mesh_export",
                "Worker Export Mesh",
                "Export selected/all mesh objects from an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "output_path": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    "overwrite": {"type": "boolean"},
                    "allow_external_paths": SAVE_PROPS["allow_external_paths"],
                },
                ["document_id", "output_path"],
                "mesh_export",
            ),
            self._worker_tool(
                "freecad_worker_mesh_evaluate",
                "Worker Evaluate Mesh",
                "Summarize mesh object quality fields inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                },
                ["document_id"],
                "mesh_evaluate",
            ),
            self._worker_tool(
                "freecad_worker_mesh_repair",
                "Worker Repair Mesh",
                "Repair mesh copies and assign them back, or create a replacement mesh object when needed.",
                {
                    "document_id": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    "actions": {"type": "array", "items": {"type": "string"}},
                    "result_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "mesh_repair",
            ),
            self._worker_tool(
                "freecad_worker_mesh_boolean",
                "Worker Mesh Boolean",
                "Run mesh union/difference/intersection inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                    "operation": {"type": "string", "enum": ["union", "difference", "intersection"]},
                    "result_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "object_names"],
                "mesh_boolean",
            ),
            self._worker_tool(
                "freecad_worker_assembly_create",
                "Worker Create Assembly",
                "Create an Assembly container inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "assembly_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "assembly_create",
            ),
            self._worker_tool(
                "freecad_worker_assembly_insert",
                "Worker Assembly Insert",
                "Insert an object into a worker Assembly as an App::Link.",
                {
                    "document_id": {"type": "string"},
                    "assembly_name": {"type": "string"},
                    "object_name": {"type": "string"},
                    "link_name": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id", "assembly_name", "object_name"],
                "assembly_insert",
            ),
            self._worker_tool(
                "freecad_worker_assembly_create_joint",
                "Worker Create Assembly Joint",
                "Create a native Assembly joint proxy inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "assembly_name": {"type": "string"},
                    "joint_name": {"type": "string"},
                    "joint_type": {"type": "string"},
                    "references": {"type": "array", "items": {"type": "object"}},
                    **SAVE_PROPS,
                },
                ["document_id", "assembly_name"],
                "assembly_create_joint",
            ),
            self._worker_tool(
                "freecad_worker_assembly_solve",
                "Worker Solve Assembly",
                "Recompute a worker Assembly document.",
                {
                    "document_id": {"type": "string"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "assembly_solve",
            ),
            self._worker_tool(
                "freecad_worker_assembly_bom",
                "Worker Assembly BOM",
                "Return a compact row list for an Assembly or the whole worker document.",
                {
                    "document_id": {"type": "string"},
                    "assembly_name": {"type": "string"},
                },
                ["document_id"],
                "assembly_bom",
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
                "freecad_worker_object_rename_label",
                "Worker Rename Object Label",
                "Set the user-visible object Label while keeping the internal FreeCAD Name stable inside an in-memory worker document.",
                {
                    "document_id": {"type": "string"},
                    "object_name": {"type": "string"},
                    "label": {"type": "string"},
                    "require_unique": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id", "object_name", "label"],
                "object_rename_label",
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

    def session_console(self, args: JsonObject) -> JsonObject:
        session_id = required_string(args, "session_id")
        max_lines = bounded_int(args, "max_lines", default=200, minimum=1, maximum=500)
        return self.manager.console(session_id, max_lines=max_lines)

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
        if method == "object_delete" and not args.get("object_name") and not args.get("object_names"):
            raise ToolInputError("object_name or object_names is required")
        if method in {"part_boolean", "mesh_boolean"} and len(args.get("object_names") or []) < 2:
            raise ToolInputError("object_names must contain at least two objects")
        if method == "assembly_create_joint":
            references = args.get("references") or []
            if references and len(references) != 2:
                raise ToolInputError("references must contain exactly two connector references")
        timeout_sec = bounded_int(args, "timeout_sec", default=30, minimum=1, maximum=180)
        params = {key: value for key, value in args.items() if key not in {"session_id", "timeout_sec"}}
        return self.manager.request(session_id, method, params, timeout_sec=timeout_sec)
