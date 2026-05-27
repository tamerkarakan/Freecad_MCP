from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from freecad_mcp.source_inventory import SourceInventoryScanner


class SourceInventoryScannerTests(unittest.TestCase):
    def test_scans_python_and_cpp_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src" / "Mod" / "Assembly").mkdir(parents=True)
            (root / "src" / "Mod" / "Part" / "Gui").mkdir(parents=True)

            (root / "src" / "Mod" / "Assembly" / "CommandCreate.py").write_text(
                """
class CommandCreateAssembly:
    def GetResources(self):
        return {
            "Pixmap": "Assembly_CreateAssembly",
            "MenuText": "New Assembly",
            "ToolTip": "Creates an assembly",
        }

Gui.addCommand("Assembly_CreateAssembly", CommandCreateAssembly())
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "Mod" / "Part" / "Gui" / "Command.cpp").write_text(
                """
DEF_STD_CMD_A(CmdPartBox)

CmdPartBox::CmdPartBox()
    : Command("Part_Box")
{
    sAppModule = "Part";
    sGroup = QT_TR_NOOP("Part");
    sMenuText = QT_TR_NOOP("Cube");
    sToolTipText = QT_TR_NOOP("Creates a solid cube");
    sPixmap = "Part_Box_Parametric";
}
""".lstrip(),
                encoding="utf-8",
            )

            payload = SourceInventoryScanner(root).build_payload()
            commands = {record["name"]: record for record in payload["commands"]}

            self.assertEqual(commands["Assembly_CreateAssembly"]["module"], "Assembly")
            self.assertEqual(commands["Assembly_CreateAssembly"]["menu_text"], "New Assembly")
            self.assertEqual(commands["Part_Box"]["language"], "cpp")
            self.assertEqual(commands["Part_Box"]["tooltip"], "Creates a solid cube")

    def test_missing_source_root_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                SourceInventoryScanner(Path(temp_dir)).build_payload()


if __name__ == "__main__":
    unittest.main()
