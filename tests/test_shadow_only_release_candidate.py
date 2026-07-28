from __future__ import annotations

import asyncio
import json
import re
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from custom_components.benni_core_contracts import async_setup, async_setup_entry
from custom_components.benni_core_contracts.const import (
    CONFIG_SCHEMA_VERSION,
    DOMAIN,
    MODE_SHADOW_ONLY,
    RELEASE_CHANNEL,
    RELEASE_VERSION,
)
from custom_components.benni_core_contracts.live_evidence import LiveEvidenceStatus
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    ProfileId,
    RuntimeMode,
)
from custom_components.benni_core_contracts.shadow import ShadowRuntime
from custom_components.benni_core_contracts.graph import SignalGraph

from tests.live_evidence_fixtures import open_benni_live_report_fixture


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "benni_core_contracts"


class _EmptyStorage:
    async def async_load(self):
        return None


class ShadowOnlyReleaseCandidateTests(unittest.TestCase):
    def _entry(self, *, profile: str = "benni", mode: str = MODE_SHADOW_ONLY):
        return SimpleNamespace(
            entry_id="shadow-entry",
            data={
                "schema_version": CONFIG_SCHEMA_VERSION,
                "profile": profile,
                "mode": mode,
                "entity_allowlist": [],
                "bindings": [],
            },
            options={},
            async_on_unload=lambda _callback: None,
        )

    def test_release_metadata_is_explicit_shadow_prerelease(self) -> None:
        manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(manifest["domain"], DOMAIN)
        self.assertEqual(manifest["version"], RELEASE_VERSION)
        self.assertEqual(RELEASE_VERSION, "0.2.0-alpha.2")
        self.assertEqual(hacs["name"], manifest["name"])
        self.assertFalse(hacs["zip_release"])
        self.assertEqual(project["project"]["version"], RELEASE_VERSION)
        self.assertEqual(RELEASE_CHANNEL, MODE_SHADOW_ONLY)

    def test_release_documents_and_ci_are_version_consistent(self) -> None:
        release_doc = (ROOT / "docs" / "shadow-release-v1.md").read_text(encoding="utf-8")
        release_notes = (ROOT / "docs" / "release-notes-shadow-0.2.0-alpha.2.md").read_text(
            encoding="utf-8"
        )
        gitlab_ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        github_workflow = (ROOT / ".github" / "workflows" / "hacs-release.yml").read_text(
            encoding="utf-8"
        )
        for document in (release_doc, release_notes):
            self.assertIn(RELEASE_VERSION, document)
            self.assertIn("shadow-only", document.lower())
            self.assertIn("0 HA-Entities", document)
            self.assertIn("parent_future", document)
        self.assertIn('HACS_GITHUB_REPOSITORY: "Levtos/benni-core-contracts"', gitlab_ci)
        self.assertIn("ha-platform/control", gitlab_ci)
        self.assertIn("--prerelease", github_workflow)
        self.assertIn("custom_components/benni_core_contracts/manifest.json", github_workflow)

    def test_repository_contains_no_secret_material(self) -> None:
        secret_patterns = (
            re.compile(r"\bglpat-[A-Za-z0-9_-]{12,}\b"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
        )
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or "__pycache__" in path.parts
                or "node_modules" in path.parts
            ):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in secret_patterns:
                self.assertIsNone(pattern.search(source), str(path))

    def test_missing_mode_never_defaults_to_shadow_only(self) -> None:
        with self.assertRaises(ValueError):
            ConfigModel()
        with self.assertRaises(ValueError):
            ConfigModel.from_dict({"profile": "benni"})
        with self.assertRaises(ValueError):
            ConfigModel.from_dict({"profile": "benni", "mode": "shadow"})
        with self.assertRaises(ValueError):
            ConfigModel.from_dict({"profile": "benni", "mode": "published"})

    def test_shadow_config_is_explicit_empty_and_has_no_entity_allowlist(self) -> None:
        config = ConfigModel.from_dict(
            {
                "profile": "benni",
                "mode": MODE_SHADOW_ONLY,
                "bindings": [],
                "entity_allowlist": [],
            }
        )
        self.assertEqual(config.mode, RuntimeMode.SHADOW_ONLY)
        self.assertEqual(config.bindings, ())
        self.assertEqual(config.entity_allowlist, ())
        with self.assertRaises(ValueError):
            ConfigModel.from_dict(
                {
                    "profile": "benni",
                    "mode": MODE_SHADOW_ONLY,
                    "entity_allowlist": ["sensor.forbidden"],
                }
            )

    def test_setup_without_config_entry_creates_no_entities(self) -> None:
        hass = SimpleNamespace(data={})
        self.assertTrue(asyncio.run(async_setup(hass, {})))
        self.assertEqual(hass.data[DOMAIN], {})
        self.assertFalse((PACKAGE / "sensor.py").exists())
        self.assertFalse((PACKAGE / "binary_sensor.py").exists())

    def test_shadow_config_entry_creates_no_entities_or_bindings(self) -> None:
        hass = SimpleNamespace(data={})
        entry = self._entry()
        with (
            patch(
                "custom_components.benni_core_contracts.HomeAssistantStorage",
                return_value=_EmptyStorage(),
            ),
            patch(
                "custom_components.benni_core_contracts.async_register_websocket_api",
                new=AsyncMock(),
            ),
            patch(
                "custom_components.benni_core_contracts.async_attach_source_listeners",
                new=AsyncMock(),
            ),
            patch(
                "custom_components.benni_core_contracts.async_setup_view",
                new=AsyncMock(),
            ),
        ):
            self.assertTrue(asyncio.run(async_setup_entry(hass, entry)))

        runtime = hass.data[DOMAIN][entry.entry_id]
        self.assertIsInstance(runtime, ShadowRuntime)
        self.assertEqual(runtime.graph.bindings(), ())
        self.assertEqual(runtime.public_entity_ids(("sensor.any_candidate",)), ())
        self.assertEqual(runtime.config.mode, RuntimeMode.SHADOW_ONLY)

    def test_parent_config_entry_is_rejected_without_activation(self) -> None:
        hass = SimpleNamespace(data={})
        self.assertFalse(asyncio.run(async_setup_entry(hass, self._entry(profile="eltern"))))
        self.assertEqual(hass.data, {})
        with self.assertRaises(ValueError):
            ShadowRuntime(
                ConfigModel(profile=ProfileId.ELTERN, mode=RuntimeMode.SHADOW_ONLY),
                SignalGraph(),
            )

    def test_invalid_mode_is_rejected_before_any_runtime_setup(self) -> None:
        hass = SimpleNamespace(data={})
        with self.assertRaises(ValueError):
            asyncio.run(async_setup_entry(hass, self._entry(mode="published")))
        self.assertEqual(hass.data, {})

    def test_read_only_boundary_has_no_services_actuation_or_policy_imports(self) -> None:
        forbidden_tokens = (
            "async_add_entities",
            "async_call",
            "call_service",
            "homeassistant.services",
        )
        forbidden_import = re.compile(r"(?:benni_(?:core_devices|.*policy)|core_devices|policy_[a-z_]+)")
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, source, path.name)
            for line in source.splitlines():
                if line.startswith(("from ", "import ")):
                    self.assertIsNone(forbidden_import.search(line), line)

    def test_blocked_live_access_cannot_fabricate_current_values(self) -> None:
        report = open_benni_live_report_fixture()
        self.assertEqual(report.status, LiveEvidenceStatus.OPEN)
        self.assertEqual(report.entity_ids, ())
        self.assertFalse(report.config_entry_activated)
        self.assertFalse(report.source_bindings_activated)
        self.assertTrue(all(field.value == "unknown" for field in report.fields))
        self.assertTrue(
            all(field.status in {LiveEvidenceStatus.BLOCKED, LiveEvidenceStatus.OPEN}
                for field in report.fields)
        )


if __name__ == "__main__":
    unittest.main()
