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


IMAGE_LIKE_SOURCE_TYPES = {
    "image",
    "reference_image",
    "screenshot",
    "photo",
    "bitmap",
    "drawing",
    "diagram",
    "visual_reference",
    "silhouette",
    "traced_image",
}

MODELING_STRATEGY_CHOICES: tuple[JsonObject, ...] = (
    {
        "id": "visual_trace",
        "label_tr": "Gorsel benzerlik",
        "label_en": "Visual trace",
        "when_to_use": "Use when the user only needs a silhouette or visually similar shape.",
        "quality_gates": ["curve_intent_declared", "native_geometry_reported"],
    },
    {
        "id": "editable_parametric_sketch",
        "label_tr": "Olculeri degistirilebilir parametrik sketch",
        "label_en": "Editable parametric sketch",
        "when_to_use": "Use when dimensions must remain editable through Sketcher constraints and expressions.",
        "quality_gates": ["constraint_policy_semantic", "named_driving_dimensions", "fully_constrained"],
    },
    {
        "id": "manufacturing_partdesign_model",
        "label_tr": "Uretilebilir PartDesign model",
        "label_en": "Manufacturing PartDesign model",
        "when_to_use": "Use when the output should be a robust Body with Pad/Pocket/Hole features.",
        "quality_gates": ["body_tip_valid", "pad_or_pocket_ready_profiles", "geometry_check"],
    },
    {
        "id": "sketcher_constraint_rebuild",
        "label_tr": "Sketcher constraint mantigini yeniden kur",
        "label_en": "Sketcher constraint rebuild",
        "when_to_use": "Use when the visual result matters less than rebuilding constraint logic from primitives.",
        "quality_gates": ["primitive_ids", "constraint_graph", "solver_status"],
    },
    {
        "id": "rough_draft",
        "label_tr": "Kaba taslak",
        "label_en": "Rough draft",
        "when_to_use": "Use for fast exploration when parametric editability is explicitly not required yet.",
        "quality_gates": ["limitations_reported", "next_refinement_step"],
    },
    {
        "id": "semantic_reconstruction",
        "label_tr": "Anlamsal yeniden kurulum",
        "label_en": "Semantic reconstruction",
        "when_to_use": "Use when the agent should infer design intent instead of tracing pixels directly.",
        "quality_gates": ["assumptions_reported", "native_geometry_reported", "constraint_graph"],
    },
    {
        "id": "dimensioned_parametric",
        "label_tr": "Olculendirilmis parametrik model",
        "label_en": "Dimensioned parametric model",
        "when_to_use": "Use when important dimensions must be named and spreadsheet/expression driven.",
        "quality_gates": ["named_driving_dimensions", "expression_bindings", "fully_constrained"],
    },
    {
        "id": "organic_silhouette",
        "label_tr": "Organik siluet",
        "label_en": "Organic silhouette",
        "when_to_use": "Use when B-spline or arc-rich freeform visual shape is more important than mechanical constraints.",
        "quality_gates": ["curve_fit_report", "bspline_or_arc_intent"],
    },
    {
        "id": "manufacturing_profile",
        "label_tr": "Uretim profili",
        "label_en": "Manufacturing profile",
        "when_to_use": "Use when a single closed sketch profile must be pad/pocket ready.",
        "quality_gates": ["closed_profile", "pad_ready", "curve_intent_declared"],
    },
)

MODELING_STRATEGY_IDS = {str(choice["id"]) for choice in MODELING_STRATEGY_CHOICES}

VISUAL_ONLY_STRATEGIES = {"visual_trace", "organic_silhouette", "rough_draft"}
SKETCH_REBUILD_STRATEGIES = {
    "editable_parametric_sketch",
    "sketcher_constraint_rebuild",
    "dimensioned_parametric",
    "manufacturing_profile",
}

CURVE_INTENT_CHOICES: tuple[JsonObject, ...] = (
    {
        "id": "bspline",
        "label_tr": "B-spline",
        "when_to_use": "Use when the screenshot shows B-spline control points/poles or Sketcher B-spline controls.",
        "tooling": ["freecad_sketch_add_geometry type=bspline", "freecad_sketch_validate geometry type_id"],
    },
    {
        "id": "arc",
        "label_tr": "Dairesel yay",
        "when_to_use": "Use only when the user or native evidence confirms circular arc geometry.",
        "tooling": ["arc_3_point", "arc_start_end_radius", "arc_center_angles"],
    },
    {
        "id": "ellipse",
        "label_tr": "Elips / elips yayı",
        "when_to_use": "Use when the visible curve is an ellipse or elliptical arc, not a circular arc.",
        "tooling": ["ellipse", "ellipse_arc"],
    },
    {
        "id": "mixed",
        "label_tr": "Karisik egri aileleri",
        "when_to_use": "Use when the sketch contains more than one native curve family.",
        "tooling": ["segment-level expected_type", "freecad_sketch_profile_validate expected_geometry"],
    },
    {
        "id": "unknown",
        "label_tr": "Belirsiz",
        "when_to_use": "Use only as an intake result that forces a user question before mutation.",
        "tooling": ["ask_user", "freecad_curve_fit_analyze"],
    },
)

CURVE_INTENT_IDS = {str(choice["id"]) for choice in CURVE_INTENT_CHOICES}


def normalize_strategy_value(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInputError("modeling_strategy must be a string")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    return normalized or None


def normalize_source_type(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInputError("source_type must be a string")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    return normalized or None


def normalize_curve_intent(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInputError("native_curve_intent must be a string")
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    return normalized or None


def optional_bool(args: JsonObject, key: str, *, default: bool = False) -> bool:
    value = args.get(key, default)
    if not isinstance(value, bool):
        raise ToolInputError(f"{key} must be a boolean")
    return value


def modeling_strategy_choices() -> list[JsonObject]:
    return [dict(choice) for choice in MODELING_STRATEGY_CHOICES]


def curve_intent_choices() -> list[JsonObject]:
    return [dict(choice) for choice in CURVE_INTENT_CHOICES]


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
            ToolDefinition(
                name="freecad_modeling_strategy_intake",
                title="Modeling Strategy Intake",
                description=(
                    "For image, screenshot, drawing, or reference-driven FreeCAD work, decide whether the agent must "
                    "ask the user which modeling outcome is expected before mutating a sketch or PartDesign model. "
                    "Use this gate when visual similarity, editable parametric Sketcher constraints, manufacturing "
                    "PartDesign output, constraint reconstruction, or rough drafting could all be plausible."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "source_type": {
                            "type": "string",
                            "description": "Input source kind, for example reference_image, screenshot, drawing, text_prompt, or existing_model.",
                        },
                        "has_image": {
                            "type": "boolean",
                            "description": "Set true when the task depends on an image, screenshot, drawing, or visual reference.",
                        },
                        "modeling_strategy": {
                            "type": "string",
                            "enum": sorted(MODELING_STRATEGY_IDS),
                            "description": "Chosen output intent. Leave empty if the user has not chosen yet.",
                        },
                        "strategy_confirmed": {
                            "type": "boolean",
                            "description": "True only when the user explicitly chose the strategy or the prompt states it unambiguously.",
                        },
                        "visible_sketch_constraints": {
                            "type": "boolean",
                            "description": "True when the reference visibly contains Sketcher constraint glyphs, equal signs, constraint indexes, or solved-state cues.",
                        },
                        "visible_dimensions": {
                            "type": "boolean",
                            "description": "True when the reference visibly contains dimension labels, distances, radii, diameters, or angle values.",
                        },
                        "visible_construction_geometry": {
                            "type": "boolean",
                            "description": "True when the reference visibly contains guide/construction geometry such as blue Sketcher lines or construction circles.",
                        },
                        "curves_visible": {
                            "type": "boolean",
                            "description": "True when the reference contains curved geometry whose native FreeCAD family matters.",
                        },
                        "visible_bspline_control_points": {
                            "type": "boolean",
                            "description": "True when the screenshot shows B-spline poles/control points/handles; this should bias the agent toward native B-spline, not circular arcs.",
                        },
                        "native_curve_intent": {
                            "type": "string",
                            "enum": sorted(CURVE_INTENT_IDS),
                            "description": "Declared native curve family for visible curves. Use unknown to force a question.",
                        },
                        "curve_intent_confirmed": {
                            "type": "boolean",
                            "description": "True only when the user or native FreeCAD evidence confirms the curve family.",
                        },
                        "task": {
                            "type": "string",
                            "description": "Optional user task text for echoing the intake decision.",
                        },
                    },
                },
                handler=self.modeling_strategy_intake,
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

    def modeling_strategy_intake(self, args: JsonObject) -> JsonObject:
        source_type = normalize_source_type(args.get("source_type"))
        has_image = optional_bool(args, "has_image", default=False)
        modeling_strategy = normalize_strategy_value(args.get("modeling_strategy"))
        strategy_confirmed = optional_bool(args, "strategy_confirmed", default=False)
        visible_sketch_constraints = optional_bool(args, "visible_sketch_constraints", default=False)
        visible_dimensions = optional_bool(args, "visible_dimensions", default=False)
        visible_construction_geometry = optional_bool(args, "visible_construction_geometry", default=False)
        curves_visible = optional_bool(args, "curves_visible", default=False)
        visible_bspline_control_points = optional_bool(args, "visible_bspline_control_points", default=False)
        native_curve_intent = normalize_curve_intent(args.get("native_curve_intent"))
        curve_intent_confirmed = optional_bool(args, "curve_intent_confirmed", default=False)
        task = optional_string(args, "task")

        if modeling_strategy and modeling_strategy not in MODELING_STRATEGY_IDS:
            raise ToolInputError("unsupported modeling_strategy: " + modeling_strategy)
        if native_curve_intent and native_curve_intent not in CURVE_INTENT_IDS:
            raise ToolInputError("unsupported native_curve_intent: " + native_curve_intent)

        image_like = bool(has_image or (source_type in IMAGE_LIKE_SOURCE_TYPES))
        visible_sketch_evidence = bool(visible_sketch_constraints or visible_dimensions or visible_construction_geometry)
        curve_intent_missing = bool(
            curves_visible and (not native_curve_intent or native_curve_intent == "unknown" or not curve_intent_confirmed)
        )
        warnings = []
        blockers = []
        missing_strategy = image_like and not modeling_strategy
        if visible_sketch_evidence and not modeling_strategy:
            blockers.append("visible_sketch_evidence_requires_strategy")
        if visible_sketch_evidence and modeling_strategy in VISUAL_ONLY_STRATEGIES and not strategy_confirmed:
            blockers.append("visible_sketch_evidence_requires_user_confirmed_visual_override")
        if curve_intent_missing:
            blockers.append("visible_curves_require_native_curve_intent")
        if visible_bspline_control_points and native_curve_intent and native_curve_intent != "bspline":
            blockers.append("visible_bspline_controls_conflict_with_non_bspline_intent")
        if image_like and modeling_strategy and not strategy_confirmed:
            warnings.append(
                "strategy_not_confirmed: ask the user to confirm this modeling_strategy unless the task text already made it explicit"
            )
        if visible_sketch_evidence and modeling_strategy in VISUAL_ONLY_STRATEGIES and strategy_confirmed:
            warnings.append(
                "confirmed_visual_override_ignores_visible_sketch_constraints: report that dimensions/constraints/construction geometry will not be reconstructed"
            )
        if visible_bspline_control_points and not native_curve_intent:
            warnings.append("visible_bspline_controls_detected: ask whether the native curve family is B-spline before using arc tools")

        status = "needs_clarification" if missing_strategy or blockers else "ok"
        action = "ask_user" if missing_strategy or blockers else ("confirm_or_continue" if warnings else "continue")
        question_tr = (
            "Bu gorselden ne bekliyorsunuz: sadece gorsel benzerlik mi, FreeCAD'de olculeri "
            "degistirilebilir parametrik sketch mi, Sketcher constraint mantiginin yeniden kurulmasi mi, "
            "uretilebilir PartDesign model mi, yoksa kaba taslak mi?"
        )
        question_en = (
            "What should this reference become: visual similarity only, an editable parametric Sketcher model, "
            "a Sketcher constraint rebuild, a manufacturable PartDesign model, or a rough draft?"
        )
        curve_question_tr = (
            "Gorseldeki egrilerin native FreeCAD tipi nedir: B-spline mi, dairesel arc mi, elips mi, "
            "yoksa karisik/belirsiz mi? B-spline kontrol noktalari gorunuyorsa arc olarak yeniden kurmayayim."
        )
        curve_question_en = (
            "What is the native FreeCAD curve family: B-spline, circular arc, ellipse, mixed, or unknown? "
            "If B-spline control points are visible, do not rebuild them as arcs."
        )
        required_fields_for_mutation = ["source_type", "modeling_strategy", "strategy_confirmed"]
        if curves_visible or visible_bspline_control_points:
            required_fields_for_mutation.extend(["native_curve_intent", "curve_intent_confirmed"])

        return {
            "status": status,
            "action": action,
            "source_type": source_type,
            "has_image": has_image,
            "image_like": image_like,
            "visible_sketch_evidence": visible_sketch_evidence,
            "visible_sketch_constraints": visible_sketch_constraints,
            "visible_dimensions": visible_dimensions,
            "visible_construction_geometry": visible_construction_geometry,
            "curves_visible": curves_visible,
            "visible_bspline_control_points": visible_bspline_control_points,
            "modeling_strategy": modeling_strategy,
            "strategy_confirmed": strategy_confirmed,
            "native_curve_intent": native_curve_intent,
            "curve_intent_confirmed": curve_intent_confirmed,
            "task": task,
            "question_tr": question_tr,
            "question_en": question_en,
            "curve_question_tr": curve_question_tr,
            "curve_question_en": curve_question_en,
            "choices": modeling_strategy_choices(),
            "recommended_strategies": (
                ["sketcher_constraint_rebuild", "editable_parametric_sketch"]
                if visible_sketch_evidence
                else ["visual_trace", "editable_parametric_sketch", "manufacturing_partdesign_model"]
            ),
            "curve_choices": curve_intent_choices(),
            "required_fields_for_mutation": required_fields_for_mutation,
            "blockers": blockers,
            "warnings": warnings,
            "message": (
                "Ask the user for the desired modeling outcome before mutating the FreeCAD document."
                if missing_strategy or blockers
                else "Carry the declared modeling and curve strategy into Sketcher/PartDesign tools."
            ),
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
