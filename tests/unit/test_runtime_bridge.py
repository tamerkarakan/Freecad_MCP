from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from freecad_mcp.runtime_bridge import FreeCadCmdBridge, FreeCadDiscovery, parse_prefixed_json


class RuntimeBridgeTests(unittest.TestCase):
    def test_discovers_executable_from_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            exe = home / "FreeCADCmd.exe"
            exe.write_text("", encoding="utf-8")

            result = FreeCadDiscovery(env={}).discover(freecad_home=str(home))

            self.assertTrue(result.found)
            self.assertEqual(result.executable, exe.resolve())

    def test_execute_python_uses_process_envelope(self) -> None:
        result = FreeCadCmdBridge(Path(sys.executable)).execute_python(
            "print('spark-runtime')",
            timeout_sec=10,
        )

        self.assertTrue(result.ok)
        self.assertIn("spark-runtime", result.stdout)
        self.assertFalse(result.timed_out)

    def test_execute_python_timeout_is_structured(self) -> None:
        result = FreeCadCmdBridge(Path(sys.executable)).execute_python(
            "import time; time.sleep(2)",
            timeout_sec=1,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.returncode)

    def test_parse_prefixed_json_ignores_noise(self) -> None:
        parsed = parse_prefixed_json('noise\n__FREECAD_MCP_JSON__{"version": ["1"]}\n')

        self.assertEqual(parsed, {"version": ["1"]})


if __name__ == "__main__":
    unittest.main()
