"""Sketcher CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class SketchCadToolService(CadDomainToolService):
    domain = "sketcher"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_sketch_create", "Create Sketch", "Create a Sketcher object, optionally inside a PartDesign Body attached to XY/XZ/YZ origin plane or a datum/support object.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "body_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "attachment_object": {"type": "string"}, "attachment_subname": {"type": "string"}, "attachment_map_mode": {"type": "string"}, "attachment_offset": {"type": "number"}, "attachment_offset_vector": {"type": "array", "items": {"type": "number"}}, "create_body_if_missing": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "sketch_create"),
            CadToolSpec(
                "freecad_sketch_add_geometry",
                "Add Sketch Geometry",
                "Add point, line, circle, arc, ellipse, conic arc, B-spline, or polyline geometry to a sketch.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "geometry": {"type": "array", "items": {"type": "object"}}, "connect_sequence": {"type": "boolean", "description": "Add Coincident constraints between adjacent endpoint-capable geometry in the submitted order."}, "close_sequence": {"type": "boolean", "description": "Also add a Coincident constraint from the last endpoint-capable geometry back to the first."}, "require_closed": {"type": "boolean", "description": "Fail before saving if the resulting sequence still has open vertices."}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "geometry"],
                "sketch_add_geometry",
            ),
            CadToolSpec(
                "freecad_sketch_add_constraint",
                "Add Sketch Constraint",
                "Add raw or named Sketcher constraints with optional metadata such as datum, driving, active, visibility, and label placement.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "constraints"],
                "sketch_add_constraint",
            ),
            CadToolSpec(
                "freecad_sketch_add_profile",
                "Add Sketch Profile",
                "Add common closed/open Sketcher profiles such as rectangle variants, named/arbitrary regular polygons, circle, polyline, and straight/oriented/arc slots.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "profile": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "profile"],
                "sketch_add_profile",
            ),
            CadToolSpec(
                "freecad_sketch_profile_create",
                "Create Sketch Profile",
                "Create loop-based pad-ready Sketcher profiles from ordered line/arc/B-spline segments with endpoint continuity and curve-preservation guards, optionally attached inside a PartDesign Body.",
                {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "body_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "attachment_object": {"type": "string"}, "attachment_subname": {"type": "string"}, "attachment_map_mode": {"type": "string"}, "attachment_offset": {"type": "number"}, "attachment_offset_vector": {"type": "array", "items": {"type": "number"}}, "create_body_if_missing": {"type": "boolean"}, "loops": {"type": "array", "items": {"type": "object"}}, "replace_existing": {"type": "boolean"}, "lock_mode": {"type": "string", "enum": ["none", "block"]}, "endpoint_tolerance": {"type": "number"}, "required_segment_types": {"type": "array", "items": {"type": "string"}}, "required_curve_types": {"type": "array", "items": {"type": "string"}}, "allowed_segment_types": {"type": "array", "items": {"type": "string"}}, "minimum_curve_segments": {"type": "integer"}, "forbid_polyline_fallback": {"type": "boolean"}, "forbid_all_line_loops": {"type": "boolean"}, "require_valid": {"type": "boolean"}, "require_pad_ready": {"type": "boolean"}, "require_fully_constrained": {"type": "boolean"}, "forbid_isolated_points": {"type": "boolean"}, "forbid_branch_points": {"type": "boolean"}, "forbid_micro_offsets": {"type": "boolean"}, "micro_offset_tolerance": {"type": "number"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["loops"],
                "sketch_profile_create",
            ),
            CadToolSpec(
                "freecad_sketch_profile_validate",
                "Validate Sketch Profile",
                "Validate whether a Sketcher object is pad-ready and whether its native geometry types match declared curve intent.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "require_pad_ready": {"type": "boolean"}, "require_fully_constrained": {"type": "boolean"}, "forbid_isolated_points": {"type": "boolean"}, "forbid_branch_points": {"type": "boolean"}, "forbid_micro_offsets": {"type": "boolean"}, "micro_offset_tolerance": {"type": "number"}, "endpoint_key_precision": {"type": "integer"}, "include_construction": {"type": "boolean"}, "required_segment_types": {"type": "array", "items": {"type": "string"}}, "required_curve_types": {"type": "array", "items": {"type": "string"}}, "minimum_curve_segments": {"type": "integer"}, "forbid_all_line_loops": {"type": "boolean"}, "forbid_polyline_fallback": {"type": "boolean"}, "forbid_intent_mismatch": {"type": "boolean"}, "expected_geometry": {"type": "array", "items": {"type": "object"}}},
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
                "Return the supported typed creation methods for Sketcher geometry, profiles, transform-generated geometry, and analysis tools.",
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
                "Run headless Sketcher transform operations such as fillet, trim, extend, split, join, copy, move, symmetry, rectangular array, and B-spline edits.",
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
                "Solve and summarize sketch geometry, constraints, solver diagnostics, missing constraints, open vertices, and per-constraint errors.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "solve": {"type": "boolean"}, "detect_missing": {"type": "boolean"}, "include_constraint_errors": {"type": "boolean"}, "precision": {"type": "number"}, "angle_precision": {"type": "number"}, "include_construction": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_validate",
            ),
        ]
