"""Product-facing module selection for the FreeCAD MCP tool surface."""

from __future__ import annotations

import os
from dataclasses import dataclass


MODULE_ENV = "FREECAD_MCP_MODULES"

HIDDEN_MCP_TOOL_PREFIXES: tuple[str, ...] = (
    "freecad_part_",
    "freecad_worker_part_",
)


MODULE_ALIASES: dict[str, set[str]] = {
    "all": {"all"},
    "default": {"all"},
    "dev": {"all"},
    "developer": {"all"},
    "local-dev": {"all"},
    "free": {"core", "headless"},
    "pro": {"core", "headless", "sketcher", "partdesign", "mesh", "assembly", "gui"},
    "studio": {"core", "headless", "sketcher", "partdesign", "mesh", "assembly", "gui", "techdraw", "cam", "fem", "worker"},
    "team": {"core", "headless", "sketcher", "partdesign", "mesh", "assembly", "gui", "techdraw", "cam", "fem", "worker", "developer"},
    "source": {"developer"},
    "source-intelligence": {"developer"},
}


@dataclass(frozen=True)
class ModuleSelection:
    requested: tuple[str, ...]
    expanded: frozenset[str]

    @property
    def includes_all(self) -> bool:
        return "all" in self.expanded

    def allows(self, tool_name: str) -> bool:
        if self.includes_all:
            return True
        modules = tool_modules(tool_name)
        if "worker" in modules and "worker" not in self.expanded:
            return False
        return bool(modules & self.expanded)

    def to_dict(self) -> dict[str, object]:
        return {
            "env": MODULE_ENV,
            "requested": list(self.requested),
            "expanded": sorted(self.expanded),
            "includes_all": self.includes_all,
        }


def parse_module_selection(value: str | None = None) -> ModuleSelection:
    raw = value if value is not None else os.environ.get(MODULE_ENV)
    requested = tuple(part.strip().lower() for part in (raw or "all").replace(";", ",").split(",") if part.strip())
    if not requested:
        requested = ("all",)
    expanded: set[str] = set()
    for item in requested:
        expanded.update(MODULE_ALIASES.get(item, {item}))
    return ModuleSelection(requested=requested, expanded=frozenset(expanded))


def is_hidden_mcp_tool(tool_name: str) -> bool:
    """Return true for implemented tools that are intentionally not advertised."""
    return any(tool_name.startswith(prefix) for prefix in HIDDEN_MCP_TOOL_PREFIXES)


def tool_modules(tool_name: str) -> set[str]:
    modules: set[str] = set()

    if tool_name.startswith("freecad_command_"):
        modules.update({"core", "developer"})
    if tool_name.startswith("freecad_source_"):
        modules.add("developer")
    if tool_name == "freecad_session_status":
        modules.update({"core", "headless"})
    if tool_name == "freecad_python_exec":
        modules.add("unsafe")

    if tool_name.startswith("freecad_gui_"):
        modules.add("gui")

    if tool_name.startswith("freecad_session_") and tool_name != "freecad_session_status":
        modules.add("worker")
    if tool_name.startswith("freecad_worker_"):
        modules.add("worker")

    if tool_name.startswith("freecad_document_") or tool_name.startswith("freecad_object_"):
        modules.add("headless")
    if tool_name.startswith("freecad_geometry_"):
        modules.add("headless")
    if tool_name.startswith("freecad_spreadsheet_"):
        modules.add("headless")
    if tool_name in {"freecad_import_file", "freecad_export_file"}:
        modules.add("headless")
    if tool_name.startswith("freecad_part_"):
        modules.add("headless")

    if tool_name.startswith("freecad_sketch_") or tool_name == "freecad_curve_fit_analyze":
        modules.add("sketcher")
    if tool_name.startswith("freecad_partdesign_"):
        modules.add("partdesign")
    if tool_name.startswith("freecad_mesh_"):
        modules.add("mesh")
    if tool_name.startswith("freecad_assembly_"):
        modules.add("assembly")
    if tool_name.startswith("freecad_techdraw_"):
        modules.add("techdraw")
    if tool_name.startswith("freecad_cam_"):
        modules.add("cam")
    if tool_name.startswith("freecad_fem_"):
        modules.add("fem")

    if tool_name.startswith("freecad_worker_sketch_"):
        modules.add("sketcher")
    if tool_name.startswith("freecad_worker_partdesign_"):
        modules.add("partdesign")
    if tool_name.startswith("freecad_worker_mesh_"):
        modules.add("mesh")
    if tool_name.startswith("freecad_worker_assembly_"):
        modules.add("assembly")
    if tool_name.startswith("freecad_worker_part_"):
        modules.add("headless")
    if tool_name.startswith("freecad_worker_geometry_"):
        modules.add("headless")
    if tool_name.startswith("freecad_worker_document_") or tool_name.startswith("freecad_worker_object_"):
        modules.add("headless")

    return modules or {"core"}
