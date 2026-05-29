# Workbench Artifact

Build the local FreeCAD Workbench module zip with:

```powershell
python scripts\build_workbench_addon.py --zip-out dist\freecad-mcp-workbench.zip
```

The resulting zip should be extracted so `FreeCADMCP/InitGui.py` sits under a FreeCAD module path. It embeds the GUI bridge script beside `InitGui.py`.

Expected zip name: `freecad-mcp-workbench.zip`
