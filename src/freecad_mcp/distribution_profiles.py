"""Distribution profile descriptors for packaging the FreeCAD MCP bundles."""

from __future__ import annotations

from dataclasses import dataclass

from freecad_mcp.mcp_stdio import REPO_ROOT_ENV, SERVER_NAME
from freecad_mcp.module_registry import MODULE_ENV
from freecad_mcp.product_bundles import ProductBundle, bundle_map
from freecad_mcp.workbench_artifact import ARTIFACT_KEY as WORKBENCH_ARTIFACT_KEY
from freecad_mcp.workbench_artifact import ZIP_NAME as WORKBENCH_ZIP_NAME


PROJECT_NAME = "freecad-hybrid-mcp"
ENTRYPOINT = "freecad-hybrid-mcp"
PYTHON_PACKAGE = "freecad_mcp"


@dataclass(frozen=True)
class DistributionProfile:
    key: str
    bundle_key: str
    channel: str
    artifacts: tuple[str, ...]
    components: tuple[str, ...]
    notes: str

    @property
    def bundle(self) -> ProductBundle:
        return bundle_map()[self.bundle_key]

    def mcp_config(self) -> dict[str, object]:
        server_name = f"freecad-{self.key}"
        return {
            "mcpServers": {
                server_name: {
                    "command": ENTRYPOINT,
                    "args": [],
                    "env": {
                        MODULE_ENV: self.bundle.profile,
                        REPO_ROOT_ENV: "<repo-root-if-running-outside-checkout>",
                        "FREECAD_MCP_WORKSPACE_ROOT": "<workspace-root>",
                        "FREECAD_MCP_FREECAD_HOME": "<portable-freecad-root>",
                    },
                }
            }
        }

    def to_dict(self) -> dict[str, object]:
        bundle = self.bundle.to_dict()
        return {
            "key": self.key,
            "bundle_key": self.bundle_key,
            "title": bundle["title"],
            "profile": bundle["profile"],
            "channel": self.channel,
            "artifacts": list(self.artifacts),
            "components": list(self.components),
            "env": {
                MODULE_ENV: bundle["profile"],
                REPO_ROOT_ENV: "<repo-root-if-running-outside-checkout>",
            },
            "entrypoint": ENTRYPOINT,
            "python_package": PYTHON_PACKAGE,
            "server_name": SERVER_NAME,
            "notes": self.notes,
            "mcp_config": self.mcp_config(),
            "workbench_artifact": {
                "artifact_key": WORKBENCH_ARTIFACT_KEY,
                "zip_name": WORKBENCH_ZIP_NAME,
            }
            if WORKBENCH_ARTIFACT_KEY in self.artifacts
            else None,
        }


DISTRIBUTION_PROFILES: tuple[DistributionProfile, ...] = (
    DistributionProfile(
        key="free",
        bundle_key="free",
        channel="public",
        artifacts=("wheel", "sdist", "stdio-mcp-config"),
        components=("python-package", "runtime-scripts"),
        notes="Base local automation package; no GUI workbench component is needed.",
    ),
    DistributionProfile(
        key="pro",
        bundle_key="pro",
        channel="paid",
        artifacts=("wheel", "sdist", "stdio-mcp-config", "freecad-workbench-module"),
        components=("python-package", "runtime-scripts", "gui-bridge", "workbench-module"),
        notes="Adds GUI attach; ship the FreeCAD workbench module next to the Python package.",
    ),
    DistributionProfile(
        key="studio",
        bundle_key="studio",
        channel="paid",
        artifacts=("wheel", "sdist", "stdio-mcp-config", "freecad-workbench-module"),
        components=("python-package", "runtime-scripts", "persistent-worker", "gui-bridge", "workbench-module"),
        notes="Adds persistent workers and advanced workbench slices; keep worker temp-script cleanup tests in the release gate.",
    ),
    DistributionProfile(
        key="team",
        bundle_key="team",
        channel="paid",
        artifacts=("wheel", "sdist", "stdio-mcp-config", "freecad-workbench-module", "source-intelligence-docs"),
        components=("python-package", "runtime-scripts", "persistent-worker", "gui-bridge", "workbench-module", "source-intelligence"),
        notes="Team profile includes source-intelligence tools for support and implementation research.",
    ),
    DistributionProfile(
        key="source",
        bundle_key="source",
        channel="add-on",
        artifacts=("wheel", "stdio-mcp-config"),
        components=("source-intelligence",),
        notes="Add-on profile for maintainers that should be layered with another paid profile when mutation tools are needed.",
    ),
    DistributionProfile(
        key="unsafe",
        bundle_key="unsafe",
        channel="add-on",
        artifacts=("wheel", "stdio-mcp-config"),
        components=("unsafe-python-exec",),
        notes="Explicit trusted-local add-on; never include in the default paid profiles.",
    ),
)


def distribution_profile_map() -> dict[str, DistributionProfile]:
    return {profile.key: profile for profile in DISTRIBUTION_PROFILES}


def distribution_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {
            "name": PROJECT_NAME,
            "python_package": PYTHON_PACKAGE,
            "entrypoint": ENTRYPOINT,
            "repo_root_env": REPO_ROOT_ENV,
            "module_env": MODULE_ENV,
        },
        "profiles": [profile.to_dict() for profile in DISTRIBUTION_PROFILES],
    }
