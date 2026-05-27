# MCP Tool Schemas

## `freecad_command_list`

List statically scanned FreeCAD GUI commands with optional filtering.

```json
{
  "type": "object",
  "properties": {
    "module": {
      "type": "string",
      "description": "Optional module/workbench name."
    },
    "language": {
      "type": "string",
      "description": "Optional source language filter.",
      "enum": [
        "python",
        "cpp"
      ]
    },
    "query": {
      "type": "string",
      "description": "Case-insensitive substring search over command name, menu text, and tooltip."
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 500
    },
    "offset": {
      "type": "integer",
      "minimum": 0
    }
  }
}
```

## `freecad_command_describe`

Return source-backed metadata for a scanned FreeCAD command.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Exact command name."
    },
    "module": {
      "type": "string",
      "description": "Optional module/workbench filter."
    }
  },
  "required": [
    "name"
  ]
}
```

## `freecad_source_symbol_index`

Return a compact summary of scanned workbenches, command counts, and MCP tool families.

```json
{
  "type": "object",
  "properties": {
    "module": {
      "type": "string",
      "description": "Optional module/workbench to summarize."
    }
  }
}
```

## `freecad_source_search`

Search the local FreeCAD checkout for text matches.

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Literal text or regex pattern."
    },
    "module": {
      "type": "string",
      "description": "Optional module under src/Mod."
    },
    "glob": {
      "type": "string",
      "description": "Optional filename glob, for example '*.py' or 'Command*.cpp'."
    },
    "regex": {
      "type": "boolean",
      "description": "Treat query as a regular expression."
    },
    "case_sensitive": {
      "type": "boolean"
    },
    "max_results": {
      "type": "integer",
      "minimum": 1,
      "maximum": 200
    }
  },
  "required": [
    "query"
  ]
}
```

## `freecad_source_open`

Read a bounded line range from a source file in the local FreeCAD checkout.

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Path relative to the FreeCAD root, for example src/Mod/Part/Gui/Command.cpp."
    },
    "start_line": {
      "type": "integer",
      "minimum": 1
    },
    "line_count": {
      "type": "integer",
      "minimum": 1,
      "maximum": 400
    }
  },
  "required": [
    "path"
  ]
}
```

## `freecad_session_status`

Discover FreeCADCmd and optionally probe the runtime version/config.

```json
{
  "type": "object",
  "properties": {
    "executable": {
      "type": "string",
      "description": "Optional explicit FreeCADCmd path."
    },
    "freecad_home": {
      "type": "string",
      "description": "Optional portable FreeCAD directory."
    },
    "probe": {
      "type": "boolean",
      "description": "Run a small FreeCAD Python probe when an executable is found."
    },
    "timeout_sec": {
      "type": "integer",
      "minimum": 1,
      "maximum": 120
    }
  }
}
```

## `freecad_python_exec`

Run a low-level Python snippet through FreeCADCmd and return stdout/stderr.

```json
{
  "type": "object",
  "properties": {
    "code": {
      "type": "string",
      "description": "Python code passed to FreeCADCmd -c. Prefer typed tools when available."
    },
    "executable": {
      "type": "string",
      "description": "Optional explicit FreeCADCmd path."
    },
    "freecad_home": {
      "type": "string",
      "description": "Optional portable FreeCAD directory."
    },
    "timeout_sec": {
      "type": "integer",
      "minimum": 1,
      "maximum": 120
    }
  },
  "required": [
    "code"
  ]
}
```
