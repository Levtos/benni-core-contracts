"""Versioned, non-activating source-binding evidence.

This module is an evidence register, not a production configuration source.
Its records deliberately cannot be converted into ConfigModel.bindings
implicitly. A record may describe a raw Home Assistant source, a derived
availability gate, or an evidence-only special case such as a cover position
or a lock state that is not part of a v1 public contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable

from .models import ProfileId, ProfileScope
from .quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessOrigin,
    FreshnessRequirement,
    FreshnessStatus,
    SafetyClass,
    TemporalEvidence,
)


SOURCE_BINDING_EVIDENCE_VERSION = 1
BENNI_CANONICAL_LOCK_ENTITY = "lock.flur_aqara_smart_lock_u200"
HISTORICAL_BENNI_LOCK_ENTITY = "lock.aqara_smart_lock_u200"
HISTORICAL_BENNI_LOCK_BATTERY_ENTITY = "sensor.aqara_smart_lock_u200_batterie"


class BindingEvidenceClass(str, Enum):
    """Allowed evidence labels for one source-binding candidate."""

    IMPLEMENTIERT = "IMPLEMENTIERT"
    KONFIGURIERT = "KONFIGURIERT"
    LIVE_VERIFIZIERT = "LIVE_VERIFIZIERT"
    DOKUMENTIERT = "DOKUMENTIERT"
    OFFEN = "OFFEN"
    ANNAHME = "ANNAHME"


class BindingKind(str, Enum):
    RAW = "raw"
    DERIVED_GATE = "derived_gate"
    EVIDENCE_ONLY = "evidence_only"
    MISSING = "missing"


class BindingDisposition(str, Enum):
    CANDIDATE = "candidate"
    DERIVED = "derived"
    EVIDENCE_ONLY = "evidence_only"
    CONFLICT = "conflict"
    OPEN = "open"
    EXCLUDED = "excluded"


_FRESHNESS_ORIGINS = frozenset(FreshnessOrigin)
_DISPOSITIONS = frozenset(BindingDisposition)


@dataclass(frozen=True)
class SourceBindingEvidence:
    """One auditable source candidate without activation authority.

    source_entity is None when no concrete source is evidenced. A missing
    source is therefore represented by absence, never by a fabricated entity
    ID. production_binding_allowed is permanently false for this model so an
    evidence matrix cannot silently populate a ConfigEntry.
    """

    binding_id: str
    profile_id: ProfileId
    contract_ref: str | None
    field: str
    logical_role: str
    source_entity: str | None
    room: str | None
    required: bool
    allowed_freshness_origins: tuple[FreshnessOrigin, ...]
    device_timestamp_present: bool | None
    ha_state_change_usable: bool | None
    retained_mqtt_possible: bool | None
    source_attribute_path: str | None
    device_timestamp_path: str | None
    ha_observation_path: str | None
    fallback: FallbackPolicy
    quality_relevance: str
    safety_relevance: SafetyClass
    evidence_class: BindingEvidenceClass
    consumers: tuple[str, ...]
    open_question: str
    binding_kind: BindingKind = BindingKind.RAW
    disposition: BindingDisposition = BindingDisposition.CANDIDATE
    evidence_note: str = ""
    production_binding_allowed: bool = False
    ha_domain: str | None = None
    historical_source_entity: str | None = None
    activation_scope: ProfileScope | None = None

    def __post_init__(self) -> None:
        if not self.binding_id or not self.field or not self.logical_role:
            raise ValueError("binding_id, field, and logical_role are required")
        if not isinstance(self.profile_id, ProfileId):
            raise ValueError("profile_id must be ProfileId")
        expected_scope = (
            ProfileScope.BENNI_PRODUCTION
            if self.profile_id == ProfileId.BENNI
            else ProfileScope.PARENT_FUTURE
        )
        if self.activation_scope is None:
            object.__setattr__(self, "activation_scope", expected_scope)
        elif self.activation_scope != expected_scope:
            raise ValueError(
                f"profile {self.profile_id.value} must use "
                f"activation_scope={expected_scope.value}"
            )
        if not self.contract_ref and self.binding_kind not in {
            BindingKind.EVIDENCE_ONLY,
            BindingKind.MISSING,
        }:
            raise ValueError("non-special evidence needs a contract reference")
        if not self.allowed_freshness_origins:
            raise ValueError("allowed_freshness_origins must not be empty")
        if not set(self.allowed_freshness_origins).issubset(_FRESHNESS_ORIGINS):
            raise ValueError("unsupported freshness origin in evidence record")
        if not self.quality_relevance or not self.open_question:
            raise ValueError("quality_relevance and open_question are required")
        if self.disposition not in _DISPOSITIONS:
            raise ValueError("unsupported binding disposition")
        if self.production_binding_allowed:
            raise ValueError("evidence records cannot authorize production bindings")

        if self.source_entity is None:
            if self.ha_domain is not None:
                raise ValueError("missing source cannot have an HA domain")
            if self.source_attribute_path is not None:
                raise ValueError("missing source cannot have an attribute path")
            if self.binding_kind == BindingKind.RAW:
                raise ValueError("raw evidence needs a concrete source entity")
        else:
            if self.source_entity.count(".") != 1 or "*" in self.source_entity:
                raise ValueError("source_entity must be one concrete entity ID")
            inferred_domain = self.source_entity.split(".", 1)[0]
            if self.ha_domain is not None and self.ha_domain != inferred_domain:
                raise ValueError("ha_domain does not match source_entity")
            object.__setattr__(self, "ha_domain", inferred_domain)
            expected_domains = {
                "opening_state": {"binary_sensor"},
                "cover_position": {"cover"},
                "lock_state": {"lock"},
            }
            if (
                self.field in expected_domains
                and inferred_domain not in expected_domains[self.field]
            ):
                raise ValueError(
                    f"{self.field} evidence needs one of "
                    f"{sorted(expected_domains[self.field])} source domains"
                )

        if self.historical_source_entity is not None:
            if (
                self.historical_source_entity.count(".") != 1
                or "*" in self.historical_source_entity
            ):
                raise ValueError(
                    "historical_source_entity must be one concrete entity ID"
                )
            if self.historical_source_entity == self.source_entity:
                raise ValueError(
                    "historical_source_entity must differ from source_entity"
                )

        if self.device_timestamp_present is True and not self.device_timestamp_path:
            raise ValueError("device timestamp presence needs a concrete timestamp path")
        if self.device_timestamp_present is False and self.device_timestamp_path:
            raise ValueError("a false device timestamp cannot have a timestamp path")
        if self.ha_state_change_usable is True and not self.ha_observation_path:
            raise ValueError("usable HA state changes need an observation path")
        if self.ha_state_change_usable is False and self.ha_observation_path:
            raise ValueError("unusable HA state changes cannot have an observation path")

        physical = self.field in {
            "opening_state",
            "is_open",
            "lock_state",
            "cover_position",
        }
        if physical and self.fallback.action != FallbackAction.REJECT:
            raise ValueError(f"physical field {self.field} must use fallback=reject")
        if physical and self.fallback.action == FallbackAction.SAFE_DEFAULT:
            raise ValueError(f"safe_default is forbidden for physical field {self.field}")
        if self.binding_kind == BindingKind.DERIVED_GATE and self.source_entity is not None:
            raise ValueError("derived availability evidence cannot bind a raw entity")
        if self.evidence_class == BindingEvidenceClass.LIVE_VERIFIZIERT:
            if self.source_entity is None or not self.evidence_note:
                raise ValueError("live-verified evidence needs a source and evidence note")

    @property
    def is_physical(self) -> bool:
        return self.field in {"opening_state", "is_open", "lock_state", "cover_position"}

    @property
    def is_activatable_candidate(self) -> bool:
        return (
            self.activation_scope == ProfileScope.BENNI_PRODUCTION
            and self.production_binding_allowed
            and self.disposition == BindingDisposition.CANDIDATE
        )

    @property
    def is_benni_production_scope(self) -> bool:
        return self.activation_scope == ProfileScope.BENNI_PRODUCTION

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "profile_id": self.profile_id.value,
            "contract": self.contract_ref,
            "field": self.field,
            "logical_role": self.logical_role,
            "source_entity": self.source_entity,
            "ha_domain": self.ha_domain,
            "room": self.room,
            "required": self.required,
            "allowed_freshness_origins": [
                origin.value for origin in self.allowed_freshness_origins
            ],
            "device_timestamp_present": self.device_timestamp_present,
            "ha_state_change_usable": self.ha_state_change_usable,
            "retained_mqtt_possible": self.retained_mqtt_possible,
            "source_attribute_path": self.source_attribute_path,
            "device_timestamp_path": self.device_timestamp_path,
            "ha_observation_path": self.ha_observation_path,
            "fallback": self.fallback.as_dict(),
            "quality_relevance": self.quality_relevance,
            "safety_relevance": self.safety_relevance.value,
            "evidence_class": self.evidence_class.value,
            "consumers": list(self.consumers),
            "open_question": self.open_question,
            "binding_kind": self.binding_kind.value,
            "disposition": self.disposition.value,
            "evidence_note": self.evidence_note,
            "production_binding_allowed": self.production_binding_allowed,
            "historical_source_entity": self.historical_source_entity,
            "activation_scope": self.activation_scope.value,
        }


@dataclass(frozen=True)
class SourceBindingEvidenceMatrix:
    """Stable, versioned record set used by the Evidence Gate only."""

    version: int
    records: tuple[SourceBindingEvidence, ...]

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("matrix version must be positive")
        ids = [record.binding_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("binding evidence IDs must be unique")
        if any(record.production_binding_allowed for record in self.records):
            raise ValueError("matrix records cannot authorize production bindings")

    def for_profile(self, profile_id: ProfileId) -> tuple[SourceBindingEvidence, ...]:
        return tuple(record for record in self.records if record.profile_id == profile_id)

    def for_contract(self, contract_ref: str) -> tuple[SourceBindingEvidence, ...]:
        return tuple(record for record in self.records if record.contract_ref == contract_ref)

    def active_candidates(self) -> tuple[SourceBindingEvidence, ...]:
        """Return Benni production-scope evidence candidates only.

        The records remain evidence and cannot authorize activation. Parent
        records are intentionally excluded even when they are concrete
        candidates for a future shared-graph fixture.
        """

        return tuple(
            record
            for record in self.records
            if (
                record.disposition == BindingDisposition.CANDIDATE
                and record.activation_scope == ProfileScope.BENNI_PRODUCTION
            )
        )

    def parent_future_records(self) -> tuple[SourceBindingEvidence, ...]:
        return tuple(
            record
            for record in self.records
            if record.activation_scope == ProfileScope.PARENT_FUTURE
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "matrix_version": self.version,
            "production_profile": ProfileId.BENNI.value,
            "parent_profile_scope": ProfileScope.PARENT_FUTURE.value,
            "production_binding_allowed": False,
            "records": [record.as_dict() for record in self.records],
        }


@dataclass(frozen=True)
class BindingEvidenceAssessment:
    """Read-only result of evaluating one observed source event."""

    binding_id: str
    source_entity: str | None
    freshness: FreshnessStatus
    accepted: bool
    activation_allowed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "source_entity": self.source_entity,
            "freshness": self.freshness.value,
            "accepted": self.accepted,
            "activation_allowed": self.activation_allowed,
            "reason": self.reason,
        }


def assess_source_binding_evidence(
    record: SourceBindingEvidence,
    evidence: TemporalEvidence | None,
    *,
    now: datetime,
    ttl_seconds: int,
) -> BindingEvidenceAssessment:
    """Evaluate one source event without activating or publishing it.

    The source record controls which temporal origins are admissible. A live
    state record may still be rejected when its disposition is conflict/open,
    when no device timestamp path was evidenced, or when the transport is a
    retained/restore replay.
    """

    if evidence is None or record.source_entity is None:
        return BindingEvidenceAssessment(
            binding_id=record.binding_id,
            source_entity=record.source_entity,
            freshness=FreshnessStatus.UNKNOWN,
            accepted=False,
            activation_allowed=False,
            reason="source_unavailable",
        )

    if evidence.origin == FreshnessOrigin.RETAINED_MQTT or evidence.retained:
        freshness, _ = evidence.freshness(
            now,
            ttl_seconds=ttl_seconds,
            requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
        )
        return BindingEvidenceAssessment(
            binding_id=record.binding_id,
            source_entity=record.source_entity,
            freshness=freshness,
            accepted=False,
            activation_allowed=False,
            reason="source_retained",
        )

    if evidence.origin == FreshnessOrigin.RESTORE or evidence.restored:
        freshness, _ = evidence.freshness(
            now,
            ttl_seconds=ttl_seconds,
            requirement=FreshnessRequirement.DEVICE_OR_HA_EVENT,
        )
        return BindingEvidenceAssessment(
            binding_id=record.binding_id,
            source_entity=record.source_entity,
            freshness=freshness,
            accepted=False,
            activation_allowed=False,
            reason="source_restored",
        )

    if evidence.origin not in record.allowed_freshness_origins:
        return BindingEvidenceAssessment(
            binding_id=record.binding_id,
            source_entity=record.source_entity,
            freshness=FreshnessStatus.UNKNOWN,
            accepted=False,
            activation_allowed=False,
            reason="source_freshness_origin_not_allowed",
        )

    if evidence.origin == FreshnessOrigin.DEVICE_TIMESTAMP:
        if record.device_timestamp_present is not True:
            return BindingEvidenceAssessment(
                binding_id=record.binding_id,
                source_entity=record.source_entity,
                freshness=FreshnessStatus.UNKNOWN,
                accepted=False,
                activation_allowed=False,
                reason="device_timestamp_not_evidenced",
            )
    if evidence.origin == FreshnessOrigin.HA_TIMESTAMP:
        if record.ha_state_change_usable is not True or not evidence.ha_state_event:
            return BindingEvidenceAssessment(
                binding_id=record.binding_id,
                source_entity=record.source_entity,
                freshness=FreshnessStatus.UNKNOWN,
                accepted=False,
                activation_allowed=False,
                reason="ha_state_change_not_evidenced",
            )

    requirement = (
        FreshnessRequirement.DEVICE_TIMESTAMP_REQUIRED
        if record.allowed_freshness_origins == (FreshnessOrigin.DEVICE_TIMESTAMP,)
        else FreshnessRequirement.DEVICE_OR_HA_EVENT
    )
    freshness, freshness_reason = evidence.freshness(
        now,
        ttl_seconds=ttl_seconds,
        requirement=requirement,
    )
    if freshness != FreshnessStatus.FRESH:
        return BindingEvidenceAssessment(
            binding_id=record.binding_id,
            source_entity=record.source_entity,
            freshness=freshness,
            accepted=False,
            activation_allowed=False,
            reason=freshness_reason or "source_not_fresh",
        )

    if record.disposition == BindingDisposition.CONFLICT:
        reason = "source_conflict"
    elif record.disposition != BindingDisposition.CANDIDATE:
        reason = "source_not_candidate"
    else:
        return BindingEvidenceAssessment(
            binding_id=record.binding_id,
            source_entity=record.source_entity,
            freshness=freshness,
            accepted=True,
            activation_allowed=False,
            reason="evidence_valid_not_activated",
        )
    return BindingEvidenceAssessment(
        binding_id=record.binding_id,
        source_entity=record.source_entity,
        freshness=freshness,
        accepted=False,
        activation_allowed=False,
        reason=reason,
    )


_DEVICE_OR_HA = (
    FreshnessOrigin.DEVICE_TIMESTAMP,
    FreshnessOrigin.HA_TIMESTAMP,
)
_DEVICE_ONLY = (FreshnessOrigin.DEVICE_TIMESTAMP,)
_REJECT = FallbackPolicy(
    action=FallbackAction.REJECT,
    reason="no_valid_source_evidence",
)
_SAFE_FALSE = FallbackPolicy(
    action=FallbackAction.SAFE_DEFAULT,
    default_value=False,
    reason="availability_is_not_assumed",
)
_HA_EVENT_PATH = "last_changed/last_reported only for a non-retained HA state event"


def _raw(
    *,
    binding_id: str,
    profile_id: ProfileId,
    contract_ref: str,
    field: str,
    logical_role: str,
    source_entity: str,
    room: str | None,
    required: bool,
    source_attribute_path: str,
    freshness: tuple[FreshnessOrigin, ...] = _DEVICE_OR_HA,
    ha_state_change_usable: bool | None = True,
    retained_mqtt_possible: bool | None = None,
    fallback: FallbackPolicy = _REJECT,
    quality_relevance: str = "value validity, transport and freshness must remain field-scoped",
    safety_relevance: SafetyClass = SafetyClass.INFORMATIONAL,
    evidence_class: BindingEvidenceClass,
    consumers: tuple[str, ...],
    open_question: str,
    disposition: BindingDisposition = BindingDisposition.CANDIDATE,
    evidence_note: str = "",
    device_timestamp_present: bool | None = False,
    device_timestamp_path: str | None = None,
    ha_observation_path: str | None = _HA_EVENT_PATH,
    binding_kind: BindingKind = BindingKind.RAW,
) -> SourceBindingEvidence:
    return SourceBindingEvidence(
        binding_id=binding_id,
        profile_id=profile_id,
        contract_ref=contract_ref,
        field=field,
        logical_role=logical_role,
        source_entity=source_entity,
        room=room,
        required=required,
        allowed_freshness_origins=freshness,
        device_timestamp_present=device_timestamp_present,
        ha_state_change_usable=ha_state_change_usable,
        retained_mqtt_possible=retained_mqtt_possible,
        source_attribute_path=source_attribute_path,
        device_timestamp_path=device_timestamp_path,
        ha_observation_path=ha_observation_path,
        fallback=fallback,
        quality_relevance=quality_relevance,
        safety_relevance=safety_relevance,
        evidence_class=evidence_class,
        consumers=consumers,
        open_question=open_question,
        binding_kind=binding_kind,
        disposition=disposition,
        evidence_note=evidence_note,
    )


def _derived(
    *,
    binding_id: str,
    profile_id: ProfileId,
    contract_ref: str,
    field: str,
    logical_role: str,
    room: str | None,
    required: bool,
    fallback: FallbackPolicy,
    safety_relevance: SafetyClass,
    consumers: tuple[str, ...],
    open_question: str,
    evidence_class: BindingEvidenceClass = BindingEvidenceClass.IMPLEMENTIERT,
) -> SourceBindingEvidence:
    return SourceBindingEvidence(
        binding_id=binding_id,
        profile_id=profile_id,
        contract_ref=contract_ref,
        field=field,
        logical_role=logical_role,
        source_entity=None,
        room=room,
        required=required,
        allowed_freshness_origins=_DEVICE_OR_HA,
        device_timestamp_present=None,
        ha_state_change_usable=None,
        retained_mqtt_possible=None,
        source_attribute_path=None,
        device_timestamp_path=None,
        ha_observation_path=None,
        fallback=fallback,
        quality_relevance="derived only from independently evaluated field evidence",
        safety_relevance=safety_relevance,
        evidence_class=evidence_class,
        consumers=consumers,
        open_question=open_question,
        binding_kind=BindingKind.DERIVED_GATE,
        disposition=BindingDisposition.DERIVED,
        evidence_note="No independent HA entity; this is an internal evidence projection.",
    )


def _missing(
    *,
    binding_id: str,
    profile_id: ProfileId,
    contract_ref: str | None,
    field: str,
    logical_role: str,
    room: str | None,
    required: bool,
    fallback: FallbackPolicy,
    safety_relevance: SafetyClass,
    consumers: tuple[str, ...],
    open_question: str,
    freshness: tuple[FreshnessOrigin, ...] = _DEVICE_OR_HA,
    evidence_class: BindingEvidenceClass = BindingEvidenceClass.OFFEN,
    disposition: BindingDisposition = BindingDisposition.OPEN,
) -> SourceBindingEvidence:
    return SourceBindingEvidence(
        binding_id=binding_id,
        profile_id=profile_id,
        contract_ref=contract_ref,
        field=field,
        logical_role=logical_role,
        source_entity=None,
        room=room,
        required=required,
        allowed_freshness_origins=freshness,
        device_timestamp_present=None,
        ha_state_change_usable=None,
        retained_mqtt_possible=None,
        source_attribute_path=None,
        device_timestamp_path=None,
        ha_observation_path=None,
        fallback=fallback,
        quality_relevance="no source evidence; required gates remain blocked",
        safety_relevance=safety_relevance,
        evidence_class=evidence_class,
        consumers=consumers,
        open_question=open_question,
        binding_kind=BindingKind.MISSING,
        disposition=disposition,
        evidence_note="No concrete entity ID was found; no placeholder ID is used.",
    )


def _special(
    *,
    binding_id: str,
    profile_id: ProfileId,
    field: str,
    logical_role: str,
    source_entity: str | None,
    room: str | None,
    required: bool,
    source_attribute_path: str | None,
    freshness: tuple[FreshnessOrigin, ...],
    device_timestamp_present: bool | None,
    ha_state_change_usable: bool | None,
    retained_mqtt_possible: bool | None,
    fallback: FallbackPolicy,
    quality_relevance: str,
    safety_relevance: SafetyClass,
    evidence_class: BindingEvidenceClass,
    consumers: tuple[str, ...],
    open_question: str,
    disposition: BindingDisposition,
    evidence_note: str,
    device_timestamp_path: str | None = None,
    ha_observation_path: str | None = _HA_EVENT_PATH,
    historical_source_entity: str | None = None,
) -> SourceBindingEvidence:
    return SourceBindingEvidence(
        binding_id=binding_id,
        profile_id=profile_id,
        contract_ref=None,
        field=field,
        logical_role=logical_role,
        source_entity=source_entity,
        room=room,
        required=required,
        allowed_freshness_origins=freshness,
        device_timestamp_present=device_timestamp_present,
        ha_state_change_usable=ha_state_change_usable,
        retained_mqtt_possible=retained_mqtt_possible,
        source_attribute_path=source_attribute_path,
        device_timestamp_path=device_timestamp_path,
        ha_observation_path=ha_observation_path,
        fallback=fallback,
        quality_relevance=quality_relevance,
        safety_relevance=safety_relevance,
        evidence_class=evidence_class,
        consumers=consumers,
        open_question=open_question,
        binding_kind=BindingKind.EVIDENCE_ONLY,
        disposition=disposition,
        evidence_note=evidence_note,
        historical_source_entity=historical_source_entity,
    )


def _climate_records(profile_id: ProfileId) -> list[SourceBindingEvidence]:
    if profile_id == ProfileId.BENNI:
        rooms = (
            (
                "living",
                "sensor.living_climate_temperature",
                "sensor.living_climate_humidity",
                "climate.eve_thermo_20ebp1701",
            ),
            (
                "kitchen",
                "sensor.kitchen_climate_temperature",
                "sensor.kitchen_climate_humidity",
                "climate.eve_thermo_20ebp1701_2",
            ),
            (
                "bathroom",
                "sensor.bath_climate_temperature",
                "sensor.bath_climate_humidity",
                "climate.eve_thermo_20ebp1701_3",
            ),
        )
        retained = None
        note = (
            "Read-only Benni live lookup on 2026-07-23 returned entity, state "
            "and expected value shape."
        )
        source_note = (
            "The local import also contains this entity; live presence does not "
            "prove a device timestamp."
        )
    else:
        rooms = (
            (
                "living",
                "sensor.living_room_temperature",
                "sensor.living_room_humidity",
                "climate.living_room_thermostat",
            ),
            (
                "kitchen",
                "sensor.kitchen_temperature",
                "sensor.kitchen_humidity",
                "climate.kitchen_thermostat",
            ),
            (
                "bathroom",
                "sensor.bathroom_temperature",
                "sensor.bathroom_humidity",
                "climate.bathroom_thermostat",
            ),
        )
        retained = True
        note = (
            "Read-only Eltern live lookup on 2026-07-23 returned entity, state "
            "and expected value shape."
        )
        source_note = (
            "The local parent YAML uses Z2M/Matter paths; retained MQTT remains "
            "possible and must be classified per event."
        )

    records: list[SourceBindingEvidence] = []
    for room, temperature, humidity, thermostat in rooms:
        prefix = f"{profile_id.value}_{room}_climate"
        records.extend(
            (
                _raw(
                    binding_id=f"{prefix}_temperature",
                    profile_id=profile_id,
                    contract_ref="room_climate.v1",
                    field="temperature",
                    logical_role="room_temperature",
                    source_entity=temperature,
                    room=room,
                    required=True,
                    source_attribute_path="state",
                    retained_mqtt_possible=retained,
                    safety_relevance=SafetyClass.SAFETY_RELEVANT,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("climate",),
                    open_question=(
                        "Confirm real device timestamp or non-retained HA "
                        "state-event semantics before production binding. "
                        + source_note
                    ),
                    evidence_note=note,
                ),
                _raw(
                    binding_id=f"{prefix}_humidity",
                    profile_id=profile_id,
                    contract_ref="room_climate.v1",
                    field="humidity",
                    logical_role="room_humidity",
                    source_entity=humidity,
                    room=room,
                    required=False,
                    source_attribute_path="state",
                    retained_mqtt_possible=retained,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("climate",),
                    open_question=(
                        "Confirm the source timestamp path and whether a "
                        "retained MQTT replay can be distinguished. "
                        + source_note
                    ),
                    evidence_note=note,
                ),
                _raw(
                    binding_id=f"{prefix}_target_temperature",
                    profile_id=profile_id,
                    contract_ref="room_climate.v1",
                    field="target_temperature",
                    logical_role="thermostat_observed_setpoint",
                    source_entity=thermostat,
                    room=room,
                    required=False,
                    source_attribute_path="attributes.temperature",
                    retained_mqtt_possible=retained,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("climate",),
                    open_question=(
                        "Confirm that the thermostat attribute is a technical "
                        "observed setpoint and not a policy target. "
                        + source_note
                    ),
                    evidence_note=note,
                ),
                _raw(
                    binding_id=f"{prefix}_hvac_mode",
                    profile_id=profile_id,
                    contract_ref="room_climate.v1",
                    field="hvac_mode",
                    logical_role="thermostat_state",
                    source_entity=thermostat,
                    room=room,
                    required=False,
                    source_attribute_path="state",
                    retained_mqtt_possible=retained,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("climate",),
                    open_question=(
                        "Confirm the raw HVAC state vocabulary and timestamp "
                        "semantics; do not import profile or heating-policy "
                        "values. "
                        + source_note
                    ),
                    evidence_note=note,
                ),
                _derived(
                    binding_id=f"{prefix}_available_evidence_gate",
                    profile_id=profile_id,
                    contract_ref="room_climate.v1",
                    field="available",
                    logical_role="required_source_availability_gate",
                    room=room,
                    required=True,
                    fallback=_SAFE_FALSE,
                    safety_relevance=SafetyClass.SAFETY_RELEVANT,
                    consumers=("climate",),
                    open_question=(
                        "Confirm which required room-climate fields constitute "
                        "availability for this room."
                    ),
                ),
            )
        )
    return records


def _opening_records(profile_id: ProfileId) -> list[SourceBindingEvidence]:
    if profile_id == ProfileId.BENNI:
        sources = (
            (
                "living",
                "living_left_open",
                "binary_sensor.living_window_left_open_contact",
                "open_contact",
            ),
            (
                "living",
                "living_left_tilt",
                "binary_sensor.living_window_left_tilt_contact",
                "tilt_contact",
            ),
            (
                "living",
                "living_right_open",
                "binary_sensor.living_window_right_open_contact",
                "open_contact",
            ),
            (
                "living",
                "living_right_tilt",
                "binary_sensor.living_window_right_tilt_contact",
                "tilt_contact",
            ),
            (
                "kitchen",
                "kitchen_patio_open",
                "binary_sensor.kitchen_patio_door_open_contact",
                "open_contact",
            ),
            (
                "kitchen",
                "kitchen_patio_tilt",
                "binary_sensor.kitchen_patio_door_tilt_contact",
                "tilt_contact",
            ),
            (
                "hall",
                "hall_entry_open",
                "binary_sensor.hall_entry_door_contact",
                "open_contact",
            ),
        )
        retained = None
        note = (
            "Read-only Benni live lookup on 2026-07-30 returned the raw "
            "contact entity, MQTT ownership and current state/history. No "
            "device timestamp or explicit retained marker was exposed."
        )
        question_tail = (
            "Confirm device timestamp availability and distinguish real HA "
            "events from any transport replay."
        )
    else:
        sources = (
            (
                "kitchen",
                "kitchen_left_open",
                "binary_sensor.kitchen_window_left_contact",
                "open_contact",
            ),
            (
                "kitchen",
                "kitchen_right_open",
                "binary_sensor.kitchen_window_right_contact",
                "open_contact",
            ),
            (
                "living",
                "living_patio_open",
                "binary_sensor.living_room_patio_door_contact",
                "open_contact",
            ),
            (
                "bathroom",
                "bathroom_right_open",
                "binary_sensor.bathroom_window_right_contact",
                "open_contact",
            ),
        )
        retained = True
        note = (
            "Read-only Eltern live lookup on 2026-07-23 returned the raw Z2M "
            "contact entity and state."
        )
        question_tail = (
            "Confirm non-retained event evidence per MQTT message and preserve "
            "unknown on replay."
        )

    records: list[SourceBindingEvidence] = []
    for room, suffix, entity, role in sources:
        records.append(
            _raw(
                binding_id=f"{profile_id.value}_opening_{suffix}",
                profile_id=profile_id,
                contract_ref="opening.v1",
                field="opening_state",
                logical_role=role,
                source_entity=entity,
                room=room,
                required=True,
                source_attribute_path="state",
                retained_mqtt_possible=retained,
                fallback=_REJECT,
                quality_relevance=(
                    "contact state, freshness, replay and cross-source conflict "
                    "are field-scoped"
                ),
                safety_relevance=SafetyClass.CONSUMER_CRITICAL,
                evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                consumers=("climate", "blind", "safety"),
                open_question=question_tail,
                evidence_note=note,
            )
        )
    records.extend(
        (
            _derived(
                binding_id=f"{profile_id.value}_opening_is_open_projection",
                profile_id=profile_id,
                contract_ref="opening.v1",
                field="is_open",
                logical_role="projection_from_opening_state_only",
                room=None,
                required=False,
                fallback=_REJECT,
                safety_relevance=SafetyClass.SAFETY_RELEVANT,
                consumers=("climate", "blind", "safety"),
                open_question=(
                    "Confirm that no consumer treats this projection as "
                    "independent evidence."
                ),
            ),
            _derived(
                binding_id=f"{profile_id.value}_opening_available_evidence_gate",
                profile_id=profile_id,
                contract_ref="opening.v1",
                field="available",
                logical_role="all_required_contact_evidence_available",
                room=None,
                required=True,
                fallback=_SAFE_FALSE,
                safety_relevance=SafetyClass.CONSUMER_CRITICAL,
                consumers=("climate", "blind", "safety"),
                open_question=(
                    "Confirm the complete opening set and whether every contact "
                    "is required for the aggregate."
                ),
            ),
            _derived(
                binding_id=f"{profile_id.value}_opening_source_count_diagnostic",
                profile_id=profile_id,
                contract_ref="opening.v1",
                field="source_count",
                logical_role="diagnostic_count_of_evaluated_contacts",
                room=None,
                required=False,
                fallback=_REJECT,
                safety_relevance=SafetyClass.INFORMATIONAL,
                consumers=("diagnostics",),
                open_question=(
                    "Confirm whether the diagnostic count counts configured, "
                    "available, or valid contacts."
                ),
            ),
        )
    )
    return records


def _weather_records(profile_id: ProfileId) -> list[SourceBindingEvidence]:
    if profile_id == ProfileId.BENNI:
        raw = (
            (
                "outdoor_temperature",
                "outdoor_temperature",
                "sensor.garden_climate_temperature",
                "state",
                SafetyClass.SAFETY_RELEVANT,
                ("climate", "blind"),
            ),
            (
                "outdoor_humidity",
                "weather_humidity",
                "weather.dwd_home",
                "attributes.humidity",
                SafetyClass.INFORMATIONAL,
                ("climate",),
            ),
            (
                "pressure",
                "weather_pressure",
                "weather.dwd_home",
                "attributes.pressure",
                SafetyClass.INFORMATIONAL,
                ("weather",),
            ),
            (
                "illuminance",
                "outdoor_illuminance",
                "sensor.garden_light_sensor_illuminance",
                "state",
                SafetyClass.INFORMATIONAL,
                ("blind", "light"),
            ),
            (
                "weather_state",
                "weather_condition",
                "weather.dwd_home",
                "state",
                SafetyClass.INFORMATIONAL,
                ("weather",),
            ),
        )
        note = (
            "Read-only Benni live lookup on 2026-07-23 returned the entity "
            "and expected state/attribute shape."
        )
        retained = None
        open_tail = (
            "Confirm the integration device timestamp or non-retained HA "
            "event semantics."
        )
    else:
        raw = (
            (
                "outdoor_temperature",
                "outdoor_temperature",
                "sensor.garden_temperature_temperature",
                "state",
                SafetyClass.SAFETY_RELEVANT,
                ("climate", "blind"),
            ),
            (
                "outdoor_humidity",
                "outdoor_humidity",
                "sensor.garden_temperature_humidity",
                "state",
                SafetyClass.INFORMATIONAL,
                ("climate",),
            ),
            (
                "illuminance",
                "outdoor_illuminance",
                "sensor.garden_brightness_illuminance",
                "state",
                SafetyClass.INFORMATIONAL,
                ("blind", "light"),
            ),
        )
        note = (
            "Read-only Eltern live lookup on 2026-07-23 returned the entity "
            "and expected state shape."
        )
        retained = True
        open_tail = (
            "Confirm Z2M message freshness and the selected weather-owner "
            "source before production binding."
        )

    records: list[SourceBindingEvidence] = []
    for field, role, entity, path, safety, consumers in raw:
        records.append(
            _raw(
                binding_id=(
                    f"{profile_id.value}_weather_{field}_"
                    f"{entity.split('.', 1)[0]}"
                ),
                profile_id=profile_id,
                contract_ref="weather_environment.v1",
                field=field,
                logical_role=role,
                source_entity=entity,
                room="outdoor",
                required=field == "outdoor_temperature",
                source_attribute_path=path,
                retained_mqtt_possible=retained,
                safety_relevance=safety,
                evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                consumers=consumers,
                open_question=open_tail,
                evidence_note=note,
            )
        )

    if profile_id == ProfileId.ELTERN:
        for field, role, entity in (
            ("pressure", "weather_pressure_candidate", "weather.forecast_home"),
            ("pressure", "weather_pressure_candidate", "weather.pirateweather"),
            ("weather_state", "weather_condition_candidate", "weather.forecast_home"),
            ("weather_state", "weather_condition_candidate", "weather.pirateweather"),
        ):
            path = "attributes.pressure" if field == "pressure" else "state"
            records.append(
                _raw(
                    binding_id=(
                        f"eltern_weather_{field}_"
                        f"{entity.split('.', 1)[1]}"
                    ),
                    profile_id=profile_id,
                    contract_ref="weather_environment.v1",
                    field=field,
                    logical_role=role,
                    source_entity=entity,
                    room="outdoor",
                    required=False,
                    source_attribute_path=path,
                    retained_mqtt_possible=None,
                    safety_relevance=SafetyClass.INFORMATIONAL,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("weather",),
                    open_question=(
                        "Select and document one weather owner; the two live "
                        "sources must not be fused by assumption."
                    ),
                    disposition=BindingDisposition.CONFLICT,
                    evidence_note=(
                        "Read-only Eltern live lookup on 2026-07-23 returned "
                        "both weather entities with usable state/attributes; "
                        "no source-owner decision exists locally."
                    ),
                )
            )
    records.append(
        _derived(
            binding_id=f"{profile_id.value}_weather_available_evidence_gate",
            profile_id=profile_id,
            contract_ref="weather_environment.v1",
            field="available",
            logical_role="required_environment_source_availability_gate",
            room="outdoor",
            required=True,
            fallback=_SAFE_FALSE,
            safety_relevance=SafetyClass.SAFETY_RELEVANT,
            consumers=("climate", "blind", "weather"),
            open_question=(
                "Confirm the required-field set and weather-owner selection "
                "before the gate can pass."
            ),
        )
    )
    return records


def _technical_records(profile_id: ProfileId) -> list[SourceBindingEvidence]:
    records: list[SourceBindingEvidence] = []
    if profile_id == ProfileId.BENNI:
        records.extend(
            (
                _derived(
                    binding_id="benni_technical_rollo_available_evidence_gate",
                    profile_id=profile_id,
                    contract_ref="technical_device.v1",
                    field="available",
                    logical_role="rollo_source_availability_gate",
                    room="living",
                    required=True,
                    fallback=_SAFE_FALSE,
                    safety_relevance=SafetyClass.SAFETY_RELEVANT,
                    consumers=("diagnostics",),
                    open_question=(
                        "Confirm which Rollo source failures make the technical "
                        "device unavailable."
                    ),
                ),
                _raw(
                    binding_id="benni_technical_rollo_device_state",
                    profile_id=profile_id,
                    contract_ref="technical_device.v1",
                    field="device_state",
                    logical_role="cover_state",
                    source_entity="cover.wohnbereich_thermo_verdunklungsrollo",
                    room="living",
                    required=False,
                    source_attribute_path="state",
                    retained_mqtt_possible=None,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("diagnostics",),
                    open_question=(
                        "Confirm device timestamp and state vocabulary; this is "
                        "technical state only, not a target position."
                    ),
                    evidence_note=(
                        "Read-only Benni live lookup on 2026-07-23 returned the "
                        "cover entity with state open."
                    ),
                ),
                _raw(
                    binding_id="benni_technical_rollo_battery",
                    profile_id=profile_id,
                    contract_ref="technical_device.v1",
                    field="battery_level",
                    logical_role="cover_battery",
                    source_entity=(
                        "sensor.wohnbereich_thermo_verdunklungsrollo_battery"
                    ),
                    room="living",
                    required=False,
                    source_attribute_path="state",
                    retained_mqtt_possible=None,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("diagnostics",),
                    open_question=(
                        "Battery is diagnostic only and never proves freshness "
                        "of cover state; confirm timestamp semantics."
                    ),
                    evidence_note=(
                        "Read-only Benni live lookup on 2026-07-23 returned "
                        "the battery entity and percentage state."
                    ),
                ),
                _raw(
                    binding_id="benni_technical_rollo_charging",
                    profile_id=profile_id,
                    contract_ref="technical_device.v1",
                    field="charging",
                    logical_role="cover_charging",
                    source_entity=(
                        "binary_sensor.wohnbereich_thermo_verdunklungsrollo_"
                        "charging_status"
                    ),
                    room="living",
                    required=False,
                    source_attribute_path="state",
                    retained_mqtt_possible=None,
                    evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                    consumers=("diagnostics",),
                    open_question=(
                        "Confirm whether charging state can be retained or "
                        "restored and keep that separate from cover freshness."
                    ),
                    evidence_note=(
                        "Read-only Benni live lookup on 2026-07-23 returned "
                        "the charging entity and state."
                    ),
                ),
            )
        )
        for field in ("is_powered", "power_w"):
            records.append(
                _missing(
                    binding_id=f"benni_technical_rollo_{field}_open",
                    profile_id=profile_id,
                    contract_ref="technical_device.v1",
                    field=field,
                    logical_role="no_direct_rollo_source_evidenced",
                    room="living",
                    required=False,
                    fallback=_REJECT,
                    safety_relevance=SafetyClass.INFORMATIONAL,
                    consumers=("diagnostics",),
                    open_question=(
                        "Do not infer power state or wattage from cover state, "
                        "running, battery, or motor text."
                    ),
                )
            )
    else:
        for field, required, fallback, safety in (
            ("available", True, _SAFE_FALSE, SafetyClass.SAFETY_RELEVANT),
            ("device_state", False, _REJECT, SafetyClass.INFORMATIONAL),
            ("is_powered", False, _REJECT, SafetyClass.INFORMATIONAL),
            ("power_w", False, _REJECT, SafetyClass.INFORMATIONAL),
            ("battery_level", False, _REJECT, SafetyClass.INFORMATIONAL),
            ("charging", False, _REJECT, SafetyClass.INFORMATIONAL),
        ):
            records.append(
                _missing(
                    binding_id=f"eltern_technical_device_{field}_open",
                    profile_id=profile_id,
                    contract_ref="technical_device.v1",
                    field=field,
                    logical_role="no_approved_technical_device_source_evidenced",
                    room=None,
                    required=required,
                    fallback=fallback,
                    safety_relevance=safety,
                    consumers=("diagnostics",),
                    open_question=(
                        "No parent technical-device binding is evidenced; do "
                        "not repurpose thermostat or policy entities without "
                        "an owner decision."
                    ),
                )
            )

    return records


def _special_records(profile_id: ProfileId) -> list[SourceBindingEvidence]:
    if profile_id == ProfileId.BENNI:
        return [
            _special(
                binding_id="benni_rollo_cover_position_evidence_only",
                profile_id=profile_id,
                field="cover_position",
                logical_role="cover_current_position",
                source_entity="cover.wohnbereich_thermo_verdunklungsrollo",
                room="living",
                required=True,
                source_attribute_path="attributes.current_position",
                freshness=_DEVICE_ONLY,
                device_timestamp_present=False,
                ha_state_change_usable=False,
                retained_mqtt_possible=None,
                fallback=_REJECT,
                quality_relevance=(
                    "position evidence must be explicit; absent or stale "
                    "position remains unknown"
                ),
                safety_relevance=SafetyClass.CONSUMER_CRITICAL,
                evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                consumers=("blind", "diagnostics"),
                open_question=(
                    "A real device timestamp or owner-approved equivalent is "
                    "required; no target-position or policy field is introduced."
                ),
                disposition=BindingDisposition.EVIDENCE_ONLY,
                evidence_note=(
                    "Read-only Benni live lookup on 2026-07-23 returned "
                    "current_position=100; this does not prove freshness."
                ),
                ha_observation_path=None,
            ),
            _special(
                binding_id="benni_lock_state_live_id_conflict",
                profile_id=profile_id,
                field="lock_state",
                logical_role="physical_lock_state",
                source_entity=BENNI_CANONICAL_LOCK_ENTITY,
                room="hall",
                required=True,
                source_attribute_path="state",
                freshness=_DEVICE_ONLY,
                device_timestamp_present=False,
                ha_state_change_usable=False,
                retained_mqtt_possible=None,
                fallback=_REJECT,
                quality_relevance=(
                    "lock state is safety-critical; HA-only observation is not "
                    "accepted until timestamp ownership is proven"
                ),
                safety_relevance=SafetyClass.CONSUMER_CRITICAL,
                evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                consumers=("safety", "diagnostics"),
                open_question=(
                    "Reconcile this live ID with the local import and prove a "
                    "reliable device timestamp before any lock contract is designed."
                ),
                disposition=BindingDisposition.CONFLICT,
                evidence_note=(
                    "Read-only Benni domain search found this live lock ID; "
                    "the configured import ID differs and was not found. The "
                    "canonical source remains conflict-blocked until its "
                    "timestamp and source ownership are reconciled."
                ),
                ha_observation_path=None,
                historical_source_entity=HISTORICAL_BENNI_LOCK_ENTITY,
            ),
            _special(
                binding_id="benni_lock_state_historical_import_id",
                profile_id=profile_id,
                field="lock_state",
                logical_role="historical_import_lock_id_not_current",
                source_entity=None,
                room="hall",
                required=True,
                source_attribute_path=None,
                freshness=_DEVICE_ONLY,
                device_timestamp_present=None,
                ha_state_change_usable=None,
                retained_mqtt_possible=None,
                fallback=_REJECT,
                quality_relevance=(
                    "configured identifier is not live evidence and cannot "
                    "pass the safety gate"
                ),
                safety_relevance=SafetyClass.CONSUMER_CRITICAL,
                evidence_class=BindingEvidenceClass.KONFIGURIERT,
                consumers=("safety", "diagnostics"),
                open_question=(
                    "This historical import ID is not a current binding. "
                    "Revalidate the live registry before recording any future "
                    "lock source."
                ),
                disposition=BindingDisposition.OPEN,
                evidence_note=(
                    "Configured in the read-only local Core-Devices import; "
                    "live lookup returned ENTITY_NOT_FOUND. It is retained "
                    "only as historical evidence."
                ),
                ha_observation_path=None,
                historical_source_entity=HISTORICAL_BENNI_LOCK_ENTITY,
            ),
            _special(
                binding_id="benni_lock_battery_live_id",
                profile_id=profile_id,
                field="lock_battery",
                logical_role="physical_lock_battery_diagnostic",
                source_entity="sensor.flur_aqara_smart_lock_u200_batterie",
                room="hall",
                required=False,
                source_attribute_path="state",
                freshness=_DEVICE_OR_HA,
                device_timestamp_present=False,
                ha_state_change_usable=True,
                retained_mqtt_possible=None,
                fallback=_REJECT,
                quality_relevance=(
                    "battery quality is diagnostic only and never establishes "
                    "lock-state freshness"
                ),
                safety_relevance=SafetyClass.SAFETY_RELEVANT,
                evidence_class=BindingEvidenceClass.LIVE_VERIFIZIERT,
                consumers=("diagnostics",),
                open_question=(
                    "Reconcile the battery ID with the local import and document "
                    "its device timestamp separately from lock state."
                ),
                disposition=BindingDisposition.CONFLICT,
                evidence_note=(
                    "Read-only Benni sensor search found the live battery "
                    "entity; the configured import ID differs."
                ),
                historical_source_entity=HISTORICAL_BENNI_LOCK_BATTERY_ENTITY,
            ),
            _special(
                binding_id="benni_lock_battery_historical_import_id",
                profile_id=profile_id,
                field="lock_battery",
                logical_role="historical_import_lock_battery_id_not_current",
                source_entity=None,
                room="hall",
                required=False,
                source_attribute_path=None,
                freshness=_DEVICE_OR_HA,
                device_timestamp_present=None,
                ha_state_change_usable=None,
                retained_mqtt_possible=None,
                fallback=_REJECT,
                quality_relevance=(
                    "configured identifier is not live evidence; battery is "
                    "never a freshness proof"
                ),
                safety_relevance=SafetyClass.SAFETY_RELEVANT,
                evidence_class=BindingEvidenceClass.KONFIGURIERT,
                consumers=("diagnostics",),
                open_question=(
                    "This historical import ID is not a current binding. "
                    "Revalidate the live registry; battery never proves lock "
                    "freshness."
                ),
                disposition=BindingDisposition.OPEN,
                evidence_note=(
                    "Configured in the read-only local Core-Devices import; "
                    "live lookup returned ENTITY_NOT_FOUND. It is retained "
                    "only as historical evidence."
                ),
                ha_observation_path=None,
                historical_source_entity=HISTORICAL_BENNI_LOCK_BATTERY_ENTITY,
            ),
            _special(
                binding_id="benni_rollo_legacy_policy_cover_excluded",
                profile_id=profile_id,
                field="cover_position",
                logical_role="documented_policy_cover_not_a_raw_source",
                source_entity="cover.living_blackout_blind",
                room="living",
                required=False,
                source_attribute_path="attributes.current_position",
                freshness=_DEVICE_ONLY,
                device_timestamp_present=None,
                ha_state_change_usable=None,
                retained_mqtt_possible=None,
                fallback=_REJECT,
                quality_relevance="documented policy target is not raw source evidence",
                safety_relevance=SafetyClass.CONSUMER_CRITICAL,
                evidence_class=BindingEvidenceClass.DOKUMENTIERT,
                consumers=("diagnostics",),
                open_question=(
                    "Keep this policy-facing identifier outside the new source "
                    "graph; verify only through its owner if needed."
                ),
                disposition=BindingDisposition.EXCLUDED,
                evidence_note=(
                    "Mentioned in local integration documentation as a policy "
                    "target; deliberately excluded from active sources."
                ),
                ha_observation_path=None,
            ),
        ]

    return [
        _special(
            binding_id="eltern_rollo_cover_position_open",
            profile_id=profile_id,
            field="cover_position",
            logical_role="no_parent_cover_source_evidenced",
            source_entity=None,
            room="living",
            required=True,
            source_attribute_path=None,
            freshness=_DEVICE_ONLY,
            device_timestamp_present=None,
            ha_state_change_usable=None,
            retained_mqtt_possible=None,
            fallback=_REJECT,
            quality_relevance="no position evidence; physical position remains unknown",
            safety_relevance=SafetyClass.CONSUMER_CRITICAL,
            evidence_class=BindingEvidenceClass.OFFEN,
            consumers=("blind", "diagnostics"),
            open_question=(
                "Parent live domain search returned no cover entity; identify "
                "and verify a real raw cover source before any position binding."
            ),
            disposition=BindingDisposition.OPEN,
            evidence_note=(
                "No concrete parent cover entity was found in the read-only "
                "live domain listing."
            ),
            ha_observation_path=None,
        ),
        _special(
            binding_id="eltern_lock_state_open",
            profile_id=profile_id,
            field="lock_state",
            logical_role="no_parent_lock_source_evidenced",
            source_entity=None,
            room="hall",
            required=True,
            source_attribute_path=None,
            freshness=_DEVICE_ONLY,
            device_timestamp_present=None,
            ha_state_change_usable=None,
            retained_mqtt_possible=None,
            fallback=_REJECT,
            quality_relevance="no lock evidence; physical lock state remains unknown",
            safety_relevance=SafetyClass.CONSUMER_CRITICAL,
            evidence_class=BindingEvidenceClass.OFFEN,
            consumers=("safety", "diagnostics"),
            open_question=(
                "Parent live domain search returned no lock entity; identify "
                "a real source and prove device-time evidence before designing "
                "a lock contract."
            ),
            disposition=BindingDisposition.OPEN,
            evidence_note=(
                "No concrete parent lock entity was found in the read-only "
                "live domain listing."
            ),
            ha_observation_path=None,
        ),
    ]


def source_binding_matrix_v1() -> SourceBindingEvidenceMatrix:
    """Return the immutable v1 evidence matrix.

    The function constructs evidence records only. It never reads a
    ConfigEntry, writes the HA store, attaches listeners, or creates entities.
    """

    records: list[SourceBindingEvidence] = []
    for profile_id in (ProfileId.BENNI, ProfileId.ELTERN):
        records.extend(_climate_records(profile_id))
        records.extend(_opening_records(profile_id))
        records.extend(_weather_records(profile_id))
        records.extend(_technical_records(profile_id))
        records.extend(_special_records(profile_id))
    return SourceBindingEvidenceMatrix(
        version=SOURCE_BINDING_EVIDENCE_VERSION,
        records=tuple(records),
    )


def evidence_classes() -> tuple[BindingEvidenceClass, ...]:
    """Expose the exact evidence vocabulary for docs, tests and diagnostics."""

    return tuple(BindingEvidenceClass)


def iter_open_records(
    records: Iterable[SourceBindingEvidence],
) -> tuple[SourceBindingEvidence, ...]:
    """Return records with no evidenced concrete source."""

    return tuple(record for record in records if record.source_entity is None)
