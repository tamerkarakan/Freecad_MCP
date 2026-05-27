# Bugs And Risks

## Open

- Runtime bridge is process-per-call only; it is not a persistent FreeCAD session yet.
- Generated inventory is static; dynamically named commands can be missed.
- Python `GetResources` parsing is conservative and can miss non-literal metadata.
- C++ parsing is regex-based and should be replaced or reinforced if source patterns become more complex.
- Server uses a minimal local JSON-RPC implementation because the Python MCP SDK is not installed in the bundled runtime.
- `freecad_python_exec` is a low-level escape hatch and should be replaced by typed tools for normal CAD operations.

## Closed

- None yet.
