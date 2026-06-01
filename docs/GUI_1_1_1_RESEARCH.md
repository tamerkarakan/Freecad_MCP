# FreeCAD 1.1.1 GUI Research

This note records the current GUI-side product direction for future coding sessions and AI agents. It combines official FreeCAD 1.1/1.1.1 documentation, official blog tutorials, and this repository's local FreeCAD 1.1.1 source-command inventory.

## Sources

Official FreeCAD wiki pages may be protected by the web frontend. Use the official Markdown mirror when automated agents cannot read the live wiki.

| Source | Why it matters |
| --- | --- |
| `https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/` | FreeCAD 1.1 feature announcement: PartDesign previews, interactive draggers, lighting, selection, Assembly/FEM animation, CAM tool library. |
| `https://blog.freecad.org/2026/04/15/freecad-1-1-1-released/` | FreeCAD 1.1.1 is a patch/fix release on top of 1.1. |
| `https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.1` | Official 1.1.1 release changelog and backport list. |
| `https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/README.md` | Confirms the Markdown mirror is official FreeCAD documentation. |
| `https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/wiki/Release_notes_1.1.md` | Workbench-level 1.1 change list. |
| `https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/wiki/Sketcher_Workbench.md` | Sketcher workflow, constraints, profile rules, edit-mode behavior. |
| `https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/wiki/PartDesign_Workbench.md` | Body, sketch attachment, additive/subtractive features, dress-up and transform tools. |
| `https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/wiki/Assembly_Workbench.md` | Built-in Assembly, joints, solver, BOM, simulation/animation workflow. |
| `https://raw.githubusercontent.com/FreeCAD/FreeCAD-documentation/main/wiki/TechDraw_Workbench.md` | Technical drawing pages, views, dimensions, annotations, DXF/SVG/PDF exports. |
| `https://blog.freecad.org/2026/04/12/tutorial-importing-and-using-scaled-reference-images/` | Official GUI tutorial for reference-image calibration and sketch-over-image workflows. |
| `https://blog.freecad.org/2026/05/15/tutorial-tips-for-the-measuring-tool/` | Official 1.1.1 GUI tutorial for persistent measurement workflows. |
| `https://blog.freecad.org/2025/10/10/tutorial-getting-started-with-techdraw/` | Official GUI tutorial for PartDesign-to-TechDraw workflow and export. |

## Local Command Inventory

The local inventory in `docs/freecad_tool_inventory.md` scans 1112 GUI command registrations from FreeCAD commit `dee977f98f8a8542c8db0be2ecc529a771931d01`.

| Workbench or module | Scanned command count | Product meaning |
| --- | ---: | --- |
| `Gui` | 208 | Broad application and view command surface; useful for status, selection, view, command metadata, and safe command boundaries. |
| `BIM` | 147 | Large domain surface, but not the first priority for mechanical 3D engineering. |
| `TechDraw` | 127 | High-value output workflow: pages, views, dimensions, annotations, and exports. |
| `Fem` | 102 | High command richness, but solver and mesh dependencies make mutation risky without fixtures. |
| `Sketcher` | 101 | Core mechanical modeling surface: geometry, constraints, DoF, validation, profile creation. |
| `Draft` | 84 | Important 2D/editing surface; useful later for mixed 2D/3D workflows. |
| `Part` | 75 | Important headless and GUI solid operations. |
| `CAM` | 49 | Valuable manufacturing workflow, but postprocessor/toolbit/job contracts need guarded expansion. |
| `PartDesign` | 41 | Fewer commands than Sketcher/TechDraw, but each command is high-level and workflow-critical. |
| `Assembly` | 31 | Fewer commands, high value; joint workflows depend heavily on GUI selection context. |

Command count is not the same as product value. For mechanical 3D engineering, prioritize workflow leverage over raw count.

## GUI Priority Order

1. `Sketcher + PartDesign`
   - Treat this as the main modeling spine.
   - Agents need active sketch state, edit mode, solver status, DoF, open contour diagnostics, external geometry state, selected geometry, Body activation, plane selection, feature Tip, recompute state, and task-panel-friendly operations.
   - Typed wrappers should remain preferred for deterministic creation, but GUI bridge tools should help the agent observe and steer the same workflow a human sees.

2. `TechDraw`
   - Treat this as the main output/documentation spine.
   - Prioritize GUI-backed SVG/PDF export, projection groups, dimensions, centerlines, sections/details, template fields, and page inspection.
   - Headless DXF exists already; SVG/PDF belongs behind GUI attach or Workbench validation because it uses `TechDrawGui`.

3. `Assembly`
   - Treat this as a selection-driven workflow.
   - Prioritize active assembly detection, insert/link flows, grounded state, joint creation from selected subelements, solve status, BOM, and simulation/animation status.
   - GUI selection records must stay normalized enough to feed typed Assembly tools safely.

4. `Visual Assist`
   - Add lightweight but high-leverage helpers: measure results, clipping view, view orientation, fit, screenshot, reference-image placement/calibration state, and command tooltips.
   - These are not flashy CAD features, but they make an AI agent much better at understanding what is on screen.

5. `CAM/FEM`
   - Keep these as advanced/specialized expansions.
   - Expand only with fixture-backed job/toolbit/postprocessor contracts for CAM and solver/mesh/result contracts for FEM.
   - Default tools should inspect and set up conservative object graphs before executing external solvers or machine-specific output.

## Recommended Next GUI Tools

| Tool family | Suggested tools | Notes |
| --- | --- | --- |
| Command catalog | `freecad_gui_command_list`, `freecad_gui_command_describe`, guarded `freecad_gui_command_run` | List by workbench, active/inactive state, menu text, tooltip, and source evidence. Command execution must be allowlisted. |
| Sketcher state | `freecad_gui_sketch_state`, `freecad_gui_sketch_enter`, `freecad_gui_sketch_leave` | Report active sketch, edit mode, DoF, open vertices, constraints, selected elements, external geometry, and visibility. |
| PartDesign flow | `freecad_gui_partdesign_state`, `freecad_gui_body_activate`, `freecad_gui_feature_task_state` | Focus on Body/plane/sketch/feature Tip and task-panel state before adding more mutation. |
| TechDraw flow | `freecad_gui_techdraw_page_export`, `freecad_gui_techdraw_dimension_create`, `freecad_gui_techdraw_projection_create` | Prioritize SVG/PDF export and selected-view/dimension workflows. |
| Assembly flow | `freecad_gui_assembly_state`, `freecad_gui_assembly_joint_from_selection`, `freecad_gui_assembly_bom_export` | Use normalized selection records; avoid blind broad command execution. |
| Visual assist | `freecad_gui_view_snapshot`, `freecad_gui_measure_get`, `freecad_gui_clipping_state`, `freecad_gui_reference_image_state` | Viewport snapshot is implemented; measure, clipping, and reference-image state remain useful for AI observation, tutorial following, and repair guidance. |

## Example Workflows To Support

### Reference Image To Solid

1. Import or detect a reference image.
2. Calibrate image scale using known points.
3. Create/activate a PartDesign Body.
4. Create a sketch on the correct plane.
5. Trace with Sketcher using line/arc/B-spline intent checks.
6. Validate a closed profile.
7. Pad/Pocket/Revolve into a solid.
8. Inspect dimensions with Measure.
9. Export a TechDraw page if documentation is needed.

### Part To Technical Drawing

1. Select a PartDesign Body or Part object.
2. Create a TechDraw page with a template.
3. Insert projection group or active view.
4. Add dimensions, center marks, sections/details, and annotations.
5. Export DXF headlessly where possible; use GUI attach for SVG/PDF.

### Assembly Joint From GUI Selection

1. Insert or activate components in an Assembly.
2. Read normalized GUI selection records for two compatible subelements.
3. Create a native joint from those references.
4. Solve and report solver status.
5. Generate BOM or animation/simulation state when available.

## Agent Rules

- Read this file before expanding GUI, Sketcher, PartDesign, Assembly, TechDraw, CAM, or FEM behavior.
- Current first slices implemented from this plan: `freecad_gui_view_snapshot`, `freecad_gui_sketch_state`, `freecad_gui_sketch_enter`, `freecad_gui_sketch_leave`, `freecad_gui_partdesign_state`, `freecad_gui_body_activate`, and `freecad_gui_feature_task_state`.
- Prefer typed tools for deterministic model mutation.
- Use GUI attach for observing live user state, selection-driven commands, TechDraw GUI exporters, task panels, and visual helpers.
- Do not add broad GUI command execution as the happy path. If command execution is needed, gate it behind an allowlist, structured preconditions, transactions, recompute, and smoke tests.
- Keep developer aliases full-surface. Product packaging must not restrict local maintainer workflow.
- Update `docs/SESSION_STATE.md`, `docs/BACKLOG.md`, and the relevant plan doc when changing GUI behavior.
