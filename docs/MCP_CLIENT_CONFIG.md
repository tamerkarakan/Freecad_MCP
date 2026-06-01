# MCP Client Config

The MCP server is a local stdio server implemented on the official Python `mcp` SDK. The client starts `server.py`; `server.py` adds `src/` to `sys.path`, so the repo does not need to be installed as a package, but the selected Python environment must have the `mcp` package installed.

## Prerequisites

Use a Python environment that has the SDK dependency:

```powershell
python -m pip install mcp
```

Then verify the server and tool surface:

```powershell
scripts\verify.ps1
```

Runtime tools need one of:

- `FREECAD_MCP_FREECAD_HOME`: portable FreeCAD root containing `FreeCADCmd.exe` and `FreeCAD.exe`.
- `FREECAD_MCP_FREECAD_CMD`: concrete path to `FreeCADCmd.exe`.

Static source tools can use:

- `FREECAD_MCP_FREECAD_ROOT`: local FreeCAD source checkout, usually `upstream\FreeCAD`.
- `FREECAD_MCP_REPO_ROOT`: repo/resource root for installed entrypoint runs when docs, schema snapshots, and inventory files are outside the current working directory.

Typed CAD write tools use `FREECAD_MCP_WORKSPACE_ROOT` as the default write boundary. Absolute output paths outside that root require `allow_external_paths=true`.

Optional product-style filtering:

```powershell
$env:FREECAD_MCP_MODULES = "pro"
```

Use `all` for the full current tool surface. `dev`, `developer`, and `local-dev` are full-surface aliases for local maintainers, so sales/package profiles do not narrow development workflows. Use `source` for the source-intelligence add-on, or explicit comma-separated modules such as `core,headless,gui,sketcher`. Generated sellable bundle counts and tool lists are in `docs/PRODUCT_BUNDLES.md`; generated distribution profiles and MCP config skeletons are in `docs/DISTRIBUTION_PROFILES.md` and `packaging/profiles/`; module rules are in `docs/PRODUCT_MODULES.md`.

Current bundle profiles:

| Profile | Tool Count | Use |
| --- | ---: | --- |
| `free` | 23 | File-based document/object/Part operations. |
| `pro` | 83 | Adds GUI attach, Sketcher, PartDesign, mesh, and Assembly. |
| `studio` | 158 | Adds worker sessions plus TechDraw, CAM, and FEM. |
| `team` | 161 | Adds source-intelligence tools. |
| `source` | 5 | Command/source intelligence add-on only. |
| `unsafe` | 1 | Only `freecad_python_exec`; opt-in add-on. |

## Codex

Codex stores stdio MCP servers in `C:\Users\tamer\.codex\config.toml` under `[mcp_servers.<name>]`.

Current working shape for this machine:

```toml
[mcp_servers.freecad]
command = 'C:\Users\tamer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
args = ['C:\Users\tamer\Codex_Projects\Freecad_MCP\server.py']

[mcp_servers.freecad.env]
FREECAD_MCP_FREECAD_ROOT = 'C:\Users\tamer\Codex_Projects\Freecad_MCP\upstream\FreeCAD'
FREECAD_MCP_FREECAD_HOME = 'E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311'
FREECAD_MCP_WORKSPACE_ROOT = 'C:\Users\tamer\Codex_Projects\Freecad_MCP'
```

Equivalent CLI add command:

```powershell
codex mcp add freecad `
  --env FREECAD_MCP_FREECAD_ROOT=C:\Users\tamer\Codex_Projects\Freecad_MCP\upstream\FreeCAD `
  --env FREECAD_MCP_FREECAD_HOME=E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311 `
  --env FREECAD_MCP_WORKSPACE_ROOT=C:\Users\tamer\Codex_Projects\Freecad_MCP `
  -- C:\Users\tamer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe C:\Users\tamer\Codex_Projects\Freecad_MCP\server.py
```

Check it with:

```powershell
codex mcp list
codex mcp get freecad
```

Installed entrypoint profile examples are generated under `packaging/profiles/*.mcp.json`. They use `freecad-hybrid-mcp` as the command and set `FREECAD_MCP_MODULES` per bundle.

## Claude Code

Claude Code can add the same stdio server:

```powershell
claude mcp add freecad `
  -s user `
  -e FREECAD_MCP_FREECAD_ROOT=C:\Users\tamer\Codex_Projects\Freecad_MCP\upstream\FreeCAD `
  -e FREECAD_MCP_FREECAD_HOME=E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311 `
  -e FREECAD_MCP_WORKSPACE_ROOT=C:\Users\tamer\Codex_Projects\Freecad_MCP `
  -- C:\Users\tamer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe C:\Users\tamer\Codex_Projects\Freecad_MCP\server.py
```

Use `-s local` instead of `-s user` if the server should be available only in the current project. Check it with:

```powershell
claude mcp list
claude mcp get freecad
```

## Claude Desktop Style JSON

Clients that expect the common JSON config shape can use:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "C:/Users/tamer/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
      "args": ["C:/Users/tamer/Codex_Projects/Freecad_MCP/server.py"],
      "env": {
        "FREECAD_MCP_FREECAD_ROOT": "C:/Users/tamer/Codex_Projects/Freecad_MCP/upstream/FreeCAD",
        "FREECAD_MCP_FREECAD_HOME": "E:/Downloads/zip/FreeCAD_1.1.1-Windows-x86_64-py311",
        "FREECAD_MCP_WORKSPACE_ROOT": "C:/Users/tamer/Codex_Projects/Freecad_MCP",
        "FREECAD_MCP_MODULES": "all"
      }
    }
  }
}
```

## GUI Attach

The MCP stdio server does not launch FreeCAD GUI by default. GUI access is opt-in:

1. Start FreeCAD with the repo workbench path:

```powershell
& "E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311\FreeCAD.exe" -M "C:\Users\tamer\Codex_Projects\Freecad_MCP\freecad_workbench"
```

If the workbench selector still does not show **FreeCAD MCP**, start with the leaf module path:

```powershell
& "E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311\FreeCAD.exe" -M "C:\Users\tamer\Codex_Projects\Freecad_MCP\freecad_workbench\FreeCADMCP"
```

For a distribution-style local module, build and extract the generated zip so `FreeCADMCP/InitGui.py` is under a FreeCAD module search path:

```powershell
python scripts\build_workbench_addon.py --zip-out dist\freecad-mcp-workbench.zip
```

2. In FreeCAD, select the **FreeCAD MCP** workbench and run **Start MCP Bridge**. Or autostart it:

```powershell
$env:FREECAD_MCP_AUTOSTART = "1"
$env:FREECAD_MCP_GUI_TOKEN = "choose-a-local-token"
& "E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311\FreeCAD.exe" -M "C:\Users\tamer\Codex_Projects\Freecad_MCP\freecad_workbench"
```

3. From Codex or Claude, call `freecad_gui_attach` with the loopback URL, normally `http://127.0.0.1:48777`, and the token if one was set.

Useful GUI tools after attach:

- `freecad_gui_status`
- `freecad_gui_active_document_get`
- `freecad_gui_active_view_get`
- `freecad_gui_selection_get`
- `freecad_gui_preselection_get`
- `freecad_gui_selection_set`
- `freecad_gui_view_fit`
- `freecad_gui_view_snapshot`
- `freecad_gui_primitive_create`

Headless typed CAD tools remain the preferred path for model mutation. GUI attach is mainly for active document/view/selection state and connector-style workflows.

The full tool schema snapshot is in `docs/mcp_tool_schemas.md`.
