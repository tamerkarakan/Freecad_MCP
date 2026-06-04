"""FreeCADCmd discovery and execution bridge."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freecad_mcp.logging_config import log_event


FREECAD_JSON_PREFIX = "__FREECAD_MCP_JSON__"
MAX_EXEC_ARG_CHARS = 2_000
MAX_EXEC_STREAM_CHARS = 12_000
MAX_INLINE_CODE_CHARS = 8_000


@dataclass(frozen=True)
class FreeCadCandidate:
    executable: Path
    source: str
    exists: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "executable": str(self.executable),
            "source": self.source,
            "exists": self.exists,
            "is_file": self.executable.is_file(),
        }


@dataclass(frozen=True)
class FreeCadDiscoveryResult:
    executable: Path | None
    candidates: list[FreeCadCandidate]

    @property
    def found(self) -> bool:
        return self.executable is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "executable": str(self.executable) if self.executable else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class FreeCadExecutionResult:
    executable: Path
    argv: list[str]
    timeout_sec: int
    duration_ms: int
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    launch_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.launch_error is None

    def to_dict(self) -> dict[str, Any]:
        argv, argv_truncated = summarize_argv(self.argv, MAX_EXEC_ARG_CHARS)
        stdout, stdout_truncated = truncate_text(self.stdout, MAX_EXEC_STREAM_CHARS)
        stderr, stderr_truncated = truncate_text(self.stderr, MAX_EXEC_STREAM_CHARS)
        return {
            "ok": self.ok,
            "executable": str(self.executable),
            "argv": argv,
            "argv_truncated": argv_truncated,
            "timeout_sec": self.timeout_sec,
            "duration_ms": self.duration_ms,
            "returncode": self.returncode,
            "stdout": stdout,
            "stdout_truncated": stdout_truncated,
            "stdout_total_chars": len(self.stdout),
            "stderr": stderr,
            "stderr_truncated": stderr_truncated,
            "stderr_total_chars": len(self.stderr),
            "timed_out": self.timed_out,
            "launch_error": self.launch_error,
        }

    def to_compact_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "executable": str(self.executable),
            "argv_count": len(self.argv),
            "timeout_sec": self.timeout_sec,
            "duration_ms": self.duration_ms,
            "returncode": self.returncode,
            "stdout_total_chars": len(self.stdout),
            "stdout_sha256": hashlib.sha256(self.stdout.encode("utf-8")).hexdigest(),
            "stderr_total_chars": len(self.stderr),
            "stderr_sha256": hashlib.sha256(self.stderr.encode("utf-8")).hexdigest(),
            "timed_out": self.timed_out,
            "launch_error": self.launch_error,
            "compact": True,
        }


class FreeCadDiscovery:
    """Find a usable FreeCADCmd executable without hard-coding machine paths."""

    def __init__(
        self,
        env: dict[str, str] | None = None,
        platform_common_roots: list[Path] | None = None,
    ):
        self.env = env if env is not None else os.environ
        self.platform_common_roots = platform_common_roots if platform_common_roots is not None else []

    def discover(
        self,
        *,
        executable: str | None = None,
        freecad_home: str | None = None,
    ) -> FreeCadDiscoveryResult:
        candidates = self._candidates(executable=executable, freecad_home=freecad_home)
        found = next((candidate.executable for candidate in candidates if candidate.exists), None)
        return FreeCadDiscoveryResult(executable=found, candidates=candidates)

    def _candidates(
        self,
        *,
        executable: str | None,
        freecad_home: str | None,
    ) -> list[FreeCadCandidate]:
        raw_candidates: list[tuple[Path, str]] = []

        if executable:
            raw_candidates.append((clean_path(executable), "argument:executable"))
        env_executable = self.env.get("FREECAD_MCP_FREECAD_CMD")
        if env_executable:
            raw_candidates.append((clean_path(env_executable), "env:FREECAD_MCP_FREECAD_CMD"))

        home_values = []
        if freecad_home:
            home_values.append((clean_path(freecad_home), "argument:freecad_home"))
        env_home = self.env.get("FREECAD_MCP_FREECAD_HOME")
        if env_home:
            home_values.append((clean_path(env_home), "env:FREECAD_MCP_FREECAD_HOME"))

        for home, source in home_values:
            raw_candidates.extend(
                [
                    (home / "FreeCADCmd.exe", source),
                    (home / "bin" / "freecadcmd.exe", source),
                    (home / "bin" / "FreeCADCmd.exe", source),
                ]
            )

        for command_name in ("FreeCADCmd.exe", "freecadcmd.exe", "FreeCADCmd", "freecadcmd"):
            path = shutil.which(command_name)
            if path:
                raw_candidates.append((Path(path), f"path:{command_name}"))

        for root in self.platform_common_roots:
            raw_candidates.extend(
                [
                    (root / "FreeCADCmd.exe", "common-root"),
                    (root / "bin" / "freecadcmd.exe", "common-root"),
                ]
            )

        deduped: dict[str, FreeCadCandidate] = {}
        for path, source in raw_candidates:
            resolved = path.expanduser().resolve()
            exists = resolved.exists() and resolved.is_file()
            deduped.setdefault(
                str(resolved).casefold(),
                FreeCadCandidate(executable=resolved, source=source, exists=exists),
            )
        return list(deduped.values())


class FreeCadCmdBridge:
    """Run Python snippets through FreeCADCmd.

    This first bridge is intentionally process-per-call. It is slower than a
    persistent session, but deterministic and easy to test.
    """

    def __init__(self, executable: Path):
        self.executable = executable.resolve()

    def execute_python(self, code: str, *, timeout_sec: int = 30) -> FreeCadExecutionResult:
        started = time.perf_counter()
        script_path: Path | None = None
        if len(code) > MAX_INLINE_CODE_CHARS:
            handle = tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False)
            try:
                handle.write(code)
                script_path = Path(handle.name)
            finally:
                handle.close()
            argv = [str(self.executable), str(script_path)]
        else:
            argv = [str(self.executable), "-c", code]
        try:
            completed = subprocess.run(
                argv,
                cwd=str(self.executable.parent),
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec,
                check=False,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = FreeCadExecutionResult(
                executable=self.executable,
                argv=argv,
                timeout_sec=timeout_sec,
                duration_ms=duration_ms,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
            )
            log_freecadcmd_execution(result)
            return result
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            result = FreeCadExecutionResult(
                executable=self.executable,
                argv=argv,
                timeout_sec=timeout_sec,
                duration_ms=duration_ms,
                returncode=None,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )
            log_freecadcmd_execution(result)
            return result
        except OSError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = FreeCadExecutionResult(
                executable=self.executable,
                argv=argv,
                timeout_sec=timeout_sec,
                duration_ms=duration_ms,
                returncode=None,
                stdout="",
                stderr=f"{type(exc).__name__}: {exc}",
                timed_out=False,
                launch_error=str(exc),
            )
            log_freecadcmd_execution(result)
            return result
        finally:
            if script_path is not None:
                try:
                    script_path.unlink()
                except OSError:
                    pass

    def probe(self, *, timeout_sec: int = 30) -> dict[str, Any]:
        code = (
            "import json\n"
            "import FreeCAD as App\n"
            "payload = {\n"
            "    'version': App.Version(),\n"
            "    'user_app_data': App.getUserAppDataDir(),\n"
            "    'resource_dir': App.getResourceDir(),\n"
            "}\n"
            f"print('{FREECAD_JSON_PREFIX}' + json.dumps(payload))\n"
        )
        result = self.execute_python(code, timeout_sec=timeout_sec)
        payload = parse_prefixed_json(result.stdout)
        return {"execution": result.to_dict(), "freecad": payload}


def clean_path(value: str) -> Path:
    return Path(value.strip().strip('"').strip("'"))


def parse_prefixed_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for line in text.splitlines():
        if line.startswith(FREECAD_JSON_PREFIX):
            try:
                parsed, _ = decoder.raw_decode(line[len(FREECAD_JSON_PREFIX) :])
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


def log_freecadcmd_execution(result: FreeCadExecutionResult) -> None:
    """Log process-per-call FreeCADCmd timings without argv/code/stdout values."""
    level = logging.INFO if result.ok else logging.WARNING
    fields: dict[str, Any] = {
        "ok": result.ok,
        "executable": str(result.executable),
        "argv_count": len(result.argv),
        "timeout_sec": result.timeout_sec,
        "duration_ms": result.duration_ms,
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "stdout_total_chars": len(result.stdout),
        "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "stderr_total_chars": len(result.stderr),
        "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
    }
    if result.launch_error is not None:
        fields["launch_error_type"] = "OSError"
    log_event(level, "freecadcmd_exec", **fields)


def truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(value) - (head + tail)
    clipped = (
        value[:head]
        + f"\n...<truncated {omitted} chars>...\n"
        + value[-tail:]
    )
    return clipped, True


def summarize_argv(argv: list[str], max_arg_chars: int) -> tuple[list[str], bool]:
    preview: list[str] = []
    truncated = False
    for arg in argv:
        clipped, arg_truncated = truncate_text(arg, max_arg_chars)
        preview.append(clipped)
        truncated = truncated or arg_truncated
    return preview, truncated
