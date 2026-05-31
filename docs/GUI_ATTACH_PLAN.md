# GUI Attach Plan

FreeCAD GUI attach is the bridge mode for live selection, active view, and selected subelement workflows. Headless `FreeCADCmd` remains the default for deterministic file-scoped automation; GUI attach should be opt-in because it must run on FreeCAD's GUI Python main thread.

For GUI expansion priorities, every coding session should read `docs/GUI_1_1_1_RESEARCH.md` first. That file records the FreeCAD 1.1/1.1.1 official documentation and blog research, the local command-count inventory, and the product-oriented order: Sketcher + PartDesign, TechDraw, Assembly, visual assist, then guarded CAM/FEM.

## Source Evidence

FreeCAD source scan commit: `dee977f98f8a8542c8db0be2ecc529a771931d01`.

| Capability | FreeCAD source evidence |
| --- | --- |
| Active GUI document | `src/Gui/ApplicationPy.cpp:344`, `src/Gui/ApplicationPy.cpp:592` expose `FreeCADGui.activeDocument()` and require the Python main thread. |
| Active GUI view | `src/Gui/ApplicationPy.cpp:358`, `src/Gui/ApplicationPy.cpp:609` expose `FreeCADGui.activeView(typeName)` and require the Python main thread. |
| Selection list with subelements | `src/Gui/Selection/Selection.cpp:2588` exposes `Gui.Selection.getSelectionEx(...)` returning `SelectionObject` records with subelement names. |
| Preselection record | `src/Gui/Selection/Selection.cpp:2527` and `src/Gui/Selection/Selection.cpp:3048` expose `Gui.Selection.getPreselection()` as a `SelectionObject`. |
| Selection object fields | `src/Gui/Selection/SelectionObjectPyImp.cpp:75` through `:165` expose object name, document name, subelement names, resolved subobjects, and picked points. |
| Assembly connector selection shape | `src/Mod/Assembly/CommandCreateJoint.py:454` and `src/Mod/Assembly/JointObject.py:1751` use `Gui.Selection.getSelectionEx("*", 0)` and iterate `SubElementNames`. |

## Implemented Lifecycle

1. User starts FreeCAD GUI normally and starts the bridge manually or through the FreeCAD MCP Workbench.
2. `scripts/freecad_gui_bridge_server.py` opens a localhost JSON bridge with an optional bearer token.
3. MCP `freecad_gui_attach` connects to that bridge and returns a `session_id`.
4. Read-only GUI tools can query active document/view/selection without mutating model state.
5. GUI selection, view-fit, Sketcher edit-mode, and PartDesign Body activation tools can change GUI state, but model geometry still belongs in typed CAD tools.
6. Closing the MCP session detaches from the bridge but does not close FreeCAD GUI.

The bridge server uses a PySide signal hop to run RPC handlers on the Qt GUI thread when called from the HTTP server thread.

## Implemented Tools

| Tool | Purpose | Mutates |
| --- | --- | --- |
| `freecad_gui_attach` | Connect to an already-running GUI bridge and return GUI session metadata. | No |
| `freecad_gui_list` | List attached GUI bridge sessions held by this MCP server process. | No |
| `freecad_gui_detach` | Forget a GUI bridge session without closing FreeCAD GUI. | No |
| `freecad_gui_status` | Report GUI process, active document, active view type, workbench, and bridge health. | No |
| `freecad_gui_active_document_get` | Return active GUI document summary plus matching App document id/name. | No |
| `freecad_gui_active_view_get` | Return active view type/name/camera snapshot when available. | No |
| `freecad_gui_selection_get` | Return normalized selection records with document, object, subelement names, resolved object labels/types, and picked points. | No |
| `freecad_gui_preselection_get` | Return current hover/preselection object and subelement when available. | No |
| `freecad_gui_selection_set` | Set selection from normalized object/subelement references. | Yes |
| `freecad_gui_view_fit` | Fit all or fit selected in the active view. | View only |
| `freecad_gui_primitive_create` | Create a typed primitive in the active GUI document; currently supports `cylinder`. | Yes |
| `freecad_gui_object_label_set` | Set a user-visible object Label while keeping the internal FreeCAD Name stable. | Yes |
| `freecad_gui_sketch_state` | Inspect active or selected Sketcher state, edit mode, DoF, geometry/constraint counts, diagnostics, selected records, and optional bounded geometry/constraint summaries. | No by default; optional diagnostics refresh can run solver/missing-constraint reads. |
| `freecad_gui_sketch_enter` | Enter Sketcher edit mode for an explicit, selected, active, or uniquely inferable sketch, optionally selecting/fitting it. | GUI state only |
| `freecad_gui_sketch_leave` | Leave current Sketcher edit mode, optionally recompute, select the sketch, and return fresh state. | GUI state plus optional recompute |
| `freecad_gui_partdesign_state` | Inspect PartDesign Body candidates, inferred active Body, Tip, feature chain, origin features, edit object, and selected records. | No |
| `freecad_gui_body_activate` | Activate an explicit, selected, active, or uniquely inferable PartDesign Body in the GUI active view. | GUI state only |
| `freecad_gui_feature_task_state` | Inspect active GUI task/dialog/widget state around Sketcher and PartDesign feature workflows. | No |

## Normalized Selection Record

```json
{
  "document_name": "Unnamed",
  "object_name": "Box",
  "object_label": "Box",
  "type_id": "Part::Box",
  "subelement_names": ["Face1"],
  "full_name": "Unnamed#Box.Face1",
  "picked_points": [[1.0, 2.0, 3.0]],
  "resolved": [
    {
      "subelement_name": "Face1",
      "kind": "face",
      "shape_summary": {
        "faces": 1,
        "edges": 4,
        "vertices": 4
      }
    }
  ]
}
```

## Policy

- GUI attach tools must be read-only by default.
- Sketcher and PartDesign GUI mutations are limited to narrow workflow state: enter/leave edit mode, selection/view changes, Body activation, and optional recompute. Geometry creation and feature creation stay in typed CAD tools.
- Object `Name` is treated as the stable technical identifier; user-facing rename flows set `Label` and should keep labels unique by default.
- Selection and view reads must not call broad Python execution.
- Returned references must be stable enough for typed tools: `document_name`, `object_name`, and `subelement_name`.
- Bridge calls must fail with structured errors when FreeCAD GUI is not on the main thread or no active document/view exists.
- Connector-aware Assembly flows should consume `freecad_gui_selection_get` records before writing native `JointObject` references.
- Screenshot/vision debugging must follow `docs/VISION_DEBUG_PIPELINE.md`: structured MCP state first, narrow programmatic GUI actions second, local screenshot evidence third, smallest useful crop/detail sent to vision models, and user confirmation for ambiguous B-spline/arc/polyline decisions.

## Test Plan

- Unit tests cover GUI bridge client/session behavior against a fake local HTTP bridge.
- Unit tests assert Sketcher and PartDesign GUI state/edit/activation/task-state tools are exposed and delegated through the bridge.
- Static MCP smoke confirms GUI attach schemas are listed.
- Opt-in GUI smoke (`scripts/smoke_gui_attach.py`) launches FreeCAD GUI, creates/selects two box faces, calls `freecad_gui_selection_get`, verifies both `Face1` records, sets a GUI object Label, enters/leaves a sketch, reads feature-task state, and activates a PartDesign Body.
- The same smoke creates a Fixed Assembly joint from those GUI selection records and asserts `Reference1`/`Reference2` are populated.

## Non-goals

- The current Workbench slice is a small bridge host, not a full AI workbench UI.
- It will not make headless `FreeCADCmd` depend on Qt.
- It will not expose arbitrary GUI command execution as the preferred path; typed tools remain primary.
- Future GUI command execution must be allowlisted and documented against `docs/GUI_1_1_1_RESEARCH.md`.
