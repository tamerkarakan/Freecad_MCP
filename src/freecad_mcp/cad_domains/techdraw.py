"""TechDraw CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class TechDrawCadToolService(CadDomainToolService):
    domain = "techdraw"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_techdraw_page_create", "Create TechDraw Page", "Create a headless TechDraw page with an optional SVG template.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "page_name": {"type": "string"}, "template_name": {"type": "string"}, "template_path": {"type": "string"}, "scale": {"type": "number"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "techdraw_page_create"),
            CadToolSpec("freecad_techdraw_view_create", "Create TechDraw Part View", "Create a TechDraw DrawViewPart on a page from source document objects.", {"document_path": {"type": "string"}, "page_name": {"type": "string"}, "source_objects": {"type": "array", "items": {"type": "string"}}, "view_name": {"type": "string"}, "direction": {"type": "array", "items": {"type": "number"}}, "x_direction": {"type": "array", "items": {"type": "number"}}, "scale": {"type": "number"}, "x": {"type": "number"}, "y": {"type": "number"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "page_name", "source_objects"], "techdraw_view_create"),
            CadToolSpec("freecad_techdraw_inspect", "Inspect TechDraw", "Inspect TechDraw pages and views in a document.", {"document_path": {"type": "string"}, "page_name": {"type": "string"}}, ["document_path"], "techdraw_inspect"),
            CadToolSpec("freecad_techdraw_page_export", "Export TechDraw Page", "Export a TechDraw page through headless TechDraw APIs. DXF is currently supported.", {"document_path": {"type": "string"}, "page_name": {"type": "string"}, "output_path": {"type": "string"}, "format": {"type": "string", "enum": ["dxf"]}, "overwrite": {"type": "boolean"}}, ["document_path", "page_name", "output_path"], "techdraw_page_export"),
        ]
