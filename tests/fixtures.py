"""Synthetic Contract Evidence Gate fixtures.

These fixtures are test data only. They use the same generic graph builder for
both profiles and never reference a live entity, Home Assistant registry, or
policy integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from custom_components.benni_core_contracts.contracts import default_schema_registry
from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    Fusion,
    ProfileId,
    RawObservation,
    RuntimeMode,
    SourceBinding,
)
from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    TemporalEvidence,
)


FIXTURE_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SourceSpec:
    field: str
    value: Any
    suffix: str
    evidence_kind: str = "device"
    age_seconds: int = 10
    entity_domain: str = "sensor"


@dataclass(frozen=True)
class FixtureObservation:
    binding_id: str
    observation: RawObservation


@dataclass(frozen=True)
class EvidenceFixture:
    name: str
    purpose: str
    profile: ProfileId
    schema_id: str
    contract_id: str
    now: datetime
    config: ConfigModel
    bindings: tuple[SourceBinding, ...]
    fusions: tuple[Fusion, ...]
    observations: tuple[FixtureObservation, ...]


def _evidence(kind: str, now: datetime, age_seconds: int) -> TemporalEvidence:
    if kind == "device":
        return TemporalEvidence(
            received_at=now,
            origin=FreshnessOrigin.DEVICE_TIMESTAMP,
            device_timestamp=now - timedelta(seconds=age_seconds),
        )
    if kind == "ha_event":
        return TemporalEvidence(
            received_at=now,
            origin=FreshnessOrigin.HA_TIMESTAMP,
            ha_timestamp=now - timedelta(seconds=age_seconds),
            ha_state_event=True,
        )
    if kind == "retained_mqtt":
        return TemporalEvidence(
            received_at=now,
            origin=FreshnessOrigin.RETAINED_MQTT,
            retained=True,
        )
    if kind == "restore":
        return TemporalEvidence(
            received_at=now,
            origin=FreshnessOrigin.RESTORE,
            restored=True,
        )
    if kind == "unknown":
        return TemporalEvidence(received_at=now, origin=FreshnessOrigin.UNKNOWN)
    raise ValueError(f"unsupported fixture evidence kind: {kind}")


def _assemble(
    *,
    name: str,
    purpose: str,
    profile: ProfileId,
    schema_id: str,
    contract_id: str,
    sources: tuple[SourceSpec, ...] = (),
    declared_fields: tuple[str, ...] = (),
    strategy_by_field: Mapping[str, str] | None = None,
    now: datetime = FIXTURE_NOW,
) -> EvidenceFixture:
    schema = default_schema_registry().get(schema_id)
    source_by_field: dict[str, list[str]] = {}
    bindings: list[SourceBinding] = []
    observations: list[FixtureObservation] = []
    fields = list(declared_fields)

    for source in sources:
        if source.field not in fields:
            fields.append(source.field)
        field_schema = schema.field(source.field)
        binding_id = f"fixture_{name}_{source.suffix}"
        entity_id = f"{source.entity_domain}.fixture_{name}_{source.suffix}"
        binding = SourceBinding(
            binding_id=binding_id,
            source_id=f"fixture_source_{name}_{source.suffix}",
            entity_id=entity_id,
            field=source.field,
            capability=schema_id,
            profile_id=profile,
            required=field_schema.required,
            freshness_ttl_seconds=field_schema.freshness_ttl_seconds,
        )
        bindings.append(binding)
        source_by_field.setdefault(source.field, []).append(binding_id)
        observations.append(
            FixtureObservation(
                binding_id=binding_id,
                observation=RawObservation(
                    source_id=binding.source_id,
                    entity_id=binding.entity_id,
                    value=source.value,
                    evidence=_evidence(source.evidence_kind, now, source.age_seconds),
                ),
            )
        )

    for field in fields:
        if field not in source_by_field:
            field_schema = schema.field(field)
            binding_id = f"fixture_{name}_{field}"
            binding = SourceBinding(
                binding_id=binding_id,
                source_id=f"fixture_source_{name}_{field}",
                entity_id=f"sensor.fixture_{name}_{field}",
                field=field,
                capability=schema_id,
                profile_id=profile,
                required=field_schema.required,
                freshness_ttl_seconds=field_schema.freshness_ttl_seconds,
            )
            bindings.append(binding)
            source_by_field[field] = [binding_id]

    strategies = strategy_by_field or {}
    fusions = tuple(
        Fusion(
            fusion_id=f"fixture_fusion_{name}_{field}",
            contract_id=contract_id,
            field=field,
            input_binding_ids=tuple(binding_ids),
            strategy=strategies.get(field, "first_healthy"),
        )
        for field, binding_ids in source_by_field.items()
    )
    config = ConfigModel(
        profile=profile,
        mode=RuntimeMode.SHADOW_ONLY,
        bindings=tuple(bindings),
    )
    return EvidenceFixture(
        name=name,
        purpose=purpose,
        profile=profile,
        schema_id=schema_id,
        contract_id=contract_id,
        now=now,
        config=config,
        bindings=tuple(bindings),
        fusions=fusions,
        observations=tuple(observations),
    )


def _room_climate_fixture(profile: ProfileId, name: str, prefix: str) -> EvidenceFixture:
    return _assemble(
        name=name,
        purpose=f"vollständige Room-Climate-Evidence für das Profil {profile.value}",
        profile=profile,
        schema_id="room_climate",
        contract_id=f"fixture.{prefix}.room_climate",
        sources=(
            SourceSpec("temperature", 21.5, "temperature"),
            SourceSpec("humidity", 48.0, "humidity"),
            SourceSpec("target_temperature", 21.0, "target_temperature"),
            SourceSpec("hvac_mode", "heat", "hvac_mode"),
            SourceSpec("available", True, "available"),
        ),
    )


def benni_room_climate_fixture() -> EvidenceFixture:
    return _room_climate_fixture(ProfileId.BENNI, "benni_room_climate", "benni")


def eltern_room_climate_fixture() -> EvidenceFixture:
    return _room_climate_fixture(ProfileId.ELTERN, "eltern_room_climate", "eltern")


def opening_fixture() -> EvidenceFixture:
    return _assemble(
        name="opening",
        purpose="gültige Opening-Evidence mit konservativer Safe-Default-Grenze",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.opening",
        sources=(
            SourceSpec("opening_state", "open", "opening_state", entity_domain="binary_sensor"),
            SourceSpec("available", True, "available", entity_domain="binary_sensor"),
            SourceSpec("is_open", True, "is_open", entity_domain="binary_sensor"),
            SourceSpec("source_count", 1, "source_count"),
        ),
    )


def opening_missing_sources_fixture() -> EvidenceFixture:
    return _assemble(
        name="opening_missing_sources",
        purpose="keine Opening-Evidence für opening_state, is_open oder available",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.opening_missing",
        declared_fields=("opening_state", "is_open", "available"),
    )


def opening_stale_fixture() -> EvidenceFixture:
    return _assemble(
        name="opening_stale",
        purpose="stale Opening-Evidence darf keinen physischen Zustand halten",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.opening_stale",
        sources=(
            SourceSpec("opening_state", "open", "opening_state", age_seconds=601),
            SourceSpec("is_open", True, "is_open", age_seconds=601),
            SourceSpec("available", True, "available"),
        ),
    )


def opening_retained_mqtt_fixture() -> EvidenceFixture:
    return _assemble(
        name="opening_retained_mqtt",
        purpose="retained Opening-Evidence darf keinen physischen Zustand halten",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.opening_retained",
        sources=(
            SourceSpec(
                "opening_state",
                "open",
                "opening_state",
                evidence_kind="retained_mqtt",
            ),
            SourceSpec(
                "is_open",
                True,
                "is_open",
                evidence_kind="retained_mqtt",
            ),
            SourceSpec("available", True, "available"),
        ),
    )


def opening_restore_fixture() -> EvidenceFixture:
    return _assemble(
        name="opening_restore",
        purpose="restaurierte Opening-Evidence bleibt unknown/restored",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.opening_restore",
        sources=(
            SourceSpec("opening_state", "open", "opening_state", evidence_kind="restore"),
            SourceSpec("is_open", True, "is_open", evidence_kind="restore"),
            SourceSpec("available", True, "available"),
        ),
    )


def opening_conflict_fixture() -> EvidenceFixture:
    return _assemble(
        name="opening_conflict",
        purpose="widersprüchliche Opening-Quellen erzeugen keinen physischen Zustand",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.opening_conflict",
        sources=(
            SourceSpec("opening_state", "open", "state_primary"),
            SourceSpec("opening_state", "closed", "state_backup"),
            SourceSpec("is_open", True, "open_primary"),
            SourceSpec("is_open", False, "open_backup"),
            SourceSpec("available", True, "available"),
        ),
    )


def weather_environment_fixture() -> EvidenceFixture:
    return _assemble(
        name="weather_environment",
        purpose="vollständige Weather-/Environment-Evidence",
        profile=ProfileId.BENNI,
        schema_id="weather_environment",
        contract_id="fixture.benni.weather_environment",
        sources=(
            SourceSpec("outdoor_temperature", 12.4, "outdoor_temperature"),
            SourceSpec("outdoor_humidity", 76.0, "outdoor_humidity"),
            SourceSpec("pressure", 1014.0, "pressure"),
            SourceSpec("illuminance", 200.0, "illuminance"),
            SourceSpec("weather_state", "partlycloudy", "weather_state"),
            SourceSpec("available", True, "available"),
        ),
    )


def technical_device_fixture() -> EvidenceFixture:
    return _assemble(
        name="technical_device",
        purpose="vollständige technische Device-Evidence",
        profile=ProfileId.BENNI,
        schema_id="technical_device",
        contract_id="fixture.benni.technical_device",
        sources=(
            SourceSpec("available", True, "available"),
            SourceSpec("device_state", "on", "device_state"),
            SourceSpec("is_powered", True, "is_powered"),
            SourceSpec("power_w", 42.0, "power_w"),
            SourceSpec("battery_level", 82.0, "battery_level"),
            SourceSpec("charging", False, "charging"),
        ),
    )


def rollo_partial_failure_fixture() -> EvidenceFixture:
    return _assemble(
        name="rollo_partial_failure",
        purpose="technischer Rollo-Teilfehler ohne Zielpositions- oder Policy-Feld",
        profile=ProfileId.BENNI,
        schema_id="technical_device",
        contract_id="fixture.benni.rollo_technical",
        sources=(
            SourceSpec("available", True, "available"),
            SourceSpec("device_state", "partial_failure", "device_state"),
            SourceSpec("is_powered", True, "is_powered"),
        ),
    )


def missing_sources_fixture() -> EvidenceFixture:
    return _assemble(
        name="missing_sources",
        purpose="keine Beobachtung für die erforderlichen Room-Climate-Quellen",
        profile=ProfileId.BENNI,
        schema_id="room_climate",
        contract_id="fixture.benni.missing_sources",
        declared_fields=("temperature", "available"),
    )


def retained_mqtt_fixture() -> EvidenceFixture:
    return _assemble(
        name="retained_mqtt",
        purpose="retained MQTT darf keinen frischen Technical-Device-Wert liefern",
        profile=ProfileId.BENNI,
        schema_id="technical_device",
        contract_id="fixture.benni.retained_mqtt",
        sources=(SourceSpec("available", True, "available", evidence_kind="retained_mqtt"),),
    )


def restore_fixture() -> EvidenceFixture:
    return _assemble(
        name="restore",
        purpose="Restore-Wert bleibt restored und blockiert Required-Evidence",
        profile=ProfileId.BENNI,
        schema_id="technical_device",
        contract_id="fixture.benni.restore",
        sources=(SourceSpec("available", True, "available", evidence_kind="restore"),),
    )


def conflicting_sources_fixture() -> EvidenceFixture:
    return _assemble(
        name="conflicting_sources",
        purpose="zwei frische, widersprüchliche Quellen mit dokumentierter Priorität",
        profile=ProfileId.BENNI,
        schema_id="technical_device",
        contract_id="fixture.benni.conflict",
        sources=(
            SourceSpec("available", True, "primary"),
            SourceSpec("available", False, "backup"),
        ),
        strategy_by_field={"available": "first_healthy"},
    )


def shadow_unavailable_technical_fixture() -> EvidenceFixture:
    """A concrete ``unavailable`` state remains source evidence, not fresh truth."""

    return _assemble(
        name="shadow_unavailable_technical",
        purpose="technische Availability ist explizit unavailable",
        profile=ProfileId.BENNI,
        schema_id="technical_device",
        contract_id="fixture.benni.shadow_unavailable_technical",
        sources=(SourceSpec("available", "unavailable", "available"),),
    )


def shadow_unknown_opening_fixture() -> EvidenceFixture:
    """An explicit unknown physical source cannot claim an opening state."""

    return _assemble(
        name="shadow_unknown_opening",
        purpose="Opening-Quelle meldet unknown statt eines physischen Zustands",
        profile=ProfileId.BENNI,
        schema_id="opening",
        contract_id="fixture.benni.shadow_unknown_opening",
        sources=(
            SourceSpec("opening_state", "unknown", "opening_state", entity_domain="binary_sensor"),
            SourceSpec("is_open", "unknown", "is_open", entity_domain="binary_sensor"),
            SourceSpec("available", True, "available", entity_domain="binary_sensor"),
        ),
    )


def shadow_room_climate_fallback_fixture() -> EvidenceFixture:
    """First-healthy skips a stale primary source for a fresh alternative."""

    return _assemble(
        name="shadow_room_climate_fallback",
        purpose="frische alternative Temperaturquelle nach stale Primärquelle",
        profile=ProfileId.BENNI,
        schema_id="room_climate",
        contract_id="fixture.benni.shadow_room_climate_fallback",
        sources=(
            SourceSpec("temperature", 18.0, "temperature_primary", age_seconds=901),
            SourceSpec("temperature", 20.0, "temperature_secondary", age_seconds=10),
            SourceSpec("available", True, "available"),
        ),
    )


def shadow_weather_partial_degradation_fixture() -> EvidenceFixture:
    """A retained optional weather field does not invalidate fresh required data."""

    return _assemble(
        name="shadow_weather_partial_degradation",
        purpose="retained optionale Outdoor-Humidity bei frischer Outdoor-Temperatur",
        profile=ProfileId.BENNI,
        schema_id="weather_environment",
        contract_id="fixture.benni.shadow_weather_partial_degradation",
        sources=(
            SourceSpec("outdoor_temperature", 12.4, "outdoor_temperature"),
            SourceSpec(
                "outdoor_humidity",
                76.0,
                "outdoor_humidity",
                evidence_kind="retained_mqtt",
            ),
            SourceSpec("available", True, "available"),
        ),
    )


def all_evidence_fixtures() -> tuple[EvidenceFixture, ...]:
    return (
        benni_room_climate_fixture(),
        eltern_room_climate_fixture(),
        opening_fixture(),
        opening_missing_sources_fixture(),
        opening_stale_fixture(),
        opening_retained_mqtt_fixture(),
        opening_restore_fixture(),
        opening_conflict_fixture(),
        weather_environment_fixture(),
        technical_device_fixture(),
        rollo_partial_failure_fixture(),
        missing_sources_fixture(),
        retained_mqtt_fixture(),
        restore_fixture(),
        conflicting_sources_fixture(),
    )


def build_fixture_graph(fixture: EvidenceFixture) -> SignalGraph:
    graph = SignalGraph(now_factory=lambda: fixture.now)
    for binding in fixture.bindings:
        graph.add_binding(binding)
    graph.add_fusions(fixture.fusions)
    for item in fixture.observations:
        graph.ingest(item.binding_id, item.observation, now=fixture.now)
    return graph
