"""Document lifecycle CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class DocumentCadToolService(CadDomainToolService):
    domain = "document"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_document_new", "Create FreeCAD Document", "Create a new FreeCAD document.", {"document_name": {"type": "string"}, "label": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "document_new"),
            CadToolSpec("freecad_document_open", "Open FreeCAD Document", "Open a FreeCAD document and return a summary.", {"document_path": {"type": "string"}}, ["document_path"], "document_open"),
            CadToolSpec("freecad_document_save", "Save FreeCAD Document", "Open and save a FreeCAD document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["document_path"], "document_save"),
            CadToolSpec("freecad_document_recompute", "Recompute FreeCAD Document", "Open/recompute a document and optionally save it.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "document_recompute"),
            CadToolSpec("freecad_document_export", "Export FreeCAD Document", "Export selected or all document objects.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "document_export"),
        ]
