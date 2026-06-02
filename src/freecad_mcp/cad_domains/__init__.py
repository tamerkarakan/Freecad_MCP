"""Domain services for typed process-per-call FreeCADCmd tools."""

from __future__ import annotations

from freecad_mcp.cad_domains.assembly import AssemblyCadToolService
from freecad_mcp.cad_domains.cam import CamCadToolService
from freecad_mcp.cad_domains.document import DocumentCadToolService
from freecad_mcp.cad_domains.fem import FemCadToolService
from freecad_mcp.cad_domains.io import IoCadToolService
from freecad_mcp.cad_domains.mesh import MeshCadToolService
from freecad_mcp.cad_domains.object import ObjectCadToolService
from freecad_mcp.cad_domains.parameters import ParametersCadToolService
from freecad_mcp.cad_domains.part import PartCadToolService
from freecad_mcp.cad_domains.partdesign import PartDesignCadToolService
from freecad_mcp.cad_domains.sketch import SketchCadToolService
from freecad_mcp.cad_domains.techdraw import TechDrawCadToolService
from freecad_mcp.cad_tool_base import CadCommandRunner, CadDomainToolService


CAD_DOMAIN_SERVICE_TYPES: tuple[type[CadDomainToolService], ...] = (
    DocumentCadToolService,
    ObjectCadToolService,
    ParametersCadToolService,
    PartCadToolService,
    PartDesignCadToolService,
    SketchCadToolService,
    IoCadToolService,
    MeshCadToolService,
    AssemblyCadToolService,
    TechDrawCadToolService,
    CamCadToolService,
    FemCadToolService,
)


def build_domain_services(runner: CadCommandRunner) -> list[CadDomainToolService]:
    return [service_type(runner) for service_type in CAD_DOMAIN_SERVICE_TYPES]
