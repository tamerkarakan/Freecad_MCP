# FreeCAD Wiki Research Notes

This note summarizes a local FreeCAD-Documentation-Project snapshot for agent-facing MCP behavior. It is not a copy of the wiki text; use it as a compact source index and design interpretation.

Reviewed scope: English root `wiki/*.wikitext` pages for Sketcher, PartDesign, Attachment, Datum geometry, feature editing, and topological naming.

## Key Agent Takeaways

1. **PartDesign starts with an active Body.**
   A Body is the PartDesign container for one main contiguous solid. Its Origin contains XY, XZ, and YZ planes and axes that are stable references for sketches, datums, and primitive features.

2. **PartDesign New Sketch is preferred inside PartDesign.**
   The PartDesign sketch command creates or uses a Body, opens Sketcher edit mode, and lets the user choose an attachment. If a plane or planar face of the active Body is selected first, the sketch is created there directly.

3. **Face-attached sketches are normal but not the most stable default.**
   A face-attached sketch is a real FreeCAD workflow for local pockets, pads, and holes on existing faces. It is also vulnerable to topological naming if the upstream feature changes and the referenced face/edge/vertex is renamed. The agent should treat a selected face as user intent, but for robust parametric design it should prefer Body Origin planes, master sketches, or datums attached to origin planes.

4. **External geometry has GUI names and typed-tool names.**
   In FreeCAD 1.1 the old Sketcher External command is obsolete. GUI users see External Projection and External Intersection. MCP now exposes explicit `freecad_sketch_external_projection` and `freecad_sketch_external_intersection` aliases while keeping the lower-level `freecad_sketch_edit_geometry` `add_external` operation for compatibility.

5. **Prefer sketch/master references over generated solid references when practical.**
   The wiki repeatedly warns that generated solid faces/edges are less stable. Sketch references, master sketches, ShapeBinders/SubShapeBinders from stable sketch geometry, Body Origin references, and datums attached to origin planes are better for models expected to survive large parameter edits.

6. **Datum planes are not a blanket replacement for face sketches.**
   Datum planes are useful for reused offset or angled supports, visual references, mirror planes, loft/sweep sections, datum chains, and shared reference geometry. For one sketch they can be redundant because sketches have attachment and offset options too. A datum attached to generated geometry still inherits topological naming risk.

7. **Hole has special sketch semantics.**
   The Hole feature uses selected sketch circles and arcs to place holes. Circle or arc centers place the holes, while the sketch radii are not the final hole diameters. Non-circle geometry is ignored for hole creation but may still need to participate in closed contours if arcs are present.

8. **Direction matters for Hole and Pocket.**
   Pocket and Hole use the sketch or face normal and may require `reversed` when the feature cuts away from the solid. A sketch on an origin plane can produce no visible hole if the cut goes away from the Body; attaching to the proper face or setting reversed is the practical fix.

9. **Profile sketches must be closed and actually connected.**
   Visual contact is not enough. Endpoints must be coincident, no gaps are allowed, and full constraint is preferred for parametric work even if PartDesign can consume a merely closed profile.

10. **Use fewer dimensions when geometry constraints express intent.**
    Sketcher tutorial material favors geometric constraints plus a smaller set of dimensional constraints. Named driving dimensional constraints are especially useful when dimensions must be reused in expressions.

## Source Index

| Wiki page | Used for |
| --- | --- |
| `wiki/PartDesign_Workbench.wikitext` | Body-based cumulative feature workflow; New Sketch on selected face/plane; Pad/Pocket/Hole/Loft/Pipe command roles. |
| `wiki/PartDesign_Body.wikitext` | Body, Origin, active Body, Tip visibility, single contiguous solid, Base Feature. |
| `wiki/PartDesign_NewSketch.wikitext` | PartDesign sketch creation, selected face/plane behavior, Map Mode, cross-reference options. |
| `wiki/PartDesign_Pad.wikitext` | Pad can extrude a sketch or face. |
| `wiki/PartDesign_Pocket.wikitext` | Pocket can cut from a sketch or face; face-normal direction; Up to face/datum support. |
| `wiki/PartDesign_Hole.wikitext` | Hole uses circles/arcs for hole centers, supports through-all, diameter/depth parameters, and `reversed` direction behavior. |
| `wiki/PartDesign_Plane.wikitext` | Datum plane usage, local offset axes, redundancy for one sketch, topological naming limitation. |
| `wiki/PartDesign_Line.wikitext` | Datum line as revolution/groove axis reference. |
| `wiki/PartDesign_Point.wikitext` | Datum point as reference geometry, with Pipe/Loft limitation. |
| `wiki/PartDesign_CoordinateSystem.wikitext` | Local coordinate system as orientation/reference datum. |
| `wiki/Sketcher_Workbench.wikitext` | Sketcher role, profile-sketch rules, constraints, Validate Sketch, attach/reorient tools. |
| `wiki/Sketcher_Projection.wikitext` | FreeCAD 1.1 External Projection GUI command and face/edge/vertex projection behavior. |
| `wiki/Sketcher_Intersection.wikitext` | FreeCAD 1.1 External Intersection GUI command and face/edge intersection behavior. |
| `wiki/Sketcher_External.wikitext` | Old external-geometry command, obsolete in 1.1, plus same-coordinate and stable-reference notes. |
| `wiki/Sketcher_requirement_for_a_sketch.wikitext` | Closed profile and coincident endpoint requirements. |
| `wiki/Sketcher_Micro_Tutorial_-_Constraint_Practices.wikitext` | Prefer geometric constraints where possible; reduce unnecessary datum constraints. |
| `wiki/Basic_Part_Design_Tutorial_019.wikitext` | Master sketch, named constraints, and stable external-reference practice. |
| `wiki/Basic_Part_Design_Tutorial.wikitext` | Face-local sketch plus external geometry workflow for pocket/pad operations. |
| `wiki/Basic_Attachment_Tutorial.wikitext` | Attachment as linked placement, attachment offsets, and sketch-to-sketch/stable reference workflow. |
| `wiki/Feature_editing.wikitext` | Stable modeling guidance: active Body, Origin references, datum usage, avoid generated geometry where possible. |
| `wiki/Topological_naming_problem.wikitext` | Face/edge/vertex support breakage, remapping, datum/origin alternatives, 1.0+ naming algorithm limits. |

## MCP Design Implications

- Keep typed PartDesign routes centered on Sketcher plus PartDesign features, not standalone Part primitives.
- Keep face attachment available because it is normal FreeCAD usage and matches user selection intent.
- Use `freecad_sketch_external_projection` and `freecad_sketch_external_intersection` when an agent is mapping from the FreeCAD 1.1 GUI names. Keep `freecad_sketch_edit_geometry` `add_external` as the lower-level compatibility path.
- When the user asks for a robust parametric model, the agent should favor master sketches, named constraints, Body Origin attachments, and datums attached to origin planes.
- When the user asks to modify a selected face, the agent may use face attachment but should capture exact `FaceN`/`EdgeN` evidence from GUI selection or shape inspection.
- When a feature appears to do nothing, inspect normal direction and `reversed` before assuming sketch failure.
