# Sketcher Capabilities

The typed Sketcher MCP surface targets headless `Sketcher::SketchObject` APIs that work through `FreeCADCmd`. GUI command handlers that depend on active view, selection overlays, or edit-mode handlers remain out of scope until GUI attach/workbench bridge mode.

## Tools

| Tool | Capability |
| --- | --- |
| `freecad_sketch_create` | Create a Sketcher object in a new or existing document. |
| `freecad_sketch_add_geometry` | Add point, line/line segment, circle/3-point circle, circle arc, ellipse, ellipse arc, hyperbola arc, parabola arc, B-spline, and polyline geometry. It can optionally connect the submitted endpoint-capable geometry sequence with `Coincident` constraints, close the sequence, and fail before saving when open vertices remain. |
| `freecad_sketch_add_constraint` | Add raw `Sketcher.Constraint` entries with optional name, datum, driving, active, virtual-space, visibility, and label metadata. |
| `freecad_sketch_add_profile` | Add rectangle, polyline, regular polygon, circle, and slot helper profiles with optional constraints/construction mode. |
| `freecad_sketch_profile_create` | Create loop-based pad-ready profiles from ordered line/arc/B-spline segments; it rejects endpoint drift before adding constraints, can `Block` geometry, validates face creation, and can enforce curve-preservation contracts such as required segment types, minimum curve count, and no line/polyline fallback. |
| `freecad_sketch_profile_validate` | Validate existing sketches for pad readiness, isolated points, branch vertices, near-duplicate micro-offset vertices, closed wires, face creation, and optional full constraint. |
| `freecad_sketch_edit_geometry` | Delete geometry, delete all geometry, set/toggle construction, add/delete external geometry, carbon-copy, move geometry, expose/delete internal geometry, and detect/remove degenerated geometry. |
| `freecad_sketch_edit_constraints` | Delete, rename, set/get datum, set/toggle driving, set/toggle active, set/toggle virtual space, set visibility, set label placement, delete point/external constraints, validate constraints, and auto-remove redundants. |
| `freecad_sketch_transform` | Fillet, trim, extend, split, join, copy, move, symmetric copy, rectangular array, remove axes alignment, convert to NURBS, and edit B-spline degree/knots. |
| `freecad_sketch_auto_constrain` | Run autoconstraint and detect/apply missing coincident, vertical/horizontal, and equality constraints. |
| `freecad_sketch_validate` | Solve and report geometry/constraint counts, DoF, open vertices, conflicts, redundants, malformed constraints, missing constraints, dependent geometry, and optional constraint errors. |

## Constraint Notes

`freecad_sketch_add_constraint` keeps the FreeCAD constructor expressive by accepting either `values` or named fields (`first`, `first_pos`, `second`, `second_pos`, `third`, `third_pos`, `value`). Datum/angle values may be passed as numbers, `{"degrees": 90}`, `{"radians": 1.5708}`, or `{"quantity": "90 deg"}`.

`Group` and `Text` constraints are intentionally not given a high-level wrapper yet. In the current FreeCAD 1.1.1 runtime, direct constructor attempts can terminate `FreeCADCmd`, so typed tools block those raw constraint types and smoke-test the safe failure path before a future wrapper is considered.

## Closed Profile Guard

For traced profiles or reference-image outlines, do not add independent line/arc/B-spline items and assume they form a Sketcher profile. Use `freecad_sketch_add_geometry` with `connect_sequence=true`, `close_sequence=true`, and `require_closed=true` when the geometry list is a single ordered closed contour. The tool then adds explicit `Coincident` constraints between adjacent endpoints, closes the final endpoint to the first, solves the sketch, and aborts before saving if `OpenVertices` is not empty.

This guard intentionally does not guess arbitrary nearby endpoints. For branched or multi-loop sketches, create each loop as its own ordered sequence or add explicit `Coincident` constraints with `freecad_sketch_add_constraint`; broad tolerance-based auto-connection can over-constrain the wrong points.

For production-style profiles, prefer `freecad_sketch_profile_create`. It treats each loop as an explicit ordered contour and checks that adjacent endpoints already coincide within `endpoint_tolerance` before adding `Coincident` constraints. This prevents the solver from dragging a visually traced curve into a different shape. When the reference image clearly contains curves, pass a curve contract such as `required_segment_types=["bspline","arc"]`, `minimum_curve_segments`, `forbid_polyline_fallback=true`, and `forbid_all_line_loops=true`; the tool rejects line/polyline approximations instead of accepting a degraded fallback. `freecad_sketch_profile_validate` then verifies the result can create Part faces, has no isolated point geometry, has no branch endpoints, and has no tiny near-duplicate endpoint offsets when the no-cheat guards are enabled.

## GUI-Only Boundary

Commands such as Sketcher edit mode, view alignment, overlays, mouse-driven create tools, and selection-driven helpers should be handled by a future GUI attach/workbench bridge. Headless MCP tools should continue to use `Sketcher::SketchObject` methods directly.

## Verification

`scripts/smoke_cad_tools.py` exercises the expanded Sketcher flow with real FreeCAD 1.1.1: advanced geometry, connected closed line/B-spline/arc chains, loop-based profile creation/validation, endpoint drift rejection, curve-preservation and line-fallback rejection, rectangle profile, constraint datum/driving/active update, construction toggling, missing-constraint detection, validation diagnostics, B-spline edits, copy, and move transforms.
