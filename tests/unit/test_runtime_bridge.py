from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from freecad_mcp.runtime_bridge import (
    FreeCadCmdBridge,
    FreeCadDiscovery,
    FreeCadExecutionResult,
    MAX_INLINE_CODE_CHARS,
    parse_prefixed_json,
)


class RuntimeBridgeTests(unittest.TestCase):
    def test_discovers_executable_from_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            exe = home / "FreeCADCmd.exe"
            exe.write_text("", encoding="utf-8")

            result = FreeCadDiscovery(env={}).discover(freecad_home=str(home))

            self.assertTrue(result.found)
            self.assertEqual(result.executable, exe.resolve())

    def test_discovers_quoted_executable_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "FreeCADCmd.exe"
            exe.write_text("", encoding="utf-8")

            result = FreeCadDiscovery(env={"FREECAD_MCP_FREECAD_CMD": f'"{exe}"'}).discover()

            self.assertTrue(result.found)
            self.assertEqual(result.executable, exe.resolve())

    def test_does_not_select_directory_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / "FreeCADCmd.exe").mkdir()

            result = FreeCadDiscovery(env={}).discover(freecad_home=str(home))

            self.assertFalse(result.found)

    def test_execute_python_uses_process_envelope(self) -> None:
        result = FreeCadCmdBridge(Path(sys.executable)).execute_python(
            "print('spark-runtime')",
            timeout_sec=10,
        )

        self.assertTrue(result.ok)
        self.assertIn("spark-runtime", result.stdout)
        self.assertFalse(result.timed_out)

    def test_execute_python_uses_temp_script_for_long_code(self) -> None:
        code = "print('long-script-runtime')\n" + ("# filler\n" * (MAX_INLINE_CODE_CHARS // 4))

        result = FreeCadCmdBridge(Path(sys.executable)).execute_python(code, timeout_sec=10)

        self.assertTrue(result.ok)
        self.assertIn("long-script-runtime", result.stdout)
        self.assertEqual(len(result.argv), 2)
        self.assertTrue(result.argv[1].endswith(".py"))
        self.assertFalse(Path(result.argv[1]).exists())

    def test_execute_python_timeout_is_structured(self) -> None:
        result = FreeCadCmdBridge(Path(sys.executable)).execute_python(
            "import time; time.sleep(2)",
            timeout_sec=1,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.returncode)

    def test_execute_python_launch_error_is_structured(self) -> None:
        missing = Path("C:/__definitely_missing__/FreeCADCmd.exe")
        result = FreeCadCmdBridge(missing).execute_python("print('x')", timeout_sec=1)

        self.assertFalse(result.ok)
        self.assertFalse(result.timed_out)
        self.assertIsNotNone(result.launch_error)
        self.assertIsNone(result.returncode)

    def test_to_dict_truncates_large_fields(self) -> None:
        long_arg = "a" * 6000
        long_stream = "s" * 20000
        result = FreeCadExecutionResult(
            executable=Path(sys.executable),
            argv=[sys.executable, "-c", long_arg],
            timeout_sec=10,
            duration_ms=1,
            returncode=0,
            stdout=long_stream,
            stderr=long_stream,
            timed_out=False,
        )
        payload = result.to_dict()

        self.assertTrue(payload["argv_truncated"])
        self.assertTrue(payload["stdout_truncated"])
        self.assertTrue(payload["stderr_truncated"])
        self.assertEqual(payload["stdout_total_chars"], len(long_stream))
        self.assertEqual(payload["stderr_total_chars"], len(long_stream))

    def test_compact_dict_omits_argv_and_stream_text(self) -> None:
        result = FreeCadExecutionResult(
            executable=Path(sys.executable),
            argv=[sys.executable, "-c", "print('x')"],
            timeout_sec=10,
            duration_ms=1,
            returncode=0,
            stdout="stream-output",
            stderr="stream-error",
            timed_out=False,
        )

        payload = result.to_compact_dict()

        self.assertTrue(payload["compact"])
        self.assertNotIn("argv", payload)
        self.assertNotIn("stdout", payload)
        self.assertNotIn("stderr", payload)
        self.assertEqual(payload["stdout_total_chars"], len("stream-output"))
        self.assertEqual(payload["stderr_total_chars"], len("stream-error"))
        self.assertIn("stdout_sha256", payload)
        self.assertIn("stderr_sha256", payload)

    def test_parse_prefixed_json_ignores_noise(self) -> None:
        parsed = parse_prefixed_json('noise\n__FREECAD_MCP_JSON__{"version": ["1"]}\n')

        self.assertEqual(parsed, {"version": ["1"]})

    def test_parse_prefixed_json_handles_malformed_payload(self) -> None:
        parsed = parse_prefixed_json("noise\n__FREECAD_MCP_JSON__{bad json}\n")

        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()
