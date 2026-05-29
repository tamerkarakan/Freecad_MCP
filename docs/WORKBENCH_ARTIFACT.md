# Workbench Artifact

Generated local FreeCAD Workbench module artifact for GUI bridge distribution.

- Artifact: `freecad-workbench-module`
- Module name: `FreeCADMCP`
- Zip name: `freecad-mcp-workbench.zip`
- Official Addon Manager package: `false`
- Consuming profiles: `pro`, `studio`, `team`

## Files

| Source | Zip Target | Role |
| --- | --- | --- |
| `freecad_workbench/FreeCADMCP/InitGui.py` | `FreeCADMCP/InitGui.py` | `workbench-entrypoint` |
| `scripts/freecad_gui_bridge_server.py` | `FreeCADMCP/freecad_gui_bridge_server.py` | `embedded-gui-bridge` |

## Install Shape

Extract the zip so `FreeCADMCP/InitGui.py` is directly under a FreeCAD module search path, such as the user `Mod` directory or a path passed with `FreeCAD.exe -M`.

The zip embeds `freecad_gui_bridge_server.py` beside `InitGui.py`, so the Workbench can host the GUI bridge without depending on the repo `scripts/` path.

This is a local module zip, not a signed FreeCAD Addon Manager package yet.
