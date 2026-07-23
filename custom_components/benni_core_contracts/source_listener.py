"""Read-only Home Assistant source adapter for configured SourceBindings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import RawObservation
from .quality import FreshnessOrigin, TemporalEvidence, utc_now
from .shadow import ShadowRuntime


def _as_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def observation_from_state(
    binding,
    state: Any,
    *,
    received_at: datetime,
    state_event: bool = False,
) -> RawObservation:
    """Normalize a HA State-like object without inferring a device timestamp.

    ``last_updated`` is usable as observation evidence only when the caller
    explicitly tells us that this object came from a real state-change event.
    Reading the current state during setup is intentionally not such an event.
    """

    attributes = getattr(state, "attributes", {}) or {}
    device_timestamp = _as_datetime(
        attributes.get("device_timestamp") or attributes.get("last_device_update")
    )
    retained = bool(attributes.get("retained", False))
    if device_timestamp is not None:
        origin = FreshnessOrigin.DEVICE_TIMESTAMP
    else:
        origin = FreshnessOrigin.RETAINED_MQTT if retained else FreshnessOrigin.HA_TIMESTAMP
    ha_timestamp = _as_datetime(getattr(state, "last_updated", None))
    value: Any = getattr(state, "state", None)
    return RawObservation(
        source_id=binding.source_id,
        entity_id=binding.entity_id,
        value=value,
        evidence=TemporalEvidence(
            received_at=received_at,
            origin=origin,
            device_timestamp=device_timestamp,
            ha_timestamp=ha_timestamp,
            retained=retained,
            ha_state_event=state_event and origin == FreshnessOrigin.HA_TIMESTAMP,
        ),
    )


async def async_attach_source_listeners(hass: Any, runtime: ShadowRuntime) -> None:
    """Subscribe to state updates only; no entity or service API is touched."""

    from homeassistant.helpers.event import async_track_state_change_event

    for binding in runtime.graph.bindings():
        async def handle_event(event: Any, current_binding=binding) -> None:
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            old_state = event.data.get("old_state")
            observation = observation_from_state(
                current_binding,
                new_state,
                received_at=getattr(event, "time_fired", None) or utc_now(),
                state_event=old_state is not None,
            )
            runtime.graph.ingest(current_binding.binding_id, observation)

        unsubscribe = async_track_state_change_event(
            hass,
            [binding.entity_id],
            handle_event,
        )
        runtime.add_unsubscribe(unsubscribe)
        current_state = hass.states.get(binding.entity_id)
        if current_state is not None:
            runtime.graph.ingest(
                binding.binding_id,
                observation_from_state(
                    binding,
                    current_state,
                    received_at=utc_now(),
                    state_event=False,
                ),
            )
