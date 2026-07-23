from __future__ import annotations

import re
import unittest
from pathlib import Path

from custom_components.benni_core_contracts.contracts import default_schema_registry
from custom_components.benni_core_contracts.evidence_gate import (
    EvidenceGateStatus,
    evaluate_contract_evidence,
)
from custom_components.benni_core_contracts.quality import (
    FreshnessStatus,
    QualityStatus,
    ValueState,
)

from fixtures import (
    all_evidence_fixtures,
    build_fixture_graph,
    conflicting_sources_fixture,
    eltern_room_climate_fixture,
    retained_mqtt_fixture,
    restore_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "benni_core_contracts"
DOCS = ROOT / "docs"


class ContractEvidenceGateTests(unittest.TestCase):
    def gate_for(self, fixture):
        graph = build_fixture_graph(fixture)
        contract = graph.evaluate_contract(fixture.contract_id, fixture.schema_id, now=fixture.now)
        schema = graph.registry.get(fixture.schema_id)
        return graph, contract, evaluate_contract_evidence(contract, schema)

    def test_all_required_fixtures_exist_and_use_the_generic_builder(self) -> None:
        fixtures = all_evidence_fixtures()
        self.assertEqual(len(fixtures), 15)
        self.assertEqual(
            {fixture.name for fixture in fixtures},
            {
                "benni_room_climate",
                "eltern_room_climate",
                "opening",
                "opening_missing_sources",
                "opening_stale",
                "opening_retained_mqtt",
                "opening_restore",
                "opening_conflict",
                "weather_environment",
                "technical_device",
                "rollo_partial_failure",
                "missing_sources",
                "retained_mqtt",
                "restore",
                "conflicting_sources",
            },
        )
        self.assertEqual(
            len({fixture.config.mode.value for fixture in fixtures}),
            1,
        )
        self.assertEqual(all(fixture.config.entity_allowlist == () for fixture in fixtures), True)

    def test_valid_contract_fixtures_pass_required_evidence_gate(self) -> None:
        expected_pass = {
            "benni_room_climate",
            "eltern_room_climate",
            "opening",
            "weather_environment",
            "technical_device",
        }
        for fixture in all_evidence_fixtures():
            if fixture.name not in expected_pass:
                continue
            _, contract, gate = self.gate_for(fixture)
            self.assertEqual(gate.status, EvidenceGateStatus.PASS, fixture.name)
            self.assertTrue(gate.required_fields_ready, fixture.name)
            self.assertEqual(contract.health.value, "healthy", fixture.name)

    def test_eltern_fixture_has_the_same_contract_semantics_as_benni(self) -> None:
        benni = all_evidence_fixtures()[0]
        eltern = eltern_room_climate_fixture()
        _, benni_contract, benni_gate = self.gate_for(benni)
        _, eltern_contract, eltern_gate = self.gate_for(eltern)
        self.assertEqual(benni_contract.schema_id, eltern_contract.schema_id)
        self.assertEqual(benni_contract.values, eltern_contract.values)
        self.assertEqual(benni_gate.status, eltern_gate.status)
        self.assertTrue(all(binding.profile_id.value == "eltern" for binding in eltern.bindings))

    def test_rollo_partial_failure_is_technical_evidence_not_a_policy_target(self) -> None:
        fixture = next(item for item in all_evidence_fixtures() if item.name == "rollo_partial_failure")
        _, contract, gate = self.gate_for(fixture)
        self.assertEqual(gate.status, EvidenceGateStatus.DEGRADED)
        self.assertTrue(gate.required_fields_ready)
        self.assertEqual(contract.values["device_state"], "partial_failure")
        self.assertNotIn("target_position", contract.values)
        self.assertNotIn("privacy", contract.values)

    def test_missing_sources_block_required_fields_but_keep_field_scope(self) -> None:
        fixture = next(item for item in all_evidence_fixtures() if item.name == "missing_sources")
        _, contract, gate = self.gate_for(fixture)
        self.assertEqual(gate.status, EvidenceGateStatus.BLOCKED)
        self.assertFalse(gate.required_fields_ready)
        self.assertEqual(set(gate.blocked_fields), {"temperature", "available"})
        self.assertIsNone(contract.values["temperature"])
        self.assertEqual(contract.values["available"], False)
        self.assertEqual(contract.field_states["temperature"], ValueState.BLOCKED)

    def test_opening_physical_fields_never_claim_open_without_valid_evidence(self) -> None:
        expected = {
            "opening_missing_sources": ("source_unavailable", None),
            "opening_stale": ("source_stale", FreshnessStatus.STALE),
            "opening_retained_mqtt": ("source_stale", FreshnessStatus.SUSPECT),
            "opening_restore": ("source_restored", FreshnessStatus.RESTORED),
            "opening_conflict": ("source_conflict", FreshnessStatus.FRESH),
        }
        fixtures = {
            fixture.name: fixture
            for fixture in all_evidence_fixtures()
            if fixture.name in expected
        }
        for name, (reason, freshness) in expected.items():
            _, contract, gate = self.gate_for(fixtures[name])
            self.assertEqual(gate.status, EvidenceGateStatus.BLOCKED, name)
            self.assertFalse(gate.required_fields_ready, name)
            self.assertEqual(contract.values["opening_state"], "unknown", name)
            self.assertEqual(contract.values["is_open"], "unknown", name)
            self.assertEqual(contract.field_states["opening_state"], ValueState.UNKNOWN, name)
            self.assertEqual(contract.field_states["is_open"], ValueState.UNKNOWN, name)
            for field in ("opening_state", "is_open"):
                self.assertIn(
                    contract.field_quality[field].health.value,
                    {"blocked", "degraded"},
                    f"{name}:{field}",
                )
                self.assertIn(
                    contract.field_quality[field].safety.value,
                    {"unsafe", "unknown"},
                    f"{name}:{field}",
                )
                if freshness is not None:
                    self.assertEqual(
                        contract.field_quality[field].freshness,
                        freshness,
                        f"{name}:{field}",
                    )
                self.assertTrue(
                    any(
                        issue.code == reason
                        for issue in contract.field_quality[field].reasons
                    ),
                    f"{name}:{field}",
                )
                gate_field = next(item for item in gate.fields if item.field == field)
                self.assertIn(reason, gate_field.reasons, f"{name}:{field}:gate")

    def test_opening_available_false_is_not_required_evidence(self) -> None:
        fixture = next(
            item
            for item in all_evidence_fixtures()
            if item.name == "opening_missing_sources"
        )
        _, contract, gate = self.gate_for(fixture)
        self.assertFalse(contract.values["available"])
        self.assertEqual(contract.field_states["available"], ValueState.UNKNOWN)
        self.assertEqual(contract.field_quality["available"].health.value, "degraded")
        self.assertFalse(gate.required_fields_ready)
        self.assertIn("available", gate.blocked_fields)

    def test_retained_mqtt_is_blocked_and_never_passes_as_fresh(self) -> None:
        _, contract, gate = self.gate_for(retained_mqtt_fixture())
        self.assertEqual(gate.status, EvidenceGateStatus.BLOCKED)
        quality = contract.field_quality["available"]
        self.assertEqual(quality.freshness, FreshnessStatus.SUSPECT)
        self.assertEqual(quality.quality, QualityStatus.DEGRADED)
        self.assertNotEqual(quality.freshness, FreshnessStatus.FRESH)

    def test_restore_is_blocked_and_remains_restored(self) -> None:
        _, contract, gate = self.gate_for(restore_fixture())
        self.assertEqual(gate.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(
            contract.field_quality["available"].freshness,
            FreshnessStatus.RESTORED,
        )
        self.assertEqual(contract.field_states["available"], ValueState.UNKNOWN)

    def test_conflicting_sources_are_visible_and_do_not_pass_required_gate(self) -> None:
        graph, contract, gate = self.gate_for(conflicting_sources_fixture())
        self.assertEqual(gate.status, EvidenceGateStatus.BLOCKED)
        self.assertTrue(gate.fields[0].required)
        self.assertEqual(contract.values["available"], True)
        self.assertEqual(contract.lineage["available"], ("fixture_conflicting_sources_primary",))
        self.assertEqual(contract.field_quality["available"].quality, QualityStatus.CONFLICT)
        diagnostic = graph.diagnostic(conflicting_sources_fixture().contract_id)
        self.assertIsNotNone(diagnostic)
        self.assertTrue(
            any(
                issue.code == "conflicting_fresh_sources"
                for issue in diagnostic.fields[0].root_causes
            )
        )

    def test_every_contract_field_has_documented_evidence_metadata(self) -> None:
        evidence_doc = (DOCS / "contract-evidence-gate-v1.md").read_text(encoding="utf-8")
        registry = default_schema_registry()
        for schema in registry.all():
            self.assertIn(f"{schema.schema_id}.v{schema.version}", evidence_doc)
            for field in schema.fields:
                self.assertIn(f"`{field.name}`", evidence_doc)
                self.assertIn(field.freshness_requirement.value, evidence_doc)
                self.assertIn(field.fallback.action.value, evidence_doc)

    def test_repository_code_matches_documented_boundaries(self) -> None:
        architecture = (DOCS / "architecture.md").read_text(encoding="utf-8")
        gate_pack = (DOCS / "gate-pack-v1.md").read_text(encoding="utf-8")
        status = (DOCS / "implementation-status.md").read_text(encoding="utf-8")
        ux = (DOCS / "ux-contract.md").read_text(encoding="utf-8")
        owner_gate = (DOCS / "benni-owner-required-field-gate-v1.md").read_text(encoding="utf-8")
        shadow_gate = (DOCS / "benni-shadow-contract-verification-v1.md").read_text(
            encoding="utf-8"
        )
        for model in (
            "SourceBinding",
            "AtomicSignal",
            "Fusion",
            "PublishedContract",
            "DiagnosticProjection",
        ):
            self.assertIn(model, architecture)
            self.assertIn(model, gate_pack)
        for schema_id in (
            "room_climate.v1",
            "opening.v1",
            "weather_environment.v1",
            "technical_device.v1",
        ):
            self.assertIn(schema_id, gate_pack)
            self.assertIn(schema_id, status)
            self.assertIn(schema_id, owner_gate)
        for marker in (
            "benni_production",
            "parent_future",
            "pass",
            "degraded",
            "blocked",
            "lock.flur_aqara_smart_lock_u200",
            "fallback=reject",
            "0 HA-Entities",
        ):
            self.assertIn(marker, owner_gate)
        for marker in (
            "verification_version=1",
            "ShadowSourceObservation",
            "active_source_entity",
            "fallback_chain",
            "parent_future",
            "lock.flur_aqara_smart_lock_u200",
            "lock.aqara_smart_lock_u200",
            "0 HA-Entities",
            "status/testing",
        ):
            self.assertIn(marker, shadow_gate)
        for command in (
            "list_contracts",
            "get_contract",
            "get_diagnostics",
            "get_graph",
            "get_health",
        ):
            self.assertIn(command, ux)
            self.assertIn(command, gate_pack)

    def test_no_entities_services_actuation_live_access_or_policy_imports(self) -> None:
        self.assertFalse((PACKAGE / "sensor.py").exists())
        self.assertFalse((PACKAGE / "binary_sensor.py").exists())
        forbidden_tokens = (
            "async_add_entities",
            "async_call",
            "call_service",
            "homeassistant.services",
            "requests.",
            "aiohttp",
            "socket.",
            "subprocess.",
        )
        forbidden_imports = re.compile(
            r"(?:benni_(?:core_devices|.*policy)|core_devices|policy_[a-z_]+)"
        )
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, source, f"forbidden boundary {token} in {path.name}")
            for line in source.splitlines():
                if line.startswith(("from ", "import ")):
                    self.assertIsNone(
                        forbidden_imports.search(line),
                        f"forbidden policy import in {path.name}: {line}",
                    )
        manifest = (PACKAGE / "manifest.json").read_text(encoding="utf-8")
        self.assertNotIn('"sensor"', manifest)
        self.assertNotIn('"binary_sensor"', manifest)
        self.assertNotIn('"platforms"', manifest)
