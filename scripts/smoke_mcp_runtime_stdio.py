#!/usr/bin/env python3
"""Smoke-test runtime-mutating tools through the stdio MCP transport."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_mcp.runtime_bridge import FreeCadDiscovery


def _reader(stream, output: queue.Queue[str | None]) -> None:
    try:
        output.put(stream.readline())
    except Exception:
        output.put(None)


def send(process: subprocess.Popen[str], payload: dict[str, Any], *, timeout_sec: int = 30) -> dict[str, Any]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()
    lines: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=_reader, args=(process.stdout, lines), daemon=True).start()
    try:
        line = lines.get(timeout=timeout_sec)
    except queue.Empty as exc:
        raise TimeoutError(f"timed out waiting for MCP response to {payload.get('method')}") from exc
    if not line:
        raise RuntimeError("server closed stdout before responding")
    return json.loads(line)


def notify(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


def cleanup_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt" and shutil.which("taskkill"):
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    discovery = FreeCadDiscovery().discover()
    if discovery.executable is None:
        message = "MCP runtime stdio smoke SKIPPED: FreeCADCmd not discovered"
        if os.environ.get("FREECAD_MCP_REQUIRE_RUNTIME") == "1":
            raise RuntimeError(message)
        print(message)
        return 0

    runs_dir = ROOT / "runs"
    runs_dir.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(SRC))
    env["FREECAD_MCP_WORKSPACE_ROOT"] = str(ROOT)
    env.setdefault("FREECAD_MCP_MODULES", "all")
    with tempfile.TemporaryDirectory(prefix="mcp-runtime-stdio-", dir=runs_dir) as temp_dir:
        output_path = Path(temp_dir) / "box.FCStd"
        process = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=ROOT,
            env=env,
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
                        "clientInfo": {"name": "runtime-smoke", "version": "0.1.0"},
                    },
                },
            )
            notify(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            created = send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "freecad_partdesign_profile_feature_create",
                        "arguments": {
                            "document_name": "McpRuntimeStdioSmoke",
                            "body_name": "Body",
                            "sketch_name": "McpRuntimeStdioSketch",
                            "feature_kind": "pad",
                            "feature_name": "McpRuntimeStdioPad",
                            "length": 6,
                            "loops": [
                                {
                                    "type": "rectangle",
                                    "origin": [0, 0, 0],
                                    "width": 10,
                                    "height": 8,
                                }
                            ],
                            "constraint_policy": "semantic",
                            "require_fully_constrained": True,
                            "output_path": str(output_path),
                            "overwrite": True,
                            "compact_execution": True,
                            "timeout_sec": 60,
                        },
                    },
                },
                timeout_sec=90,
            )
            listed = send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "freecad_object_list",
                        "arguments": {
                            "document_path": str(output_path),
                            "compact_execution": True,
                            "timeout_sec": 60,
                        },
                    },
                },
                timeout_sec=90,
            )
        finally:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cleanup_process_tree(process)
            stderr = process.stderr.read() if process.stderr else ""

    assert "tools" in initialized["result"]["capabilities"]
    created_payload = created["result"]["structuredContent"]
    listed_payload = listed["result"]["structuredContent"]
    assert created_payload["freecad"]["ok"] is True, created_payload
    assert listed_payload["freecad"]["ok"] is True, listed_payload
    objects = listed_payload["freecad"].get("objects") or listed_payload["freecad"].get("document", {}).get("objects", [])
    assert any(obj.get("name") == "McpRuntimeStdioPad" for obj in objects), listed_payload
    if process.returncode != 0:
        raise RuntimeError(f"server exited with {process.returncode}: {stderr}")
    print("MCP runtime stdio smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
