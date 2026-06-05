# Agent Modeling Contract

This project expects AI agents to model FreeCAD work as deterministic CAD intent, not as loose drawing.

## Core Rule

A complex Sketcher profile is primitive geometry plus explicit constraints plus validation. In practical tool terms, that means:

1. primitive geometry,
2. explicit constraints,
3. stable references or returned geometry indices,
4. validation evidence.

If any of those are missing, the agent should treat the result as incomplete.

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
- geometry/BRep check for the resulting PartDesign Body when a solid is created.

If validation fails, the agent should repair the sketch or recreate it through a stronger recipe instead of continuing to feature creation.

## Face And Datum Policy

Use Body Origin planes for base sketches. For normal holes or pockets on the top/side of an existing solid, attach the sketch directly to the selected planar `FaceN`, add external/reference geometry from that face's edges or vertices when dimensions need local references, dimension the profile, then call Hole or Pocket.

Use datum planes, lines, points, or LCS only for reusable/named references, offset or angled supports, mirror/revolution axes, loft/sweep sections, visible guide geometry, or explicit user datum workflows. A datum plane used for one sketch is usually redundant.
