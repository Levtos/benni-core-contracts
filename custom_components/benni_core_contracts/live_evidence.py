"""Read-only Benni live-evidence acquisition model.

The acquisition gate deliberately does not contact Home Assistant. It accepts
one explicitly supplied, sanitised read-only snapshot and evaluates whether
that snapshot is sufficient for a matrix record. This keeps network access,
credentials and ConfigEntry activation outside the contract package while
still making the live-evidence boundary executable and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .evidence_gate import EvidenceGateStatus
from .models import ProfileId
from .quality import (
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    QualityStatus,
    SafetyClass,
    SafetyStatus,
    TemporalEvidence,
)
from .source_binding_evidence import (
    BENNI_CANONICAL_LOCK_ENTITY,
    HISTORICAL_BENNI_LOCK_ENTITY,
    BindingDisposition,
    BindingEvidenceClass,
    SourceBindingEvidence,
    SourceBindingEvidenceMatrix,
    assess_source_binding_evidence,
)


LIVE_EVIDENCE_ACQUISITION_VERSION = 1
UNKNOWN_VALUE = "unknown"
HA_STATE_CHANGE_ORIGIN = "ha_state_change"

PHYSICAL_FIELDS = frozenset(
    {
        "opening_state",
        "is_open",
        "lock_state",
        "cover_position",
    }
)
CAPABILITIES = frozenset(
    {
        "climate",
        "opening",
        "blind",
        "cover",
        "weather",
        "device",
        "diagnostics",
        "lock",
        "safety",
    }
)
SENSITIVE_ATTRIBUTE_MARKERS = (
    "token",
    "password",
    "secret",
    "cookie",
    "authorization",
)


class LiveEvidenceStatus(str, Enum):
    """Status of the current acquisition attempt, not a publish decision."""

    PASS = "pass"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    OPEN = "OPEN"


@dataclass(frozen=True)
class ReadOnlySourceSnapshot:
    """Small, sanitised state snapshot supplied by an external read-only probe.

    The snapshot stores only selected state, attributes and timing metadata.
    It has no Home Assistant client, credential, write method or activation
    authority. last_updated and received_at are retained for audit context
    and are never sufficient freshness evidence by themselves.
    """

    entity_id: str
    state: Any = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    available: bool | None = None
    last_changed: datetime | None = None
    last_updated: datetime | None = None
    device_timestamp: datetime | None = None
    received_at: datetime | None = None
    event_origin: str | None = None
    ha_state_event: bool = False
    retained: bool = False
    restored: bool = False
    stale: bool = False
    source_owner: str | None = None
    competing_sources: tuple[str, ...] = ()
    evidence_class: BindingEvidenceClass = BindingEvidenceClass.ANNAHME

    def __post_init__(self) -> None:
        if self.entity_id.count(".") != 1 or "*" in self.entity_id:
            raise ValueError("entity_id must be one concrete entity ID")
        if self.entity_id == HISTORICAL_BENNI_LOCK_ENTITY:
            raise ValueError(
                "historical Benni lock ID cannot be used as a current source"
            )
        if not isinstance(self.attributes, Mapping):
            raise ValueError("attributes must be a mapping")
        for key in self.attributes:
            lowered = str(key).lower()
            if any(marker in lowered for marker in SENSITIVE_ATTRIBUTE_MARKERS):
                raise ValueError(
                    "sanitised snapshots cannot contain credential-like attributes"
                )
        for timestamp_name in (
            "last_changed",
            "last_updated",
            "device_timestamp",
            "received_at",
        ):
            timestamp = getattr(self, timestamp_name)
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError(f"{timestamp_name} must be timezone-aware")
        if self.event_origin is not None and not self.event_origin:
            raise ValueError("event_origin must not be empty")
        if any(
            entity_id.count(".") != 1 or "*" in entity_id
            for entity_id in self.competing_sources
        ):
            raise ValueError("competing_sources must contain concrete entity IDs")

    @property
    def ha_domain(self) -> str:
        return self.entity_id.split(".", 1)[0]

    def temporal_evidence(self, checked_at: datetime) -> TemporalEvidence:
        """Convert explicit snapshot metadata without inventing freshness."""

        received_at = self.received_at or checked_at
        if self.restored:
            return TemporalEvidence(
                received_at=received_at,
                origin=FreshnessOrigin.RESTORE,
                restored=True,
            )
        if self.retained:
            return TemporalEvidence(
                received_at=received_at,
                origin=FreshnessOrigin.RETAINED_MQTT,
                retained=True,
            )
        if self.device_timestamp is not None:
            return TemporalEvidence(
                received_at=received_at,
                origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                device_timestamp=self.device_timestamp,
            )
        if (
            self.ha_state_event
            and self.event_origin == HA_STATE_CHANGE_ORIGIN
            and self.last_changed is not None
        ):
            return TemporalEvidence(
                received_at=received_at,
                origin=FreshnessOrigin.HA_TIMESTAMP,
                ha_timestamp=self.last_changed,
                ha_state_event=True,
            )
        # A last_updated value without an explicit event is intentionally not
        # promoted to HA_TIMESTAMP. received_at is equally non-authoritative.
        return TemporalEvidence(
            received_at=received_at,
            origin=FreshnessOrigin.UNKNOWN,
        )

    def as_dict(self) -> dict[str, Any]:
        def iso(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        return {
            "entity_id": self.entity_id,
            "domain": self.ha_domain,
            "state": self.state,
            "attributes": dict(self.attributes),
            "available": self.available,
            "last_changed": iso(self.last_changed),
            "last_updated": iso(self.last_updated),
            "device_timestamp": iso(self.device_timestamp),
            "received_at": iso(self.received_at),
            "event_origin": self.event_origin,
            "ha_state_event": self.ha_state_event,
            "retained": self.retained,
            "restored": self.restored,
            "stale": self.stale,
            "source_owner": self.source_owner,
            "competing_sources": list(self.competing_sources),
            "evidence_class": self.evidence_class.value,
        }


@dataclass(frozen=True)
class LiveFieldEvidence:
    """Current acquisition result for one matrix field."""

    version: int
    binding_id: str
    contract_ref: str | None
    profile_id: ProfileId
    field: str
    logical_role: str
    room: str | None
    required: bool
    status: LiveEvidenceStatus
    gate_status: EvidenceGateStatus
    value: Any
    source_entity: str | None
    active_source_entity: str | None
    ha_domain: str | None
    source_state: Any
    relevant_attributes: Mapping[str, Any]
    available: bool | None
    last_changed: datetime | None
    last_updated: datetime | None
    device_timestamp: datetime | None
    received_at: datetime | None
    event_origin: str | None
    source_owner: str | None
    competing_sources: tuple[str, ...]
    evidence_class: BindingEvidenceClass
    freshness: FreshnessStatus
    quality: QualityStatus
    health: HealthStatus
    safety: SafetyStatus
    safety_relevance: SafetyClass
    root_cause: str
    reason_codes: tuple[str, ...]
    fallback_chain: tuple[str, ...]
    affected_capabilities: tuple[str, ...]
    unaffected_capabilities: tuple[str, ...]
    consumer_impact: str
    checked_at: datetime

    def __post_init__(self) -> None:
        if self.version != LIVE_EVIDENCE_ACQUISITION_VERSION:
            raise ValueError("unsupported live evidence acquisition version")
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("live evidence acquisition is Benni-only")
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        if self.source_entity is not None:
            if self.source_entity.count(".") != 1 or "*" in self.source_entity:
                raise ValueError("source_entity must be one concrete entity ID")
            if self.source_entity == HISTORICAL_BENNI_LOCK_ENTITY:
                raise ValueError(
                    "historical Benni lock ID cannot be an acquisition source"
                )
        if self.active_source_entity == HISTORICAL_BENNI_LOCK_ENTITY:
            raise ValueError("historical Benni lock ID cannot be active")
        if self.field in PHYSICAL_FIELDS and self.status != LiveEvidenceStatus.PASS:
            if self.value not in (UNKNOWN_VALUE, None):
                raise ValueError(
                    "physical fields cannot claim a value without passing evidence"
                )

    @property
    def contract_id(self) -> str | None:
        if self.contract_ref is None:
            return None
        return self.contract_ref.rsplit(".v", 1)[0]

    @property
    def schema_version(self) -> int | None:
        if self.contract_ref is None:
            return None
        try:
            return int(self.contract_ref.rsplit(".v", 1)[1])
        except (IndexError, ValueError):
            return None

    @property
    def is_open(self) -> bool:
        return self.status == LiveEvidenceStatus.OPEN

    def as_dict(self) -> dict[str, Any]:
        def iso(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        return {
            "acquisition_version": self.version,
            "binding_id": self.binding_id,
            "contract": self.contract_ref,
            "contract_id": self.contract_id,
            "schema_version": self.schema_version,
            "profile": self.profile_id.value,
            "field": self.field,
            "logical_role": self.logical_role,
            "room": self.room,
            "required": self.required,
            "status": self.status.value,
            "gate_status": self.gate_status.value,
            "value": self.value,
            "source_entity": self.source_entity,
            "active_source_entity": self.active_source_entity,
            "ha_domain": self.ha_domain,
            "source_state": self.source_state,
            "relevant_attributes": dict(self.relevant_attributes),
            "available": self.available,
            "last_changed": iso(self.last_changed),
            "last_updated": iso(self.last_updated),
            "device_timestamp": iso(self.device_timestamp),
            "received_at": iso(self.received_at),
            "event_origin": self.event_origin,
            "source_owner": self.source_owner,
            "competing_sources": list(self.competing_sources),
            "evidence_class": self.evidence_class.value,
            "freshness": self.freshness.value,
            "quality": self.quality.value,
            "health": self.health.value,
            "safety": self.safety.value,
            "safety_relevance": self.safety_relevance.value,
            "root_cause": self.root_cause,
            "reason_codes": list(self.reason_codes),
            "fallback_chain": list(self.fallback_chain),
            "affected_capabilities": list(self.affected_capabilities),
            "unaffected_capabilities": list(self.unaffected_capabilities),
            "consumer_impact": self.consumer_impact,
            "checked_at": iso(self.checked_at),
        }


@dataclass(frozen=True)
class LiveEvidenceAcquisitionReport:
    """Versioned, read-only acquisition result with a hard no-activation edge."""

    version: int
    profile_id: ProfileId
    checked_at: datetime
    endpoint: str
    status: LiveEvidenceStatus
    access_reason: str
    fields: tuple[LiveFieldEvidence, ...]
    config_entry_activated: bool = False
    source_bindings_activated: bool = False
    published: bool = False
    entity_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.version != LIVE_EVIDENCE_ACQUISITION_VERSION:
            raise ValueError("unsupported live evidence acquisition version")
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("live evidence acquisition is Benni-only")
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        if (
            self.config_entry_activated
            or self.source_bindings_activated
            or self.published
            or self.entity_ids
        ):
            raise ValueError(
                "live evidence acquisition cannot activate, publish or create entities"
            )
        if any(field.profile_id != self.profile_id for field in self.fields):
            raise ValueError("report fields must use the report profile")

    @property
    def open_fields(self) -> tuple[str, ...]:
        return tuple(
            field.field
            for field in self.fields
            if field.status == LiveEvidenceStatus.OPEN
        )

    @property
    def blocked_fields(self) -> tuple[str, ...]:
        return tuple(
            field.field
            for field in self.fields
            if field.status == LiveEvidenceStatus.BLOCKED
        )

    @property
    def source_entities(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    field.source_entity
                    for field in self.fields
                    if field.source_entity is not None
                }
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "acquisition_version": self.version,
            "profile": self.profile_id.value,
            "checked_at": self.checked_at.isoformat(),
            "endpoint": self.endpoint,
            "status": self.status.value,
            "access_reason": self.access_reason,
            "open_fields": list(self.open_fields),
            "blocked_fields": list(self.blocked_fields),
            "source_entities": list(self.source_entities),
            "fields": [field.as_dict() for field in self.fields],
            "config_entry_activated": self.config_entry_activated,
            "source_bindings_activated": self.source_bindings_activated,
            "published": self.published,
            "entity_ids": list(self.entity_ids),
        }


def _is_physical(record: SourceBindingEvidence) -> bool:
    return record.field in PHYSICAL_FIELDS


def _gate_status(
    status: LiveEvidenceStatus,
    *,
    required: bool,
) -> EvidenceGateStatus:
    if status == LiveEvidenceStatus.PASS:
        return EvidenceGateStatus.PASS
    if required:
        return EvidenceGateStatus.BLOCKED
    return EvidenceGateStatus.DEGRADED


def _failure_safety(record: SourceBindingEvidence) -> SafetyStatus:
    if _is_physical(record):
        return SafetyStatus.UNKNOWN
    if record.safety_relevance != SafetyClass.INFORMATIONAL:
        return SafetyStatus.BLOCKED
    return SafetyStatus.UNKNOWN


def _failure_quality(
    *,
    freshness: FreshnessStatus,
    reason: str,
) -> QualityStatus:
    if reason == "source_conflict":
        return QualityStatus.CONFLICT
    if freshness == FreshnessStatus.STALE:
        return QualityStatus.STALE
    if freshness == FreshnessStatus.SUSPECT:
        return QualityStatus.SUSPECT
    if freshness == FreshnessStatus.RESTORED:
        return QualityStatus.UNKNOWN
    if reason in {"source_unavailable", "source_state_unavailable"}:
        return QualityStatus.UNAVAILABLE
    return QualityStatus.UNKNOWN


def _status_for_failure(
    record: SourceBindingEvidence,
    *,
    open_evidence: bool = False,
) -> LiveEvidenceStatus:
    if open_evidence and not _is_physical(record):
        return LiveEvidenceStatus.OPEN
    if record.required or _is_physical(record):
        return LiveEvidenceStatus.BLOCKED
    return LiveEvidenceStatus.DEGRADED


def _reason_for_freshness(
    freshness: FreshnessStatus,
    assessment_reason: str,
) -> str:
    if freshness == FreshnessStatus.STALE:
        return "source_stale"
    if freshness == FreshnessStatus.RESTORED:
        return "source_restored"
    if freshness == FreshnessStatus.SUSPECT:
        return "source_retained"
    if freshness == FreshnessStatus.UNKNOWN:
        if assessment_reason in {
            "device_timestamp_not_evidenced",
            "ha_state_change_not_evidenced",
            "freshness_timestamp_unknown",
            "source_freshness_origin_not_allowed",
        }:
            return "freshness_not_evidenced"
        return assessment_reason or "freshness_unknown"
    return assessment_reason or "source_not_accepted"


def _make_result(
    record: SourceBindingEvidence,
    snapshot: ReadOnlySourceSnapshot | None,
    *,
    checked_at: datetime,
    status: LiveEvidenceStatus,
    freshness: FreshnessStatus,
    quality: QualityStatus,
    health: HealthStatus,
    safety: SafetyStatus,
    reason_codes: tuple[str, ...],
    value: Any = UNKNOWN_VALUE,
    active_source_entity: str | None = None,
    source_state: Any = None,
    relevant_attributes: Mapping[str, Any] | None = None,
    source_owner: str | None = None,
    competing_sources: tuple[str, ...] = (),
    evidence_class: BindingEvidenceClass = BindingEvidenceClass.OFFEN,
) -> LiveFieldEvidence:
    consumers = tuple(record.consumers)
    unaffected = tuple(sorted(CAPABILITIES.difference(consumers)))
    root_cause = reason_codes[0] if reason_codes else "live_evidence_not_assessed"
    return LiveFieldEvidence(
        version=LIVE_EVIDENCE_ACQUISITION_VERSION,
        binding_id=record.binding_id,
        contract_ref=record.contract_ref,
        profile_id=record.profile_id,
        field=record.field,
        logical_role=record.logical_role,
        room=record.room,
        required=record.required,
        status=status,
        gate_status=_gate_status(status, required=record.required),
        value=value,
        source_entity=record.source_entity,
        active_source_entity=active_source_entity,
        ha_domain=record.ha_domain,
        source_state=source_state,
        relevant_attributes=dict(relevant_attributes or {}),
        available=snapshot.available if snapshot else None,
        last_changed=snapshot.last_changed if snapshot else None,
        last_updated=snapshot.last_updated if snapshot else None,
        device_timestamp=snapshot.device_timestamp if snapshot else None,
        received_at=snapshot.received_at if snapshot else None,
        event_origin=snapshot.event_origin if snapshot else None,
        source_owner=source_owner,
        competing_sources=competing_sources,
        evidence_class=evidence_class,
        freshness=freshness,
        quality=quality,
        health=health,
        safety=safety,
        safety_relevance=record.safety_relevance,
        root_cause=root_cause,
        reason_codes=reason_codes,
        fallback_chain=(record.fallback.action.value,),
        affected_capabilities=consumers,
        unaffected_capabilities=unaffected,
        consumer_impact=(
            "not_activated; field-scoped evidence only"
            if status == LiveEvidenceStatus.PASS
            else "field remains unavailable to consumers until evidence gate passes"
        ),
        checked_at=checked_at,
    )


def assess_live_source(
    record: SourceBindingEvidence,
    snapshot: ReadOnlySourceSnapshot | None,
    *,
    checked_at: datetime,
    ttl_seconds: int | None = None,
) -> LiveFieldEvidence:
    """Assess one explicit snapshot without changing the matrix or runtime.

    OPEN means that acquisition evidence is still missing or unresolved.
    gate_status makes the downstream consequence explicit: a required field
    remains blocked even when its acquisition status is OPEN.
    """

    if record.profile_id != ProfileId.BENNI:
        raise ValueError("live evidence acquisition accepts Benni records only")
    if checked_at.tzinfo is None:
        raise ValueError("checked_at must be timezone-aware")
    if record.source_entity == HISTORICAL_BENNI_LOCK_ENTITY:
        raise ValueError("historical Benni lock ID cannot be a current source")
    if snapshot is not None:
        if snapshot.entity_id != record.source_entity:
            raise ValueError("snapshot entity does not match matrix source")
        if snapshot.entity_id == HISTORICAL_BENNI_LOCK_ENTITY:
            raise ValueError("historical Benni lock ID cannot be observed as current")

    if record.source_entity is None or snapshot is None:
        reason = (
            "source_projection_not_obtained"
            if record.source_entity is None
            else "live_snapshot_not_obtained"
        )
        status = _status_for_failure(record, open_evidence=True)
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=status,
            freshness=FreshnessStatus.UNKNOWN,
            quality=QualityStatus.UNKNOWN,
            health=(
                HealthStatus.BLOCKED
                if record.required or _is_physical(record)
                else HealthStatus.UNKNOWN
            ),
            safety=_failure_safety(record),
            reason_codes=(reason, "live_evidence_open"),
        )

    temporal = snapshot.temporal_evidence(checked_at)
    ttl = ttl_seconds or 900
    assessment = assess_source_binding_evidence(
        record,
        temporal,
        now=checked_at,
        ttl_seconds=ttl,
    )
    freshness = assessment.freshness
    assessment_reason = assessment.reason

    if snapshot.stale:
        freshness = FreshnessStatus.STALE
        assessment_reason = "source_stale"
    reason = _reason_for_freshness(freshness, assessment_reason)

    if snapshot.competing_sources or record.disposition == BindingDisposition.CONFLICT:
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=LiveEvidenceStatus.BLOCKED,
            freshness=freshness,
            quality=QualityStatus.CONFLICT,
            health=HealthStatus.BLOCKED,
            safety=_failure_safety(record),
            reason_codes=("source_conflict",),
            source_state=snapshot.state,
            relevant_attributes=snapshot.attributes,
            source_owner=snapshot.source_owner,
            competing_sources=snapshot.competing_sources,
            evidence_class=snapshot.evidence_class,
        )

    raw_state = snapshot.state
    state_unavailable = (
        snapshot.available is False
        or raw_state is None
        or (
            isinstance(raw_state, str)
            and raw_state in {"unavailable", "unknown"}
        )
    )
    if state_unavailable:
        unavailable_reason = (
            "source_unavailable"
            if snapshot.available is False or raw_state is None
            else "source_state_unknown"
        )
        status = _status_for_failure(record)
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=status,
            freshness=freshness,
            quality=(
                QualityStatus.UNAVAILABLE
                if unavailable_reason == "source_unavailable"
                else QualityStatus.UNKNOWN
            ),
            health=(
                HealthStatus.BLOCKED
                if record.required or _is_physical(record)
                else HealthStatus.DEGRADED
            ),
            safety=_failure_safety(record),
            reason_codes=(unavailable_reason,),
            source_state=raw_state,
            relevant_attributes=snapshot.attributes,
            source_owner=snapshot.source_owner,
            evidence_class=snapshot.evidence_class,
        )

    if not snapshot.source_owner or snapshot.source_owner == "OPEN":
        status = _status_for_failure(
            record,
            open_evidence=not _is_physical(record),
        )
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=status,
            freshness=freshness,
            quality=QualityStatus.UNKNOWN,
            health=(
                HealthStatus.BLOCKED
                if record.required or _is_physical(record)
                else HealthStatus.UNKNOWN
            ),
            safety=_failure_safety(record),
            reason_codes=("source_ownership_unverified", "live_evidence_open"),
            source_state=raw_state,
            relevant_attributes=snapshot.attributes,
            source_owner=snapshot.source_owner,
            competing_sources=snapshot.competing_sources,
            evidence_class=snapshot.evidence_class,
        )

    if (
        freshness == FreshnessStatus.FRESH
        and record.disposition
        not in {BindingDisposition.CANDIDATE, BindingDisposition.DERIVED}
    ):
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=LiveEvidenceStatus.BLOCKED,
            freshness=freshness,
            quality=QualityStatus.DEGRADED,
            health=HealthStatus.BLOCKED,
            safety=_failure_safety(record),
            reason_codes=("binding_not_publishable",),
            source_state=raw_state,
            relevant_attributes=snapshot.attributes,
            source_owner=snapshot.source_owner,
            evidence_class=snapshot.evidence_class,
        )

    if not assessment.accepted or freshness != FreshnessStatus.FRESH:
        status = _status_for_failure(
            record,
            open_evidence=freshness == FreshnessStatus.UNKNOWN,
        )
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=status,
            freshness=freshness,
            quality=_failure_quality(freshness=freshness, reason=reason),
            health=(
                HealthStatus.BLOCKED
                if record.required or _is_physical(record)
                else HealthStatus.DEGRADED
            ),
            safety=_failure_safety(record),
            reason_codes=(reason,),
            source_state=raw_state,
            relevant_attributes=snapshot.attributes,
            source_owner=snapshot.source_owner,
            evidence_class=snapshot.evidence_class,
        )

    if record.disposition not in {
        BindingDisposition.CANDIDATE,
        BindingDisposition.DERIVED,
    }:
        return _make_result(
            record,
            snapshot,
            checked_at=checked_at,
            status=LiveEvidenceStatus.BLOCKED,
            freshness=freshness,
            quality=QualityStatus.DEGRADED,
            health=HealthStatus.BLOCKED,
            safety=_failure_safety(record),
            reason_codes=("binding_not_publishable",),
            source_state=raw_state,
            relevant_attributes=snapshot.attributes,
            source_owner=snapshot.source_owner,
            evidence_class=snapshot.evidence_class,
        )

    return _make_result(
        record,
        snapshot,
        checked_at=checked_at,
        status=LiveEvidenceStatus.PASS,
        freshness=FreshnessStatus.FRESH,
        quality=QualityStatus.GOOD,
        health=HealthStatus.HEALTHY,
        safety=SafetyStatus.VALID,
        reason_codes=("live_evidence_valid_not_activated",),
        value=raw_state,
        active_source_entity=record.source_entity,
        source_state=raw_state,
        relevant_attributes=snapshot.attributes,
        source_owner=snapshot.source_owner,
        competing_sources=snapshot.competing_sources,
        evidence_class=snapshot.evidence_class,
    )


def build_open_benni_acquisition_report(
    matrix: SourceBindingEvidenceMatrix,
    *,
    checked_at: datetime,
    endpoint: str,
    blocker: str,
) -> LiveEvidenceAcquisitionReport:
    """Build the explicit OPEN report used when live state cannot be read."""

    records = tuple(
        record for record in matrix.records if record.profile_id == ProfileId.BENNI
    )
    fields = tuple(
        assess_live_source(record, None, checked_at=checked_at)
        for record in records
    )
    return LiveEvidenceAcquisitionReport(
        version=LIVE_EVIDENCE_ACQUISITION_VERSION,
        profile_id=ProfileId.BENNI,
        checked_at=checked_at,
        endpoint=endpoint,
        status=LiveEvidenceStatus.OPEN,
        access_reason=blocker,
        fields=fields,
    )


def current_lock_entity_ids() -> tuple[str, str]:
    """Expose the candidate/history pair without making either active."""

    return BENNI_CANONICAL_LOCK_ENTITY, HISTORICAL_BENNI_LOCK_ENTITY
