$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $Root
try {
    $env:PYTHONPATH = Join-Path $Root "src"
    $env:FREECAD_MCP_WORKSPACE_ROOT = $Root
    & $Python -m compileall -q server.py scripts src tests
    & $Python -m unittest discover -s tests\unit -p "test_*.py"
    & $Python scripts\export_mcp_tool_schemas.py
    & $Python scripts\smoke_static_mcp.py
    & $Python scripts\smoke_freecad_runtime.py
    & $Python scripts\smoke_cad_tools.py
    & $Python scripts\smoke_fixture_documents.py
    & $Python scripts\smoke_persistent_worker.py
    if (Test-Path upstream\FreeCAD\src) {
        & $Python scripts\scan_freecad_tools.py --freecad-root upstream\FreeCAD --out-json docs\freecad_tool_inventory.json --out-md docs\freecad_tool_inventory.md
    }
}
finally {
    Pop-Location
}
