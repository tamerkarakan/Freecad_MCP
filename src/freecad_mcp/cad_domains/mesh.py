"""Mesh CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class MeshCadToolService(CadDomainToolService):
    domain = "mesh"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_mesh_import", "Import Mesh", "Import a mesh file into a document.", {"input_path": {"type": "string"}, "document_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["input_path"], "mesh_import"),
            CadToolSpec("freecad_mesh_export", "Export Mesh", "Export mesh objects.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "mesh_export"),
            CadToolSpec("freecad_mesh_evaluate", "Evaluate Mesh", "Summarize mesh object health.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}}, ["document_path"], "mesh_evaluate"),
            CadToolSpec("freecad_mesh_repair", "Repair Mesh", "Run conservative mesh repair actions.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "actions": {"type": "array", "items": {"type": "string", "enum": ["harmonize_normals", "remove_duplicated_points"]}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "mesh_repair"),
            CadToolSpec("freecad_mesh_boolean", "Mesh Boolean", "Run mesh boolean operation when supported by FreeCAD build.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "operation": {"type": "string", "enum": ["union", "difference", "intersection"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_names"], "mesh_boolean"),
        ]
