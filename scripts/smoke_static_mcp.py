#!/usr/bin/env python3
"""Smoke-test the stdio MCP server with newline-delimited JSON-RPC."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def send(process: subprocess.Popen[str], payload: dict[str, Any]) -> dict[str, Any]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("server closed stdout before responding")
    return json.loads(line)


def main() -> int:
    process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=ROOT,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        initialized = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0.1.0"},
                },
            },
        )
        tools = send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        described = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "freecad_command_describe",
                    "arguments": {"name": "Part_Box"},
                },
            },
        )
    finally:
        if process.stdin:
            process.stdin.close()
        stderr = process.stderr.read() if process.stderr else ""
        process.wait(timeout=10)

    assert initialized["result"]["capabilities"]["tools"]["listChanged"] is False
    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "freecad_command_describe" in tool_names
    assert described["result"]["structuredContent"]["matches"][0]["name"] == "Part_Box"
    if process.returncode != 0:
        raise RuntimeError(f"server exited with {process.returncode}: {stderr}")
    print("static MCP smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
