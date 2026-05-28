"""Typed CAD tools backed by process-per-call FreeCADCmd."""

from __future__ import annotations

import json
import base64
import os
from pathlib import Path

from freecad_mcp.runtime_bridge import (
    FREECAD_JSON_PREFIX,
    FreeCadCmdBridge,
    FreeCadDiscovery,
    parse_prefixed_json,
)
from freecad_mcp.tooling import (
    JsonObject,
    ToolDefinition,
    ToolInputError,
    bounded_int,
    load_runtime_script,
    optional_string,
    required_string,
)


COMMON_RUNTIME_PROPS: JsonObject = {
    "executable": {"type": "string", "description": "Optional explicit FreeCADCmd path."},
    "freecad_home": {"type": "string", "description": "Optional portable FreeCAD directory."},
    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 180},
    "compact_execution": {
        "type": "boolean",
        "description": "Return compact execution metadata without stdout/stderr/argv text.",
    },
    "allow_external_paths": {
        "type": "boolean",
        "description": "Allow absolute output paths outside FREECAD_MCP_WORKSPACE_ROOT/server workspace.",
    },
}


CAD_ACTION_SCRIPT = load_runtime_script("cad_action.py")


class CadToolService:
    """Typed document/object/geometry tools."""

    def __init__(self, discovery: FreeCadDiscovery | None = None):
        self.discovery = discovery or FreeCadDiscovery()

    def definitions(self) -> list[ToolDefinition]:
        return [
            self._tool("freecad_document_new", "Create FreeCAD Document", "Create a new FreeCAD document.", {"document_name": {"type": "string"}, "label": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "document_new"),
            self._tool("freecad_document_open", "Open FreeCAD Document", "Open a FreeCAD document and return a summary.", {"document_path": {"type": "string"}}, ["document_path"], "document_open"),
            self._tool("freecad_document_save", "Save FreeCAD Document", "Open and save a FreeCAD document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["document_path"], "document_save"),
            self._tool("freecad_document_recompute", "Recompute FreeCAD Document", "Open/recompute a document and optionally save it.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "document_recompute"),
            self._tool("freecad_document_export", "Export FreeCAD Document", "Export selected or all document objects.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "document_export"),
            self._tool("freecad_object_list", "List FreeCAD Objects", "List document objects.", {"document_path": {"type": "string"}}, ["document_path"], "object_list"),
            self._tool("freecad_object_get", "Get FreeCAD Object", "Inspect one document object.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "include_properties": {"type": "boolean"}}, ["document_path", "object_name"], "object_get"),
            self._tool("freecad_object_set_properties", "Set FreeCAD Object Properties", "Set simple object properties and save optionally.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "properties": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_name", "properties"], "object_set_properties"),
            self._tool("freecad_object_delete", "Delete FreeCAD Objects", "Delete object(s) by name/label.", {"document_path": {"type": "string"}, "object_name": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "object_delete"),
            self._tool("freecad_part_create_primitive", "Create Part Primitive", "Create a Part primitive.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "primitive": {"type": "string", "enum": ["box", "cylinder", "sphere", "cone", "torus"]}, "object_name": {"type": "string"}, "properties": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "part_create_primitive"),
            self._tool("freecad_part_boolean", "Part Boolean", "Fuse/cut/common Part shapes.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "operation": {"type": "string", "enum": ["fuse", "cut", "common"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_names"], "part_boolean"),
            self._tool("freecad_part_extrude", "Part Extrude", "Extrude a source shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "vector": {"type": "array", "items": {"type": "number"}}, "extrude_mode": {"type": "string", "enum": ["auto", "shape", "feature"]}, "solid": {"type": "boolean"}, "symmetric": {"type": "boolean"}, "length_fwd": {"type": "number"}, "length_rev": {"type": "number"}, "taper_angle": {"type": "number", "description": "Forward taper angle in degrees."}, "taper_angle_rev": {"type": "number", "description": "Reverse taper angle in degrees."}, "reversed": {"type": "boolean"}, "dir_mode": {"type": "string", "enum": ["Custom", "Normal"]}, "face_maker_mode": {"type": "string", "enum": ["Simple", "Cheese", "Extrusion", "Bullseye"]}, "inner_wire_taper": {"type": "string", "enum": ["Inverted", "SameAsOuter"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object"], "part_extrude"),
            self._tool("freecad_partdesign_body_create", "Create PartDesign Body", "Create or reuse a PartDesign Body with origin planes.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "body_name": {"type": "string"}, "create_body_if_missing": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, [], "partdesign_body_create"),
            self._tool("freecad_partdesign_pad", "Create PartDesign Pad", "Create a PartDesign Pad from a Sketcher profile inside a Body, attaching the sketch to an origin plane when needed.", {"document_path": {"type": "string"}, "body_name": {"type": "string"}, "sketch_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "pad_name": {"type": "string"}, "result_name": {"type": "string"}, "length": {"type": "number"}, "length2": {"type": "number"}, "midplane": {"type": "boolean"}, "reversed": {"type": "boolean"}, "require_solid": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "sketch_name"], "partdesign_pad"),
            self._tool("freecad_part_revolve", "Part Revolve", "Revolve a source shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "base": {"type": "array", "items": {"type": "number"}}, "axis": {"type": "array", "items": {"type": "number"}}, "angle": {"type": "number"}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object"], "part_revolve"),
            self._tool("freecad_part_fillet", "Part Fillet", "Create a filleted copy of a shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "radius": {"type": "number"}, "edge_indices": {"type": "array", "items": {"type": "integer"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object", "radius"], "part_fillet"),
            self._tool("freecad_part_chamfer", "Part Chamfer", "Create a chamfered copy of a shape.", {"document_path": {"type": "string"}, "source_object": {"type": "string"}, "distance": {"type": "number"}, "edge_indices": {"type": "array", "items": {"type": "integer"}}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "source_object", "distance"], "part_chamfer"),
            self._tool("freecad_part_check_geometry", "Check Part Geometry", "Run shape validity checks.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "run_bop_check": {"type": "boolean"}}, ["document_path"], "part_check_geometry"),
            self._tool("freecad_sketch_create", "Create Sketch", "Create a Sketcher object, optionally inside a PartDesign Body attached to XY/XZ/YZ origin plane.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "body_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "sketch_create"),
            self._tool(
                "freecad_sketch_add_geometry",
                "Add Sketch Geometry",
                "Add point, line, circle, arc, ellipse, conic arc, B-spline, or polyline geometry to a sketch.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "geometry": {"type": "array", "items": {"type": "object"}}, "connect_sequence": {"type": "boolean", "description": "Add Coincident constraints between adjacent endpoint-capable geometry in the submitted order."}, "close_sequence": {"type": "boolean", "description": "Also add a Coincident constraint from the last endpoint-capable geometry back to the first."}, "require_closed": {"type": "boolean", "description": "Fail before saving if the resulting sequence still has open vertices."}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "geometry"],
                "sketch_add_geometry",
            ),
            self._tool(
                "freecad_sketch_add_constraint",
                "Add Sketch Constraint",
                "Add raw or named Sketcher constraints with optional metadata such as datum, driving, active, visibility, and label placement.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "constraints"],
                "sketch_add_constraint",
            ),
            self._tool(
                "freecad_sketch_add_profile",
                "Add Sketch Profile",
                "Add common closed/open Sketcher profiles such as rectangle variants, named/arbitrary regular polygons, circle, polyline, and straight/oriented/arc slots.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "profile": {"type": "object"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "profile"],
                "sketch_add_profile",
            ),
            self._tool(
                "freecad_sketch_profile_create",
                "Create Sketch Profile",
                "Create loop-based pad-ready Sketcher profiles from ordered line/arc/B-spline segments with endpoint continuity and curve-preservation guards, optionally attached inside a PartDesign Body.",
                {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "sketch_name": {"type": "string"}, "body_name": {"type": "string"}, "attachment_plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]}, "create_body_if_missing": {"type": "boolean"}, "loops": {"type": "array", "items": {"type": "object"}}, "replace_existing": {"type": "boolean"}, "lock_mode": {"type": "string", "enum": ["none", "block"]}, "endpoint_tolerance": {"type": "number"}, "required_segment_types": {"type": "array", "items": {"type": "string"}}, "required_curve_types": {"type": "array", "items": {"type": "string"}}, "allowed_segment_types": {"type": "array", "items": {"type": "string"}}, "minimum_curve_segments": {"type": "integer"}, "forbid_polyline_fallback": {"type": "boolean"}, "forbid_all_line_loops": {"type": "boolean"}, "require_valid": {"type": "boolean"}, "require_pad_ready": {"type": "boolean"}, "require_fully_constrained": {"type": "boolean"}, "forbid_isolated_points": {"type": "boolean"}, "forbid_branch_points": {"type": "boolean"}, "forbid_micro_offsets": {"type": "boolean"}, "micro_offset_tolerance": {"type": "number"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["loops"],
                "sketch_profile_create",
            ),
            self._tool(
                "freecad_sketch_profile_validate",
                "Validate Sketch Profile",
                "Validate whether a Sketcher object is pad-ready and whether its native geometry types match declared curve intent.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "require_pad_ready": {"type": "boolean"}, "require_fully_constrained": {"type": "boolean"}, "forbid_isolated_points": {"type": "boolean"}, "forbid_branch_points": {"type": "boolean"}, "forbid_micro_offsets": {"type": "boolean"}, "micro_offset_tolerance": {"type": "number"}, "endpoint_key_precision": {"type": "integer"}, "include_construction": {"type": "boolean"}, "required_segment_types": {"type": "array", "items": {"type": "string"}}, "required_curve_types": {"type": "array", "items": {"type": "string"}}, "minimum_curve_segments": {"type": "integer"}, "forbid_all_line_loops": {"type": "boolean"}, "forbid_polyline_fallback": {"type": "boolean"}, "forbid_intent_mismatch": {"type": "boolean"}, "expected_geometry": {"type": "array", "items": {"type": "object"}}},
                ["document_path", "sketch_name"],
                "sketch_profile_validate",
            ),
            self._tool(
                "freecad_curve_fit_analyze",
                "Analyze Curve Fit",
                "Compare line and circular-arc fit errors for traced sketch points and recommend line, arc, or B-spline without mutating a document.",
                {"points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}}, "tolerance": {"type": "number"}, "fit_tolerance": {"type": "number"}},
                ["points"],
                "curve_fit_analyze",
            ),
            self._tool(
                "freecad_sketch_geometry_method_catalog",
                "Sketch Geometry Method Catalog",
                "Return the supported typed creation methods for Sketcher geometry, profiles, transform-generated geometry, and analysis tools.",
                {},
                [],
                "sketch_geometry_method_catalog",
            ),
            self._tool(
                "freecad_sketch_edit_geometry",
                "Edit Sketch Geometry",
                "Delete, move, toggle construction state, add external geometry, carbon-copy, and maintain internal/degenerated Sketcher geometry.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_edit_geometry",
            ),
            self._tool(
                "freecad_sketch_edit_constraints",
                "Edit Sketch Constraints",
                "Delete, rename, set datum/driving/active/visibility/virtual-space state, validate, and auto-remove redundant Sketcher constraints.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_edit_constraints",
            ),
            self._tool(
                "freecad_sketch_transform",
                "Transform Sketch Geometry",
                "Run headless Sketcher transform operations such as fillet, trim, extend, split, join, copy, move, symmetry, rectangular array, and B-spline edits.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name", "operations"],
                "sketch_transform",
            ),
            self._tool(
                "freecad_sketch_auto_constrain",
                "Auto Constrain Sketch",
                "Detect/apply missing Sketcher coincident, vertical/horizontal, equality constraints, run autoconstraint, and validate/clean constraints.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_auto_constrain",
            ),
            self._tool(
                "freecad_sketch_validate",
                "Validate Sketch",
                "Solve and summarize sketch geometry, constraints, solver diagnostics, missing constraints, open vertices, and per-constraint errors.",
                {"document_path": {"type": "string"}, "sketch_name": {"type": "string"}, "solve": {"type": "boolean"}, "detect_missing": {"type": "boolean"}, "include_constraint_errors": {"type": "boolean"}, "precision": {"type": "number"}, "angle_precision": {"type": "number"}, "include_construction": {"type": "boolean"}},
                ["document_path", "sketch_name"],
                "sketch_validate",
            ),
            self._tool("freecad_import_file", "Import File", "Import a CAD/mesh file into a document.", {"input_path": {"type": "string"}, "document_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["input_path"], "import_file"),
            self._tool("freecad_export_file", "Export File", "Export selected/all objects from a document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "export_file"),
            self._tool("freecad_supported_formats", "Supported Formats", "Return common import/export formats.", {}, [], "supported_formats"),
            self._tool("freecad_mesh_import", "Import Mesh", "Import a mesh file into a document.", {"input_path": {"type": "string"}, "document_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["input_path"], "mesh_import"),
            self._tool("freecad_mesh_export", "Export Mesh", "Export mesh objects.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "overwrite": {"type": "boolean"}}, ["document_path", "output_path"], "mesh_export"),
            self._tool("freecad_mesh_evaluate", "Evaluate Mesh", "Summarize mesh object health.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}}, ["document_path"], "mesh_evaluate"),
            self._tool("freecad_mesh_repair", "Repair Mesh", "Run conservative mesh repair actions.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "actions": {"type": "array", "items": {"type": "string", "enum": ["harmonize_normals", "remove_duplicated_points"]}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "mesh_repair"),
            self._tool("freecad_mesh_boolean", "Mesh Boolean", "Run mesh boolean operation when supported by FreeCAD build.", {"document_path": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "operation": {"type": "string", "enum": ["union", "difference", "intersection"]}, "result_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "object_names"], "mesh_boolean"),
            self._tool("freecad_assembly_create", "Create Assembly", "Create an Assembly object.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "assembly_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "assembly_create"),
            self._tool("freecad_assembly_insert", "Insert Assembly Link", "Insert an existing object into an assembly as an App::Link.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "object_name": {"type": "string"}, "link_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name", "object_name"], "assembly_insert"),
            self._tool("freecad_assembly_create_joint", "Create Assembly Joint", "Create a native Assembly JointObject proxy under an assembly joint group.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}, "joint_type": {"type": "string", "enum": ["Fixed", "Revolute", "Cylindrical", "Slider", "Ball", "Distance", "Parallel", "Perpendicular", "Angle", "RackPinion", "Screw", "Gears", "Belt"]}, "joint_name": {"type": "string"}, "references": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "assembly_name"], "assembly_create_joint"),
            self._tool("freecad_assembly_solve", "Solve Assembly", "Recompute an assembly document.", {"document_path": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "assembly_solve"),
            self._tool("freecad_assembly_bom", "Assembly BOM", "Return a simple assembly bill of materials.", {"document_path": {"type": "string"}, "assembly_name": {"type": "string"}}, ["document_path"], "assembly_bom"),
            self._tool("freecad_techdraw_page_create", "Create TechDraw Page", "Create a headless TechDraw page with an optional SVG template.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "page_name": {"type": "string"}, "template_name": {"type": "string"}, "template_path": {"type": "string"}, "scale": {"type": "number"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "techdraw_page_create"),
            self._tool("freecad_techdraw_view_create", "Create TechDraw Part View", "Create a TechDraw DrawViewPart on a page from source document objects.", {"document_path": {"type": "string"}, "page_name": {"type": "string"}, "source_objects": {"type": "array", "items": {"type": "string"}}, "view_name": {"type": "string"}, "direction": {"type": "array", "items": {"type": "number"}}, "x_direction": {"type": "array", "items": {"type": "number"}}, "scale": {"type": "number"}, "x": {"type": "number"}, "y": {"type": "number"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path", "page_name", "source_objects"], "techdraw_view_create"),
            self._tool("freecad_techdraw_inspect", "Inspect TechDraw", "Inspect TechDraw pages and views in a document.", {"document_path": {"type": "string"}, "page_name": {"type": "string"}}, ["document_path"], "techdraw_inspect"),
            self._tool("freecad_techdraw_page_export", "Export TechDraw Page", "Export a TechDraw page through headless TechDraw APIs. DXF is currently supported.", {"document_path": {"type": "string"}, "page_name": {"type": "string"}, "output_path": {"type": "string"}, "format": {"type": "string", "enum": ["dxf"]}, "overwrite": {"type": "boolean"}}, ["document_path", "page_name", "output_path"], "techdraw_page_export"),
            self._tool("freecad_cam_path_create", "Create CAM Path", "Create a simple CAM Path::Feature from explicit G-code command specs.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "path_name": {"type": "string"}, "commands": {"type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "object"}]}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["commands"], "cam_path_create"),
            self._tool("freecad_cam_path_inspect", "Inspect CAM Path", "Inspect CAM Path::Feature objects and command summaries.", {"document_path": {"type": "string"}, "path_name": {"type": "string"}}, ["document_path"], "cam_path_inspect"),
            self._tool("freecad_cam_path_export", "Export CAM Path G-code", "Export a CAM Path::Feature to raw G-code without invoking a machine postprocessor.", {"document_path": {"type": "string"}, "path_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, ["document_path", "path_name", "output_path"], "cam_path_export"),
            self._tool("freecad_fem_analysis_create", "Create FEM Analysis", "Create a FEM analysis container.", {"document_path": {"type": "string"}, "document_name": {"type": "string"}, "analysis_name": {"type": "string"}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}}, [], "fem_analysis_create"),
            self._tool("freecad_fem_material_create", "Create FEM Material", "Create a FEM solid material and add it to an analysis.", {"document_path": {"type": "string"}, "analysis_name": {"type": "string"}, "material_name": {"type": "string"}, "material": {"type": "object"}, "references": {"type": "array", "items": {"type": "object"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "fem_material_create"),
            self._tool("freecad_fem_constraint_create", "Create FEM Constraint", "Create a fixture-safe FEM fixed or force constraint and add it to an analysis.", {"document_path": {"type": "string"}, "analysis_name": {"type": "string"}, "constraint_type": {"type": "string", "enum": ["fixed", "force"]}, "constraint_name": {"type": "string"}, "references": {"type": "array", "items": {"type": "object"}}, "force": {"type": "string"}, "direction_reference": {"type": "object"}, "direction_vector": {"type": "array", "items": {"type": "number"}}, "output_path": {"type": "string"}, "overwrite": {"type": "boolean"}, "save": {"type": "boolean"}}, ["document_path"], "fem_constraint_create"),
            self._tool("freecad_fem_inspect", "Inspect FEM Analysis", "Inspect FEM analyses, materials, and constraints in a document.", {"document_path": {"type": "string"}}, ["document_path"], "fem_inspect"),
        ]

    def definition_map(self) -> dict[str, ToolDefinition]:
        return {definition.name: definition for definition in self.definitions()}

    def _tool(
        self,
        name: str,
        title: str,
        description: str,
        properties: JsonObject,
        required: list[str],
        action: str,
    ) -> ToolDefinition:
        schema = {"type": "object", "properties": {**properties, **COMMON_RUNTIME_PROPS}}
        if required:
            schema["required"] = required
        return ToolDefinition(
            name,
            title,
            description,
            schema,
            lambda args, action=action, required=required: self._run(action, args, required),
        )

    def _run(self, action: str, args: JsonObject, required: list[str]) -> JsonObject:
        for key in required:
            if key not in args or args[key] in (None, ""):
                raise ToolInputError(f"{key} is required")
        executable_arg = optional_string(args, "executable")
        freecad_home = optional_string(args, "freecad_home")
        timeout_sec = bounded_int(args, "timeout_sec", default=60, minimum=1, maximum=180)
        compact_execution = args.get("compact_execution", False)
        if not isinstance(compact_execution, bool):
            raise ToolInputError("compact_execution must be a boolean")
        discovery = self.discovery.discover(executable=executable_arg, freecad_home=freecad_home)
        if discovery.executable is None:
            raise ToolInputError(
                "FreeCADCmd not found. Set FREECAD_MCP_FREECAD_HOME, FREECAD_MCP_FREECAD_CMD, "
                "or pass freecad_home/executable."
            )

        action_args = {
            key: value
            for key, value in args.items()
            if key not in {"executable", "freecad_home", "timeout_sec", "compact_execution"}
        }
        action_args["_workspace_root"] = os.environ.get("FREECAD_MCP_WORKSPACE_ROOT") or str(Path.cwd())
        action_args["action"] = action
        if action == "object_delete" and not action_args.get("object_name") and not action_args.get("object_names"):
            raise ToolInputError("object_name or object_names is required")
        encoded_args = base64.b64encode(json.dumps(action_args).encode("utf-8")).decode("ascii")
        code = CAD_ACTION_SCRIPT.replace("__ARGS_B64__", encoded_args)
        result = FreeCadCmdBridge(Path(discovery.executable)).execute_python(code, timeout_sec=timeout_sec)
        payload = parse_prefixed_json(result.stdout)
        if result.ok and payload is None:
            raise ToolInputError("FreeCAD response did not include a valid MCP JSON payload")
        return {
            "discovery": discovery.to_dict(),
            "execution": result.to_compact_dict() if compact_execution else result.to_dict(),
            "freecad": payload,
        }
