#!/usr/bin/env python3
"""Smoke-check the generated FreeCAD MCP Workbench module zip."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeConsole:
    messages: list[str] = []

    @classmethod
    def PrintMessage(cls, message: str) -> None:
        cls.messages.append(message)


class FakeWorkbench:
    def appendToolbar(self, name: str, commands: list[str]) -> None:
        self.toolbar = (name, commands)

    def appendMenu(self, name: str, commands: list[str]) -> None:
        self.menu = (name, commands)


class FakeGui(types.ModuleType):
    Workbench = FakeWorkbench

    def __init__(self) -> None:
        super().__init__("FreeCADGui")
        self.commands: dict[str, object] = {}
        self.workbenches: list[object] = []

    def addCommand(self, name: str, command: object) -> None:
        self.commands[name] = command

    def addWorkbench(self, workbench: object) -> None:
        self.workbenches.append(workbench)


def import_init_gui(path: Path):
    fake_app = types.ModuleType("FreeCAD")
    fake_app.Console = FakeConsole
    fake_gui = FakeGui()
    spec = importlib.util.spec_from_file_location("freecad_mcp_artifact_InitGui", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"FreeCAD": fake_app, "FreeCADGui": fake_gui}):
        spec.loader.exec_module(module)
    return module, fake_gui


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="freecad-mcp-workbench-") as temp_dir:
        temp_root = Path(temp_dir)
        zip_path = temp_root / "freecad-mcp-workbench.zip"
        subprocess.run(
            [sys.executable, "scripts/build_workbench_addon.py", "--zip-out", str(zip_path)],
            cwd=ROOT,
            check=True,
        )
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            assert "FreeCADMCP/InitGui.py" in names
            assert "FreeCADMCP/freecad_gui_bridge_server.py" in names
            assert "FreeCADMCP/workbench_artifact.json" in names
            manifest = json.loads(archive.read("FreeCADMCP/workbench_artifact.json").decode("utf-8"))
            assert manifest["artifact_key"] == "freecad-workbench-module"
            archive.extractall(temp_root / "extract")

        init_gui = temp_root / "extract" / "FreeCADMCP" / "InitGui.py"
        module, fake_gui = import_init_gui(init_gui)
        assert module.bridge_script_path() == init_gui.parent / "freecad_gui_bridge_server.py"
        assert len(fake_gui.workbenches) == 1
        workbench = fake_gui.workbenches[0]
        workbench.Initialize()
        assert module.START_COMMAND in fake_gui.commands
        compile((init_gui.parent / "freecad_gui_bridge_server.py").read_text(encoding="utf-8"), "freecad_gui_bridge_server.py", "exec")

    print("workbench artifact smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
