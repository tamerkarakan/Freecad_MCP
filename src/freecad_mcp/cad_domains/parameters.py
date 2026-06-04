"""Spreadsheet and expression parameter CAD tools."""

from __future__ import annotations

from freecad_mcp.cad_tool_base import CadDomainToolService, CadToolSpec


class ParametersCadToolService(CadDomainToolService):
    domain = "parameters"

    def specs(self) -> list[CadToolSpec]:
        return [
            CadToolSpec(
                "freecad_spreadsheet_create",
                "Create FreeCAD Spreadsheet Parameters",
                (
                    "Create or update a Spreadsheet::Sheet with explicit cells or label/value/alias rows. "
                    "For physical CAD dimensions, pass a unit or default_unit such as 'mm'; with "
                    "require_units=true, bare numeric values are rejected so the agent must ask the user "
                    "which unit to use. Use unitless=true only for counts, ratios, or other dimensionless values."
                ),
                {
                    "document_path": {"type": "string"},
                    "document_name": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "default_unit": {
                        "type": "string",
                        "description": "Default FreeCAD unit for bare numeric value cells, for example 'mm', 'cm', 'in', or 'deg'.",
                    },
                    "require_units": {
                        "type": "boolean",
                        "description": "Reject bare numeric value cells unless a unit/default_unit is supplied or the row/cell sets unitless=true.",
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "row": {"type": "integer", "minimum": 1},
                                "label": {},
                                "value": {
                                    "description": "Cell value. Use {'quantity':'92 mm'} or value+unit for physical dimensions.",
                                },
                                "alias": {"type": "string"},
                                "unit": {"type": "string", "description": "Unit for this value cell when value is numeric."},
                                "display_unit": {"type": "string", "description": "Optional Spreadsheet display unit."},
                                "unitless": {
                                    "type": "boolean",
                                    "description": "Set true only for counts, ratios, or other dimensionless numeric values.",
                                },
                                "label_cell": {"type": "string"},
                                "value_cell": {"type": "string"},
                                "cell": {"type": "string"},
                            },
                        },
                        "description": "Rows with label, value, optional alias, and optional unit/unitless. Defaults to A/B columns.",
                    },
                    "cells": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cell": {"type": "string"},
                                "value": {
                                    "description": "Cell value. Use {'quantity':'92 mm'} or value+unit for physical dimensions.",
                                },
                                "alias": {"type": "string"},
                                "unit": {"type": "string", "description": "Unit for this value cell when value is numeric."},
                                "display_unit": {"type": "string", "description": "Optional Spreadsheet display unit."},
                                "unitless": {
                                    "type": "boolean",
                                    "description": "Set true only for counts, ratios, or other dimensionless numeric values.",
                                },
                            },
                        },
                        "description": "Explicit cell writes with cell, value, optional alias, and optional unit/unitless.",
                    },
                    "start_row": {"type": "integer", "minimum": 1},
                    "label_column": {"type": "string"},
                    "value_column": {"type": "string"},
                    "output_path": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                    "save": {"type": "boolean"},
                },
                [],
                "spreadsheet_create",
            ),
            CadToolSpec(
                "freecad_spreadsheet_get",
                "Get FreeCAD Spreadsheet Parameters",
                "Read selected Spreadsheet cells and aliases from a FreeCAD document.",
                {
                    "document_path": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "cells": {"type": "array", "items": {"type": "string"}},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "include_known_aliases": {"type": "boolean"},
                },
                ["document_path", "sheet_name"],
                "spreadsheet_get",
            ),
            CadToolSpec(
                "freecad_object_expression_set",
                "Set FreeCAD Object Expressions",
                "Set or clear expression bindings on an object property such as Length, Placement.Base.x, or Sketcher Constraints[0].",
                {
                    "document_path": {"type": "string"},
                    "object_name": {"type": "string"},
                    "expressions": {
                        "type": "object",
                        "description": "Map of object property path to expression string. Null or empty clears the expression.",
                    },
                    "output_path": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                    "save": {"type": "boolean"},
                },
                ["document_path", "object_name", "expressions"],
                "object_expression_set",
            ),
            CadToolSpec(
                "freecad_object_expression_list",
                "List FreeCAD Object Expressions",
                "List expression bindings for one or more document objects, including Sketcher dimension constraints.",
                {
                    "document_path": {"type": "string"},
                    "object_name": {"type": "string"},
                    "object_names": {"type": "array", "items": {"type": "string"}},
                },
                ["document_path"],
                "object_expression_list",
            ),
        ]
