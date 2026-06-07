"""Sketcher CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


SKETCH_ATTACHMENT_POLICY = (
    "FreeCAD PartDesign attachment decision: use a Body Origin plane (XY/XZ/YZ) for base sketches "
    "and simple independent offsets; use attachment_object plus attachment_subname such as Face1 "
    "for ordinary face-local operations on an existing planar face, like a hole or pocket on a "
    "cube top/side face; use datum support for named/reused reference planes, special orientations, "
    "loft/sweep sections, or explicit user-visible reference geometry."
)

SKETCH_COMPLEX_PROFILE_POLICY = (
    "Complex sketches are primitive geometry plus explicit constraints plus validation, not just loose "
    "overlapping primitives. Prefer intent/profile helpers for known shapes such as rectangle, circle, "
    "regular_polygon/hexagon, slot, and keyhole. For keyhole/circle-slot cuts, use the single-loop "
    "keyhole helper or an explicit ordered arc/line loop; do not make separate overlapping circle + "
    "rectangle/slot profiles for a PartDesign cut. Use trim for editing or repairing existing geometry, "
    "not as the primary construction path for new parametric profiles. For user-editable or parametric "
    "profiles, prefer constraint_policy='semantic' plus require_fully_constrained=true so dimensions are "
    "named Sketcher drivers instead of static coordinates or Block constraints. Treat helper/profile "
    "intent as native geometry plus constraint fingerprint, not as a separate primitive family."
)

SKETCH_HELPER_LAYER_POLICY = (
    "Report helper/profile intent separately from native primitives: Rectangle is 4 LineSegment geometry "
    "with Horizontal/Vertical/Coincident constraints; regular polygons are LineSegment loops with a "
    "construction circle, PointOnObject, and Equal constraints; slot is 2 LineSegment plus 2 ArcOfCircle "
    "with Tangent and equal/radius constraints. Do not call helpers separate native primitive types."
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

SKETCH_STRATEGY_POLICY = (
    "For image/screenshot/drawing/reference-driven work, do not mutate the sketch until the user has "
    "chosen the expected outcome. Call freecad_modeling_strategy_intake when unclear, then pass "
    "source_type, modeling_strategy, and strategy_confirmed=true. Use editable_parametric_sketch, "
    "dimensioned_parametric, manufacturing_profile, or manufacturing_partdesign_model when dimensions "
    "must survive later edits; use visual_trace or organic_silhouette only when visual similarity is the goal."
)

SKETCH_STRATEGY_PROPS = {
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
}


SKETCH_EXTERNAL_REFERENCE_PROPS = {
    "document_path": {"type": "string"},
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
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
}


class SketchCadToolService(CadDomainToolService):
    domain = "sketcher"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_sketch_create", "Create Sketch", "Create a Sketcher object, optionally inside a PartDesign Body attached to XY/XZ/YZ origin plane, planar face, datum, or other support. " + SKETCH_ATTACHMENT_POLICY, {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "body_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"], "description": "Body Origin plane for base sketches or simple independent offsets."}, "attachment_object": {"type": "string", "description": "Support object for the sketch. Use with attachment_subname='FaceN' for normal planar-face sketching, or with a datum/support object for reusable references."}, "attachment_subname": {"type": "string", "description": "Support subelement such as Face1, Edge1, or Vertex1. For PartDesign face-local holes/pockets, use a planar FaceN selected from the target Body feature."}, "attachment_map_mode": {"type": "string"}, "attachment_offset": {"type": "number", "description": "Offset from the selected origin plane, planar face, or datum support."}, "attachment_offset_vector": {"type": "array", "items": {"type": "number"}, "description": "XYZ offset from the selected origin plane, planar face, or datum support."}, "create_body_if_missing": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "sketch_create"),
            CadToolSpec(
                "freecad_sketch_add_geometry",
                "Add Sketch Geometry",
                "Add point, line, circle, arc, ellipse, conic arc, B-spline, or polyline geometry to a sketch. Coordinate arrays may be [x,y] or [x,y,z]. Use this low-level primitive path when exact geometry/control is needed; for common closed profiles prefer profile helpers so constraints and pad-readiness are not left for the agent to guess. " + SKETCH_COMPLEX_PROFILE_POLICY + " " + SKETCH_STRATEGY_POLICY,
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "geometry": {"type": "array", "items": {"type": "object"}}, "connect_sequence": {"type": "boolean", "description": "Add Coincident constraints between adjacent endpoint-capable geometry in the submitted order."}, "close_sequence": {"type": "boolean", "description": "Also add a Coincident constraint from the last endpoint-capable geometry back to the first."}, "require_closed": {"type": "boolean", "description": "Fail before saving if the resulting sequence still has open vertices."}, **SKETCH_STRATEGY_PROPS, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "geometry"],
                "sketch_add_geometry",
            ),
            CadToolSpec(
                "freecad_sketch_add_constraint",
                "Add Sketch Constraint",
                "Add raw or named Sketcher constraints by passing the provided type string to FreeCAD's Sketcher.Constraint(type, *values) constructor, except blocked unsafe/crashy types Group and Text. Common supported type strings include Coincident, Tangent, Equal, Angle, Distance, DistanceX, DistanceY, PointOnObject, Radius, Diameter, Horizontal, Vertical, Parallel, Perpendicular, Symmetric, Lock, and Block; call freecad_sketch_geometry_method_catalog for the machine-readable constraint_methods list and field shapes. Optional metadata includes datum, driving, active, visibility, and label placement. A complex reusable sketch must be primitive geometry plus coincident/tangent/equality/symmetry/dimensional constraints; add named driving dimensions and expressions instead of leaving important distances as raw coordinates.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "constraints"],
                "sketch_add_constraint",
            ),
            CadToolSpec(
                "freecad_sketch_add_profile",
                "Add Sketch Profile",
                "Add common closed/open Sketcher profiles such as rectangle variants, named/arbitrary regular polygons, circle, polyline, straight/oriented/arc slots, and single-loop keyhole circle+slot profiles. Prefer these helpers over loose overlapping primitives; for a keyhole cut, use the keyhole helper rather than separate circle + rectangle/slot geometry. " + SKETCH_STRATEGY_POLICY,
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "profile": {"type": "object"}, **SKETCH_STRATEGY_PROPS, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "profile"],
                "sketch_add_profile",
            ),
            CadToolSpec(
                "freecad_sketch_profile_create",
                "Create Sketch Profile",
                "Create loop-based pad-ready Sketcher profiles from ordered line/arc/B-spline segments or helper loops: rectangle/polyline, circle, named/arbitrary regular polygons such as hexagon, straight slots, and single-loop keyhole circle+slot profiles. This is the preferred complex-sketch builder when an agent must combine primitives into a real FreeCAD profile: it expands helpers or ordered segments, applies endpoint/shape constraints, validates closed wires, and can enforce pad-ready/full-constraint contracts. With constraint_policy='semantic', supported helper loops emit named driving dimensions such as width/height, polygon radius/center/orientation, circle radius/center, slot radius, or keyhole radii instead of relying on Block constraints. Coordinate arrays may be [x,y] or [x,y,z]. " + SKETCH_COMPLEX_PROFILE_POLICY + " " + SKETCH_ATTACHMENT_POLICY + " " + SKETCH_STRATEGY_POLICY,
                {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "body_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"], "description": "Body Origin plane for base profile sketches or simple independent offsets."}, "attachment_object": {"type": "string", "description": "Support object for the profile sketch. Use with attachment_subname='FaceN' for normal planar-face hole/pocket profiles, or with a datum/support object for reusable references."}, "attachment_subname": {"type": "string", "description": "Support subelement such as Face1, Edge1, or Vertex1. For PartDesign face-local holes/pockets, use a planar FaceN selected from the target Body feature."}, "attachment_map_mode": {"type": "string"}, "attachment_offset": {"type": "number", "description": "Offset from the selected origin plane, planar face, or datum support."}, "attachment_offset_vector": {"type": "array", "items": {"type": "number"}, "description": "XYZ offset from the selected origin plane, planar face, or datum support."}, "create_body_if_missing": {"type": "boolean"}, "loops": {"type": "array", "items": {"type": "object"}}, "replace_existing": {"type": "boolean"}, "lock_mode": {"type": "string", "enum": ["none", "block"]}, "constraint_policy": {"type": "string", "enum": ["none", "shape", "semantic"], "description": "For supported helper loops, add shape-preserving constraints; semantic also adds named driving dimensions and rejects Block-constraint shortcuts during validation."}, "semantic_constraints": {"type": "boolean", "description": "Alias for constraint_policy='semantic'."}, "forbid_block_constraints": {"type": "boolean", "description": "Reject Sketcher Block constraints during validation; implied by semantic constraint policy."}, "endpoint_tolerance": {"type": "number"}, "required_segment_types": {"type": "array", "items": {"type": "string"}}, "required_curve_types": {"type": "array", "items": {"type": "string"}}, "allowed_segment_types": {"type": "array", "items": {"type": "string"}}, "minimum_curve_segments": {"type": "integer"}, "forbid_polyline_fallback": {"type": "boolean"}, "forbid_all_line_loops": {"type": "boolean"}, "require_valid": {"type": "boolean"}, "require_pad_ready": {"type": "boolean"}, "require_fully_constrained": {"type": "boolean"}, "forbid_isolated_points": {"type": "boolean"}, "forbid_branch_points": {"type": "boolean"}, "forbid_micro_offsets": {"type": "boolean"}, "micro_offset_tolerance": {"type": "number"}, **SKETCH_STRATEGY_PROPS, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["loops"],
                "sketch_profile_create",
            ),
            CadToolSpec(
                "freecad_sketch_profile_validate",
                "Validate Sketch Profile",
                "Validate whether a Sketcher object is pad-ready and whether its native geometry types match declared curve intent. Use after low-level primitive/constraint work and reject results that are open, under-constrained when full constraint is required, or only appear complex because of overlapping untrimmed profiles. " + SKETCH_STRATEGY_POLICY,
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "require_pad_ready": {"type": "boolean"}, "require_fully_constrained": {"type": "boolean"}, "constraint_policy": {"type": "string", "enum": ["none", "shape", "semantic"], "description": "Validation policy; semantic rejects Block-constraint shortcuts."}, "semantic_constraints": {"type": "boolean"}, "forbid_block_constraints": {"type": "boolean"}, "forbid_isolated_points": {"type": "boolean"}, "forbid_branch_points": {"type": "boolean"}, "forbid_micro_offsets": {"type": "boolean"}, "micro_offset_tolerance": {"type": "number"}, "endpoint_key_precision": {"type": "integer"}, "include_construction": {"type": "boolean"}, "required_segment_types": {"type": "array", "items": {"type": "string"}}, "required_curve_types": {"type": "array", "items": {"type": "string"}}, "minimum_curve_segments": {"type": "integer"}, "forbid_all_line_loops": {"type": "boolean"}, "forbid_polyline_fallback": {"type": "boolean"}, "forbid_intent_mismatch": {"type": "boolean"}, "expected_geometry": {"type": "array", "items": {"type": "object"}}, **SKETCH_STRATEGY_PROPS},
                ["document_path", "sketch_name"],
                "sketch_profile_validate",
            ),
            CadToolSpec(
                "freecad_curve_fit_analyze",
                "Analyze Curve Fit",
                "Compare line and circular-arc fit errors for traced sketch points and recommend line, arc, or B-spline without mutating a document.",
                {"points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}}, "tolerance": {"type": "number"}, "fit_tolerance": {"type": "number"}},
                ["points"],
                "curve_fit_analyze",
            ),
            CadToolSpec(
                "freecad_sketch_geometry_method_catalog",
                "Sketch Geometry Method Catalog",
                "Return the supported typed creation methods for Sketcher geometry, profiles, constraints, transform-generated geometry, and analysis tools, including which helper/profile paths should be used instead of ad-hoc overlapping primitive sketches. The constraint_methods section lists common FreeCAD Sketcher.Constraint type strings and argument field shapes.",
                {},
                [],
                "sketch_geometry_method_catalog",
            ),
            CadToolSpec(
                "freecad_sketch_edit_geometry",
                "Edit Sketch Geometry",
                "Delete, move, toggle construction state, add external geometry, carbon-copy, and maintain internal/degenerated Sketcher geometry.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_edit_geometry",
            ),
            CadToolSpec(
                "freecad_sketch_external_projection",
                "Add Sketch External Projection",
                "Add FreeCAD 1.1 Sketcher External Projection references to a sketch from selected faces, edges, vertices, master sketches, or datum/support geometry. This is the named typed alias for `freecad_sketch_edit_geometry` operation `add_external` with `intersection=false`.",
                SKETCH_EXTERNAL_REFERENCE_PROPS,
                ["document_path", "sketch_name"],
                "sketch_external_projection",
            ),
            CadToolSpec(
                "freecad_sketch_external_intersection",
                "Add Sketch External Intersection",
                "Add FreeCAD 1.1 Sketcher External Intersection references to a sketch from selected faces, edges, vertices, master sketches, or datum/support geometry. This is the named typed alias for `freecad_sketch_edit_geometry` operation `add_external` with `intersection=true`.",
                SKETCH_EXTERNAL_REFERENCE_PROPS,
                ["document_path", "sketch_name"],
                "sketch_external_intersection",
            ),
            CadToolSpec(
                "freecad_sketch_edit_constraints",
                "Edit Sketch Constraints",
                "Delete, rename, set datum/driving/active/visibility/virtual-space state, validate, and auto-remove redundant Sketcher constraints.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_edit_constraints",
            ),
            CadToolSpec(
                "freecad_sketch_transform",
                "Transform Sketch Geometry",
                "Run headless Sketcher transform operations such as fillet, trim, extend, split, join, copy, move, symmetry, rectangular array, and B-spline edits. Trim is an edit/repair operation for existing geometry; for new parametric keyholes, slots, sockets, and reusable closed profiles prefer profile helpers or ordered arc/line loops with semantic constraints and validation.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_transform",
            ),
            CadToolSpec(
                "freecad_sketch_auto_constrain",
                "Auto Constrain Sketch",
                "Detect/apply missing Sketcher coincident, vertical/horizontal, equality constraints, run autoconstraint, and validate/clean constraints.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_auto_constrain",
            ),
            CadToolSpec(
                "freecad_sketch_validate",
                "Validate Sketch",
                "Solve and summarize native Sketcher geometry, constraints, solver diagnostics, missing constraints, open vertices, semantic groups such as tangent/equal chains, helper-intent report layers, and per-constraint errors. Use this to get native Sketcher evidence instead of inferring constraint state from screenshot colors. " + SKETCH_HELPER_LAYER_POLICY,
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "solve": {"type": "boolean"}, "detect_missing": {"type": "boolean"}, "include_geometry": {"type": "boolean", "description": "Include native geometry details such as type_id, construction flag, start/end/center/radius and B-spline poles/knots when available. Defaults true."}, "include_constraints": {"type": "boolean", "description": "Include constraint type, raw indices, resolved refs, names, values, driving/active state, and label metadata. Defaults true."}, "include_semantic_groups": {"type": "boolean", "description": "Include derived tangent pairs/chains, equal groups, PointOnObject, horizontal/vertical, symmetry, dimensional/radius constraints, construction geometry, and coincident pairs. Defaults true."}, "include_report_layers": {"type": "boolean", "description": "Include native_geometry, construction_geometry, constraint_graph, and helper_intent_inference layers. Defaults true."}, "include_constraint_errors": {"type": "boolean"}, "precision": {"type": "number"}, "angle_precision": {"type": "number"}, "include_construction": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_validate",
            ),
        ]
