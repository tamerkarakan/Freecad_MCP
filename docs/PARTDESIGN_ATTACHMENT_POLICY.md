# PartDesign Attachment Policy

This project should model the way FreeCAD users actually work, not only the cleanest headless graph.

## Attachment Choices

Use three normal attachment paths:

1. **Body Origin plane**
   - Use `XY`, `XZ`, or `YZ` for base sketches, symmetric base profiles, and simple independent offsets.
   - In the GUI the Body Origin is hidden by default; users may need to show it before selecting origin planes manually. MCP tools can address those planes directly.
   - `attachment_offset` and `attachment_offset_vector` are local to the selected support; for datum planes and sketch attachments the local Z offset is along the support normal.

2. **Planar generated face**
   - This is a common FreeCAD workflow for holes and pockets on an existing cube/top/side face.
   - Attach the sketch to the selected planar face with `attachment_object=<Body Tip or feature>` and `attachment_subname="FaceN"`.
   - Add external/reference geometry from face edges or vertices when the sketch needs local distances. In the FreeCAD 1.1 GUI this is usually External Projection or External Intersection. With typed MCP tools, use `freecad_sketch_edit_geometry` operation `add_external` with `object_name` and `sub_name` such as `Edge1`, `Vertex1`, or a selected reference.
   - Dimension the circle/profile, then call `freecad_partdesign_hole` or `freecad_partdesign_pocket`.
   - Use face attachment when the user explicitly selected that face or the design intent is local to that face. For robust parametric models, prefer Body Origin planes, master sketches, or datums attached to origin planes when those can express the same intent.

3. **Datum geometry**
   - Datum planes, datum lines, datum points, and local coordinate systems live inside a PartDesign Body.
   - Use datums for arbitrary mirror planes, visible reference indicators, reusable offset/angled supports for multiple sketches, loft/sweep section supports, revolution/groove axes, datum chains, and LCS orientation references.
   - A datum plane used only as support for one sketch is basically redundant; attach the sketch directly to the origin plane or face when that is clearer.
   - A datum attached to generated faces has the same topological naming risk as a sketch attached to generated faces. It does not magically make a face reference stable.
   - Datum points are references for sketches or other datum geometry, but should not be used as Pipe/Loft sections.

## External References

FreeCAD 1.1 split the older Sketcher External command into External Projection and External Intersection. The MCP typed operation is currently named `add_external`; treat that as the API-level operation for adding external/reference geometry, not as a claim that the old GUI command is still present.

Prefer references to sketches or master sketches when possible. Generated solid faces and edges are sometimes the correct practical choice, but they are less stable under large topology changes.

## Feature Notes

- `Hole` uses sketch circle and arc centers to place holes; the sketch radii are not the final hole diameters. Set the hole `diameter` explicitly.
- `Hole` and `Pocket` follow the sketch or face normal. If the operation appears to cut away from the solid, check `reversed` or attach the sketch to the opposite face.
- `Pocket` can cut from a sketch or from one or more selected Body faces, and `Up to face` may reference a Body face or datum plane.
- PartDesign Bodies normally model one contiguous solid. Make sure subtractive/additive features remain connected unless a deliberate compound-body workflow is being used.

## Topological Naming

Face-attached sketches are normal FreeCAD practice, especially for mechanical holes and pockets. They are still sensitive to topology changes. If upstream features are likely to reorder faces, prefer a more stable Body Origin or datum-based construction, or refresh the face reference from GUI selection/inspection before continuing.

Do not turn this into a blanket rule against face sketches. The correct agent behavior is:

- Base feature: Body Origin plane.
- Hole or pocket on an existing planar face selected by the user: face-attached sketch, then external projection/intersection references for edge/vertex distances.
- Robust parametric model with expected later edits: master sketch, Body Origin plane, sketch-to-sketch references, or datum attached to origin plane.
- Reused visible offset/angle plane, mirror plane, loft/sweep section, or named design reference: datum.
- Ambiguous selected face/edge/vertex: use GUI selection tools or object/shape summaries to capture the exact `FaceN`/`EdgeN` before mutating.

## Source Notes

This policy is cross-checked against the local FreeCAD-Documentation-Project snapshot. See `docs/FREECAD_WIKI_RESEARCH.md` for the compact source index and agent-facing interpretation.
