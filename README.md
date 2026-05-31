# FreeCAD Hybrid MCP

FreeCAD icin hibrit MCP server calismasi.

Bu repo iki kaynagi birlestirecek:

- Static source tools: Git ile alinan FreeCAD kod tabaninda arama, sembol ve komut envanteri.
- Runtime tools: Calisan FreeCAD Python oturumuna baglanip belge, obje ve geometri islemleri.

## Current Inventory

FreeCAD upstream checkout:

```powershell
upstream\FreeCAD
```

Tool inventory generation:

```powershell
& 'C:\Users\tamer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\scan_freecad_tools.py --freecad-root upstream\FreeCAD
```

Generated files:

- `docs/freecad_tool_inventory.md`
- `docs/freecad_tool_inventory.json`
- `docs/mcp_tool_plan.md`

## MCP Server

Run the local stdio MCP server:

```powershell
python server.py
```

Example MCP client config:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["C:/path/to/Freecad_MCP/server.py"]
    }
  }
}
```

Available Phase 1 tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_source_symbol_index`
- `freecad_source_search`
- `freecad_source_open`

Available Phase 2 runtime tools:

- `freecad_session_status`
- `freecad_python_exec`

Available persistent worker tools:

- `freecad_session_start`, `freecad_session_list`, `freecad_session_close`
- `freecad_worker_session_start/list/status/close`
- `freecad_worker_document_new/open/save/recompute/close/export`
- `freecad_worker_part_create_primitive/boolean/extrude/revolve/check_geometry`
- `freecad_worker_sketch_create/add_geometry/add_constraint/add_profile/edit_geometry/edit_constraints/transform/auto_constrain/validate`
- `freecad_worker_mesh_import/export/evaluate/repair/boolean`
- `freecad_worker_assembly_create/insert/create_joint/solve/bom`
- `freecad_worker_object_list/get/set_properties/delete`

Available GUI attach tools:

- `freecad_gui_attach/list/detach/status`
- `freecad_gui_active_document_get`
- `freecad_gui_active_view_get`
- `freecad_gui_selection_get`
- `freecad_gui_preselection_get`
- `freecad_gui_selection_set`
- `freecad_gui_view_fit`
- `freecad_gui_primitive_create`

GUI attach is opt-in. Start `scripts/freecad_gui_bridge_server.py` inside a running FreeCAD GUI Python console, then call `freecad_gui_attach` with the local bridge URL and optional token. This mode is for live active document/view/selection state; typed CAD tools remain the primary way to mutate geometry.

Opt-in GUI smoke:

```powershell
$env:FREECAD_MCP_GUI_SMOKE = "1"
scripts\verify.ps1
```

The opt-in smoke also validates that GUI selection records can populate native Assembly `Reference1`/`Reference2` connector fields through `freecad_assembly_create_joint`.

Workbench-hosted bridge:

- Add `freecad_workbench` as a FreeCAD module path (`-M`). If needed, pass the leaf `freecad_workbench\FreeCADMCP` directory directly.
- Load the **FreeCAD MCP** workbench to start/stop/status the bridge from FreeCAD.
- Set `FREECAD_MCP_AUTOSTART=1` and `FREECAD_MCP_GUI_TOKEN` to host automatically when the module is loaded.
- Build the local module zip with `python scripts\build_workbench_addon.py --zip-out dist\freecad-mcp-workbench.zip`; the zip embeds the GUI bridge script beside `InitGui.py`.

Product-style module filtering:

```powershell
$env:FREECAD_MCP_MODULES = "pro"
python server.py
```

Supported aliases include `free`, `pro`, `studio`, `team`, `source`, and `all`; `dev`, `developer`, and `local-dev` intentionally map to the full local `all` surface so product filtering does not shrink maintainer workflows. Explicit comma-separated module lists such as `core,headless,gui,sketcher` are also supported. Generated sellable bundle counts and tool lists are in `docs/PRODUCT_BUNDLES.md`; generated distribution profiles and MCP config skeletons are in `docs/DISTRIBUTION_PROFILES.md` and `packaging/profiles/`; module rules are in `docs/PRODUCT_MODULES.md`.

Installed-package entrypoint shape:

```powershell
freecad-hybrid-mcp
```

Set `FREECAD_MCP_REPO_ROOT` when running the installed entrypoint outside this checkout but still relying on repo-local docs/inventory resources.

Typed CAD tool groups are also available:

- document: new/open/save/recompute/export
- object: list/get/set properties/delete
- Part: primitives, boolean, direct/parametric extrude, revolve, fillet, chamfer, geometry check
- PartDesign: Body, Datum Plane, Pad, Pocket, Hole, Revolution, Groove, Additive Loft, Subtractive Loft
- Sketcher: create, advanced geometry/profile creation, constraint create/update, geometry/constraint edit, transform, auto-constrain, validate
- import/export and mesh tools
- Assembly: create/insert/link native JointObject proxies/recompute/BOM
- TechDraw: create page/template, create part view, inspect pages/views, export headless DXF
- CAM: create simple `Path::Feature` from explicit commands, inspect, and export raw G-code
- FEM: create analysis containers, material objects, fixed/force constraints, and inspect analysis membership

The server also exposes MCP resources for architecture, session state, testing, Sketcher capabilities, GUI attach planning, Workbench bridge setup, Workbench artifact shape, TechDraw/CAM/FEM typed-wrapper planning, product modules, product bundles, distribution profiles, tool schemas, and inventory summary, plus workflow prompts for design tasks and phase gates.

Sketcher details are tracked in `docs/SKETCHER_CAPABILITIES.md`.

For runtime tools, set one of:

- `FREECAD_MCP_FREECAD_HOME` to a portable FreeCAD directory
- `FREECAD_MCP_FREECAD_CMD` to a concrete `FreeCADCmd.exe`
- `FREECAD_MCP_WORKSPACE_ROOT` to constrain typed CAD output paths

Typed CAD tools require absolute `output_path` values. Writes outside the workspace root require `allow_external_paths=true`.

Smoke test:

```powershell
scripts\verify.ps1
```
