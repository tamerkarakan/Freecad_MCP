# Backlog

## Now

- No unblocked roadmap item remains in the current scope. See `docs/ROADMAP_STATUS.md` for the completed, blocked, and future-deepening split.
- The Claude Desktop stdio runtime-tool hang was fixed by isolating process-per-call FreeCADCmd stdin and covered by `scripts/smoke_mcp_runtime_stdio.py`; no follow-up backlog item is open for that bug.
- FreeCAD GUI's regular-polygon Sketcher signature (`center` plus `corner`) has been folded into typed process and worker profile helpers with construction-circle constraints; no separate backlog item is open for that helper.
- Tester-reported repair gaps for Body Tip `$ref` setting, current-Tip delete fallback, slot redundant-constraint avoidance, keyhole-style circle+slot single-loop profiles, and compact worker responses are implemented and smoke-covered; no separate backlog item remains for those exact cases.
- FreeCAD 1.1 Sketcher External Projection/External Intersection are exposed as explicit process and worker aliases; the lower-level `freecad_sketch_edit_geometry` `add_external` operation remains as compatibility surface.

## Next Expansion Candidates

- Add a remote MCP transport endpoint in addition to stdio. Cover HTTP/SSE and current Streamable HTTP MCP patterns, keep stdio as the stable local default, and add smoke tests for initialize/tools/list/tools/call over the new transport.
- Deepen structured server logging beyond the current opt-in request/response timing layer: add crash bundles, worker restart correlation reports, and performance rollups while continuing to avoid credentials and large CAD payload dumps by default.
- Add GUI bridge watchdog/heartbeat hardening for repeated live-GUI calls: surface queued/busy state, bound stuck calls with clearer recovery guidance, and record bridge restart evidence without sending large screenshots or CAD payloads by default.
- Extend FreeCAD console reading beyond the current persistent-worker console tool. Capture or proxy console output from process-per-call `FreeCADCmd`, GUI bridge, and Workbench bridge sessions so agents can inspect warnings/errors without using broad Python execution.
- Expand GUI live bridge into full live FreeCAD access. Now that explicit `.FCStd` document open, final-object visibility repair, view orientation, and viewport snapshot are covered, go beyond active document/view/selection/preselection/view-fit/visibility/orientation/snapshot into richer live drawing observation, command execution boundaries, transaction status, console forwarding, document dirty state, and safe GUI-side mutation policies.
- Deepen image-to-sketch guidance beyond the current `freecad_curve_fit_analyze` decision report. Add richer prompt/resource workflows for ambiguous native geometry such as B-spline vs circular arc vs polyline. Preserve curve intent; line/polyline fallback must be explicit.
- Extend GUI coverage according to `docs/GUI_1_1_1_RESEARCH.md`: after viewport snapshot, the first Sketcher edit enter/leave, PartDesign Body activation, and feature-task state tools, deepen task-specific preconditions before TechDraw GUI exporters/dimensions/projections, Assembly joint-from-selection/BOM/solve flows, and remaining visual assist helpers such as Measure, clipping, and reference-image calibration state. Keep CAM/FEM as guarded advanced expansions.
- Research and extend Sketcher and PartDesign coverage from both FreeCAD documentation and the local FreeCAD source checkout. PartDesign dress-up features are implemented for Fillet, Chamfer, Thickness, and Draft; basic transform coverage is implemented for LinearPattern, PolarPattern, and Mirrored. Next PartDesign priority is deeper transform coverage such as MultiTransform/Scaled/Boolean only after fixture-backed contracts are clear. Advanced Pipe now has guarded multisection and auxiliary-spine coverage; combined auxiliary-plus-multisection fixtures and deeper scaling/orientation variants should wait for source-backed examples. Include GUI commands where safe through GUI/workbench bridge paths, and add typed wrappers only with source evidence, fixture-backed behavior, and smoke tests.
- Deepen PartDesign transform fixtures beyond the clean two-direction LinearPattern smoke: add subtractive Pocket arrays with explicit cut-count/topology expectations, transformed feature-chain repair cases, and model-specific regression fixtures when a real generated `.FCStd` reproduces a single-row two-direction pattern.
- Generalize overlapping-profile repair beyond the implemented keyhole/circle+slot helper only after a fixture-backed 2D boolean-to-Sketcher contract exists. Do not promise arbitrary overlapping circle/slot/arc/profile union until the extracted loop ordering, native curve preservation, and PartDesign Pocket behavior are smoke-covered.
- Add persistent-worker parity for the process-per-call parameter tools: Spreadsheet creation/reading and object/Sketcher expression set/list, with worker smoke proving a Spreadsheet alias can drive a Sketcher dimension constraint.
- Extend the Spreadsheet unit policy to every direct numeric CAD length/angle input surface, including direct PartDesign feature lengths, Sketcher dimension constraints, and future worker Spreadsheet/expression parity. `freecad_spreadsheet_create` now has `default_unit`/`require_units`; the next step is making the same "ask the user for a unit or mark unitless" contract consistent across all physical-dimension tool schemas.
- Add a compact parametric Sketcher/PartDesign profile builder that creates multi-profile geometry with named driving constraints and Spreadsheet expression bindings in one call. The immediate tester case is socket/hex arrays where Pad/Pocket lengths are expression-driven but many Sketcher points remain numeric because current helpers do not emit named constraints for every profile coordinate.
- Expose a dedicated geometry-check tool that remains visible even while Part primitive tools are hidden from MCP `tools/list`, so agents can run BRep validation without falling back to Body shape summaries.
- Add a guarded GUI command catalog and runner: command list/describe by workbench, active state, tooltip/menu text, source evidence, and allowlisted `freecad_gui_command_run` only after preconditions, transaction/recompute policy, and smoke coverage are clear.
- Bound `StaticToolService.source_search` rglob traversal with a file-count/time limit and early termination so a large FreeCAD source tree cannot hang or time out the tool.
- Push/enable the existing POSIX CI workflow once credentials include the `workflow` OAuth scope, so the `safe_source_path` symlink-escape unit test runs instead of skipping.
- After the generated distribution profiles settle, decide whether any profiles should become separate installable Python packages or Codex plugin bundles; the FreeCAD Workbench path now has a local module zip, but not signed Addon Manager packaging.

## Blocked Or Waiting

- Revisit high-level Sketcher `Group` and `Text` wrappers only after the FreeCAD 1.1.1 constructor crash/typing issue is resolved upstream or a safe API path is found.

## Future Deepening

- Extend CAM/FEM beyond first slice only with fixture-backed job/solver contracts.
- Add TechDraw SVG/PDF export only behind GUI attach or Workbench validation because those APIs live behind `TechDrawGui`.
- Add official-tutorial-driven GUI workflows for scaled reference images, Measure, clipping view, PartDesign-to-TechDraw, and Assembly examples.
- Add higher-level semantic naming helpers: batch label planning, tree-readability linting, and automatic labels for common generated Body/Sketch/Pad/Pocket/Hole/Revolution/Groove patterns.

## Later

- Signed/installed FreeCAD Addon Manager packaging polish for the Workbench-hosted bridge.
- Add a local custom-tool authoring pipeline after the core CAD surface is mature: AI may draft typed recipes or raw scripts, but registration must pass a mandatory security analyzer MCP gate, sandbox smoke test, explicit user approval, hash/audit logging, permission manifest, and safe runtime enforcement before the tool can be enabled. Prefer declarative recipes over raw Python; keep raw-script custom tools local-dev/unsafe only.
