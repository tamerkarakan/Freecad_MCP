# MCP Client Config

Phase 1 is a local stdio MCP server. The MCP client starts `server.py`.

Generic config shape:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["C:/path/to/Freecad_MCP/server.py"]
    }
  }
}
```

If Windows `python` points to the Microsoft Store alias, use the concrete Python executable from the environment that can run the tests.

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
