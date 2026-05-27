# Testing

Primary verification command:

```powershell
scripts\verify.ps1
```

Current checks:

- Python syntax compile for scanner package and CLI wrapper.
- Unit tests with a fake FreeCAD source tree from `tests/unit`.
- Inventory regeneration when `upstream/FreeCAD/src` exists.

Expected future checks:

- MCP tool schema tests.
- Fake bridge integration tests.
- Optional real FreeCAD smoke tests gated by an explicit executable path.
