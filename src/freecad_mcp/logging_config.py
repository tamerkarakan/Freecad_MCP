"""Structured, stdout-safe logging for the FreeCAD MCP server.

stdout carries the MCP JSON-RPC stream, so every log record goes to stderr (or an
optional file) and never to stdout — writing logs to stdout would corrupt the
protocol. Logging is opt-in through environment variables so default runs stay
silent and protocol-safe:

- ``FREECAD_MCP_LOG_LEVEL``  DEBUG/INFO/WARNING/ERROR (unset or ``OFF`` disables logging)
- ``FREECAD_MCP_LOG_FILE``   optional path; when set, logs append there instead of stderr

Records are emitted as one JSON object per line. Tool-call logging records the
tool name, outcome, duration, and argument *key names* and payload size only —
never argument values — so credentials and large CAD payloads are not dumped.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

LOGGER_NAME = "freecad_mcp"
_DISABLED_LEVEL = logging.CRITICAL + 1

_configured = False


class JsonLogFormatter(logging.Formatter):
    """Render log records as single-line JSON, merging structured ``fields``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                if key not in payload:
                    payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(*, force: bool = False) -> logging.Logger:
    """Configure and return the package logger from environment settings.

    Idempotent: repeated calls are no-ops unless ``force`` is set. Safe to call at
    server startup.
    """
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    level_name = os.environ.get("FREECAD_MCP_LOG_LEVEL", "").strip().upper()
    logger.propagate = False

    if not level_name or level_name == "OFF":
        logger.addHandler(logging.NullHandler())
        logger.setLevel(_DISABLED_LEVEL)
        _configured = True
        return logger

    level = getattr(logging, level_name, logging.WARNING)
    log_file = os.environ.get("FREECAD_MCP_LOG_FILE", "").strip()
    handler: logging.Handler
    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
    else:
        # stderr, never stdout: stdout is the MCP protocol channel.
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    _configured = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_event(level: int, event: str, **fields: Any) -> None:
    """Emit a structured event. ``fields`` must contain no sensitive values."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.isEnabledFor(level):
        logger.log(level, event, extra={"fields": {"event": event, **fields}})


def summarize_arguments(arguments: Any) -> dict[str, Any]:
    """Describe tool arguments without leaking values.

    Returns the sorted argument key names and an approximate serialized payload
    size. Values are deliberately omitted so credentials (``token``), code
    payloads (``code``), and large CAD geometry never reach the logs.
    """
    if not isinstance(arguments, dict):
        return {"arg_keys": [], "arg_count": 0, "payload_bytes": 0}
    try:
        payload_bytes = len(json.dumps(arguments, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        payload_bytes = -1
    return {
        "arg_keys": sorted(str(key) for key in arguments),
        "arg_count": len(arguments),
        "payload_bytes": payload_bytes,
    }


@contextmanager
def log_tool_call(tool_name: str, arguments: Any) -> Iterator[None]:
    """Time a tool call and log its outcome (no argument values)."""
    summary = summarize_arguments(arguments)
    started = time.monotonic()
    try:
        yield
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_event(
            logging.WARNING,
            "tool_call",
            tool=tool_name,
            ok=False,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            **summary,
        )
        raise
    else:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_event(
            logging.INFO,
            "tool_call",
            tool=tool_name,
            ok=True,
            duration_ms=duration_ms,
            **summary,
        )
