# Hybrid MCP Tool Plan

FreeCAD source scan commit: `dee977f98f8a8542c8db0be2ecc529a771931d01`.

The static scan found 1112 GUI command registrations across 26 modules. The MCP server should not expose all of them as separate top-level tools. The safer shape is a small typed core plus a command registry escape hatch.

## P0 Tools

| Tool | Purpose | Backend |
| --- | --- | --- |
| `freecad_source_search` | Search FreeCAD source by text/glob/module. | Git checkout |
| `freecad_source_open` | Read a source file region with line numbers. | Git checkout |
| `freecad_source_symbol_index` | Return indexed command/class/module records. | Generated inventory |
| `freecad_session_start` | Start or attach to a FreeCAD Python runtime. | FreeCAD process |
| `freecad_session_status` | Report process, document, and bridge state. | FreeCAD process |
| `freecad_python_exec` | Execute controlled Python snippets for diagnostics. | FreeCAD process |
| `freecad_document_new` | Create a new FreeCAD document. | FreeCAD API |
| `freecad_document_open` | Open `.FCStd` or importable CAD file. | FreeCAD API |
| `freecad_document_save` | Save active document. | FreeCAD API |
| `freecad_document_recompute` | Recompute document and return errors/warnings. | FreeCAD API |
| `freecad_document_export` | Export selected objects or active document. | FreeCAD API |
| `freecad_object_list` | List objects with labels, types, visibility, placement. | FreeCAD API |
| `freecad_object_get` | Inspect object properties and shape summary. | FreeCAD API |
| `freecad_object_set_properties` | Set validated object properties. | FreeCAD API |
| `freecad_object_delete` | Remove object(s) by stable name. | FreeCAD API |

## P1 Tools

| Tool | Purpose | Evidence |
| --- | --- | --- |
| `freecad_command_list` | List scanned/runtime GUI commands. | 1112 scanned command records |
| `freecad_command_describe` | Return menu text, tooltip, module, source ref. | `docs/freecad_tool_inventory.json` |
| `freecad_command_run` | Run a named FreeCAD GUI command when a typed wrapper is missing. | Command registry |
| `freecad_part_create_primitive` | Create box, cylinder, sphere, cone, torus. | `Part_*` command/API surface |
| `freecad_part_boolean` | Fuse/cut/common selected Part shapes. | Part workbench commands |
| `freecad_part_extrude` | Extrude selected profile/face. | Part workbench commands |
| `freecad_part_revolve` | Revolve selected profile/face. | Part workbench commands |
| `freecad_part_fillet` | Add fillet to selected edges. | Part workbench commands |
| `freecad_part_chamfer` | Add chamfer to selected edges. | Part workbench commands |
| `freecad_part_check_geometry` | Run geometry validation. | `Part_CheckGeometry` |
| `freecad_sketch_create` | Create sketch on plane or selected face. | Sketcher commands |
| `freecad_sketch_add_geometry` | Add line, circle, arc, polyline geometry. | Sketcher commands/API |
| `freecad_sketch_add_constraint` | Add coincident, distance, angle, symmetry constraints. | Sketcher commands/API |
| `freecad_sketch_validate` | Validate sketch constraints/geometry. | Sketcher validation command |

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
| `freecad_import_file` | Import CAD file into active document. | Import/Part/Mesh commands |
| `freecad_export_file` | Export selected/all objects. | Import/Part/Mesh commands |
| `freecad_supported_formats` | Report detected import/export formats. | Source/runtime registry |

## Implementation Notes

- Typed tools should call FreeCAD Python APIs directly where possible.
- `freecad_command_run` is an escape hatch, not the primary interface.
- Every mutating runtime tool should return a structured document/object diff.
- Source tools can work without FreeCAD installed; runtime tools require a configured FreeCAD executable.
- The next implementation step is the MCP scaffold plus a local FreeCAD bridge process.

