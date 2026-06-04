"""Structured, stdout-safe logging for the FreeCAD MCP server.

stdout carries the MCP JSON-RPC stream, so every log record goes to stderr (or an
optional file) and never to stdout — writing logs to stdout would corrupt the
protocol. Logging is opt-in through environment variables so default runs stay
silent and protocol-safe:

- ``FREECAD_MCP_LOG_LEVEL``  DEBUG/INFO/WARNING/ERROR (unset or ``OFF`` disables logging)
- ``FREECAD_MCP_LOG_FILE``   optional path; when set, logs append there instead of stderr
- ``FREECAD_MCP_AGENT_ID``   optional stable label for the calling agent/client

Records are emitted as one JSON object per line. Tool-call logging records the
tool name, correlation ids, outcome, duration, and argument/response *key names*,
payload sizes, and payload hashes only. It never logs argument or response
values, so credentials, raw Python code, and large CAD payloads are not dumped.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

LOGGER_NAME = "freecad_mcp"
_DISABLED_LEVEL = logging.CRITICAL + 1

_configured = False
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "credential", "authorization", "api_key", "apikey")


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
    if not _configured:
        return
    logger = logging.getLogger(LOGGER_NAME)
    if logger.isEnabledFor(level):
        logger.log(level, event, extra={"fields": {"event": event, **runtime_identity(), **fields}})


def runtime_identity() -> dict[str, Any]:
    """Return low-cardinality process/agent identity fields for every record."""
    agent_id = os.environ.get("FREECAD_MCP_AGENT_ID", "").strip()
    return {
        "agent_id": agent_id or None,
        "server_pid": os.getpid(),
    }


def _json_fingerprint(payload: Any) -> tuple[int, str | None]:
    try:
        encoded = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return -1, None
    import hashlib

    return len(encoded), hashlib.sha256(encoded).hexdigest()


def _sensitive_keys(payload: dict[Any, Any]) -> list[str]:
    sensitive: list[str] = []
    for key in payload:
        key_text = str(key).casefold()
        if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
            sensitive.append(str(key))
    return sorted(sensitive)


def summarize_payload(payload: Any, *, prefix: str) -> dict[str, Any]:
    """Summarize a request or response payload without logging values."""
    payload_bytes, payload_sha256 = _json_fingerprint(payload)
    summary: dict[str, Any] = {
        f"{prefix}_type": type(payload).__name__,
        f"{prefix}_payload_bytes": payload_bytes,
    }
    if payload_sha256 is not None:
        summary[f"{prefix}_payload_sha256"] = payload_sha256
    if isinstance(payload, dict):
        summary[f"{prefix}_keys"] = sorted(str(key) for key in payload)
        summary[f"{prefix}_key_count"] = len(payload)
        sensitive = _sensitive_keys(payload)
        if sensitive:
            summary[f"{prefix}_sensitive_keys_redacted"] = sensitive
        if isinstance(payload.get("ok"), bool):
            summary[f"{prefix}_ok"] = payload["ok"]
    elif isinstance(payload, (list, tuple)):
        summary[f"{prefix}_length"] = len(payload)
    return summary


def summarize_arguments(arguments: Any) -> dict[str, Any]:
    """Describe tool arguments without leaking values.

    Returns the sorted argument key names and an approximate serialized payload
    size. Values are deliberately omitted so credentials (``token``), code
    payloads (``code``), and large CAD geometry never reach the logs.
    """
    if not isinstance(arguments, dict):
        return {
            "arg_keys": [],
            "arg_count": 0,
            "payload_bytes": 0,
            "arg_payload_bytes": 0,
        }
    payload_summary = summarize_payload(arguments, prefix="arg")
    summary: dict[str, Any] = {
        "arg_keys": payload_summary["arg_keys"],
        "arg_count": len(arguments),
        # Backward-compatible alias used by older tests/docs.
        "payload_bytes": payload_summary["arg_payload_bytes"],
        "arg_payload_bytes": payload_summary["arg_payload_bytes"],
    }
    if "arg_payload_sha256" in payload_summary:
        summary["arg_payload_sha256"] = payload_summary["arg_payload_sha256"]
    if "arg_sensitive_keys_redacted" in payload_summary:
        summary["arg_sensitive_keys_redacted"] = payload_summary["arg_sensitive_keys_redacted"]
    return summary


def summarize_response(response: Any) -> dict[str, Any]:
    """Describe a tool/bridge response without leaking values."""
    return summarize_payload(response, prefix="response")


@contextmanager
def log_timed_operation(
    event: str,
    *,
    start_event: bool = False,
    level: int = logging.INFO,
    failure_level: int = logging.WARNING,
    **fields: Any,
) -> Iterator[dict[str, Any]]:
    """Time an operation and log structured start/end records."""
    operation_id = uuid.uuid4().hex[:12]
    base = {"operation_id": operation_id, **fields}
    details: dict[str, Any] = {}
    started = time.perf_counter()
    if start_event:
        log_event(level, f"{event}_start", **base)
    try:
        yield details
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            failure_level,
            event,
            ok=False,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            **base,
            **details,
        )
        raise
    else:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(level, event, ok=True, duration_ms=duration_ms, **base, **details)


@contextmanager
def log_tool_call(tool_name: str, arguments: Any, *, request_fields: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Time a tool call and log its outcome (no argument or response values)."""
    call_id = uuid.uuid4().hex[:12]
    summary = summarize_arguments(arguments)
    fields = {
        "call_id": call_id,
        "tool": tool_name,
        **(request_fields or {}),
        **summary,
    }
    details: dict[str, Any] = {}
    started = time.perf_counter()
    log_event(logging.INFO, "tool_call_start", **fields)
    try:
        yield details
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logging.WARNING,
            "tool_call",
            ok=False,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            **fields,
            **details,
        )
        raise
    else:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logging.INFO,
            "tool_call",
            ok=True,
            duration_ms=duration_ms,
            **fields,
            **details,
        )
