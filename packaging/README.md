# Packaging Profiles

This directory contains generated MCP client config skeletons for each product profile.
Regenerate them with:

```powershell
python scripts\export_distribution_profiles.py
```

Each config assumes the installed console entrypoint `freecad-hybrid-mcp` is on PATH.
Replace placeholder environment values before handing a profile to a user.
GUI-capable profiles also consume the generated local Workbench module zip from `packaging/workbench/` or a path produced by `scripts\build_workbench_addon.py --zip-out`.

| File | Profile |
| --- | --- |
| `profiles/free.mcp.json` | `free` |
| `profiles/pro.mcp.json` | `pro` |
| `profiles/studio.mcp.json` | `studio` |
| `profiles/team.mcp.json` | `team` |
| `profiles/source.mcp.json` | `source` |
| `profiles/unsafe.mcp.json` | `unsafe` |
