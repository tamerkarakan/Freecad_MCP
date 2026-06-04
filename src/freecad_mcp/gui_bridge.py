"""Client-side manager for an opt-in FreeCAD GUI loopback bridge."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib import error, parse, request

from freecad_mcp.logging_config import log_event, summarize_payload
from freecad_mcp.tooling import JsonObject, ToolInputError


DEFAULT_GUI_BRIDGE_URL = "http://127.0.0.1:48777"


def gui_bridge_error_message(detail: str, *, http_code: int | None = None) -> str:
    """Turn bridge error payloads into actionable MCP-facing messages."""
    error_text = detail.strip()
    try:
        payload = json.loads(error_text)
        if isinstance(payload, dict):
            error_text = str(payload.get("error") or error_text)
    except json.JSONDecodeError:
        pass

    if error_text.startswith("unknown method:"):
        method = error_text.split(":", 1)[1].strip()
        message = (
            f"GUI bridge does not support RPC method '{method}'. "
            "The MCP server and the FreeCAD GUI bridge script are out of sync; "
            "stop/start the FreeCAD MCP bridge or restart FreeCAD so it reloads "
            "the current freecad_gui_bridge_server.py. If you installed a "
            "Workbench zip, rebuild and reinstall that zip first."
        )
    else:
        message = error_text

    if http_code is not None:
        return f"GUI bridge HTTP {http_code}: {message}"
    return message


def safe_url_fields(url: str) -> JsonObject:
    parsed = parse.urlsplit(url)
    return {
        "url_scheme": parsed.scheme,
        "url_host": parsed.hostname,
        "url_port": parsed.port,
    }


@dataclass
class GuiBridgeSession:
    session_id: str
    url: str
    token: str | None = None
    created_at: float = field(default_factory=time.time)
    request_count: int = 0
    last_status: JsonObject | None = None
    last_ok_at: float | None = None
    last_error_at: float | None = None
    last_error: str | None = None
    last_method: str | None = None
    last_duration_ms: int | None = None
    consecutive_failures: int = 0

    def record_success(self, method: str, duration_ms: int, *, status: JsonObject | None = None) -> None:
        self.request_count += 1
        self.last_method = method
        self.last_duration_ms = duration_ms
        self.last_ok_at = time.time()
        self.last_error = None
        self.last_error_at = None
        self.consecutive_failures = 0
        if method == "status" and status is not None:
            self.last_status = status

    def record_failure(self, method: str, duration_ms: int, message: str) -> None:
        self.request_count += 1
        self.last_method = method
        self.last_duration_ms = duration_ms
        self.last_error_at = time.time()
        self.last_error = message
        self.consecutive_failures += 1

    def recovery_guidance(self) -> str:
        return (
            "Run freecad_gui_watchdog_status with probe=true to re-check it. "
            "If the probe also fails, stop/start the FreeCAD MCP Workbench bridge or restart FreeCAD GUI, "
            "then attach again."
        )

    def to_dict(self) -> JsonObject:
        healthy = self.consecutive_failures == 0
        return {
            "session_id": self.session_id,
            "mode": "freecad-gui-attach",
            "url": self.url,
            "token_configured": self.token is not None,
            "created_at": self.created_at,
            "request_count": self.request_count,
            "last_status": self.last_status,
            "watchdog": {
                "healthy": healthy,
                "consecutive_failures": self.consecutive_failures,
                "last_ok_at": self.last_ok_at,
                "last_error_at": self.last_error_at,
                "last_error": self.last_error,
                "last_method": self.last_method,
                "last_duration_ms": self.last_duration_ms,
                "recovery": None if healthy else self.recovery_guidance(),
            },
        }


class GuiBridgeClient:
    """JSON-over-HTTP client for the GUI bridge script."""

    def call(
        self,
        *,
        url: str,
        method: str,
        params: JsonObject | None = None,
        token: str | None = None,
        timeout_sec: int = 10,
    ) -> JsonObject:
        started = time.perf_counter()
        endpoint = url.rstrip("/") + "/rpc"
        body = json.dumps({"method": method, "params": params or {}, "timeout_sec": timeout_sec}, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        rpc_request = request.Request(endpoint, data=body, headers=headers, method="POST")
        base_fields = {
            "method": method,
            "timeout_sec": timeout_sec,
            "token_configured": token is not None,
            **safe_url_fields(url),
            **summarize_payload(params or {}, prefix="gui_request"),
        }
        try:
            with request.urlopen(rpc_request, timeout=timeout_sec) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            log_event(
                logging.WARNING,
                "gui_bridge_rpc",
                ok=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                http_code=exc.code,
                error_type=type(exc).__name__,
                **base_fields,
            )
            raise ToolInputError(gui_bridge_error_message(detail, http_code=exc.code)) from exc
        except OSError as exc:
            log_event(
                logging.WARNING,
                "gui_bridge_rpc",
                ok=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error_type=type(exc).__name__,
                **base_fields,
            )
            raise ToolInputError(f"GUI bridge is not reachable at {url}: {exc}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            log_event(
                logging.WARNING,
                "gui_bridge_rpc",
                ok=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error_type=type(exc).__name__,
                **base_fields,
            )
            raise ToolInputError(f"GUI bridge returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            log_event(
                logging.WARNING,
                "gui_bridge_rpc",
                ok=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error_type="NonObjectResponse",
                **base_fields,
                **summarize_payload(payload, prefix="gui_response"),
            )
            raise ToolInputError("GUI bridge returned a non-object response")
        if not payload.get("ok", False):
            log_event(
                logging.WARNING,
                "gui_bridge_rpc",
                ok=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                bridge_ok=False,
                **base_fields,
                **summarize_payload(payload, prefix="gui_response"),
            )
            raise ToolInputError(gui_bridge_error_message(str(payload.get("error") or "GUI bridge call failed")))
        result = payload.get("result")
        returned = result if isinstance(result, dict) else {"result": result}
        log_event(
            logging.INFO,
            "gui_bridge_rpc",
            ok=True,
            duration_ms=int((time.perf_counter() - started) * 1000),
            bridge_ok=True,
            **base_fields,
            **summarize_payload(returned, prefix="gui_response"),
        )
        return returned


class GuiBridgeManager:
    """Tracks attached GUI bridge sessions for one MCP server process."""

    def __init__(self, client: GuiBridgeClient | None = None):
        self.client = client or GuiBridgeClient()
        self.sessions: dict[str, GuiBridgeSession] = {}

    def attach(
        self,
        *,
        url: str = DEFAULT_GUI_BRIDGE_URL,
        token: str | None = None,
        probe: bool = True,
        timeout_sec: int = 10,
    ) -> JsonObject:
        session = GuiBridgeSession(session_id=uuid.uuid4().hex[:12], url=url.rstrip("/"), token=token)
        status = None
        if probe:
            started = time.perf_counter()
            status = self.client.call(url=session.url, token=token, method="status", timeout_sec=timeout_sec)
            session.record_success("status", int((time.perf_counter() - started) * 1000), status=status)
        self.sessions[session.session_id] = session
        return {"session": session.to_dict(), "status": status}

    def list_sessions(self) -> JsonObject:
        return {"sessions": [session.to_dict() for session in self.sessions.values()], "count": len(self.sessions)}

    def detach(self, session_id: str) -> JsonObject:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return {"session": {"session_id": session_id, "mode": "freecad-gui-attach"}, "already_detached": True}
        return {"session": session.to_dict(), "detached": True}

    def call(self, session_id: str, method: str, params: JsonObject | None = None, *, timeout_sec: int = 10) -> JsonObject:
        session = self.sessions.get(session_id)
        if session is None:
            raise ToolInputError(f"unknown GUI bridge session: {session_id}")
        started = time.perf_counter()
        try:
            result = self.client.call(url=session.url, token=session.token, method=method, params=params, timeout_sec=timeout_sec)
        except ToolInputError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            session.record_failure(method, duration_ms, str(exc))
            raise ToolInputError(f"{exc}. GUI bridge session marked unhealthy; {session.recovery_guidance()}") from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        session.record_success(method, duration_ms, status=result if method == "status" else None)
        return {"session": session.to_dict(), "gui": result}

    def watchdog_status(self, session_id: str, *, probe: bool = False, timeout_sec: int = 3) -> JsonObject:
        session = self.sessions.get(session_id)
        if session is None:
            raise ToolInputError(f"unknown GUI bridge session: {session_id}")
        if probe:
            try:
                probe_result = self.call(session_id, "status", {}, timeout_sec=timeout_sec)
                return {
                    "ok": True,
                    "probed": True,
                    "session": probe_result["session"],
                    "gui": probe_result["gui"],
                }
            except ToolInputError as exc:
                return {
                    "ok": False,
                    "probed": True,
                    "session": session.to_dict(),
                    "error": str(exc),
                    "recovery": session.recovery_guidance(),
                }
        healthy = session.consecutive_failures == 0
        return {
            "ok": healthy,
            "probed": False,
            "session": session.to_dict(),
            "recovery": None if healthy else session.recovery_guidance(),
        }
