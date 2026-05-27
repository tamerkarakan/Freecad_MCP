# FreeCAD Hybrid MCP

FreeCAD icin hibrit MCP server calismasi.

Bu repo iki kaynagi birlestirecek:

- Static source tools: Git ile alinan FreeCAD kod tabaninda arama, sembol ve komut envanteri.
- Runtime tools: Calisan FreeCAD Python oturumuna baglanip belge, obje ve geometri islemleri.

## Current Inventory

FreeCAD upstream checkout:

```powershell
upstream\FreeCAD
```

Tool inventory generation:

```powershell
& 'C:\Users\tamer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\scan_freecad_tools.py --freecad-root upstream\FreeCAD
```

Generated files:

- `docs/freecad_tool_inventory.md`
- `docs/freecad_tool_inventory.json`
- `docs/mcp_tool_plan.md`

