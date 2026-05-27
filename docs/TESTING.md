# Testing

Primary verification command:

```powershell
scripts\verify.ps1
```

Current checks:

- Python syntax compile for server, scripts, package, and tests.
- Unit tests with a fake FreeCAD source tree from `tests/unit`.
- Phase 1 tool schema snapshot export.
- Static stdio MCP smoke test through `scripts/smoke_static_mcp.py`.
- Inventory regeneration when `upstream/FreeCAD/src` exists.

Expected future checks:

- MCP tool schema tests.
- Fake bridge integration tests.
- Optional real FreeCAD smoke tests gated by an explicit executable path.
