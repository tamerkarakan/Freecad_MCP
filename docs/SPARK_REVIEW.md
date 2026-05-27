# Spark Review Gate

`GPT-5.3-Codex-Spark` was used as a second-eye reviewer for the Phase 2 bridge and remaining-phase plan.

## Findings Applied

- Added unsafe opt-in for `freecad_python_exec`.
- Added SHA-256 audit metadata for unsafe Python execution.
- Hardened malformed prefixed JSON parsing.
- Added stricter FreeCADCmd candidate handling for quoted paths and directories.
- Added query length limits for source search.
- Added schema duplicate/tool contract tests.
- Added optional `FREECAD_MCP_REQUIRE_RUNTIME=1` smoke behavior.
- Added `output_path` policy: absolute paths only, default writes constrained to `FREECAD_MCP_WORKSPACE_ROOT`/server workspace, with explicit `allow_external_paths=true` escape hatch.
- Added missing-resource handling for MCP resources.

## Remaining Watch Items

- Persistent bridge is still a plan, not implemented.
- `freecad_python_exec` remains intentionally dangerous and requires explicit opt-in.
- File reads/imports can still access caller-provided paths; only writes are workspace-gated by default.
- Mesh boolean support depends on the actual FreeCAD build.
- Assembly joint creation is currently placeholder metadata; connector solving needs persistent GUI/workbench mode.
