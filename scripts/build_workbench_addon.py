from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freecad_mcp.workbench_artifact import ZIP_NAME, workbench_artifact_manifest  # noqa: E402


def build_markdown(manifest: dict[str, object]) -> str:
    files = manifest["files"]
    assert isinstance(files, list)
    lines = [
        "# Workbench Artifact",
        "",
        "Generated local FreeCAD Workbench module artifact for GUI bridge distribution.",
        "",
        f"- Artifact: `{manifest['artifact_key']}`",
        f"- Module name: `{manifest['module_name']}`",
        f"- Zip name: `{manifest['zip_name']}`",
        f"- Official Addon Manager package: `{str(manifest['official_addon_manager_package']).lower()}`",
        f"- Consuming profiles: {', '.join(f'`{profile}`' for profile in manifest['consuming_profiles'])}",
        "",
        "## Files",
        "",
        "| Source | Zip Target | Role |",
        "| --- | --- | --- |",
    ]
    for file_spec in files:
        assert isinstance(file_spec, dict)
        lines.append(f"| `{file_spec['source']}` | `{file_spec['target']}` | `{file_spec['role']}` |")
    lines.extend(
        [
            "",
            "## Install Shape",
            "",
            "Extract the zip so `FreeCADMCP/InitGui.py` is directly under a FreeCAD module search path, such as the user `Mod` directory or a path passed with `FreeCAD.exe -M`.",
            "",
            "The zip embeds `freecad_gui_bridge_server.py` beside `InitGui.py`, so the Workbench can host the GUI bridge without depending on the repo `scripts/` path.",
            "",
            "This is a local module zip, not a signed FreeCAD Addon Manager package yet.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_packaging_readme(manifest: dict[str, object]) -> str:
    return (
        "# Workbench Artifact\n\n"
        "Build the local FreeCAD Workbench module zip with:\n\n"
        "```powershell\n"
        "python scripts\\build_workbench_addon.py --zip-out dist\\freecad-mcp-workbench.zip\n"
        "```\n\n"
        "The resulting zip should be extracted so `FreeCADMCP/InitGui.py` sits under a FreeCAD module path. "
        "It embeds the GUI bridge script beside `InitGui.py`.\n\n"
        f"Expected zip name: `{manifest['zip_name']}`\n"
    )


def write_docs(manifest: dict[str, object]) -> None:
    docs_json = ROOT / "docs" / "workbench_artifact.json"
    docs_md = ROOT / "docs" / "WORKBENCH_ARTIFACT.md"
    packaging_dir = ROOT / "packaging" / "workbench"
    packaging_dir.mkdir(parents=True, exist_ok=True)
    docs_json.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    docs_md.write_text(build_markdown(manifest), encoding="utf-8")
    (packaging_dir / "README.md").write_text(build_packaging_readme(manifest), encoding="utf-8")
    print(f"wrote {docs_json.relative_to(ROOT)}")
    print(f"wrote {docs_md.relative_to(ROOT)}")
    print(f"wrote {(packaging_dir / 'README.md').relative_to(ROOT)}")


def build_zip(manifest: dict[str, object], zip_out: Path) -> None:
    zip_out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_spec in manifest["files"]:
            assert isinstance(file_spec, dict)
            source = ROOT / str(file_spec["source"])
            archive.write(source, str(file_spec["target"]))
        archive.writestr("FreeCADMCP/workbench_artifact.json", json.dumps(manifest, indent=2) + "\n")
        archive.writestr("FreeCADMCP/README.md", build_packaging_readme(manifest))
    print(f"wrote {zip_out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the FreeCAD MCP Workbench module artifact.")
    parser.add_argument("--zip-out", type=Path, default=None, help=f"Optional zip output path, e.g. dist/{ZIP_NAME}.")
    args = parser.parse_args()

    manifest = workbench_artifact_manifest(ROOT)
    write_docs(manifest)
    if args.zip_out is not None:
        build_zip(manifest, args.zip_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
