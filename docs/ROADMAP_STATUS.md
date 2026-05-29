# Roadmap Status

Last verified against the configured FreeCAD 1.1.1 portable runtime on 2026-05-28.

## Completed

- Phase 1 static source intelligence and generated FreeCAD command inventory.
- Phase 2 process-per-call `FreeCADCmd` runtime bridge with typed document/object/Part/Sketcher/import-export/mesh/Assembly tools.
- Expanded Sketcher typed coverage for geometry, geometry method cataloging, arc actual-geometry reporting, profiles, constraints, transforms, diagnostics, and auto-constraints.
- Loop-based Sketcher profile builder/validator for pad-ready traced profiles, endpoint drift rejection, curve-preservation contracts, native geometry type/intent reporting, curve fit analysis, Part face validation, and no-cheat topology checks.
- PartDesign Body/plane attachment and Pad creation for Sketcher profiles that need the same Body + origin plane workflow FreeCAD GUI prompts for.
- Persistent `freecadcmd-worker` sessions with document/object/Part/Sketcher/mesh/Assembly operations and crash cleanup.
- GUI attach bridge tools for active document, active view, selection/preselection, selection set, and view fit.
- Opt-in live GUI smoke that validates GUI selection records and Assembly connector references.
- Workbench-hosted bridge module under `freecad_workbench/FreeCADMCP`.
- Local Workbench module zip artifact descriptor and smoke path for embedding the GUI bridge beside `InitGui.py`.
- TechDraw typed slice for page/template creation, part views, inspection, and headless DXF export.
- CAM typed slice for raw `Path::Feature` command paths, inspection, and raw G-code export without postprocessor execution.
- FEM typed slice for analysis containers, material objects, fixed/force constraints, and inspection without solver execution.

## Blocked Or Waiting

- CI workflow push: `.github/workflows/ci.yml` exists but pushing it needs a remote credential with the `workflow` OAuth scope.

## Recently Completed (was blocked/expansion)

- MCP SDK adapter: `mcp` is now installable, so the stdio server runs on `mcp.server.lowlevel.Server` and the hand-rolled JSON-RPC dispatcher was removed (`mcp>=1.0` dependency).
- Structured JSON server logging; FreeCAD worker console reading (`freecad_session_console`); `source_search` traversal bounds; image-to-sketch decision guidance in `freecad_curve_fit_analyze`; the `freecad_partdesign_pocket` typed tool.
- Product-style tool filtering through `FREECAD_MCP_MODULES`, with `free`, `pro`, `studio`, `team`, and explicit module-list support.
- Product bundle manifests generated at `docs/PRODUCT_BUNDLES.md` and `docs/product_bundles.json`; worker tools now require the `worker` module, source-code intelligence is the `source` add-on, `developer/dev/local-dev` remain full local maintainer aliases, and unsafe Python exec remains an explicit add-on.
- Distribution profile skeletons generated at `docs/DISTRIBUTION_PROFILES.md`, `docs/distribution_profiles.json`, and `packaging/profiles/*.mcp.json`; `pyproject.toml` now declares setuptools build metadata, package discovery, runtime script package data, and the `freecad-hybrid-mcp` console entrypoint.
- Python package smoke now builds and inspects wheel and sdist artifacts, installs the wheel into a temporary venv, starts the installed `freecad-hybrid-mcp` entrypoint, and verifies MCP initialize/tool calls under the `free` profile.
- Workbench artifact generation now writes `docs/WORKBENCH_ARTIFACT.md`, `docs/workbench_artifact.json`, and `packaging/workbench/README.md`; `scripts/smoke_workbench_artifact.py` builds and inspects the local `freecad-mcp-workbench.zip`.
- Headless typed CAD tools were split from the monolithic `cad_tools.py` implementation into shared runner code plus domain services under `freecad_mcp.cad_domains`.
- Sketcher `Group` and `Text` wrappers: direct constructor attempts can terminate FreeCADCmd in the current FreeCAD 1.1.1 runtime, so typed tools block them until a stable API path exists.

There are no unblocked roadmap items left in the current scope.

## Future Deepening

- Add remote MCP transport support for HTTP/SSE and Streamable HTTP while preserving stdio as the local default.
- Deepen structured logs beyond the current opt-in JSON logger with crash bundles, FreeCAD subprocess lifecycle rollups, request/response size summaries, timing, and tool-level performance.
- Extend FreeCAD console reading beyond the current persistent-worker console tool to process-per-call, GUI bridge, and Workbench-hosted bridge modes.
- Expand GUI bridge into full live FreeCAD access for observing live drawing, GUI command boundaries, transaction/dirty state, console forwarding, and safe GUI-side mutations.
- Deepen image-to-sketch guidance beyond the current `freecad_curve_fit_analyze` decision report so ambiguous traces can drive prompt/resource flows for B-spline vs arc vs line/polyline decisions.
- Research Sketcher and PartDesign workbenches from FreeCAD docs and the local source checkout, then add safe typed and GUI/workbench-backed MCP wrappers with fixtures and smoke tests.
- TechDraw SVG/PDF export should go through GUI attach or Workbench validation because those APIs live behind `TechDrawGui`.
- CAM job/toolbit/postprocessor workflows need machine/post fixture contracts before default typed mutation tools are safe.
- FEM mesh generation, solver execution, and result import need solver availability and fixture contracts before default typed mutation tools are safe.
- Decide whether the generated bundle profiles should become separate installable Python packages or Codex plugin bundles.
- Polish the local Workbench module zip into a signed/installed FreeCAD Addon Manager package after the generated `freecad-workbench-module` path is exercised more.
