#!/usr/bin/env python3
"""Optional real FreeCADCmd runtime smoke test."""

from __future__ import annotations

import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_mcp.runtime_bridge import FreeCadCmdBridge, FreeCadDiscovery


def main() -> int:
    discovery = FreeCadDiscovery().discover()
    if discovery.executable is None:
        message = "real FreeCAD runtime smoke SKIPPED: FreeCADCmd not discovered"
        if os.environ.get("FREECAD_MCP_REQUIRE_RUNTIME") == "1":
            raise RuntimeError(message)
        print(message)
        return 0

    bridge = FreeCadCmdBridge(discovery.executable)
    probe = bridge.probe(timeout_sec=60)
    if not probe["execution"]["ok"] or not probe["freecad"]:
        raise RuntimeError(f"FreeCAD probe failed: {probe}")

    code = (
        "import FreeCAD as App\n"
        "doc = App.newDocument('McpRuntimeSmoke')\n"
        "box = doc.addObject('Part::Box', 'Box')\n"
        "doc.recompute()\n"
        "print('FREECAD_MCP_SMOKE_OBJECT=' + box.Name)\n"
        "App.closeDocument(doc.Name)\n"
    )
    execution = bridge.execute_python(code, timeout_sec=60)
    if not execution.ok or "FREECAD_MCP_SMOKE_OBJECT=Box" not in execution.stdout:
        raise RuntimeError(f"FreeCAD object smoke failed: {execution.to_dict()}")

    version = ".".join(str(part) for part in probe["freecad"]["version"][:3])
    print(f"real FreeCAD runtime smoke OK: {version} via {discovery.executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
