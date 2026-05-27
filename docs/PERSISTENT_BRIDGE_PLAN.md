# Persistent Bridge Plan

Current runtime mode is `freecadcmd-process-per-call`. It is reliable for file-scoped tools and CI-like smoke tests, but it cannot preserve an in-memory document or GUI selection between MCP calls.

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

## Current Decision

Typed tools are implemented over process-per-call first because they are deterministic and easy to verify. Persistent modes should reuse the same tool schemas where possible and only add session/document identifiers.

