"""PartDesign CAD tools."""

from __future__ import annotations

from typing import Any

from freecad_mcp.cad_tool_base import COMMON_RUNTIME_PROPS, CadDomainToolService, CadToolSpec
from freecad_mcp.tooling import JsonObject, ToolDefinition, ToolInputError


PIPE_MODE_ENUM = ["standard", "fixed", "frenet", "auxiliary", "binormal"]
PIPE_TRANSITION_ENUM = ["transformed", "right_corner", "round_corner"]
PIPE_TRANSFORMATION_ENUM = ["constant", "multisection", "linear", "s_shape", "interpolation"]

PIPE_PROPS = {
    "document_path": {"type": "string"},
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
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
}

DRESSUP_BASE_PROPS = {
    "document_path": {"type": "string"},
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
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
}

FILLET_PROPS = {
    **DRESSUP_BASE_PROPS,
    "radius": {"type": "number"},
    "use_all_edges": {"type": "boolean"},
    "fillet_name": {"type": "string"},
}

CHAMFER_PROPS = {
    **DRESSUP_BASE_PROPS,
    "distance": {"type": "number"},
    "size": {"type": "number"},
    "size2": {"type": "number"},
    "angle": {"type": "number"},
    "chamfer_type": {"type": "string", "enum": ["equal_distance", "two_distances", "distance_and_angle"]},
    "flip_direction": {"type": "boolean"},
    "use_all_edges": {"type": "boolean"},
    "chamfer_name": {"type": "string"},
}

THICKNESS_PROPS = {
    **DRESSUP_BASE_PROPS,
    "thickness": {"type": "number"},
    "value": {"type": "number"},
    "mode": {"type": "string", "enum": ["skin", "pipe", "recto_verso"]},
    "join": {"type": "string", "enum": ["arc", "intersection"]},
    "reversed": {"type": "boolean"},
    "intersection": {"type": "boolean"},
    "thickness_name": {"type": "string"},
}

DRAFT_PROPS = {
    **DRESSUP_BASE_PROPS,
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

TRANSFORM_BASE_PROPS = {
    "document_path": {"type": "string"},
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
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
}

LINEAR_PATTERN_PROPS = {
    **TRANSFORM_BASE_PROPS,
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

POLAR_PATTERN_PROPS = {
    **TRANSFORM_BASE_PROPS,
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

MIRRORED_PROPS = {
    **TRANSFORM_BASE_PROPS,
    "mirror_plane": {"type": "string"},
    "mirror_plane_name": {"type": "string"},
    "mirror_plane_object": {"type": "string"},
    "mirror_plane_subname": {"type": "string"},
    "mirrored_name": {"type": "string"},
    "mirror_name": {"type": "string"},
}

PROFILE_WORKFLOW_PROPS = {
    "document_path": {"type": "string"},
    "document_name": {"type": "string"},
    "body_name": {"type": "string"},
    "sketch_name": {"type": "string"},
    "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
    "attachment_object": {"type": "string"},
    "attachment_subname": {"type": "string"},
    "attachment_map_mode": {"type": "string"},
    "attachment_offset": {"type": "number"},
    "attachment_offset_vector": {"type": "array", "items": {"type": "number"}},
    "create_body_if_missing": {"type": "boolean"},
    "loops": {"type": "array", "items": {"type": "object"}},
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
    "feature_kind": {"type": "string", "enum": ["pad", "pocket", "revolution", "groove"], "default": "pad"},
    "feature_name": {"type": "string"},
    "result_name": {"type": "string"},
    "length": {"type": "number"},
    "length2": {"type": "number"},
    "midplane": {"type": "boolean"},
    "reversed": {"type": "boolean"},
    "reference_axis": {"type": "string", "enum": ["sketch_v_axis", "sketch_h_axis", "x_axis", "y_axis", "z_axis"]},
    "reference_axis_object": {"type": "string"},
    "reference_axis_subname": {"type": "string"},
    "mode": {"type": "string", "enum": ["angle", "through_all", "up_to_last", "up_to_first", "up_to_face", "two_angles"]},
    "angle": {"type": "number"},
    "angle2": {"type": "number"},
    "up_to_face_object": {"type": "string"},
    "up_to_face_subname": {"type": "string"},
    "fuse_order": {"type": "string", "enum": ["base_first", "feature_first"]},
    "require_solid": {"type": "boolean"},
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
}

SWEEP_WORKFLOW_PROPS = {
    "document_path": {"type": "string"},
    "document_name": {"type": "string"},
    "body_name": {"type": "string"},
    "feature_kind": {"type": "string", "enum": ["additive_pipe", "subtractive_pipe"], "default": "additive_pipe"},
    "profile_sketch_name": {"type": "string"},
    "profile_name": {"type": "string"},
    "profile": {"type": "object", "description": "Profile helper for freecad_sketch_add_profile, such as a circle."},
    "profile_loops": {"type": "array", "items": {"type": "object"}},
    "profile_attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
    "profile_attachment_object": {"type": "string"},
    "profile_attachment_subname": {"type": "string"},
    "profile_attachment_map_mode": {"type": "string"},
    "profile_attachment_offset": {"type": "number"},
    "profile_attachment_offset_vector": {"type": "array", "items": {"type": "number"}},
    "spine_sketch_name": {"type": "string"},
    "spine_name": {"type": "string"},
    "spine_geometry": {"type": "array", "items": {"type": "object"}},
    "spine_constraints": {"type": "array", "items": {"type": "object"}},
    "spine_attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
    "spine_attachment_object": {"type": "string"},
    "spine_attachment_subname": {"type": "string"},
    "spine_attachment_map_mode": {"type": "string"},
    "spine_attachment_offset": {"type": "number"},
    "spine_attachment_offset_vector": {"type": "array", "items": {"type": "number"}},
    "spine_subname": {"type": "string"},
    "spine_tangent": {"type": "boolean"},
    "sections": {"type": "array", "items": {"type": ["string", "object"]}},
    "section_names": {"type": "array", "items": {"type": "string"}},
    "orientation_mode": {"type": "string", "enum": PIPE_MODE_ENUM},
    "mode": {"type": "string", "enum": PIPE_MODE_ENUM},
    "transition": {"type": "string", "enum": PIPE_TRANSITION_ENUM},
    "transformation": {"type": "string", "enum": PIPE_TRANSFORMATION_ENUM},
    "scaling_mode": {"type": "string", "enum": PIPE_TRANSFORMATION_ENUM},
    "binormal": {"type": "array", "items": {"type": "number"}},
    "auxiliary_spine_name": {"type": "string"},
    "auxiliary_spine_subname": {"type": "string"},
    "auxiliary_spine_tangent": {"type": "boolean"},
    "auxiliary_curvilinear": {"type": "boolean"},
    "pipe_name": {"type": "string"},
    "result_name": {"type": "string"},
    "require_solid": {"type": "boolean"},
    "create_body_if_missing": {"type": "boolean"},
    "output_path": {"type": "string"},
    "overwrite": {"type": "boolean"},
    "save": {"type": "boolean"},
}

RUNTIME_ARG_KEYS = set(COMMON_RUNTIME_PROPS)


class PartDesignCadToolService(CadDomainToolService):
    domain = "partdesign"

    def definitions(self) -> list[ToolDefinition]:
        return [
            *super().definitions(),
            ToolDefinition(
                "freecad_partdesign_profile_feature_create",
                "Create PartDesign Profile Feature Recipe",
                "High-level recipe that creates a Body-attached pad-ready Sketcher profile, validates it, then creates Pad, Pocket, Revolution, or Groove. Pocket and Groove require document_path with an existing Body solid.",
                {"type": "object", "properties": {**PROFILE_WORKFLOW_PROPS, **COMMON_RUNTIME_PROPS}, "required": ["loops"]},
                self.profile_feature_create,
            ),
            ToolDefinition(
                "freecad_partdesign_sweep_feature_create",
                "Create PartDesign Sweep Feature Recipe",
                "High-level recipe that creates Body-attached profile and spine sketches, then creates an Additive/Subtractive Pipe sweep. Subtractive Pipe requires document_path with an existing Body solid.",
                {"type": "object", "properties": {**SWEEP_WORKFLOW_PROPS, **COMMON_RUNTIME_PROPS}, "required": ["spine_geometry"]},
                self.sweep_feature_create,
            ),
        ]

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_partdesign_body_create", "Create PartDesign Body", "Create or reuse a PartDesign Body with origin planes.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "body_name": {"type": "string"}, "create_body_if_missing": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "partdesign_body_create"),
            CadToolSpec("freecad_partdesign_datum_plane_create", "Create PartDesign Datum Plane", "Create a PartDesign datum plane inside a Body, attached to a Body origin plane or another support object with optional offset.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "body_name": {"type": "string"}, "create_body_if_missing": {"type": "boolean"}, "datum_plane_name": {"type": "string"}, "plane_name": {"type": "string"}, "result_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "attachment_object": {"type": "string"}, "attachment_subname": {"type": "string"}, "attachment_map_mode": {"type": "string"}, "attachment_offset": {"type": "number"}, "attachment_offset_vector": {"type": "array", "items": {"type": "number"}}, "require_valid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "partdesign_datum_plane_create"),
            CadToolSpec("freecad_partdesign_pad", "Create PartDesign Pad", "Create a PartDesign Pad from a Sketcher profile inside a Body, attaching the sketch to an origin plane when needed.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "pad_name": {"type": "string"}, "result_name": {"type": "string"}, "length": {"type": "number"}, "length2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_pad"),
            CadToolSpec("freecad_partdesign_pocket", "Create PartDesign Pocket", "Create a PartDesign Pocket that removes material from an existing Body solid using a Sketcher profile. The Body must already contain a solid feature such as a Pad.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "pocket_name": {"type": "string"}, "result_name": {"type": "string"}, "length": {"type": "number"}, "length2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_pocket"),
            CadToolSpec("freecad_partdesign_hole", "Create PartDesign Hole", "Create a plain PartDesign Hole from a Sketcher circle profile inside an existing Body solid.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "hole_name": {"type": "string"}, "result_name": {"type": "string"}, "diameter": {"type": "number"}, "depth": {"type": "number"}, "depth_type": {"type": "string", "enum": ["dimension", "through_all"]}, "drill_point": {"type": "string", "enum": ["flat", "angled"]}, "drill_point_angle": {"type": "number"}, "tapered": {"type": "boolean"}, "tapered_angle": {"type": "number"}, "hole_cut_type": {"type": "string", "enum": ["none", "counterbore", "countersink"]}, "hole_cut_diameter": {"type": "number"}, "hole_cut_depth": {"type": "number"}, "hole_cut_countersink_angle": {"type": "number"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name", "diameter"], "partdesign_hole"),
            CadToolSpec("freecad_partdesign_revolution", "Create PartDesign Revolution", "Create an additive PartDesign Revolution from a Sketcher profile around a sketch or document axis.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "revolution_name": {"type": "string"}, "result_name": {"type": "string"}, "reference_axis": {"type": "string", "enum": ["sketch_v_axis", "sketch_h_axis", "x_axis", "y_axis", "z_axis"]}, "reference_axis_object": {"type": "string"}, "reference_axis_subname": {"type": "string"}, "mode": {"type": "string", "enum": ["angle", "through_all", "up_to_last", "up_to_first", "up_to_face", "two_angles"]}, "angle": {"type": "number"}, "angle2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "up_to_face_object": {"type": "string"}, "up_to_face_subname": {"type": "string"}, "fuse_order": {"type": "string", "enum": ["base_first", "feature_first"]}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_revolution"),
            CadToolSpec("freecad_partdesign_groove", "Create PartDesign Groove", "Create a subtractive PartDesign Groove from a Sketcher profile around a sketch or document axis. The Body must already contain a solid feature such as a Pad.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "groove_name": {"type": "string"}, "result_name": {"type": "string"}, "reference_axis": {"type": "string", "enum": ["sketch_v_axis", "sketch_h_axis", "x_axis", "y_axis", "z_axis"]}, "reference_axis_object": {"type": "string"}, "reference_axis_subname": {"type": "string"}, "mode": {"type": "string", "enum": ["angle", "through_all", "up_to_first", "up_to_face", "two_angles"]}, "angle": {"type": "number"}, "angle2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "up_to_face_object": {"type": "string"}, "up_to_face_subname": {"type": "string"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_groove"),
            CadToolSpec("freecad_partdesign_additive_loft", "Create PartDesign Additive Loft", "Create an additive PartDesign Loft from a profile sketch and one or more section sketches inside a Body.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "profile_name": {"type": "string"}, "profile_sketch": {"type": "string"}, "sketch_name": {"type": "string"}, "profile_subname": {"type": "string"}, "profile_subnames": {"type": "array", "items": {"type": "string"}}, "sections": {"type": "array", "items": {"type": ["string", "object"]}}, "section_names": {"type": "array", "items": {"type": "string"}}, "loft_name": {"type": "string"}, "result_name": {"type": "string"}, "ruled": {"type": "boolean"}, "closed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "partdesign_additive_loft"),
            CadToolSpec("freecad_partdesign_subtractive_loft", "Create PartDesign Subtractive Loft", "Create a subtractive PartDesign Loft that removes material from an existing Body solid using a profile sketch and one or more section sketches.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "profile_name": {"type": "string"}, "profile_sketch": {"type": "string"}, "sketch_name": {"type": "string"}, "profile_subname": {"type": "string"}, "profile_subnames": {"type": "array", "items": {"type": "string"}}, "sections": {"type": "array", "items": {"type": ["string", "object"]}}, "section_names": {"type": "array", "items": {"type": "string"}}, "loft_name": {"type": "string"}, "result_name": {"type": "string"}, "ruled": {"type": "boolean"}, "closed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "partdesign_subtractive_loft"),
            CadToolSpec("freecad_partdesign_additive_pipe", "Create PartDesign Additive Pipe", "Create an additive PartDesign Pipe by sweeping a profile sketch along a spine/path sketch inside a Body.", dict(PIPE_PROPS), ["document_path"], "partdesign_additive_pipe"),
            CadToolSpec("freecad_partdesign_subtractive_pipe", "Create PartDesign Subtractive Pipe", "Create a subtractive PartDesign Pipe by sweeping a profile sketch along a spine/path sketch to remove material from an existing Body solid.", dict(PIPE_PROPS), ["document_path"], "partdesign_subtractive_pipe"),
            CadToolSpec("freecad_partdesign_fillet", "Create PartDesign Fillet", "Create a PartDesign Fillet dress-up on selected base edges/faces or all edges of an existing Body solid.", dict(FILLET_PROPS), ["document_path"], "partdesign_fillet"),
            CadToolSpec("freecad_partdesign_chamfer", "Create PartDesign Chamfer", "Create a PartDesign Chamfer dress-up on selected base edges/faces or all edges of an existing Body solid.", dict(CHAMFER_PROPS), ["document_path"], "partdesign_chamfer"),
            CadToolSpec("freecad_partdesign_thickness", "Create PartDesign Thickness", "Create a PartDesign Thickness dress-up from selected base faces of an existing Body solid.", dict(THICKNESS_PROPS), ["document_path"], "partdesign_thickness"),
            CadToolSpec("freecad_partdesign_draft", "Create PartDesign Draft", "Create a PartDesign Draft dress-up from selected base faces plus neutral-plane and pull-direction references.", dict(DRAFT_PROPS), ["document_path"], "partdesign_draft"),
            CadToolSpec("freecad_partdesign_linear_pattern", "Create PartDesign Linear Pattern", "Create a PartDesign LinearPattern transform from selected Body features or the whole Body shape.", dict(LINEAR_PATTERN_PROPS), ["document_path"], "partdesign_linear_pattern"),
            CadToolSpec("freecad_partdesign_polar_pattern", "Create PartDesign Polar Pattern", "Create a PartDesign PolarPattern transform from selected Body features or the whole Body shape.", dict(POLAR_PATTERN_PROPS), ["document_path"], "partdesign_polar_pattern"),
            CadToolSpec("freecad_partdesign_mirrored", "Create PartDesign Mirrored", "Create a PartDesign Mirrored transform from selected Body features or the whole Body shape.", dict(MIRRORED_PROPS), ["document_path"], "partdesign_mirrored"),
        ]

    def _with_runtime(self, args: JsonObject, action_args: JsonObject) -> JsonObject:
        merged = {key: args[key] for key in RUNTIME_ARG_KEYS if key in args}
        merged.update(action_args)
        return merged

    def _persistence_args(self, args: JsonObject, *, first_write: bool) -> JsonObject:
        if args.get("output_path"):
            return {"output_path": args["output_path"], "overwrite": bool(args.get("overwrite", False)) if first_write else True}
        return {"save": True}

    def _ensure_ok(self, result: JsonObject, step: str) -> JsonObject:
        payload = result.get("freecad")
        if not isinstance(payload, dict) or not payload.get("ok"):
            message = payload.get("error") if isinstance(payload, dict) else "missing FreeCAD payload"
            raise ToolInputError(f"{step} failed: {message}")
        return payload

    def _working_path(self, args: JsonObject, payload: JsonObject) -> str:
        path = payload.get("saved_path") or args.get("output_path") or args.get("document_path")
        if not isinstance(path, str) or not path:
            raise ToolInputError("document_path or output_path is required for multi-step PartDesign workflow tools")
        return path

    def profile_feature_create(self, args: JsonObject) -> JsonObject:
        if not args.get("document_path") and not args.get("output_path"):
            raise ToolInputError("document_path or output_path is required")
        feature_kind = str(args.get("feature_kind") or "pad")
        action_by_kind = {
            "pad": "partdesign_pad",
            "pocket": "partdesign_pocket",
            "revolution": "partdesign_revolution",
            "groove": "partdesign_groove",
        }
        name_key_by_kind = {
            "pad": "pad_name",
            "pocket": "pocket_name",
            "revolution": "revolution_name",
            "groove": "groove_name",
        }
        if feature_kind not in action_by_kind:
            raise ToolInputError("feature_kind must be one of pad, pocket, revolution, groove")
        if feature_kind in {"pocket", "groove"} and not args.get("document_path"):
            raise ToolInputError(f"{feature_kind} recipe requires document_path with an existing Body solid")

        body_name = str(args.get("body_name") or "Body")
        sketch_name = str(args.get("sketch_name") or f"{feature_kind.title()}ProfileSketch")
        profile_args: JsonObject = {
            "sketch_name": sketch_name,
            "body_name": body_name,
            "loops": args["loops"],
            "create_body_if_missing": args.get("create_body_if_missing", True),
            "attachment_plane": args.get("attachment_plane") or "XY",
            "require_valid": args.get("require_valid", True),
            "require_pad_ready": args.get("require_pad_ready", True),
        }
        for key in (
            "document_path",
            "document_name",
            "attachment_object",
            "attachment_subname",
            "attachment_map_mode",
            "attachment_offset",
            "attachment_offset_vector",
            "lock_mode",
            "endpoint_tolerance",
            "required_segment_types",
            "required_curve_types",
            "allowed_segment_types",
            "minimum_curve_segments",
            "forbid_polyline_fallback",
            "forbid_all_line_loops",
            "require_fully_constrained",
            "forbid_isolated_points",
            "forbid_branch_points",
            "forbid_micro_offsets",
            "micro_offset_tolerance",
        ):
            if key in args:
                profile_args[key] = args[key]
        profile_args.update(self._persistence_args(args, first_write=True))
        profile_result = self.runner.run("sketch_profile_create", self._with_runtime(args, profile_args), ["loops"])
        profile_payload = self._ensure_ok(profile_result, "profile sketch creation")
        working_path = self._working_path(args, profile_payload)

        feature_args: JsonObject = {
            "document_path": working_path,
            "body_name": body_name,
            "sketch_name": sketch_name,
            "attachment_plane": args.get("attachment_plane") or "XY",
            "create_body_if_missing": args.get("create_body_if_missing", True),
            "require_solid": args.get("require_solid", True),
        }
        if args.get("feature_name"):
            feature_args[name_key_by_kind[feature_kind]] = args["feature_name"]
        for key in (
            "result_name",
            "length",
            "length2",
            "midplane",
            "reversed",
            "reference_axis",
            "reference_axis_object",
            "reference_axis_subname",
            "mode",
            "angle",
            "angle2",
            "up_to_face_object",
            "up_to_face_subname",
            "fuse_order",
        ):
            if key in args:
                feature_args[key] = args[key]
        feature_args.update(self._persistence_args(args, first_write=False))
        feature_result = self.runner.run(action_by_kind[feature_kind], self._with_runtime(args, feature_args), ["document_path", "sketch_name"])
        feature_payload = self._ensure_ok(feature_result, feature_kind)
        return {
            "discovery": feature_result.get("discovery"),
            "execution": feature_result.get("execution"),
            "freecad": feature_payload,
            "workflow": {
                "ok": True,
                "kind": "partdesign_profile_feature",
                "feature_kind": feature_kind,
                "body_name": body_name,
                "sketch_name": sketch_name,
                "document_path": feature_payload.get("saved_path") or working_path,
                "steps": ["sketch_profile_create", action_by_kind[feature_kind]],
            },
            "steps": {
                "profile": profile_result,
                "feature": feature_result,
            },
        }

    def _create_attached_sketch(self, args: JsonObject, *, name: str, plane: str, prefix: str, working_path: str | None) -> tuple[JsonObject, str]:
        sketch_args: JsonObject = {
            "sketch_name": name,
            "body_name": str(args.get("body_name") or "Body"),
            "attachment_plane": plane,
            "create_body_if_missing": args.get("create_body_if_missing", True),
        }
        if working_path:
            sketch_args["document_path"] = working_path
        elif args.get("document_path"):
            sketch_args["document_path"] = args["document_path"]
        elif args.get("document_name"):
            sketch_args["document_name"] = args["document_name"]
        for source, target in (
            (f"{prefix}_attachment_object", "attachment_object"),
            (f"{prefix}_attachment_subname", "attachment_subname"),
            (f"{prefix}_attachment_map_mode", "attachment_map_mode"),
            (f"{prefix}_attachment_offset", "attachment_offset"),
            (f"{prefix}_attachment_offset_vector", "attachment_offset_vector"),
        ):
            if source in args:
                sketch_args[target] = args[source]
        sketch_args.update(self._persistence_args(args, first_write=working_path is None and not args.get("document_path")))
        result = self.runner.run("sketch_create", self._with_runtime(args, sketch_args), [])
        payload = self._ensure_ok(result, f"{prefix} sketch creation")
        return result, self._working_path(args, payload)

    def sweep_feature_create(self, args: JsonObject) -> JsonObject:
        if not args.get("document_path") and not args.get("output_path"):
            raise ToolInputError("document_path or output_path is required")
        feature_kind = str(args.get("feature_kind") or "additive_pipe")
        action_by_kind = {"additive_pipe": "partdesign_additive_pipe", "subtractive_pipe": "partdesign_subtractive_pipe"}
        if feature_kind not in action_by_kind:
            raise ToolInputError("feature_kind must be additive_pipe or subtractive_pipe")
        if feature_kind == "subtractive_pipe" and not args.get("document_path"):
            raise ToolInputError("subtractive_pipe recipe requires document_path with an existing Body solid")
        if not args.get("profile") and not args.get("profile_loops"):
            raise ToolInputError("profile or profile_loops is required")

        body_name = str(args.get("body_name") or "Body")
        profile_name = str(args.get("profile_sketch_name") or args.get("profile_name") or "SweepProfileSketch")
        spine_name = str(args.get("spine_sketch_name") or args.get("spine_name") or "SweepSpineSketch")
        steps: dict[str, Any] = {}
        working_path = args.get("document_path")

        if args.get("profile_loops"):
            profile_args: JsonObject = {
                "sketch_name": profile_name,
                "body_name": body_name,
                "loops": args["profile_loops"],
                "attachment_plane": args.get("profile_attachment_plane") or "XY",
                "create_body_if_missing": args.get("create_body_if_missing", True),
                "require_valid": True,
                "require_pad_ready": True,
            }
            if working_path:
                profile_args["document_path"] = working_path
            elif args.get("document_name"):
                profile_args["document_name"] = args["document_name"]
            for source, target in (
                ("profile_attachment_object", "attachment_object"),
                ("profile_attachment_subname", "attachment_subname"),
                ("profile_attachment_map_mode", "attachment_map_mode"),
                ("profile_attachment_offset", "attachment_offset"),
                ("profile_attachment_offset_vector", "attachment_offset_vector"),
            ):
                if source in args:
                    profile_args[target] = args[source]
            profile_args.update(self._persistence_args(args, first_write=working_path is None))
            profile_result = self.runner.run("sketch_profile_create", self._with_runtime(args, profile_args), ["loops"])
            profile_payload = self._ensure_ok(profile_result, "sweep profile creation")
            working_path = self._working_path(args, profile_payload)
            steps["profile"] = profile_result
        else:
            profile_sketch_result, working_path = self._create_attached_sketch(
                args,
                name=profile_name,
                plane=str(args.get("profile_attachment_plane") or "XY"),
                prefix="profile",
                working_path=working_path,
            )
            steps["profile_sketch"] = profile_sketch_result
            profile_add_args = {
                "document_path": working_path,
                "sketch_name": profile_name,
                "profile": args["profile"],
                **self._persistence_args(args, first_write=False),
            }
            profile_result = self.runner.run("sketch_add_profile", self._with_runtime(args, profile_add_args), ["document_path", "sketch_name", "profile"])
            self._ensure_ok(profile_result, "sweep profile helper")
            steps["profile"] = profile_result

        spine_sketch_result, working_path = self._create_attached_sketch(
            args,
            name=spine_name,
            plane=str(args.get("spine_attachment_plane") or "XZ"),
            prefix="spine",
            working_path=working_path,
        )
        steps["spine_sketch"] = spine_sketch_result
        spine_geometry_args = {
            "document_path": working_path,
            "sketch_name": spine_name,
            "geometry": args["spine_geometry"],
            **self._persistence_args(args, first_write=False),
        }
        spine_geometry_result = self.runner.run("sketch_add_geometry", self._with_runtime(args, spine_geometry_args), ["document_path", "sketch_name", "geometry"])
        self._ensure_ok(spine_geometry_result, "sweep spine geometry")
        steps["spine_geometry"] = spine_geometry_result
        if args.get("spine_constraints"):
            spine_constraints_args = {
                "document_path": working_path,
                "sketch_name": spine_name,
                "constraints": args["spine_constraints"],
                **self._persistence_args(args, first_write=False),
            }
            spine_constraints_result = self.runner.run(
                "sketch_add_constraint",
                self._with_runtime(args, spine_constraints_args),
                ["document_path", "sketch_name", "constraints"],
            )
            self._ensure_ok(spine_constraints_result, "sweep spine constraints")
            steps["spine_constraints"] = spine_constraints_result

        pipe_args: JsonObject = {
            "document_path": working_path,
            "body_name": body_name,
            "profile_name": profile_name,
            "spine_name": spine_name,
            "require_solid": args.get("require_solid", True),
        }
        for key in (
            "spine_subname",
            "spine_tangent",
            "sections",
            "section_names",
            "orientation_mode",
            "mode",
            "transition",
            "transformation",
            "scaling_mode",
            "binormal",
            "auxiliary_spine_name",
            "auxiliary_spine_subname",
            "auxiliary_spine_tangent",
            "auxiliary_curvilinear",
            "pipe_name",
            "result_name",
        ):
            if key in args:
                pipe_args[key] = args[key]
        pipe_args.update(self._persistence_args(args, first_write=False))
        pipe_result = self.runner.run(action_by_kind[feature_kind], self._with_runtime(args, pipe_args), ["document_path"])
        pipe_payload = self._ensure_ok(pipe_result, feature_kind)
        steps["feature"] = pipe_result
        return {
            "discovery": pipe_result.get("discovery"),
            "execution": pipe_result.get("execution"),
            "freecad": pipe_payload,
            "workflow": {
                "ok": True,
                "kind": "partdesign_sweep_feature",
                "feature_kind": feature_kind,
                "body_name": body_name,
                "profile_name": profile_name,
                "spine_name": spine_name,
                "document_path": pipe_payload.get("saved_path") or working_path,
                "steps": list(steps),
            },
            "steps": steps,
        }
