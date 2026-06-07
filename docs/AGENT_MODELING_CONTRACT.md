# Agent Modeling Contract

This project expects AI agents to model FreeCAD work as deterministic CAD intent, not as loose drawing.

## Core Rule

A complex Sketcher profile is primitive geometry plus explicit constraints plus validation. In practical tool terms, that means:

1. primitive geometry,
2. explicit constraints,
3. stable references or returned geometry indices,
4. validation evidence.

If any of those are missing, the agent should treat the result as incomplete.

## Image And Reference Intake

When a task starts from an image, screenshot, drawing, diagram, or other visual reference, the agent must not guess the desired CAD outcome if several interpretations are plausible. Before mutating a document, ask the user which result they expect or call `freecad_modeling_strategy_intake`.

Use these user-facing choices and carry the chosen `modeling_strategy` into Sketcher mutation tools:

- `visual_trace`: visual similarity or silhouette only.
- `editable_parametric_sketch`: a Sketcher model whose dimensions remain editable.
- `manufacturing_partdesign_model`: a Body-based PartDesign model suitable for Pad/Pocket/Hole workflows.
- `sketcher_constraint_rebuild`: rebuild the visible Sketcher constraint logic from primitives.
- `construction_guides_only`: recreate only blue construction/reference geometry; do not claim a pad-ready or fully constrained profile.
- `rough_draft`: fast exploratory geometry with limitations reported.

The MCP server does not interpret the image itself. It enforces an explicit modeling contract: for image/reference work the agent should pass `source_type`, `modeling_strategy`, and `strategy_confirmed=true` to `freecad_sketch_add_geometry`, `freecad_sketch_add_profile`, or `freecad_sketch_profile_create`. If `source_type`/`has_image` marks an image-like task and no strategy is provided, those tools stop before mutation so the user is not left waiting for the wrong kind of model.

If the reference visibly contains Sketcher constraint glyphs, red dimension labels, equality/constraint indexes, or blue construction geometry, the safe default is not `visual_trace`. The agent should ask whether the user wants `sketcher_constraint_rebuild` or `editable_parametric_sketch`, and it should treat construction geometry as construction geometry rather than decoration.

If visible curves could be freeform/B-spline, circular arcs, ellipses, or a mixed set, the agent must ask for `native_curve_intent` before mutation. This MCP profile does not support native B-spline/freeform profile creation. If B-spline/freeform controls are visible, the safe choices are: ask the user for an arc/ellipse-supported reinterpretation, or use `construction_guides_only` and create only construction geometry. Do not approximate unsupported freeform curves with many real lines or polylines.

## Native Geometry Versus Helper Intent

Sketcher helpers are not extra primitive geometry types. The agent should read them as native geometry plus a constraint fingerprint:

- Rectangle: 4 `LineSegment` items plus `Coincident`, `Horizontal`, and `Vertical` constraints.
- Regular polygon/triangle/square/hexagon: `LineSegment` loop plus a construction circle, `PointOnObject`, and `Equal` constraints.
- Slot: 2 `LineSegment` items plus 2 `ArcOfCircle` items with `Coincident`, `Tangent`, and equal/radius constraints.
- Circle: native `Circle` geometry unless native validation says it is an arc chain.
- Existing/imported B-spline: detectable as native `BSplineCurve`, but unsupported for new profile creation in this MCP profile.

When validating an existing sketch, prefer `report_layers.native_geometry`, `report_layers.construction_geometry`, `report_layers.constraint_graph`, and `report_layers.helper_intent_inference` over visual guesswork. Helper intent is an inference layer, not the primitive layer.

## Choose The Right Layer

Use high-level PartDesign or Sketcher profile recipes when the intent is known:

- `rectangle`, `circle`, `regular_polygon`, `hexagon`, `slot`, and `keyhole` should be helper/profile loops.
- `Pad`, `Pocket`, `Revolution`, and `Groove` should normally go through `freecad_partdesign_profile_feature_create` or `freecad_partdesign_parametric_profile_feature_create`.
- Raw primitive geometry is for exact custom contours or when no helper exists.

Do not build common CAD features by overlapping unrelated profiles and hoping FreeCAD will infer the desired union.

## Keyhole And Slot Policy

For a keyhole or circle-slot cut:

- Prefer a single `keyhole` helper loop.
- If the helper is not expressive enough, create one ordered loop with native arcs and lines.
- Use `Coincident`, `Tangent`, `Equal`, radius, width, length, and position constraints as needed.
- Do not model the same intent as an overlapping circle plus rectangle/slot profile.

`trim` is useful for editing or repairing existing sketch geometry. It should not be the first-choice construction method for a new parametric keyhole, slot, or socket profile.

## Parametric Policy

For user-editable or Spreadsheet-driven models:

- Use Sketcher dimensions as the real drivers.
- Use `freecad_sketch_geometry_method_catalog` when unsure which Sketcher constraint type string or argument fields are available; its `constraint_methods` section documents common `Sketcher.Constraint(type, *values)` constructor strings.
- Use Spreadsheet aliases as named parameters feeding expressions into Sketcher constraints and feature properties.
- Prefer `constraint_policy="semantic"` for supported helper loops.
- Prefer `require_fully_constrained=true` when later parameter edits must preserve shape intent.
- Avoid `Block` constraints as a shortcut for parametric profiles.

For example, a rectangle should preserve width and height through named constraints, not by leaving one free edge to move after a Spreadsheet edit. A hex socket should bind the polygon radius or across-flats expression and keep equal sides and center/orientation constraints.

## Validation Policy

After construction, the agent should inspect or report:

- closed profile / open vertices,
- pad-ready or pocket-ready status,
- solver status and degrees of freedom,
- conflicting, redundant, or malformed constraints,
- native geometry type counts when curve intent matters,
- unsupported freeform/B-spline rejection and line/polyline fallback guards when curve intent matters,
- geometry/BRep check for the resulting PartDesign Body when a solid is created.

Do not leave fully-constrained or tangent/equal intent to image interpretation. Use `freecad_sketch_validate` or `freecad_worker_sketch_validate` to get native Sketcher evidence: `fully_constrained`, `degrees_of_freedom`, detailed `geometry`, detailed `constraints`, `semantic_groups` for tangent pairs/chains, equal groups, coincident pairs, dimensional/radius constraints, and construction geometry, plus `report_layers` for native/helper separation.

If validation fails, the agent should repair the sketch or recreate it through a stronger recipe instead of continuing to feature creation.

## Face And Datum Policy

Use Body Origin planes for base sketches. For normal holes or pockets on the top/side of an existing solid, attach the sketch directly to the selected planar `FaceN`, add external/reference geometry from that face's edges or vertices when dimensions need local references, dimension the profile, then call Hole or Pocket.

Use datum planes, lines, points, or LCS only for reusable/named references, offset or angled supports, mirror/revolution axes, loft/sweep sections, visible guide geometry, or explicit user datum workflows. A datum plane used for one sketch is usually redundant.
