# Bugs And Risks

## Open

- Runtime bridge is not implemented yet.
- Generated inventory is static; dynamically named commands can be missed.
- Python `GetResources` parsing is conservative and can miss non-literal metadata.
- C++ parsing is regex-based and should be replaced or reinforced if source patterns become more complex.
- Runtime bridge has not been smoke-tested against a real FreeCAD executable yet.

## Closed

- None yet.
