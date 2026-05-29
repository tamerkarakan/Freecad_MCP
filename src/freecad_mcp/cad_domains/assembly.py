"""Assembly CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class AssemblyCadToolService(CadDomainToolService):
    domain = "assembly"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec("freecad_assembly_create", "Create Assembly", "Create an Assembly object.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "assembly_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "assembly_create"),
            CadToolSpec("freecad_assembly_insert", "Insert Assembly Link", "Insert an existing object into an assembly as an App::Link.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "object_name": {"type": "string"}, "link_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name", "object_name"], "assembly_insert"),
            CadToolSpec("freecad_assembly_create_joint", "Create Assembly Joint", "Create a native Assembly JointObject proxy under an assembly joint group.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "joint_type": {"type": "string", "enum": ["Fixed", "Revolute", "Cylindrical", "Slider", "Ball", "Distance", "Parallel", "Perpendicular", "Angle", "RackPinion", "Screw", "Gears", "Belt"]}, "joint_name": {"type": "string"}, "references": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name"], "assembly_create_joint"),
            CadToolSpec("freecad_assembly_solve", "Solve Assembly", "Recompute an assembly document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "assembly_solve"),
            CadToolSpec("freecad_assembly_bom", "Assembly BOM", "Return a simple assembly bill of materials.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}}, ["document_path"], "assembly_bom"),
        ]
