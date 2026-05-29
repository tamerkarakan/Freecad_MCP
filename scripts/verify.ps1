$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

function Invoke-PythonChecked {
    param(
        [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE`: $Python $($Arguments -join ' ')"
    }
}

Push-Location $Root
try {
    $env:PYTHONPATH = Join-Path $Root "src"
    $env:FREECAD_MCP_WORKSPACE_ROOT = $Root
    Invoke-PythonChecked @("-m", "compileall", "-q", "server.py", "scripts", "src", "tests", "freecad_workbench")
    Invoke-PythonChecked @("-m", "unittest", "discover", "-s", "tests\unit", "-p", "test_*.py")
    Invoke-PythonChecked @("scripts\export_product_bundles.py")
    Invoke-PythonChecked @("scripts\export_distribution_profiles.py")
    Invoke-PythonChecked @("scripts\build_workbench_addon.py")
    Invoke-PythonChecked @("scripts\smoke_distribution_profiles.py")
    Invoke-PythonChecked @("scripts\smoke_workbench_artifact.py")
    Invoke-PythonChecked @("scripts\smoke_python_package.py")
    Invoke-PythonChecked @("scripts\export_mcp_tool_schemas.py")
    Invoke-PythonChecked @("scripts\smoke_static_mcp.py")
    Invoke-PythonChecked @("scripts\smoke_freecad_runtime.py")
    Invoke-PythonChecked @("scripts\smoke_cad_tools.py")
    Invoke-PythonChecked @("scripts\smoke_fixture_documents.py")
    Invoke-PythonChecked @("scripts\smoke_persistent_worker.py")
    if ($env:FREECAD_MCP_GUI_SMOKE -eq "1") {
        Invoke-PythonChecked @("scripts\smoke_gui_attach.py")
    }
    if (Test-Path upstream\FreeCAD\src) {
        Invoke-PythonChecked @("scripts\scan_freecad_tools.py", "--freecad-root", "upstream\FreeCAD", "--out-json", "docs\freecad_tool_inventory.json", "--out-md", "docs\freecad_tool_inventory.md")
    }
}
finally {
    Pop-Location
}
