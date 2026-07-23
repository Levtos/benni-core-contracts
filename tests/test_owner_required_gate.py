from __future__ import annotations

import unittest
from dataclasses import replace

from custom_components.benni_core_contracts.evidence_gate import EvidenceGateStatus
from custom_components.benni_core_contracts.const import SUPPORTED_CONFIG_PROFILES
from custom_components.benni_core_contracts.models import ProfileId, ProfileScope
from custom_components.benni_core_contracts.owner_required_gate import (
    RequiredEvidenceSelection,
    build_benni_owner_required_gate_v1,
)
from custom_components.benni_core_contracts.profiles import profile_definition
from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    FreshnessStatus,
    SafetyStatus,
    ValueState,
)
from custom_components.benni_core_contracts.source_binding_evidence import (
    BENNI_CANONICAL_LOCK_ENTITY,
    HISTORICAL_BENNI_LOCK_ENTITY,
    BindingDisposition,
    SourceBindingEvidenceMatrix,
    assess_source_binding_evidence,
    source_binding_matrix_v1,
)

from source_binding_fixtures import (
    FIXTURE_NOW,
    benni_binding_fixture,
    benni_owner_gate_pass_inputs,
    benni_owner_required_gate_fixture,
    eltern_binding_fixture,
    lock_without_reliable_source_fixture,
    temporal_evidence,
)


class OwnerRequiredFieldGateTests(unittest.TestCase):
    def test_gate_is_benni_only_and_parent_is_parent_future(self) -> None:
        matrix = source_binding_matrix_v1()
        gate = benni_owner_required_gate_fixture()

        self.assertEqual(gate.profile_id, ProfileId.BENNI)
        self.assertEqual(gate.activation_scope, ProfileScope.BENNI_PRODUCTION)
        self.assertEqual(gate.parent_profile, ProfileId.ELTERN)
        self.assertEqual(gate.parent_scope, ProfileScope.PARENT_FUTURE)
        self.assertFalse(gate.activation_allowed)
        self.assertTrue(gate.specs)
        self.assertTrue(all(spec.profile_id == ProfileId.BENNI for spec in gate.specs))
        self.assertTrue(
            all(record.is_benni_production_scope for record in matrix.active_candidates())
        )
        self.assertTrue(matrix.parent_future_records())
        self.assertTrue(
            all(
                record.activation_scope == ProfileScope.PARENT_FUTURE
                and not record.is_activatable_candidate
                for record in matrix.parent_future_records()
            )
        )
        self.assertEqual(
            profile_definition(ProfileId.BENNI).activation_scope,
            ProfileScope.BENNI_PRODUCTION,
        )
        self.assertTrue(profile_definition(ProfileId.BENNI).productive_target)
        self.assertEqual(SUPPORTED_CONFIG_PROFILES, ("benni",))
        self.assertTrue(profile_definition(ProfileId.BENNI).shadow_runtime_allowed)
        self.assertEqual(
            profile_definition(ProfileId.ELTERN).activation_scope,
            ProfileScope.PARENT_FUTURE,
        )
        self.assertFalse(profile_definition(ProfileId.ELTERN).productive_target)
        self.assertFalse(profile_definition(ProfileId.ELTERN).config_activation_allowed)
        self.assertFalse(profile_definition(ProfileId.ELTERN).shadow_runtime_allowed)

    def test_required_field_set_is_exactly_the_current_benni_schema_set(self) -> None:
        gate = benni_owner_required_gate_fixture()
        self.assertEqual(
            {spec.key for spec in gate.specs},
            {
                "room_climate.v1:temperature:living",
                "room_climate.v1:temperature:kitchen",
                "room_climate.v1:temperature:bathroom",
                "room_climate.v1:available:living",
                "room_climate.v1:available:kitchen",
                "room_climate.v1:available:bathroom",
                "opening.v1:opening_state",
                "opening.v1:available",
                "weather_environment.v1:outdoor_temperature:outdoor",
                "weather_environment.v1:available:outdoor",
                "technical_device.v1:available",
            },
        )
        self.assertFalse(any("lock" in spec.field for spec in gate.specs))
        self.assertFalse(any("cover" in spec.field for spec in gate.specs))

    def test_fresh_inputs_can_pass_but_never_authorize_activation(self) -> None:
        gate = benni_owner_required_gate_fixture()
        observations, values, derived_statuses = benni_owner_gate_pass_inputs(gate)

        result = gate.evaluate(
            observations=observations,
            values=values,
            derived_statuses=derived_statuses,
            now=FIXTURE_NOW,
        )

        self.assertEqual(result.status, EvidenceGateStatus.PASS)
        self.assertTrue(result.required_fields_ready)
        self.assertFalse(result.activation_allowed)
        opening = next(field for field in result.fields if field.field == "opening_state")
        self.assertEqual(opening.value_state, ValueState.VALID)
        self.assertTrue(opening.physical_claim_allowed)
        self.assertEqual(opening.safety, SafetyStatus.VALID)

    def test_missing_observation_blocks_gate_and_does_not_claim_physical_state(self) -> None:
        gate = benni_owner_required_gate_fixture()
        observations, values, derived_statuses = benni_owner_gate_pass_inputs(gate)
        opening = gate.spec("opening.v1:opening_state")
        values[opening.key] = "open"
        observations.pop(opening.binding_ids[0])

        result = gate.evaluate(
            observations=observations,
            values=values,
            derived_statuses=derived_statuses,
            now=FIXTURE_NOW,
        )
        decision = next(field for field in result.fields if field.key == opening.key)

        self.assertEqual(result.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(decision.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(decision.value_state, ValueState.UNKNOWN)
        self.assertFalse(decision.physical_claim_allowed)
        self.assertEqual(decision.safety, SafetyStatus.UNKNOWN)
        self.assertIn("source_unavailable", decision.reasons)

    def test_retained_restored_stale_and_conflict_never_pass_physical_gate(self) -> None:
        cases = (
            (FreshnessOrigin.RETAINED_MQTT, 10, "source_retained", FreshnessStatus.SUSPECT),
            (FreshnessOrigin.RESTORE, 10, "source_restored", FreshnessStatus.RESTORED),
            (FreshnessOrigin.HA_TIMESTAMP, 3600, "freshness_ttl_exceeded", FreshnessStatus.STALE),
        )
        for origin, age, reason, freshness in cases:
            gate = benni_owner_required_gate_fixture()
            observations, values, derived_statuses = benni_owner_gate_pass_inputs(gate)
            opening = gate.spec("opening.v1:opening_state")
            values[opening.key] = "open"
            observations[opening.binding_ids[0]] = temporal_evidence(
                origin,
                age_seconds=age,
            )
            result = gate.evaluate(
                observations=observations,
                values=values,
                derived_statuses=derived_statuses,
                now=FIXTURE_NOW,
            )
            decision = next(field for field in result.fields if field.key == opening.key)
            self.assertEqual(decision.status, EvidenceGateStatus.BLOCKED, origin.value)
            self.assertEqual(decision.value_state, ValueState.UNKNOWN, origin.value)
            self.assertFalse(decision.physical_claim_allowed, origin.value)
            self.assertIn(reason, decision.reasons, origin.value)
            self.assertEqual(decision.freshness, freshness, origin.value)

        base_gate = benni_owner_required_gate_fixture()
        observations, values, derived_statuses = benni_owner_gate_pass_inputs(base_gate)
        opening = base_gate.spec("opening.v1:opening_state")
        values[opening.key] = "open"
        records = list(base_gate.matrix.records)
        target = opening.binding_ids[0]
        index = next(i for i, record in enumerate(records) if record.binding_id == target)
        records[index] = replace(records[index], disposition=BindingDisposition.CONFLICT)
        conflict_gate = build_benni_owner_required_gate_v1(
            matrix=SourceBindingEvidenceMatrix(
                version=base_gate.matrix.version,
                records=tuple(records),
            )
        )
        result = conflict_gate.evaluate(
            observations=observations,
            values=values,
            derived_statuses=derived_statuses,
            now=FIXTURE_NOW,
        )
        decision = next(field for field in result.fields if field.key == opening.key)
        self.assertEqual(decision.status, EvidenceGateStatus.BLOCKED)
        self.assertEqual(decision.value_state, ValueState.UNKNOWN)
        self.assertFalse(decision.physical_claim_allowed)
        self.assertIn("source_conflict", decision.reasons)

    def test_degraded_is_visible_for_partial_nonphysical_evidence(self) -> None:
        gate = benni_owner_required_gate_fixture()
        original = gate.spec("room_climate.v1:temperature:living")
        alternatives = tuple(
            record
            for record in gate.matrix.records
            if record.profile_id == ProfileId.BENNI
            and record.contract_ref == "room_climate.v1"
            and record.field == "temperature"
        )
        degraded = replace(
            original,
            key="synthetic:room_temperature",
            room=None,
            binding_ids=tuple(record.binding_id for record in alternatives),
            source_entities=tuple(record.source_entity for record in alternatives),
            selection=RequiredEvidenceSelection.ANY_HEALTHY,
        )
        gate = replace(gate, specs=(degraded,))
        observations = {
            alternatives[0].binding_id: temporal_evidence(FreshnessOrigin.HA_TIMESTAMP),
            alternatives[1].binding_id: temporal_evidence(
                FreshnessOrigin.HA_TIMESTAMP,
                age_seconds=3600,
            ),
        }
        result = gate.evaluate(
            observations=observations,
            values={degraded.key: 18.5},
            now=FIXTURE_NOW,
        )
        decision = result.fields[0]
        self.assertEqual(decision.status, EvidenceGateStatus.DEGRADED)
        self.assertEqual(decision.health.value, "degraded")
        self.assertEqual(decision.quality.value, "stale")
        self.assertEqual(decision.safety.value, "conservative")
        self.assertFalse(result.required_fields_ready)

    def test_false_availability_does_not_pass_required_gate(self) -> None:
        gate = benni_owner_required_gate_fixture()
        observations, values, derived_statuses = benni_owner_gate_pass_inputs(gate)
        key = "room_climate.v1:available:living"
        values[key] = False
        result = gate.evaluate(
            observations=observations,
            values=values,
            derived_statuses=derived_statuses,
            now=FIXTURE_NOW,
        )
        decision = next(field for field in result.fields if field.key == key)
        self.assertEqual(decision.status, EvidenceGateStatus.BLOCKED)
        self.assertIn("required_availability_false", decision.reasons)

    def test_lock_and_position_evidence_remain_outside_current_required_schema(self) -> None:
        matrix = source_binding_matrix_v1()
        lock_records = [
            record for record in matrix.records if record.field == "lock_state"
        ]
        canonical = [
            record
            for record in lock_records
            if record.source_entity == BENNI_CANONICAL_LOCK_ENTITY
        ]
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0].evidence_class.value, "LIVE_VERIFIZIERT")
        self.assertEqual(canonical[0].historical_source_entity, HISTORICAL_BENNI_LOCK_ENTITY)
        self.assertEqual(
            [record for record in lock_records if record.source_entity == HISTORICAL_BENNI_LOCK_ENTITY],
            [],
        )
        self.assertFalse(
            any(spec.field in {"lock_state", "cover_position"} for spec in benni_owner_required_gate_fixture().specs)
        )
        missing = assess_source_binding_evidence(
            canonical[0],
            None,
            now=FIXTURE_NOW,
            ttl_seconds=600,
        )
        self.assertEqual(missing.freshness, FreshnessStatus.UNKNOWN)
        self.assertEqual(missing.reason, "source_unavailable")

        position = next(
            record
            for record in matrix.records
            if record.binding_id == "benni_rollo_cover_position_evidence_only"
        )
        position_missing = assess_source_binding_evidence(
            position,
            None,
            now=FIXTURE_NOW,
            ttl_seconds=600,
        )
        self.assertEqual(position_missing.freshness, FreshnessStatus.UNKNOWN)
        self.assertEqual(position_missing.reason, "source_unavailable")

    def test_shared_fixture_code_remains_profile_generic(self) -> None:
        benni = benni_binding_fixture()
        eltern = eltern_binding_fixture()
        self.assertTrue(benni)
        self.assertTrue(eltern)
        self.assertTrue(all(record.profile_id == ProfileId.BENNI for record in benni))
        self.assertTrue(all(record.profile_id == ProfileId.ELTERN for record in eltern))
        self.assertNotEqual(
            {record.field for record in benni},
            set(),
        )
        self.assertNotEqual(
            {record.field for record in eltern},
            set(),
        )

    def test_no_entity_surface_and_no_production_binding_activation(self) -> None:
        gate = benni_owner_required_gate_fixture()
        package = __import__(
            "pathlib"
        ).Path(__file__).resolve().parents[1] / "custom_components" / "benni_core_contracts"
        self.assertFalse((package / "sensor.py").exists())
        self.assertFalse((package / "binary_sensor.py").exists())
        self.assertFalse(gate.activation_allowed)
        self.assertFalse(any(record.production_binding_allowed for record in gate.matrix.records))
        self.assertEqual(gate.as_dict()["parent_scope"], ProfileScope.PARENT_FUTURE.value)
        config_flow = (package / "config_flow.py").read_text(encoding="utf-8")
        adapter = (package / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("SUPPORTED_CONFIG_PROFILES", config_flow)
        self.assertIn("shadow_runtime_allowed", adapter)


if __name__ == "__main__":
    unittest.main()
