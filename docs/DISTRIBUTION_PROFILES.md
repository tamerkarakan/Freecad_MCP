# Distribution Profiles

Generated packaging skeleton for the sellable FreeCAD MCP bundles.

- Python distribution: `freecad-hybrid-mcp`
- Python package: `freecad_mcp`
- Console entrypoint: `freecad-hybrid-mcp`
- Module selector env: `FREECAD_MCP_MODULES`
- Repo/resource root env: `FREECAD_MCP_REPO_ROOT`

Verification: `scripts/smoke_python_package.py` builds wheel and sdist artifacts, installs the wheel into a temporary venv, starts the installed `freecad-hybrid-mcp` entrypoint outside the repo working directory, and checks MCP initialize/tool calls with `FREECAD_MCP_MODULES=free`.

| Profile | Channel | Tools | Artifacts | Components |
| --- | --- | ---: | --- | --- |
| `free` | public | 22 | `wheel`, `sdist`, `stdio-mcp-config` | `python-package`, `runtime-scripts` |
| `pro` | paid | 91 | `wheel`, `sdist`, `stdio-mcp-config`, `freecad-workbench-module` | `python-package`, `runtime-scripts`, `gui-bridge`, `workbench-module` |
| `studio` | paid | 164 | `wheel`, `sdist`, `stdio-mcp-config`, `freecad-workbench-module` | `python-package`, `runtime-scripts`, `persistent-worker`, `gui-bridge`, `workbench-module` |
| `team` | paid | 167 | `wheel`, `sdist`, `stdio-mcp-config`, `freecad-workbench-module`, `source-intelligence-docs` | `python-package`, `runtime-scripts`, `persistent-worker`, `gui-bridge`, `workbench-module`, `source-intelligence` |
| `source` | add-on | 5 | `wheel`, `stdio-mcp-config` | `source-intelligence` |
| `unsafe` | add-on | 1 | `wheel`, `stdio-mcp-config` | `unsafe-python-exec` |

## Generated MCP Configs

Per-profile MCP JSON examples are generated under `packaging/profiles/`.

### FreeCAD MCP Free

- Profile: `free`
- Entrypoint command: `freecad-hybrid-mcp`
- Notes: Base local automation package; no GUI workbench component is needed.
- Config: `packaging/profiles/free.mcp.json`

### FreeCAD MCP Pro

- Profile: `pro`
- Entrypoint command: `freecad-hybrid-mcp`
- Notes: Adds GUI attach; ship the FreeCAD workbench module next to the Python package.
- Config: `packaging/profiles/pro.mcp.json`
- Workbench artifact: `freecad-mcp-workbench.zip`

### FreeCAD MCP Studio

- Profile: `studio`
- Entrypoint command: `freecad-hybrid-mcp`
- Notes: Adds persistent workers and advanced workbench slices; keep worker temp-script cleanup tests in the release gate.
- Config: `packaging/profiles/studio.mcp.json`
- Workbench artifact: `freecad-mcp-workbench.zip`

### FreeCAD MCP Team

- Profile: `team`
- Entrypoint command: `freecad-hybrid-mcp`
- Notes: Team profile includes source-intelligence tools for support and implementation research.
- Config: `packaging/profiles/team.mcp.json`
- Workbench artifact: `freecad-mcp-workbench.zip`

### Source Intelligence Add-on

- Profile: `source`
- Entrypoint command: `freecad-hybrid-mcp`
- Notes: Add-on profile for maintainers that should be layered with another paid profile when mutation tools are needed.
- Config: `packaging/profiles/source.mcp.json`

### Unsafe Python Exec Add-on

- Profile: `unsafe`
- Entrypoint command: `freecad-hybrid-mcp`
- Notes: Explicit trusted-local add-on; never include in the default paid profiles.
- Config: `packaging/profiles/unsafe.mcp.json`
