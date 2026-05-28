# Sketcher Capabilities

The typed Sketcher MCP surface targets headless `Sketcher::SketchObject` APIs that work through `FreeCADCmd`. GUI command handlers that depend on active view, selection overlays, or edit-mode handlers remain out of scope until GUI attach/workbench bridge mode.

## Tools

| Tool | Capability |
| --- | --- |
| `freecad_sketch_create` | Create a Sketcher object in a new or existing document. |
| `freecad_sketch_add_geometry` | Add point, line/line segment, circle/3-point circle, circle arc, ellipse, ellipse arc, hyperbola arc, parabola arc, B-spline, and polyline geometry. It can optionally connect the submitted endpoint-capable geometry sequence with `Coincident` constraints, close the sequence, and fail before saving when open vertices remain. |
| `freecad_sketch_add_constraint` | Add raw `Sketcher.Constraint` entries with optional name, datum, driving, active, virtual-space, visibility, and label metadata. |
| `freecad_sketch_add_profile` | Add rectangle, polyline, regular polygon, circle, and slot helper profiles with optional constraints/construction mode. |
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

## GUI-Only Boundary

Commands such as Sketcher edit mode, view alignment, overlays, mouse-driven create tools, and selection-driven helpers should be handled by a future GUI attach/workbench bridge. Headless MCP tools should continue to use `Sketcher::SketchObject` methods directly.

## Verification

`scripts/smoke_cad_tools.py` exercises the expanded Sketcher flow with real FreeCAD 1.1.1: advanced geometry, connected closed line/B-spline/arc chains, rectangle profile, constraint datum/driving/active update, construction toggling, missing-constraint detection, validation diagnostics, B-spline edits, copy, and move transforms.
