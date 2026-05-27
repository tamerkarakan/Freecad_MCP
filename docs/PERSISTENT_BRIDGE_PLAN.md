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
- Object basics: list/get.
- Part basics: primitive creation.
- Tests: unit worker lifecycle/framing tests and real FreeCAD worker smoke.

## Remaining Persistent Work

- Broaden worker tools to reuse more typed CAD operations.
- Add crash injection and automatic unhealthy-session cleanup coverage.
- Add GUI attach and Workbench-hosted bridge modes for live selection/view workflows.
