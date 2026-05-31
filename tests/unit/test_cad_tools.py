from __future__ import annotations

import unittest

from freecad_mcp.cad_tools import CAD_ACTION_SCRIPT, CadToolService
from freecad_mcp.tooling import ToolInputError, load_runtime_script


class _DiscoveryResult:
    """Minimal stand-in for FreeCadDiscoveryResult."""

    def __init__(self, executable: str | None) -> None:
        self.executable = executable

    def to_dict(self) -> dict:
        return {"found": self.executable is not None, "executable": self.executable}


class _RecordingDiscovery:
    """Fake discovery that records calls and never launches FreeCADCmd."""

    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable
        self.calls = 0

    def discover(self, executable: str | None = None, freecad_home: str | None = None) -> _DiscoveryResult:
        self.calls += 1
        return _DiscoveryResult(self._executable)


class CadActionScriptTests(unittest.TestCase):
    def test_cad_action_script_is_valid_python_with_args_placeholder(self) -> None:
        # Guards the embedded-script contract: it must stay syntactically valid
        # Python and keep the base64 args placeholder the host substitutes before
        # sending it to FreeCADCmd. This protects any move to an external script file.
        self.assertIn("__ARGS_B64__", CAD_ACTION_SCRIPT)
        self.assertIn("def emit(", CAD_ACTION_SCRIPT)
        self.assertIn('"is_null": True', CAD_ACTION_SCRIPT)
        compile(CAD_ACTION_SCRIPT, "<cad_action_script>", "exec")


class LoadRuntimeScriptTests(unittest.TestCase):
    def test_loads_known_runtime_scripts(self) -> None:
        # Guards against the extracted script files being omitted from packaging:
        # both must exist on disk and load with real content.
        for name in ("cad_action.py", "worker.py"):
            content = load_runtime_script(name)
            self.assertGreater(len(content), 1000, name)

    def test_missing_script_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing or unreadable"):
            load_runtime_script("does_not_exist_xyz.py")


class CadToolServiceDefinitionTests(unittest.TestCase):
    def test_aggregate_keeps_domain_services_split(self) -> None:
        service = CadToolService()

        self.assertEqual(
            service.domain_names(),
            [
                "document",
                "object",
                "part",
                "partdesign",
                "sketcher",
                "io",
                "mesh",
                "assembly",
                "techdraw",
                "cam",
                "fem",
            ],
        )
        self.assertEqual(len(service.definitions()), 60)

    def test_definitions_have_unique_names_and_merge_common_runtime_props(self) -> None:
        definitions = CadToolService().definitions()
        names = [definition.name for definition in definitions]

        self.assertEqual(len(names), len(set(names)), "duplicate CAD tool names")
        self.assertTrue(all(name.startswith("freecad_") for name in names))
        for definition in definitions:
            schema = definition.input_schema
            self.assertEqual(schema.get("type"), "object", definition.name)
            # COMMON_RUNTIME_PROPS must be merged into every typed CAD tool.
            self.assertIn("timeout_sec", schema["properties"], definition.name)
            self.assertIn("compact_execution", schema["properties"], definition.name)


class CadToolServiceRunTests(unittest.TestCase):
    def _handler(self, service: CadToolService, tool_name: str):
        return service.definition_map()[tool_name].handler

    def test_required_field_validation_raises_before_discovery(self) -> None:
        discovery = _RecordingDiscovery()
        service = CadToolService(discovery=discovery)
        handler = self._handler(service, "freecad_document_open")

        with self.assertRaises(ToolInputError):
            handler({})

        self.assertEqual(discovery.calls, 0, "discovery must not run when args are invalid")

    def test_empty_string_required_field_is_rejected(self) -> None:
        discovery = _RecordingDiscovery()
        service = CadToolService(discovery=discovery)
        handler = self._handler(service, "freecad_document_open")

        with self.assertRaises(ToolInputError):
            handler({"document_path": ""})

        self.assertEqual(discovery.calls, 0)

    def test_timeout_sec_out_of_range_raises_before_discovery(self) -> None:
        discovery = _RecordingDiscovery()
        service = CadToolService(discovery=discovery)
        handler = self._handler(service, "freecad_document_open")

        with self.assertRaises(ToolInputError):
            handler({"document_path": "model.FCStd", "timeout_sec": 9999})

        self.assertEqual(discovery.calls, 0)

    def test_compact_execution_must_be_boolean(self) -> None:
        discovery = _RecordingDiscovery()
        service = CadToolService(discovery=discovery)
        handler = self._handler(service, "freecad_document_open")

        with self.assertRaises(ToolInputError):
            handler({"document_path": "model.FCStd", "compact_execution": "yes"})

        self.assertEqual(discovery.calls, 0)

    def test_object_delete_requires_object_selector_after_discovery(self) -> None:
        # Discovery succeeds, so the selector guard is what must reject the call,
        # and it must do so before any FreeCADCmd process is launched.
        discovery = _RecordingDiscovery(executable="C:/nonexistent/FreeCADCmd.exe")
        service = CadToolService(discovery=discovery)
        handler = self._handler(service, "freecad_object_delete")

        with self.assertRaises(ToolInputError):
            handler({"document_path": "model.FCStd"})

        self.assertEqual(discovery.calls, 1)

    def test_missing_freecadcmd_raises_tool_input_error(self) -> None:
        discovery = _RecordingDiscovery(executable=None)
        service = CadToolService(discovery=discovery)
        handler = self._handler(service, "freecad_document_open")

        with self.assertRaises(ToolInputError) as ctx:
            handler({"document_path": "model.FCStd"})

        self.assertIn("FreeCADCmd not found", str(ctx.exception))
        self.assertEqual(discovery.calls, 1)


if __name__ == "__main__":
    unittest.main()
