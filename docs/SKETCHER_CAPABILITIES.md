# Sketcher Capabilities

The typed Sketcher MCP surface targets headless `Sketcher::SketchObject` APIs that work through `FreeCADCmd`. GUI command handlers that depend on active view, selection overlays, or edit-mode handlers remain out of scope until GUI attach/workbench bridge mode.

## Tools

| Tool | Capability |
| --- | --- |
| `freecad_sketch_create` | Create a Sketcher object in a new or existing document, optionally inside a PartDesign Body attached to a Body Origin plane, a selected planar face such as `Face1`, a datum, or another support. |
| `freecad_sketch_add_geometry` | Add point, line/line segment, circle/3-point circle, circle arc, ellipse, ellipse arc, hyperbola arc, parabola arc, B-spline, and polyline geometry. It accepts `[x,y]` and `[x,y,z]` coordinate arrays, can optionally connect the submitted endpoint-capable geometry sequence with `Coincident` constraints, close the sequence, and fail before saving when open vertices remain. |
| `freecad_sketch_add_constraint` | Add raw `Sketcher.Constraint` entries with optional name, datum, driving, active, virtual-space, visibility, and label metadata. |
| `freecad_sketch_add_profile` | Add rectangle, rectangle-center, rectangle-3-point, named regular polygons (`triangle` through `octagon`), arbitrary regular polygon, circle, straight slot, oriented slot, arc slot, single-loop keyhole circle+slot, and polyline helper profiles with optional constraints/construction mode. Regular polygons follow the FreeCAD GUI signature with `center` plus `corner`, or the equivalent `center` plus `radius` and `start_angle`, and default to a construction circle plus point-on-circle constraints. Slot helpers avoid redundant equal-arc/tangent constraints by default. |
| `freecad_sketch_profile_create` | Create loop-based pad-ready profiles from ordered line/arc/B-spline segments or safe rectangle/polyline loop helpers; it accepts `[x,y]` and `[x,y,z]` coordinate arrays, rejects endpoint drift before adding constraints, can `Block` geometry, validates face creation, can attach to a PartDesign Body Origin plane, selected planar face, or datum/support object, and can enforce curve-preservation contracts such as required segment types, minimum curve count, and no line/polyline fallback. |
| `freecad_sketch_profile_validate` | Validate existing sketches for pad readiness, isolated points, branch vertices, near-duplicate micro-offset vertices, closed wires, face creation, native geometry type counts, curve intent mismatches, and optional full constraint. |
| `freecad_curve_fit_analyze` | Compare line and circular-arc fit errors for traced points and recommend `line`, `arc`, or `bspline` before creating sketch geometry. |
| `freecad_sketch_geometry_method_catalog` | Report the supported typed creation methods for point, line, circle, circular arc, ellipse, conic arc, B-spline, polyline, helper profiles, transform-created geometry, and analysis tools. |
| `freecad_sketch_edit_geometry` | Delete geometry, delete all geometry, set/toggle construction, add/delete external geometry, carbon-copy, move geometry, expose/delete internal geometry, and detect/remove degenerated geometry. |
| `freecad_sketch_external_projection` | FreeCAD 1.1 GUI-name alias for adding External Projection references from faces, edges, vertices, sketches, or datum/support geometry. Worker parity: `freecad_worker_sketch_external_projection`. |
| `freecad_sketch_external_intersection` | FreeCAD 1.1 GUI-name alias for adding External Intersection references from faces, edges, vertices, sketches, or datum/support geometry. Worker parity: `freecad_worker_sketch_external_intersection`. |
| `freecad_sketch_edit_constraints` | Delete, rename, set/get datum, set/toggle driving, set/toggle active, set/toggle virtual space, set visibility, set label placement, delete point/external constraints, validate constraints, and auto-remove redundants. |
| `freecad_sketch_transform` | Fillet, trim, extend, split, join, copy, move, symmetric copy, rectangular array, remove axes alignment, convert to NURBS, and edit B-spline degree/knots. |
| `freecad_sketch_auto_constrain` | Run autoconstraint and detect/apply missing coincident, vertical/horizontal, and equality constraints. |
| `freecad_sketch_validate` | Solve and report geometry/constraint counts, DoF, open vertices, conflicts, redundants, malformed constraints, missing constraints, dependent geometry, and optional constraint errors. |
| `freecad_object_expression_set` | Bind expressions into Sketcher dimension constraints such as `Constraints[0]`, usually from a Spreadsheet alias like `params.width`. |
| `freecad_object_expression_list` | Read expression bindings back from Sketcher objects. FreeCAD may report a named dimension constraint canonically, e.g. `.Constraints.width`. |

## Constraint Notes

`freecad_sketch_add_constraint` keeps the FreeCAD constructor expressive by accepting either `values` or named fields (`first`, `first_pos`, `second`, `second_pos`, `third`, `third_pos`, `value`). Datum/angle values may be passed as numbers, `{"degrees": 90}`, `{"radians": 1.5708}`, or `{"quantity": "90 deg"}`.

Sketch dimensions are the actual parametric drivers. Spreadsheet cells are useful as named parameters, but they should feed constraints/properties through expressions rather than replacing Sketcher dimensions. A typical typed flow is `freecad_spreadsheet_create` with an alias such as `width`, then `freecad_object_expression_set` on the sketch with `{"Constraints[0]": "params.width"}`. If the constraint has a name, FreeCAD may report the stored expression path as `.Constraints.width`.

`Group` and `Text` constraints are intentionally not given a high-level wrapper yet. In the current FreeCAD 1.1.1 runtime, direct constructor attempts can terminate `FreeCADCmd`, so typed tools block those raw constraint types and smoke-test the safe failure path before a future wrapper is considered.

## Closed Profile Guard

For traced profiles or reference-image outlines, do not add independent line/arc/B-spline items and assume they form a Sketcher profile. Use `freecad_sketch_add_geometry` with `connect_sequence=true`, `close_sequence=true`, and `require_closed=true` when the geometry list is a single ordered closed contour. The tool then adds explicit `Coincident` constraints between adjacent endpoints, closes the final endpoint to the first, solves the sketch, and aborts before saving if `OpenVertices` is not empty.

This guard intentionally does not guess arbitrary nearby endpoints. For branched or multi-loop sketches, create each loop as its own ordered sequence or add explicit `Coincident` constraints with `freecad_sketch_add_constraint`; broad tolerance-based auto-connection can over-constrain the wrong points.

For production-style profiles, prefer `freecad_sketch_profile_create`. It treats each loop as an explicit ordered contour and checks that adjacent endpoints already coincide within `endpoint_tolerance` before adding `Coincident` constraints. This prevents the solver from dragging a visually traced curve into a different shape. When the reference image clearly contains curves, pass a curve contract such as `required_segment_types=["bspline","arc"]`, `minimum_curve_segments`, `forbid_polyline_fallback=true`, and `forbid_all_line_loops=true`; the tool rejects line/polyline approximations instead of accepting a degraded fallback. Segment-level `expected_type` with `fallback_policy="fail"` can also make a specific trace segment fail if the submitted actual geometry is not the intended native type. `freecad_sketch_profile_validate` then verifies the result can create Part faces, has no isolated point geometry, has no branch endpoints, has no tiny near-duplicate endpoint offsets, reports native geometry type counts, and can compare existing geometry indices against declared intent.

For simple rectangular loops, agents may pass a helper loop directly to `freecad_sketch_profile_create`, for example `{"type":"rectangle","origin":[0,0],"width":30,"height":20}`. The tool expands it into four ordered line segments before applying the same endpoint, face, and optional full-constraint validation.

Use `freecad_curve_fit_analyze` before choosing between `arc` and `bspline` when a trace is ambiguous. It fits the submitted points as a line and as a circular arc; if those simpler fits exceed tolerance, it recommends B-spline/freeform instead of letting the agent rely only on visual intuition.

## Arc Method Notes

Circular arcs are exposed through several explicit intent forms: `arc_3_point` / `arc_start_mid_end` for traced start-mid-end input, `arc_start_end_radius` for start/end/radius with requested `side` and `sweep`, and `arc_center_angles` for center/radius/start/end angle input with `direction`. `arc_3_point` should be preferred for reference-image tracing because the midpoint anchors which visual arc FreeCAD must pass through.

`freecad_sketch_add_geometry` and `freecad_sketch_profile_create` now return `geometry_reports` for circular arcs. Each report includes `actual_start`, `actual_end`, `center`, `radius`, `sweep_deg`, and `normal`, so callers can reject a visually plausible but wrong long-arc result immediately.

## Profile Method Notes

FreeCAD GUI exposes rectangle, center rectangle, 3-point rectangle, regular polygon presets, slot, and arc slot as Sketcher create commands. The typed MCP equivalent is `freecad_sketch_add_profile`: `rectangle`, `rectangle_center`, `rectangle_3_point`, `triangle`, `square`, `pentagon`, `hexagon`, `heptagon`, `octagon`, `regular_polygon`, `slot`, `slot_start_end_radius`, `arc_slot`, `keyhole`, `circle`, and `polyline`. Named polygons are aliases for `regular_polygon` with fixed side counts. For polygons, prefer the GUI-style payload `{"type":"hexagon","center":[0,0,0],"corner":[10,0,0]}` or `{"type":"regular_polygon","sides":6,"center":[0,0,0],"corner":[10,0,0]}`. The typed helper adds the construction circumcircle and `PointOnObject` constraints by default; pass `construction_circle=false` only when an intentionally plain equal-edge line loop is needed. For keyhole-like circle+slot cuts, prefer `{"type":"keyhole","circle_center":[3,5,0],"circle_radius":1.5,"slot_end":[7,5,0],"slot_radius":0.5}` instead of overlapping separate circle and slot profiles.

## PartDesign Body Attachment

FreeCAD GUI asks whether to create a Body and which face/plane/support to use before a Sketcher profile can drive PartDesign features. The MCP equivalent is to pass `body_name` and either:

- `attachment_plane` (`XY`, `XZ`, or `YZ`) for Body Origin plane base sketches and independent offsets,
- `attachment_object` plus `attachment_subname` such as `Face1` for the ordinary FreeCAD workflow of sketching directly on a selected planar face before a Hole or Pocket,
- or `attachment_object` pointing at a named datum/support object such as a plane created with `freecad_partdesign_datum_plane_create` for reusable/visible reference geometry, angled/offset support, loft/sweep sections, mirror planes, or explicit user datum workflows.

The tool creates or reuses the Body, adds the sketch to it, sets `AttachmentSupport`, and sets `MapMode="FlatFace"` unless another `attachment_map_mode` is provided. For a hole or pocket on a cube top/side face, attach the sketch to that face, use `freecad_sketch_external_projection` or `freecad_sketch_external_intersection` to reference face edges or vertices when needed, dimension the circle/profile, then call `freecad_partdesign_hole` or `freecad_partdesign_pocket`. `freecad_sketch_edit_geometry` with `add_external` remains available as the lower-level compatibility form.

In FreeCAD 1.1 GUI language, external-reference creation is usually `External Projection` or `External Intersection`; the older `Sketcher External` command page is obsolete. In this MCP codebase the named aliases map to the same underlying external/reference geometry operation while keeping GUI language visible to agents.

Datum geometry is not banned. Datum planes, lines, points, and local coordinate systems live inside a Body and are useful for visible reference indicators, arbitrary mirror planes, reusable offset/angled supports for multiple sketches, revolution/groove axes, loft/sweep section supports, datum chains, and LCS orientation references. A datum plane used only as support for one sketch is basically redundant, and a datum attached to generated faces has the same topological naming risk as a sketch attached to generated faces.

Use `freecad_partdesign_pad` when the intended result is an additive Body solid, `freecad_partdesign_pocket` when an attached sketch should remove material from an existing Body solid, `freecad_partdesign_hole` when a circle sketch should drive a typed hole feature, `freecad_partdesign_revolution` for additive revolved profiles, `freecad_partdesign_groove` for subtractive revolved profiles, Additive/Subtractive Loft/Pipe for multi-sketch or sweep features, `freecad_partdesign_fillet`/`freecad_partdesign_chamfer`/`freecad_partdesign_thickness`/`freecad_partdesign_draft` for Body dress-up features from explicit edge/face selections, and `freecad_partdesign_linear_pattern`/`freecad_partdesign_polar_pattern`/`freecad_partdesign_mirrored` for selected Body feature transforms.

For agents that may not know this FreeCAD workflow, prefer the high-level recipes first: `freecad_partdesign_profile_feature_create` creates and validates a Body-attached profile sketch before Pad/Pocket/Revolution/Groove, and `freecad_partdesign_sweep_feature_create` creates Body-attached profile and spine sketches before Additive/Subtractive Pipe. The lower-level tools remain available when the sketch/supports already exist or when the user needs exact control.

## GUI-Only Boundary

Commands such as Sketcher edit mode, view alignment, overlays, mouse-driven create tools, and selection-driven helpers should be handled by a future GUI attach/workbench bridge. Headless MCP tools should continue to use `Sketcher::SketchObject` methods directly.

## Verification

`scripts/smoke_cad_tools.py` exercises the expanded Sketcher flow with real FreeCAD 1.1.1: advanced geometry, arc creation method catalog/reporting, profile method catalog coverage, rectangle/center rectangle/3-point rectangle/GUI-style regular polygon/slot/keyhole/arc-slot profiles, slot Pad solid validation without redundant constraints, keyhole single-loop Pocket validation, connected closed line/B-spline/arc chains, `[x,y]` coordinate acceptance, rectangle helper loops inside `freecad_sketch_profile_create`, loop-based profile creation/validation, Spreadsheet alias to Sketcher dimension expression binding, native geometry type reporting, segment intent mismatch rejection, endpoint drift rejection, curve-preservation and line-fallback rejection, curve fit recommendation, constraint datum/driving/active update, construction toggling, missing-constraint detection, validation diagnostics, B-spline edits, copy, and move transforms.
