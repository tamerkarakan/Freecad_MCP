"""Shared tool contracts and argument validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


JsonObject = dict[str, Any]


class ToolInputError(ValueError):
    """Raised when a tool receives invalid user arguments."""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    title: str
    description: str
    input_schema: JsonObject
    handler: Callable[[JsonObject], JsonObject]

    def to_mcp(self) -> JsonObject:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


def required_string(args: JsonObject, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} is required")
    return value


def optional_string(args: JsonObject, key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInputError(f"{key} must be a string")
    return value or None


def bounded_int(args: JsonObject, key: str, *, default: int, minimum: int, maximum: int) -> int:
    value = args.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ToolInputError(f"{key} must be an integer")
    if value < minimum or value > maximum:
        raise ToolInputError(f"{key} must be between {minimum} and {maximum}")
    return value


def load_runtime_script(name: str) -> str:
    """Load an embedded FreeCAD runtime script shipped under ``runtime_scripts/``.

    These scripts execute inside a FreeCADCmd subprocess (they are never imported),
    so they live as standalone ``.py`` files for editor highlighting, per-line
    debugging, and reviewable diffs instead of multi-thousand-line in-module string
    literals. Reading uses universal newlines, so a script keeps the same content
    regardless of how line endings are stored on disk.
    """
    from pathlib import Path

    script_path = Path(__file__).resolve().parent / "runtime_scripts" / name
    try:
        return script_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"embedded FreeCAD runtime script {name!r} is missing or unreadable at "
            f"{script_path}; ensure the runtime_scripts/ directory ships with the package "
            f"(it must be committed alongside the modules that load it): {exc}"
        ) from exc
