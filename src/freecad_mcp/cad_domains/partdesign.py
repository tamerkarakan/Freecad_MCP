"""PartDesign CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class PartDesignCadToolService(CadDomainToolService):
    domain = "partdesign"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_partdesign_body_create", "Create PartDesign Body", "Create or reuse a PartDesign Body with origin planes.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "body_name": {"type": "string"}, "create_body_if_missing": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "partdesign_body_create"),
            CadToolSpec("freecad_partdesign_pad", "Create PartDesign Pad", "Create a PartDesign Pad from a Sketcher profile inside a Body, attaching the sketch to an origin plane when needed.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "pad_name": {"type": "string"}, "result_name": {"type": "string"}, "length": {"type": "number"}, "length2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_pad"),
            CadToolSpec("freecad_partdesign_pocket", "Create PartDesign Pocket", "Create a PartDesign Pocket that removes material from an existing Body solid using a Sketcher profile. The Body must already contain a solid feature such as a Pad.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "pocket_name": {"type": "string"}, "result_name": {"type": "string"}, "length": {"type": "number"}, "length2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_pocket"),
        ]
