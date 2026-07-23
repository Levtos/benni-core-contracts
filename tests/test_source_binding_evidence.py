from __future__ import annotations

import json
import re
import unittest
from dataclasses import replace
from pathlib import Path

from custom_components.benni_core_contracts.contracts import default_schema_registry
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    ProfileId,
    RuntimeMode,
)
from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    FreshnessStatus,
)
from custom_components.benni_core_contracts.source_binding_evidence import (
    BindingDisposition,
    BindingEvidenceClass,
    BindingKind,
    SourceBindingEvidence,
    assess_source_binding_evidence,
    evidence_classes,
    source_binding_matrix_v1,
)

from source_binding_fixtures import (
    benni_binding_fixture,
    conflicting_sources_fixture,
    eltern_binding_fixture,
    freshness_for_fixture,
    lock_without_reliable_source_fixture,
    missing_eltern_evidence_fixture,
    missing_timestamp_fixture,
    retained_mqtt_fixture,
    restore_fixture,
    rollo_competing_cover_sources_fixture,
    stale_fixture,
    temporal_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "benni_core_contracts"


class SourceBindingEvidenceTests(unittest.TestCase):
    def test_matrix_is_versioned_and_uses_only_the_declared_evidence_classes(self) -> None:
        matrix = source_binding_matrix_v1()
        self.assertEqual(matrix.version, 1)
        self.assertEqual(
            set(evidence_classes()),
            {
                BindingEvidenceClass.IMPLEMENTIERT,
                BindingEvidenceClass.KONFIGURIERT,
                BindingEvidenceClass.LIVE_VERIFIZIERT,
                BindingEvidenceClass.DOKUMENTIERT,
                BindingEvidenceClass.OFFEN,
                BindingEvidenceClass.ANNAHME,
            },
        )
        self.assertTrue(
            {record.evidence_class for record in matrix.records}.issubset(
                set(evidence_classes())
            )
        )
        self.assertEqual(
            len({record.binding_id for record in matrix.records}),
            len(matrix.records),
        )

    def test_matrix_has_every_v1_field_for_both_profiles(self) -> None:
        matrix = source_binding_matrix_v1()
        for profile in (ProfileId.BENNI, ProfileId.ELTERN):
            records = matrix.for_profile(profile)
            for schema in default_schema_registry().all():
                fields = {
                    record.field
                    for record in records
                    if record.contract_ref == f"{schema.schema_id}.v{schema.version}"
                }
                self.assertEqual(
                    fields,
                    {field.name for field in schema.fields},
                    f"{profile.value}:{schema.schema_id}",
                )

    def test_benni_confirmed_fixture_contains_all_required_source_evidence(self) -> None:
        records = benni_binding_fixture()
        self.assertTrue(records)
        for contract_ref in (
            "room_climate.v1",
            "opening.v1",
            "weather_environment.v1",
            "technical_device.v1",
        ):
            schema = default_schema_registry().get(contract_ref.rsplit(".", 1)[0])
            for field in schema.fields:
                if not field.required:
                    continue
                field_records = [
                    record
                    for record in records
                    if record.contract_ref == contract_ref
                    and record.field == field.name
                ]
                self.assertTrue(field_records, f"missing Benni field {contract_ref}:{field.name}")
                self.assertTrue(
                    any(
                        record.disposition in {
                            BindingDisposition.CANDIDATE,
                            BindingDisposition.DERIVED,
                        }
                        for record in field_records
                    ),
                    f"required Benni field not represented: {contract_ref}:{field.name}",
                )

    def test_eltern_fixture_is_evidence_complete_only_for_the_proven_parts(self) -> None:
        records = eltern_binding_fixture()
        self.assertTrue(records)
        for contract_ref, field in (
            ("room_climate.v1", "temperature"),
            ("opening.v1", "opening_state"),
            ("weather_environment.v1", "outdoor_temperature"),
        ):
            self.assertTrue(
                any(
                    record.contract_ref == contract_ref
                    and record.field == field
                    and record.evidence_class == BindingEvidenceClass.LIVE_VERIFIZIERT
                    for record in records
                )
            )
        self.assertFalse(
            any(
                record.contract_ref == "technical_device.v1"
                and record.field == "available"
                and record.disposition == BindingDisposition.CANDIDATE
                for record in records
            )
        )

    def test_missing_parent_evidence_has_no_placeholder_entity(self) -> None:
        records = missing_eltern_evidence_fixture()
        self.assertTrue(records)
        self.assertTrue(all(record.source_entity is None for record in records))
        self.assertTrue(all(record.evidence_class == BindingEvidenceClass.OFFEN for record in records))
        self.assertTrue(all(record.disposition == BindingDisposition.OPEN for record in records))
        self.assertTrue(
            any(record.field == "cover_position" for record in records)
        )
        self.assertTrue(any(record.field == "lock_state" for record in records))

    def test_matrix_records_expose_all_required_evidence_columns(self) -> None:
        required_keys = {
            "profile_id",
            "contract",
            "field",
            "logical_role",
            "source_entity",
            "ha_domain",
            "room",
            "required",
            "allowed_freshness_origins",
            "device_timestamp_present",
            "ha_state_change_usable",
            "retained_mqtt_possible",
            "source_attribute_path",
            "device_timestamp_path",
            "ha_observation_path",
            "fallback",
            "quality_relevance",
            "safety_relevance",
            "evidence_class",
            "consumers",
            "open_question",
            "historical_source_entity",
            "activation_scope",
        }
        for record in source_binding_matrix_v1().records:
            self.assertTrue(required_keys.issubset(record.as_dict()))
            if record.source_entity is not None:
                self.assertEqual(
                    record.ha_domain,
                    record.source_entity.split(".", 1)[0],
                )

    def test_missing_device_timestamps_never_become_device_timestamp_evidence(self) -> None:
        records = missing_timestamp_fixture()
        self.assertTrue(records)
        self.assertTrue(
            all(
                record.device_timestamp_present is False
                and record.device_timestamp_path is None
                for record in records
            )
        )
        physical = [
            record
            for record in records
            if record.field in {"opening_state", "cover_position", "lock_state"}
        ]
        self.assertTrue(physical)
        self.assertTrue(
            all(
                record.fallback.action.value == "reject"
                for record in physical
            )
        )
        self.assertTrue(
            all(
                record.field != "lock_state"
                or (
                    record.allowed_freshness_origins
                    == (FreshnessOrigin.DEVICE_TIMESTAMP,)
                    and record.ha_state_change_usable is False
                )
                for record in physical
            )
        )

    def test_retained_mqtt_fixture_is_suspect_and_rejected_for_fresh_gate(self) -> None:
        fixture = retained_mqtt_fixture()
        freshness, reason = freshness_for_fixture(fixture)
        self.assertEqual(freshness, fixture.expected_freshness)
        self.assertEqual(reason, fixture.expected_reason)
        self.assertFalse(fixture.expected_accepted)
        self.assertTrue(fixture.record.retained_mqtt_possible)
        self.assertNotEqual(freshness, FreshnessStatus.FRESH)

    def test_restore_fixture_is_restored_and_rejected_for_fresh_gate(self) -> None:
        fixture = restore_fixture()
        freshness, reason = freshness_for_fixture(fixture)
        self.assertEqual(freshness, FreshnessStatus.RESTORED)
        self.assertEqual(reason, "restore_value_is_not_fresh")
        self.assertFalse(fixture.expected_accepted)
        self.assertNotEqual(freshness, FreshnessStatus.FRESH)

    def test_stale_fixture_does_not_pass_even_with_an_ha_timestamp(self) -> None:
        fixture = stale_fixture()
        freshness, _ = freshness_for_fixture(fixture)
        self.assertEqual(freshness, FreshnessStatus.STALE)
        self.assertFalse(fixture.expected_accepted)

    def test_gate_assessment_accepts_only_an_allowed_real_ha_event(self) -> None:
        record = next(
            item
            for item in source_binding_matrix_v1().records
            if item.binding_id == "benni_living_climate_temperature"
        )
        assessment = assess_source_binding_evidence(
            record,
            temporal_evidence(FreshnessOrigin.HA_TIMESTAMP),
            now=temporal_evidence(FreshnessOrigin.HA_TIMESTAMP).received_at,
            ttl_seconds=900,
        )
        self.assertTrue(assessment.accepted)
        self.assertFalse(assessment.activation_allowed)
        self.assertEqual(assessment.reason, "evidence_valid_not_activated")
        self.assertEqual(assessment.freshness, FreshnessStatus.FRESH)

    def test_gate_assessment_rejects_device_timestamp_without_a_proven_path(self) -> None:
        record = next(
            item
            for item in source_binding_matrix_v1().records
            if item.binding_id == "benni_living_climate_temperature"
        )
        assessment = assess_source_binding_evidence(
            record,
            temporal_evidence(FreshnessOrigin.DEVICE_TIMESTAMP),
            now=temporal_evidence(FreshnessOrigin.DEVICE_TIMESTAMP).received_at,
            ttl_seconds=900,
        )
        self.assertFalse(assessment.accepted)
        self.assertEqual(assessment.freshness, FreshnessStatus.UNKNOWN)
        self.assertEqual(assessment.reason, "device_timestamp_not_evidenced")

    def test_gate_assessment_preserves_missing_retained_restore_and_stale_reasons(self) -> None:
        retained = retained_mqtt_fixture()
        retained_assessment = assess_source_binding_evidence(
            retained.record,
            temporal_evidence(retained.observation_origin),
            now=temporal_evidence(retained.observation_origin).received_at,
            ttl_seconds=900,
        )
        self.assertFalse(retained_assessment.accepted)
        self.assertEqual(retained_assessment.freshness, FreshnessStatus.SUSPECT)
        self.assertEqual(retained_assessment.reason, "source_retained")

        restored = restore_fixture()
        restored_assessment = assess_source_binding_evidence(
            restored.record,
            temporal_evidence(restored.observation_origin),
            now=temporal_evidence(restored.observation_origin).received_at,
            ttl_seconds=900,
        )
        self.assertFalse(restored_assessment.accepted)
        self.assertEqual(restored_assessment.freshness, FreshnessStatus.RESTORED)
        self.assertEqual(restored_assessment.reason, "source_restored")

        stale = stale_fixture()
        stale_evidence = temporal_evidence(
            stale.observation_origin,
            age_seconds=stale.age_seconds,
        )
        stale_assessment = assess_source_binding_evidence(
            stale.record,
            stale_evidence,
            now=stale_evidence.received_at,
            ttl_seconds=900,
        )
        self.assertFalse(stale_assessment.accepted)
        self.assertEqual(stale_assessment.freshness, FreshnessStatus.STALE)
        self.assertEqual(stale_assessment.reason, "freshness_ttl_exceeded")

    def test_gate_assessment_blocks_missing_and_conflicting_sources(self) -> None:
        missing = next(
            item
            for item in source_binding_matrix_v1().records
            if item.binding_id == "eltern_lock_state_open"
        )
        missing_assessment = assess_source_binding_evidence(
            missing,
            None,
            now=temporal_evidence(FreshnessOrigin.UNKNOWN).received_at,
            ttl_seconds=900,
        )
        self.assertFalse(missing_assessment.accepted)
        self.assertEqual(missing_assessment.freshness, FreshnessStatus.UNKNOWN)
        self.assertEqual(missing_assessment.reason, "source_unavailable")

        conflict = conflicting_sources_fixture()[0]
        conflict_evidence = temporal_evidence(FreshnessOrigin.HA_TIMESTAMP)
        conflict_assessment = assess_source_binding_evidence(
            conflict,
            conflict_evidence,
            now=conflict_evidence.received_at,
            ttl_seconds=900,
        )
        self.assertFalse(conflict_assessment.accepted)
        self.assertEqual(conflict_assessment.freshness, FreshnessStatus.FRESH)
        self.assertEqual(conflict_assessment.reason, "source_conflict")

    def test_weather_conflict_has_no_implicitly_selected_source(self) -> None:
        records = conflicting_sources_fixture()
        self.assertEqual(len(records), 2)
        self.assertEqual(
            {record.source_entity for record in records},
            {"weather.forecast_home", "weather.pirateweather"},
        )
        self.assertTrue(
            all(record.disposition == BindingDisposition.CONFLICT for record in records)
        )
        matrix = source_binding_matrix_v1()
        self.assertFalse(
            any(
                record.field == "weather_state"
                and record.profile_id == ProfileId.ELTERN
                and record.disposition == BindingDisposition.CANDIDATE
                for record in matrix.records
            )
        )

    def test_wrong_physical_source_domain_is_rejected(self) -> None:
        record = next(
            item
            for item in source_binding_matrix_v1().records
            if item.binding_id == "benni_lock_state_live_id_conflict"
        )
        with self.assertRaises(ValueError):
            replace(
                record,
                source_entity="sensor.living_climate_temperature",
                ha_domain=None,
            )

    def test_rollo_competing_cover_sources_do_not_create_a_position_winner(self) -> None:
        records = rollo_competing_cover_sources_fixture()
        self.assertEqual(
            {record.source_entity for record in records},
            {
                "cover.wohnbereich_thermo_verdunklungsrollo",
                "cover.living_blackout_blind",
            },
        )
        self.assertTrue(
            any(record.evidence_class == BindingEvidenceClass.LIVE_VERIFIZIERT for record in records)
        )
        self.assertTrue(
            any(record.disposition == BindingDisposition.EXCLUDED for record in records)
        )
        self.assertTrue(all(not record.is_activatable_candidate for record in records))

    def test_lock_without_reliable_source_cannot_pass_safety_evidence(self) -> None:
        records = lock_without_reliable_source_fixture()
        self.assertTrue(records)
        self.assertTrue(
            all(record.disposition != BindingDisposition.CANDIDATE for record in records)
        )
        live = next(
            record
            for record in records
            if record.source_entity == "lock.flur_aqara_smart_lock_u200"
        )
        self.assertEqual(live.evidence_class, BindingEvidenceClass.LIVE_VERIFIZIERT)
        self.assertFalse(live.device_timestamp_present)
        self.assertFalse(live.ha_state_change_usable)
        self.assertEqual(live.fallback.action.value, "reject")
        parent = next(
            record
            for record in records
            if record.profile_id == ProfileId.ELTERN
        )
        self.assertIsNone(parent.source_entity)
        self.assertEqual(parent.evidence_class, BindingEvidenceClass.OFFEN)

    def test_matrix_is_not_a_second_config_source(self) -> None:
        matrix = source_binding_matrix_v1()
        config = ConfigModel(mode=RuntimeMode.SHADOW_ONLY)
        self.assertEqual(config.bindings, ())
        self.assertFalse(any(record.production_binding_allowed for record in matrix.records))
        self.assertFalse(any(record.is_activatable_candidate for record in matrix.records))
        payload = matrix.as_dict()
        self.assertFalse(payload["production_binding_allowed"])
        self.assertEqual(payload["production_profile"], "benni")
        self.assertEqual(payload["parent_profile_scope"], "parent_future")
        json.dumps(payload)

    def test_profiles_use_one_model_and_no_separate_logic_tree(self) -> None:
        benni_ids = {record.binding_id.split("_", 1)[1] for record in benni_binding_fixture()}
        eltern_ids = {record.binding_id.split("_", 1)[1] for record in eltern_binding_fixture()}
        self.assertTrue(benni_ids)
        self.assertTrue(eltern_ids)
        self.assertNotEqual(benni_ids, set())
        self.assertNotEqual(eltern_ids, set())
        source = (PACKAGE / "source_binding_evidence.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def _climate_records"), 1)
        self.assertEqual(source.count("def _opening_records"), 1)
        self.assertEqual(source.count("def _weather_records"), 1)
        self.assertEqual(source.count("def _technical_records"), 1)

    def test_source_binding_module_has_no_entity_or_actuation_surface(self) -> None:
        source = (PACKAGE / "source_binding_evidence.py").read_text(encoding="utf-8")
        for token in (
            "async_add_entities",
            "async_call",
            "call_service",
            "homeassistant.services",
        ):
            self.assertNotIn(token, source)
        self.assertFalse((PACKAGE / "sensor.py").exists())
        self.assertFalse((PACKAGE / "binary_sensor.py").exists())
        self.assertIsNone(
            re.search(r"^\s*(?:from|import)\s+[^#\n]*(?:core_devices|policy)", source, re.MULTILINE)
        )

    def test_all_open_physical_records_reject_safe_defaults(self) -> None:
        for record in source_binding_matrix_v1().records:
            if record.is_physical:
                self.assertEqual(record.fallback.action.value, "reject")
                self.assertNotEqual(record.fallback.action.value, "safe_default")
                if (
                    record.source_entity is None
                    and record.binding_kind == BindingKind.MISSING
                ):
                    self.assertEqual(record.evidence_class, BindingEvidenceClass.OFFEN)

    def test_legacy_and_policy_sources_are_not_active_matrix_candidates(self) -> None:
        matrix = source_binding_matrix_v1()
        excluded = next(
            record
            for record in matrix.records
            if record.binding_id == "benni_rollo_legacy_policy_cover_excluded"
        )
        self.assertEqual(excluded.disposition, BindingDisposition.EXCLUDED)
        self.assertFalse(excluded.is_activatable_candidate)
        self.assertNotIn(
            "sensor.benni_master_living_rollo",
            {record.source_entity for record in matrix.active_candidates()},
        )
