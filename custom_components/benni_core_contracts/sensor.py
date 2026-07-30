"""The sole explicitly allowlisted PublishedContract entity."""

from __future__ import annotations

from typing import Any

from .const import (
    DOMAIN,
    PILOT_OPENING_CONTRACT_ID,
    PILOT_OPENING_ENTITY_ID,
)
from .shadow import PublishedRuntime

try:  # Home Assistant is available only when the platform is loaded.
    from homeassistant.components.sensor import SensorEntity

    HA_AVAILABLE = True
except ImportError:  # pragma: no cover - stdlib-only tests use pure helpers
    HA_AVAILABLE = False

    class SensorEntity:  # type: ignore[no-redef]
        pass


async def async_setup_entry(hass: Any, entry: Any, async_add_entities) -> None:
    """Create exactly the allowlisted pilot entity, never raw-source entities."""

    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not isinstance(runtime, PublishedRuntime):
        return
    if not runtime.public_entity_ids((PILOT_OPENING_ENTITY_ID,)):
        return
    async_add_entities([OpeningContractSensor(runtime)])


def _field_diagnostic(runtime: PublishedRuntime, field_name: str):
    diagnostic = runtime.graph.diagnostic(PILOT_OPENING_CONTRACT_ID)
    if diagnostic is None:
        return None
    return next((field for field in diagnostic.fields if field.field == field_name), None)


def _source_snapshots(runtime: PublishedRuntime) -> dict[str, dict[str, Any]]:
    """Expose only the pilot's observed raw state/evidence as attributes."""

    snapshots: dict[str, dict[str, Any]] = {}
    for binding in runtime.graph.bindings():
        if binding.capability != "opening":
            continue
        signal = runtime.graph.signal(binding.binding_id)
        snapshots[binding.entity_id] = {
            "state": signal.value if signal is not None else None,
            "evidence": signal.evidence.as_dict() if signal is not None else None,
        }
    return snapshots


if HA_AVAILABLE:

    class OpeningContractSensor(SensorEntity):
        """One sensor for the published opening state, with field metadata."""

        _attr_should_poll = False
        _attr_name = "Benni Opening Kitchen Patio Door"
        _attr_icon = "mdi:door"
        _attr_unique_id = PILOT_OPENING_CONTRACT_ID
        _attr_suggested_object_id = PILOT_OPENING_ENTITY_ID.split(".", 1)[1]

        def __init__(self, runtime: PublishedRuntime) -> None:
            self._runtime = runtime
            self._runtime.add_contract_update_listener(self._handle_runtime_update)

        @property
        def native_value(self) -> str:
            contract = self._runtime.graph.contract(PILOT_OPENING_CONTRACT_ID)
            if contract is None:
                return "unknown"
            value = contract.values.get("opening_state", "unknown")
            return str(value) if value is not None else "unknown"

        @property
        def available(self) -> bool:
            # Entity availability means the integration/contract object exists.
            # Source availability is exposed separately as a contract field so
            # missing evidence yields the factual state ``unknown`` instead of
            # HA replacing it with the transport state ``unavailable``.
            return self._runtime.graph.contract(PILOT_OPENING_CONTRACT_ID) is not None

        @property
        def extra_state_attributes(self) -> dict[str, Any]:
            contract = self._runtime.graph.contract(PILOT_OPENING_CONTRACT_ID)
            if contract is None:
                return {
                    "contract_id": PILOT_OPENING_CONTRACT_ID,
                    "schema_id": "opening",
                    "schema_version": 1,
                    "opening_state": "unknown",
                    "published": True,
                    "mode": "published",
                }
            opening = _field_diagnostic(self._runtime, "opening_state")
            available = _field_diagnostic(self._runtime, "available")
            return {
                "contract_id": contract.contract_id,
                "schema_id": contract.schema_id,
                "schema_version": contract.schema_version,
                "profile": "benni",
                "published": True,
                "mode": "published",
                "opening_state": contract.values.get("opening_state", "unknown"),
                "is_open": contract.values.get("is_open", "unknown"),
                "contract_available": contract.values.get("available", False),
                "health": contract.health.value,
                "quality": (
                    contract.field_quality["opening_state"].as_dict()
                    if "opening_state" in contract.field_quality
                    else "unknown"
                ),
                "freshness": (
                    contract.field_quality["opening_state"].freshness.value
                    if "opening_state" in contract.field_quality
                    else "unknown"
                ),
                "safety": (
                    contract.field_quality["opening_state"].safety.value
                    if "opening_state" in contract.field_quality
                    else "unknown"
                ),
                "source_entities": list(opening.source_entities) if opening else [],
                "configured_source_entities": [
                    binding.entity_id for binding in self._runtime.graph.bindings()
                ],
                "active_source_entities": (
                    list(opening.active_source_entities) if opening else []
                ),
                "source_snapshots": _source_snapshots(self._runtime),
                "source_count": contract.values.get("source_count", "unknown"),
                "available_quality": (
                    contract.field_quality["available"].as_dict()
                    if "available" in contract.field_quality
                    else "unknown"
                ),
                "available_health": available.health.value if available else "unknown",
            }

        def _handle_runtime_update(self) -> None:
            if hasattr(self, "async_write_ha_state"):
                self.async_write_ha_state()

        async def async_will_remove_from_hass(self) -> None:
            self._runtime.remove_contract_update_listener(self._handle_runtime_update)
            await super().async_will_remove_from_hass()

else:

    class OpeningContractSensor(SensorEntity):  # type: ignore[no-redef]
        """Import-safe placeholder; HA never loads this branch at runtime."""

        def __init__(self, runtime: PublishedRuntime) -> None:
            self._runtime = runtime
