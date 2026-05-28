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
- Optional typed CAD smoke test through `scripts/smoke_cad_tools.py`, including primitive/export, STEP roundtrip import, Part boolean + geometry check, mesh import/repair, unsupported mesh repair action reporting, Assembly creation, closed Sketcher rectangle to solid extrusion, parametric shell-only/symmetric/taper extrusion, open Sketcher extrusion, safe Sketcher Group/Text constraint blocking, current solid-shape extrude failure behavior, advanced Sketcher geometry/profile/constraint diagnostics, auto-constraint detection/application, B-spline edits, copy, and move transforms.
- Optional generated fixture document smoke through `scripts/smoke_fixture_documents.py`, including a multi-object FreeCAD document, object metadata and visibility, boolean geometry, Sketcher profile extrusion, Assembly link, reopen/list/get checks, geometry validation, STEP export, and STL export.
- Optional persistent worker smoke test through `scripts/smoke_persistent_worker.py`, including worker session start/list/status/close, in-memory document lifecycle, primitive creation, object list/get/set/delete, Part boolean + geometry check, closed Sketcher profile to solid extrude, worker parametric shell-only extrusion, safe worker Sketcher Group constraint blocking, Sketcher geometry/constraint/edit/transform/auto-constraint/validate flows, STL mesh roundtrip import/evaluate/repair, Assembly create/insert/native joint/BOM/solve, document export, save, and document close.
- Inventory regeneration when `upstream/FreeCAD/src` exists.
- Unit guard for stdio serialization fallback (`test_mcp_stdio.py`).
- Unit guard for stdio EOF shutdown cleanup (`test_mcp_stdio.py`).
- Unit guard for empty MCP resource-template listing (`resources/templates/list`).
- Static MCP smoke guard for empty resource-template listing (`resources/templates/list`).
- Static MCP smoke guard for GUI attach tool schemas (`freecad_gui_attach`, `freecad_gui_selection_get`).
- Static MCP resource coverage includes architecture, session state, testing, Sketcher capabilities, GUI attach planning, schemas, and inventory summary.
- Unit guard for structured launch errors, runtime output truncation, compact execution metadata, and long-code temp-script execution (`test_runtime_bridge.py`).
- Unit guard for persistent worker request/response framing, structured worker errors, long worker temp-script lifecycle, cross-field input validation, session cleanup, and unknown-session errors (`test_persistent_bridge.py`).
- Unit guard for GUI bridge attach/call/detach/error handling against a fake local HTTP bridge (`test_gui_bridge.py`).
- Opt-in live FreeCAD GUI attach smoke (`FREECAD_MCP_GUI_SMOKE=1 scripts\verify.ps1` or `scripts/smoke_gui_attach.py`) launches FreeCAD GUI, starts the bridge, selects two Part faces, reads them via MCP GUI tools, fits the view, closes the GUI process, and verifies a Fixed Assembly joint populated from those selection records.

Expected future checks:

- MCP tool schema tests.
- Real imported third-party fixture files once small license-clean samples are chosen.
- Workbench bridge integration tests once Workbench-hosted mode exists.
