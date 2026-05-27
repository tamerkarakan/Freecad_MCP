# Bugs And Risks

## Open

- Runtime bridge is process-per-call only; it is not a persistent FreeCAD session yet.
- Assembly joint creation currently writes placeholder metadata; full connector solving needs persistent GUI/workbench bridge mode.
- Mesh boolean support depends on the actual FreeCAD build and may return tool errors on unsupported operations.
- File reads/imports accept caller-provided paths; write paths are workspace-gated by default.
- Generated inventory is static; dynamically named commands can be missed.
- Python `GetResources` parsing is conservative and can miss non-literal metadata.
- C++ parsing is regex-based and should be replaced or reinforced if source patterns become more complex.
- Server uses a minimal local JSON-RPC implementation because the Python MCP SDK is not installed in the bundled runtime.
- `freecad_python_exec` is a low-level escape hatch and requires explicit unsafe opt-in.
- Even with response truncation, some Windows MCP clients may still report `Transport closed` under extreme runtime output/IO conditions; continue validating in long smoke sessions.

## Closed

- Closed Sketcher/profile extrusion previously produced a shell-only `Part::Feature`; `freecad_part_extrude` now builds a planar face from closed wires before extrusion so rectangle profiles become solids.
- `freecad_mesh_repair` previously attempted to mutate `Mesh::Feature.Mesh` directly and could hit immutable mesh errors; it now repairs a copy and assigns it back, with replacement-object fallback.
- Response serialization errors in `serve_stdio` previously could terminate the stdio loop; they now fall back to a structured `-32603` error response.
- Large runtime envelopes could grow excessively because raw `argv`/`stdout`/`stderr` were returned verbatim; execution payloads now return truncated previews plus total-length metadata.
- Some MCP clients call `resources/templates/list` even when no resource templates are exposed; the server now returns an empty `resourceTemplates` list instead of `-32601`.
