# Persistent Bridge Plan

Current runtime modes are `freecadcmd-process-per-call` and `freecadcmd-worker`. Process-per-call remains reliable for file-scoped tools and CI-like smoke tests. Worker mode preserves in-memory documents across MCP calls, but it still does not expose GUI selection or active view state.

## Target Modes

| Mode | Lifecycle | Use case |
| --- | --- | --- |
| `freecadcmd-process-per-call` | MCP tool starts `FreeCADCmd -c` for each call. | Safe file-scoped automation, CI, smoke tests. |
| `freecadcmd-worker` | MCP server starts a long-lived helper process with a request loop. | Faster document/object workflows without GUI state. |
| `freecad-gui-attach` | FreeCAD GUI starts or exposes a local bridge. | Active view, selection, selected edge/face workflows. |
| `freecad-workbench` | FreeCAD Workbench starts bridge when FreeCAD opens. | Native interactive AI workbench. |

## Required Contract Before Implementation

- Every stateful session has a generated `session_id`.
- Every opened document has a bridge-local `document_id` plus `FileName` when saved.
- Mutating calls use named transactions and recompute unless explicitly skipped.
- GUI selection tools must return stable object/subelement references.
- Low-level Python execution remains opt-in and audited.

## Implemented Worker Slice

- Session lifecycle: start/list/status/close.
- Document lifecycle: new/open/save/recompute/close.
- Object basics: list/get/set properties/delete.
- Part basics: primitive creation, boolean, direct/parametric extrude, revolve, and geometry check.
- Sketcher coverage: create, add geometry/constraints/profiles, edit geometry/constraints, transform, auto-constrain, and validate.
- Mesh coverage: import, export, evaluate, repair, and boolean operations where supported by the FreeCAD build.
- Assembly coverage: create assembly containers, insert links, create native JointObject proxies, recompute, and BOM rows.
- Document export from in-memory worker documents.
- Tests: unit worker lifecycle/framing/schema tests and real FreeCAD worker smoke across Part, Sketcher, mesh, and Assembly.

## Remaining Persistent Work

- Add signed Addon Manager packaging polish for the Workbench-hosted bridge after the local module zip workflow is exercised more.
