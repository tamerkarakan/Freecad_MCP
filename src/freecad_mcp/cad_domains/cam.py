"""CAM CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class CamCadToolService(CadDomainToolService):
    domain = "cam"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_cam_path_create", "Create CAM Path", "Create a simple CAM Path::Feature from explicit G-code command specs.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "path_name": {"type": "string"}, "commands": {"type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "object"}]}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["commands"], "cam_path_create"),
            CadToolSpec("freecad_cam_path_inspect", "Inspect CAM Path", "Inspect CAM Path::Feature objects and command summaries.", {"document_path": {"type": "string"}, "path_name": {"type": "string"}}, ["document_path"], "cam_path_inspect"),
            CadToolSpec("freecad_cam_path_export", "Export CAM Path G-code", "Export a CAM Path::Feature to raw G-code without invoking a machine postprocessor.", {"document_path": {"type": "string"}, "path_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["document_path", "path_name", "output_path"], "cam_path_export"),
        ]
