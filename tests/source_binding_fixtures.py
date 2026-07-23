"""Synthetic Source Binding Evidence Gate fixtures.

The fixtures reuse only records from the versioned evidence matrix or explicit
no-source cases. They never write ConfigEntry data and never represent a
production activation decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    FreshnessRequirement,
    FreshnessStatus,
    TemporalEvidence,
)
from custom_components.benni_core_contracts.models import ProfileId
from custom_components.benni_core_contracts.evidence_gate import EvidenceGateStatus
from custom_components.benni_core_contracts.owner_required_gate import (
    BenniOwnerRequiredFieldGate,
    build_benni_owner_required_gate_v1,
)
from custom_components.benni_core_contracts.source_binding_evidence import (
    BindingDisposition,
    BindingEvidenceClass,
    SourceBindingEvidence,
    source_binding_matrix_v1,
)


FIXTURE_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class BindingObservationFixture:
    name: str
    record: SourceBindingEvidence
    observation_origin: FreshnessOrigin
    expected_freshness: FreshnessStatus
    expected_accepted: bool
    expected_reason: str
    age_seconds: int = 10


def benni_binding_fixture() -> tuple[SourceBindingEvidence, ...]:
    matrix = source_binding_matrix_v1()
    return tuple(
        record
        for record in matrix.for_profile(ProfileId.BENNI)
        if record.disposition
        in {BindingDisposition.CANDIDATE, BindingDisposition.DERIVED}
    )


def eltern_binding_fixture() -> tuple[SourceBindingEvidence, ...]:
    matrix = source_binding_matrix_v1()
    return tuple(
        record
        for record in matrix.for_profile(ProfileId.ELTERN)
        if record.disposition
        in {BindingDisposition.CANDIDATE, BindingDisposition.DERIVED}
    )


def missing_eltern_evidence_fixture() -> tuple[SourceBindingEvidence, ...]:
    matrix = source_binding_matrix_v1()
    return tuple(
        record
        for record in matrix.for_profile(ProfileId.ELTERN)
        if record.evidence_class == BindingEvidenceClass.OFFEN
        and record.source_entity is None
    )


def missing_timestamp_fixture() -> tuple[SourceBindingEvidence, ...]:
    matrix = source_binding_matrix_v1()
    return tuple(
        record
        for record in matrix.records
        if record.device_timestamp_present is False
        and record.source_entity is not None
    )


def retained_mqtt_fixture() -> BindingObservationFixture:
    record = next(
        item
        for item in source_binding_matrix_v1().records
        if item.binding_id == "eltern_kitchen_climate_temperature"
    )
    return BindingObservationFixture(
        name="retained_mqtt",
        record=record,
        observation_origin=FreshnessOrigin.RETAINED_MQTT,
        expected_freshness=FreshnessStatus.SUSPECT,
        expected_accepted=False,
        expected_reason="retained_mqtt_is_not_fresh_evidence",
    )


def restore_fixture() -> BindingObservationFixture:
    record = next(
        item
        for item in source_binding_matrix_v1().records
        if item.binding_id == "benni_opening_living_left_open"
    )
    return BindingObservationFixture(
        name="restore",
        record=record,
        observation_origin=FreshnessOrigin.RESTORE,
        expected_freshness=FreshnessStatus.RESTORED,
        expected_accepted=False,
        expected_reason="restore_value_is_not_fresh",
    )


def stale_fixture() -> BindingObservationFixture:
    record = next(
        item
        for item in source_binding_matrix_v1().records
        if item.binding_id == "benni_weather_outdoor_temperature_sensor"
    )
    return BindingObservationFixture(
        name="stale",
        record=record,
        observation_origin=FreshnessOrigin.HA_TIMESTAMP,
        expected_freshness=FreshnessStatus.STALE,
        expected_accepted=False,
        expected_reason="stale",
        age_seconds=3600,
    )


def conflicting_sources_fixture() -> tuple[SourceBindingEvidence, ...]:
    return tuple(
        record
        for record in source_binding_matrix_v1().records
        if record.profile_id == ProfileId.ELTERN
        and record.field == "weather_state"
        and record.disposition == BindingDisposition.CONFLICT
    )


def rollo_competing_cover_sources_fixture() -> tuple[SourceBindingEvidence, ...]:
    matrix = source_binding_matrix_v1()
    return tuple(
        record
        for record in matrix.records
        if record.profile_id == ProfileId.BENNI
        and record.field == "cover_position"
    )


def lock_without_reliable_source_fixture() -> tuple[SourceBindingEvidence, ...]:
    matrix = source_binding_matrix_v1()
    return tuple(
        record
        for record in matrix.records
        if record.field == "lock_state"
    )


def benni_owner_required_gate_fixture() -> BenniOwnerRequiredFieldGate:
    """Return the Benni-only gate without activating any binding."""

    return build_benni_owner_required_gate_v1()


def benni_owner_gate_pass_inputs(
    gate: BenniOwnerRequiredFieldGate,
) -> tuple[
    dict[str, TemporalEvidence | None],
    dict[str, object],
    dict[str, EvidenceGateStatus],
]:
    """Build synthetic fresh inputs for every Benni required-field rule."""

    observations: dict[str, TemporalEvidence | None] = {}
    values: dict[str, object] = {}
    derived_statuses: dict[str, EvidenceGateStatus] = {}
    for spec in gate.specs:
        if spec.selection.value == "derived":
            values[spec.key] = True
            derived_statuses[spec.key] = EvidenceGateStatus.PASS
            continue
        values[spec.key] = (
            "closed"
            if spec.field == "opening_state"
            else 18.5
        )
        for binding_id in spec.binding_ids:
            observations[binding_id] = temporal_evidence(FreshnessOrigin.HA_TIMESTAMP)
        derived_statuses[spec.key] = EvidenceGateStatus.PASS
    # The technical-device availability rule depends on an optional raw
    # device-state assessment; the fixture supplies that synthetic result.
    derived_statuses["technical_device.v1:device_state"] = EvidenceGateStatus.PASS
    return observations, values, derived_statuses


def temporal_evidence(
    origin: FreshnessOrigin,
    *,
    age_seconds: int = 10,
) -> TemporalEvidence:
    if origin == FreshnessOrigin.DEVICE_TIMESTAMP:
        return TemporalEvidence(
            received_at=FIXTURE_NOW,
            origin=origin,
            device_timestamp=FIXTURE_NOW - timedelta(seconds=age_seconds),
        )
    if origin == FreshnessOrigin.HA_TIMESTAMP:
        return TemporalEvidence(
            received_at=FIXTURE_NOW,
            origin=origin,
            ha_timestamp=FIXTURE_NOW - timedelta(seconds=age_seconds),
            ha_state_event=True,
        )
    if origin == FreshnessOrigin.RETAINED_MQTT:
        return TemporalEvidence(
            received_at=FIXTURE_NOW,
            origin=origin,
            retained=True,
        )
    if origin == FreshnessOrigin.RESTORE:
        return TemporalEvidence(
            received_at=FIXTURE_NOW,
            origin=origin,
            restored=True,
        )
    return TemporalEvidence(received_at=FIXTURE_NOW, origin=origin)


def freshness_for_fixture(
    fixture: BindingObservationFixture,
) -> tuple[FreshnessStatus, str | None]:
    requirement = (
        FreshnessRequirement.DEVICE_TIMESTAMP_REQUIRED
        if fixture.record.allowed_freshness_origins
        == (FreshnessOrigin.DEVICE_TIMESTAMP,)
        else FreshnessRequirement.DEVICE_OR_HA_EVENT
    )
    return temporal_evidence(
        fixture.observation_origin,
        age_seconds=fixture.age_seconds,
    ).freshness(
        FIXTURE_NOW,
        ttl_seconds=900,
        requirement=requirement,
    )
