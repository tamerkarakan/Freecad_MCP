from __future__ import annotations

import sys
import unittest
from pathlib import Path

from freecad_mcp.runtime_tools import RuntimeToolService
from freecad_mcp.tooling import ToolInputError


class RuntimeToolServiceTests(unittest.TestCase):
    def test_python_exec_accepts_explicit_executable(self) -> None:
        service = RuntimeToolService()

        result = service.python_exec(
            {
                "executable": sys.executable,
                "code": "print('spark-tool')",
                "allow_unsafe": True,
                "timeout_sec": 10,
            }
        )

        self.assertTrue(result["execution"]["ok"])
        self.assertIn("spark-tool", result["execution"]["stdout"])
        self.assertEqual(result["audit"]["unsafe_opt_in"], True)

    def test_python_exec_requires_unsafe_opt_in(self) -> None:
        service = RuntimeToolService()

        with self.assertRaises(ToolInputError):
            service.python_exec({"executable": sys.executable, "code": "print('blocked')"})

    def test_python_exec_compact_output_omits_stream_text(self) -> None:
        service = RuntimeToolService()

        result = service.python_exec(
            {
                "executable": sys.executable,
                "code": "print('spark-compact')",
                "allow_unsafe": True,
                "compact_output": True,
                "timeout_sec": 10,
            }
        )

        self.assertTrue(result["execution"]["ok"])
        self.assertTrue(result["execution"]["compact"])
        self.assertNotIn("stdout", result["execution"])
        self.assertGreater(result["execution"]["stdout_total_chars"], 0)
        self.assertEqual(result["audit"]["compact_output"], True)

    def test_status_reports_discovery_without_probe(self) -> None:
        service = RuntimeToolService()

        result = service.session_status({"executable": sys.executable, "probe": False})

        self.assertTrue(result["discovery"]["found"])
        self.assertEqual(Path(result["discovery"]["executable"]).resolve(), Path(sys.executable).resolve())


if __name__ == "__main__":
    unittest.main()
