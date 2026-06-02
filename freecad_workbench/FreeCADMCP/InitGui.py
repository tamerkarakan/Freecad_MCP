"""FreeCAD Workbench entrypoint for hosting the FreeCAD MCP GUI bridge."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


if globals() is not locals() and not locals().get("_FREECAD_MCP_SHARED_EXEC"):
    _this_file = Path(sys._getframe().f_code.co_filename).resolve()
    _namespace: dict[str, Any] = {
        "__builtins__": globals().get("__builtins__", __builtins__),
        "__file__": str(_this_file),
        "__name__": "FreeCADMCP.InitGui",
        "_FREECAD_MCP_SHARED_EXEC": True,
    }
    exec(compile(_this_file.read_text(encoding="utf-8"), str(_this_file), "exec"), _namespace)
else:
    import FreeCAD as App
    import FreeCADGui as Gui

    WORKBENCH_NAME = "FreeCAD MCP"
    START_COMMAND = "FreeCAD_MCP_StartBridge"
    STOP_COMMAND = "FreeCAD_MCP_StopBridge"
    STATUS_COMMAND = "FreeCAD_MCP_StatusBridge"
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 48777

    _BRIDGE_NS: dict[str, Any] | None = None

    def module_file() -> Path:
        configured = globals().get("__file__")
        if configured:
            return Path(str(configured)).resolve()
        return Path(sys._getframe().f_code.co_filename).resolve()

    def bridge_script_path() -> Path:
        configured = os.environ.get("FREECAD_MCP_BRIDGE_SCRIPT")
        if configured:
            return Path(configured)
        bundled = module_file().parent / "freecad_gui_bridge_server.py"
        if bundled.exists():
            return bundled
        return module_file().parents[2] / "scripts" / "freecad_gui_bridge_server.py"

    def bridge_namespace() -> dict[str, Any]:
        global _BRIDGE_NS
        if _BRIDGE_NS is not None:
            return _BRIDGE_NS
        script_path = bridge_script_path()
        namespace: dict[str, Any] = {}
        exec(script_path.read_text(encoding="utf-8"), namespace)
        _BRIDGE_NS = namespace
        return namespace

    def bridge_options() -> dict[str, Any]:
        return {
            "host": os.environ.get("FREECAD_MCP_GUI_HOST") or DEFAULT_HOST,
            "port": int(os.environ.get("FREECAD_MCP_GUI_PORT") or DEFAULT_PORT),
            "token": os.environ.get("FREECAD_MCP_GUI_TOKEN") or None,
        }

    def start_bridge() -> dict[str, Any]:
        namespace = bridge_namespace()
        return namespace["start_bridge"](**bridge_options())

    def stop_bridge() -> dict[str, Any]:
        global _BRIDGE_NS
        namespace = bridge_namespace()
        result = namespace["stop_bridge"]()
        _BRIDGE_NS = None
        return result

    def print_message(message: str) -> None:
        App.Console.PrintMessage(message.rstrip() + "\n")

    def autostart_enabled() -> bool:
        return os.environ.get("FREECAD_MCP_AUTOSTART", "").lower() in {"1", "true", "yes", "on"}

    class StartBridgeCommand:
        def GetResources(self) -> dict[str, str]:
            return {
                "MenuText": "Start MCP Bridge",
                "ToolTip": "Start the local FreeCAD MCP GUI bridge.",
                "Pixmap": "applications-internet",
            }

        def Activated(self) -> None:
            print_message(f"FreeCAD MCP bridge started: {start_bridge()}")

        def IsActive(self) -> bool:
            return True

    class StopBridgeCommand:
        def GetResources(self) -> dict[str, str]:
            return {
                "MenuText": "Stop MCP Bridge",
                "ToolTip": "Stop the local FreeCAD MCP GUI bridge.",
                "Pixmap": "process-stop",
            }

        def Activated(self) -> None:
            print_message(f"FreeCAD MCP bridge stopped: {stop_bridge()}")

        def IsActive(self) -> bool:
            return True

    class StatusBridgeCommand:
        def GetResources(self) -> dict[str, str]:
            return {
                "MenuText": "MCP Bridge Status",
                "ToolTip": "Print local FreeCAD MCP GUI bridge status.",
                "Pixmap": "help-about",
            }

        def Activated(self) -> None:
            namespace = bridge_namespace()
            status = namespace["rpc_status"]({})
            print_message(f"FreeCAD MCP bridge status: {status}")

        def IsActive(self) -> bool:
            return True

    class FreeCADMCPWorkbench(Gui.Workbench):
        MenuText = WORKBENCH_NAME
        ToolTip = "Host the local FreeCAD MCP GUI bridge."

        def Initialize(self) -> None:
            Gui.addCommand(START_COMMAND, StartBridgeCommand())
            Gui.addCommand(STOP_COMMAND, StopBridgeCommand())
            Gui.addCommand(STATUS_COMMAND, StatusBridgeCommand())
            self.appendToolbar(WORKBENCH_NAME, [START_COMMAND, STOP_COMMAND, STATUS_COMMAND])
            self.appendMenu(WORKBENCH_NAME, [START_COMMAND, STOP_COMMAND, STATUS_COMMAND])

        def Activated(self) -> None:
            if autostart_enabled():
                print_message(f"FreeCAD MCP bridge autostarted: {start_bridge()}")

        def Deactivated(self) -> None:
            return

        def GetClassName(self) -> str:
            return "Gui::PythonWorkbench"

    Gui.addWorkbench(FreeCADMCPWorkbench())

    if autostart_enabled():
        print_message(f"FreeCAD MCP bridge autostarted: {start_bridge()}")
