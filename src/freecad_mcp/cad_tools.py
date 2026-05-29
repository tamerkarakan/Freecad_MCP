"""Typed CAD tools backed by process-per-call FreeCADCmd."""

from __future__ import annotations

from collections.abc import Iterable

from freecad_mcp.cad_domains import build_domain_services
from freecad_mcp.cad_tool_base import CAD_ACTION_SCRIPT, COMMON_RUNTIME_PROPS, CadCommandRunner, CadDomainToolService
from freecad_mcp.runtime_bridge import FreeCadDiscovery
from freecad_mcp.tooling import ToolDefinition


class CadToolService:
    """Aggregate typed CAD domain services behind the historical public API."""

    def __init__(
        self,
        discovery: FreeCadDiscovery | None = None,
        domain_services: Iterable[CadDomainToolService] | None = None,
    ):
        self.runner = CadCommandRunner(discovery=discovery)
        self.domain_services = list(domain_services) if domain_services is not None else build_domain_services(self.runner)

    def definitions(self) -> list[ToolDefinition]:
        definitions: list[ToolDefinition] = []
        for service in self.domain_services:
            definitions.extend(service.definitions())
        return definitions

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def domain_names(self) -> list[str]:
        return [service.domain for service in self.domain_services]
