"""FreeCADCmd discovery and execution bridge."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FREECAD_JSON_PREFIX = "__FREECAD_MCP_JSON__"


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

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "executable": str(self.executable),
            "argv": self.argv,
            "timeout_sec": self.timeout_sec,
            "duration_ms": self.duration_ms,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
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
        argv = [str(self.executable), "-c", code]
        try:
            completed = subprocess.run(
                argv,
                cwd=str(self.executable.parent),
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec,
                check=False,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return FreeCadExecutionResult(
                executable=self.executable,
                argv=argv,
                timeout_sec=timeout_sec,
                duration_ms=duration_ms,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return FreeCadExecutionResult(
                executable=self.executable,
                argv=argv,
                timeout_sec=timeout_sec,
                duration_ms=duration_ms,
                returncode=None,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )

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
    for line in text.splitlines():
        if line.startswith(FREECAD_JSON_PREFIX):
            try:
                parsed = json.loads(line[len(FREECAD_JSON_PREFIX) :])
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None
