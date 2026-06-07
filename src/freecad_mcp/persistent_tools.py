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

WORKER_COMPACT_PROPS: JsonObject = {
    "compact_response": {
        "type": "boolean",
        "description": "Return a compact worker response that omits repeated full document object dumps.",
    },
    "compact_execution": {
        "type": "boolean",
        "description": "Alias for compact_response on worker tools.",
    },
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

PIPE_MODE_ENUM = ["standard", "fixed", "frenet", "auxiliary", "binormal"]
PIPE_TRANSITION_ENUM = ["transformed", "right_corner", "round_corner"]
PIPE_TRANSFORMATION_ENUM = ["constant", "multisection", "linear", "s_shape", "interpolation"]
DATUM_USAGE_POLICY = (
    "FreeCAD workflow policy: use Body Origin planes for base sketches; for ordinary holes/pockets "
    "on an existing cube/top/side face, attach the sketch directly to the selected planar FaceN, "
    "add external/reference geometry from that face's edges or vertices when needed, dimension the "
    "circle/profile, then use Hole or Pocket. Datum objects live inside a Body and are useful for "
    "arbitrary mirror planes, visible reference indicators, reusable offset/angled supports for "
    "multiple sketches, revolution/groove axes, loft/sweep section supports, datum chains, and LCS "
    "orientation references. A datum plane is basically redundant for support of one sketch, and a "
    "datum attached to generated faces has the same topological naming risk as a sketch attached to "
    "those faces."
)

SKETCH_COMPLEX_PROFILE_POLICY = (
    "Complex sketches are primitive geometry plus explicit constraints plus validation, not just loose "
    "overlapping primitives. Prefer helper/profile recipes for known shapes such as rectangle, circle, "
    "regular_polygon/hexagon, slot, and keyhole. For keyhole/circle-slot cuts, use the single-loop "
    "keyhole helper or an explicit ordered arc/line loop; do not make separate overlapping circle + "
    "rectangle/slot profiles. Use trim for editing or repairing existing geometry, not as the primary "
    "construction path for new parametric profiles. For user-editable profiles, prefer "
    "constraint_policy='semantic' plus require_fully_constrained=true."
)

MODELING_STRATEGY_ENUM = [
    "visual_trace",
    "editable_parametric_sketch",
    "manufacturing_partdesign_model",
    "sketcher_constraint_rebuild",
    "rough_draft",
    "semantic_reconstruction",
    "dimensioned_parametric",
    "organic_silhouette",
    "manufacturing_profile",
]

VISUAL_ONLY_STRATEGY_ENUM = ["visual_trace", "organic_silhouette", "rough_draft"]

SOURCE_TYPE_ENUM = [
    "text_prompt",
    "image",
    "reference_image",
    "screenshot",
    "photo",
    "bitmap",
    "drawing",
    "diagram",
    "visual_reference",
    "silhouette",
    "traced_image",
    "existing_model",
    "sketch",
]

NATIVE_CURVE_INTENT_ENUM = ["none", "bspline", "arc", "ellipse", "mixed", "unknown"]

SKETCH_STRATEGY_POLICY = (
    "For image/screenshot/drawing/reference-driven work, do not mutate the sketch until the user has "
    "chosen the expected outcome. Call freecad_modeling_strategy_intake when unclear, then pass "
    "source_type, modeling_strategy, and strategy_confirmed=true. Use editable_parametric_sketch, "
    "dimensioned_parametric, manufacturing_profile, or manufacturing_partdesign_model when dimensions "
    "must survive later edits; use visual_trace or organic_silhouette only when visual similarity is the goal. "
    "If the reference shows Sketcher dimensions/constraint glyphs/construction lines, ask before choosing a "
    "visual-only strategy. If visible curves could be B-spline, arc, or ellipse, ask for native_curve_intent; "
    "visible B-spline poles/control points mean use B-spline tooling, not arc approximation; set "
    "enforce_native_curve_intent=true on low-level mutation or validate/profile-create with "
    "native_curve_intent='bspline' so arc/polyline fallback fails."
)

SKETCH_STRATEGY_PROPS: JsonObject = {
    "source_type": {
        "type": "string",
        "enum": SOURCE_TYPE_ENUM,
        "description": "Task source kind. For image/reference inputs, this triggers the modeling strategy gate.",
    },
    "has_image": {
        "type": "boolean",
        "description": "Set true when the sketch is derived from an image, screenshot, drawing, or visual reference.",
    },
    "modeling_strategy": {
        "type": "string",
        "enum": MODELING_STRATEGY_ENUM,
        "description": "Declared user intent for image/reference work, such as editable_parametric_sketch or visual_trace.",
    },
    "strategy_confirmed": {
        "type": "boolean",
        "description": "True only when the user explicitly chose the strategy or the prompt made it unambiguous.",
    },
    "visible_sketch_constraints": {
        "type": "boolean",
        "description": "Set true when the reference visibly contains Sketcher constraint glyphs/indexes or solved-state constraint cues.",
    },
    "visible_dimensions": {
        "type": "boolean",
        "description": "Set true when the reference visibly contains distance/radius/diameter/angle dimensions.",
    },
    "visible_construction_geometry": {
        "type": "boolean",
        "description": "Set true when blue guide/construction geometry is visible and should be reconstructed as construction geometry.",
    },
    "curves_visible": {
        "type": "boolean",
        "description": "Set true when visible curves require a native family decision before mutation.",
    },
    "visible_bspline_control_points": {
        "type": "boolean",
        "description": "Set true when B-spline poles/control points/handles are visible; do not submit arc geometry unless the user explicitly overrides.",
    },
    "native_curve_intent": {
        "type": "string",
        "enum": NATIVE_CURVE_INTENT_ENUM,
        "description": "Native curve family expected from the reference: bspline, arc, ellipse, mixed, none, or unknown.",
    },
    "curve_intent_confirmed": {
        "type": "boolean",
        "description": "True only when the user, GUI controls, or native FreeCAD evidence confirms the curve family.",
    },
    "curve_intent_source": {
        "type": "string",
        "enum": ["user_confirmed", "visible_gui_controls", "native_freecad_geometry", "visual_guess"],
        "description": "Evidence source for native_curve_intent. visual_guess is not enough for B-spline-vs-arc decisions.",
    },
    "enforce_native_curve_intent": {
        "type": "boolean",
        "description": "For low-level mutation tools, abort before saving if the final sketch does not contain the declared native curve family. Profile create/validate always reports this as validation failure for native_curve_intent='bspline'.",
    },
}

PIPE_WORKER_PROPS: JsonObject = {
    "document_id": {"type": "string"},
    "body_name": {"type": "string"},
    "profile_name": {"type": "string"},
    "profile_sketch": {"type": "string"},
    "sketch_name": {"type": "string"},
    "profile_subname": {"type": "string"},
    "profile_subnames": {"type": "array", "items": {"type": "string"}},
    "spine_name": {"type": "string"},
    "spine_sketch": {"type": "string"},
    "path_name": {"type": "string"},
    "path_sketch": {"type": "string"},
    "spine_subname": {"type": "string"},
    "spine_subnames": {"type": "array", "items": {"type": "string"}},
    "path_subname": {"type": "string"},
    "spine_tangent": {"type": "boolean"},
    "auxiliary_spine_name": {"type": "string"},
    "auxiliary_spine_sketch": {"type": "string"},
    "aux_spine_name": {"type": "string"},
    "aux_spine_sketch": {"type": "string"},
    "auxiliary_spine_subname": {"type": "string"},
    "auxiliary_spine_subnames": {"type": "array", "items": {"type": "string"}},
    "aux_spine_subname": {"type": "string"},
    "aux_spine_subnames": {"type": "array", "items": {"type": "string"}},
    "auxiliary_spine_tangent": {"type": "boolean"},
    "auxiliary_curvilinear": {"type": "boolean"},
    "sections": {"type": "array", "items": {"type": ["string", "object"]}},
    "section_names": {"type": "array", "items": {"type": "string"}},
    "mode": {"type": "string", "enum": PIPE_MODE_ENUM},
    "orientation_mode": {"type": "string", "enum": PIPE_MODE_ENUM},
    "transition": {"type": "string", "enum": PIPE_TRANSITION_ENUM},
    "transformation": {"type": "string", "enum": PIPE_TRANSFORMATION_ENUM},
    "scaling_mode": {"type": "string", "enum": PIPE_TRANSFORMATION_ENUM},
    "binormal": {"type": "array", "items": {"type": "number"}},
    "pipe_name": {"type": "string"},
    "result_name": {"type": "string"},
    "require_solid": {"type": "boolean"},
    **SAVE_PROPS,
}

DRESSUP_BASE_WORKER_PROPS: JsonObject = {
    "document_id": {"type": "string"},
    "body_name": {"type": "string"},
    "base_feature_name": {"type": "string"},
    "base_name": {"type": "string"},
    "source_object": {"type": "string"},
    "feature_name": {"type": "string"},
    "base_subname": {"type": "string"},
    "base_subnames": {"type": "array", "items": {"type": "string"}},
    "subname": {"type": "string"},
    "subnames": {"type": "array", "items": {"type": "string"}},
    "edge_name": {"type": "string"},
    "edge_names": {"type": "array", "items": {"type": "string"}},
    "edge_indices": {"type": "array", "items": {"type": "integer"}},
    "face_name": {"type": "string"},
    "face_names": {"type": "array", "items": {"type": "string"}},
    "face_indices": {"type": "array", "items": {"type": "integer"}},
    "dressup_name": {"type": "string"},
    "result_name": {"type": "string"},
    "support_transform": {"type": "boolean"},
    "require_solid": {"type": "boolean"},
    **SAVE_PROPS,
}

FILLET_WORKER_PROPS: JsonObject = {
    **DRESSUP_BASE_WORKER_PROPS,
    "radius": {"type": "number"},
    "use_all_edges": {"type": "boolean"},
    "fillet_name": {"type": "string"},
}

CHAMFER_WORKER_PROPS: JsonObject = {
    **DRESSUP_BASE_WORKER_PROPS,
    "distance": {"type": "number"},
    "size": {"type": "number"},
    "size2": {"type": "number"},
    "angle": {"type": "number"},
    "chamfer_type": {"type": "string", "enum": ["equal_distance", "two_distances", "distance_and_angle"]},
    "flip_direction": {"type": "boolean"},
    "use_all_edges": {"type": "boolean"},
    "chamfer_name": {"type": "string"},
}

THICKNESS_WORKER_PROPS: JsonObject = {
    **DRESSUP_BASE_WORKER_PROPS,
    "thickness": {"type": "number"},
    "value": {"type": "number"},
    "mode": {"type": "string", "enum": ["skin", "pipe", "recto_verso"]},
    "join": {"type": "string", "enum": ["arc", "intersection"]},
    "reversed": {"type": "boolean"},
    "intersection": {"type": "boolean"},
    "thickness_name": {"type": "string"},
}

DRAFT_WORKER_PROPS: JsonObject = {
    **DRESSUP_BASE_WORKER_PROPS,
    "neutral_plane_name": {"type": "string"},
    "neutral_plane_object": {"type": "string"},
    "neutral_plane": {"type": "string"},
    "neutral_plane_subname": {"type": "string"},
    "pull_direction_name": {"type": "string"},
    "pull_direction_object": {"type": "string"},
    "pull_direction": {"type": "string"},
    "pull_direction_subname": {"type": "string"},
    "angle": {"type": "number"},
    "reversed": {"type": "boolean"},
    "draft_name": {"type": "string"},
}

TRANSFORM_BASE_WORKER_PROPS: JsonObject = {
    "document_id": {"type": "string"},
    "body_name": {"type": "string"},
    "original_feature_name": {"type": "string"},
    "original_names": {"type": "array", "items": {"type": "string"}},
    "feature_name": {"type": "string"},
    "feature_names": {"type": "array", "items": {"type": "string"}},
    "base_feature_name": {"type": "string"},
    "source_object": {"type": "string"},
    "whole_shape": {"type": "boolean"},
    "transform_mode": {"type": "string", "enum": ["features", "whole_shape"]},
    "transform_name": {"type": "string"},
    "result_name": {"type": "string"},
    "require_solid": {"type": "boolean"},
    **SAVE_PROPS,
}

LINEAR_PATTERN_WORKER_PROPS: JsonObject = {
    **TRANSFORM_BASE_WORKER_PROPS,
    "direction_axis": {"type": "string", "enum": ["x_axis", "y_axis", "z_axis"]},
    "direction_name": {"type": "string"},
    "direction_object": {"type": "string"},
    "direction_subname": {"type": "string"},
    "reversed": {"type": "boolean"},
    "mode": {"type": "string", "enum": ["extent", "spacing"]},
    "length": {"type": "number"},
    "offset": {"type": "number"},
    "occurrences": {"type": "integer", "minimum": 1},
    "direction2_axis": {"type": "string", "enum": ["x_axis", "y_axis", "z_axis"]},
    "direction2_name": {"type": "string"},
    "direction2_object": {"type": "string"},
    "direction2_subname": {"type": "string"},
    "reversed2": {"type": "boolean"},
    "mode2": {"type": "string", "enum": ["extent", "spacing"]},
    "length2": {"type": "number"},
    "offset2": {"type": "number"},
    "occurrences2": {"type": "integer", "minimum": 1},
    "linear_pattern_name": {"type": "string"},
    "pattern_name": {"type": "string"},
}

POLAR_PATTERN_WORKER_PROPS: JsonObject = {
    **TRANSFORM_BASE_WORKER_PROPS,
    "axis": {"type": "string"},
    "axis_name": {"type": "string"},
    "axis_object": {"type": "string"},
    "axis_subname": {"type": "string"},
    "reversed": {"type": "boolean"},
    "mode": {"type": "string", "enum": ["extent", "spacing"]},
    "angle": {"type": "number"},
    "offset": {"type": "number"},
    "occurrences": {"type": "integer", "minimum": 1},
    "polar_pattern_name": {"type": "string"},
    "pattern_name": {"type": "string"},
}

MIRRORED_WORKER_PROPS: JsonObject = {
    **TRANSFORM_BASE_WORKER_PROPS,
    "mirror_plane": {"type": "string"},
    "mirror_plane_name": {"type": "string"},
    "mirror_plane_object": {"type": "string"},
    "mirror_plane_subname": {"type": "string"},
    "mirrored_name": {"type": "string"},
    "mirror_name": {"type": "string"},
}

WORKER_SKETCH_EXTERNAL_REFERENCE_PROPS: JsonObject = {
    "document_id": {"type": "string"},
    "sketch_name": {"type": "string"},
    "object_name": {"type": "string", "description": "Referenced object or feature name, such as a Body Tip feature, master sketch, or datum/support object."},
    "sub_name": {"type": "string", "description": "Referenced subelement such as Edge1, Face1, or Vertex1."},
    "sub_names": {"type": "array", "items": {"type": "string"}, "description": "Multiple subelements on the same object."},
    "references": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "object_name": {"type": "string"},
                "sub_name": {"type": "string"},
            },
        },
        "description": "Multiple object/subelement references. Use this when references come from different objects.",
    },
    "defining": {"type": "boolean", "description": "Create defining external geometry where FreeCAD supports it; false creates normal reference geometry."},
    **SAVE_PROPS,
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
                "Create a PartDesign datum plane inside a worker Body, attached to a Body origin plane or another support object with optional offset. " + DATUM_USAGE_POLICY,
                {
                    "document_id": {"type": "string"},
                    "body_name": {"type": "string"},
                    "create_body_if_missing": {"type": "boolean"},
                    "datum_plane_name": {"type": "string"},
                    "plane_name": {"type": "string"},
                    "result_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"], "description": "Origin plane to derive this datum from. The Body Origin may be hidden in GUI but is still addressable."},
                    "attachment_object": {"type": "string", "description": "Optional support object for datum references, including origin plane, planar face, edge, vertex, or another datum."},
                    "attachment_subname": {"type": "string", "description": "Support subelement such as Face1, Edge1, or Vertex1."},
                    "attachment_map_mode": {"type": "string"},
                    "attachment_offset": {"type": "number", "description": "Datum offset in the datum's local coordinate system; z is along the datum normal."},
                    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}, "description": "Datum XYZ offset in the datum's local coordinate system; z is along the datum normal."},
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
                "Create a PartDesign Pocket that removes material from an existing worker Body solid using a Sketcher profile. Common FreeCAD workflow: sketch on the target planar FaceN, reference face edges/vertices with external geometry, dimension the profile, then pocket.",
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
                "Create a plain PartDesign Hole from a worker Sketcher circle profile inside an existing Body solid. Common FreeCAD workflow: sketch on the target planar FaceN, reference face edges/vertices with external geometry, dimension the circle position and diameter, then create Hole.",
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
                "freecad_worker_partdesign_additive_pipe",
                "Worker Create PartDesign Additive Pipe",
                "Create an additive PartDesign Pipe by sweeping a worker profile sketch along a spine/path sketch inside a Body.",
                dict(PIPE_WORKER_PROPS),
                ["document_id"],
                "partdesign_additive_pipe",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_subtractive_pipe",
                "Worker Create PartDesign Subtractive Pipe",
                "Create a subtractive PartDesign Pipe by sweeping a worker profile sketch along a spine/path sketch to remove material from an existing Body solid.",
                dict(PIPE_WORKER_PROPS),
                ["document_id"],
                "partdesign_subtractive_pipe",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_fillet",
                "Worker Create PartDesign Fillet",
                "Create a PartDesign Fillet dress-up in an in-memory worker document.",
                dict(FILLET_WORKER_PROPS),
                ["document_id"],
                "partdesign_fillet",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_chamfer",
                "Worker Create PartDesign Chamfer",
                "Create a PartDesign Chamfer dress-up in an in-memory worker document.",
                dict(CHAMFER_WORKER_PROPS),
                ["document_id"],
                "partdesign_chamfer",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_thickness",
                "Worker Create PartDesign Thickness",
                "Create a PartDesign Thickness dress-up in an in-memory worker document.",
                dict(THICKNESS_WORKER_PROPS),
                ["document_id"],
                "partdesign_thickness",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_draft",
                "Worker Create PartDesign Draft",
                "Create a PartDesign Draft dress-up in an in-memory worker document.",
                dict(DRAFT_WORKER_PROPS),
                ["document_id"],
                "partdesign_draft",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_linear_pattern",
                "Worker Create PartDesign Linear Pattern",
                "Create a PartDesign LinearPattern transform in an in-memory worker document.",
                dict(LINEAR_PATTERN_WORKER_PROPS),
                ["document_id"],
                "partdesign_linear_pattern",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_polar_pattern",
                "Worker Create PartDesign Polar Pattern",
                "Create a PartDesign PolarPattern transform in an in-memory worker document.",
                dict(POLAR_PATTERN_WORKER_PROPS),
                ["document_id"],
                "partdesign_polar_pattern",
            ),
            self._worker_tool(
                "freecad_worker_partdesign_mirrored",
                "Worker Create PartDesign Mirrored",
                "Create a PartDesign Mirrored transform in an in-memory worker document.",
                dict(MIRRORED_WORKER_PROPS),
                ["document_id"],
                "partdesign_mirrored",
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
                "freecad_worker_geometry_check",
                "Worker Check Geometry",
                "Run visible BRep/shape geometry validity checks inside an in-memory worker document without exposing standalone Part primitive creation tools.",
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
                "Create a Sketcher object inside an in-memory worker document, optionally inside a PartDesign Body attached to XY/XZ/YZ origin plane, planar face, datum, or other support. " + DATUM_USAGE_POLICY,
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "body_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"], "description": "Body Origin plane for base sketches or simple independent offsets."},
                    "attachment_object": {"type": "string", "description": "Support object for the sketch. Use with attachment_subname='FaceN' for normal planar-face sketching, or with a datum/support object for reusable references."},
                    "attachment_subname": {"type": "string", "description": "Support subelement such as Face1, Edge1, or Vertex1. For PartDesign face-local holes/pockets, use a planar FaceN selected from the target Body feature."},
                    "attachment_map_mode": {"type": "string"},
                    "attachment_offset": {"type": "number", "description": "Offset from the selected origin plane, planar face, or datum support."},
                    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}, "description": "XYZ offset from the selected origin plane, planar face, or datum support."},
                    "create_body_if_missing": {"type": "boolean"},
                    **SAVE_PROPS,
                },
                ["document_id"],
                "sketch_create",
            ),
            self._worker_tool(
                "freecad_worker_sketch_add_geometry",
                "Worker Add Sketch Geometry",
                "Add typed geometry to a worker Sketcher object. Coordinate arrays may be [x,y] or [x,y,z]. Use this low-level primitive path when exact control is needed; for common closed profiles prefer helper/profile tools so constraints and pad-readiness are not left for the agent to guess. " + SKETCH_COMPLEX_PROFILE_POLICY + " " + SKETCH_STRATEGY_POLICY,
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
                    **SKETCH_STRATEGY_PROPS,
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "geometry"],
                "sketch_add_geometry",
            ),
            self._worker_tool(
                "freecad_worker_sketch_add_constraint",
                "Worker Add Sketch Constraint",
                "Add typed constraints to a worker Sketcher object by passing the provided type string to FreeCAD's Sketcher.Constraint(type, *values) constructor, except blocked unsafe/crashy types Group and Text. Common supported type strings include Coincident, Tangent, Equal, Angle, Distance, DistanceX, DistanceY, PointOnObject, Radius, Diameter, Horizontal, Vertical, Parallel, Perpendicular, Symmetric, Lock, and Block; the process freecad_sketch_geometry_method_catalog exposes the machine-readable constraint_methods list and field shapes. A complex reusable sketch must be primitive geometry plus coincident/tangent/equality/symmetry/dimensional constraints; add named driving dimensions and expressions instead of leaving important distances as raw coordinates.",
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
                "Add a helper profile such as rectangle variants, named/arbitrary regular polygons, circle, polyline, straight/oriented/arc slots, and single-loop keyhole circle+slot profiles. Prefer these helpers over loose overlapping primitives; for a keyhole cut, use the keyhole helper rather than separate circle + rectangle/slot geometry. " + SKETCH_STRATEGY_POLICY,
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "profile": {"type": "object"},
                    **SKETCH_STRATEGY_PROPS,
                    **SAVE_PROPS,
                },
                ["document_id", "sketch_name", "profile"],
                "sketch_add_profile",
            ),
            self._worker_tool(
                "freecad_worker_sketch_profile_create",
                "Worker Create Sketch Profile",
                "Create loop-based pad-ready Sketcher profiles from ordered line/arc/B-spline segments or helper loops such as rectangle, circle, regular_polygon/hexagon, slot, and keyhole, with endpoint continuity and curve-preservation guards, optionally attached inside a PartDesign Body. This is the preferred complex-sketch builder for worker sessions: it expands helpers or ordered segments, validates closed wires, and can enforce pad-ready/full-constraint contracts. Coordinate arrays may be [x,y] or [x,y,z]. " + SKETCH_COMPLEX_PROFILE_POLICY + " " + DATUM_USAGE_POLICY + " " + SKETCH_STRATEGY_POLICY,
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "body_name": {"type": "string"},
                    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"], "description": "Body Origin plane for base profile sketches or simple independent offsets."},
                    "attachment_object": {"type": "string", "description": "Support object for the profile sketch. Use with attachment_subname='FaceN' for normal planar-face hole/pocket profiles, or with a datum/support object for reusable references."},
                    "attachment_subname": {"type": "string", "description": "Support subelement such as Face1, Edge1, or Vertex1. For PartDesign face-local holes/pockets, use a planar FaceN selected from the target Body feature."},
                    "attachment_map_mode": {"type": "string"},
                    "attachment_offset": {"type": "number", "description": "Offset from the selected origin plane, planar face, or datum support."},
                    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}, "description": "XYZ offset from the selected origin plane, planar face, or datum support."},
                    "create_body_if_missing": {"type": "boolean"},
                    "loops": {"type": "array", "items": {"type": "object"}},
                    "replace_existing": {"type": "boolean"},
                    "lock_mode": {"type": "string", "enum": ["none", "block"]},
                    "constraint_policy": {"type": "string", "enum": ["none", "shape", "semantic"], "description": "For supported helper loops, add shape-preserving constraints; semantic also adds named driving dimensions and rejects Block-constraint shortcuts during validation."},
                    "semantic_constraints": {"type": "boolean", "description": "Alias for constraint_policy='semantic'."},
                    "forbid_block_constraints": {"type": "boolean", "description": "Reject Sketcher Block constraints during validation; implied by semantic constraint policy."},
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
                    **SKETCH_STRATEGY_PROPS,
                    **SAVE_PROPS,
                },
                ["document_id", "loops"],
                "sketch_profile_create",
            ),
            self._worker_tool(
                "freecad_worker_sketch_profile_validate",
                "Worker Validate Sketch Profile",
                "Validate whether a worker Sketcher object is pad-ready and whether native geometry types match declared curve intent. Use after low-level primitive/constraint work and reject results that are open, under-constrained when full constraint is required, or only appear complex because of overlapping untrimmed profiles. " + SKETCH_STRATEGY_POLICY,
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "require_pad_ready": {"type": "boolean"},
                    "require_fully_constrained": {"type": "boolean"},
                    "constraint_policy": {"type": "string", "enum": ["none", "shape", "semantic"], "description": "Validation policy; semantic rejects Block-constraint shortcuts."},
                    "semantic_constraints": {"type": "boolean"},
                    "forbid_block_constraints": {"type": "boolean"},
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
                    **SKETCH_STRATEGY_PROPS,
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
                "freecad_worker_sketch_external_projection",
                "Worker Add Sketch External Projection",
                "Add FreeCAD 1.1 Sketcher External Projection references to a worker sketch from selected faces, edges, vertices, master sketches, or datum/support geometry.",
                WORKER_SKETCH_EXTERNAL_REFERENCE_PROPS,
                ["document_id", "sketch_name"],
                "sketch_external_projection",
            ),
            self._worker_tool(
                "freecad_worker_sketch_external_intersection",
                "Worker Add Sketch External Intersection",
                "Add FreeCAD 1.1 Sketcher External Intersection references to a worker sketch from selected faces, edges, vertices, master sketches, or datum/support geometry.",
                WORKER_SKETCH_EXTERNAL_REFERENCE_PROPS,
                ["document_id", "sketch_name"],
                "sketch_external_intersection",
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
                "Apply Sketcher transform operations such as copy, fillet, trim, array, and B-spline edits. Trim is an edit/repair operation for existing geometry; for new parametric keyholes, slots, sockets, and reusable closed profiles prefer profile helpers or ordered arc/line loops with semantic constraints and validation.",
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
                "Solve and summarize native Sketcher state, geometry, constraints, missing constraints, semantic groups such as tangent/equal chains, helper-intent report layers, and constraint errors. Use this to get native Sketcher evidence instead of inferring constraint state from screenshot colors. Report helper/profile intent separately from native primitives: rectangle is 4 LineSegment geometry with Horizontal/Vertical/Coincident constraints; regular polygon is LineSegment plus construction circle, PointOnObject, and Equal constraints; slot is 2 LineSegment plus 2 ArcOfCircle with Tangent and equal/radius constraints.",
                {
                    "document_id": {"type": "string"},
                    "sketch_name": {"type": "string"},
                    "solve": {"type": "boolean"},
                    "detect_missing": {"type": "boolean"},
                    "include_geometry": {"type": "boolean", "description": "Include native geometry details such as type_id, construction flag, start/end/center/radius and B-spline poles/knots when available. Defaults true."},
                    "include_constraints": {"type": "boolean", "description": "Include constraint type, raw indices, resolved refs, names, values, driving/active state, and label metadata. Defaults true."},
                    "include_semantic_groups": {"type": "boolean", "description": "Include derived tangent pairs/chains, equal groups, PointOnObject, horizontal/vertical, symmetry, dimensional/radius constraints, construction geometry, and coincident pairs. Defaults true."},
                    "include_report_layers": {"type": "boolean", "description": "Include native_geometry, construction_geometry, constraint_graph, and helper_intent_inference layers. Defaults true."},
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
                "Set simple object properties and link properties such as Tip, BaseFeature, or Group using {'$ref':'ObjectName'} / {'$refs':['A','B']} specs inside an in-memory worker document.",
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
                "Delete object(s) inside an in-memory worker document and restore a PartDesign Body Tip to the previous solid feature when the deleted object was the current Tip.",
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
        schema = {"type": "object", "properties": {**SESSION_PROPS, **properties, **WORKER_COMPACT_PROPS}}
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
        compact_response = args.get("compact_response", args.get("compact_execution", False))
        if not isinstance(compact_response, bool):
            raise ToolInputError("compact_response must be a boolean")
        params = {
            key: value
            for key, value in args.items()
            if key not in {"session_id", "timeout_sec", "compact_response", "compact_execution"}
        }
        payload = self.manager.request(session_id, method, params, timeout_sec=timeout_sec)
        return compact_worker_payload(payload) if compact_response else payload


def compact_shape_summary(shape: object) -> object:
    if not isinstance(shape, dict):
        return shape
    return {key: shape.get(key) for key in ("valid", "is_null", "solids", "faces", "edges", "vertices") if key in shape}


def compact_sketch_summary(sketch: object) -> object:
    if not isinstance(sketch, dict):
        return sketch
    return {
        key: sketch.get(key)
        for key in ("geometry_count", "constraint_count", "degrees_of_freedom", "open_vertices", "redundant_constraints", "conflicting_constraints")
        if key in sketch
    }


def compact_partdesign_summary(partdesign: object) -> object:
    if not isinstance(partdesign, dict):
        return partdesign
    return {
        key: partdesign.get(key)
        for key in ("type", "tip", "profile", "length", "length2", "reversed", "midplane")
        if key in partdesign
    }


def compact_object_summary(value: JsonObject) -> JsonObject:
    result: JsonObject = {
        key: value.get(key)
        for key in ("name", "label", "type_id", "visibility")
        if key in value
    }
    if "shape" in value:
        result["shape"] = compact_shape_summary(value.get("shape"))
    if value.get("sketch") is not None:
        result["sketch"] = compact_sketch_summary(value.get("sketch"))
    if value.get("partdesign") is not None:
        result["partdesign"] = compact_partdesign_summary(value.get("partdesign"))
    return result


def compact_document_summary(value: JsonObject) -> JsonObject:
    return {
        key: value.get(key)
        for key in ("document_id", "name", "label", "file_name", "object_count")
        if key in value
    }


def compact_worker_value(value: object) -> object:
    if isinstance(value, list):
        return [compact_worker_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "objects" in value and "object_count" in value:
        return compact_document_summary(value)
    if "type_id" in value and "name" in value:
        return compact_object_summary(value)
    return {key: compact_worker_value(item) for key, item in value.items()}


def compact_worker_payload(payload: JsonObject) -> JsonObject:
    compacted: JsonObject = {"ok": payload.get("ok"), "compact_response": True}
    session = payload.get("session")
    if isinstance(session, dict):
        compacted["session"] = {
            key: session.get(key)
            for key in ("session_id", "mode", "pid", "running", "request_count")
            if key in session
        }
    worker = payload.get("worker")
    if isinstance(worker, dict):
        compact_worker: JsonObject = {"ok": worker.get("ok")}
        if "result" in worker:
            compact_worker["result"] = compact_worker_value(worker.get("result"))
        if "error" in worker:
            compact_worker["error"] = worker.get("error")
        if "traceback_truncated" in worker:
            compact_worker["traceback_truncated"] = worker.get("traceback_truncated")
        compacted["worker"] = compact_worker
    return compacted
