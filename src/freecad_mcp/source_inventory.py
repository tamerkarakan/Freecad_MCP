#!/usr/bin/env python3
"""Scan a FreeCAD checkout for GUI commands and module surfaces.

The scanner is intentionally conservative: it records command registrations and
metadata that can be proven from source text, then writes a compact MCP planning
inventory. It does not import FreeCAD or execute upstream code.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PY_ADD_COMMAND_RE = re.compile(
    r"(?:FreeCADGui|Gui)\.addCommand\s*\(\s*"
    r"(?P<quote>['\"])(?P<name>[^'\"]+)(?P=quote)\s*,\s*"
    r"(?P<factory>[A-Za-z_][A-Za-z0-9_\.]*)?",
    re.MULTILINE,
)

PY_CLASS_RE = re.compile(
    r"^class\s+(?P<class>[A-Za-z_][A-Za-z0-9_]*)\b(?P<body>.*?)(?=^class\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)

PY_GET_RESOURCES_RE = re.compile(
    r"def\s+GetResources\s*\([^)]*\)\s*:(?P<body>.*?)(?=^\s*def\s+|^class\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)

CPP_CTOR_RE = re.compile(
    r"(?P<class>[A-Za-z_][A-Za-z0-9_]*)::(?P=class)\s*\([^)]*\)\s*"
    r"(?::(?P<init>[^{]*?Command\s*\(\s*\"(?P<name>[^\"]+)\"\s*\)[^{]*))?"
    r"\{(?P<body>.*?)\n\}",
    re.DOTALL,
)


@dataclass(frozen=True)
class SourceRef:
    path: str
    line: int


@dataclass
class CommandRecord:
    name: str
    module: str
    language: str
    source_kind: str
    source: SourceRef
    class_name: str | None = None
    menu_text: str | None = None
    tooltip: str | None = None
    group: str | None = None
    pixmap: str | None = None


class SourceInventoryScanner:
    """Build a static inventory from a FreeCAD source checkout."""

    def __init__(self, freecad_root: Path):
        self.freecad_root = freecad_root.resolve()

    def validate(self) -> None:
        if not (self.freecad_root / "src").exists():
            raise FileNotFoundError(f"FreeCAD source root not found: {self.freecad_root}")

    def build_payload(self) -> dict[str, object]:
        self.validate()
        commands = scan_commands(self.freecad_root)
        workbenches = workbench_records(self.freecad_root)
        remote = git_value(self.freecad_root, "config", "--get", "remote.origin.url") or "unknown"
        commit = git_value(self.freecad_root, "rev-parse", "HEAD") or "unknown"
        branch = git_value(self.freecad_root, "branch", "--show-current") or "unknown"

        return {
            "scan": {
                "remote": remote,
                "branch": branch,
                "commit": commit,
                "freecad_root": str(self.freecad_root),
            },
            "workbenches": workbenches,
            "proposed_tool_families": proposed_tool_families(commands),
            "commands": [asdict(command) for command in commands],
        }

    def write(self, out_json: Path, out_md: Path) -> dict[str, object]:
        payload = self.build_payload()
        write_json(out_json, payload)
        write_markdown(out_md, payload)
        return payload


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def module_for_path(path: Path, freecad_root: Path) -> str:
    parts = path.relative_to(freecad_root).parts
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "Mod":
        return parts[2]
    if len(parts) >= 2 and parts[0] == "src":
        return parts[1]
    return "unknown"


def strip_markup(value: str | None) -> str | None:
    if not value:
        return value
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip() or None


def extract_python_string(expr: str) -> str | None:
    string_parts = re.findall(r"['\"]([^'\"]+)['\"]", expr)
    if not string_parts:
        return None
    # QT_TRANSLATE_NOOP("context", "value") and translate("context", "value")
    # appear often; the useful user-facing text is normally the last literal.
    return strip_markup(string_parts[-1])


def extract_dict_value(block: str, key: str) -> str | None:
    match = re.search(
        rf"['\"]{re.escape(key)}['\"]\s*:\s*(?P<expr>.*?)(?:,\s*\n|\n\s*\}})",
        block,
        re.DOTALL,
    )
    if not match:
        return None
    return extract_python_string(match.group("expr"))


def python_resource_map(text: str) -> dict[str, dict[str, str | None]]:
    resources: dict[str, dict[str, str | None]] = {}
    for class_match in PY_CLASS_RE.finditer(text):
        class_name = class_match.group("class")
        body = class_match.group("body")
        res_match = PY_GET_RESOURCES_RE.search(body)
        if not res_match:
            continue
        res_body = res_match.group("body")
        resources[class_name] = {
            "menu_text": extract_dict_value(res_body, "MenuText"),
            "tooltip": extract_dict_value(res_body, "ToolTip"),
            "group": extract_dict_value(res_body, "Group"),
            "pixmap": extract_dict_value(res_body, "Pixmap"),
        }
    return resources


def scan_python_file(path: Path, freecad_root: Path) -> list[CommandRecord]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")

    resources = python_resource_map(text)
    records: list[CommandRecord] = []
    for match in PY_ADD_COMMAND_RE.finditer(text):
        factory_expr = match.group("factory")
        class_name = factory_expr.split(".")[-1] if factory_expr else None
        meta = resources.get(class_name or "", {})
        records.append(
            CommandRecord(
                name=match.group("name"),
                module=module_for_path(path, freecad_root),
                language="python",
                source_kind="FreeCADGui.addCommand",
                source=SourceRef(rel(path, freecad_root), line_for_offset(text, match.start())),
                class_name=class_name,
                menu_text=meta.get("menu_text"),
                tooltip=meta.get("tooltip"),
                group=meta.get("group"),
                pixmap=meta.get("pixmap"),
            )
        )
    return records


def extract_cpp_assignment(body: str, field: str) -> str | None:
    patterns = [
        rf"{re.escape(field)}\s*=\s*QT_TR_NOOP\s*\(\s*\"([^\"]+)\"\s*\)",
        rf"{re.escape(field)}\s*=\s*\"([^\"]+)\"",
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return strip_markup(match.group(1))
    return None


def scan_cpp_file(path: Path, freecad_root: Path) -> list[CommandRecord]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")

    records: list[CommandRecord] = []
    for match in CPP_CTOR_RE.finditer(text):
        name = match.group("name")
        if not name:
            continue
        body = match.group("body")
        class_name = match.group("class")
        records.append(
            CommandRecord(
                name=name,
                module=module_for_path(path, freecad_root),
                language="cpp",
                source_kind="Gui::Command constructor",
                source=SourceRef(rel(path, freecad_root), line_for_offset(text, match.start())),
                class_name=class_name,
                menu_text=extract_cpp_assignment(body, "sMenuText"),
                tooltip=extract_cpp_assignment(body, "sToolTipText"),
                group=extract_cpp_assignment(body, "sGroup"),
                pixmap=extract_cpp_assignment(body, "sPixmap"),
            )
        )
    return records


def iter_source_files(root: Path) -> Iterable[Path]:
    include_roots = [root / "src" / "Mod", root / "src" / "Gui", root / "src" / "App"]
    suffixes = {".py", ".cpp", ".cxx", ".cc"}
    for include_root in include_roots:
        if not include_root.exists():
            continue
        for path in include_root.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                yield path


def scan_commands(freecad_root: Path) -> list[CommandRecord]:
    records: list[CommandRecord] = []
    for path in iter_source_files(freecad_root):
        if path.suffix == ".py":
            records.extend(scan_python_file(path, freecad_root))
        elif path.suffix in {".cpp", ".cxx", ".cc"}:
            records.extend(scan_cpp_file(path, freecad_root))

    deduped: dict[tuple[str, str, str], CommandRecord] = {}
    for record in records:
        key = (record.name, record.source.path, record.language)
        deduped.setdefault(key, record)
    return sorted(deduped.values(), key=lambda r: (r.module.lower(), r.name.lower(), r.source.path))


def workbench_records(freecad_root: Path) -> list[dict[str, object]]:
    mod_root = freecad_root / "src" / "Mod"
    records = []
    if not mod_root.exists():
        return records
    for path in sorted(p for p in mod_root.iterdir() if p.is_dir()):
        records.append(
            {
                "name": path.name,
                "has_init_gui": (path / "InitGui.py").exists(),
                "has_gui_cpp": (path / "Gui").exists(),
                "python_files": len(list(path.rglob("*.py"))),
                "cpp_files": len(list(path.rglob("*.cpp"))),
            }
        )
    return records


def proposed_tool_families(commands: list[CommandRecord]) -> list[dict[str, object]]:
    counts = Counter(command.module for command in commands)
    return [
        {
            "family": "freecad.source",
            "priority": "P0",
            "tools": [
                "freecad_source_search",
                "freecad_source_open",
                "freecad_source_symbol_index",
            ],
            "evidence": "Needed to answer questions against the checked-out FreeCAD source.",
        },
        {
            "family": "freecad.session",
            "priority": "P0",
            "tools": [
                "freecad_session_start",
                "freecad_session_list",
                "freecad_session_status",
                "freecad_session_close",
                "freecad_worker_session_start",
                "freecad_worker_session_list",
                "freecad_worker_session_status",
                "freecad_worker_session_close",
                "freecad_worker_document_new",
                "freecad_worker_document_open",
                "freecad_worker_document_save",
                "freecad_worker_document_recompute",
                "freecad_worker_document_close",
                "freecad_worker_document_export",
                "freecad_worker_part_create_primitive",
                "freecad_worker_part_boolean",
                "freecad_worker_part_extrude",
                "freecad_worker_partdesign_body_create",
                "freecad_worker_partdesign_datum_plane_create",
                "freecad_worker_partdesign_pad",
                "freecad_worker_partdesign_pocket",
                "freecad_worker_partdesign_hole",
                "freecad_worker_partdesign_revolution",
                "freecad_worker_partdesign_groove",
                "freecad_worker_partdesign_additive_loft",
                "freecad_worker_part_revolve",
                "freecad_worker_part_check_geometry",
                "freecad_worker_sketch_create",
                "freecad_worker_sketch_add_geometry",
                "freecad_worker_sketch_add_constraint",
                "freecad_worker_sketch_add_profile",
                "freecad_worker_sketch_profile_create",
                "freecad_worker_sketch_profile_validate",
                "freecad_worker_sketch_edit_geometry",
                "freecad_worker_sketch_edit_constraints",
                "freecad_worker_sketch_transform",
                "freecad_worker_sketch_auto_constrain",
                "freecad_worker_sketch_validate",
                "freecad_worker_mesh_import",
                "freecad_worker_mesh_export",
                "freecad_worker_mesh_evaluate",
                "freecad_worker_mesh_repair",
                "freecad_worker_mesh_boolean",
                "freecad_worker_assembly_create",
                "freecad_worker_assembly_insert",
                "freecad_worker_assembly_create_joint",
                "freecad_worker_assembly_solve",
                "freecad_worker_assembly_bom",
                "freecad_worker_object_list",
                "freecad_worker_object_get",
                "freecad_worker_object_set_properties",
                "freecad_worker_object_rename_label",
                "freecad_worker_object_delete",
                "freecad_python_exec",
            ],
            "evidence": "Hybrid server needs a live FreeCAD Python bridge for stateful operations.",
        },
        {
            "family": "freecad.gui",
            "priority": "P0",
            "tools": [
                "freecad_gui_attach",
                "freecad_gui_list",
                "freecad_gui_detach",
                "freecad_gui_status",
                "freecad_gui_active_document_get",
                "freecad_gui_active_view_get",
                "freecad_gui_selection_get",
                "freecad_gui_preselection_get",
                "freecad_gui_selection_set",
                "freecad_gui_view_fit",
                "freecad_gui_primitive_create",
                "freecad_gui_object_label_set",
                "freecad_gui_sketch_state",
                "freecad_gui_sketch_enter",
                "freecad_gui_sketch_leave",
                "freecad_gui_partdesign_state",
                "freecad_gui_body_activate",
                "freecad_gui_feature_task_state",
            ],
            "evidence": "GUI attach mode is required for active view, preselection, picked points, selected edge/face state, user-visible labels, live Sketcher edit mode, PartDesign Body/Tip activation state, and task-panel observation.",
        },
        {
            "family": "freecad.document",
            "priority": "P0",
            "tools": [
                "freecad_document_new",
                "freecad_document_open",
                "freecad_document_save",
                "freecad_document_recompute",
                "freecad_document_export",
            ],
            "evidence": "Core App document lifecycle is the base for every workbench.",
        },
        {
            "family": "freecad.object",
            "priority": "P0",
            "tools": [
                "freecad_object_list",
                "freecad_object_get",
                "freecad_object_set_properties",
                "freecad_object_rename_label",
                "freecad_object_delete",
                "freecad_object_fit_view",
            ],
            "evidence": "MCP clients need deterministic object inspection and user-visible naming instead of blind command execution.",
        },
        {
            "family": "freecad.command",
            "priority": "P1",
            "tools": [
                "freecad_command_list",
                "freecad_command_describe",
                "freecad_command_run",
            ],
            "evidence": f"Source scan found {len(commands)} GUI command registrations across {len(counts)} modules.",
        },
        {
            "family": "freecad.part",
            "priority": "P1",
            "tools": [
                "freecad_part_create_primitive",
                "freecad_part_boolean",
                "freecad_part_extrude",
                "freecad_part_revolve",
                "freecad_part_fillet",
                "freecad_part_chamfer",
                "freecad_part_check_geometry",
            ],
            "evidence": f"Part module exposes {counts.get('Part', 0)} scanned commands.",
        },
        {
            "family": "freecad.partdesign",
            "priority": "P1",
            "tools": [
                "freecad_partdesign_body_create",
                "freecad_partdesign_datum_plane_create",
                "freecad_partdesign_pad",
                "freecad_partdesign_pocket",
                "freecad_partdesign_hole",
                "freecad_partdesign_revolution",
                "freecad_partdesign_groove",
                "freecad_partdesign_additive_loft",
            ],
            "evidence": f"PartDesign module exposes {counts.get('PartDesign', 0)} scanned commands and requires Body/datum/plane attachment for Pad/Pocket/Hole/Revolution/Groove/Loft workflows.",
        },
        {
            "family": "freecad.sketcher",
            "priority": "P1",
            "tools": [
                "freecad_sketch_create",
                "freecad_sketch_add_geometry",
                "freecad_sketch_add_constraint",
                "freecad_sketch_add_profile",
                "freecad_sketch_profile_create",
                "freecad_sketch_profile_validate",
                "freecad_curve_fit_analyze",
                "freecad_sketch_geometry_method_catalog",
                "freecad_sketch_edit_geometry",
                "freecad_sketch_edit_constraints",
                "freecad_sketch_transform",
                "freecad_sketch_auto_constrain",
                "freecad_sketch_validate",
            ],
            "evidence": f"Sketcher module exposes {counts.get('Sketcher', 0)} scanned commands.",
        },
        {
            "family": "freecad.mesh",
            "priority": "P2",
            "tools": [
                "freecad_mesh_import",
                "freecad_mesh_export",
                "freecad_mesh_evaluate",
                "freecad_mesh_repair",
                "freecad_mesh_boolean",
            ],
            "evidence": f"Mesh and MeshPart modules expose {counts.get('Mesh', 0) + counts.get('MeshPart', 0)} scanned commands.",
        },
        {
            "family": "freecad.assembly",
            "priority": "P2",
            "tools": [
                "freecad_assembly_create",
                "freecad_assembly_insert",
                "freecad_assembly_create_joint",
                "freecad_assembly_solve",
                "freecad_assembly_bom",
            ],
            "evidence": f"Assembly module exposes {counts.get('Assembly', 0)} scanned commands.",
        },
        {
            "family": "freecad.techdraw",
            "priority": "P2",
            "tools": [
                "freecad_techdraw_page_create",
                "freecad_techdraw_view_create",
                "freecad_techdraw_inspect",
                "freecad_techdraw_page_export",
            ],
            "evidence": f"TechDraw module exposes {counts.get('TechDraw', 0)} scanned commands and headless App APIs for DrawPage/DrawViewPart/DXF export.",
        },
        {
            "family": "freecad.import_export",
            "priority": "P2",
            "tools": [
                "freecad_import_file",
                "freecad_export_file",
                "freecad_supported_formats",
            ],
            "evidence": "Import/export commands are distributed across Part, Mesh, TechDraw, Spreadsheet, and Import modules.",
        },
        {
            "family": "freecad.cam",
            "priority": "P3",
            "tools": [
                "freecad_cam_path_create",
                "freecad_cam_path_inspect",
                "freecad_cam_path_export",
            ],
            "evidence": f"CAM module exposes {counts.get('CAM', 0)} scanned commands; first typed slice avoids job/toolbit/postprocessor mutation.",
        },
        {
            "family": "freecad.fem",
            "priority": "P3",
            "tools": [
                "freecad_fem_analysis_create",
                "freecad_fem_material_create",
                "freecad_fem_constraint_create",
                "freecad_fem_inspect",
            ],
            "evidence": f"FEM module exposes {counts.get('Fem', 0)} scanned commands; first typed slice avoids solver execution.",
        },
    ]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    scan = payload["scan"]
    workbenches = payload["workbenches"]
    command_records = payload["commands"]
    tool_families = payload["proposed_tool_families"]

    module_counts = Counter(record["module"] for record in command_records)
    source_counts = Counter(record["language"] for record in command_records)

    lines = [
        "# FreeCAD MCP Tool Inventory",
        "",
        f"- Upstream: `{scan['remote']}`",
        f"- Branch/commit: `{scan['branch']}` / `{scan['commit']}`",
        f"- Scanned commands: **{len(command_records)}**",
        f"- Workbench/module directories: **{len(workbenches)}**",
        f"- Source split: {', '.join(f'{k}={v}' for k, v in sorted(source_counts.items()))}",
        "",
        "## Proposed MCP Tool Families",
        "",
        "| Priority | Family | Initial tools | Source evidence |",
        "| --- | --- | --- | --- |",
    ]
    for family in tool_families:
        lines.append(
            "| {priority} | `{family}` | {tools} | {evidence} |".format(
                priority=family["priority"],
                family=family["family"],
                tools=", ".join(f"`{tool}`" for tool in family["tools"]),
                evidence=family["evidence"],
            )
        )

    lines.extend(
        [
            "",
            "## Workbench Command Counts",
            "",
            "| Module | Commands | Python files | C++ files | InitGui | Gui dir |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    workbench_by_name = {record["name"]: record for record in workbenches}
    for module, count in sorted(module_counts.items(), key=lambda item: (-item[1], item[0].lower())):
        wb = workbench_by_name.get(module, {})
        lines.append(
            "| {module} | {count} | {py} | {cpp} | {init_gui} | {gui} |".format(
                module=module,
                count=count,
                py=wb.get("python_files", ""),
                cpp=wb.get("cpp_files", ""),
                init_gui="yes" if wb.get("has_init_gui") else "no",
                gui="yes" if wb.get("has_gui_cpp") else "no",
            )
        )

    lines.extend(
        [
            "",
            "## Representative Commands",
            "",
            "| Module | Command | Menu text | Source |",
            "| --- | --- | --- | --- |",
        ]
    )
    per_module = defaultdict(list)
    for record in command_records:
        per_module[record["module"]].append(record)
    for module in sorted(per_module):
        for record in per_module[module][:8]:
            source = record["source"]
            menu = record.get("menu_text") or ""
            lines.append(
                f"| {module} | `{record['name']}` | {menu} | `{source['path']}:{source['line']}` |"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is a static source scan. Runtime-only commands and dynamically named commands may need a live FreeCAD bridge pass.",
            "- C++ command names are taken from `Gui::Command(\"...\")` constructors.",
            "- Python command names are taken from literal `FreeCADGui.addCommand(...)` / `Gui.addCommand(...)` calls.",
            "- For the MCP server, prefer typed document/object/Part/Sketch tools first, then expose `freecad_command_run` as a lower-level escape hatch.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freecad-root", default="upstream/FreeCAD", type=Path)
    parser.add_argument("--out-json", default="docs/freecad_tool_inventory.json", type=Path)
    parser.add_argument("--out-md", default="docs/freecad_tool_inventory.md", type=Path)
    args = parser.parse_args()

    scanner = SourceInventoryScanner(args.freecad_root)
    try:
        payload = scanner.write(args.out_json, args.out_md)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    scan = payload["scan"]
    commands = payload["commands"]
    workbenches = payload["workbenches"]
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")
    print(f"commands={len(commands)} workbenches={len(workbenches)} commit={scan['commit'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
