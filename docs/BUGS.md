# Bugs And Risks

## Open

- Runtime bridge is not implemented yet.
- Generated inventory is static; dynamically named commands can be missed.
- Python `GetResources` parsing is conservative and can miss non-literal metadata.
- C++ parsing is regex-based and should be replaced or reinforced if source patterns become more complex.
- No remote repository is configured yet, so the first push is pending.

## Closed

- None yet.

