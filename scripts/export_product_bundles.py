from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "src"))

from freecad_mcp.mcp_stdio import build_server  # noqa: E402
from freecad_mcp.product_bundles import PRODUCT_BUNDLES, product_bundle_manifest  # noqa: E402


def _bundle_tools(profile: str) -> list[str]:
    service = build_server(ROOT, enabled_modules=profile)
    try:
        return [definition.name for definition in service.definitions()]
    finally:
        service.shutdown()


def build_manifest() -> dict[str, object]:
    manifest = product_bundle_manifest()
    tools_by_profile = {bundle.profile: _bundle_tools(bundle.profile) for bundle in PRODUCT_BUNDLES}
    for bundle in manifest["bundles"]:
        assert isinstance(bundle, dict)
        tool_names = tools_by_profile[str(bundle["profile"])]
        bundle["tool_count"] = len(tool_names)
        bundle["tool_names"] = tool_names
    return manifest


def build_markdown(manifest: dict[str, object]) -> str:
    bundles = manifest["bundles"]
    assert isinstance(bundles, list)
    lines = [
        "# Product Bundles",
        "",
        "Generated sellable bundle manifest for the current MCP tool surface.",
        "",
        "| Bundle | Profile | Kind | Tools | Modules | Position |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in bundles:
        assert isinstance(item, dict)
        modules = ", ".join(f"`{module}`" for module in item["modules"])
        lines.append(
            f"| {item['title']} | `{item['profile']}` | {item['kind']} | {item['tool_count']} | {modules} | {item['position']} |"
        )
    lines.extend(["", "## Bundle Details", ""])
    for item in bundles:
        assert isinstance(item, dict)
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Environment: `FREECAD_MCP_MODULES={item['profile']}`",
                f"- Audience: {item['audience']}",
                f"- Limits: {item['limits']}",
                f"- Unsafe Python exec included: `{str(item['includes_unsafe']).lower()}`",
                f"- Tool count: `{item['tool_count']}`",
            ]
        )
        if item.get("upgrade_to"):
            lines.append(f"- Upgrade path: `{item['upgrade_to']}`")
        lines.extend(["", "Tools:", ""])
        lines.extend(f"- `{name}`" for name in item["tool_names"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    manifest = build_manifest()
    json_path = ROOT / "docs" / "product_bundles.json"
    md_path = ROOT / "docs" / "PRODUCT_BUNDLES.md"
    json_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(manifest), encoding="utf-8")
    print(f"wrote {json_path.relative_to(ROOT)}")
    print(f"wrote {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
