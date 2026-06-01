# Testing

Primary verification command:

```powershell
scripts\verify.ps1
```

Current checks:

- Python syntax compile for server, scripts, package, and tests.
- Unit tests with a fake FreeCAD source tree from `tests/unit`.
- MCP tool schema snapshot export.
- Static stdio MCP smoke test through `scripts/smoke_static_mcp.py`.
- Optional real FreeCADCmd runtime smoke test through `scripts/smoke_freecad_runtime.py`.
- Optional typed CAD smoke test through `scripts/smoke_cad_tools.py`, including primitive/export, STEP roundtrip import, Part boolean + geometry check, PartDesign Body-attached sketch profiles with Pad solid creation, Pocket subtraction, plain Hole creation from a circle sketch, datum plane creation with Body Tip preservation, sketch attachment to a datum plane, additive Revolution, subtractive Groove, Additive/Subtractive Loft, Additive Pipe with multisection scaling, Auxiliary Additive Pipe orientation, Subtractive Pipe, PartDesign Fillet/Chamfer/Thickness/Draft dress-up tools, PartDesign LinearPattern/PolarPattern/Mirrored transforms, mesh import/repair, unsupported mesh repair action reporting, Assembly creation, closed Sketcher rectangle to solid extrusion, connected closed line/B-spline/arc chain validation, loop-based pad-ready profile creation/validation, native geometry type reporting, Sketcher geometry/profile method catalog coverage, circular arc actual-geometry reporting, rectangle/center rectangle/3-point rectangle/named polygon/slot/arc-slot profile helpers, segment intent mismatch rejection, endpoint drift rejection, curve-preservation and line-fallback rejection, curve fit arc/B-spline recommendation, parametric shell-only/symmetric/taper extrusion, open Sketcher extrusion, safe Sketcher Group/Text constraint blocking, current solid-shape extrude failure behavior, advanced Sketcher geometry/profile/constraint diagnostics, auto-constraint detection/application, B-spline edits, copy, and move transforms.
- Typed CAD smoke also covers the TechDraw first slice: Part source object, page/template creation, `DrawViewPart` creation, page/view inspection, and headless DXF page export.
- Typed CAD smoke also covers CAM raw `Path::Feature` creation/inspection/G-code export and FEM analysis/material/fixed-force constraint creation/inspection without postprocessor or solver execution.
- Optional generated fixture document smoke through `scripts/smoke_fixture_documents.py`, including a multi-object FreeCAD document, object metadata and visibility, boolean geometry, Sketcher profile extrusion, Assembly link, reopen/list/get checks, geometry validation, STEP export, and STL export.
- Optional persistent worker smoke test through `scripts/smoke_persistent_worker.py`, including worker session start/list/status/close, in-memory document lifecycle, primitive creation, object list/get/set/delete, Part boolean + geometry check, worker PartDesign Body-attached sketch profiles with Pad solid creation, Pocket subtraction, plain Hole creation from a circle sketch, datum plane creation with Body Tip preservation, sketch attachment to a datum plane, Fillet/Chamfer/Thickness/Draft dress-up tools, LinearPattern/PolarPattern/Mirrored transforms, additive Revolution, subtractive Groove, Additive/Subtractive Loft in clean worker sessions, Additive Pipe with auxiliary-spine orientation, Subtractive Pipe in clean worker sessions, closed Sketcher profile to solid extrude, connected closed Sketcher curve chain validation, worker circular arc method/reporting coverage, worker loop-based profile creation/validation, worker native geometry type reporting, worker segment intent mismatch rejection, worker curve-preservation and line-fallback rejection, worker parametric shell-only extrusion, safe worker Sketcher Group constraint blocking, Sketcher geometry/constraint/edit/transform/auto-constraint/validate flows, STL export plus deterministic STL fixture import/evaluate/repair, Assembly create/insert/native joint/BOM/solve, document export, save, and document close.
- The persistent worker STL mesh import leg uses a tiny deterministic ASCII STL fixture and explicit longer timeouts around worker import/export requests because full verify runs after package/build/typed-smoke work, where FreeCAD mesh I/O can be slower than the default worker request timeout on Windows.
- The persistent worker smoke restarts the worker between PartDesign/early-Sketcher, PartDesign dress-up features, PartDesign transform features, PartDesign Revolution/Groove, PartDesign Additive Loft, PartDesign Subtractive Loft, PartDesign Additive Pipe, PartDesign Subtractive Pipe, Sketcher edit/transform, and later Part/mesh/Assembly slices so unrelated global state or recomputes do not mask the tool behavior under test.
- Real FreeCAD runtime verification with `FREECAD_MCP_REQUIRE_RUNTIME=1` also covers structured null-shape reporting for shell-only parametric extrusions, so a present-but-null FreeCAD `Shape` does not break downstream topology-count consumers.
- Inventory regeneration when `upstream/FreeCAD/src` exists.
- Unit guard for stdio serialization fallback (`test_mcp_stdio.py`).
- Unit guard for stdio EOF shutdown cleanup (`test_mcp_stdio.py`).
- Unit guard for empty MCP resource-template listing (`resources/templates/list`).
- Unit guard for `FREECAD_MCP_MODULES` product aliases, full-surface local developer aliases, GUI-only filtering, worker-module gating, and source-intelligence add-on behavior (`test_mcp_stdio.py`).
- Unit guard for generated sellable bundle descriptors, unsafe add-on separation, and upgrade-ladder tool counts (`test_product_bundles.py`).
- Unit guard for distribution profile descriptors, generated MCP config skeleton shape, and `pyproject.toml` packaging declarations (`test_distribution_profiles.py`).
- Static MCP smoke guard for empty resource-template listing (`resources/templates/list`).
- Static MCP smoke guard for GUI attach tool schemas (`freecad_gui_attach`, `freecad_gui_selection_get`, GUI object label set, Sketcher edit/state tools, PartDesign state/body activation tools, and feature-task state).
- Distribution profile smoke checks `docs/distribution_profiles.json` and `packaging/profiles/*.mcp.json` after generation.
- Workbench artifact generation writes `docs/WORKBENCH_ARTIFACT.md`, `docs/workbench_artifact.json`, and `packaging/workbench/README.md`.
- Workbench artifact smoke builds `freecad-mcp-workbench.zip`, imports the extracted `FreeCADMCP/InitGui.py` with fake FreeCAD modules, verifies the embedded sibling `freecad_gui_bridge_server.py` path is preferred, and compiles the embedded bridge script.
- Python package smoke builds the wheel with `pip wheel --no-deps --no-build-isolation`, builds/inspects an sdist through the setuptools backend, verifies runtime scripts plus the `freecad-hybrid-mcp` console entrypoint are present, installs the wheel into a temporary venv, starts the installed entrypoint, and checks MCP `initialize`, `tools/list`, and `freecad_command_describe` under the `free` profile.
- Static MCP resource coverage includes architecture, session state, roadmap status, testing, Sketcher capabilities, GUI attach planning, GUI 1.1.1 research, vision debug pipeline, Workbench bridge setup, Workbench artifact shape, TechDraw/CAM/FEM planning, product modules, product bundles, distribution profiles, schemas, and inventory summary.
- Unit guard for structured launch errors, runtime output truncation, compact execution metadata, and long-code temp-script execution (`test_runtime_bridge.py`).
- Unit guard for persistent worker request/response framing, structured worker errors, fake crash injection cleanup, long worker temp-script lifecycle, cross-field input validation, session cleanup, and unknown-session errors (`test_persistent_bridge.py`).
- Unit guard for GUI bridge attach/call/detach/error handling, GUI primitive-create/object-label delegation, and Sketcher/PartDesign GUI state/edit/activation/task-state delegation against a fake local HTTP bridge (`test_gui_bridge.py`).
- Unit guard for Workbench bridge registration, parent-module `InitGui.py` shim delegation, `__file__`-less FreeCAD exec behavior, bundled sibling bridge lookup, and autostart environment handling with fake `FreeCAD`/`FreeCADGui` modules (`test_workbench_bridge.py`).
- Unit guard for the Workbench artifact manifest file list, hashes, consuming profiles, and zip naming (`test_workbench_artifact.py`).
- Opt-in live FreeCAD GUI attach smoke (`FREECAD_MCP_GUI_SMOKE=1 scripts\verify.ps1` or `scripts/smoke_gui_attach.py`) launches FreeCAD GUI, starts the bridge, selects two Part faces, reads them via MCP GUI tools, sets a GUI object Label, enters/leaves a Sketcher edit session, reads feature-task state, activates a PartDesign Body, fits the view, closes the GUI process, and verifies a Fixed Assembly joint populated from those selection records.
- Unit guard for `CadToolService` host-side dispatch/validation (required-field, `compact_execution`, `timeout` bounds, `object_delete` selector, missing-FreeCADCmd), the CAD domain-service split, plus `CAD_ACTION_SCRIPT` and `FREECAD_WORKER_SCRIPT` integrity (compilable, retain `__ARGS_B64__`/worker protocol markers and null-shape summary metadata) and runtime-script loading/missing-script error (`test_cad_tools.py`, `test_persistent_bridge.py`).
- Unit guard for `safe_source_path` in-root acceptance, absolute/parent-traversal rejection, and (POSIX-only) symlink-escape rejection (`test_static_tools.py`).
- Unit guard for the persistent worker session cap (`max_sessions`) and de-tautologized worker selector guards using a real worker session with message-matched assertions (`test_persistent_bridge.py`).

Expected future checks:

- MCP tool schema tests.
- Run the unit suite on at least one POSIX CI leg so the `safe_source_path` symlink-escape test executes (it self-skips where symlink creation is not permitted, e.g. Windows without Developer Mode).
- Real imported third-party fixture files once small license-clean samples are chosen.
- Signed FreeCAD Addon Manager packaging and installed-addon integration tests after that packaging path is chosen.
