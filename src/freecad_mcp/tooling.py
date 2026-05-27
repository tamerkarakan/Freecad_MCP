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
