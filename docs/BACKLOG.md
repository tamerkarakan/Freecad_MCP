# Backlog

## Now

- Run live FreeCAD GUI attach smoke: start `scripts/freecad_gui_bridge_server.py` in GUI, select a Part face, call `freecad_gui_selection_get`, and verify subelement/picked-point records.

## Next

- Add Assembly connector-reference smoke using GUI selection records once stable example documents exist.
- Revisit high-level Sketcher `Group` and `Text` wrappers only after the FreeCAD 1.1.1 constructor crash/typing issue is resolved upstream or a safe API path is found.
- Add MCP SDK adapter if the Python SDK becomes available in the runtime.
- Add crash injection and automatic unhealthy-session cleanup coverage for persistent worker mode.

## Later

- Add Workbench-hosted bridge mode.
- Add TechDraw/CAM/FEM typed wrappers after source-backed design review.
