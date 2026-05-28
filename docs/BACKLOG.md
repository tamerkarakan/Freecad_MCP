# Backlog

## Now

- No unblocked roadmap item remains in the current scope. See `docs/ROADMAP_STATUS.md` for the completed, blocked, and future-deepening split.

## Next Expansion Candidates

- Add a remote MCP transport endpoint in addition to stdio. Cover HTTP/SSE and current Streamable HTTP MCP patterns, keep stdio as the stable local default, and add smoke tests for initialize/tools/list/tools/call over the new transport.
- Add structured server logging for crash diagnosis, request/response timing, payload sizes, FreeCAD subprocess lifecycle, worker session restarts, and tool-level performance. Logs must avoid credentials and large CAD payload dumps by default.
- Add FreeCAD console reading. Capture or proxy FreeCAD console output from `FreeCADCmd`, persistent workers, and GUI/workbench bridge sessions so agents can inspect warnings/errors without using broad Python execution.
- Expand GUI live bridge into full live FreeCAD access. Go beyond active document/view/selection/preselection/view-fit into live drawing observation, command execution boundaries, transaction status, console forwarding, document dirty state, and safe GUI-side mutation policies.
- Improve image-to-sketch guidance. When visual tracing cannot confidently distinguish native geometry such as B-spline vs circular arc vs polyline, the MCP/tool prompt flow should ask the user for a choice or expose a small decision report instead of silently degrading curves. Preserve curve intent; line/polyline fallback must be explicit.
- Research and extend Sketcher and PartDesign coverage from both FreeCAD documentation and the local FreeCAD source checkout. Include GUI commands where safe through GUI/workbench bridge paths, and add typed wrappers only with source evidence, fixture-backed behavior, and smoke tests.
- Bound `StaticToolService.source_search` rglob traversal with a file-count/time limit and early termination so a large FreeCAD source tree cannot hang or time out the tool.
- Add a POSIX CI leg (or document enabling Windows Developer Mode) so the `safe_source_path` symlink-escape unit test runs instead of skipping.

## Blocked Or Waiting

- Add MCP SDK adapter if the Python SDK becomes available in the runtime; bundled Python currently does not include the `mcp` package.
- Revisit high-level Sketcher `Group` and `Text` wrappers only after the FreeCAD 1.1.1 constructor crash/typing issue is resolved upstream or a safe API path is found.

## Future Deepening

- Extend CAM/FEM beyond first slice only with fixture-backed job/solver contracts.
- Add TechDraw SVG/PDF export only behind GUI attach or Workbench validation because those APIs live behind `TechDrawGui`.

## Later

- Installed/addon packaging polish for the Workbench-hosted bridge.
