#!/usr/bin/env python3
"""Export MCP tool schemas as reviewable docs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_mcp.mcp_stdio import build_server


def main() -> int:
    service = build_server(ROOT)
    tools = [definition.to_mcp() for definition in service.definitions()]

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    json_path = docs / "mcp_tool_schemas.json"
    md_path = docs / "mcp_tool_schemas.md"

    json_path.write_text(json.dumps({"tools": tools}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# MCP Tool Schemas", ""]
    for tool in tools:
        lines.extend(
            [
                f"## `{tool['name']}`",
                "",
                tool["description"],
                "",
                "```json",
                json.dumps(tool["inputSchema"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {json_path.relative_to(ROOT)}")
    print(f"wrote {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
