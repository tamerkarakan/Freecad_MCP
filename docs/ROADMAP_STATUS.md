# Roadmap Status

Last verified against the configured FreeCAD 1.1.1 portable runtime on 2026-05-28.

## Completed

- Phase 1 static source intelligence and generated FreeCAD command inventory.
- Phase 2 process-per-call `FreeCADCmd` runtime bridge with typed document/object/Part/Sketcher/import-export/mesh/Assembly tools.
- Expanded Sketcher typed coverage for geometry, profiles, constraints, transforms, diagnostics, and auto-constraints.
- Loop-based Sketcher profile builder/validator for pad-ready traced profiles, endpoint drift rejection, curve-preservation contracts, Part face validation, and no-cheat topology checks.
- Persistent `freecadcmd-worker` sessions with document/object/Part/Sketcher/mesh/Assembly operations and crash cleanup.
- GUI attach bridge tools for active document, active view, selection/preselection, selection set, and view fit.
- Opt-in live GUI smoke that validates GUI selection records and Assembly connector references.
- Workbench-hosted bridge module under `freecad_workbench/FreeCADMCP`.
- TechDraw typed slice for page/template creation, part views, inspection, and headless DXF export.
- CAM typed slice for raw `Path::Feature` command paths, inspection, and raw G-code export without postprocessor execution.
- FEM typed slice for analysis containers, material objects, fixed/force constraints, and inspection without solver execution.

## Blocked Or Waiting

- MCP SDK adapter: bundled Python currently has no importable `mcp` package, so the minimal local JSON-RPC dispatcher remains active.
- Sketcher `Group` and `Text` wrappers: direct constructor attempts can terminate FreeCADCmd in the current FreeCAD 1.1.1 runtime, so typed tools block them until a stable API path exists.

There are no unblocked roadmap items left in the current scope.

## Future Deepening

- TechDraw SVG/PDF export should go through GUI attach or Workbench validation because those APIs live behind `TechDrawGui`.
- CAM job/toolbit/postprocessor workflows need machine/post fixture contracts before default typed mutation tools are safe.
- FEM mesh generation, solver execution, and result import need solver availability and fixture contracts before default typed mutation tools are safe.
- Workbench bridge can be polished into installed/addon packaging after the local module-path workflow is exercised more.
