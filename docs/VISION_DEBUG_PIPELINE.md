# Vision Debug Pipeline

This policy applies when an agent uses FreeCAD GUI screenshots or viewport captures for debugging, visual QA, sketch tracing, selection checks, or live drawing review.

## Default Rule

Do not stream full-screen GUI screenshots by default. Capture screenshots locally for evidence, then send only the smallest useful visual input to a vision-capable model when text logs, structured tool results, selection records, or geometry reports are insufficient.

## Model And Detail Policy

1. Start with structured MCP data first: document/object summaries, Sketcher validation, geometry reports, selection records, console/log output, and tool errors.
2. For coarse GUI state checks, use the cheapest available vision model that can reliably identify UI state, with low detail.
3. For minimum reliable FreeCAD GUI debugging, use a small/mini vision-capable model with low detail first.
4. For sketch/constraint/selection/edge-face inspection, crop the relevant viewport or panel and use high detail only for that crop.
5. For ambiguous CAD intent such as B-spline vs circular arc vs polyline, do not silently decide from one screenshot. Produce a short uncertainty report and ask the user or request a tighter crop/reference.
6. Use a stronger model only after the mini-model result is uncertain, contradictory, or would drive an irreversible modeling decision.

## Screenshot Budget Rules

- Prefer viewport crop over full-screen capture.
- Prefer low detail unless the task depends on small geometry, constraint markers, labels, selected edges/faces, or curve shape.
- Prefer event-based snapshots over periodic streaming.
- Avoid original-resolution screenshots unless a high-detail crop still cannot resolve the issue.
- Save local screenshots and include their paths in reports instead of repeatedly re-sending the same image.
- Before cost-sensitive runs, verify current API pricing because model names and image token accounting can change.

## FreeCAD-Specific Ambiguity Rules

- Green Sketcher geometry alone is not enough evidence that a traced profile is pad-ready; also require `freecad_sketch_profile_validate` or equivalent structured validation.
- If a reference image may contain both arcs and B-splines, ask for the intended native geometry or use `freecad_curve_fit_analyze` on trace points before creating geometry.
- If the agent falls back from B-spline/arc to line/polyline, the fallback must be explicit and accepted by the user or by a tool contract that permits it.
- For arc creation, prefer intent-specific methods such as `arc_3_point`, `arc_start_end_radius`, or `arc_center_angles`, then inspect `geometry_reports`.
- For GUI selection debugging, prefer `freecad_gui_selection_get` and `freecad_gui_preselection_get` before visual screenshot interpretation.

## Programmatic GUI Plus Screenshot Checks

For repeatable GUI validation, prefer programmatic GUI actions first and screenshot/vision checks second. For example, enter Sketcher edit mode with `freecad_gui_sketch_enter`, assert `freecad_gui_sketch_state.edit.in_edit=true` and the expected sketch name, then capture the FreeCAD window as visual evidence.

Agent-side Windows control such as Computer Use is appropriate for this visual verification layer because it can capture the actual FreeCAD window without adding a runtime dependency to this repository. Do not make repo tests depend on Codex-only UI automation. Keep it as an opt-in agent validation path for live GUI sessions.

Use screenshots to verify coarse UI facts: active workbench cues, visible task panels, modal dialogs, selected/highlighted objects, and whether the viewport visibly changed after a programmatic action. Use structured FreeCAD state for exact facts: active edit object, selected subelements, Sketcher DoF, open vertices, topology counts, Body Tip, and export paths.

## Recommended Flow

1. Collect structured state with MCP tools.
2. Mutate GUI state only through narrow tools such as `freecad_gui_sketch_enter`, `freecad_gui_sketch_leave`, `freecad_gui_body_activate`, or selection/view tools.
3. Re-read structured state and assert the expected edit/selection/body/task state.
4. Capture a local screenshot only if visual confirmation is useful or structured state is insufficient.
5. Send a low-detail viewport crop to the minimum reliable vision model.
6. If uncertain, send a high-detail crop of only the relevant region.
7. If CAD intent is still ambiguous, ask the user a direct question before mutating the model.
8. Record the screenshot path, model/detail choice, and decision reason in the debug report.
