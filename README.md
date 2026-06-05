# FreeCAD Hybrid MCP

FreeCAD Hybrid MCP is a local Model Context Protocol server for FreeCAD. It lets AI coding agents inspect the FreeCAD command/source inventory, create and modify CAD documents through typed tools, keep persistent `FreeCADCmd` sessions alive, and optionally attach to a running FreeCAD GUI for live document, view, and selection context.

The project is built around one main rule: prefer deterministic typed CAD tools over broad Python execution. Raw Python remains an explicit unsafe escape hatch, while normal modeling flows use structured tool schemas, FreeCAD transactions, recompute, validation, and JSON result reporting.

For Sketcher and PartDesign work, the modeling contract is stronger than "draw some primitives": complex profiles should be primitive geometry plus explicit constraints plus validation. Agents should prefer helper/profile recipes for known CAD intents such as rectangle, circle, regular polygon/hexagon, slot, and keyhole; use semantic named Sketcher dimensions for parametric models; and avoid loose overlapping profiles such as circle + rectangle when a single keyhole loop or ordered arc/line loop is the real CAD intent.

## Current Status

- Primary runtime verified against FreeCAD `1.1.1` portable on Windows.
- Full current MCP surface: `159` tools with `FREECAD_MCP_MODULES=all`.
- Product-style profiles are generated for `free`, `pro`, `studio`, `team`, `source`, and `unsafe`.
- The repository includes generated MCP tool schemas, product bundle manifests, distribution profile skeletons, and a local FreeCAD Workbench bridge artifact.
- The source command inventory currently scans `1112` FreeCAD GUI command registrations from the configured local FreeCAD source checkout.

See [docs/ROADMAP_STATUS.md](docs/ROADMAP_STATUS.md), [docs/SESSION_STATE.md](docs/SESSION_STATE.md), and [docs/PRODUCT_BUNDLES.md](docs/PRODUCT_BUNDLES.md) for the most detailed generated status.

## What It Is For

Use this MCP server when you want an AI agent to:

- Create FreeCAD documents and geometry from natural-language instructions.
- Build and validate Sketcher profiles before PartDesign features are created.
- Bind named parameters into object properties and Sketcher dimension constraints.
- Create Body-attached Pad, Pocket, Hole, Revolution, Groove, Loft, Pipe, dress-up, and pattern features.
- Inspect object metadata, topology, bounding boxes, and geometry-check results.
- Import/export FreeCAD-supported formats such as FCStd, STEP, STL, DXF, and raw G-code where implemented.
- Open generated `.FCStd` documents in a live FreeCAD GUI and read GUI selection/view state when the user is already working there.
- Research FreeCAD source commands and implementation details from a local source checkout.
- Offer a safer alternative to "just run arbitrary FreeCAD Python" workflows.

## Quick Start

Install Python dependencies:

```powershell
python -m pip install mcp
```

Point the server at FreeCAD:

```powershell
$env:FREECAD_MCP_FREECAD_HOME = "E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311"
$env:FREECAD_MCP_WORKSPACE_ROOT = "C:\Users\tamer\Codex_Projects\Freecad_MCP"
```

Run the local stdio MCP server from the repository:

```powershell
python server.py
```

Or use the installed package entrypoint after packaging/installing:

```powershell
freecad-hybrid-mcp
```

Run the verification suite:

```powershell
scripts\verify.ps1
```

For Codex, Claude Code, Claude Desktop-style clients, and other local MCP clients, see [docs/MCP_CLIENT_CONFIG.md](docs/MCP_CLIENT_CONFIG.md).

## MCP Client Config Shape

Minimal JSON-style MCP client config:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["C:/path/to/Freecad_MCP/server.py"],
      "env": {
        "FREECAD_MCP_FREECAD_HOME": "C:/path/to/FreeCAD",
        "FREECAD_MCP_WORKSPACE_ROOT": "C:/path/to/Freecad_MCP",
        "FREECAD_MCP_MODULES": "pro"
      }
    }
  }
}
```

`FREECAD_MCP_FREECAD_HOME` should point to a FreeCAD directory containing `FreeCADCmd.exe` and, for GUI workflows, `FreeCAD.exe`. You can also use `FREECAD_MCP_FREECAD_CMD` to point directly at `FreeCADCmd.exe`.

## Product Profiles

The server can expose different tool surfaces with `FREECAD_MCP_MODULES`.

| Profile | Tools | Intended Use |
| --- | ---: | --- |
| `free` | 20 | Static command inventory plus file-based document/object/parameter/import-export operations. |
| `pro` | 85 | Adds GUI attach, Sketcher, PartDesign, mesh, and Assembly typed tools. |
| `studio` | 155 | Adds persistent worker sessions plus TechDraw, CAM, and FEM first slices. |
| `team` | 158 | Studio surface plus source-intelligence tools. |
| `source` | 5 | Command/source intelligence add-on only. |
| `unsafe` | 1 | Broad `freecad_python_exec` escape hatch only. |
| `all` | 159 | Full advertised MCP surface. |

Generated profile files live under [packaging/profiles](packaging/profiles), and the generated bundle manifest is [docs/PRODUCT_BUNDLES.md](docs/PRODUCT_BUNDLES.md).

## Supported Tool Families

| Area | Current Support |
| --- | --- |
| Static command inventory | List and describe FreeCAD commands from the generated source inventory. |
| Source intelligence | Search/open source files and symbol index data from a local FreeCAD checkout. |
| Runtime status | Discover and report the configured `FreeCADCmd` runtime. |
| Documents | Create, open, save, recompute, close, and export FreeCAD documents. |
| Objects | List/get/set properties, rename user-visible labels, and delete objects. |
| Parameters and expressions | Create/read Spreadsheet parameter sheets and bind expressions into object properties or Sketcher dimension constraints such as `Constraints[0]`. |
| Sketcher | Create sketches, add geometry and constraints, add profile helpers, build/validate pad-ready profile loops, edit geometry/constraints, transform, auto-constrain, validate, and analyze curve-fit intent. |
| PartDesign | Body and Datum Plane creation, Pad, Pocket, Hole, Revolution, Groove, Additive/Subtractive Loft, Additive/Subtractive Pipe, Fillet, Chamfer, Thickness, Draft, LinearPattern, PolarPattern, and Mirrored. |
| PartDesign recipes | High-level Body-attached workflow tools for profile features and sweep features, so agents do not need to guess FreeCAD's Body + Sketch + plane/support sequence. |
| Import/export | Common file import/export entrypoints plus supported-format reporting. |
| Mesh | Import, export, evaluate, repair, and boolean operations. |
| Assembly | Create assemblies, insert objects, create native joint proxies, solve/recompute, and generate BOM data. |
| Persistent worker | Long-lived `FreeCADCmd` sessions for lower startup overhead and session-aware workflows. |
| GUI attach | Opt-in loopback bridge for opening generated `.FCStd` documents, active document/view, selection/preselection, selection set, final-object visibility repair, view orientation, view fit, viewport snapshot, primitive creation, and label updates. |
| Workbench bridge | Local FreeCAD workbench module that can start/stop/status the GUI bridge from inside FreeCAD. |
| TechDraw | First typed slice for page/template/view creation, page/view inspection, and headless DXF export. |
| CAM | First typed slice for explicit raw `Path::Feature` command paths and raw G-code export. |
| FEM | First typed slice for analysis containers, material objects, fixed/force constraints, and inspection. |
| Resources/prompts | MCP resources for schemas, inventory, product bundles, architecture, session state, testing, GUI plans, and roadmap status. |
| Unsafe Python | `freecad_python_exec` is intentionally separated into the `unsafe` profile/add-on. |

The full generated schema snapshot is [docs/mcp_tool_schemas.md](docs/mcp_tool_schemas.md).

## Sketcher And PartDesign Focus

The highest-value engineering path in this project is Sketcher + PartDesign. The server tries to encode the FreeCAD workflow an expert user would follow in the GUI:

1. Create or reuse a PartDesign Body.
2. Attach the sketch to an origin plane, datum plane, or support object.
3. Build a closed, valid, pad-ready profile.
4. Drive dimensions through Sketcher constraints and expressions, optionally using Spreadsheet aliases as named parameters.
5. Validate topology before creating the PartDesign feature.
6. Create the feature, recompute, and report the Body Tip and shape summary.

High-level recipe tools:

- `freecad_partdesign_profile_feature_create`: creates and validates a Body-attached profile sketch, then creates Pad, Pocket, Revolution, or Groove.
- `freecad_partdesign_parametric_profile_feature_create`: creates Spreadsheet parameters, semantic Sketcher profile constraints, expression bindings, final profile validation, and the PartDesign feature in one compact flow. For rectangle loops, `constraint_policy="semantic"` plus `width_expression`/`height_expression` keeps width and height as driven Sketcher dimensions and rejects `Block` shortcuts. For keyhole, slot, polygon/socket, and similar repeated CAD intents, prefer helper loops plus `require_fully_constrained=true` over static coordinates or overlapping primitive profiles.
- `freecad_partdesign_sweep_feature_create`: creates Body-attached profile and spine sketches, then creates Additive or Subtractive Pipe.

Lower-level tools remain available when the sketch, support objects, or selected subelements already exist.

Parameter tools:

- `freecad_spreadsheet_create` and `freecad_spreadsheet_get`: create/read named parameter sheets.
- `freecad_object_expression_set` and `freecad_object_expression_list`: bind/read object property expressions, including Sketcher dimension paths such as `Constraints[0]`. FreeCAD may report a named constraint back in canonical form such as `.Constraints.width`.

## GUI Attach

The MCP stdio server does not launch or control the FreeCAD GUI by default. GUI access is opt-in and local.

Start FreeCAD with the workbench path:

```powershell
& "E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311\FreeCAD.exe" -M "C:\Users\tamer\Codex_Projects\Freecad_MCP\freecad_workbench"
```

Then select the **FreeCAD MCP** workbench and run **Start MCP Bridge**, or configure autostart with:

```powershell
$env:FREECAD_MCP_AUTOSTART = "1"
$env:FREECAD_MCP_GUI_TOKEN = "choose-a-local-token"
```

After that, an MCP client can call `freecad_gui_attach` against the local loopback bridge URL, normally `http://127.0.0.1:48777`.

GUI attach is mainly for opening generated `.FCStd` files in the live GUI, active document/view/selection state, and visual evidence. `freecad_gui_document_open` defaults to turning on the final display object/Body visibility before fitting the view; `freecad_gui_visibility_ensure` can repair an already-open document whose tree objects are hidden, and `freecad_gui_view_orientation_set` can set isometric/front/top/right-style views before snapshots. Headless typed tools remain the preferred path for deterministic model mutation.

## Safety Model

- Typed tools are the default modeling surface.
- Broad Python execution is isolated behind the `unsafe` profile/add-on.
- Runtime mutating tools use structured arguments, transactions where applicable, recompute, and JSON result reporting.
- `FREECAD_MCP_WORKSPACE_ROOT` defines the normal output boundary. Absolute writes outside that root require explicit `allow_external_paths=true`.
- GUI attach is local/loopback and can use a token.
- Generated docs and tool schemas make the exposed tool surface reviewable before use.
- Verification includes unit tests, static MCP smoke, package smoke, real FreeCAD runtime smoke, typed CAD smoke, fixture document smoke, and persistent worker smoke.

## Verification

Run the main verification script before publishing or pushing changes:

```powershell
scripts\verify.ps1
```

Optional GUI smoke:

```powershell
$env:FREECAD_MCP_GUI_SMOKE = "1"
scripts\verify.ps1
```

The GUI smoke launches/uses FreeCAD GUI paths and is intentionally opt-in.

## Documentation Map

- [docs/MCP_CLIENT_CONFIG.md](docs/MCP_CLIENT_CONFIG.md): Codex, Claude, and JSON-style MCP client setup.
- [docs/PRODUCT_MODULES.md](docs/PRODUCT_MODULES.md): module filtering rules.
- [docs/PRODUCT_BUNDLES.md](docs/PRODUCT_BUNDLES.md): generated bundle profile manifest.
- [docs/DISTRIBUTION_PROFILES.md](docs/DISTRIBUTION_PROFILES.md): generated distribution profile config skeletons.
- [docs/SKETCHER_CAPABILITIES.md](docs/SKETCHER_CAPABILITIES.md): Sketcher geometry, profile, validation, and PartDesign attachment notes.
- [docs/AGENT_MODELING_CONTRACT.md](docs/AGENT_MODELING_CONTRACT.md): agent rules for primitive, helper, recipe, constraint, trim, and validation choices.
- [docs/GUI_ATTACH_PLAN.md](docs/GUI_ATTACH_PLAN.md): GUI bridge design.
- [docs/WORKBENCH_BRIDGE.md](docs/WORKBENCH_BRIDGE.md): FreeCAD workbench-hosted bridge setup.
- [docs/TECHDRAW_CAM_FEM_PLAN.md](docs/TECHDRAW_CAM_FEM_PLAN.md): guarded first-slice plans for advanced workbenches.
- [docs/BACKLOG.md](docs/BACKLOG.md): next expansion candidates and future deepening.
- [docs/BUGS.md](docs/BUGS.md): known behavioral boundaries and intentionally blocked flows.
- [docs/TESTING.md](docs/TESTING.md): verification scope.

## Roadmap / TODO

Current unblocked scope is complete, but the next useful expansion areas are:

- Add remote MCP transport support for HTTP/SSE and Streamable HTTP while keeping stdio as the stable local default.
- Deepen structured logging with crash bundles, worker restart correlation, response-size summaries, and performance rollups.
- Extend console reading beyond persistent worker sessions to process-per-call, GUI bridge, and Workbench bridge modes.
- Expand GUI live bridge coverage beyond viewport snapshots into command boundaries, transaction/dirty state, console forwarding, and safer GUI-side mutation policies.
- Deepen image-to-sketch guidance for ambiguous B-spline vs circular arc vs line/polyline decisions.
- Continue Sketcher and PartDesign research from official docs and local FreeCAD source. Next PartDesign targets include MultiTransform, Scaled, Boolean, and deeper combined Pipe orientation/scaling fixtures.
- Add persistent-worker parity for Spreadsheet/expression parameter tools after the process-per-call surface settles.
- Add a guarded GUI command catalog and allowlisted GUI command runner after preconditions, transaction policy, and smoke coverage are clear.
- Enable the existing GitHub Actions workflow after credentials include the `workflow` OAuth scope.
- Decide whether generated profiles should become separate packages, Codex plugin bundles, or commercial add-ons.
- Add TechDraw SVG/PDF export only through GUI attach or Workbench validation.
- Extend CAM and FEM only with fixture-backed machine, solver, and result contracts.
- Polish the Workbench module zip toward signed/installed FreeCAD Addon Manager packaging.
- Add a local custom-tool authoring pipeline with mandatory security analysis, sandbox smoke tests, explicit user approval, hash/audit logging, permission manifests, and safe runtime enforcement.

## Known Limitations

- This is an experimental MCP server, not a certified CAD automation product.
- The project is developed and verified primarily on Windows with a portable FreeCAD 1.1.1 runtime.
- GUI attach is intentionally limited and opt-in.
- TechDraw, CAM, and FEM are first-slice typed integrations, not full workbench replacements.
- CAM postprocessor execution, FEM solver execution, and GUI-only TechDraw PDF/SVG export are not default-safe flows yet.
- Part workbench primitive/boolean/extrude/revolve/fillet/chamfer/check tools are intentionally hidden from the advertised MCP surface for now. Their code remains in the repository for internal smoke/regression use, but public agent workflows should use Sketcher + PartDesign instead.
- Some Sketcher raw constraint constructors are blocked because they can terminate the current FreeCADCmd runtime.
- AI-generated CAD should always be reviewed by a qualified human before manufacturing, safety-critical use, quoting, or release.

## Contributors

- Tamer Karakan - project owner and maintainer.
- Codex (OpenAI) - AI coding agent contributor for implementation support, documentation, verification, and repository maintenance.

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by the FreeCAD project or its contributors.

FreeCAD Hybrid MCP is provided for experimentation, automation research, and local development workflows. It is provided "as is", without warranties of any kind, including fitness for a particular purpose, merchantability, correctness, reliability, safety, or non-infringement.

CAD models, generated toolpaths, FEM setups, dimensions, constraints, and exported files produced through this MCP server may be incomplete, invalid, unsafe, or misunderstood by an AI agent. You are responsible for independently checking all geometry, constraints, tolerances, manufacturing assumptions, simulation inputs, file paths, and generated outputs before using them.

Do not rely on this project for safety-critical engineering, regulated design, production manufacturing, legal compliance, financial decisions, or professional certification without independent expert review. Running MCP tools can launch local FreeCAD processes and write files on your machine; review configuration, workspace boundaries, tokens, prompts, and input files before use.

## License

No open-source license has been selected yet. Until a license is added, the default copyright rules apply.
