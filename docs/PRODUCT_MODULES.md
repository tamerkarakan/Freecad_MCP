# Product Modules

The repo is still one codebase, but the MCP tool surface can now be exposed as product-style modules with `FREECAD_MCP_MODULES`.

Default behavior is unchanged:

```powershell
$env:FREECAD_MCP_MODULES = "all"
```

Multiple modules can be comma-separated:

```powershell
$env:FREECAD_MCP_MODULES = "core,headless,gui,sketcher,partdesign"
```

## Module Names

| Module | Purpose |
| --- | --- |
| `core` | FreeCAD command inventory and runtime status/discovery. |
| `headless` | FreeCADCmd document/object/import-export/Part primitives and operations. |
| `worker` | Persistent FreeCADCmd worker sessions and in-memory document workflows. |
| `gui` | FreeCAD GUI attach, active document/view, selection, view-fit, first live primitive creation, and live Sketcher/PartDesign state inspection. |
| `sketcher` | Sketcher creation, geometry, constraints, profile validation, transforms, and curve-fit guidance. |
| `partdesign` | PartDesign Body, Pad, and Pocket typed tools. |
| `mesh` | Mesh import/export/evaluate/repair/boolean tools. |
| `assembly` | Assembly create/insert/native joint/solve/BOM tools. |
| `techdraw` | TechDraw page/template/view/inspect and headless DXF export. |
| `cam` | Conservative CAM raw Path::Feature creation, inspect, and raw G-code export. |
| `fem` | Conservative FEM analysis/material/fixed-force constraint setup and inspect. |
| `developer` | Internal source-intelligence module tag for `freecad_source_*`; not the local maintainer profile. |
| `unsafe` | Explicit low-level `freecad_python_exec` escape hatch. |

## Product Aliases

| Alias | Expands To |
| --- | --- |
| `free` | `core,headless` |
| `pro` | `core,headless,sketcher,partdesign,mesh,assembly,gui` |
| `studio` | `core,headless,sketcher,partdesign,mesh,assembly,gui,techdraw,cam,fem,worker` |
| `team` | `studio,developer` |
| `source` | Internal `developer` module only. |
| `dev`, `developer`, `local-dev` | Full local maintainer surface, equivalent to `all`. |
| `all` / `default` | all tools |

## Sellable Bundles

Generated bundle counts and tool lists are in `docs/PRODUCT_BUNDLES.md` and `docs/product_bundles.json`. Generated distribution profiles and MCP config skeletons are in `docs/DISTRIBUTION_PROFILES.md`, `docs/distribution_profiles.json`, and `packaging/profiles/`.

Current generated counts:

| Bundle | Profile | Tool Count | Notes |
| --- | --- | ---: | --- |
| Free | `free` | 22 | File-based FreeCADCmd document/object/Part operations. |
| Pro | `pro` | 61 | Adds GUI attach, Sketcher, PartDesign, mesh, and Assembly. |
| Studio | `studio` | 119 | Adds persistent worker sessions plus TechDraw, CAM, and FEM. |
| Team | `team` | 122 | Adds source-intelligence tools. |
| Source add-on | `source` | 5 | Command/source intelligence only. |
| Local developer | `developer` / `dev` / `local-dev` | Full surface | Same as `all`; not a sellable restricted package. |
| Unsafe add-on | `unsafe` | 1 | Only `freecad_python_exec`; never included in paid tiers by default. |

## Current Packaging Rule

This is still one installable codebase, but the headless typed CAD surface is no longer one monolithic `cad_tools.py` implementation. Shared execution lives in `freecad_mcp.cad_tool_base`, and domain services live under `freecad_mcp.cad_domains`.

The registry still controls what the MCP client sees. Product bundle manifests make the commercial split explicit, but the local maintainer aliases stay full-surface by design. A local FreeCAD Workbench module zip exists for GUI-capable profiles; separate paid/free Python packages, Codex plugin bundles, and signed FreeCAD Addon Manager packaging are later distribution phases.
