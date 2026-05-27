# Agent Operating Contract

This repo is meant to be safe for multi-session coding agents.

## Git Boundaries

- Keep `upstream/` out of this repository. It is a local FreeCAD checkout used as source evidence.
- Commit small, reviewable steps.
- Do not rewrite history after anything has been pushed.
- Do not commit local credentials, FreeCAD user config, generated caches, or machine-specific runtime paths.
- Before a push, run `scripts/verify.ps1`.

## Engineering Principles

- Prefer typed MCP tools over broad Python execution.
- Keep broad escape hatches such as `freecad_python_exec` and `freecad_command_run` visibly lower-level.
- Runtime mutating tools should use FreeCAD transactions, recompute, and structured result reporting.
- Source intelligence must cite the FreeCAD commit and source file references.
- Favor small cohesive classes around scanner, bridge, policy, and tool registration responsibilities.

## Session Handoff

Every session that changes behavior should update:

- `docs/SESSION_STATE.md`
- `docs/BACKLOG.md`
- `docs/BUGS.md` if an issue is discovered or intentionally left open
- `docs/TESTING.md` if verification scope changes

