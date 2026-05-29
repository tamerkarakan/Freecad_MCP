from __future__ import annotations

import json
import logging
import os
import unittest

from freecad_mcp import logging_config
from freecad_mcp.logging_config import (
    JsonLogFormatter,
    configure_logging,
    log_event,
    log_tool_call,
    summarize_arguments,
)


def _reset_logger() -> None:
    logging_config._configured = False
    logger = logging.getLogger(logging_config.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)


class SummarizeArgumentsTests(unittest.TestCase):
    def test_reports_keys_and_size_without_values(self) -> None:
        summary = summarize_arguments({"code": "print('secret')", "token": "abc123"})

        self.assertEqual(summary["arg_keys"], ["code", "token"])
        self.assertEqual(summary["arg_count"], 2)
        self.assertGreater(summary["payload_bytes"], 0)
        blob = json.dumps(summary)
        self.assertNotIn("secret", blob)
        self.assertNotIn("abc123", blob)

    def test_handles_non_dict(self) -> None:
        self.assertEqual(
            summarize_arguments(None), {"arg_keys": [], "arg_count": 0, "payload_bytes": 0}
        )


class JsonFormatterTests(unittest.TestCase):
    def test_formats_record_with_fields_as_json(self) -> None:
        record = logging.LogRecord(
            name="freecad_mcp", level=logging.INFO, pathname=__file__, lineno=1,
            msg="tool_call", args=(), exc_info=None,
        )
        record.fields = {"event": "tool_call", "tool": "demo", "ok": True}

        rendered = json.loads(JsonLogFormatter().format(record))

        self.assertEqual(rendered["level"], "INFO")
        self.assertEqual(rendered["tool"], "demo")
        self.assertTrue(rendered["ok"])
        self.assertIn("ts", rendered)


class ConfigureLoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_logger()
        os.environ.pop("FREECAD_MCP_LOG_LEVEL", None)

    def test_logging_disabled_by_default(self) -> None:
        os.environ.pop("FREECAD_MCP_LOG_LEVEL", None)
        _reset_logger()
        logger = configure_logging(force=True)

        self.assertFalse(logger.isEnabledFor(logging.WARNING))

    def test_log_level_enables_records(self) -> None:
        os.environ["FREECAD_MCP_LOG_LEVEL"] = "INFO"
        _reset_logger()
        configure_logging(force=True)

        with self.assertLogs("freecad_mcp", level="INFO") as captured:
            log_event(logging.INFO, "server_start", tools=117)

        self.assertTrue(any("server_start" in line for line in captured.output))


class LogToolCallTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["FREECAD_MCP_LOG_LEVEL"] = "INFO"
        _reset_logger()
        configure_logging(force=True)

    def tearDown(self) -> None:
        _reset_logger()
        os.environ.pop("FREECAD_MCP_LOG_LEVEL", None)

    def test_success_logs_outcome_without_values(self) -> None:
        with self.assertLogs("freecad_mcp", level="INFO") as captured:
            with log_tool_call("freecad_python_exec", {"code": "print('secret')"}):
                pass

        # Structured data lives in record.fields, not the bare message; rendered
        # JSON (what actually reaches stderr) must never contain argument values.
        record = captured.records[-1]
        self.assertEqual(record.fields["event"], "tool_call")
        self.assertEqual(record.fields["tool"], "freecad_python_exec")
        self.assertTrue(record.fields["ok"])
        self.assertEqual(record.fields["arg_keys"], ["code"])
        rendered = JsonLogFormatter().format(record)
        self.assertNotIn("secret", rendered)

    def test_failure_logs_error_type_and_reraises(self) -> None:
        with self.assertLogs("freecad_mcp", level="WARNING") as captured:
            with self.assertRaises(ValueError):
                with log_tool_call("demo", {"x": 1}):
                    raise ValueError("boom")

        record = captured.records[-1]
        self.assertEqual(record.fields["tool"], "demo")
        self.assertFalse(record.fields["ok"])
        self.assertEqual(record.fields["error_type"], "ValueError")
        rendered = JsonLogFormatter().format(record)
        self.assertNotIn("boom", rendered)


if __name__ == "__main__":
    unittest.main()
