# Bugs And Risks

## Open

- Runtime bridge is not implemented yet.
- Runtime bridge discovery is not implemented yet.
- Generated inventory is static; dynamically named commands can be missed.
- Python `GetResources` parsing is conservative and can miss non-literal metadata.
- C++ parsing is regex-based and should be replaced or reinforced if source patterns become more complex.
- Runtime bridge has not been smoke-tested against a real FreeCAD executable yet.
- Phase 1 server uses a minimal local JSON-RPC implementation because the Python MCP SDK is not installed in the bundled runtime.

## Closed

- None yet.
