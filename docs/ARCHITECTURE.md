# Architecture

The server is hybrid in two ways:

- Lifecycle hybrid: MCP stdio server starts normally from the client, then the runtime bridge can use headless `FreeCADCmd`, attach to a GUI bridge, or later run from a FreeCAD Workbench.
- Capability hybrid: source tools answer from the Git checkout and generated inventory; runtime tools operate on a live FreeCAD document/session.

## Components

| Component | Responsibility |
| --- | --- |
| `freecad_mcp.source_inventory` | Static scanner for FreeCAD workbenches, commands, and source references. |
| `freecad_mcp.static_tools` | Source-backed Phase 1 tool implementations. |
| `freecad_mcp.runtime_bridge` | FreeCADCmd discovery and process-per-call execution bridge, with temp-script fallback for long Python payloads on Windows. |
| `freecad_mcp.runtime_tools` | Phase 2 runtime MCP tools. |
| `freecad_mcp.persistent_bridge` | Long-lived FreeCADCmd worker process lifecycle and JSON request bridge. |
| `freecad_mcp.persistent_tools` | Persistent worker MCP session/document/object/Part/Sketcher/mesh/assembly tools. |
| `freecad_mcp.gui_bridge` | Client-side session manager for an opt-in FreeCAD GUI loopback bridge. |
| `freecad_mcp.gui_tools` | MCP tools for attaching to FreeCAD GUI and reading active document, active view, selection, and preselection state. |
| `freecad_mcp.module_registry` | Product-style module aliases and `FREECAD_MCP_MODULES` tool-surface filtering. |
| `freecad_mcp.product_bundles` | Sellable bundle descriptors for Free, Pro, Studio, Team, Source, and Unsafe profiles. |
| `freecad_mcp.distribution_profiles` | Distribution profile descriptors for wheel/sdist, MCP config skeletons, and optional Workbench module artifacts. |
| `freecad_mcp.workbench_artifact` | Local Workbench module zip descriptor for embedding the GUI bridge beside `InitGui.py`. |
| `freecad_mcp.cad_tool_base` | Shared process-per-call FreeCADCmd runner and typed CAD tool schema builder. |
| `freecad_mcp.cad_domains.*` | Domain services for document, object, Part, PartDesign, Sketcher, import-export, mesh, assembly, TechDraw, CAM, and FEM tools. |
| `freecad_mcp.cad_tools` | Backward-compatible aggregate over the CAD domain services. |
| `freecad_mcp.mcp_stdio` | Official Python `mcp` SDK stdio adapter, tool/resource/prompt registration, and logging/error shaping. |
| `server.py` | MCP stdio entrypoint. |
| `scripts/freecad_gui_bridge_server.py` | Local JSON bridge script to execute inside FreeCAD GUI. It marshals RPC handlers onto the Qt GUI thread when PySide is available. |
| `freecad_workbench/FreeCADMCP/InitGui.py` | FreeCAD Workbench/module entrypoint that can host the GUI bridge manually or via `FREECAD_MCP_AUTOSTART=1`. |
| `bridge/` | Future FreeCAD runtime process/session bridge. |
| `policy/` | Future transaction, recompute, geometry-check, and result-shaping rules. |
| `docs/` | Architecture, backlog, bugs, testing, and session continuity. |

## Phase 1 Static MCP Tools

| Tool | Status |
| --- | --- |
| `freecad_command_list` | Implemented |
| `freecad_command_describe` | Implemented |
| `freecad_source_symbol_index` | Implemented |
| `freecad_source_search` | Implemented |
| `freecad_source_open` | Implemented |

## Phase 2 Runtime Tools

| Tool | Status |
| --- | --- |
| `freecad_session_status` | Implemented with FreeCADCmd discovery and optional probe |
| `freecad_python_exec` | Implemented as low-level FreeCADCmd `-c` execution |

Process-per-call runtime remains the deterministic default for file-scoped tools.

## Phase 4 Persistent Worker Tools

The server also exposes a long-lived `freecadcmd-worker` mode. It starts a `FreeCADCmd` helper process, keeps documents in memory, and accepts framed JSON requests over stdin/stdout.

| Tool group | Status |
| --- | --- |
| Session lifecycle | `freecad_session_start`, `freecad_session_list`, `freecad_session_close`, plus `freecad_worker_session_*` explicit forms |
| Document lifecycle | Worker new/open/save/recompute/close/export by `document_id` |
| Object basics | Worker object list/get/set properties/delete |
| Part basics | Worker primitive creation, boolean, extrude, revolve, and geometry check in an in-memory document |
| PartDesign basics | Worker Body creation, Sketch-to-origin-plane attachment, Pad feature creation, selected dress-up features, and basic pattern/mirror transforms |
| Sketcher basics and advanced operations | Worker create/add geometry/add constraints/add profiles/profile create/profile validate/edit geometry/edit constraints/transform/auto-constrain/validate, including curve-preserving profile contracts and native geometry type validation |
| Mesh basics | Worker import/export/evaluate/repair/boolean |
| Assembly basics | Worker create/insert/native joint proxy/recompute/BOM |

## GUI Attach Tools

The server exposes `freecad-gui-attach` mode for live GUI state. The MCP client does not start FreeCAD GUI; a user starts `scripts/freecad_gui_bridge_server.py` inside FreeCAD GUI manually or through the FreeCAD MCP Workbench, then MCP tools connect to the local loopback bridge.

| Tool group | Status |
| --- | --- |
| Bridge lifecycle | `freecad_gui_attach`, `freecad_gui_list`, `freecad_gui_detach`, `freecad_gui_status` |
| Active GUI state | `freecad_gui_active_document_get`, `freecad_gui_document_open`, `freecad_gui_active_view_get` |
| Selection state | `freecad_gui_selection_get`, `freecad_gui_preselection_get`, `freecad_gui_selection_set` |
| View and visibility action | `freecad_gui_visibility_ensure`, `freecad_gui_view_orientation_set`, `freecad_gui_view_fit`, `freecad_gui_view_snapshot` |

`freecad_workbench/FreeCADMCP/InitGui.py` also registers a **FreeCAD MCP** workbench with start/stop/status commands and optional autostart via environment variables.

## Typed CAD Tools

Implemented groups:

- Document lifecycle: new, open, save, recompute, export.
- Object inspection and mutation: list, get, set simple properties, delete.
- Part operations: create primitives, boolean, direct or parametric extrude, revolve, fillet, chamfer, and check geometry remain implemented internally for regression coverage, but are hidden from the advertised MCP surface so agents use Sketcher + PartDesign workflows.
- PartDesign operations: create/reuse Body objects, attach Sketcher profiles to Body origin planes (`XY`, `XZ`, `YZ`), create Pad/Pocket/Hole/Revolution/Groove/Loft/Pipe features, expose high-level Body-attached recipe tools for profile features and sweep features, apply Fillet/Chamfer/Thickness/Draft dress-up features, and create LinearPattern/PolarPattern/Mirrored transforms while keeping the Body Tip and solid result consistent.
- Sketcher typed coverage: create sketches; optionally attach sketches to PartDesign Body origin planes; add point, line, circle, arc, ellipse/conic arc, and polyline geometry; add common profiles; analyze trace points for supported line/arc fits and unsupported freeform; create/update constraints except blocked `Block`/`Group`/`Text`; create and validate loop-based pad-ready profiles with curve-preservation, unsupported-freeform, and line-fallback guards; edit geometry/constraints; run transform, auto-constrain, and diagnostics flows. Native B-spline/freeform profile creation is intentionally unsupported.
- Import/export and mesh operations.
- Assembly basics: create assembly, insert links, native JointObject proxy creation, recompute, BOM.
- TechDraw first slice: create page/template, create part view, inspect page/view graph, and export headless DXF.
- CAM first slice: create simple `Path::Feature` objects from explicit commands, inspect command summaries, and export raw G-code without invoking a machine postprocessor.
- FEM first slice: create analysis containers, solid material objects, fixed/force constraints, and inspect analysis membership without running solvers.

Process-per-call typed tools use explicit file paths and output paths. Persistent worker tools use `session_id` plus bridge-local `document_id` for in-memory workflows.

Write paths are guarded by default: `output_path` must be absolute and remain under `FREECAD_MCP_WORKSPACE_ROOT` or the server workspace unless the caller passes `allow_external_paths=true`.

## MCP Resources And Prompts

The server exposes read-only resources for architecture, session state, roadmap status, testing, Sketcher capabilities, PartDesign attachment policy, FreeCAD wiki research notes, GUI attach planning, Workbench bridge setup, Workbench artifact shape, TechDraw/CAM/FEM typed-wrapper planning, product-module filtering, product bundles, distribution profiles, tool schemas, and inventory summary. It also exposes workflow prompts for design tasks and phase gates.

## Product Module Filtering

`FREECAD_MCP_MODULES` can limit the advertised tool surface. Default is `all`. Product aliases such as `free`, `pro`, `studio`, `team`, and `source` expand to domain modules; `dev`, `developer`, and `local-dev` intentionally expand to the full advertised surface for local maintainer work. Explicit comma-separated module lists are also supported. Worker tools require the `worker` module even when they also belong to domains such as Sketcher or mesh, source-code intelligence requires the internal `developer` module or the user-facing `source` add-on alias, and implemented Part primitive tools are hidden by policy even when their modules would otherwise match. Generated sellable bundle manifests live in `docs/PRODUCT_BUNDLES.md` and `docs/product_bundles.json`; distribution profile manifests and per-profile MCP config skeletons live in `docs/DISTRIBUTION_PROFILES.md`, `docs/distribution_profiles.json`, and `packaging/profiles/*.mcp.json`. The local Workbench module zip is described by `docs/WORKBENCH_ARTIFACT.md` and `docs/workbench_artifact.json`.

The headless typed CAD surface is now split into domain services under `freecad_mcp.cad_domains`; signed marketplace/addon packaging remains a later distribution step.

## Runtime Policy Target

Mutating runtime tools should follow this shape:

1. Validate requested document/object references.
2. Open a named FreeCAD transaction.
3. Apply changes through typed APIs where possible.
4. Recompute.
5. Optionally run geometry checks for shape-producing tools.
6. Return structured before/after document and object summaries.
