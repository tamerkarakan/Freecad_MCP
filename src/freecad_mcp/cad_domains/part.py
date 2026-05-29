"""Part workbench CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class PartCadToolService(CadDomainToolService):
    domain = "part"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_part_create_primitive", "Create Part Primitive", "Create a Part primitive.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "primitive": {"type": "string", "enum": ["box", "cylinder", "sphere", "cone", "torus"]}, "object_name": {"type": "string"}, "properties": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "part_create_primitive"),
            CadToolSpec("freecad_part_boolean", "Part Boolean", "Fuse/cut/common Part shapes.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "operation": {"type": "string", "enum": ["fuse", "cut", "common"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_names"], "part_boolean"),
            CadToolSpec("freecad_part_extrude", "Part Extrude", "Extrude a source shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "vector": {"type": "array", "items": {"type": "number"}}, "extrude_mode": {"type": "string", "enum": ["auto", "shape", "feature"]}, "solid": {"type": "boolean"}, "symmetric": {"type": "boolean"}, "length_fwd": {"type": "number"}, "length_rev": {"type": "number"}, "taper_angle": {"type": "number", "description": "Forward taper angle in degrees."}, "taper_angle_rev": {"type": "number", "description": "Reverse taper angle in degrees."}, "reversed": {"type": "boolean"}, "dir_mode": {"type": "string", "enum": ["Custom", "Normal"]}, "face_maker_mode": {"type": "string", "enum": ["Simple", "Cheese", "Extrusion", "Bullseye"]}, "inner_wire_taper": {"type": "string", "enum": ["Inverted", "SameAsOuter"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object"], "part_extrude"),
            CadToolSpec("freecad_part_revolve", "Part Revolve", "Revolve a source shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "base": {"type": "array", "items": {"type": "number"}}, "axis": {"type": "array", "items": {"type": "number"}}, "angle": {"type": "number"}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object"], "part_revolve"),
            CadToolSpec("freecad_part_fillet", "Part Fillet", "Create a filleted copy of a shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "radius": {"type": "number"}, "edge_indices": {"type": "array", "items": {"type": "integer"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object", "radius"], "part_fillet"),
            CadToolSpec("freecad_part_chamfer", "Part Chamfer", "Create a chamfered copy of a shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "distance": {"type": "number"}, "edge_indices": {"type": "array", "items": {"type": "integer"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object", "distance"], "part_chamfer"),
            CadToolSpec("freecad_part_check_geometry", "Check Part Geometry", "Run shape validity checks.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "run_bop_check": {"type": "boolean"}}, ["document_path"], "part_check_geometry"),
        ]
