"""FEM CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class FemCadToolService(CadDomainToolService):
    domain = "fem"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_fem_analysis_create", "Create FEM Analysis", "Create a FEM analysis container.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "analysis_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "fem_analysis_create"),
            CadToolSpec("freecad_fem_material_create", "Create FEM Material", "Create a FEM solid material and add it to an analysis.", {"document_path": {"type": "string"}, "analysis_name": {"type": "string"}, "material_name": {"type": "string"}, "material": {"type": "object"}, "references": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "fem_material_create"),
            CadToolSpec("freecad_fem_constraint_create", "Create FEM Constraint", "Create a fixture-safe FEM fixed or force constraint and add it to an analysis.", {"document_path": {"type": "string"}, "analysis_name": {"type": "string"}, "constraint_type": {"type": "string", "enum": ["fixed", "force"]}, "constraint_name": {"type": "string"}, "references": {"type": "array", "items": {"type": "object"}}, "force": {"type": "string"}, "direction_reference": {"type": "object"}, "direction_vector": {"type": "array", "items": {"type": "number"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "fem_constraint_create"),
            CadToolSpec("freecad_fem_inspect", "Inspect FEM Analysis", "Inspect FEM analyses, materials, and constraints in a document.", {"document_path": {"type": "string"}}, ["document_path"], "fem_inspect"),
        ]
