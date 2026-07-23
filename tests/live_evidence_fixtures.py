"""Sanitised fixtures for the Benni Live Evidence Acquisition Gate.

The OPEN fixture represents the real acquisition result of this run:
Home Assistant's frontend is reachable, but its state API requires
authentication. The other fixtures are synthetic evaluator cases and are
never treated as live evidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.benni_core_contracts.live_evidence import (
    HA_STATE_CHANGE_ORIGIN,
    ReadOnlySourceSnapshot,
    build_open_benni_acquisition_report,
)
from custom_components.benni_core_contracts.source_binding_evidence import (
    source_binding_matrix_v1,
)


LIVE_FIXTURE_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def matrix_record(binding_id: str):
    return next(
        record
        for record in source_binding_matrix_v1().records
        if record.binding_id == binding_id
    )


def open_benni_live_report_fixture():
    return build_open_benni_acquisition_report(
        source_binding_matrix_v1(),
        checked_at=LIVE_FIXTURE_NOW,
        endpoint="http://192.168.178.106:8123/api/",
        blocker="api_requires_authentication_no_read_only_connector_or_token_used",
    )


def fresh_ha_event_snapshot(
    entity_id: str,
    *,
    state,
    source_owner: str | None = "synthetic_read_only_probe",
    attributes: dict | None = None,
) -> ReadOnlySourceSnapshot:
    event_time = LIVE_FIXTURE_NOW - timedelta(seconds=5)
    return ReadOnlySourceSnapshot(
        entity_id=entity_id,
        state=state,
        attributes=attributes or {},
        available=True,
        last_changed=event_time,
        last_updated=event_time,
        received_at=LIVE_FIXTURE_NOW - timedelta(seconds=4),
        event_origin=HA_STATE_CHANGE_ORIGIN,
        ha_state_event=True,
        source_owner=source_owner,
    )


def retained_weather_snapshot() -> ReadOnlySourceSnapshot:
    record = matrix_record("benni_weather_outdoor_humidity_weather")
    return ReadOnlySourceSnapshot(
        entity_id=record.source_entity,
        state=55.0,
        attributes={"unit_of_measurement": "%"},
        available=True,
        last_updated=LIVE_FIXTURE_NOW - timedelta(seconds=2),
        received_at=LIVE_FIXTURE_NOW - timedelta(seconds=1),
        retained=True,
        source_owner="synthetic_dwd_probe",
    )


def restored_opening_snapshot() -> ReadOnlySourceSnapshot:
    record = matrix_record("benni_opening_living_left_open")
    return ReadOnlySourceSnapshot(
        entity_id=record.source_entity,
        state="on",
        available=True,
        last_updated=LIVE_FIXTURE_NOW - timedelta(seconds=1),
        received_at=LIVE_FIXTURE_NOW,
        restored=True,
        source_owner="synthetic_z2m_probe",
    )


def stale_opening_snapshot() -> ReadOnlySourceSnapshot:
    record = matrix_record("benni_opening_kitchen_patio_open")
    old = LIVE_FIXTURE_NOW - timedelta(hours=2)
    return ReadOnlySourceSnapshot(
        entity_id=record.source_entity,
        state="on",
        available=True,
        last_changed=old,
        last_updated=old,
        received_at=LIVE_FIXTURE_NOW - timedelta(seconds=1),
        event_origin=HA_STATE_CHANGE_ORIGIN,
        ha_state_event=True,
        stale=True,
        source_owner="synthetic_z2m_probe",
    )


def conflicting_opening_snapshot() -> ReadOnlySourceSnapshot:
    record = matrix_record("benni_opening_living_left_open")
    return ReadOnlySourceSnapshot(
        entity_id=record.source_entity,
        state="on",
        available=True,
        competing_sources=("binary_sensor.living_window_right_open_contact",),
        source_owner="synthetic_z2m_probe",
        last_changed=LIVE_FIXTURE_NOW - timedelta(seconds=5),
        last_updated=LIVE_FIXTURE_NOW - timedelta(seconds=5),
        event_origin=HA_STATE_CHANGE_ORIGIN,
        ha_state_event=True,
    )


def lock_without_timestamp_snapshot() -> ReadOnlySourceSnapshot:
    return ReadOnlySourceSnapshot(
        entity_id="lock.flur_aqara_smart_lock_u200",
        state="locked",
        attributes={"device_class": "lock"},
        available=True,
        last_updated=LIVE_FIXTURE_NOW - timedelta(seconds=1),
        received_at=LIVE_FIXTURE_NOW,
        source_owner="synthetic_matter_probe",
    )
