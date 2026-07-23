"""Benni-only Owner-/Required-Field-Gate v1.

This gate defines the production owner scope and evaluates required-field
evidence without activating a ConfigEntry, publishing an entity, or making a
policy decision. Eltern remains part of the shared schema/graph test surface,
but is explicitly outside the production scope of this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .contracts import default_schema_registry
from .evidence_gate import EvidenceGateStatus
from .models import ProfileId, ProfileScope
from .quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessOrigin,
    FreshnessRequirement,
    FreshnessStatus,
    HealthStatus,
    QualityStatus,
    SafetyClass,
    SafetyStatus,
    TemporalEvidence,
    ValueState,
)
from .schema import ContractFieldSchema, ContractSchema, SchemaRegistry
from .source_binding_evidence import (
    BindingDisposition,
    BindingKind,
    SourceBindingEvidence,
    SourceBindingEvidenceMatrix,
    assess_source_binding_evidence,
    source_binding_matrix_v1,
)


OWNER_REQUIRED_FIELD_GATE_VERSION = 1
_MISSING = object()


class RequiredEvidenceSelection(str, Enum):
    """How a required field consumes its source evidence."""

    ANY_HEALTHY = "any_healthy"
    ALL_REQUIRED = "all_required"
    DERIVED = "derived"


@dataclass(frozen=True)
class RequiredFieldSpec:
    """One Benni-owned required-field rule derived from a v1 schema."""

    key: str
    profile_id: ProfileId
    activation_scope: ProfileScope
    contract_ref: str
    field: str
    room: str | None
    required: bool
    physical_state: bool
    safety_class: SafetyClass
    fallback: FallbackPolicy
    freshness_requirement: FreshnessRequirement
    allowed_freshness_origins: tuple[FreshnessOrigin, ...]
    selection: RequiredEvidenceSelection
    binding_ids: tuple[str, ...]
    source_entities: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    derived_from_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("RequiredFieldSpec is Benni-only")
        if self.activation_scope != ProfileScope.BENNI_PRODUCTION:
            raise ValueError("Benni required fields need benni_production scope")
        if not self.required:
            raise ValueError("RequiredFieldSpec must describe a required field")
        if not self.key or not self.contract_ref or not self.field:
            raise ValueError("required-field identity is incomplete")
        if not self.binding_ids:
            raise ValueError("required field needs matrix lineage")
        if not self.allowed_freshness_origins:
            raise ValueError("required field needs allowed freshness origins")
        if self.physical_state and self.fallback.action != FallbackAction.REJECT:
            raise ValueError("physical required fields must use fallback=reject")
        if self.selection == RequiredEvidenceSelection.DERIVED:
            if not self.derived_from_keys:
                raise ValueError("derived required fields need dependencies")
        elif self.derived_from_keys:
            raise ValueError("raw required fields cannot declare derived dependencies")

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "profile_id": self.profile_id.value,
            "activation_scope": self.activation_scope.value,
            "contract": self.contract_ref,
            "field": self.field,
            "room": self.room,
            "required": self.required,
            "physical_state": self.physical_state,
            "safety_class": self.safety_class.value,
            "fallback": self.fallback.as_dict(),
            "freshness_requirement": self.freshness_requirement.value,
            "allowed_freshness_origins": [
                origin.value for origin in self.allowed_freshness_origins
            ],
            "selection": self.selection.value,
            "binding_ids": list(self.binding_ids),
            "source_entities": list(self.source_entities),
            "consumer_ids": list(self.consumer_ids),
            "derived_from_keys": list(self.derived_from_keys),
        }


@dataclass(frozen=True)
class RequiredFieldDecision:
    """Read-only result for one required field."""

    key: str
    contract_ref: str
    field: str
    room: str | None
    status: EvidenceGateStatus
    value_state: ValueState
    health: HealthStatus
    quality: QualityStatus
    freshness: FreshnessStatus
    safety: SafetyStatus
    active_binding_ids: tuple[str, ...]
    source_entities: tuple[str, ...]
    completeness: bool
    physical_claim_allowed: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "contract": self.contract_ref,
            "field": self.field,
            "room": self.room,
            "status": self.status.value,
            "value_state": self.value_state.value,
            "health": self.health.value,
            "quality": self.quality.value,
            "freshness": self.freshness.value,
            "safety": self.safety.value,
            "active_binding_ids": list(self.active_binding_ids),
            "source_entities": list(self.source_entities),
            "completeness": self.completeness,
            "physical_claim_allowed": self.physical_claim_allowed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class OwnerRequiredGateResult:
    """Aggregate result; it never authorizes activation."""

    gate_id: str
    version: int
    profile_id: ProfileId
    activation_scope: ProfileScope
    status: EvidenceGateStatus
    required_fields_ready: bool
    activation_allowed: bool
    fields: tuple[RequiredFieldDecision, ...]

    @property
    def blocked_fields(self) -> tuple[str, ...]:
        return tuple(
            field.key
            for field in self.fields
            if field.status == EvidenceGateStatus.BLOCKED
        )

    @property
    def degraded_fields(self) -> tuple[str, ...]:
        return tuple(
            field.key
            for field in self.fields
            if field.status == EvidenceGateStatus.DEGRADED
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "version": self.version,
            "profile_id": self.profile_id.value,
            "activation_scope": self.activation_scope.value,
            "status": self.status.value,
            "required_fields_ready": self.required_fields_ready,
            "activation_allowed": self.activation_allowed,
            "blocked_fields": list(self.blocked_fields),
            "degraded_fields": list(self.degraded_fields),
            "fields": [field.as_dict() for field in self.fields],
        }


@dataclass(frozen=True)
class BenniOwnerRequiredFieldGate:
    """Versioned Benni production-scope rules and evaluator."""

    version: int
    profile_id: ProfileId
    activation_scope: ProfileScope
    parent_profile: ProfileId
    parent_scope: ProfileScope
    activation_allowed: bool
    specs: tuple[RequiredFieldSpec, ...]
    matrix: SourceBindingEvidenceMatrix
    registry: SchemaRegistry

    def __post_init__(self) -> None:
        if self.version != OWNER_REQUIRED_FIELD_GATE_VERSION:
            raise ValueError("unsupported owner required-field gate version")
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("owner gate production profile must be Benni")
        if self.activation_scope != ProfileScope.BENNI_PRODUCTION:
            raise ValueError("owner gate must use benni_production scope")
        if self.parent_profile != ProfileId.ELTERN:
            raise ValueError("parent profile must remain Eltern")
        if self.parent_scope != ProfileScope.PARENT_FUTURE:
            raise ValueError("parent profile must remain parent_future")
        if self.activation_allowed:
            raise ValueError("v1 owner gate cannot activate production bindings")
        keys = [spec.key for spec in self.specs]
        if len(keys) != len(set(keys)):
            raise ValueError("required-field keys must be unique")
        if any(spec.profile_id != ProfileId.BENNI for spec in self.specs):
            raise ValueError("parent fields cannot enter the Benni required gate")

    def spec(self, key: str) -> RequiredFieldSpec:
        for spec in self.specs:
            if spec.key == key:
                return spec
        raise KeyError(key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_version": self.version,
            "production_profile": self.profile_id.value,
            "production_scope": self.activation_scope.value,
            "parent_profile": self.parent_profile.value,
            "parent_scope": self.parent_scope.value,
            "activation_allowed": self.activation_allowed,
            "required_fields": [spec.as_dict() for spec in self.specs],
        }

    def evaluate(
        self,
        *,
        observations: Mapping[str, TemporalEvidence | None],
        values: Mapping[str, Any],
        now: datetime,
        derived_statuses: Mapping[str, EvidenceGateStatus] | None = None,
    ) -> OwnerRequiredGateResult:
        """Evaluate all Benni required fields without activating anything."""

        derived_statuses = derived_statuses or {}
        decisions = tuple(
            _evaluate_spec(
                spec,
                matrix=self.matrix,
                schema=self.registry.get(
                    spec.contract_ref.rsplit(".", 1)[0],
                    int(spec.contract_ref.rsplit(".", 1)[1].lstrip("v")),
                ),
                observations=observations,
                values=values,
                now=now,
                derived_statuses=derived_statuses,
            )
            for spec in self.specs
        )
        if any(field.status == EvidenceGateStatus.BLOCKED for field in decisions):
            status = EvidenceGateStatus.BLOCKED
        elif any(field.status == EvidenceGateStatus.DEGRADED for field in decisions):
            status = EvidenceGateStatus.DEGRADED
        else:
            status = EvidenceGateStatus.PASS
        return OwnerRequiredGateResult(
            gate_id=f"owner-required:{self.profile_id.value}:v{self.version}",
            version=self.version,
            profile_id=self.profile_id,
            activation_scope=self.activation_scope,
            status=status,
            required_fields_ready=all(
                field.status == EvidenceGateStatus.PASS for field in decisions
            ),
            activation_allowed=False,
            fields=decisions,
        )


def _freshness_origins(field: ContractFieldSchema) -> tuple[FreshnessOrigin, ...]:
    if field.freshness_requirement == FreshnessRequirement.DEVICE_TIMESTAMP_REQUIRED:
        return (FreshnessOrigin.DEVICE_TIMESTAMP,)
    return (FreshnessOrigin.DEVICE_TIMESTAMP, FreshnessOrigin.HA_TIMESTAMP)


def _key(contract_ref: str, field: str, room: str | None) -> str:
    return f"{contract_ref}:{field}" + (f":{room}" if room else "")


def _required_records(
    matrix: SourceBindingEvidenceMatrix,
    contract_ref: str,
    field: str,
) -> tuple[SourceBindingEvidence, ...]:
    return tuple(
        record
        for record in matrix.for_profile(ProfileId.BENNI)
        if record.contract_ref == contract_ref
        and record.field == field
        and record.required
        and record.disposition in {
            BindingDisposition.CANDIDATE,
            BindingDisposition.DERIVED,
            BindingDisposition.CONFLICT,
        }
    )


def _groups(
    contract_ref: str,
    field: ContractFieldSchema,
    records: tuple[SourceBindingEvidence, ...],
) -> tuple[tuple[str | None, tuple[SourceBindingEvidence, ...]], ...]:
    if contract_ref == "room_climate.v1":
        rooms = sorted({record.room for record in records if record.room is not None})
        if rooms:
            return tuple(
                (
                    room,
                    tuple(record for record in records if record.room == room),
                )
                for room in rooms
            )
    if contract_ref == "technical_device.v1":
        return ((None, records),)
    rooms = {record.room for record in records if record.room is not None}
    if len(rooms) == 1:
        room = next(iter(rooms))
        return ((room, records),)
    return ((None, records),)


def _derived_dependencies(contract_ref: str, field: str, room: str | None) -> tuple[str, ...]:
    if contract_ref == "room_climate.v1" and field == "available" and room:
        return (_key(contract_ref, "temperature", room),)
    if contract_ref == "opening.v1" and field == "available":
        return (_key(contract_ref, "opening_state", None),)
    if contract_ref == "weather_environment.v1" and field == "available":
        return (_key(contract_ref, "outdoor_temperature", "outdoor"),)
    if contract_ref == "technical_device.v1" and field == "available":
        return ("technical_device.v1:device_state",)
    return ()


def build_benni_owner_required_gate_v1(
    *,
    matrix: SourceBindingEvidenceMatrix | None = None,
    registry: SchemaRegistry | None = None,
) -> BenniOwnerRequiredFieldGate:
    """Build the fixed Benni required-field set from the v1 registry."""

    matrix = matrix or source_binding_matrix_v1()
    registry = registry or default_schema_registry()
    specs: list[RequiredFieldSpec] = []
    for schema in registry.all():
        contract_ref = f"{schema.schema_id}.v{schema.version}"
        for field in schema.fields:
            if not field.required:
                continue
            records = _required_records(matrix, contract_ref, field.name)
            for room, grouped in _groups(contract_ref, field, records):
                selection = (
                    RequiredEvidenceSelection.DERIVED
                    if any(record.binding_kind == BindingKind.DERIVED_GATE for record in grouped)
                    else RequiredEvidenceSelection.ALL_REQUIRED
                    if contract_ref == "opening.v1" and field.name == "opening_state"
                    else RequiredEvidenceSelection.ANY_HEALTHY
                )
                specs.append(
                    RequiredFieldSpec(
                        key=_key(contract_ref, field.name, room),
                        profile_id=ProfileId.BENNI,
                        activation_scope=ProfileScope.BENNI_PRODUCTION,
                        contract_ref=contract_ref,
                        field=field.name,
                        room=room,
                        required=True,
                        physical_state=field.physical_state,
                        safety_class=field.safety_class,
                        fallback=field.fallback,
                        freshness_requirement=field.freshness_requirement,
                        allowed_freshness_origins=_freshness_origins(field),
                        selection=selection,
                        binding_ids=tuple(record.binding_id for record in grouped),
                        source_entities=tuple(
                            record.source_entity
                            for record in grouped
                            if record.source_entity is not None
                        ),
                        consumer_ids=field.consumer_ids,
                        derived_from_keys=_derived_dependencies(
                            contract_ref,
                            field.name,
                            room,
                        ),
                    )
                )
    return BenniOwnerRequiredFieldGate(
        version=OWNER_REQUIRED_FIELD_GATE_VERSION,
        profile_id=ProfileId.BENNI,
        activation_scope=ProfileScope.BENNI_PRODUCTION,
        parent_profile=ProfileId.ELTERN,
        parent_scope=ProfileScope.PARENT_FUTURE,
        activation_allowed=False,
        specs=tuple(specs),
        matrix=matrix,
        registry=registry,
    )


def _worst_freshness(values: tuple[FreshnessStatus, ...]) -> FreshnessStatus:
    if not values:
        return FreshnessStatus.UNKNOWN
    order = {
        FreshnessStatus.RESTORED: 5,
        FreshnessStatus.STALE: 4,
        FreshnessStatus.SUSPECT: 3,
        FreshnessStatus.UNKNOWN: 2,
        FreshnessStatus.FRESH: 1,
    }
    return max(values, key=lambda value: order[value])


def _decision(
    *,
    spec: RequiredFieldSpec,
    status: EvidenceGateStatus,
    value_state: ValueState,
    health: HealthStatus,
    quality: QualityStatus,
    freshness: FreshnessStatus,
    safety: SafetyStatus,
    active_binding_ids: tuple[str, ...],
    completeness: bool,
    reasons: tuple[str, ...],
) -> RequiredFieldDecision:
    return RequiredFieldDecision(
        key=spec.key,
        contract_ref=spec.contract_ref,
        field=spec.field,
        room=spec.room,
        status=status,
        value_state=value_state,
        health=health,
        quality=quality,
        freshness=freshness,
        safety=safety,
        active_binding_ids=active_binding_ids,
        source_entities=spec.source_entities,
        completeness=completeness,
        physical_claim_allowed=(
            not spec.physical_state
            or (
                status == EvidenceGateStatus.PASS
                and value_state == ValueState.VALID
            )
        ),
        reasons=reasons,
    )


def _value_state(
    field: ContractFieldSchema,
    value: Any,
) -> ValueState:
    if value is _MISSING:
        return ValueState.UNKNOWN
    return field.classify(value)


def _evaluate_spec(
    spec: RequiredFieldSpec,
    *,
    matrix: SourceBindingEvidenceMatrix,
    schema: ContractSchema,
    observations: Mapping[str, TemporalEvidence | None],
    values: Mapping[str, Any],
    now: datetime,
    derived_statuses: Mapping[str, EvidenceGateStatus],
) -> RequiredFieldDecision:
    field_schema = schema.field(spec.field)
    value = values.get(spec.key, _MISSING)
    value_state = _value_state(field_schema, value)

    if spec.selection == RequiredEvidenceSelection.DERIVED:
        dependency_statuses = [
            derived_statuses.get(key)
            for key in spec.derived_from_keys
        ]
        reasons: list[str] = []
        if any(status is None for status in dependency_statuses):
            reasons.append("derived_evidence_not_evaluated")
            status = EvidenceGateStatus.BLOCKED
        elif any(status == EvidenceGateStatus.BLOCKED for status in dependency_statuses):
            reasons.append("required_dependency_blocked")
            status = EvidenceGateStatus.BLOCKED
        elif any(status == EvidenceGateStatus.DEGRADED for status in dependency_statuses):
            reasons.append("required_dependency_degraded")
            status = EvidenceGateStatus.DEGRADED
        else:
            status = EvidenceGateStatus.PASS
        if value is _MISSING:
            reasons.append("required_value_missing")
            status = EvidenceGateStatus.BLOCKED
        elif value is False and spec.field == "available":
            reasons.append("required_availability_false")
            status = EvidenceGateStatus.BLOCKED
        elif value_state != ValueState.VALID:
            reasons.append(f"value_state:{value_state.value}")
            status = EvidenceGateStatus.BLOCKED
        if status == EvidenceGateStatus.PASS:
            return _decision(
                spec=spec,
                status=status,
                value_state=value_state,
                health=HealthStatus.HEALTHY,
                quality=QualityStatus.GOOD,
                freshness=FreshnessStatus.FRESH,
                safety=SafetyStatus.VALID,
                active_binding_ids=spec.binding_ids,
                completeness=True,
                reasons=tuple(reasons),
            )
        if status == EvidenceGateStatus.DEGRADED:
            return _decision(
                spec=spec,
                status=status,
                value_state=value_state,
                health=HealthStatus.DEGRADED,
                quality=QualityStatus.DEGRADED,
                freshness=FreshnessStatus.UNKNOWN,
                safety=(
                    SafetyStatus.CONSERVATIVE
                    if spec.safety_class != SafetyClass.INFORMATIONAL
                    else SafetyStatus.UNKNOWN
                ),
                active_binding_ids=spec.binding_ids,
                completeness=False,
                reasons=tuple(reasons),
            )
        return _decision(
            spec=spec,
            status=status,
            value_state=value_state,
            health=HealthStatus.BLOCKED,
            quality=QualityStatus.UNAVAILABLE,
            freshness=FreshnessStatus.UNKNOWN,
            safety=(
                SafetyStatus.UNKNOWN
                if spec.physical_state
                else SafetyStatus.BLOCKED
            ),
            active_binding_ids=(),
            completeness=False,
            reasons=tuple(reasons),
        )

    records = {
        record.binding_id: record
        for record in matrix.records
        if record.binding_id in spec.binding_ids
    }
    assessments = tuple(
        assess_source_binding_evidence(
            records[binding_id],
            observations.get(binding_id),
            now=now,
            ttl_seconds=field_schema.freshness_ttl_seconds,
        )
        for binding_id in spec.binding_ids
    )
    freshness = _worst_freshness(tuple(item.freshness for item in assessments))
    reasons = tuple(dict.fromkeys(item.reason for item in assessments))
    accepted = tuple(item.binding_id for item in assessments if item.accepted)
    conflict = any(item.reason == "source_conflict" for item in assessments)
    complete = (
        all(item.accepted for item in assessments)
        if spec.selection == RequiredEvidenceSelection.ALL_REQUIRED
        else bool(accepted)
    )
    if value is _MISSING:
        value_state = ValueState.UNKNOWN
        reasons = tuple(dict.fromkeys((*reasons, "required_value_missing")))
    if value_state != ValueState.VALID:
        reasons = tuple(dict.fromkeys((*reasons, f"value_state:{value_state.value}")))

    if conflict:
        status = EvidenceGateStatus.BLOCKED
        reasons = tuple(dict.fromkeys((*reasons, "source_conflict")))
    elif not accepted or not complete:
        status = (
            EvidenceGateStatus.BLOCKED
            if spec.physical_state
            else EvidenceGateStatus.BLOCKED
        )
    elif any(item.freshness != FreshnessStatus.FRESH for item in assessments):
        status = (
            EvidenceGateStatus.BLOCKED
            if spec.physical_state
            else EvidenceGateStatus.DEGRADED
        )
    else:
        status = EvidenceGateStatus.PASS

    if status == EvidenceGateStatus.PASS and value_state != ValueState.VALID:
        status = EvidenceGateStatus.BLOCKED
    if spec.physical_state and status != EvidenceGateStatus.PASS:
        reasons = tuple(dict.fromkeys((*reasons, "physical_state_not_proven")))

    if status == EvidenceGateStatus.PASS:
        return _decision(
            spec=spec,
            status=status,
            value_state=value_state,
            health=HealthStatus.HEALTHY,
            quality=QualityStatus.GOOD,
            freshness=freshness,
            safety=SafetyStatus.VALID,
            active_binding_ids=accepted,
            completeness=complete,
            reasons=reasons,
        )
    if status == EvidenceGateStatus.DEGRADED:
        quality = {
            FreshnessStatus.SUSPECT: QualityStatus.SUSPECT,
            FreshnessStatus.STALE: QualityStatus.STALE,
        }.get(freshness, QualityStatus.DEGRADED)
        return _decision(
            spec=spec,
            status=status,
            value_state=value_state,
            health=HealthStatus.DEGRADED,
            quality=quality,
            freshness=freshness,
            safety=(
                SafetyStatus.CONSERVATIVE
                if spec.safety_class != SafetyClass.INFORMATIONAL
                else SafetyStatus.UNKNOWN
            ),
            active_binding_ids=accepted,
            completeness=complete,
            reasons=reasons,
        )
    quality = (
        QualityStatus.CONFLICT
        if conflict
        else QualityStatus.UNAVAILABLE
        if not accepted
        else QualityStatus.UNKNOWN
        if freshness in {FreshnessStatus.UNKNOWN, FreshnessStatus.RESTORED}
        else QualityStatus.STALE
    )
    return _decision(
        spec=spec,
        status=status,
        value_state=(
            ValueState.UNKNOWN if spec.physical_state else value_state
        ),
        health=HealthStatus.BLOCKED,
        quality=quality,
        freshness=freshness,
        safety=(
            SafetyStatus.UNKNOWN
            if spec.physical_state and freshness == FreshnessStatus.UNKNOWN
            else SafetyStatus.UNSAFE
            if spec.physical_state
            else SafetyStatus.BLOCKED
        ),
        active_binding_ids=accepted,
        completeness=complete,
        reasons=reasons,
    )


def parent_profile_is_out_of_scope(profile_id: ProfileId) -> bool:
    """Return whether a profile is deliberately excluded from this gate."""

    return profile_id == ProfileId.ELTERN
