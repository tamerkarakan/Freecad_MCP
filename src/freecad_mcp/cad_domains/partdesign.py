"""PartDesign CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


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


class PartDesignCadToolService(CadDomainToolService):
    domain = "partdesign"

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
        ]
