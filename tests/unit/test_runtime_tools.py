from __future__ import annotations

import sys
import unittest
from pathlib import Path

from freecad_mcp.runtime_tools import RuntimeToolService


class RuntimeToolServiceTests(unittest.TestCase):
    def test_python_exec_accepts_explicit_executable(self) -> None:
        service = RuntimeToolService()

        result = service.python_exec(
            {
                "executable": sys.executable,
                "code": "print('spark-tool')",
                "timeout_sec": 10,
            }
        )

        self.assertTrue(result["execution"]["ok"])
        self.assertIn("spark-tool", result["execution"]["stdout"])

    def test_status_reports_discovery_without_probe(self) -> None:
        service = RuntimeToolService()

        result = service.session_status({"executable": sys.executable, "probe": False})

        self.assertTrue(result["discovery"]["found"])
        self.assertEqual(Path(result["discovery"]["executable"]).resolve(), Path(sys.executable).resolve())


if __name__ == "__main__":
    unittest.main()
