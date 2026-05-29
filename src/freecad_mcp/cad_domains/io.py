"""Import/export CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class IoCadToolService(CadDomainToolService):
    domain = "io"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_import_file", "Import File", "Import a CAD/mesh file into a document.", {"input_path": {"type": "string"}, "document_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["input_path"], "import_file"),
            CadToolSpec("freecad_export_file", "Export File", "Export selected/all objects from a document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "export_file"),
            CadToolSpec("freecad_supported_formats", "Supported Formats", "Return common import/export formats.", {}, [], "supported_formats"),
        ]
