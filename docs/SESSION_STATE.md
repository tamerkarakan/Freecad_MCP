# Session State

## Current Status

- Local git repository initialized on `main`.
- First baseline commit exists: `720e9f2 chore: initialize FreeCAD MCP inventory`.
- Repo discipline and verification commit exists: `7c6ef09 chore: add repo discipline and verification automation`.
- Phase 1 static MCP commit exists: `57930c3 feat: add static MCP server tools`.
- Phase 2 runtime bridge commit exists: `558b4b0 feat: add FreeCADCmd runtime bridge`.
- Typed FreeCAD MCP surface commit exists: `3dcc942 feat: complete typed FreeCAD MCP tool surface`.
- Remote repository is configured as `origin`: `https://github.com/tamerkarakan/Freecad_MCP.git`.
- First GitHub push completed to `origin/main`; repository was created private.
- FreeCAD upstream source is checked out under ignored `upstream/FreeCAD`.
- Static inventory currently scans 1112 GUI command registrations from FreeCAD commit `dee977f98f8a8542c8db0be2ecc529a771931d01`.
- MCP plan favors typed document/object/Part/Sketch tools plus lower-level command and Python escape hatches.
- Verification command: `scripts\verify.ps1`.
- MCP server entrypoint exists at `server.py`.
- Implemented static tools: `freecad_command_list`, `freecad_command_describe`, `freecad_source_symbol_index`, `freecad_source_search`, `freecad_source_open`.
- MCP client config example exists at `docs/MCP_CLIENT_CONFIG.md`.
- MCP tool schema snapshots are generated at `docs/mcp_tool_schemas.json` and `docs/mcp_tool_schemas.md`.
- Phase 2 FreeCADCmd bridge is implemented as process-per-call.
- Implemented runtime tools: `freecad_session_status`, `freecad_python_exec`.
- Typed CAD tools are implemented for document, object, Part, Sketcher, import/export, mesh, and Assembly basics.
- Sketcher typed tools now cover 9 tools: create, add geometry, add constraint, add profile, edit geometry, edit constraints, transform, auto-constrain, and validate.
- Sketcher geometry support includes point, line, circle, circle arc, ellipse, ellipse arc, hyperbola arc, parabola arc, B-spline, and polyline creation.
- Sketcher diagnostics now report solver result, DoF, open vertices, conflicts/redundants/malformed constraints, missing constraints, dependent geometry, and optional per-constraint errors.
- `freecad_part_extrude` now converts closed wire/sketch profiles to a planar `Part.Face` before extrusion, so closed Sketcher rectangles produce solid Part extrusions instead of shell-only results.
- `freecad_mesh_repair` repairs a mesh copy and assigns it back to avoid immutable mesh errors on imported `Mesh::Feature` objects.
- Long process-per-call runtime scripts now run through a temporary `.py` file when the inline `FreeCADCmd -c` command would exceed the Windows command-line limit.
- Runtime execution payloads now truncate oversized `argv`/`stdout`/`stderr` previews with total-length metadata to reduce oversized MCP responses.
- `FreeCadCmdBridge.execute_python` now returns structured launch failures (`launch_error`) for process start errors instead of propagating raw OS exceptions.
- Stdio server response writing now has a serialization fallback so non-JSON-serializable tool payloads return a structured internal error instead of terminating the server loop.
- MCP resource template listing is supported with an empty `resourceTemplates` response for clients that probe `resources/templates/list`.
- `scripts/smoke_static_mcp.py` now smoke-checks `resources/templates/list`.
- `scripts/smoke_cad_tools.py` now covers STEP export/import roundtrip, Part boolean fuse + BOP geometry check, unsupported mesh repair action reporting, open-sketch extrusion, current solid-shape extrude failure behavior, and expanded Sketcher advanced geometry/profile/constraint/diagnostic/transform flows.
- Persistent `freecadcmd-worker` mode is implemented for session lifecycle, in-memory document lifecycle, object list/get, and primitive creation.
- Persistent worker tools include roadmap aliases `freecad_session_start`, `freecad_session_list`, `freecad_session_close` plus explicit `freecad_worker_*` tools.
- `freecad_assembly_create_joint` now creates native Assembly `JointObject.Joint` proxies instead of plain placeholder string metadata.
- Current MCP tool count is 60.
- MCP resources and prompts are implemented in `freecad_mcp.mcp_stdio`.
- GUI attach and Workbench-hosted bridge modes remain planned in `docs/PERSISTENT_BRIDGE_PLAN.md`.

## Next Session Checklist

1. Run `git status --short --branch`.
2. Run `scripts\verify.ps1`.
3. Read `docs/BACKLOG.md` and `docs/BUGS.md`.
4. Re-run a Sketcher profile smoke if extrude behavior changes again.
5. Run unit tests for `runtime_bridge` and `mcp_stdio` when touching transport/serialization code.
6. Run persistent worker smoke when touching session lifecycle or worker tools.
7. Push only after verification passes.
