from __future__ import annotations

import re
import unittest
from pathlib import Path

from custom_components.benni_core_contracts.evidence_gate import EvidenceGateStatus
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    ProfileId,
    RuntimeMode,
)
from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    FreshnessStatus,
    SafetyStatus,
)
from custom_components.benni_core_contracts.shadow_verification import (
    SHADOW_CONTRACT_VERIFICATION_VERSION,
    UNKNOWN_VALUE,
    ShadowSourceObservation,
    verify_benni_shadow_contract,
    verify_benni_shadow_report,
    verify_evidence_only_binding,
)
from custom_components.benni_core_contracts.shadow import ShadowRuntime
from custom_components.benni_core_contracts.source_binding_evidence import (
    BENNI_CANONICAL_LOCK_ENTITY,
    HISTORICAL_BENNI_LOCK_ENTITY,
    BindingDisposition,
    source_binding_matrix_v1,
)

from fixtures import (
    benni_room_climate_fixture,
    build_fixture_graph,
    opening_conflict_fixture,
    opening_fixture,
    opening_missing_sources_fixture,
    opening_restore_fixture,
    opening_retained_mqtt_fixture,
    opening_stale_fixture,
    shadow_room_climate_fallback_fixture,
    shadow_unavailable_technical_fixture,
    shadow_unknown_opening_fixture,
    shadow_weather_partial_degradation_fixture,
    technical_device_fixture,
    weather_environment_fixture,
)
from shadow_verification_fixtures import (
    shadow_result_for_fixture,
    source_observations_for_fixture,
)
from source_binding_fixtures import FIXTURE_NOW, temporal_evidence


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "benni_core_contracts"


class BenniShadowContractVerificationTests(unittest.TestCase):
    def field(self, result, name: str):
        return next(item for item in result.fields if item.field == name)

    def test_valid_benni_contracts_report_complete_read_only_field_evidence(self) -> None:
        fixtures = (
            benni_room_climate_fixture(),
            opening_fixture(),
            weather_environment_fixture(),
            technical_device_fixture(),
        )
        for fixture in fixtures:
            _, _, result = shadow_result_for_fixture(fixture)
            self.assertEqual(result.version, SHADOW_CONTRACT_VERIFICATION_VERSION)
            self.assertEqual(result.profile_id, ProfileId.BENNI)
            self.assertEqual(result.status, EvidenceGateStatus.PASS, fixture.name)
            self.assertTrue(result.required_fields_ready, fixture.name)
            self.assertFalse(result.activation_allowed)
            self.assertFalse(result.config_entry_activated)
            self.assertEqual(result.entity_ids, ())
            for field in result.fields:
                payload = field.as_dict()
                for key in (
                    "contract_id",
                    "schema_version",
                    "profile",
                    "status",
                    "value",
                    "active_source_entity",
                    "fallback_chain",
                    "source_state",
                    "source_attributes",
                    "quality",
                    "health",
                    "freshness",
                    "root_causes",
                    "reason_codes",
                    "affected_capabilities",
                    "unaffected_capabilities",
                    "safety",
                    "consumer_impact",
                ):
                    self.assertIn(key, payload)
                self.assertEqual(field.status, EvidenceGateStatus.PASS)
                self.assertTrue(field.source_observations)
                self.assertTrue(field.active_source_entity)

    def test_shadow_runtime_exposes_the_same_internal_verification_without_activation(self) -> None:
        fixture = opening_fixture()
        graph = build_fixture_graph(fixture)
        graph.evaluate_contract(fixture.contract_id, fixture.schema_id, now=fixture.now)
        runtime = ShadowRuntime(
            ConfigModel(profile=ProfileId.BENNI, mode=RuntimeMode.SHADOW_ONLY),
            graph,
        )
        report = runtime.benni_contract_verification(now=fixture.now)
        self.assertEqual(report.status, EvidenceGateStatus.PASS)
        self.assertFalse(report.activation_allowed)
        self.assertFalse(report.config_entry_activated)
        self.assertEqual(report.entity_ids, ())
        self.assertEqual(runtime.public_entity_ids(("sensor.not_created",)), ())
        with self.assertRaises(ValueError):
            ConfigModel.from_dict(
                {
                    "profile": ProfileId.BENNI.value,
                    "mode": "published",
                }
            )

    def test_missing_source_forces_required_evidence_open_and_unknown(self) -> None:
        fixture = opening_missing_sources_fixture()
        _, _, result = shadow_result_for_fixture(fixture)
        opening = self.field(result, "opening_state")
        available = self.field(result, "available")

        self.assertEqual(result.status, EvidenceGateStatus.BLOCKED)
        self.assertFalse(result.required_fields_ready)
        self.assertEqual(opening.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(opening.value, UNKNOWN_VALUE)
        self.assertFalse(opening.physical_claim_allowed)
        self.assertEqual(opening.health.value, "blocked")
        self.assertEqual(opening.safety, SafetyStatus.UNKNOWN)
        self.assertIn("source_unavailable", opening.reason_codes)
        self.assertIn("live_evidence_open", opening.reason_codes)
        self.assertEqual(available.value, UNKNOWN_VALUE)
        self.assertNotEqual(available.value, True)

    def test_unavailable_and_unknown_source_states_do_not_pass(self) -> None:
        _, _, unavailable = shadow_result_for_fixture(shadow_unavailable_technical_fixture())
        technical_available = self.field(unavailable, "available")
        self.assertEqual(unavailable.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(technical_available.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(technical_available.value, UNKNOWN_VALUE)
        self.assertIn("source_state_unavailable", technical_available.reason_codes)

        _, _, unknown = shadow_result_for_fixture(shadow_unknown_opening_fixture())
        opening = self.field(unknown, "opening_state")
        self.assertEqual(unknown.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(opening.value, UNKNOWN_VALUE)
        self.assertFalse(opening.physical_claim_allowed)
        self.assertIn("source_state_unknown", opening.reason_codes)

    def test_stale_retained_restore_and_conflict_never_claim_physical_opening(self) -> None:
        cases = (
            (opening_stale_fixture(), "source_stale", FreshnessStatus.STALE),
            (opening_retained_mqtt_fixture(), "source_retained", FreshnessStatus.SUSPECT),
            (opening_restore_fixture(), "source_restored", FreshnessStatus.RESTORED),
            (opening_conflict_fixture(), "source_conflict", FreshnessStatus.FRESH),
        )
        for fixture, reason, freshness in cases:
            _, _, result = shadow_result_for_fixture(fixture)
            opening = self.field(result, "opening_state")
            is_open = self.field(result, "is_open")
            self.assertEqual(result.status, EvidenceGateStatus.BLOCKED, fixture.name)
            for field in (opening, is_open):
                self.assertEqual(field.value, UNKNOWN_VALUE, fixture.name)
                self.assertFalse(field.physical_claim_allowed, fixture.name)
                self.assertIn(reason, field.reason_codes, fixture.name)
                self.assertEqual(field.freshness, freshness, fixture.name)
                self.assertNotEqual(field.value, "open", fixture.name)
                self.assertNotEqual(field.value, True, fixture.name)

    def test_first_healthy_fallback_is_reported_with_its_selected_alternative(self) -> None:
        fixture = shadow_room_climate_fallback_fixture()
        _, _, result = shadow_result_for_fixture(fixture)
        temperature = self.field(result, "temperature")
        self.assertEqual(temperature.status, EvidenceGateStatus.PASS)
        self.assertEqual(temperature.value, 20.0)
        self.assertTrue(temperature.active_source_entity.endswith("temperature_secondary"))
        self.assertIn("fallback_to:fixture_shadow_room_climate_fallback_temperature_secondary", temperature.fallback_chain)
        self.assertEqual(temperature.freshness, FreshnessStatus.FRESH)

    def test_partial_weather_degradation_does_not_degrade_a_valid_technical_contract(self) -> None:
        weather_fixture = shadow_weather_partial_degradation_fixture()
        technical_fixture = technical_device_fixture()
        weather_graph, weather_contract, weather = shadow_result_for_fixture(weather_fixture)
        technical_graph, technical_contract, technical = shadow_result_for_fixture(technical_fixture)
        report = verify_benni_shadow_report(
            (weather_contract, technical_contract),
            weather_graph.registry,
            source_bindings=weather_fixture.bindings + technical_fixture.bindings,
            source_observations=(
                source_observations_for_fixture(weather_fixture)
                | source_observations_for_fixture(technical_fixture)
            ),
            now=weather_fixture.now,
        )
        humidity = self.field(weather, "outdoor_humidity")
        outdoor_temperature = self.field(weather, "outdoor_temperature")
        technical_available = self.field(technical, "available")
        self.assertEqual(weather.status, EvidenceGateStatus.DEGRADED)
        self.assertEqual(humidity.status, EvidenceGateStatus.DEGRADED)
        self.assertEqual(outdoor_temperature.status, EvidenceGateStatus.PASS)
        self.assertEqual(technical.status, EvidenceGateStatus.PASS)
        self.assertEqual(technical_available.status, EvidenceGateStatus.PASS)
        self.assertEqual(report.status, EvidenceGateStatus.DEGRADED)
        self.assertTrue(any(item.schema_id == "technical_device" and item.status == EvidenceGateStatus.PASS for item in report.contracts))
        self.assertIn("device", humidity.unaffected_capabilities)
        self.assertIn("cover", humidity.unaffected_capabilities)
        self.assertIsNotNone(technical_graph)

    def test_missing_live_observation_blocks_even_a_previously_healthy_graph_contract(self) -> None:
        fixture = opening_fixture()
        graph = build_fixture_graph(fixture)
        contract = graph.evaluate_contract(fixture.contract_id, fixture.schema_id, now=fixture.now)
        result = verify_benni_shadow_contract(
            contract,
            graph.registry.get(fixture.schema_id),
            source_bindings=fixture.bindings,
            source_observations={},
            now=fixture.now,
        )
        opening = self.field(result, "opening_state")
        self.assertEqual(result.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(opening.value, UNKNOWN_VALUE)
        self.assertIn("live_evidence_open", opening.reason_codes)
        self.assertNotEqual(opening.value, "closed")

    def test_lock_is_evidence_only_and_blocks_without_timestamp_or_ownership_evidence(self) -> None:
        matrix = source_binding_matrix_v1()
        canonical = next(
            record
            for record in matrix.records
            if record.source_entity == BENNI_CANONICAL_LOCK_ENTITY
        )
        self.assertEqual(canonical.disposition, BindingDisposition.CONFLICT)
        self.assertEqual(canonical.historical_source_entity, HISTORICAL_BENNI_LOCK_ENTITY)
        self.assertFalse(
            any(
                record.source_entity == HISTORICAL_BENNI_LOCK_ENTITY
                for record in matrix.records
            )
        )
        result = verify_evidence_only_binding(
            canonical,
            temporal_evidence(FreshnessOrigin.DEVICE_TIMESTAMP),
            now=FIXTURE_NOW,
            source_ownership_verified=False,
            value="locked",
        )
        self.assertEqual(result.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(result.value, UNKNOWN_VALUE)
        self.assertEqual(result.source_entity, BENNI_CANONICAL_LOCK_ENTITY)
        self.assertIn("device_timestamp_not_evidenced", result.reason_codes)
        self.assertIn("source_ownership_unverified", result.reason_codes)
        self.assertIn("source_conflict", result.reason_codes)
        self.assertFalse(result.activation_allowed)
        self.assertEqual(result.entity_ids, ())

    def test_parent_profile_or_binding_is_rejected_before_shadow_evaluation(self) -> None:
        fixture = benni_room_climate_fixture()
        graph = build_fixture_graph(fixture)
        contract = graph.evaluate_contract(fixture.contract_id, fixture.schema_id, now=fixture.now)
        observations = source_observations_for_fixture(fixture)
        with self.assertRaises(ValueError):
            verify_benni_shadow_contract(
                contract,
                graph.registry.get(fixture.schema_id),
                source_bindings=fixture.bindings,
                source_observations=observations,
                now=fixture.now,
                profile_id=ProfileId.ELTERN,
            )

        parent_binding = fixture.bindings[0].__class__(
            binding_id="parent_binding",
            source_id="parent_source",
            entity_id="sensor.parent_fixture",
            field="temperature",
            capability="room_climate",
            profile_id=ProfileId.ELTERN,
        )
        with self.assertRaises(ValueError):
            verify_benni_shadow_contract(
                contract,
                graph.registry.get(fixture.schema_id),
                source_bindings=fixture.bindings + (parent_binding,),
                source_observations=observations,
                now=fixture.now,
            )

    def test_shadow_boundary_has_no_entities_configentry_services_or_actuation(self) -> None:
        _, _, result = shadow_result_for_fixture(opening_fixture())
        self.assertEqual(result.entity_ids, ())
        self.assertFalse(result.activation_allowed)
        self.assertFalse(result.config_entry_activated)
        self.assertFalse((PACKAGE / "sensor.py").exists())
        self.assertFalse((PACKAGE / "binary_sensor.py").exists())
        self.assertFalse((PACKAGE / "cover.py").exists())
        self.assertFalse((PACKAGE / "lock.py").exists())
        forbidden_import = re.compile(
            r"(?:benni_(?:core_devices|.*policy)|core_devices|policy_[a-z_]+)"
        )
        forbidden_tokens = (
            "async_add_entities",
            "async_call",
            "call_service",
            "homeassistant.services",
        )
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, source, f"{token} in {path.name}")
            for line in source.splitlines():
                if line.startswith(("from ", "import ")):
                    self.assertIsNone(forbidden_import.search(line), line)


if __name__ == "__main__":
    unittest.main()
