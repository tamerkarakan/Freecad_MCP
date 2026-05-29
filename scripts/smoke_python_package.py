#!/usr/bin/env python3
"""Build, inspect, and install-smoke the Python package skeleton."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, check=True)


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _send(process: subprocess.Popen[str], payload: dict[str, object]) -> dict[str, object]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("installed entrypoint closed stdout before responding")
    return json.loads(line)


def _notify(process: subprocess.Popen[str], payload: dict[str, object]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _build_sdist(out_dir: Path) -> Path:
    import setuptools.build_meta as build_meta

    old_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        filename = build_meta.build_sdist(str(out_dir))
    finally:
        os.chdir(old_cwd)
    return out_dir / filename


def _inspect_sdist(sdist_path: Path) -> None:
    with tarfile.open(sdist_path, "r:gz") as sdist:
        names = set(sdist.getnames())
    assert any(name.endswith("/pyproject.toml") for name in names)
    assert any(name.endswith("/README.md") for name in names)
    assert any(name.endswith("/src/freecad_mcp/runtime_scripts/cad_action.py") for name in names)
    assert any(name.endswith("/src/freecad_mcp/runtime_scripts/worker.py") for name in names)
    assert any(name.endswith("/src/freecad_mcp/cad_domains/sketch.py") for name in names)


def _inspect_wheel(wheel_path: Path) -> None:
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        assert "freecad_mcp/runtime_scripts/cad_action.py" in names
        assert "freecad_mcp/runtime_scripts/worker.py" in names
        entry_points = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        assert len(entry_points) == 1, entry_points
        entry_text = wheel.read(entry_points[0]).decode("utf-8")
        assert "freecad-hybrid-mcp = freecad_mcp.mcp_stdio:main" in entry_text


def _entrypoint_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        for name in ("freecad-hybrid-mcp.exe", "freecad-hybrid-mcp.cmd", "freecad-hybrid-mcp"):
            candidate = venv_dir / "Scripts" / name
            if candidate.exists():
                return candidate
    candidate = venv_dir / "bin" / "freecad-hybrid-mcp"
    if candidate.exists():
        return candidate
    raise AssertionError(f"installed entrypoint not found under {venv_dir}")


def _smoke_installed_entrypoint(wheel_path: Path, temp_root: Path) -> None:
    venv_dir = temp_root / "venv"
    _run([sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)], env=_clean_env())
    venv_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "--force-reinstall", str(wheel_path)],
        cwd=temp_root,
        env=_clean_env(),
    )

    env = _clean_env()
    env["FREECAD_MCP_REPO_ROOT"] = str(ROOT)
    env["FREECAD_MCP_MODULES"] = "free"
    entrypoint = _entrypoint_path(venv_dir)
    process = subprocess.Popen(
        [str(entrypoint)],
        cwd=temp_root,
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        initialized = _send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "package-smoke", "version": "0.1.0"},
                },
            },
        )
        _notify(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = _send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        described = _send(
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

    assert "tools" in initialized["result"]["capabilities"]
    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "freecad_part_create_primitive" in tool_names
    assert "freecad_gui_attach" not in tool_names
    assert "freecad_worker_document_new" not in tool_names
    assert described["result"]["structuredContent"]["matches"][0]["name"] == "Part_Box"
    if process.returncode != 0:
        raise RuntimeError(f"installed entrypoint exited with {process.returncode}: {stderr}")


def main() -> int:
    egg_info = ROOT / "src" / "freecad_hybrid_mcp.egg-info"
    with tempfile.TemporaryDirectory(prefix="freecad-mcp-package-") as temp_dir:
        try:
            out_dir = Path(temp_dir)
            _run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    ".",
                    "--no-deps",
                    "--no-build-isolation",
                    "-w",
                    str(out_dir),
                ],
            )
            wheels = sorted(out_dir.glob("freecad_hybrid_mcp-*.whl"))
            assert len(wheels) == 1, wheels
            _inspect_wheel(wheels[0])
            sdist_path = _build_sdist(out_dir)
            _inspect_sdist(sdist_path)
            _smoke_installed_entrypoint(wheels[0], out_dir)
        finally:
            if egg_info.exists():
                shutil.rmtree(egg_info)
    print("python package smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
