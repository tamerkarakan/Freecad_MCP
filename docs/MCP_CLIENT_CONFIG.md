# MCP Client Config

Phase 1 is a local stdio MCP server. The MCP client starts `server.py`.

Generic config shape:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["C:/path/to/Freecad_MCP/server.py"],
      "env": {
        "FREECAD_MCP_FREECAD_HOME": "C:/path/to/FreeCAD"
      }
    }
  }
}
```

If Windows `python` points to the Microsoft Store alias, use the concrete Python executable from the environment that can run the tests.
If you prefer a concrete executable instead of a home directory, set `FREECAD_MCP_FREECAD_CMD` to `FreeCADCmd.exe`.
Set `FREECAD_MCP_WORKSPACE_ROOT` if you want CAD output writes constrained to a specific workspace. Typed tools require `output_path` to be absolute; writes outside this root require `allow_external_paths=true`.

Before wiring the client:

```powershell
scripts\verify.ps1
```

Available tools:

- `freecad_command_list`
- `freecad_command_describe`
- `freecad_source_symbol_index`
- `freecad_source_search`
- `freecad_source_open`
- `freecad_session_status`
- `freecad_python_exec`

The full tool schema snapshot is in `docs/mcp_tool_schemas.md`.
