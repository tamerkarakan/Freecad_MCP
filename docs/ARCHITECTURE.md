# Architecture

The server is hybrid in two ways:

- Lifecycle hybrid: MCP stdio server starts normally from the client, then the runtime bridge can use headless `FreeCADCmd`, attach to a GUI bridge, or later run from a FreeCAD Workbench.
- Capability hybrid: source tools answer from the Git checkout and generated inventory; runtime tools operate on a live FreeCAD document/session.

## Components

| Component | Responsibility |
| --- | --- |
| `freecad_mcp.source_inventory` | Static scanner for FreeCAD workbenches, commands, and source references. |
| `freecad_mcp.static_tools` | Source-backed Phase 1 tool implementations. |
| `freecad_mcp.runtime_bridge` | FreeCADCmd discovery and process-per-call execution bridge. |
| `freecad_mcp.runtime_tools` | Phase 2 runtime MCP tools. |
| `freecad_mcp.persistent_bridge` | Long-lived FreeCADCmd worker process lifecycle and JSON request bridge. |
| `freecad_mcp.persistent_tools` | Persistent worker MCP session/document/object tools. |
| `freecad_mcp.cad_tools` | Typed document/object/Part/Sketcher/import-export/mesh/assembly tools. |
| `freecad_mcp.mcp_stdio` | Minimal newline-delimited JSON-RPC stdio MCP dispatcher. |
| `server.py` | MCP stdio entrypoint. |
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
| Document lifecycle | Worker new/open/save/recompute/close by `document_id` |
| Object basics | Worker object list/get |
| Part basics | Worker primitive creation in an in-memory document |

## Typed CAD Tools

Implemented groups:

- Document lifecycle: new, open, save, recompute, export.
- Object inspection and mutation: list, get, set simple properties, delete.
- Part operations: create primitives, boolean, extrude, revolve, fillet, chamfer, check geometry.
- Sketcher basics: create sketches, add line/circle/arc geometry, add constraints, validate.
- Import/export and mesh operations.
- Assembly basics: create assembly, insert links, native JointObject proxy creation, recompute, BOM.

Process-per-call typed tools use explicit file paths and output paths. Persistent worker tools use `session_id` plus bridge-local `document_id` for in-memory workflows.

Write paths are guarded by default: `output_path` must be absolute and remain under `FREECAD_MCP_WORKSPACE_ROOT` or the server workspace unless the caller passes `allow_external_paths=true`.

## MCP Resources And Prompts

The server exposes read-only resources for architecture, session state, testing, tool schemas, and inventory summary. It also exposes workflow prompts for design tasks and phase gates.

## Runtime Policy Target

Mutating runtime tools should follow this shape:

1. Validate requested document/object references.
2. Open a named FreeCAD transaction.
3. Apply changes through typed APIs where possible.
4. Recompute.
5. Optionally run geometry checks for shape-producing tools.
6. Return structured before/after document and object summaries.
