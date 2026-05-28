from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
INIT_GUI = ROOT / "freecad_workbench" / "FreeCADMCP" / "InitGui.py"


class FakeConsole:
    messages: list[str] = []

    @classmethod
    def PrintMessage(cls, message: str) -> None:
        cls.messages.append(message)


class FakeWorkbench:
    def __init__(self) -> None:
        self.toolbars: list[tuple[str, list[str]]] = []
        self.menus: list[tuple[str, list[str]]] = []

    def appendToolbar(self, name: str, commands: list[str]) -> None:
        self.toolbars.append((name, commands))

    def appendMenu(self, name: str, commands: list[str]) -> None:
        self.menus.append((name, commands))


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


class WorkbenchBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeConsole.messages = []

    def import_init_gui(self, *, autostart: bool = False) -> tuple[types.ModuleType, FakeGui]:
        fake_app = types.ModuleType("FreeCAD")
        fake_app.Console = FakeConsole
        fake_gui = FakeGui()
        env = {"FREECAD_MCP_AUTOSTART": "1"} if autostart else {}
        module_name = "freecad_mcp_test_InitGui"
        spec = importlib.util.spec_from_file_location(module_name, INIT_GUI)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"FreeCAD": fake_app, "FreeCADGui": fake_gui}):
            with patch.dict(os.environ, env, clear=False):
                spec.loader.exec_module(module)
        return module, fake_gui

    def test_workbench_registers_commands_without_autostart(self) -> None:
        module, fake_gui = self.import_init_gui()

        self.assertFalse(module.autostart_enabled())
        self.assertEqual(len(fake_gui.workbenches), 1)
        workbench = fake_gui.workbenches[0]
        workbench.Initialize()
        self.assertIn(module.START_COMMAND, fake_gui.commands)
        self.assertIn(module.STOP_COMMAND, fake_gui.commands)
        self.assertIn(module.STATUS_COMMAND, fake_gui.commands)
        self.assertEqual(workbench.GetClassName(), "Gui::PythonWorkbench")

    def test_bridge_script_path_defaults_to_repo_script(self) -> None:
        module, _ = self.import_init_gui()

        self.assertEqual(module.bridge_script_path(), ROOT / "scripts" / "freecad_gui_bridge_server.py")

    def test_autostart_env_flag_is_detected(self) -> None:
        fake_bridge = ROOT / "runs" / "fake-bridge.py"
        fake_bridge.parent.mkdir(parents=True, exist_ok=True)
        fake_bridge.write_text(
            "def start_bridge(**kwargs):\n"
            "    return {'running': True, 'kwargs': kwargs}\n"
            "def stop_bridge():\n"
            "    return {'running': False}\n"
            "def rpc_status(params):\n"
            "    return {'bridge': 'ok'}\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"FREECAD_MCP_BRIDGE_SCRIPT": str(fake_bridge), "FREECAD_MCP_GUI_TOKEN": "secret"}):
            module, _ = self.import_init_gui(autostart=True)

        with patch.dict(os.environ, {"FREECAD_MCP_AUTOSTART": "1"}):
            self.assertTrue(module.autostart_enabled())
        self.assertTrue(any("autostarted" in message for message in FakeConsole.messages))


if __name__ == "__main__":
    unittest.main()
