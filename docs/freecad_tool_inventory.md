# FreeCAD MCP Tool Inventory

- Upstream: `https://github.com/FreeCAD/FreeCAD.git`
- Branch/commit: `main` / `dee977f98f8a8542c8db0be2ecc529a771931d01`
- Scanned commands: **1112**
- Workbench/module directories: **32**
- Source split: cpp=685, python=427

## Proposed MCP Tool Families

| Priority | Family | Initial tools | Source evidence |
| --- | --- | --- | --- |
| P0 | `freecad.source` | `freecad_source_search`, `freecad_source_open`, `freecad_source_symbol_index` | Needed to answer questions against the checked-out FreeCAD source. |
| P0 | `freecad.session` | `freecad_session_start`, `freecad_session_list`, `freecad_session_status`, `freecad_session_close`, `freecad_worker_session_start`, `freecad_worker_session_list`, `freecad_worker_session_status`, `freecad_worker_session_close`, `freecad_worker_document_new`, `freecad_worker_document_open`, `freecad_worker_document_save`, `freecad_worker_document_recompute`, `freecad_worker_document_close`, `freecad_worker_document_export`, `freecad_worker_part_create_primitive`, `freecad_worker_part_boolean`, `freecad_worker_part_extrude`, `freecad_worker_part_revolve`, `freecad_worker_part_check_geometry`, `freecad_worker_sketch_create`, `freecad_worker_sketch_add_geometry`, `freecad_worker_sketch_add_constraint`, `freecad_worker_sketch_add_profile`, `freecad_worker_sketch_profile_create`, `freecad_worker_sketch_profile_validate`, `freecad_worker_sketch_edit_geometry`, `freecad_worker_sketch_edit_constraints`, `freecad_worker_sketch_transform`, `freecad_worker_sketch_auto_constrain`, `freecad_worker_sketch_validate`, `freecad_worker_mesh_import`, `freecad_worker_mesh_export`, `freecad_worker_mesh_evaluate`, `freecad_worker_mesh_repair`, `freecad_worker_mesh_boolean`, `freecad_worker_assembly_create`, `freecad_worker_assembly_insert`, `freecad_worker_assembly_create_joint`, `freecad_worker_assembly_solve`, `freecad_worker_assembly_bom`, `freecad_worker_object_list`, `freecad_worker_object_get`, `freecad_worker_object_set_properties`, `freecad_worker_object_delete`, `freecad_python_exec` | Hybrid server needs a live FreeCAD Python bridge for stateful operations. |
| P0 | `freecad.gui` | `freecad_gui_attach`, `freecad_gui_list`, `freecad_gui_detach`, `freecad_gui_status`, `freecad_gui_active_document_get`, `freecad_gui_active_view_get`, `freecad_gui_selection_get`, `freecad_gui_preselection_get`, `freecad_gui_selection_set`, `freecad_gui_view_fit` | GUI attach mode is required for active view, preselection, picked points, and selected edge/face state. |
| P0 | `freecad.document` | `freecad_document_new`, `freecad_document_open`, `freecad_document_save`, `freecad_document_recompute`, `freecad_document_export` | Core App document lifecycle is the base for every workbench. |
| P0 | `freecad.object` | `freecad_object_list`, `freecad_object_get`, `freecad_object_set_properties`, `freecad_object_delete`, `freecad_object_fit_view` | MCP clients need deterministic object inspection instead of blind command execution. |
| P1 | `freecad.command` | `freecad_command_list`, `freecad_command_describe`, `freecad_command_run` | Source scan found 1112 GUI command registrations across 26 modules. |
| P1 | `freecad.part` | `freecad_part_create_primitive`, `freecad_part_boolean`, `freecad_part_extrude`, `freecad_part_revolve`, `freecad_part_fillet`, `freecad_part_chamfer`, `freecad_part_check_geometry` | Part module exposes 75 scanned commands. |
| P1 | `freecad.sketcher` | `freecad_sketch_create`, `freecad_sketch_add_geometry`, `freecad_sketch_add_constraint`, `freecad_sketch_add_profile`, `freecad_sketch_profile_create`, `freecad_sketch_profile_validate`, `freecad_curve_fit_analyze`, `freecad_sketch_edit_geometry`, `freecad_sketch_edit_constraints`, `freecad_sketch_transform`, `freecad_sketch_auto_constrain`, `freecad_sketch_validate` | Sketcher module exposes 101 scanned commands. |
| P2 | `freecad.mesh` | `freecad_mesh_import`, `freecad_mesh_export`, `freecad_mesh_evaluate`, `freecad_mesh_repair`, `freecad_mesh_boolean` | Mesh and MeshPart modules expose 43 scanned commands. |
| P2 | `freecad.assembly` | `freecad_assembly_create`, `freecad_assembly_insert`, `freecad_assembly_create_joint`, `freecad_assembly_solve`, `freecad_assembly_bom` | Assembly module exposes 31 scanned commands. |
| P2 | `freecad.techdraw` | `freecad_techdraw_page_create`, `freecad_techdraw_view_create`, `freecad_techdraw_inspect`, `freecad_techdraw_page_export` | TechDraw module exposes 127 scanned commands and headless App APIs for DrawPage/DrawViewPart/DXF export. |
| P2 | `freecad.import_export` | `freecad_import_file`, `freecad_export_file`, `freecad_supported_formats` | Import/export commands are distributed across Part, Mesh, TechDraw, Spreadsheet, and Import modules. |
| P3 | `freecad.cam` | `freecad_cam_path_create`, `freecad_cam_path_inspect`, `freecad_cam_path_export` | CAM module exposes 49 scanned commands; first typed slice avoids job/toolbit/postprocessor mutation. |
| P3 | `freecad.fem` | `freecad_fem_analysis_create`, `freecad_fem_material_create`, `freecad_fem_constraint_create`, `freecad_fem_inspect` | FEM module exposes 102 scanned commands; first typed slice avoids solver execution. |

## Workbench Command Counts

| Module | Commands | Python files | C++ files | InitGui | Gui dir |
| --- | ---: | ---: | ---: | --- | --- |
| Gui | 208 |  |  | no | no |
| BIM | 147 | 223 | 0 | yes | no |
| TechDraw | 127 | 35 | 241 | yes | yes |
| Fem | 102 | 433 | 139 | yes | yes |
| Sketcher | 101 | 18 | 82 | yes | yes |
| Draft | 84 | 239 | 2 | yes | no |
| Part | 75 | 43 | 267 | yes | yes |
| CAM | 49 | 415 | 81 | yes | yes |
| PartDesign | 41 | 56 | 110 | yes | yes |
| Mesh | 36 | 6 | 148 | yes | yes |
| Assembly | 31 | 24 | 29 | yes | yes |
| OpenSCAD | 15 | 21 | 0 | yes | no |
| Robot | 15 | 6 | 95 | yes | yes |
| Spreadsheet | 15 | 6 | 29 | yes | yes |
| ReverseEngineering | 12 | 2 | 15 | yes | yes |
| Test | 11 | 26 | 3 | yes | yes |
| TemplatePyMod | 8 | 13 | 0 | yes | no |
| MeshPart | 7 | 3 | 16 | yes | yes |
| Surface | 7 | 5 | 24 | yes | yes |
| Material | 6 | 18 | 63 | yes | yes |
| Points | 6 | 4 | 15 | yes | yes |
| Import | 3 | 24 | 27 | yes | yes |
| Inspection | 2 | 2 | 7 | yes | yes |
| Measure | 2 | 6 | 30 | yes | yes |
| Cloud | 1 | 2 | 4 | yes | yes |
| Start | 1 | 3 | 19 | yes | yes |

## Representative Commands

| Module | Command | Menu text | Source |
| --- | --- | --- | --- |
| Assembly | `Assembly_ActivateAssembly` | Activate Assembly | `src/Mod/Assembly/CommandCreateAssembly.py:172` |
| Assembly | `Assembly_CreateAssembly` | New Assembly | `src/Mod/Assembly/CommandCreateAssembly.py:171` |
| Assembly | `Assembly_CreateBom` | Bill of Materials | `src/Mod/Assembly/CommandCreateBom.py:439` |
| Assembly | `Assembly_CreateJointAngle` | Angle Joint | `src/Mod/Assembly/CommandCreateJoint.py:516` |
| Assembly | `Assembly_CreateJointBall` | Ball Joint | `src/Mod/Assembly/CommandCreateJoint.py:512` |
| Assembly | `Assembly_CreateJointBelt` | Belt Joint | `src/Mod/Assembly/CommandCreateJoint.py:520` |
| Assembly | `Assembly_CreateJointCylindrical` | Cylindrical Joint | `src/Mod/Assembly/CommandCreateJoint.py:510` |
| Assembly | `Assembly_CreateJointDistance` | Distance Joint | `src/Mod/Assembly/CommandCreateJoint.py:513` |
| BIM | `Arch_Add` | Add Component | `src/Mod/BIM/bimcommands/BimArchUtils.py:609` |
| BIM | `Arch_Axis` | Axis | `src/Mod/BIM/bimcommands/BimAxis.py:146` |
| BIM | `Arch_AxisSystem` | Axis System | `src/Mod/BIM/bimcommands/BimAxis.py:147` |
| BIM | `Arch_AxisTools` | Axis Tools | `src/Mod/BIM/bimcommands/BimAxis.py:149` |
| BIM | `Arch_Building` | Building | `src/Mod/BIM/ArchBuilding.py:359` |
| BIM | `Arch_Building` | Building | `src/Mod/BIM/bimcommands/BimBuildingPart.py:99` |
| BIM | `Arch_Check` | Check | `src/Mod/BIM/bimcommands/BimArchUtils.py:616` |
| BIM | `Arch_CloneComponent` | Clone Component | `src/Mod/BIM/bimcommands/BimArchUtils.py:620` |
| CAM | `CAM_3dTools` |  | `src/Mod/CAM/InitGui.py:256` |
| CAM | `CAM_Area` | Area | `src/Mod/CAM/Gui/Command.cpp:43` |
| CAM | `CAM_Area_Workplane` | Area Workplane | `src/Mod/CAM/Gui/Command.cpp:142` |
| CAM | `CAM_Array` | Array | `src/Mod/CAM/Path/Op/Gui/Array.py:600` |
| CAM | `CAM_Camotics` | CAMotics | `src/Mod/CAM/Path/Main/Gui/Camotics.py:336` |
| CAM | `CAM_Comment` | Comment | `src/Mod/CAM/Path/Op/Gui/Comment.py:135` |
| CAM | `CAM_Compound` | Compound | `src/Mod/CAM/Gui/Command.cpp:239` |
| CAM | `CAM_Copy` | Copy | `src/Mod/CAM/Path/Op/Gui/Copy.py:149` |
| Cloud | `Cloud_Test` | Hello | `src/Mod/Cloud/Gui/Command.cpp:37` |
| Draft | `Draft_AddConstruction` | Add to Construction Group | `src/Mod/Draft/draftguitools/gui_groups.py:411` |
| Draft | `Draft_AddNamedGroup` | New Named Group | `src/Mod/Draft/draftguitools/gui_groups.py:452` |
| Draft | `Draft_AddToGroup` | Add to Group | `src/Mod/Draft/draftguitools/gui_groups.py:151` |
| Draft | `Draft_AddToLayer` | Add to Layer | `src/Mod/Draft/draftguitools/gui_layers.py:636` |
| Draft | `Draft_AnnotationStyleEditor` | Annotation Styles | `src/Mod/Draft/draftguitools/gui_annotationstyleeditor.py:442` |
| Draft | `Draft_ApplyStyle` | Apply Current Style | `src/Mod/Draft/draftguitools/gui_styles.py:78` |
| Draft | `Draft_Arc` | Arc | `src/Mod/Draft/draftguitools/gui_arcs.py:507` |
| Draft | `Draft_Arc_3Points` | Arc From 3 Points | `src/Mod/Draft/draftguitools/gui_arcs.py:677` |
| Fem | `FEM_Analysis` |  | `src/Mod/Fem/femcommands/commands.py:1381` |
| Fem | `FEM_ClippingPlaneAdd` |  | `src/Mod/Fem/femcommands/commands.py:1382` |
| Fem | `FEM_ClippingPlaneRemoveAll` |  | `src/Mod/Fem/femcommands/commands.py:1383` |
| Fem | `FEM_CompEmConstraints` | Electromagnetic Boundary Conditions | `src/Mod/Fem/Gui/Command.cpp:1499` |
| Fem | `FEM_CompEmEquations` | Electromagnetic Equations | `src/Mod/Fem/Gui/Command.cpp:1683` |
| Fem | `FEM_CompMechEquations` | Mechanical Equations | `src/Mod/Fem/Gui/Command.cpp:1879` |
| Fem | `FEM_CompSolvers` |  | `src/Mod/Fem/femcommands/commands.py:1443` |
| Fem | `FEM_ConstantVacuumPermittivity` |  | `src/Mod/Fem/femcommands/commands.py:1384` |
| Gui | `NaviCubeDraggableCmd` | Movable Navigation Cube | `src/Gui/NaviCube.cpp:1159` |
| Gui | `Std_About` | &About %1 | `src/Gui/CommandStd.cpp:231` |
| Gui | `Std_AboutQt` | About &Qt | `src/Gui/CommandStd.cpp:295` |
| Gui | `Std_ActivateNextWindow` | &Next | `src/Gui/CommandWindow.cpp:164` |
| Gui | `Std_ActivatePrevWindow` | &Previous | `src/Gui/CommandWindow.cpp:193` |
| Gui | `Std_Alignment` | Ali&gn To… | `src/Gui/CommandDoc.cpp:1949` |
| Gui | `Std_AlignToSelection` | &Align to Selection | `src/Gui/CommandView.cpp:4192` |
| Gui | `Std_AnnotationLabel` | Annotation Label | `src/Gui/CommandStd.cpp:979` |
| Import | `Import_Iges` | Import IGES | `src/Mod/Import/Gui/Command.cpp:137` |
| Import | `Import_ReadBREP` | Read BREP | `src/Mod/Import/Gui/Command.cpp:41` |
| Import | `Part_ImportStep` | Import STEP | `src/Mod/Import/Gui/Command.cpp:86` |
| Inspection | `Inspection_InspectElement` | Inspection… | `src/Mod/Inspection/Gui/Command.cpp:70` |
| Inspection | `Inspection_VisualInspection` | Visual Inspection… | `src/Mod/Inspection/Gui/Command.cpp:44` |
| Material | `Material_Edit` | Edit | `src/Mod/Material/Gui/Command.cpp:49` |
| Material | `Materials_InspectAppearance` | Inspect Appearance | `src/Mod/Material/Gui/Command.cpp:142` |
| Material | `Materials_InspectMaterial` | Inspect Material | `src/Mod/Material/Gui/Command.cpp:169` |
| Material | `Materials_MigrateToExternal` | Migrate | `src/Mod/Material/Gui/Command.cpp:198` |
| Material | `Std_SetAppearance` | &Appearance | `src/Mod/Material/Gui/Command.cpp:84` |
| Material | `Std_SetMaterial` | &Material | `src/Mod/Material/Gui/Command.cpp:113` |
| Measure | `Std_MassProperties` | Mass Properties | `src/Mod/Measure/Gui/Command.cpp:93` |
| Measure | `Std_Measure` | &Measure | `src/Mod/Measure/Gui/Command.cpp:47` |
| Mesh | `Mesh_AddFacet` | Add Triangle | `src/Mod/Mesh/Gui/Command.cpp:746` |
| Mesh | `Mesh_BoundingBox` | Bounding Box Info | `src/Mod/Mesh/Gui/Command.cpp:1483` |
| Mesh | `Mesh_BuildRegularSolid` | Regular Solid | `src/Mod/Mesh/Gui/Command.cpp:1538` |
| Mesh | `Mesh_CrossSections` | Cross-Sections | `src/Mod/Mesh/Gui/Command.cpp:988` |
| Mesh | `Mesh_CurvatureInfo` | Curvature Info | `src/Mod/Mesh/Gui/Command.cpp:634` |
| Mesh | `Mesh_Decimating` | Decimate | `src/Mod/Mesh/Gui/Command.cpp:1373` |
| Mesh | `Mesh_Difference` | Difference | `src/Mod/Mesh/Gui/Command.cpp:168` |
| Mesh | `Mesh_EvaluateFacet` | Face Info | `src/Mod/Mesh/Gui/Command.cpp:1121` |
| MeshPart | `MeshPart_CreateFlatFace` | Unwrap Face | `src/Mod/MeshPart/Gui/MeshFlatteningCommand.py:132` |
| MeshPart | `MeshPart_CreateFlatMesh` | Unwrap Mesh | `src/Mod/MeshPart/Gui/MeshFlatteningCommand.py:131` |
| MeshPart | `MeshPart_CrossSections` | Cross-Sections | `src/Mod/MeshPart/Gui/Command.cpp:272` |
| MeshPart | `MeshPart_CurveOnMesh` | Curve on Mesh | `src/Mod/MeshPart/Gui/Command.cpp:308` |
| MeshPart | `MeshPart_Mesher` | Mesh From Shape | `src/Mod/MeshPart/Gui/Command.cpp:54` |
| MeshPart | `MeshPart_SectionByPlane` | Section | `src/Mod/MeshPart/Gui/Command.cpp:186` |
| MeshPart | `MeshPart_TrimByPlane` | Trim Mesh | `src/Mod/MeshPart/Gui/Command.cpp:80` |
| OpenSCAD | `OpenSCAD_AddOpenSCADElement` | Add OpenSCAD Element | `src/Mod/OpenSCAD/OpenSCADCommands.py:601` |
| OpenSCAD | `OpenSCAD_ColorCodeShape` | Color Shapes | `src/Mod/OpenSCAD/OpenSCADCommands.py:590` |
| OpenSCAD | `OpenSCAD_Edgestofaces` | Convert Edges to Faces | `src/Mod/OpenSCAD/OpenSCADCommands.py:592` |
| OpenSCAD | `OpenSCAD_ExpandPlacements` | Expand Placements | `src/Mod/OpenSCAD/OpenSCADCommands.py:598` |
| OpenSCAD | `OpenSCAD_ExplodeGroup` | Explode Group | `src/Mod/OpenSCAD/OpenSCADCommands.py:591` |
| OpenSCAD | `OpenSCAD_Hull` | Hull | `src/Mod/OpenSCAD/OpenSCADCommands.py:603` |
| OpenSCAD | `OpenSCAD_IncreaseToleranceFeature` | Increase Tolerance Feature | `src/Mod/OpenSCAD/OpenSCADCommands.py:597` |
| OpenSCAD | `OpenSCAD_MeshBoolean` | Mesh Boolean | `src/Mod/OpenSCAD/OpenSCADCommands.py:602` |
| Part | `Part_Boolean` | Boolean Operation | `src/Mod/Part/Gui/Command.cpp:1399` |
| Part | `Part_BooleanFragments` | Boolean Fragments | `src/Mod/Part/BOPTools/SplitFeatures.py:707` |
| Part | `Part_Box` | Cube | `src/Mod/Part/Gui/CommandParametric.cpp:109` |
| Part | `Part_Box2` | Box Fix 1 | `src/Mod/Part/Gui/Command.cpp:129` |
| Part | `Part_Box3` | Box Fix 2 | `src/Mod/Part/Gui/Command.cpp:172` |
| Part | `Part_BoxSelection` | Box Selection | `src/Mod/Part/Gui/Command.cpp:2390` |
| Part | `Part_Builder` | Shape Builder | `src/Mod/Part/Gui/Command.cpp:1698` |
| Part | `Part_Chamfer` | Chamfer | `src/Mod/Part/Gui/Command.cpp:1603` |
| PartDesign | `PartDesign_AdditiveHelix` | Additive Helix | `src/Mod/PartDesign/Gui/Command.cpp:1660` |
| PartDesign | `PartDesign_AdditiveLoft` | Additive Loft | `src/Mod/PartDesign/Gui/Command.cpp:1561` |
| PartDesign | `PartDesign_AdditivePipe` | Additive Pipe | `src/Mod/PartDesign/Gui/Command.cpp:1461` |
| PartDesign | `PartDesign_Body` | New Body | `src/Mod/PartDesign/Gui/CommandBody.cpp:88` |
| PartDesign | `PartDesign_Boolean` | Boolean Operation | `src/Mod/PartDesign/Gui/Command.cpp:2576` |
| PartDesign | `PartDesign_Chamfer` | Chamfer | `src/Mod/PartDesign/Gui/Command.cpp:1987` |
| PartDesign | `PartDesign_Clone` | Clone | `src/Mod/PartDesign/Gui/Command.cpp:488` |
| PartDesign | `PartDesign_CompPrimitiveAdditive` | Additive Primitive | `src/Mod/PartDesign/Gui/CommandPrimitive.cpp:72` |
| Points | `Points_Convert` | Convert to Points | `src/Mod/Points/Gui/Command.cpp:198` |
| Points | `Points_Export` | Export Points… | `src/Mod/Points/Gui/Command.cpp:146` |
| Points | `Points_Import` | Import Points… | `src/Mod/Points/Gui/Command.cpp:64` |
| Points | `Points_Merge` | Merge Point Clouds | `src/Mod/Points/Gui/Command.cpp:337` |
| Points | `Points_PolyCut` | Cut Point Cloud | `src/Mod/Points/Gui/Command.cpp:287` |
| Points | `Points_Structure` | Structured Point Cloud | `src/Mod/Points/Gui/Command.cpp:401` |
| ReverseEngineering | `Reen_ApproxCurve` | Approximate B-Spline Curve… | `src/Mod/ReverseEngineering/Gui/Command.cpp:63` |
| ReverseEngineering | `Reen_ApproxCylinder` | Cylinder | `src/Mod/ReverseEngineering/Gui/Command.cpp:242` |
| ReverseEngineering | `Reen_ApproxPlane` | Plane | `src/Mod/ReverseEngineering/Gui/Command.cpp:137` |
| ReverseEngineering | `Reen_ApproxPolynomial` | Polynomial Surface | `src/Mod/ReverseEngineering/Gui/Command.cpp:358` |
| ReverseEngineering | `Reen_ApproxSphere` | Sphere | `src/Mod/ReverseEngineering/Gui/Command.cpp:310` |
| ReverseEngineering | `Reen_ApproxSurface` | Approximate B-Spline Surface… | `src/Mod/ReverseEngineering/Gui/Command.cpp:98` |
| ReverseEngineering | `Reen_MeshBoundary` | Wire From Mesh Boundary… | `src/Mod/ReverseEngineering/Gui/Command.cpp:527` |
| ReverseEngineering | `Reen_PoissonReconstruction` | Poisson… | `src/Mod/ReverseEngineering/Gui/Command.cpp:592` |
| Robot | `Robot_AddToolShape` | Tool | `src/Mod/Robot/Gui/CommandInsertRobot.cpp:42` |
| Robot | `Robot_Create` | Place Robot | `src/Mod/Robot/Gui/Command.cpp:197` |
| Robot | `Robot_CreateTrajectory` | Trajectory | `src/Mod/Robot/Gui/CommandTrajectory.cpp:51` |
| Robot | `Robot_Edge2Trac` | Edge to Trajectory | `src/Mod/Robot/Gui/CommandTrajectory.cpp:375` |
| Robot | `Robot_ExportKukaCompact` | Kuka Compact Subroutine | `src/Mod/Robot/Gui/CommandExport.cpp:42` |
| Robot | `Robot_ExportKukaFull` | Kuka Full Subroutine | `src/Mod/Robot/Gui/CommandExport.cpp:124` |
| Robot | `Robot_InsertWaypoint` | Insert in Trajectory | `src/Mod/Robot/Gui/CommandTrajectory.cpp:87` |
| Robot | `Robot_InsertWaypointPreselect` | Insert in Trajectory | `src/Mod/Robot/Gui/CommandTrajectory.cpp:160` |
| Sketcher | `Sketcher_ArcOverlay` | Toggle Circular Helper for Arcs | `src/Mod/Sketcher/Gui/CommandSketcherOverlay.cpp:399` |
| Sketcher | `Sketcher_BSplineComb` | Toggle B-Spline Curvature Comb | `src/Mod/Sketcher/Gui/CommandSketcherOverlay.cpp:120` |
| Sketcher | `Sketcher_BSplineConvertToNURBS` | Geometry to B-Spline | `src/Mod/Sketcher/Gui/CommandSketcherBSpline.cpp:111` |
| Sketcher | `Sketcher_BSplineDecreaseDegree` | Decrease B-Spline Degree | `src/Mod/Sketcher/Gui/CommandSketcherBSpline.cpp:266` |
| Sketcher | `Sketcher_BSplineDecreaseKnotMultiplicity` | Decrease Knot Multiplicity | `src/Mod/Sketcher/Gui/CommandSketcherBSpline.cpp:545` |
| Sketcher | `Sketcher_BSplineDegree` | Toggle B-Spline Degree | `src/Mod/Sketcher/Gui/CommandSketcherOverlay.cpp:62` |
| Sketcher | `Sketcher_BSplineIncreaseDegree` | Increase B-Spline Degree | `src/Mod/Sketcher/Gui/CommandSketcherBSpline.cpp:189` |
| Sketcher | `Sketcher_BSplineIncreaseKnotMultiplicity` | Increase Knot Multiplicity | `src/Mod/Sketcher/Gui/CommandSketcherBSpline.cpp:388` |
| Spreadsheet | `Spreadsheet_AlignBottom` | Align &Bottom | `src/Mod/Spreadsheet/Gui/Command.cpp:510` |
| Spreadsheet | `Spreadsheet_AlignCenter` | Align Horizontal &Center | `src/Mod/Spreadsheet/Gui/Command.cpp:339` |
| Spreadsheet | `Spreadsheet_AlignLeft` | Align &Left | `src/Mod/Spreadsheet/Gui/Command.cpp:282` |
| Spreadsheet | `Spreadsheet_AlignRight` | Align &Right | `src/Mod/Spreadsheet/Gui/Command.cpp:396` |
| Spreadsheet | `Spreadsheet_AlignTop` | Align &Top | `src/Mod/Spreadsheet/Gui/Command.cpp:453` |
| Spreadsheet | `Spreadsheet_AlignVCenter` | Align &Vertical Center | `src/Mod/Spreadsheet/Gui/Command.cpp:567` |
| Spreadsheet | `Spreadsheet_CreateSheet` | &New Spreadsheet | `src/Mod/Spreadsheet/Gui/Command.cpp:951` |
| Spreadsheet | `Spreadsheet_Export` | &Export Spreadsheet | `src/Mod/Spreadsheet/Gui/Command.cpp:237` |
| Start | `Start_Start` | &Start Page | `src/Mod/Start/Gui/Manipulator.cpp:41` |
| Surface | `Surface_BlendCurve` | Blend Curve | `src/Mod/Surface/Gui/Command.cpp:216` |
| Surface | `Surface_CurveOnMesh` | Curve on Mesh | `src/Mod/Surface/Gui/Command.cpp:174` |
| Surface | `Surface_Cut` | Surface Cut | `src/Mod/Surface/Gui/Command.cpp:50` |
| Surface | `Surface_ExtendFace` | Extend Face | `src/Mod/Surface/Gui/Command.cpp:282` |
| Surface | `Surface_Filling` | Filling | `src/Mod/Surface/Gui/Command.cpp:108` |
| Surface | `Surface_GeomFillSurface` | Fill Boundary Curves | `src/Mod/Surface/Gui/Command.cpp:144` |
| Surface | `Surface_Sections` | Sections | `src/Mod/Surface/Gui/Command.cpp:328` |
| TechDraw | `TechDraw_2LineCenterLine` | Centerline Between 2 Lines | `src/Mod/TechDraw/Gui/CommandAnnotate.cpp:785` |
| TechDraw | `TechDraw_2PointCenterLine` | Centerline Between 2 Points | `src/Mod/TechDraw/Gui/CommandAnnotate.cpp:860` |
| TechDraw | `TechDraw_2PointCosmeticLine` | Cosmetic Line Through 2 Points | `src/Mod/TechDraw/Gui/CommandAnnotate.cpp:973` |
| TechDraw | `TechDraw_3PtAngleDimension` | Angle Dimension From 3 Points | `src/Mod/TechDraw/Gui/CommandCreateDims.cpp:1773` |
| TechDraw | `TechDraw_ActiveView` | Active View | `src/Mod/TechDraw/Gui/Command.cpp:702` |
| TechDraw | `TechDraw_AlignVertexesHorizontally` | Align Vertices/Edge Horizontally | `src/Mod/TechDraw/Gui/CommandAlign.cpp:150` |
| TechDraw | `TechDraw_AlignVertexesVertically` | Align Vertices/Edge Vertically | `src/Mod/TechDraw/Gui/CommandAlign.cpp:117` |
| TechDraw | `TechDraw_AngleDimension` | Angle Dimension | `src/Mod/TechDraw/Gui/CommandCreateDims.cpp:1726` |
| TemplatePyMod | `TemplatePyCheckable` |  | `src/Mod/TemplatePyMod/Commands.py:260` |
| TemplatePyMod | `TemplatePyGroup` |  | `src/Mod/TemplatePyMod/Commands.py:259` |
| TemplatePyMod | `TemplatePyGrp_1` |  | `src/Mod/TemplatePyMod/Commands.py:256` |
| TemplatePyMod | `TemplatePyGrp_2` |  | `src/Mod/TemplatePyMod/Commands.py:257` |
| TemplatePyMod | `TemplatePyGrp_3` |  | `src/Mod/TemplatePyMod/Commands.py:258` |
| TemplatePyMod | `TemplatePyMod_Cmd4` |  | `src/Mod/TemplatePyMod/Commands.py:253` |
| TemplatePyMod | `TemplatePyMod_Cmd5` |  | `src/Mod/TemplatePyMod/Commands.py:254` |
| TemplatePyMod | `TemplatePyMod_Cmd6` |  | `src/Mod/TemplatePyMod/Commands.py:255` |
| Test | `Test_InsertFeature` | Insert a TestFeature | `src/Mod/Test/TestGui.py:238` |
| Test | `Test_Test` | Self-test... | `src/Mod/Test/TestGui.py:228` |
| Test | `Test_TestAll` | Test all | `src/Mod/Test/TestGui.py:232` |
| Test | `Test_TestAllText` | Test all | `src/Mod/Test/TestGui.py:229` |
| Test | `Test_TestBase` | Test base | `src/Mod/Test/TestGui.py:234` |
| Test | `Test_TestBaseText` | Test base | `src/Mod/Test/TestGui.py:231` |
| Test | `Test_TestCreateMenu` | Add menu | `src/Mod/Test/TestGui.py:236` |
| Test | `Test_TestDeleteMenu` | Remove menu | `src/Mod/Test/TestGui.py:237` |

## Notes

- This is a static source scan. Runtime-only commands and dynamically named commands may need a live FreeCAD bridge pass.
- C++ command names are taken from `Gui::Command("...")` constructors.
- Python command names are taken from literal `FreeCADGui.addCommand(...)` / `Gui.addCommand(...)` calls.
- For the MCP server, prefer typed document/object/Part/Sketch tools first, then expose `freecad_command_run` as a lower-level escape hatch.
