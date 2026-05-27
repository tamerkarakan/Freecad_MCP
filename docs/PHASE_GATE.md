# Phase Gate Checklist

Use this before pushing a phase:

- `git status --short --branch` is understood.
- `scripts\verify.ps1` passes.
- If real FreeCAD behavior changed, run with `FREECAD_MCP_REQUIRE_RUNTIME=1`.
- Tool schemas are regenerated and reviewed.
- `docs/SESSION_STATE.md` is updated.
- `docs/BUGS.md` records known limitations.
- Spark or equivalent second-eye review is run for broad/risky phases.
- Commit message describes behavior, not only files.

