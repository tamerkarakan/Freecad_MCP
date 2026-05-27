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
      "description": "Python code passed to FreeCADCmd -c. Prefer typed tools when available.",
      "maxLength": 20000
    },
    "allow_unsafe": {
      "type": "boolean",
      "description": "Must be true unless FREECAD_MCP_ALLOW_UNSAFE_PYTHON=1 is set."
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

## `freecad_document_new`

Create a new FreeCAD document.

```json
{
  "type": "object",
  "properties": {
    "document_name": {
      "type": "string"
    },
    "label": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  }
}
```

## `freecad_document_open`

Open a FreeCAD document and return a summary.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_document_save`

Open and save a FreeCAD document.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_document_recompute`

Open/recompute a document and optionally save it.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  }
}
```

## `freecad_document_export`

Export selected or all document objects.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "output_path"
  ]
}
```

## `freecad_object_list`

List document objects.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_object_get`

Inspect one document object.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_name": {
      "type": "string"
    },
    "include_properties": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "object_name"
  ]
}
```

## `freecad_object_set_properties`

Set simple object properties and save optionally.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_name": {
      "type": "string"
    },
    "properties": {
      "type": "object"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "object_name",
    "properties"
  ]
}
```

## `freecad_object_delete`

Delete object(s) by name/label.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_name": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_part_create_primitive`

Create a Part primitive.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "document_name": {
      "type": "string"
    },
    "primitive": {
      "type": "string",
      "enum": [
        "box",
        "cylinder",
        "sphere",
        "cone",
        "torus"
      ]
    },
    "object_name": {
      "type": "string"
    },
    "properties": {
      "type": "object"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  }
}
```

## `freecad_part_boolean`

Fuse/cut/common Part shapes.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "operation": {
      "type": "string",
      "enum": [
        "fuse",
        "cut",
        "common"
      ]
    },
    "result_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "object_names"
  ]
}
```

## `freecad_part_extrude`

Extrude a source shape.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "source_object": {
      "type": "string"
    },
    "vector": {
      "type": "array",
      "items": {
        "type": "number"
      }
    },
    "result_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "source_object"
  ]
}
```

## `freecad_part_revolve`

Revolve a source shape.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "source_object": {
      "type": "string"
    },
    "base": {
      "type": "array",
      "items": {
        "type": "number"
      }
    },
    "axis": {
      "type": "array",
      "items": {
        "type": "number"
      }
    },
    "angle": {
      "type": "number"
    },
    "result_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "source_object"
  ]
}
```

## `freecad_part_fillet`

Create a filleted copy of a shape.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "source_object": {
      "type": "string"
    },
    "radius": {
      "type": "number"
    },
    "edge_indices": {
      "type": "array",
      "items": {
        "type": "integer"
      }
    },
    "result_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "source_object",
    "radius"
  ]
}
```

## `freecad_part_chamfer`

Create a chamfered copy of a shape.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "source_object": {
      "type": "string"
    },
    "distance": {
      "type": "number"
    },
    "edge_indices": {
      "type": "array",
      "items": {
        "type": "integer"
      }
    },
    "result_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "source_object",
    "distance"
  ]
}
```

## `freecad_part_check_geometry`

Run shape validity checks.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "run_bop_check": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_sketch_create`

Create a Sketcher object.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "document_name": {
      "type": "string"
    },
    "sketch_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  }
}
```

## `freecad_sketch_add_geometry`

Add line/circle/arc geometry to a sketch.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "sketch_name": {
      "type": "string"
    },
    "geometry": {
      "type": "array",
      "items": {
        "type": "object"
      }
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "sketch_name",
    "geometry"
  ]
}
```

## `freecad_sketch_add_constraint`

Add Sketcher constraints.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "sketch_name": {
      "type": "string"
    },
    "constraints": {
      "type": "array",
      "items": {
        "type": "object"
      }
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "sketch_name",
    "constraints"
  ]
}
```

## `freecad_sketch_validate`

Summarize sketch geometry and constraints.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "sketch_name": {
      "type": "string"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "sketch_name"
  ]
}
```

## `freecad_import_file`

Import a CAD/mesh file into a document.

```json
{
  "type": "object",
  "properties": {
    "input_path": {
      "type": "string"
    },
    "document_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "input_path"
  ]
}
```

## `freecad_export_file`

Export selected/all objects from a document.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "output_path"
  ]
}
```

## `freecad_supported_formats`

Return common import/export formats.

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
    "timeout_sec": {
      "type": "integer",
      "minimum": 1,
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  }
}
```

## `freecad_mesh_import`

Import a mesh file into a document.

```json
{
  "type": "object",
  "properties": {
    "input_path": {
      "type": "string"
    },
    "document_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "input_path"
  ]
}
```

## `freecad_mesh_export`

Export mesh objects.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "output_path"
  ]
}
```

## `freecad_mesh_evaluate`

Summarize mesh object health.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_mesh_repair`

Run conservative mesh repair actions.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "actions": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "harmonize_normals",
          "remove_duplicated_points"
        ]
      }
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_mesh_boolean`

Run mesh boolean operation when supported by FreeCAD build.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "object_names": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "operation": {
      "type": "string",
      "enum": [
        "union",
        "difference",
        "intersection"
      ]
    },
    "result_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "object_names"
  ]
}
```

## `freecad_assembly_create`

Create an Assembly object.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "document_name": {
      "type": "string"
    },
    "assembly_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  }
}
```

## `freecad_assembly_insert`

Insert an existing object into an assembly as an App::Link.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "assembly_name": {
      "type": "string"
    },
    "object_name": {
      "type": "string"
    },
    "link_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "assembly_name",
    "object_name"
  ]
}
```

## `freecad_assembly_create_joint`

Create placeholder joint metadata under an assembly joint group.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "assembly_name": {
      "type": "string"
    },
    "joint_type": {
      "type": "string"
    },
    "joint_name": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path",
    "assembly_name"
  ]
}
```

## `freecad_assembly_solve`

Recompute an assembly document.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "output_path": {
      "type": "string"
    },
    "overwrite": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```

## `freecad_assembly_bom`

Return a simple assembly bill of materials.

```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string"
    },
    "assembly_name": {
      "type": "string"
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
      "maximum": 180
    },
    "allow_external_paths": {
      "type": "boolean",
      "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace."
    }
  },
  "required": [
    "document_path"
  ]
}
```
