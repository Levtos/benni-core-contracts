from __future__ import annotations

import re
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from custom_components.benni_core_contracts.config_flow import SUPPORTED_CONFIG_PROFILES
from custom_components.benni_core_contracts.evidence_gate import EvidenceGateStatus
from custom_components.benni_core_contracts.live_evidence import (
    HA_STATE_CHANGE_ORIGIN,
    LiveEvidenceStatus,
    ReadOnlySourceSnapshot,
    UNKNOWN_VALUE,
    assess_live_source,
    current_lock_entity_ids,
)
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    ProfileId,
    RuntimeMode,
)
from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    QualityStatus,
    SafetyStatus,
)
from custom_components.benni_core_contracts.source_binding_evidence import (
    BindingEvidenceClass,
    BENNI_CANONICAL_LOCK_ENTITY,
    HISTORICAL_BENNI_LOCK_ENTITY,
    source_binding_matrix_v1,
)

from tests.live_evidence_fixtures import (
    LIVE_FIXTURE_NOW,
    conflicting_opening_snapshot,
    fresh_ha_event_snapshot,
    lock_without_timestamp_snapshot,
    matrix_record,
    open_benni_live_report_fixture,
    restored_opening_snapshot,
    retained_weather_snapshot,
    stale_opening_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "benni_core_contracts"


class LiveEvidenceAcquisitionTests(unittest.TestCase):
    def test_real_probe_blocker_is_open_and_does_not_become_current_state(self) -> None:
        report = open_benni_live_report_fixture()
        self.assertEqual(report.status, LiveEvidenceStatus.OPEN)
        self.assertIn("api_requires_authentication", report.access_reason)
        self.assertTrue(report.fields)
        self.assertEqual(report.profile_id, ProfileId.BENNI)
        self.assertFalse(report.config_entry_activated)
        self.assertFalse(report.source_bindings_activated)
        self.assertFalse(report.published)
        self.assertEqual(report.entity_ids, ())
        self.assertTrue(report.open_fields)
        for field in report.fields:
            self.assertIsNone(field.source_owner)
            self.assertIsNone(field.last_changed)
            self.assertIsNone(field.last_updated)
            self.assertIsNone(field.device_timestamp)
            self.assertIsNone(field.received_at)
            self.assertEqual(field.evidence_class, BindingEvidenceClass.OFFEN)
            self.assertEqual(field.value, UNKNOWN_VALUE)
            if field.required:
                self.assertEqual(field.gate_status, EvidenceGateStatus.BLOCKED)

    def test_valid_non_retained_ha_event_is_a_synthetic_pass_only(self) -> None:
        record = matrix_record("benni_living_climate_temperature")
        snapshot = fresh_ha_event_snapshot(
            record.source_entity,
            state=21.4,
            attributes={"unit_of_measurement": "°C"},
        )
        result = assess_live_source(record, snapshot, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(result.status, LiveEvidenceStatus.PASS)
        self.assertEqual(result.gate_status, EvidenceGateStatus.PASS)
        self.assertEqual(result.contract_id, "room_climate")
        self.assertEqual(result.schema_version, 1)
        self.assertEqual(result.value, 21.4)
        self.assertEqual(result.source_entity, record.source_entity)
        self.assertEqual(result.active_source_entity, record.source_entity)
        self.assertEqual(result.freshness, FreshnessStatus.FRESH)
        self.assertEqual(result.quality, QualityStatus.GOOD)
        self.assertEqual(result.health, HealthStatus.HEALTHY)
        self.assertEqual(result.safety, SafetyStatus.VALID)
        self.assertEqual(result.evidence_class, BindingEvidenceClass.ANNAHME)
        self.assertEqual(result.event_origin, HA_STATE_CHANGE_ORIGIN)
        self.assertIn("climate", result.affected_capabilities)
        self.assertEqual(result.fallback_chain, ("reject",))

    def test_device_timestamp_can_pass_only_when_the_matrix_proves_the_path(self) -> None:
        record = matrix_record("benni_living_climate_temperature")
        record = replace(
            record,
            allowed_freshness_origins=(
                FreshnessOrigin.DEVICE_TIMESTAMP,
                FreshnessOrigin.HA_TIMESTAMP,
            ),
            device_timestamp_present=True,
            device_timestamp_path="attributes.device_timestamp",
        )
        snapshot = ReadOnlySourceSnapshot(
            entity_id=record.source_entity,
            state=21.1,
            attributes={"device_timestamp": "2026-07-23T11:59:55+00:00"},
            available=True,
            device_timestamp=LIVE_FIXTURE_NOW - timedelta(seconds=5),
            received_at=LIVE_FIXTURE_NOW,
            source_owner="synthetic_device_probe",
        )
        result = assess_live_source(record, snapshot, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(result.status, LiveEvidenceStatus.PASS)
        self.assertEqual(result.freshness, FreshnessStatus.FRESH)

    def test_last_updated_and_received_at_alone_remain_open(self) -> None:
        record = matrix_record("benni_living_climate_temperature")
        snapshot = ReadOnlySourceSnapshot(
            entity_id=record.source_entity,
            state=21.0,
            available=True,
            last_updated=LIVE_FIXTURE_NOW,
            received_at=LIVE_FIXTURE_NOW,
            source_owner="synthetic_source_owner",
        )
        result = assess_live_source(record, snapshot, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(result.status, LiveEvidenceStatus.OPEN)
        self.assertEqual(result.gate_status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(result.freshness, FreshnessStatus.UNKNOWN)
        self.assertIn("freshness_not_evidenced", result.reason_codes)
        self.assertEqual(result.value, UNKNOWN_VALUE)

    def test_battery_value_does_not_prove_freshness(self) -> None:
        record = matrix_record("benni_technical_rollo_battery")
        snapshot = ReadOnlySourceSnapshot(
            entity_id=record.source_entity,
            state=78,
            attributes={"unit_of_measurement": "%"},
            available=True,
            last_updated=LIVE_FIXTURE_NOW,
            received_at=LIVE_FIXTURE_NOW,
            source_owner="synthetic_cover_probe",
        )
        result = assess_live_source(record, snapshot, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(result.status, LiveEvidenceStatus.OPEN)
        self.assertEqual(result.freshness, FreshnessStatus.UNKNOWN)
        self.assertIn("freshness_not_evidenced", result.reason_codes)
        self.assertEqual(result.value, UNKNOWN_VALUE)

    def test_unverified_source_owner_remains_open_with_a_fresh_timestamp(self) -> None:
        record = matrix_record("benni_kitchen_climate_temperature")
        snapshot = fresh_ha_event_snapshot(
            record.source_entity,
            state=20.8,
            source_owner=None,
        )
        result = assess_live_source(record, snapshot, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(result.status, LiveEvidenceStatus.OPEN)
        self.assertEqual(result.gate_status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(result.freshness, FreshnessStatus.FRESH)
        self.assertIn("source_ownership_unverified", result.reason_codes)
        self.assertEqual(result.value, UNKNOWN_VALUE)

    def test_retained_weather_is_degraded_and_not_fresh(self) -> None:
        record = matrix_record("benni_weather_outdoor_humidity_weather")
        result = assess_live_source(
            record,
            retained_weather_snapshot(),
            checked_at=LIVE_FIXTURE_NOW,
        )
        self.assertEqual(result.status, LiveEvidenceStatus.DEGRADED)
        self.assertEqual(result.gate_status, EvidenceGateStatus.DEGRADED)
        self.assertEqual(result.freshness, FreshnessStatus.SUSPECT)
        self.assertEqual(result.quality, QualityStatus.SUSPECT)
        self.assertEqual(result.value, UNKNOWN_VALUE)
        self.assertIn("source_retained", result.reason_codes)

    def test_stale_and_restored_opening_never_claim_a_physical_state(self) -> None:
        stale = assess_live_source(
            matrix_record("benni_opening_kitchen_patio_open"),
            stale_opening_snapshot(),
            checked_at=LIVE_FIXTURE_NOW,
        )
        restored = assess_live_source(
            matrix_record("benni_opening_living_left_open"),
            restored_opening_snapshot(),
            checked_at=LIVE_FIXTURE_NOW,
        )
        for result, freshness, reason in (
            (stale, FreshnessStatus.STALE, "source_stale"),
            (restored, FreshnessStatus.RESTORED, "source_restored"),
        ):
            self.assertEqual(result.status, LiveEvidenceStatus.BLOCKED)
            self.assertEqual(result.gate_status, EvidenceGateStatus.BLOCKED)
            self.assertEqual(result.value, UNKNOWN_VALUE)
            self.assertEqual(result.freshness, freshness)
            self.assertEqual(result.safety, SafetyStatus.UNKNOWN)
            self.assertIn(reason, result.reason_codes)

    def test_conflicting_opening_sources_are_blocked_and_value_is_unknown(self) -> None:
        result = assess_live_source(
            matrix_record("benni_opening_living_left_open"),
            conflicting_opening_snapshot(),
            checked_at=LIVE_FIXTURE_NOW,
        )
        self.assertEqual(result.status, LiveEvidenceStatus.BLOCKED)
        self.assertEqual(result.gate_status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(result.value, UNKNOWN_VALUE)
        self.assertEqual(result.quality, QualityStatus.CONFLICT)
        self.assertEqual(result.health, HealthStatus.BLOCKED)
        self.assertIn("source_conflict", result.reason_codes)
        self.assertEqual(
            result.competing_sources,
            ("binary_sensor.living_window_right_open_contact",),
        )

    def test_missing_or_unavailable_required_source_keeps_gate_blocked(self) -> None:
        record = matrix_record("benni_weather_outdoor_temperature_sensor")
        missing = assess_live_source(record, None, checked_at=LIVE_FIXTURE_NOW)
        unavailable = assess_live_source(
            record,
            ReadOnlySourceSnapshot(
                entity_id=record.source_entity,
                state="unavailable",
                available=False,
                source_owner="synthetic_source_owner",
            ),
            checked_at=LIVE_FIXTURE_NOW,
        )
        self.assertEqual(missing.status, LiveEvidenceStatus.OPEN)
        self.assertEqual(missing.gate_status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(missing.value, UNKNOWN_VALUE)
        self.assertIn("live_snapshot_not_obtained", missing.reason_codes)
        self.assertEqual(unavailable.status, LiveEvidenceStatus.BLOCKED)
        self.assertEqual(unavailable.gate_status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(unavailable.value, UNKNOWN_VALUE)
        self.assertIn("source_unavailable", unavailable.reason_codes)
        unknown = assess_live_source(
            record,
            ReadOnlySourceSnapshot(
                entity_id=record.source_entity,
                state="unknown",
                available=True,
                source_owner="synthetic_source_owner",
            ),
            checked_at=LIVE_FIXTURE_NOW,
        )
        self.assertEqual(unknown.status, LiveEvidenceStatus.BLOCKED)
        self.assertEqual(unknown.value, UNKNOWN_VALUE)
        self.assertIn("source_state_unknown", unknown.reason_codes)

    def test_lock_without_device_timestamp_is_blocked_using_canonical_candidate(self) -> None:
        record = matrix_record("benni_lock_state_live_id_conflict")
        result = assess_live_source(
            record,
            lock_without_timestamp_snapshot(),
            checked_at=LIVE_FIXTURE_NOW,
        )
        self.assertEqual(record.source_entity, BENNI_CANONICAL_LOCK_ENTITY)
        self.assertEqual(result.source_entity, BENNI_CANONICAL_LOCK_ENTITY)
        self.assertEqual(result.status, LiveEvidenceStatus.BLOCKED)
        self.assertEqual(result.gate_status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(result.value, UNKNOWN_VALUE)
        self.assertEqual(result.safety, SafetyStatus.UNKNOWN)
        self.assertIn("source_conflict", result.reason_codes)
        self.assertEqual(current_lock_entity_ids()[0], BENNI_CANONICAL_LOCK_ENTITY)
        self.assertEqual(current_lock_entity_ids()[1], HISTORICAL_BENNI_LOCK_ENTITY)

    def test_historical_lock_id_is_rejected_and_never_repaired(self) -> None:
        with self.assertRaises(ValueError):
            ReadOnlySourceSnapshot(
                entity_id=HISTORICAL_BENNI_LOCK_ENTITY,
                state="locked",
            )
        canonical = matrix_record("benni_lock_state_live_id_conflict")
        historical_record = replace(
            canonical,
            source_entity=HISTORICAL_BENNI_LOCK_ENTITY,
            historical_source_entity=None,
            ha_domain=None,
        )
        with self.assertRaises(ValueError):
            assess_live_source(historical_record, None, checked_at=LIVE_FIXTURE_NOW)

    def test_cover_position_stays_evidence_only_even_with_a_fresh_snapshot(self) -> None:
        record = matrix_record("benni_rollo_cover_position_evidence_only")
        record = replace(
            record,
            allowed_freshness_origins=(FreshnessOrigin.HA_TIMESTAMP,),
            ha_state_change_usable=True,
            ha_observation_path="last_changed",
        )
        snapshot = fresh_ha_event_snapshot(
            record.source_entity,
            state="open",
            attributes={"current_position": 100},
            source_owner="synthetic_cover_probe",
        )
        result = assess_live_source(record, snapshot, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(result.status, LiveEvidenceStatus.BLOCKED)
        self.assertEqual(result.value, UNKNOWN_VALUE)
        self.assertIn("binding_not_publishable", result.reason_codes)
        self.assertEqual(result.active_source_entity, None)

    def test_parent_source_record_is_rejected_before_acquisition(self) -> None:
        parent = next(
            record
            for record in source_binding_matrix_v1().records
            if record.profile_id == ProfileId.ELTERN
        )
        with self.assertRaises(ValueError):
            assess_live_source(parent, None, checked_at=LIVE_FIXTURE_NOW)
        self.assertEqual(SUPPORTED_CONFIG_PROFILES, ("benni",))

    def test_snapshot_sanitisation_rejects_secret_like_attributes(self) -> None:
        with self.assertRaises(ValueError):
            ReadOnlySourceSnapshot(
                entity_id="sensor.fixture_temperature",
                state=21.0,
                attributes={"access_token": "not-stored"},
            )

    def test_matrix_is_the_only_candidate_universe_and_parent_is_not_in_report(self) -> None:
        matrix = source_binding_matrix_v1()
        report = open_benni_live_report_fixture()
        benni_ids = {
            record.binding_id
            for record in matrix.records
            if record.profile_id == ProfileId.BENNI
        }
        parent_ids = {
            record.binding_id
            for record in matrix.records
            if record.profile_id == ProfileId.ELTERN
        }
        self.assertTrue({field.binding_id for field in report.fields}.issubset(benni_ids))
        self.assertFalse({field.binding_id for field in report.fields} & parent_ids)
        self.assertNotIn(HISTORICAL_BENNI_LOCK_ENTITY, report.source_entities)

    def test_boundary_stays_shadow_only_without_entities_or_write_surfaces(self) -> None:
        report = open_benni_live_report_fixture()
        self.assertEqual(report.entity_ids, ())
        self.assertFalse(report.config_entry_activated)
        self.assertFalse(report.source_bindings_activated)
        self.assertFalse(report.published)
        self.assertEqual(
            ConfigModel(mode=RuntimeMode.SHADOW_ONLY).bindings,
            (),
        )
        for filename in ("sensor.py", "binary_sensor.py", "cover.py", "lock.py"):
            self.assertFalse((PACKAGE / filename).exists())
        forbidden_tokens = (
            "async_add_entities",
            "async_call",
            "call_service",
            "homeassistant.services",
        )
        forbidden_import = re.compile(
            r"(?:benni_(?:core_devices|.*policy)|core_devices|policy_[a-z_]+)"
        )
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, source, path.name)
            for line in source.splitlines():
                if line.startswith(("from ", "import ")):
                    self.assertIsNone(forbidden_import.search(line), line)


if __name__ == "__main__":
    unittest.main()
