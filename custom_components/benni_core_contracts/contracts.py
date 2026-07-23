"""Gate Pack v1 contract schemas.

The schemas describe technical source truth only. They do not contain policy
targets, profiles, actuation commands, or consumer decisions.
"""

from __future__ import annotations

from .quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessRequirement,
    SafetyClass,
)
from .schema import ContractFieldSchema, ContractSchema, ValueType


def _reject(reason: str = "no_valid_observation") -> FallbackPolicy:
    return FallbackPolicy(action=FallbackAction.REJECT, reason=reason)


def _safe(value: object, reason: str) -> FallbackPolicy:
    return FallbackPolicy(
        action=FallbackAction.SAFE_DEFAULT,
        default_value=value,
        reason=reason,
    )


ROOM_CLIMATE_V1 = ContractSchema(
    schema_id="room_climate",
    version=1,
    fields=(
        ContractFieldSchema(
            name="temperature",
            value_type=ValueType.NUMBER,
            unit="°C",
            required=True,
            safety_class=SafetyClass.SAFETY_RELEVANT,
            fallback=_reject("room temperature is required for technical climate truth"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("climate",),
        ),
        ContractFieldSchema(
            name="humidity",
            value_type=ValueType.NUMBER,
            unit="%",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("humidity is unavailable"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("climate",),
        ),
        ContractFieldSchema(
            name="target_temperature",
            value_type=ValueType.NUMBER,
            unit="°C",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("target temperature is unavailable"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("climate",),
        ),
        ContractFieldSchema(
            name="hvac_mode",
            value_type=ValueType.TEXT,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("HVAC mode is unavailable"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("climate",),
        ),
        ContractFieldSchema(
            name="available",
            value_type=ValueType.BOOLEAN,
            required=True,
            safety_class=SafetyClass.SAFETY_RELEVANT,
            fallback=_safe(False, "climate availability cannot be assumed"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            safe_default_allowed=True,
            safe_default_note="unavailable climate source is not presented as available",
            consumer_ids=("climate",),
        ),
    ),
)


OPENING_V1 = ContractSchema(
    schema_id="opening",
    version=1,
    fields=(
        ContractFieldSchema(
            name="opening_state",
            value_type=ValueType.ENUM,
            required=True,
            safety_class=SafetyClass.CONSUMER_CRITICAL,
            fallback=_reject("opening source evidence is required"),
            freshness_ttl_seconds=600,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            allowed_values=("closed", "tilted", "open", "unknown"),
            physical_state=True,
            consumer_ids=("climate", "blind", "safety"),
        ),
        ContractFieldSchema(
            name="available",
            value_type=ValueType.BOOLEAN,
            required=True,
            safety_class=SafetyClass.CONSUMER_CRITICAL,
            fallback=_safe(False, "opening availability cannot be assumed"),
            freshness_ttl_seconds=600,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            safe_default_allowed=True,
            safe_default_note="missing opening sources are not presented as available",
            consumer_ids=("climate", "blind", "safety"),
        ),
        ContractFieldSchema(
            name="is_open",
            value_type=ValueType.BOOLEAN,
            safety_class=SafetyClass.SAFETY_RELEVANT,
            fallback=_reject("opening source evidence is required"),
            freshness_ttl_seconds=600,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            physical_state=True,
            consumer_ids=("climate", "blind", "safety"),
        ),
        ContractFieldSchema(
            name="source_count",
            value_type=ValueType.NUMBER,
            unit="count",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("opening source count is unavailable"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("diagnostics",),
        ),
    ),
)


WEATHER_ENVIRONMENT_V1 = ContractSchema(
    schema_id="weather_environment",
    version=1,
    fields=(
        ContractFieldSchema(
            name="outdoor_temperature",
            value_type=ValueType.NUMBER,
            unit="°C",
            required=True,
            safety_class=SafetyClass.SAFETY_RELEVANT,
            fallback=_reject("outdoor temperature is required for technical environment truth"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("climate", "blind"),
        ),
        ContractFieldSchema(
            name="outdoor_humidity",
            value_type=ValueType.NUMBER,
            unit="%",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("outdoor humidity is unavailable"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("climate",),
        ),
        ContractFieldSchema(
            name="pressure",
            value_type=ValueType.NUMBER,
            unit="hPa",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("pressure is unavailable"),
            freshness_ttl_seconds=3600,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("weather",),
        ),
        ContractFieldSchema(
            name="illuminance",
            value_type=ValueType.NUMBER,
            unit="lx",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("illuminance is unavailable"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("blind", "light"),
        ),
        ContractFieldSchema(
            name="weather_state",
            value_type=ValueType.TEXT,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("weather state is unavailable"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("weather",),
        ),
        ContractFieldSchema(
            name="available",
            value_type=ValueType.BOOLEAN,
            required=True,
            safety_class=SafetyClass.SAFETY_RELEVANT,
            fallback=_safe(False, "environment availability cannot be assumed"),
            freshness_ttl_seconds=1800,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            safe_default_allowed=True,
            safe_default_note="unavailable environment source is not presented as available",
            consumer_ids=("climate", "blind", "weather"),
        ),
    ),
)


TECHNICAL_DEVICE_V1 = ContractSchema(
    schema_id="technical_device",
    version=1,
    fields=(
        ContractFieldSchema(
            name="available",
            value_type=ValueType.BOOLEAN,
            required=True,
            safety_class=SafetyClass.SAFETY_RELEVANT,
            fallback=_safe(False, "device availability cannot be assumed"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            safe_default_allowed=True,
            safe_default_note="unavailable device source is not presented as available",
            consumer_ids=("diagnostics",),
        ),
        ContractFieldSchema(
            name="device_state",
            value_type=ValueType.TEXT,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("device state is unavailable"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("diagnostics",),
        ),
        ContractFieldSchema(
            name="is_powered",
            value_type=ValueType.BOOLEAN,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("power state is unavailable"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("diagnostics",),
        ),
        ContractFieldSchema(
            name="power_w",
            value_type=ValueType.NUMBER,
            unit="W",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("power measurement is unavailable"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("diagnostics",),
        ),
        ContractFieldSchema(
            name="battery_level",
            value_type=ValueType.NUMBER,
            unit="%",
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("raw battery report is unavailable"),
            freshness_ttl_seconds=3600,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("diagnostics",),
        ),
        ContractFieldSchema(
            name="charging",
            value_type=ValueType.BOOLEAN,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=_reject("charging state is unavailable"),
            freshness_ttl_seconds=900,
            freshness_requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
            consumer_ids=("diagnostics",),
        ),
    ),
)


def default_schema_registry():
    from .schema import SchemaRegistry

    return SchemaRegistry(
        (
            ROOM_CLIMATE_V1,
            OPENING_V1,
            WEATHER_ENVIRONMENT_V1,
            TECHNICAL_DEVICE_V1,
        )
    )
