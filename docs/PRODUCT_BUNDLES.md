# Product Bundles

Generated sellable bundle manifest for the current MCP tool surface.

| Bundle | Profile | Kind | Tools | Modules | Position |
| --- | --- | --- | ---: | --- | --- |
| FreeCAD MCP Free | `free` | base | 23 | `core`, `headless` | Static command inventory, runtime discovery, and process-per-call document/object/Part operations. |
| FreeCAD MCP Pro | `pro` | paid | 79 | `assembly`, `core`, `gui`, `headless`, `mesh`, `partdesign`, `sketcher` | Adds GUI attach plus Sketcher, PartDesign datum/feature, mesh, and Assembly typed tools. |
| FreeCAD MCP Studio | `studio` | paid | 151 | `assembly`, `cam`, `core`, `fem`, `gui`, `headless`, `mesh`, `partdesign`, `sketcher`, `techdraw`, `worker` | Adds persistent FreeCADCmd worker sessions plus TechDraw, CAM, and FEM first slices. |
| FreeCAD MCP Team | `team` | paid | 154 | `assembly`, `cam`, `core`, `developer`, `fem`, `gui`, `headless`, `mesh`, `partdesign`, `sketcher`, `techdraw`, `worker` | Studio surface plus source-intelligence tools for implementation research and support. |
| Source Intelligence Add-on | `source` | add-on | 5 | `developer` | Command inventory plus source search/open/symbol index. |
| Unsafe Python Exec Add-on | `unsafe` | add-on | 1 | `unsafe` | Exposes only the broad `freecad_python_exec` escape hatch. |

## Bundle Details

### FreeCAD MCP Free

- Environment: `FREECAD_MCP_MODULES=free`
- Audience: Users who want local file-based FreeCAD automation from ChatGPT, Codex, or Claude.
- Limits: No GUI attach, no Sketcher/PartDesign premium flow, no worker sessions, no source-code intelligence, no unsafe Python exec.
- Unsafe Python exec included: `false`
- Tool count: `23`
- Upgrade path: `pro`

Tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_session_status`
- `freecad_document_new`
- `freecad_document_open`
- `freecad_document_save`
- `freecad_document_recompute`
- `freecad_document_export`
- `freecad_object_list`
- `freecad_object_get`
- `freecad_object_set_properties`
- `freecad_object_rename_label`
- `freecad_object_delete`
- `freecad_part_create_primitive`
- `freecad_part_boolean`
- `freecad_part_extrude`
- `freecad_part_revolve`
- `freecad_part_fillet`
- `freecad_part_chamfer`
- `freecad_part_check_geometry`
- `freecad_import_file`
- `freecad_export_file`
- `freecad_supported_formats`

### FreeCAD MCP Pro

- Environment: `FREECAD_MCP_MODULES=pro`
- Audience: Design users who need Sketcher, PartDesign, mesh, assembly, and live GUI selection workflows.
- Limits: No persistent worker sessions, TechDraw, CAM, FEM, source-code intelligence, or unsafe Python exec.
- Unsafe Python exec included: `false`
- Tool count: `79`
- Upgrade path: `studio`

Tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_session_status`
- `freecad_document_new`
- `freecad_document_open`
- `freecad_document_save`
- `freecad_document_recompute`
- `freecad_document_export`
- `freecad_object_list`
- `freecad_object_get`
- `freecad_object_set_properties`
- `freecad_object_rename_label`
- `freecad_object_delete`
- `freecad_part_create_primitive`
- `freecad_part_boolean`
- `freecad_part_extrude`
- `freecad_part_revolve`
- `freecad_part_fillet`
- `freecad_part_chamfer`
- `freecad_part_check_geometry`
- `freecad_partdesign_body_create`
- `freecad_partdesign_datum_plane_create`
- `freecad_partdesign_pad`
- `freecad_partdesign_pocket`
- `freecad_partdesign_hole`
- `freecad_partdesign_revolution`
- `freecad_partdesign_groove`
- `freecad_partdesign_additive_loft`
- `freecad_partdesign_subtractive_loft`
- `freecad_partdesign_additive_pipe`
- `freecad_partdesign_subtractive_pipe`
- `freecad_partdesign_fillet`
- `freecad_partdesign_chamfer`
- `freecad_partdesign_thickness`
- `freecad_partdesign_draft`
- `freecad_sketch_create`
- `freecad_sketch_add_geometry`
- `freecad_sketch_add_constraint`
- `freecad_sketch_add_profile`
- `freecad_sketch_profile_create`
- `freecad_sketch_profile_validate`
- `freecad_curve_fit_analyze`
- `freecad_sketch_geometry_method_catalog`
- `freecad_sketch_edit_geometry`
- `freecad_sketch_edit_constraints`
- `freecad_sketch_transform`
- `freecad_sketch_auto_constrain`
- `freecad_sketch_validate`
- `freecad_import_file`
- `freecad_export_file`
- `freecad_supported_formats`
- `freecad_mesh_import`
- `freecad_mesh_export`
- `freecad_mesh_evaluate`
- `freecad_mesh_repair`
- `freecad_mesh_boolean`
- `freecad_assembly_create`
- `freecad_assembly_insert`
- `freecad_assembly_create_joint`
- `freecad_assembly_solve`
- `freecad_assembly_bom`
- `freecad_gui_attach`
- `freecad_gui_list`
- `freecad_gui_detach`
- `freecad_gui_status`
- `freecad_gui_active_document_get`
- `freecad_gui_active_view_get`
- `freecad_gui_selection_get`
- `freecad_gui_preselection_get`
- `freecad_gui_selection_set`
- `freecad_gui_view_fit`
- `freecad_gui_primitive_create`
- `freecad_gui_object_label_set`
- `freecad_gui_sketch_state`
- `freecad_gui_sketch_enter`
- `freecad_gui_sketch_leave`
- `freecad_gui_partdesign_state`
- `freecad_gui_body_activate`
- `freecad_gui_feature_task_state`

### FreeCAD MCP Studio

- Environment: `FREECAD_MCP_MODULES=studio`
- Audience: Power users and small studios that need persistent sessions and advanced workbench coverage.
- Limits: No source-code intelligence and no unsafe Python exec.
- Unsafe Python exec included: `false`
- Tool count: `151`
- Upgrade path: `team`

Tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_session_status`
- `freecad_session_start`
- `freecad_session_list`
- `freecad_session_close`
- `freecad_worker_session_start`
- `freecad_worker_session_list`
- `freecad_worker_session_status`
- `freecad_worker_session_close`
- `freecad_session_console`
- `freecad_worker_console_read`
- `freecad_worker_document_new`
- `freecad_worker_document_open`
- `freecad_worker_document_save`
- `freecad_worker_document_recompute`
- `freecad_worker_document_close`
- `freecad_worker_document_export`
- `freecad_worker_part_create_primitive`
- `freecad_worker_part_boolean`
- `freecad_worker_part_extrude`
- `freecad_worker_partdesign_body_create`
- `freecad_worker_partdesign_datum_plane_create`
- `freecad_worker_partdesign_pad`
- `freecad_worker_partdesign_pocket`
- `freecad_worker_partdesign_hole`
- `freecad_worker_partdesign_revolution`
- `freecad_worker_partdesign_groove`
- `freecad_worker_partdesign_additive_loft`
- `freecad_worker_partdesign_subtractive_loft`
- `freecad_worker_partdesign_additive_pipe`
- `freecad_worker_partdesign_subtractive_pipe`
- `freecad_worker_partdesign_fillet`
- `freecad_worker_partdesign_chamfer`
- `freecad_worker_partdesign_thickness`
- `freecad_worker_partdesign_draft`
- `freecad_worker_part_revolve`
- `freecad_worker_part_check_geometry`
- `freecad_worker_sketch_create`
- `freecad_worker_sketch_add_geometry`
- `freecad_worker_sketch_add_constraint`
- `freecad_worker_sketch_add_profile`
- `freecad_worker_sketch_profile_create`
- `freecad_worker_sketch_profile_validate`
- `freecad_worker_sketch_edit_geometry`
- `freecad_worker_sketch_edit_constraints`
- `freecad_worker_sketch_transform`
- `freecad_worker_sketch_auto_constrain`
- `freecad_worker_sketch_validate`
- `freecad_worker_mesh_import`
- `freecad_worker_mesh_export`
- `freecad_worker_mesh_evaluate`
- `freecad_worker_mesh_repair`
- `freecad_worker_mesh_boolean`
- `freecad_worker_assembly_create`
- `freecad_worker_assembly_insert`
- `freecad_worker_assembly_create_joint`
- `freecad_worker_assembly_solve`
- `freecad_worker_assembly_bom`
- `freecad_worker_object_list`
- `freecad_worker_object_get`
- `freecad_worker_object_set_properties`
- `freecad_worker_object_rename_label`
- `freecad_worker_object_delete`
- `freecad_document_new`
- `freecad_document_open`
- `freecad_document_save`
- `freecad_document_recompute`
- `freecad_document_export`
- `freecad_object_list`
- `freecad_object_get`
- `freecad_object_set_properties`
- `freecad_object_rename_label`
- `freecad_object_delete`
- `freecad_part_create_primitive`
- `freecad_part_boolean`
- `freecad_part_extrude`
- `freecad_part_revolve`
- `freecad_part_fillet`
- `freecad_part_chamfer`
- `freecad_part_check_geometry`
- `freecad_partdesign_body_create`
- `freecad_partdesign_datum_plane_create`
- `freecad_partdesign_pad`
- `freecad_partdesign_pocket`
- `freecad_partdesign_hole`
- `freecad_partdesign_revolution`
- `freecad_partdesign_groove`
- `freecad_partdesign_additive_loft`
- `freecad_partdesign_subtractive_loft`
- `freecad_partdesign_additive_pipe`
- `freecad_partdesign_subtractive_pipe`
- `freecad_partdesign_fillet`
- `freecad_partdesign_chamfer`
- `freecad_partdesign_thickness`
- `freecad_partdesign_draft`
- `freecad_sketch_create`
- `freecad_sketch_add_geometry`
- `freecad_sketch_add_constraint`
- `freecad_sketch_add_profile`
- `freecad_sketch_profile_create`
- `freecad_sketch_profile_validate`
- `freecad_curve_fit_analyze`
- `freecad_sketch_geometry_method_catalog`
- `freecad_sketch_edit_geometry`
- `freecad_sketch_edit_constraints`
- `freecad_sketch_transform`
- `freecad_sketch_auto_constrain`
- `freecad_sketch_validate`
- `freecad_import_file`
- `freecad_export_file`
- `freecad_supported_formats`
- `freecad_mesh_import`
- `freecad_mesh_export`
- `freecad_mesh_evaluate`
- `freecad_mesh_repair`
- `freecad_mesh_boolean`
- `freecad_assembly_create`
- `freecad_assembly_insert`
- `freecad_assembly_create_joint`
- `freecad_assembly_solve`
- `freecad_assembly_bom`
- `freecad_techdraw_page_create`
- `freecad_techdraw_view_create`
- `freecad_techdraw_inspect`
- `freecad_techdraw_page_export`
- `freecad_cam_path_create`
- `freecad_cam_path_inspect`
- `freecad_cam_path_export`
- `freecad_fem_analysis_create`
- `freecad_fem_material_create`
- `freecad_fem_constraint_create`
- `freecad_fem_inspect`
- `freecad_gui_attach`
- `freecad_gui_list`
- `freecad_gui_detach`
- `freecad_gui_status`
- `freecad_gui_active_document_get`
- `freecad_gui_active_view_get`
- `freecad_gui_selection_get`
- `freecad_gui_preselection_get`
- `freecad_gui_selection_set`
- `freecad_gui_view_fit`
- `freecad_gui_primitive_create`
- `freecad_gui_object_label_set`
- `freecad_gui_sketch_state`
- `freecad_gui_sketch_enter`
- `freecad_gui_sketch_leave`
- `freecad_gui_partdesign_state`
- `freecad_gui_body_activate`
- `freecad_gui_feature_task_state`

### FreeCAD MCP Team

- Environment: `FREECAD_MCP_MODULES=team`
- Audience: Teams building or auditing FreeCAD automation who need source-backed implementation evidence.
- Limits: No unsafe Python exec by default.
- Unsafe Python exec included: `false`
- Tool count: `154`

Tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_source_symbol_index`
- `freecad_source_search`
- `freecad_source_open`
- `freecad_session_status`
- `freecad_session_start`
- `freecad_session_list`
- `freecad_session_close`
- `freecad_worker_session_start`
- `freecad_worker_session_list`
- `freecad_worker_session_status`
- `freecad_worker_session_close`
- `freecad_session_console`
- `freecad_worker_console_read`
- `freecad_worker_document_new`
- `freecad_worker_document_open`
- `freecad_worker_document_save`
- `freecad_worker_document_recompute`
- `freecad_worker_document_close`
- `freecad_worker_document_export`
- `freecad_worker_part_create_primitive`
- `freecad_worker_part_boolean`
- `freecad_worker_part_extrude`
- `freecad_worker_partdesign_body_create`
- `freecad_worker_partdesign_datum_plane_create`
- `freecad_worker_partdesign_pad`
- `freecad_worker_partdesign_pocket`
- `freecad_worker_partdesign_hole`
- `freecad_worker_partdesign_revolution`
- `freecad_worker_partdesign_groove`
- `freecad_worker_partdesign_additive_loft`
- `freecad_worker_partdesign_subtractive_loft`
- `freecad_worker_partdesign_additive_pipe`
- `freecad_worker_partdesign_subtractive_pipe`
- `freecad_worker_partdesign_fillet`
- `freecad_worker_partdesign_chamfer`
- `freecad_worker_partdesign_thickness`
- `freecad_worker_partdesign_draft`
- `freecad_worker_part_revolve`
- `freecad_worker_part_check_geometry`
- `freecad_worker_sketch_create`
- `freecad_worker_sketch_add_geometry`
- `freecad_worker_sketch_add_constraint`
- `freecad_worker_sketch_add_profile`
- `freecad_worker_sketch_profile_create`
- `freecad_worker_sketch_profile_validate`
- `freecad_worker_sketch_edit_geometry`
- `freecad_worker_sketch_edit_constraints`
- `freecad_worker_sketch_transform`
- `freecad_worker_sketch_auto_constrain`
- `freecad_worker_sketch_validate`
- `freecad_worker_mesh_import`
- `freecad_worker_mesh_export`
- `freecad_worker_mesh_evaluate`
- `freecad_worker_mesh_repair`
- `freecad_worker_mesh_boolean`
- `freecad_worker_assembly_create`
- `freecad_worker_assembly_insert`
- `freecad_worker_assembly_create_joint`
- `freecad_worker_assembly_solve`
- `freecad_worker_assembly_bom`
- `freecad_worker_object_list`
- `freecad_worker_object_get`
- `freecad_worker_object_set_properties`
- `freecad_worker_object_rename_label`
- `freecad_worker_object_delete`
- `freecad_document_new`
- `freecad_document_open`
- `freecad_document_save`
- `freecad_document_recompute`
- `freecad_document_export`
- `freecad_object_list`
- `freecad_object_get`
- `freecad_object_set_properties`
- `freecad_object_rename_label`
- `freecad_object_delete`
- `freecad_part_create_primitive`
- `freecad_part_boolean`
- `freecad_part_extrude`
- `freecad_part_revolve`
- `freecad_part_fillet`
- `freecad_part_chamfer`
- `freecad_part_check_geometry`
- `freecad_partdesign_body_create`
- `freecad_partdesign_datum_plane_create`
- `freecad_partdesign_pad`
- `freecad_partdesign_pocket`
- `freecad_partdesign_hole`
- `freecad_partdesign_revolution`
- `freecad_partdesign_groove`
- `freecad_partdesign_additive_loft`
- `freecad_partdesign_subtractive_loft`
- `freecad_partdesign_additive_pipe`
- `freecad_partdesign_subtractive_pipe`
- `freecad_partdesign_fillet`
- `freecad_partdesign_chamfer`
- `freecad_partdesign_thickness`
- `freecad_partdesign_draft`
- `freecad_sketch_create`
- `freecad_sketch_add_geometry`
- `freecad_sketch_add_constraint`
- `freecad_sketch_add_profile`
- `freecad_sketch_profile_create`
- `freecad_sketch_profile_validate`
- `freecad_curve_fit_analyze`
- `freecad_sketch_geometry_method_catalog`
- `freecad_sketch_edit_geometry`
- `freecad_sketch_edit_constraints`
- `freecad_sketch_transform`
- `freecad_sketch_auto_constrain`
- `freecad_sketch_validate`
- `freecad_import_file`
- `freecad_export_file`
- `freecad_supported_formats`
- `freecad_mesh_import`
- `freecad_mesh_export`
- `freecad_mesh_evaluate`
- `freecad_mesh_repair`
- `freecad_mesh_boolean`
- `freecad_assembly_create`
- `freecad_assembly_insert`
- `freecad_assembly_create_joint`
- `freecad_assembly_solve`
- `freecad_assembly_bom`
- `freecad_techdraw_page_create`
- `freecad_techdraw_view_create`
- `freecad_techdraw_inspect`
- `freecad_techdraw_page_export`
- `freecad_cam_path_create`
- `freecad_cam_path_inspect`
- `freecad_cam_path_export`
- `freecad_fem_analysis_create`
- `freecad_fem_material_create`
- `freecad_fem_constraint_create`
- `freecad_fem_inspect`
- `freecad_gui_attach`
- `freecad_gui_list`
- `freecad_gui_detach`
- `freecad_gui_status`
- `freecad_gui_active_document_get`
- `freecad_gui_active_view_get`
- `freecad_gui_selection_get`
- `freecad_gui_preselection_get`
- `freecad_gui_selection_set`
- `freecad_gui_view_fit`
- `freecad_gui_primitive_create`
- `freecad_gui_object_label_set`
- `freecad_gui_sketch_state`
- `freecad_gui_sketch_enter`
- `freecad_gui_sketch_leave`
- `freecad_gui_partdesign_state`
- `freecad_gui_body_activate`
- `freecad_gui_feature_task_state`

### Source Intelligence Add-on

- Environment: `FREECAD_MCP_MODULES=source`
- Audience: Maintainers and support engineers who need command/source lookup without mutation tools.
- Limits: No document mutation, no GUI attach, no worker sessions, no unsafe Python exec.
- Unsafe Python exec included: `false`
- Tool count: `5`

Tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_source_symbol_index`
- `freecad_source_search`
- `freecad_source_open`

### Unsafe Python Exec Add-on

- Environment: `FREECAD_MCP_MODULES=unsafe`
- Audience: Trusted local developers who explicitly need raw FreeCADCmd Python execution.
- Limits: Must stay opt-in and should not be bundled into paid tiers by default.
- Unsafe Python exec included: `true`
- Tool count: `1`

Tools:

- `freecad_python_exec`
