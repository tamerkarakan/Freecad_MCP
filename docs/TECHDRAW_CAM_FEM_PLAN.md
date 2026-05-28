# TechDraw, CAM, FEM Typed Wrapper Plan

FreeCAD source scan commit: `dee977f98f8a8542c8db0be2ecc529a771931d01`.

## Recommendation

The first typed slice is TechDraw. It has small headless App APIs that can be smoke-tested with `FreeCADCmd`: page creation, SVG template attachment, `DrawViewPart` creation, page/view inspection, and DXF page export.

CAM and FEM remain design-first for now. Both have larger solver/postprocessor/toolbit dependency surfaces and should start with source-backed, fixture-driven wrappers rather than broad command mirroring.

## Source Evidence

| Area | Evidence |
| --- | --- |
| TechDraw page/template | `src/Mod/TechDraw/TDTest/TechDrawTestUtilities.py:13-16` creates `TechDraw::DrawPage` and `TechDraw::DrawSVGTemplate`, then assigns `page.Template`. |
| TechDraw part view | `src/Mod/TechDraw/TDTest/DrawViewPartTest.py:33-35` creates `TechDraw::DrawViewPart`, calls `page.addView(view)`, and sets `view.Source`. |
| Headless DXF export | `src/Mod/TechDraw/App/AppTechDrawPy.cpp:142-145` exposes `writeDXFView` and `writeDXFPage`. |
| GUI-only SVG/PDF export | `src/Mod/TechDraw/Gui/AppTechDrawGuiPy.cpp:56-60` exposes `exportPageAsPdf` and `exportPageAsSvg` through `TechDrawGui`, so these belong behind GUI attach/workbench validation. |
| CAM app surface | `src/Mod/CAM/App/AppPath.cpp:84-95` initializes `Path::Command`, `Path::Toolpath`, `Path::Feature`, `Path::FeatureCompound`, and `Path::FeatureArea`; production wrappers should validate jobs/toolbits/postprocessors before mutation. |
| FEM app surface | `src/Mod/Fem/App/AppFem.cpp:140-169` initializes `Fem::FemAnalysis`, constraints, solver/mesh objects; Python examples such as `src/Mod/Fem/femexamples/ccx_cantilever_base_solid.py:53-95` use `ObjectsFem` factories. |

## Implemented TechDraw Slice

| Tool | Backend |
| --- | --- |
| `freecad_techdraw_page_create` | Adds `TechDraw::DrawPage` and `TechDraw::DrawSVGTemplate`. |
| `freecad_techdraw_view_create` | Adds `TechDraw::DrawViewPart`, sets `Source`, and attaches it with `page.addView(view)`. |
| `freecad_techdraw_inspect` | Summarizes TechDraw pages/views and source object links. |
| `freecad_techdraw_page_export` | Uses headless `TechDraw.writeDXFPage(page, output_path)` for DXF export. |

## Deferred CAM/FEM Scope

- CAM first safe candidates: inspect/import `Path::Feature`, create simple `Path::Feature` from explicit G-code commands, validate existing CAM job via `CAMTests`/sanity APIs, and export postprocessor output only from fixture-backed jobs.
- FEM first safe candidates: create `ObjectsFem.makeAnalysis`, create material/solver placeholders, add simple fixed/force constraints to selected references, and inspect analysis membership. Solver execution should stay out of the first typed slice.
- Both need license-clean fixture documents and source-backed property contracts before being promoted from design to default typed tools.

## Verification

`scripts/smoke_cad_tools.py` creates a Part box, adds a TechDraw page and part view, inspects the page/view graph, exports DXF through headless TechDraw, and asserts the exported file exists and is non-empty.
