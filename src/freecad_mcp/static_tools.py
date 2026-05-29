"""Static source-backed MCP tools.

These tools deliberately do not import or execute FreeCAD. They answer from the
generated inventory and from the local ignored FreeCAD checkout.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from freecad_mcp.tooling import (
    JsonObject,
    ToolDefinition,
    ToolInputError,
    bounded_int,
    optional_string,
    required_string,
)


class InventoryStore:
    """Read-only access to the generated FreeCAD source inventory."""

    def __init__(
        self,
        repo_root: Path,
        inventory_path: Path | None = None,
        freecad_root: Path | None = None,
    ):
        self.repo_root = repo_root.resolve()
        self.inventory_path = (
            inventory_path
            if inventory_path is not None
            else self.repo_root / "docs" / "freecad_tool_inventory.json"
        ).resolve()
        self._inventory: JsonObject | None = None
        self._freecad_root_override = freecad_root.resolve() if freecad_root else None

    @property
    def inventory(self) -> JsonObject:
        if self._inventory is None:
            self._inventory = json.loads(self.inventory_path.read_text(encoding="utf-8"))
        return self._inventory

    @property
    def scan(self) -> JsonObject:
        return self.inventory.get("scan", {})

    @property
    def commands(self) -> list[JsonObject]:
        return list(self.inventory.get("commands", []))

    @property
    def workbenches(self) -> list[JsonObject]:
        return list(self.inventory.get("workbenches", []))

    @property
    def tool_families(self) -> list[JsonObject]:
        return list(self.inventory.get("proposed_tool_families", []))

    @property
    def freecad_root(self) -> Path:
        env_root = os.environ.get("FREECAD_MCP_FREECAD_ROOT")
        if env_root:
            return Path(env_root).resolve()
        if self._freecad_root_override:
            return self._freecad_root_override
        scan_root = self.scan.get("freecad_root")
        if scan_root:
            return Path(str(scan_root)).resolve()
        return self.repo_root / "upstream" / "FreeCAD"


class StaticToolService:
    """Typed static tool implementation for Phase 1."""

    TEXT_SUFFIXES = {
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".hxx",
        ".py",
        ".md",
        ".txt",
        ".cmake",
        ".json",
        ".xml",
        ".ui",
        ".qrc",
    }

    def __init__(self, store: InventoryStore):
        self.store = store

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="freecad_command_list",
                title="List FreeCAD Commands",
                description="List statically scanned FreeCAD GUI commands with optional filtering.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "description": "Optional module/workbench name."},
                        "language": {
                            "type": "string",
                            "description": "Optional source language filter.",
                            "enum": ["python", "cpp"],
                        },
                        "query": {
                            "type": "string",
                            "description": "Case-insensitive substring search over command name, menu text, and tooltip.",
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        "offset": {"type": "integer", "minimum": 0},
                    },
                },
                handler=self.command_list,
            ),
            ToolDefinition(
                name="freecad_command_describe",
                title="Describe FreeCAD Command",
                description="Return source-backed metadata for a scanned FreeCAD command.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Exact command name."},
                        "module": {"type": "string", "description": "Optional module/workbench filter."},
                    },
                    "required": ["name"],
                },
                handler=self.command_describe,
            ),
            ToolDefinition(
                name="freecad_source_symbol_index",
                title="FreeCAD Source Symbol Index",
                description="Return a compact summary of scanned workbenches, command counts, and MCP tool families.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "description": "Optional module/workbench to summarize."}
                    },
                },
                handler=self.source_symbol_index,
            ),
            ToolDefinition(
                name="freecad_source_search",
                title="Search FreeCAD Source",
                description="Search the local FreeCAD checkout for text matches.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Literal text or regex pattern."},
                        "module": {"type": "string", "description": "Optional module under src/Mod."},
                        "glob": {
                            "type": "string",
                            "description": "Optional filename glob, for example '*.py' or 'Command*.cpp'.",
                        },
                        "regex": {"type": "boolean", "description": "Treat query as a regular expression."},
                        "case_sensitive": {"type": "boolean"},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
                        "max_files": {"type": "integer", "minimum": 1, "maximum": 100000, "description": "Maximum files to scan before truncating."},
                        "time_budget_sec": {"type": "integer", "minimum": 1, "maximum": 120, "description": "Wall-clock scan budget before truncating."},
                    },
                    "required": ["query"],
                },
                handler=self.source_search,
            ),
            ToolDefinition(
                name="freecad_source_open",
                title="Open FreeCAD Source",
                description="Read a bounded line range from a source file in the local FreeCAD checkout.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to the FreeCAD root, for example src/Mod/Part/Gui/Command.cpp.",
                        },
                        "start_line": {"type": "integer", "minimum": 1},
                        "line_count": {"type": "integer", "minimum": 1, "maximum": 400},
                    },
                    "required": ["path"],
                },
                handler=self.source_open,
            ),
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def command_list(self, args: JsonObject) -> JsonObject:
        module = optional_string(args, "module")
        language = optional_string(args, "language")
        query = optional_string(args, "query")
        limit = bounded_int(args, "limit", default=100, minimum=1, maximum=500)
        offset = bounded_int(args, "offset", default=0, minimum=0, maximum=1_000_000)

        records = self.store.commands
        if module:
            records = [record for record in records if record.get("module") == module]
        if language:
            if language not in {"python", "cpp"}:
                raise ToolInputError("language must be 'python' or 'cpp'")
            records = [record for record in records if record.get("language") == language]
        if query:
            needle = query.casefold()
            records = [
                record
                for record in records
                if needle in searchable_command_text(record).casefold()
            ]

        return {
            "scan": self.store.scan,
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "commands": records[offset : offset + limit],
        }

    def command_describe(self, args: JsonObject) -> JsonObject:
        name = required_string(args, "name")
        module = optional_string(args, "module")

        matches = [record for record in self.store.commands if record.get("name") == name]
        if module:
            matches = [record for record in matches if record.get("module") == module]
        if not matches:
            raise ToolInputError(f"command not found: {name}")

        return {"scan": self.store.scan, "matches": matches, "count": len(matches)}

    def source_symbol_index(self, args: JsonObject) -> JsonObject:
        module = optional_string(args, "module")
        commands = self.store.commands
        workbenches = self.store.workbenches
        if module:
            commands = [record for record in commands if record.get("module") == module]
            workbenches = [record for record in workbenches if record.get("name") == module]

        module_counts = Counter(str(record.get("module", "unknown")) for record in commands)
        language_counts = Counter(str(record.get("language", "unknown")) for record in commands)

        return {
            "scan": self.store.scan,
            "command_count": len(commands),
            "module_counts": dict(sorted(module_counts.items())),
            "language_counts": dict(sorted(language_counts.items())),
            "workbenches": workbenches,
            "proposed_tool_families": self.store.tool_families,
        }

    def source_search(self, args: JsonObject) -> JsonObject:
        query = required_string(args, "query")
        if len(query) > 500:
            raise ToolInputError("query exceeds 500 characters")
        module = optional_string(args, "module")
        glob_pattern = optional_string(args, "glob") or "*"
        use_regex = bool(args.get("regex", False))
        case_sensitive = bool(args.get("case_sensitive", False))
        max_results = bounded_int(args, "max_results", default=50, minimum=1, maximum=200)
        max_files = bounded_int(args, "max_files", default=5000, minimum=1, maximum=100000)
        time_budget_sec = bounded_int(args, "time_budget_sec", default=20, minimum=1, maximum=120)

        freecad_root = self.store.freecad_root
        search_root = self._source_search_root(freecad_root, module)
        if not search_root.exists():
            raise ToolInputError(f"source root not found: {search_root}")

        matcher = build_matcher(query, use_regex=use_regex, case_sensitive=case_sensitive)
        results: list[JsonObject] = []
        files_scanned = 0
        deadline = time.monotonic() + time_budget_sec
        truncated = False
        stop_reason: str | None = None

        # Walk lazily (os.walk does not materialize and sort the whole tree the way
        # sorted(rglob("*")) did) and stop on the first limit hit: max_results
        # matches, max_files scanned, or the wall-clock budget. Names are sorted per
        # directory for deterministic order without an upfront full traversal.
        for current_dir, dir_names, file_names in os.walk(search_root):
            dir_names.sort()
            for file_name in sorted(file_names):
                if time.monotonic() > deadline:
                    truncated = True
                    stop_reason = "time_budget"
                    break
                path = Path(current_dir) / file_name
                if path.suffix.lower() not in self.TEXT_SUFFIXES:
                    continue
                if not fnmatch.fnmatch(file_name, glob_pattern):
                    continue
                if files_scanned >= max_files:
                    truncated = True
                    stop_reason = "max_files"
                    break
                files_scanned += 1
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                except UnicodeDecodeError:
                    lines = path.read_text(encoding="latin-1").splitlines()
                for index, line in enumerate(lines, start=1):
                    if matcher(line):
                        results.append(
                            {
                                "path": relative_source_path(path, freecad_root),
                                "line": index,
                                "text": line.strip(),
                            }
                        )
                        if len(results) >= max_results:
                            truncated = True
                            stop_reason = "max_results"
                            break
                if stop_reason is not None:
                    break
            if truncated:
                break

        payload: JsonObject = {
            "query": query,
            "source_root": str(freecad_root),
            "files_scanned": files_scanned,
            "truncated": truncated,
            "matches": results,
        }
        if stop_reason is not None:
            payload["stop_reason"] = stop_reason
        return payload

    def source_open(self, args: JsonObject) -> JsonObject:
        source_path = required_string(args, "path")
        start_line = bounded_int(args, "start_line", default=1, minimum=1, maximum=1_000_000)
        line_count = bounded_int(args, "line_count", default=120, minimum=1, maximum=400)

        freecad_root = self.store.freecad_root
        target = safe_source_path(freecad_root, source_path)
        if not target.exists() or not target.is_file():
            raise ToolInputError(f"source file not found: {source_path}")

        try:
            file_lines = target.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            file_lines = target.read_text(encoding="latin-1").splitlines()

        end_line = min(start_line + line_count - 1, len(file_lines))
        selected = [
            {"line": line_number, "text": file_lines[line_number - 1]}
            for line_number in range(start_line, end_line + 1)
        ]
        return {
            "path": relative_source_path(target, freecad_root),
            "source_root": str(freecad_root),
            "start_line": start_line,
            "end_line": end_line,
            "total_lines": len(file_lines),
            "lines": selected,
        }

    def _source_search_root(self, freecad_root: Path, module: str | None) -> Path:
        if not module:
            return freecad_root / "src"
        if not re.fullmatch(r"[A-Za-z0-9_+-]+", module):
            raise ToolInputError("module contains unsupported characters")
        return freecad_root / "src" / "Mod" / module


def searchable_command_text(record: JsonObject) -> str:
    parts = [
        record.get("name"),
        record.get("module"),
        record.get("menu_text"),
        record.get("tooltip"),
        record.get("class_name"),
    ]
    return " ".join(str(part) for part in parts if part)


def build_matcher(
    query: str,
    *,
    use_regex: bool,
    case_sensitive: bool,
) -> Callable[[str], bool]:
    if not use_regex:
        needle = query if case_sensitive else query.casefold()

        def literal(line: str) -> bool:
            haystack = line if case_sensitive else line.casefold()
            return needle in haystack

        return literal

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as exc:
        raise ToolInputError(f"invalid regex: {exc}") from exc
    return lambda line: pattern.search(line) is not None


def safe_source_path(freecad_root: Path, source_path: str) -> Path:
    """Resolve a caller-supplied relative path against the FreeCAD root, safely.

    The security boundary is a single real-path containment check: the candidate
    is fully resolved (which dereferences every symlink in the chain) and must
    land inside the resolved root. Because resolution follows symlinks, a link
    that points outside the root is rejected here, so no separate, race-prone
    per-segment symlink pass is required. Parent-directory segments are rejected
    lexically before any filesystem access, so resolution can never be coaxed
    above the root through ``..`` traversal.
    """
    normalized = source_path.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        raise ToolInputError("path must be relative to the FreeCAD root")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ToolInputError("path must not contain parent-directory segments")

    root = freecad_root.resolve()
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise ToolInputError("path escapes the FreeCAD root")
    return target


def relative_source_path(path: Path, freecad_root: Path) -> str:
    return path.resolve().relative_to(freecad_root.resolve()).as_posix()
