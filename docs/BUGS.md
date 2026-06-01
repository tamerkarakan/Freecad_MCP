# Bugs And Risks

## Open

- GUI attach tools now expose active document/view and selection/preselection through a local bridge, opt-in live GUI smoke passes, a module-path Workbench host exists, and a generated local `freecad-mcp-workbench.zip` module artifact exists; signed/installed FreeCAD Addon Manager packaging is still pending.
- Sketcher GUI-only command handlers, edit-mode overlays, and active-selection workflows are not covered by headless typed tools; they require GUI attach or Workbench-hosted bridge mode.
- Sketcher `Group` and `Text` constraint constructors can terminate FreeCADCmd in this FreeCAD 1.1.1 build; typed tools now block those raw constraint types until a stable API path exists.
- Reference-image tracing can produce visually plausible but topologically open Sketcher geometry if raw lines/arcs/B-splines are added without `Coincident` constraints. Use the connected sequence guard on `freecad_sketch_add_geometry` for ordered closed contours; the user-provided local sample `runs/reference_profile_sketch.FCStd` is an example of the bad pattern, with 24 geometry items, 0 constraints, and open vertices.
- Loop-based `freecad_sketch_profile_create` is the preferred mitigation for traced production profiles: it rejects non-colocated endpoints before constraining, validates Part face creation, rejects declared line/polyline fallback when curve contracts are required, reports native geometry type/intent mismatches, and reports branch/micro-offset patterns instead of relying only on DoF/open-vertex metrics.
- PartDesign workflows require sketches to live inside a Body and be attached to an origin plane or datum/support object. `freecad_sketch_create`/`freecad_sketch_profile_create` now accept `body_name` plus `attachment_plane` or `attachment_object`, `freecad_partdesign_datum_plane_create` creates offset support planes without stealing the solid Body Tip, additive/subtractive Loft accept Body sketches plus datum-attached section sketches, additive/subtractive Pipe accept Body profile and spine sketches, subtractive Loft/Pipe require an existing Body solid before cutting, and `freecad_partdesign_pad` should be used when a Body feature is required instead of standalone `freecad_part_extrude`.
- Advanced Pipe coverage is split into known-good fixture paths: multisection sections/scaling and auxiliary-spine orientation pass separately. A trial fixture that combined auxiliary spine plus multisection sections in one Additive Pipe returned FreeCAD `BRep_API: command not done`; do not promise that combined flow until a source-backed/tutorial-backed fixture is added.
- Long mixed persistent-worker sessions can still expose FreeCAD global-state/recompute hangs around heavy PartDesign feature chains. The worker smoke isolates Revolution/Groove, Additive/Subtractive Loft, and Additive/Subtractive Pipe in clean worker sessions; prefer shorter worker sessions for heavy PartDesign feature chains until deeper lifecycle isolation is implemented.
- Assembly joint creation now creates native JointObject proxies and opt-in GUI connector-reference smoke populates `Reference1`/`Reference2`; broader solver correctness fixtures are still pending.
- Mesh boolean support depends on the actual FreeCAD build and may return tool errors on unsupported operations.
- TechDraw typed tools currently support headless DXF export only; SVG/PDF export uses `TechDrawGui` APIs and should be validated behind GUI attach/workbench mode.
- CAM/FEM first typed slices avoid machine postprocessor and solver execution; job/toolbit/postprocessor/solver workflows still need fixture-backed property contracts before default mutation tools are safe.
- File reads/imports accept caller-provided paths; write paths are workspace-gated by default.
- Generated inventory is static; dynamically named commands can be missed.
- Python `GetResources` parsing is conservative and can miss non-literal metadata.
- C++ parsing is regex-based and should be replaced or reinforced if source patterns become more complex.
- `freecad_python_exec` is a low-level escape hatch and requires explicit unsafe opt-in.
- The GUI bridge script is still local loopback only. The Workbench zip embeds it beside `InitGui.py`, but it is not a signed FreeCAD Addon Manager package yet; prefer a bearer token for attached GUI sessions.
- Even with response truncation, some Windows MCP clients may still report `Transport closed` under extreme runtime output/IO conditions; continue validating in long smoke sessions.
- `freecad_part_extrude` currently supports wire/face-like profiles; directly extruding an existing solid shape can return the FreeCAD OCC error `Solids are not Processed`.
- Embedded FreeCAD runtime scripts now live in `src/freecad_mcp/runtime_scripts/*.py` and are read at import; they are package data and must ship with the package, otherwise the stdio server fails to start (the loader raises a clear, named error rather than a bare traceback).
- The `safe_source_path` symlink-escape unit test only runs where symlink creation is permitted; it self-skips (with a visible reason) on Windows without Developer Mode/privilege, so that branch is currently exercised only on POSIX.

## Closed

- GUI bridge object summaries previously assumed every object `Shape` could expose topology and volume; empty/invalid Sketch shapes in live FreeCAD GUI can raise `shape is invalid`, so GUI shape summaries now guard invalid/null shapes and return bounded counts instead of failing state reads.
- FreeCAD 1.1.1 can return a present-but-null `Shape` for shell-only Sketcher `Part::Extrusion` features; runtime shape summaries now report structured `is_null=true` metadata with zero counts instead of returning `None` and breaking downstream smoke/tool consumers.
- Persistent worker mode previously covered only session/document/object basics, document export, and several Part operations; it now exposes worker Sketcher, mesh, and Assembly typed operations with real FreeCAD smoke coverage.
- Persistent worker crashed/stopped sessions could remain in the manager after a request/status failure; manager cleanup now drops them and unit tests inject a fake worker crash.
- Closed Sketcher/profile extrusion previously produced a shell-only `Part::Feature`; `freecad_part_extrude` now builds a planar face from closed wires before extrusion so rectangle profiles become solids.
- `freecad_mesh_repair` previously attempted to mutate `Mesh::Feature.Mesh` directly and could hit immutable mesh errors; it now repairs a copy and assigns it back, with replacement-object fallback.
- Response serialization errors in `serve_stdio` previously could terminate the stdio loop; they now fall back to a structured `-32603` error response.
- Large runtime envelopes could grow excessively because raw `argv`/`stdout`/`stderr` were returned verbatim; execution payloads now return truncated previews plus total-length metadata.
- Extremely large runtime outputs can opt into compact execution metadata to omit stdout/stderr/argv text entirely while keeping totals and hashes.
- Some MCP clients call `resources/templates/list` even when no resource templates are exposed; the server now returns an empty `resourceTemplates` list instead of `-32601`.
- The server previously used a minimal local JSON-RPC implementation because the Python MCP SDK was not available in the selected runtime; it now depends on `mcp>=1.0` and uses `mcp.server.lowlevel.Server` for stdio.
- Persistent worker processes could survive MCP server EOF if sessions were not explicitly closed; stdio shutdown now calls service cleanup.
- Large process-per-call CAD scripts could exceed the Windows command-line length limit when passed through `FreeCADCmd -c`; long scripts now run from a temporary `.py` file and are cleaned up after execution.
- Launching FreeCAD with `-M freecad_workbench` previously did not show the Workbench because FreeCAD 1.1.1 treats additional module paths as flat module directories. A parent-level `freecad_workbench/InitGui.py` shim now delegates to `freecad_workbench/FreeCADMCP/InitGui.py`; both InitGui files avoid relying on `__file__` because FreeCAD executes them without defining it.
