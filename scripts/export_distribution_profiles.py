from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freecad_mcp.distribution_profiles import DISTRIBUTION_PROFILES, distribution_manifest  # noqa: E402
from freecad_mcp.mcp_stdio import build_server  # noqa: E402


def _tool_names(profile: str) -> list[str]:
    service = build_server(ROOT, enabled_modules=profile)
    try:
        return [definition.name for definition in service.definitions()]
    finally:
        service.shutdown()


def build_manifest() -> dict[str, object]:
    manifest = distribution_manifest()
    tools_by_profile = {
        profile.bundle.profile: _tool_names(profile.bundle.profile)
        for profile in DISTRIBUTION_PROFILES
    }
    for profile in manifest["profiles"]:
        assert isinstance(profile, dict)
        tool_names = tools_by_profile[str(profile["profile"])]
        profile["tool_count"] = len(tool_names)
        profile["tool_names"] = tool_names
    return manifest


def build_markdown(manifest: dict[str, object]) -> str:
    project = manifest["project"]
    profiles = manifest["profiles"]
    assert isinstance(project, dict)
    assert isinstance(profiles, list)
    lines = [
        "# Distribution Profiles",
        "",
        "Generated packaging skeleton for the sellable FreeCAD MCP bundles.",
        "",
        f"- Python distribution: `{project['name']}`",
        f"- Python package: `{project['python_package']}`",
        f"- Console entrypoint: `{project['entrypoint']}`",
        f"- Module selector env: `{project['module_env']}`",
        f"- Repo/resource root env: `{project['repo_root_env']}`",
        "",
        "Verification: `scripts/smoke_python_package.py` builds wheel and sdist artifacts, installs the wheel into a temporary venv, starts the installed `freecad-hybrid-mcp` entrypoint outside the repo working directory, and checks MCP initialize/tool calls with `FREECAD_MCP_MODULES=free`.",
        "",
        "| Profile | Channel | Tools | Artifacts | Components |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in profiles:
        assert isinstance(item, dict)
        artifacts = ", ".join(f"`{artifact}`" for artifact in item["artifacts"])
        components = ", ".join(f"`{component}`" for component in item["components"])
        lines.append(
            f"| `{item['key']}` | {item['channel']} | {item['tool_count']} | {artifacts} | {components} |"
        )
    lines.extend(["", "## Generated MCP Configs", ""])
    lines.append("Per-profile MCP JSON examples are generated under `packaging/profiles/`.")
    lines.append("")
    for item in profiles:
        assert isinstance(item, dict)
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Profile: `{item['profile']}`",
                f"- Entrypoint command: `{item['entrypoint']}`",
                f"- Notes: {item['notes']}",
                f"- Config: `packaging/profiles/{item['key']}.mcp.json`",
            ]
        )
        workbench_artifact = item.get("workbench_artifact")
        if isinstance(workbench_artifact, dict):
            lines.append(f"- Workbench artifact: `{workbench_artifact['zip_name']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_packaging_readme(manifest: dict[str, object]) -> str:
    profiles = manifest["profiles"]
    assert isinstance(profiles, list)
    lines = [
        "# Packaging Profiles",
        "",
        "This directory contains generated MCP client config skeletons for each product profile.",
        "Regenerate them with:",
        "",
        "```powershell",
        "python scripts\\export_distribution_profiles.py",
        "```",
        "",
        "Each config assumes the installed console entrypoint `freecad-hybrid-mcp` is on PATH.",
        "Replace placeholder environment values before handing a profile to a user.",
        "GUI-capable profiles also consume the generated local Workbench module zip from `packaging/workbench/` or a path produced by `scripts\\build_workbench_addon.py --zip-out`.",
        "",
        "| File | Profile |",
        "| --- | --- |",
    ]
    for item in profiles:
        assert isinstance(item, dict)
        lines.append(f"| `profiles/{item['key']}.mcp.json` | `{item['profile']}` |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    manifest = build_manifest()
    docs_json = ROOT / "docs" / "distribution_profiles.json"
    docs_md = ROOT / "docs" / "DISTRIBUTION_PROFILES.md"
    packaging_dir = ROOT / "packaging"
    profiles_dir = packaging_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    expected_config_names = {
        f"{profile['key']}.mcp.json"
        for profile in manifest["profiles"]
        if isinstance(profile, dict)
    }
    for existing_config in profiles_dir.glob("*.mcp.json"):
        if existing_config.name not in expected_config_names:
            existing_config.unlink()

    docs_json.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    docs_md.write_text(build_markdown(manifest), encoding="utf-8")
    (packaging_dir / "README.md").write_text(build_packaging_readme(manifest), encoding="utf-8")

    for profile in manifest["profiles"]:
        assert isinstance(profile, dict)
        config_path = profiles_dir / f"{profile['key']}.mcp.json"
        config_path.write_text(json.dumps(profile["mcp_config"], indent=2) + "\n", encoding="utf-8")

    print(f"wrote {docs_json.relative_to(ROOT)}")
    print(f"wrote {docs_md.relative_to(ROOT)}")
    print(f"wrote {packaging_dir.relative_to(ROOT)}\\README.md")
    print(f"wrote {profiles_dir.relative_to(ROOT)}\\*.mcp.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
