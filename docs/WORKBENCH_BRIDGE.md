# Workbench Bridge

The repo includes a small FreeCAD Workbench entrypoint at `freecad_workbench/FreeCADMCP/InitGui.py`. It hosts the same loopback GUI bridge as `scripts/freecad_gui_bridge_server.py`, but from FreeCAD's Workbench/module loading path.

## Local Development Load

Start FreeCAD with the repo workbench directory as an additional module path:

```powershell
& "$env:FREECAD_MCP_FREECAD_HOME\bin\FreeCAD.exe" -M "C:\path\to\Freecad_MCP\freecad_workbench"
```

Then select the **FreeCAD MCP** workbench and use:

- `Start MCP Bridge`
- `Stop MCP Bridge`
- `MCP Bridge Status`

## Autostart

For automatic hosting when the module is loaded, set:

```powershell
$env:FREECAD_MCP_AUTOSTART = "1"
$env:FREECAD_MCP_GUI_TOKEN = "choose-a-local-token"
```

Optional overrides:

- `FREECAD_MCP_GUI_HOST`, default `127.0.0.1`
- `FREECAD_MCP_GUI_PORT`, default `48777`
- `FREECAD_MCP_BRIDGE_SCRIPT`, default repo `scripts/freecad_gui_bridge_server.py`

The bridge remains local loopback only by default. MCP clients attach with `freecad_gui_attach` after FreeCAD loads the module or starts the workbench.
