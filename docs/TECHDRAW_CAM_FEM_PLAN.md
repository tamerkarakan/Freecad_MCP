# TechDraw, CAM, FEM Typed Wrapper Plan

FreeCAD source scan commit: `dee977f98f8a8542c8db0be2ecc529a771931d01`.

## Recommendation

The first typed slices should avoid external solvers, machine postprocessors, and GUI-only exporters. TechDraw is the most complete first slice because it has small headless App APIs that can be smoke-tested with `FreeCADCmd`: page creation, SVG template attachment, `DrawViewPart` creation, page/view inspection, and DXF page export.

CAM and FEM have larger dependency surfaces, so their first slices are intentionally conservative: raw `Path::Feature` command paths for CAM, and analysis/material/fixed-force object graph setup for FEM.

## Source Evidence

| Area | Evidence |
| --- | --- |
| TechDraw page/template | `src/Mod/TechDraw/TDTest/TechDrawTestUtilities.py:13-16` creates `TechDraw::DrawPage` and `TechDraw::DrawSVGTemplate`, then assigns `page.Template`. |
| TechDraw part view | `src/Mod/TechDraw/TDTest/DrawViewPartTest.py:33-35` creates `TechDraw::DrawViewPart`, calls `page.addView(view)`, and sets `view.Source`. |
| Headless DXF export | `src/Mod/TechDraw/App/AppTechDrawPy.cpp:142-145` exposes `writeDXFView` and `writeDXFPage`. |
| GUI-only SVG/PDF export | `src/Mod/TechDraw/Gui/AppTechDrawGuiPy.cpp:56-60` exposes `exportPageAsPdf` and `exportPageAsSvg` through `TechDrawGui`, so these belong behind GUI attach/workbench validation. |
| CAM app surface | `src/Mod/CAM/App/AppPath.cpp:84-95` initializes `Path::Command`, `Path::Toolpath`, `Path::Feature`, `Path::FeatureCompound`, and `Path::FeatureArea`; production wrappers should validate jobs/toolbits/postprocessors before mutation. |
| FEM app surface | `src/Mod/Fem/App/AppFem.cpp:140-169` initializes `Fem::FemAnalysis`, constraints, solver/mesh objects; Python examples such as `src/Mod/Fem/femexamples/ccx_cantilever_base_solid.py:53-95` use `ObjectsFem` factories. |

## Implemented Slices

### TechDraw

| Tool | Backend |
| --- | --- |
| `freecad_techdraw_page_create` | Adds `TechDraw::DrawPage` and `TechDraw::DrawSVGTemplate`. |
| `freecad_techdraw_view_create` | Adds `TechDraw::DrawViewPart`, sets `Source`, and attaches it with `page.addView(view)`. |
| `freecad_techdraw_inspect` | Summarizes TechDraw pages/views and source object links. |
| `freecad_techdraw_page_export` | Uses headless `TechDraw.writeDXFPage(page, output_path)` for DXF export. |

### CAM

| Tool | Backend |
| --- | --- |
| `freecad_cam_path_create` | Creates `Path::Feature` from explicit `Path.Command` specs. |
| `freecad_cam_path_inspect` | Summarizes path command counts and command parameters. |
| `freecad_cam_path_export` | Writes raw `Path.Path.toGCode()` output without invoking a machine postprocessor. |

### FEM

| Tool | Backend |
| --- | --- |
| `freecad_fem_analysis_create` | Uses `ObjectsFem.makeAnalysis`. |
| `freecad_fem_material_create` | Uses `ObjectsFem.makeMaterialSolid` and adds it to the analysis. |
| `freecad_fem_constraint_create` | Uses `ObjectsFem.makeConstraintFixed` or `ObjectsFem.makeConstraintForce` and adds it to the analysis. |
| `freecad_fem_inspect` | Summarizes FEM analyses, materials, constraints, references, and member links. |

## Deferred CAM/FEM Scope

- CAM postprocessor output, toolbit libraries, operation generation, and job validation need fixture-backed machine/post contracts before becoming default typed tools.
- FEM solver execution, mesh generation, and result import need solver availability and fixture-backed property contracts before becoming default typed tools.

## Verification

`scripts/smoke_cad_tools.py` creates a Part box, adds a TechDraw page and part view, inspects the page/view graph, exports DXF through headless TechDraw, creates/exports a CAM path, and creates/inspects a FEM analysis with material, fixed constraint, and force constraint.
