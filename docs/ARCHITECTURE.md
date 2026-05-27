# Architecture

The server is hybrid in two ways:

- Lifecycle hybrid: MCP stdio server starts normally from the client, then the runtime bridge can use headless `FreeCADCmd`, attach to a GUI bridge, or later run from a FreeCAD Workbench.
- Capability hybrid: source tools answer from the Git checkout and generated inventory; runtime tools operate on a live FreeCAD document/session.

## Components

| Component | Responsibility |
| --- | --- |
| `freecad_mcp.source_inventory` | Static scanner for FreeCAD workbenches, commands, and source references. |
| `freecad_mcp.static_tools` | Source-backed Phase 1 tool implementations. |
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

## Runtime Policy Target

Mutating runtime tools should follow this shape:

1. Validate requested document/object references.
2. Open a named FreeCAD transaction.
3. Apply changes through typed APIs where possible.
4. Recompute.
5. Optionally run geometry checks for shape-producing tools.
6. Return structured before/after document and object summaries.
