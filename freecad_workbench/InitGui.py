"""Compatibility entrypoint when FreeCAD is launched with ``-M freecad_workbench``."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


_THIS_FILE = Path(sys._getframe().f_code.co_filename).resolve()
runpy.run_path(str(_THIS_FILE.parent / "FreeCADMCP" / "InitGui.py"))
