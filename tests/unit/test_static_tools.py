from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from freecad_mcp.static_tools import InventoryStore, StaticToolService, safe_source_path
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

    def test_source_search_rejects_long_query(self) -> None:
        with fake_repo() as repo:
            service = StaticToolService(InventoryStore(repo))

            with self.assertRaises(ToolInputError):
                service.source_search({"query": "x" * 501})


class SafeSourcePathTests(unittest.TestCase):
    def test_accepts_nested_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "Mod").mkdir(parents=True)

            target = safe_source_path(root, "src/Mod")

            self.assertTrue(target.is_relative_to(root.resolve()))

    def test_rejects_absolute_and_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for bad in ("../secret.txt", "src/../../etc", "/etc/passwd", "C:/Windows", "a/../../b"):
                with self.assertRaises(ToolInputError):
                    safe_source_path(root, bad)

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            (root / "src").mkdir(parents=True)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("top secret", encoding="utf-8")

            link = root / "src" / "escape"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not permitted on this platform")

            # The link resolves outside the root, so the resolved-path containment
            # check must reject traversal through it.
            with self.assertRaises(ToolInputError):
                safe_source_path(root, "src/escape/secret.txt")


class SourceSearchBoundTests(unittest.TestCase):
    def test_max_files_truncates_scan(self) -> None:
        with fake_repo() as repo:
            service = StaticToolService(InventoryStore(repo))
            src_dir = repo / "upstream" / "FreeCAD" / "src"
            for index in range(5):
                (src_dir / f"extra_{index}.cpp").write_text('Command("Part_Box")\n', encoding="utf-8")

            result = service.source_search(
                {"query": "Command", "glob": "*.cpp", "max_files": 1, "max_results": 100}
            )

            self.assertTrue(result["truncated"])
            self.assertEqual(result["files_scanned"], 1)
            self.assertEqual(result["stop_reason"], "max_files")

    def test_unbounded_scan_reports_not_truncated(self) -> None:
        with fake_repo() as repo:
            service = StaticToolService(InventoryStore(repo))

            result = service.source_search({"query": "Command", "glob": "*.cpp"})

            self.assertFalse(result["truncated"])
            self.assertNotIn("stop_reason", result)
            self.assertGreaterEqual(len(result["matches"]), 1)


class fake_repo:
    def __enter__(self) -> Path:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"FREECAD_MCP_FREECAD_ROOT": ""})
        self.env_patch.start()
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
        self.env_patch.stop()
        self.temp_dir.cleanup()
