$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $Root
try {
    $env:PYTHONPATH = Join-Path $Root "src"
    & $Python -m py_compile src\freecad_mcp\source_inventory.py scripts\scan_freecad_tools.py
    & $Python -m unittest discover -s tests\unit -p "test_*.py"
    if (Test-Path upstream\FreeCAD\src) {
        & $Python scripts\scan_freecad_tools.py --freecad-root upstream\FreeCAD --out-json docs\freecad_tool_inventory.json --out-md docs\freecad_tool_inventory.md
    }
}
finally {
    Pop-Location
}
