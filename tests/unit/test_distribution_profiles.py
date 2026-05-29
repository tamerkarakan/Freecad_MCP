from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from freecad_mcp.distribution_profiles import distribution_manifest, distribution_profile_map


ROOT = Path(__file__).resolve().parents[2]


class DistributionProfileTests(unittest.TestCase):
    def test_manifest_lists_distribution_profiles(self) -> None:
        manifest = distribution_manifest()
        keys = [profile["key"] for profile in manifest["profiles"]]

        self.assertEqual(keys, ["free", "pro", "studio", "team", "source", "unsafe"])
        self.assertEqual(manifest["project"]["entrypoint"], "freecad-hybrid-mcp")

    def test_gui_profiles_carry_workbench_component(self) -> None:
        profiles = distribution_profile_map()

        self.assertNotIn("workbench-module", profiles["free"].components)
        for key in ("pro", "studio", "team"):
            self.assertIn("workbench-module", profiles[key].components)
            self.assertEqual(profiles[key].to_dict()["workbench_artifact"]["zip_name"], "freecad-mcp-workbench.zip")

    def test_mcp_config_uses_profile_env(self) -> None:
        pro_config = distribution_profile_map()["pro"].mcp_config()
        server = pro_config["mcpServers"]["freecad-pro"]

        self.assertEqual(server["command"], "freecad-hybrid-mcp")
        self.assertEqual(server["env"]["FREECAD_MCP_MODULES"], "pro")
        self.assertIn("FREECAD_MCP_REPO_ROOT", server["env"])

    def test_pyproject_declares_installable_package_shape(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["build-system"]["build-backend"], "setuptools.build_meta")
        self.assertEqual(pyproject["project"]["scripts"]["freecad-hybrid-mcp"], "freecad_mcp.mcp_stdio:main")
        self.assertEqual(pyproject["tool"]["setuptools"]["packages"]["find"]["where"], ["src"])
        self.assertIn("runtime_scripts/*.py", pyproject["tool"]["setuptools"]["package-data"]["freecad_mcp"])


if __name__ == "__main__":
    unittest.main()
