# Hybrid MCP Tool Plan

FreeCAD source scan commit: `dee977f98f8a8542c8db0be2ecc529a771931d01`.

The static scan found 1112 GUI command registrations across 26 modules. The MCP server should not expose all of them as separate top-level tools. The safer shape is a small typed core plus a command registry escape hatch.

## P0 Tools

| Tool | Purpose | Backend |
| --- | --- | --- |
| `freecad_source_search` | Search FreeCAD source by text/glob/module. | Git checkout |
| `freecad_source_open` | Read a source file region with line numbers. | Git checkout |
| `freecad_source_symbol_index` | Return indexed command/class/module records. | Generated inventory |
| `freecad_modeling_strategy_intake` | Ask or confirm the expected modeling outcome for image/reference-driven CAD work before sketch mutation. | Static tool contract |
| `freecad_session_start` | Start or attach to a FreeCAD Python runtime. | FreeCAD process |
| `freecad_session_status` | Report process, document, and bridge state. | FreeCAD process |
| `freecad_session_list` | List persistent FreeCAD worker sessions. | FreeCAD process |
| `freecad_session_close` | Close a persistent FreeCAD worker session. | FreeCAD process |
| `freecad_worker_document_new/open/save/recompute/close/export` | Manage and export in-memory worker documents by document id. | FreeCAD process |
| `freecad_worker_partdesign_body_create/datum_plane_create/pad/pocket/hole/revolution/groove/additive_loft/subtractive_loft/additive_pipe/subtractive_pipe/fillet/chamfer/thickness/draft/linear_pattern/polar_pattern/mirrored` | Create Body-based datum, additive, subtractive, multi-sketch, sweep, dress-up, and transform PartDesign features in persistent worker documents. | PartDesign App API |
| `freecad_worker_sketch_create/add_geometry/add_constraint/add_profile/profile_create/profile_validate/edit_geometry/edit_constraints/transform/auto_constrain/validate` | Edit and validate Sketcher objects in persistent worker documents, including loop-based pad-ready profile creation with curve-preservation guards. | Sketcher App API |
| `freecad_worker_mesh_import/export/evaluate/repair/boolean` | Import, export, evaluate, repair, and boolean mesh objects in persistent worker documents. | Mesh module |
| `freecad_worker_assembly_create/insert/create_joint/solve/bom` | Create Assembly containers, links, native joint proxies, recompute, and BOM rows in persistent worker documents. | Assembly module |
| `freecad_worker_object_list/get/set_properties/rename_label/delete` | Inspect and mutate in-memory worker document objects, including user-visible Labels. | FreeCAD process |
| `freecad_gui_attach/list/detach/status/watchdog_status` | Attach to a running FreeCAD GUI loopback bridge, manage GUI bridge sessions, and report heartbeat/watchdog health. | FreeCAD GUI bridge |
| `freecad_gui_active_document_get/active_view_get` | Read the active GUI document and active view/camera snapshot. | FreeCADGui API |
| `freecad_gui_selection_get/preselection_get/selection_set/view_fit/view_snapshot` | Read or set GUI selection/preselection records, fit the active view, and save viewport snapshots for local visual evidence. | FreeCADGui Selection/View API |
| `freecad_python_exec` | Execute controlled Python snippets for diagnostics, with optional compact execution metadata. | FreeCAD process |
| `freecad_document_new` | Create a new FreeCAD document. | FreeCAD API |
| `freecad_document_open` | Open `.FCStd` or importable CAD file. | FreeCAD API |
| `freecad_document_save` | Save active document. | FreeCAD API |
| `freecad_document_recompute` | Recompute document and return errors/warnings. | FreeCAD API |
| `freecad_document_export` | Export selected objects or active document. | FreeCAD API |
| `freecad_object_list` | List objects with labels, types, visibility, placement. | FreeCAD API |
| `freecad_object_get` | Inspect object properties and shape summary. | FreeCAD API |
| `freecad_object_set_properties` | Set validated object properties. | FreeCAD API |
| `freecad_object_rename_label` | Set a user-visible object Label while keeping internal Name stable. | FreeCAD API |
| `freecad_object_delete` | Remove object(s) by stable name. | FreeCAD API |

## P1 Tools

| Tool | Purpose | Evidence |
| --- | --- | --- |
| `freecad_command_list` | List scanned/runtime GUI commands. | 1112 scanned command records |
| `freecad_command_describe` | Return menu text, tooltip, module, source ref. | `docs/freecad_tool_inventory.json` |
| `freecad_command_run` | Run a named FreeCAD GUI command when a typed wrapper is missing. | Command registry |
| `freecad_partdesign_body_create` | Create or reuse a PartDesign Body with origin planes. | PartDesign App API |
| `freecad_partdesign_datum_plane_create` | Create a PartDesign datum plane inside a Body, attached to an origin plane or support object with optional offset. | PartDesign App API |
| `freecad_partdesign_pad` | Create a PartDesign Pad from a Sketcher profile inside a Body, attaching to `XY`/`XZ`/`YZ` when needed. | PartDesign App API |
| `freecad_partdesign_pocket` | Create a PartDesign Pocket that removes material from an existing Body solid using a Sketcher profile. | PartDesign App API |
| `freecad_partdesign_hole` | Create a plain PartDesign Hole from a Sketcher circle profile inside an existing Body solid. | PartDesign App API |
| `freecad_partdesign_revolution` | Create an additive PartDesign Revolution from a Sketcher profile around a sketch or document axis. | PartDesign App API |
| `freecad_partdesign_groove` | Create a subtractive PartDesign Groove from a Sketcher profile around a sketch or document axis. | PartDesign App API |
| `freecad_partdesign_additive_loft` | Create an additive PartDesign Loft from a profile sketch and one or more section sketches in a Body. | PartDesign App API |
| `freecad_partdesign_subtractive_loft` | Create a subtractive PartDesign Loft from a profile sketch and one or more section sketches in an existing Body solid. | PartDesign App API |
| `freecad_partdesign_additive_pipe` | Create an additive PartDesign Pipe by sweeping a profile sketch along a spine/path sketch in a Body, with guarded multisection and auxiliary-spine options. | PartDesign App API |
| `freecad_partdesign_subtractive_pipe` | Create a subtractive PartDesign Pipe by sweeping a profile sketch along a spine/path sketch in an existing Body solid, with the same guarded Pipe options. | PartDesign App API |
| `freecad_partdesign_fillet` | Create a PartDesign Fillet dress-up from selected base edges/faces or all edges of an existing Body solid. | PartDesign App API |
| `freecad_partdesign_chamfer` | Create a PartDesign Chamfer dress-up from selected base edges/faces or all edges of an existing Body solid. | PartDesign App API |
| `freecad_partdesign_thickness` | Create a PartDesign Thickness dress-up from selected base faces of an existing Body solid. | PartDesign App API |
| `freecad_partdesign_draft` | Create a PartDesign Draft dress-up from selected base faces plus neutral-plane and pull-direction references. | PartDesign App API |
| `freecad_partdesign_linear_pattern` | Create a PartDesign LinearPattern transform from selected Body features or the whole Body shape. | PartDesign App API |
| `freecad_partdesign_profile_feature_create` | Recipe tool: create/validate a Body-attached profile sketch, then Pad/Pocket/Revolution/Groove. | Existing typed Sketcher + PartDesign tools |
| `freecad_partdesign_parametric_profile_feature_create` | Compact recipe tool: create Spreadsheet parameters, Body-attached profile loops, named Sketcher driving constraints, sketch/feature expression bindings, then Pad/Pocket/Revolution/Groove. | Existing typed Spreadsheet + Sketcher + PartDesign tools |
| `freecad_partdesign_sweep_feature_create` | Recipe tool: create Body-attached profile and spine sketches, then Additive/Subtractive Pipe sweep. | Existing typed Sketcher + PartDesign tools |
| `freecad_partdesign_polar_pattern` | Create a PartDesign PolarPattern transform from selected Body features or the whole Body shape. | PartDesign App API |
| `freecad_partdesign_mirrored` | Create a PartDesign Mirrored transform from selected Body features or the whole Body shape. | PartDesign App API |
| `freecad_sketch_create` | Create a Sketcher object, optionally inside a PartDesign Body attached to an origin plane, planar face/subelement, or datum/support object. | Sketcher + PartDesign App API |
| `freecad_sketch_add_geometry` | Add point, line, circle, multiple circular arc intent forms, ellipse/conic arc, B-spline, and polyline geometry, with optional ordered-chain Coincident constraints, closed-profile validation, circular-arc actual geometry reports, and image/reference modeling strategy gate fields. | Sketcher App API |
| `freecad_sketch_add_constraint` | Add raw Sketcher constraints by passing the provided type string to `Sketcher.Constraint(type, *values)`, with datum/driving/active/visibility metadata and `Group`/`Text` blocked for safety. | Sketcher App API |
| `freecad_sketch_add_profile` | Add helper profiles such as rectangle variants, named/arbitrary regular polygons, circle, straight/oriented/arc slots, and polyline, with image/reference modeling strategy gate fields. | Sketcher App API |
| `freecad_sketch_profile_create` | Create loop-based pad-ready profiles from ordered line/arc/B-spline segments or helper loops such as rectangle, circle, regular polygon/hexagon, slot, and keyhole, with endpoint drift rejection, curve-preservation contracts, semantic named constraints, optional non-parametric Block constraints, image/reference modeling strategy gate fields, and optional PartDesign Body origin-plane, planar face/subelement, or datum/support attachment. | Sketcher + PartDesign App API |
| `freecad_sketch_profile_validate` | Validate sketch pad-readiness with closed-wire, Part face, isolated point, branch endpoint, micro-offset, native geometry type, intent-mismatch checks, and optional modeling strategy report. | Sketcher + Part App API |
| `freecad_curve_fit_analyze` | Compare line and circular-arc fit errors for traced points and recommend line, arc, or B-spline before sketch creation. | Geometry analysis |
| `freecad_sketch_geometry_method_catalog` | List supported typed Sketcher creation methods, profile helpers, common `Sketcher.Constraint` type strings/field shapes, and transform-generated geometry. | Tool metadata |
| `freecad_sketch_edit_geometry` | Delete/move geometry, toggle construction, add/delete external geometry, carbon-copy, and maintain internal/degenerated geometry. | Sketcher App API |
| `freecad_sketch_edit_constraints` | Delete/rename/update constraints, set datum/driving/active/virtual/visibility state, and clean redundant/invalid constraints. | Sketcher App API |
| `freecad_sketch_transform` | Apply fillet/trim/extend/split/join/copy/move/symmetry/array and B-spline transform operations. | Sketcher App API |
| `freecad_sketch_auto_constrain` | Detect/apply missing coincident, horizontal/vertical, equality constraints and run autoconstraint. | Sketcher App API |
| `freecad_sketch_validate` | Solve and summarize fully constrained/DoF state, native geometry details, constraint refs, semantic tangent/equal groups, report layers for native geometry/construction geometry/constraint graph/helper-intent inference, missing constraints, open vertices, dependency, and per-constraint errors. | Sketcher validation API |

## P2 Tools

| Tool | Purpose | Evidence |
| --- | --- | --- |
| `freecad_mesh_import` | Import mesh formats. | Mesh import command |
| `freecad_mesh_export` | Export mesh object(s). | Mesh export command |
| `freecad_mesh_evaluate` | Analyze mesh quality/solidness. | Mesh evaluation commands |
| `freecad_mesh_repair` | Repair holes, normals, components where possible. | Mesh repair commands |
| `freecad_mesh_boolean` | Mesh union/difference/intersection. | Mesh boolean commands |
| `freecad_assembly_create` | Create assembly container. | Assembly commands |
| `freecad_assembly_insert` | Insert part/link into assembly. | Assembly insert commands |
| `freecad_assembly_create_joint` | Create fixed/revolute/slider/etc. joints. | Assembly joint commands |
| `freecad_assembly_solve` | Solve active assembly. | `Assembly_SolveAssembly` |
| `freecad_assembly_bom` | Generate bill of materials. | `Assembly_CreateBom` |
| `freecad_techdraw_page_create` | Create a TechDraw page and optional SVG template. | `TechDraw::DrawPage`, `TechDraw::DrawSVGTemplate` |
| `freecad_techdraw_view_create` | Create a TechDraw part view from document source objects. | `TechDraw::DrawViewPart`, `DrawPage.addView` |
| `freecad_techdraw_inspect` | Inspect TechDraw pages, views, and source object links. | TechDraw App object graph |
| `freecad_techdraw_page_export` | Export a TechDraw page as DXF in headless mode. | `TechDraw.writeDXFPage` |
| `freecad_cam_path_create` | Create a simple CAM path from explicit command specs. | `Path.Command`, `Path.Path`, `Path::Feature` |
| `freecad_cam_path_inspect` | Inspect CAM path commands. | `Path::Feature.Path.Commands` |
| `freecad_cam_path_export` | Export raw path G-code without postprocessor execution. | `Path.Path.toGCode` |
| `freecad_fem_analysis_create` | Create a FEM analysis container. | `ObjectsFem.makeAnalysis` |
| `freecad_fem_material_create` | Create a FEM material and add it to an analysis. | `ObjectsFem.makeMaterialSolid` |
| `freecad_fem_constraint_create` | Create fixed/force constraints and add them to an analysis. | `ObjectsFem.makeConstraintFixed`, `ObjectsFem.makeConstraintForce` |
| `freecad_fem_inspect` | Inspect analysis membership, materials, constraints, and references. | FEM object graph |
| `freecad_import_file` | Import CAD file into active document. | Import/Part/Mesh commands |
| `freecad_export_file` | Export selected/all objects. | Import/Part/Mesh commands |
| `freecad_supported_formats` | Report detected import/export formats. | Source/runtime registry |

## Implementation Notes

- Typed tools should call FreeCAD Python APIs directly where possible.
- Part primitive/boolean/extrude/revolve/fillet/chamfer/check tools remain implemented internally but are hidden from the advertised MCP surface while Sketcher + PartDesign maturity is the product focus.
- `freecad_command_run` is an escape hatch, not the primary interface.
- Every mutating runtime tool should return a structured document/object diff.
- Source tools can work without FreeCAD installed; runtime tools require a configured FreeCAD executable.
- GUI attach is opt-in and requires `scripts/freecad_gui_bridge_server.py` or the FreeCAD MCP Workbench-hosted bridge inside FreeCAD GUI.
