from __future__ import annotations

import unittest
from pathlib import Path

from freecad_mcp.workbench_artifact import workbench_artifact_manifest


ROOT = Path(__file__).resolve().parents[2]


class WorkbenchArtifactTests(unittest.TestCase):
    def test_manifest_lists_embedded_bridge_files(self) -> None:
        manifest = workbench_artifact_manifest(ROOT)
        targets = {file_spec["target"] for file_spec in manifest["files"]}

        self.assertEqual(manifest["artifact_key"], "freecad-workbench-module")
        self.assertIn("pro", manifest["consuming_profiles"])
        self.assertIn("FreeCADMCP/InitGui.py", targets)
        self.assertIn("FreeCADMCP/freecad_gui_bridge_server.py", targets)

    def test_manifest_sources_have_hashes(self) -> None:
        manifest = workbench_artifact_manifest(ROOT)

        for file_spec in manifest["files"]:
            self.assertGreater(file_spec["size"], 0)
            self.assertRegex(file_spec["sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
