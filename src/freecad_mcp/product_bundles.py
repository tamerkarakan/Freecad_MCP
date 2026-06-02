"""Sellable product bundle descriptors for the FreeCAD MCP surface."""

from __future__ import annotations

from dataclasses import dataclass

from freecad_mcp.module_registry import MODULE_ENV, parse_module_selection


@dataclass(frozen=True)
class ProductBundle:
    key: str
    title: str
    profile: str
    kind: str
    audience: str
    position: str
    limits: str
    upgrade_to: str | None = None

    def to_dict(self) -> dict[str, object]:
        selection = parse_module_selection(self.profile)
        return {
            "key": self.key,
            "title": self.title,
            "profile": self.profile,
            "kind": self.kind,
            "env": {MODULE_ENV: self.profile},
            "modules": sorted(selection.expanded),
            "audience": self.audience,
            "position": self.position,
            "limits": self.limits,
            "upgrade_to": self.upgrade_to,
            "includes_unsafe": "unsafe" in selection.expanded or selection.includes_all,
        }


PRODUCT_BUNDLES: tuple[ProductBundle, ...] = (
    ProductBundle(
        key="free",
        title="FreeCAD MCP Free",
        profile="free",
        kind="base",
        audience="Users who want local file-based FreeCAD automation from ChatGPT, Codex, or Claude.",
        position="Static command inventory, runtime discovery, and process-per-call document/object/Part/parameter operations.",
        limits="No GUI attach, no Sketcher/PartDesign premium flow, no worker sessions, no source-code intelligence, no unsafe Python exec.",
        upgrade_to="pro",
    ),
    ProductBundle(
        key="pro",
        title="FreeCAD MCP Pro",
        profile="pro",
        kind="paid",
        audience="Design users who need Sketcher, PartDesign, mesh, assembly, and live GUI selection workflows.",
        position="Adds GUI attach plus Sketcher dimension, PartDesign datum/feature, mesh, and Assembly typed tools.",
        limits="No persistent worker sessions, TechDraw, CAM, FEM, source-code intelligence, or unsafe Python exec.",
        upgrade_to="studio",
    ),
    ProductBundle(
        key="studio",
        title="FreeCAD MCP Studio",
        profile="studio",
        kind="paid",
        audience="Power users and small studios that need persistent sessions and advanced workbench coverage.",
        position="Adds persistent FreeCADCmd worker sessions plus TechDraw, CAM, and FEM first slices.",
        limits="No source-code intelligence and no unsafe Python exec.",
        upgrade_to="team",
    ),
    ProductBundle(
        key="team",
        title="FreeCAD MCP Team",
        profile="team",
        kind="paid",
        audience="Teams building or auditing FreeCAD automation who need source-backed implementation evidence.",
        position="Studio surface plus source-intelligence tools for implementation research and support.",
        limits="No unsafe Python exec by default.",
        upgrade_to=None,
    ),
    ProductBundle(
        key="source",
        title="Source Intelligence Add-on",
        profile="source",
        kind="add-on",
        audience="Maintainers and support engineers who need command/source lookup without mutation tools.",
        position="Command inventory plus source search/open/symbol index.",
        limits="No document mutation, no GUI attach, no worker sessions, no unsafe Python exec.",
        upgrade_to=None,
    ),
    ProductBundle(
        key="unsafe",
        title="Unsafe Python Exec Add-on",
        profile="unsafe",
        kind="add-on",
        audience="Trusted local developers who explicitly need raw FreeCADCmd Python execution.",
        position="Exposes only the broad `freecad_python_exec` escape hatch.",
        limits="Must stay opt-in and should not be bundled into paid tiers by default.",
        upgrade_to=None,
    ),
)


def bundle_map() -> dict[str, ProductBundle]:
    return {bundle.key: bundle for bundle in PRODUCT_BUNDLES}


def product_bundle_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "env": MODULE_ENV,
        "bundles": [bundle.to_dict() for bundle in PRODUCT_BUNDLES],
    }
