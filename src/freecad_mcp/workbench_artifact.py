"""Workbench module artifact descriptor for FreeCAD GUI bridge distribution."""

from __future__ import annotations

import hashlib
from pathlib import Path


ARTIFACT_KEY = "freecad-workbench-module"
MODULE_NAME = "FreeCADMCP"
ZIP_NAME = "freecad-mcp-workbench.zip"


WORKBENCH_FILES: tuple[dict[str, str], ...] = (
    {
        "source": "freecad_workbench/FreeCADMCP/InitGui.py",
        "target": "FreeCADMCP/InitGui.py",
        "role": "workbench-entrypoint",
    },
    {
        "source": "scripts/freecad_gui_bridge_server.py",
        "target": "FreeCADMCP/freecad_gui_bridge_server.py",
        "role": "embedded-gui-bridge",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workbench_artifact_manifest(repo_root: Path | None = None) -> dict[str, object]:
    root = (repo_root or Path.cwd()).resolve()
    files: list[dict[str, object]] = []
    for file_spec in WORKBENCH_FILES:
        source = root / file_spec["source"]
        files.append(
            {
                **file_spec,
                "size": source.stat().st_size if source.exists() else None,
                "sha256": _sha256(source) if source.exists() else None,
            }
        )
    return {
        "schema_version": 1,
        "artifact_key": ARTIFACT_KEY,
        "module_name": MODULE_NAME,
        "zip_name": ZIP_NAME,
        "zip_root": MODULE_NAME,
        "description": "Local FreeCAD Workbench module that hosts the loopback MCP GUI bridge.",
        "official_addon_manager_package": False,
        "consuming_profiles": ["pro", "studio", "team"],
        "files": files,
        "install": {
            "extract_zip_parent": "<FreeCAD user Mod directory or any path passed with FreeCAD -M>",
            "module_path": "<extract_zip_parent>/FreeCADMCP",
            "freecad_launch_example": 'FreeCAD.exe -M "<extract_zip_parent>"',
            "workbench_name": "FreeCAD MCP",
        },
        "env": {
            "FREECAD_MCP_AUTOSTART": "optional 1/true/yes/on",
            "FREECAD_MCP_GUI_TOKEN": "optional bearer token for local bridge attach",
            "FREECAD_MCP_GUI_HOST": "optional, default 127.0.0.1",
            "FREECAD_MCP_GUI_PORT": "optional, default 48777",
            "FREECAD_MCP_BRIDGE_SCRIPT": "optional override; bundled sibling bridge is used by default",
        },
    }
