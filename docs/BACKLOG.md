# Backlog

## Now

- No unblocked roadmap item remains in the current scope. See `docs/ROADMAP_STATUS.md` for the completed, blocked, and future-deepening split.

## Blocked Or Waiting

- Add MCP SDK adapter if the Python SDK becomes available in the runtime; bundled Python currently does not include the `mcp` package.
- Revisit high-level Sketcher `Group` and `Text` wrappers only after the FreeCAD 1.1.1 constructor crash/typing issue is resolved upstream or a safe API path is found.

## Future Deepening

- Extend CAM/FEM beyond first slice only with fixture-backed job/solver contracts.
- Add TechDraw SVG/PDF export only behind GUI attach or Workbench validation because those APIs live behind `TechDrawGui`.

## Later

- Installed/addon packaging polish for the Workbench-hosted bridge.
