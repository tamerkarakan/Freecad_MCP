# Testing

Primary verification command:

```powershell
scripts\verify.ps1
```

Current checks:

- Python syntax compile for server, scripts, package, and tests.
- Unit tests with a fake FreeCAD source tree from `tests/unit`.
- MCP tool schema snapshot export.
- Static stdio MCP smoke test through `scripts/smoke_static_mcp.py`.
- Optional real FreeCADCmd runtime smoke test through `scripts/smoke_freecad_runtime.py`.
- Inventory regeneration when `upstream/FreeCAD/src` exists.

Expected future checks:

- MCP tool schema tests.
- Fake bridge integration tests for document and object tools.
- Persistent bridge integration tests once GUI/workbench bridge mode exists.
