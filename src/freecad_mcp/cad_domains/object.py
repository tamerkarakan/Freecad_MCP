"""Object inspection and mutation CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class ObjectCadToolService(CadDomainToolService):
    domain = "object"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_object_list", "List FreeCAD Objects", "List document objects.", {"document_path": {"type": "string"}}, ["document_path"], "object_list"),
            CadToolSpec("freecad_object_get", "Get FreeCAD Object", "Inspect one document object.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "include_properties": {"type": "boolean"}}, ["document_path", "object_name"], "object_get"),
            CadToolSpec("freecad_object_set_properties", "Set FreeCAD Object Properties", "Set simple object properties and save optionally.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "properties": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_name", "properties"], "object_set_properties"),
            CadToolSpec("freecad_object_delete", "Delete FreeCAD Objects", "Delete object(s) by name/label.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "object_delete"),
        ]
