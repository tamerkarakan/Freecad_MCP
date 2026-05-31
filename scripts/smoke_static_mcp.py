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


def notify(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


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
        notify(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
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
        status = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "freecad_session_status",
                    "arguments": {"probe": False},
                },
            },
        )
        unsafe = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "freecad_python_exec",
                    "arguments": {"code": "print('blocked')"},
                },
            },
        )
        resources = send(process, {"jsonrpc": "2.0", "id": 6, "method": "resources/list"})
        resource_templates = send(process, {"jsonrpc": "2.0", "id": 7, "method": "resources/templates/list"})
        prompt = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "prompts/get",
                "params": {"name": "freecad_phase_gate", "arguments": {"phase": "smoke"}},
            },
        )
    finally:
        if process.stdin:
            process.stdin.close()
        stderr = process.stderr.read() if process.stderr else ""
        process.wait(timeout=10)

    assert "tools" in initialized["result"]["capabilities"]
    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "freecad_command_describe" in tool_names
    assert "freecad_session_status" in tool_names
    assert "freecad_session_start" in tool_names
    assert "freecad_worker_document_new" in tool_names
    assert "freecad_gui_attach" in tool_names
    assert "freecad_gui_selection_get" in tool_names
    assert "freecad_gui_object_label_set" in tool_names
    assert "freecad_gui_sketch_state" in tool_names
    assert "freecad_gui_sketch_enter" in tool_names
    assert "freecad_gui_sketch_leave" in tool_names
    assert "freecad_gui_partdesign_state" in tool_names
    assert "freecad_gui_body_activate" in tool_names
    assert "freecad_gui_feature_task_state" in tool_names
    assert "freecad_techdraw_page_create" in tool_names
    assert "freecad_techdraw_page_export" in tool_names
    assert "freecad_cam_path_create" in tool_names
    assert "freecad_fem_analysis_create" in tool_names
    assert "freecad_partdesign_body_create" in tool_names
    assert "freecad_partdesign_pad" in tool_names
    assert "freecad_partdesign_pocket" in tool_names
    assert "freecad_worker_partdesign_pocket" in tool_names
    assert "freecad_object_rename_label" in tool_names
    assert "freecad_sketch_profile_create" in tool_names
    assert "freecad_sketch_profile_validate" in tool_names
    assert "freecad_curve_fit_analyze" in tool_names
    assert "freecad_sketch_geometry_method_catalog" in tool_names
    assert "freecad_python_exec" in tool_names
    assert described["result"]["structuredContent"]["matches"][0]["name"] == "Part_Box"
    assert "discovery" in status["result"]["structuredContent"]
    assert unsafe["result"]["isError"] is True
    assert "unsafe" in unsafe["result"]["content"][0]["text"]
    assert any(resource["uri"] == "freecad://schemas/tools" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/roadmap-status" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/workbench-bridge" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/gui-1-1-1-research" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/vision-debug-pipeline" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/techdraw-cam-fem-plan" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/product-modules" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/product-bundles" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://product/bundles" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/distribution-profiles" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://distribution/profiles" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://docs/workbench-artifact" for resource in resources["result"]["resources"])
    assert any(resource["uri"] == "freecad://workbench/artifact" for resource in resources["result"]["resources"])
    assert resource_templates["result"]["resourceTemplates"] == []
    assert "Phase: smoke" in prompt["result"]["messages"][0]["content"]["text"]
    if process.returncode != 0:
        raise RuntimeError(f"server exited with {process.returncode}: {stderr}")
    print("static MCP smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
