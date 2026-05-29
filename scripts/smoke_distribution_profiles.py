#!/usr/bin/env python3
"""Smoke-check generated distribution profile artifacts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest_path = ROOT / "docs" / "distribution_profiles.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles = manifest["profiles"]
    profile_dir = ROOT / "packaging" / "profiles"

    assert manifest["project"]["entrypoint"] == "freecad-hybrid-mcp"
    expected_keys = {"free", "pro", "studio", "team", "source", "unsafe"}
    assert {profile["key"] for profile in profiles} == expected_keys
    actual_config_keys = {
        path.name[: -len(".mcp.json")]
        for path in profile_dir.glob("*.mcp.json")
    }
    assert actual_config_keys == expected_keys

    for profile in profiles:
        config_path = profile_dir / f"{profile['key']}.mcp.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        server_name = f"freecad-{profile['key']}"
        server = config["mcpServers"][server_name]
        assert server["command"] == "freecad-hybrid-mcp"
        assert server["env"]["FREECAD_MCP_MODULES"] == profile["profile"]
        assert "FREECAD_MCP_REPO_ROOT" in server["env"]

    print("distribution profiles smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
