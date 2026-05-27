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
- Optional typed CAD smoke test through `scripts/smoke_cad_tools.py`, including primitive/export, mesh import/repair, Assembly creation, and Sketcher rectangle to solid extrusion.
- Inventory regeneration when `upstream/FreeCAD/src` exists.
- Unit guard for stdio serialization fallback (`test_mcp_stdio.py`).
- Unit guard for empty MCP resource-template listing (`resources/templates/list`).
- Unit guard for structured launch errors and runtime output truncation (`test_runtime_bridge.py`).

Expected future checks:

- MCP tool schema tests.
- More fixture coverage for document/object/Part/Sketcher/mesh/assembly tools.
- Persistent bridge integration tests once GUI/workbench bridge mode exists.
