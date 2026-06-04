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

Optional structured logging:

- `FREECAD_MCP_LOG_LEVEL`: set to `INFO` for normal request/response timing, or `DEBUG` when future debug-only records are added. Unset or `OFF` keeps logging disabled.
- `FREECAD_MCP_LOG_FILE`: JSONL output path. If omitted while logging is enabled, records go to stderr, never stdout.
- `FREECAD_MCP_AGENT_ID`: stable caller label such as `codex-desktop`, `claude-desktop`, or `claude-code`.

Example:

```powershell
$env:FREECAD_MCP_LOG_LEVEL = "INFO"
$env:FREECAD_MCP_LOG_FILE = "C:\Users\tamer\Codex_Projects\Freecad_MCP\runs\freecad-mcp-codex.jsonl"
$env:FREECAD_MCP_AGENT_ID = "codex-desktop"
```

The JSONL records include MCP request id/client info when the SDK exposes them, `call_id`, tool names, outcome, duration, response key/size/hash summaries, process-per-call `FreeCADCmd` timings, persistent-worker RPC timings, and GUI bridge RPC timings. Raw argument values, raw response values, bearer tokens, and Python code payloads are deliberately not logged.

Optional product-style filtering:

```powershell
$env:FREECAD_MCP_MODULES = "pro"
```

Use `all` for the full advertised tool surface. `dev`, `developer`, and `local-dev` are full advertised-surface aliases for local maintainers, while hidden Part primitive tools remain unlisted so agents stay on Sketcher + PartDesign paths. Use `source` for the source-intelligence add-on, or explicit comma-separated modules such as `core,headless,gui,sketcher`. Generated sellable bundle counts and tool lists are in `docs/PRODUCT_BUNDLES.md`; generated distribution profiles and MCP config skeletons are in `docs/DISTRIBUTION_PROFILES.md` and `packaging/profiles/`; module rules are in `docs/PRODUCT_MODULES.md`.

Current bundle profiles:

| Profile | Tool Count | Use |
| --- | ---: | --- |
| `free` | 20 | File-based document/object/parameter/import-export operations. |
| `pro` | 85 | Adds GUI attach, Sketcher, PartDesign, mesh, and Assembly. |
| `studio` | 155 | Adds worker sessions plus TechDraw, CAM, and FEM. |
| `team` | 158 | Adds source-intelligence tools. |
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
FREECAD_MCP_AGENT_ID = 'codex-desktop'
```

Equivalent CLI add command:

```powershell
codex mcp add freecad `
  --env FREECAD_MCP_FREECAD_ROOT=C:\Users\tamer\Codex_Projects\Freecad_MCP\upstream\FreeCAD `
  --env FREECAD_MCP_FREECAD_HOME=E:\Downloads\zip\FreeCAD_1.1.1-Windows-x86_64-py311 `
  --env FREECAD_MCP_WORKSPACE_ROOT=C:\Users\tamer\Codex_Projects\Freecad_MCP `
  --env FREECAD_MCP_AGENT_ID=codex-desktop `
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
  -e FREECAD_MCP_AGENT_ID=claude-code `
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
        "FREECAD_MCP_MODULES": "all",
        "FREECAD_MCP_AGENT_ID": "claude-desktop"
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
- `freecad_gui_document_open`
- `freecad_gui_active_view_get`
- `freecad_gui_selection_get`
- `freecad_gui_preselection_get`
- `freecad_gui_selection_set`
- `freecad_gui_view_fit`
- `freecad_gui_view_orientation_set`
- `freecad_gui_visibility_ensure`
- `freecad_gui_view_snapshot`
- `freecad_gui_primitive_create`

Headless typed CAD tools remain the preferred path for model mutation. GUI attach is mainly for opening generated `.FCStd` files in the live GUI, active document/view/selection state, visibility repair when a loaded document appears hidden, orientation-controlled snapshots, and connector-style workflows. New bridge versions make `freecad_gui_document_open` ensure the final display object is visible by default.

If a GUI tool returns `unknown method: ...`, the MCP client is talking to an older bridge script already running inside FreeCAD. Stop and start the **FreeCAD MCP** bridge, or restart FreeCAD. If you use an installed Workbench zip instead of the repo `-M` path, rebuild and reinstall the zip before restarting FreeCAD.

For repeated GUI calls, use `freecad_gui_watchdog_status` when a live session starts timing out or returning errors. Normal GUI tool failures mark the MCP-side session unhealthy; `probe=true` runs a short status heartbeat. If the watchdog probe also fails, stop/start the Workbench bridge or restart FreeCAD GUI, then attach again. Bridge API v4 status includes heartbeat counters such as `rpc_count`, `in_flight`, and the last RPC method.

The full tool schema snapshot is in `docs/mcp_tool_schemas.md`.
