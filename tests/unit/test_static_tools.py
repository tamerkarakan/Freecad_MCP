from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from freecad_mcp.static_tools import InventoryStore, StaticToolService
from freecad_mcp.tooling import ToolInputError


class StaticToolServiceTests(unittest.TestCase):
    def test_command_filters_and_describe(self) -> None:
        with fake_repo() as repo:
            service = StaticToolService(InventoryStore(repo))

            result = service.command_list({"module": "Part", "query": "cube"})

            self.assertEqual(result["total"], 1)
            self.assertEqual(result["commands"][0]["name"], "Part_Box")
            described = service.command_describe({"name": "Part_Box"})
            self.assertEqual(described["matches"][0]["source"]["path"], "src/Mod/Part/Gui/Command.cpp")

    def test_source_search_and_open_are_bounded_to_freecad_root(self) -> None:
        with fake_repo() as repo:
            service = StaticToolService(InventoryStore(repo))

            matches = service.source_search({"query": "Command(\"Part_Box\")", "glob": "*.cpp"})

            self.assertEqual(matches["matches"][0]["path"], "src/Mod/Part/Gui/Command.cpp")
            opened = service.source_open(
                {"path": "src/Mod/Part/Gui/Command.cpp", "start_line": 1, "line_count": 2}
            )
            self.assertEqual(len(opened["lines"]), 2)
            with self.assertRaises(ToolInputError):
                service.source_open({"path": "../secret.txt"})


class fake_repo:
    def __enter__(self) -> Path:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        freecad_root = root / "upstream" / "FreeCAD"
        command_file = freecad_root / "src" / "Mod" / "Part" / "Gui" / "Command.cpp"
        command_file.parent.mkdir(parents=True)
        command_file.write_text(
            "CmdPartBox::CmdPartBox()\n"
            "    : Command(\"Part_Box\")\n"
            "{\n"
            "    sMenuText = QT_TR_NOOP(\"Cube\");\n"
            "}\n",
            encoding="utf-8",
        )
        inventory = {
            "scan": {
                "remote": "https://github.com/FreeCAD/FreeCAD.git",
                "branch": "main",
                "commit": "abc123",
                "freecad_root": str(freecad_root),
            },
            "workbenches": [{"name": "Part", "has_init_gui": True, "has_gui_cpp": True}],
            "proposed_tool_families": [],
            "commands": [
                {
                    "name": "Part_Box",
                    "module": "Part",
                    "language": "cpp",
                    "source_kind": "Gui::Command constructor",
                    "source": {"path": "src/Mod/Part/Gui/Command.cpp", "line": 2},
                    "class_name": "CmdPartBox",
                    "menu_text": "Cube",
                    "tooltip": "Creates a solid cube",
                    "group": "Part",
                    "pixmap": "Part_Box",
                }
            ],
        }
        docs = root / "docs"
        docs.mkdir()
        (docs / "freecad_tool_inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
        return root

    def __exit__(self, exc_type, exc, tb) -> None:
        self.temp_dir.cleanup()
