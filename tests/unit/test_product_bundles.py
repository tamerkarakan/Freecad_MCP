from __future__ import annotations

import unittest
from pathlib import Path

from freecad_mcp.mcp_stdio import build_server
from freecad_mcp.product_bundles import PRODUCT_BUNDLES, bundle_map, product_bundle_manifest


ROOT = Path(__file__).resolve().parents[2]


class ProductBundleTests(unittest.TestCase):
    def test_manifest_lists_sellable_bundles(self) -> None:
        manifest = product_bundle_manifest()
        keys = [item["key"] for item in manifest["bundles"]]

        self.assertEqual(keys, ["free", "pro", "studio", "team", "source", "unsafe"])
        self.assertEqual(manifest["env"], "FREECAD_MCP_MODULES")

    def test_paid_bundles_do_not_include_unsafe_exec(self) -> None:
        bundles = bundle_map()

        for key in ("free", "pro", "studio", "team"):
            self.assertFalse(bundles[key].to_dict()["includes_unsafe"], key)
        self.assertTrue(bundles["unsafe"].to_dict()["includes_unsafe"])

    def test_bundle_tool_counts_follow_upgrade_ladder(self) -> None:
        counts = {
            bundle.key: len(build_server(ROOT, enabled_modules=bundle.profile).definitions())
            for bundle in PRODUCT_BUNDLES
        }

        self.assertLess(counts["free"], counts["pro"])
        self.assertLess(counts["pro"], counts["studio"])
        self.assertLess(counts["studio"], counts["team"])
        self.assertEqual(counts["source"], 5)
        self.assertEqual(counts["unsafe"], 1)


if __name__ == "__main__":
    unittest.main()
