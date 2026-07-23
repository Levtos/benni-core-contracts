"""Read-only Contract Evidence Gate.

The gate answers whether the evidence currently attached to a published
*internal* contract is sufficient for its declared required fields. It never
creates entities, publishes a contract to Home Assistant, calls a service, or
makes a policy decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import PublishedContract
from .quality import FreshnessStatus, HealthStatus, QualityStatus, SafetyStatus, ValueState
from .schema import ContractSchema


class EvidenceGateStatus(str, Enum):
    PASS = "pass"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EvidenceFieldResult:
    """Gate result for one schema field."""

    field: str
    required: bool
    status: EvidenceGateStatus
    value_state: ValueState
    health: HealthStatus
    quality: QualityStatus
    freshness: FreshnessStatus
    safety: SafetyStatus
    active_binding_ids: tuple[str, ...]
    completeness: bool
    required_evidence: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "required": self.required,
            "status": self.status.value,
            "value_state": self.value_state.value,
            "health": self.health.value,
            "quality": self.quality.value,
            "freshness": self.freshness.value,
            "safety": self.safety.value,
            "active_binding_ids": list(self.active_binding_ids),
            "completeness": self.completeness,
            "required_evidence": self.required_evidence,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class EvidenceGateResult:
    """Deterministic evidence assessment for one internal contract."""

    gate_id: str
    contract_id: str
    schema_id: str
    schema_version: int
    status: EvidenceGateStatus
    required_fields_ready: bool
    fields: tuple[EvidenceFieldResult, ...]

    @property
    def blocked_fields(self) -> tuple[str, ...]:
        return tuple(
            result.field
            for result in self.fields
            if result.status == EvidenceGateStatus.BLOCKED
        )

    @property
    def degraded_fields(self) -> tuple[str, ...]:
        return tuple(
            result.field
            for result in self.fields
            if result.status == EvidenceGateStatus.DEGRADED
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "status": self.status.value,
            "required_fields_ready": self.required_fields_ready,
            "blocked_fields": list(self.blocked_fields),
            "degraded_fields": list(self.degraded_fields),
            "fields": [field.as_dict() for field in self.fields],
        }


def _required_evidence(field) -> str:
    return field.freshness_requirement.value


def _field_reasons(
    *,
    required: bool,
    value_state: ValueState,
    health: HealthStatus,
    quality: QualityStatus,
    freshness: FreshnessStatus,
    safety: SafetyStatus,
    completeness: bool,
    quality_reasons: tuple[Any, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if value_state != ValueState.VALID:
        reasons.append(f"value_state:{value_state.value}")
    if freshness != FreshnessStatus.FRESH:
        reasons.append(f"freshness:{freshness.value}")
    if safety != SafetyStatus.VALID:
        reasons.append(f"safety:{safety.value}")
    if quality != QualityStatus.GOOD:
        reasons.append(f"quality:{quality.value}")
    if health != HealthStatus.HEALTHY:
        reasons.append(f"health:{health.value}")
    if not completeness:
        reasons.append("fusion_incomplete")
    reasons.extend(
        reason.code
        for reason in quality_reasons
        if reason.code not in reasons
    )
    if not required and not reasons:
        reasons.append("optional_evidence_healthy")
    return tuple(reasons)


def evaluate_contract_evidence(
    contract: PublishedContract,
    schema: ContractSchema,
) -> EvidenceGateResult:
    """Assess declared evidence without changing the contract or runtime.

    Required fields are blocked unless they are valid, fresh, safe, complete,
    healthy, and free of a quality conflict. Optional fields can be absent
    without blocking the contract, but their degradation remains visible.
    """

    if contract.schema_id != schema.schema_id or contract.schema_version != schema.version:
        raise ValueError("contract and evidence-gate schema do not match")

    field_results: list[EvidenceFieldResult] = []
    for field_schema in schema.fields:
        try:
            quality = contract.field_quality[field_schema.name]
            value_state = contract.field_states[field_schema.name]
            evaluation = contract.field_evaluations[field_schema.name]
        except KeyError as err:
            raise ValueError(f"contract is missing field evidence: {err.args[0]}") from err

        reasons = _field_reasons(
            required=field_schema.required,
            value_state=value_state,
            health=quality.health,
            quality=quality.quality,
            freshness=quality.freshness,
            safety=quality.safety,
            completeness=evaluation.completeness,
            quality_reasons=quality.reasons,
        )
        required_ready = (
            value_state == ValueState.VALID
            and quality.health == HealthStatus.HEALTHY
            and quality.quality == QualityStatus.GOOD
            and quality.freshness == FreshnessStatus.FRESH
            and quality.safety == SafetyStatus.VALID
            and evaluation.completeness
        )
        if field_schema.required:
            status = (
                EvidenceGateStatus.PASS
                if required_ready
                else EvidenceGateStatus.BLOCKED
            )
        else:
            status = (
                EvidenceGateStatus.PASS
                if required_ready
                else EvidenceGateStatus.DEGRADED
            )
        field_results.append(
            EvidenceFieldResult(
                field=field_schema.name,
                required=field_schema.required,
                status=status,
                value_state=value_state,
                health=quality.health,
                quality=quality.quality,
                freshness=quality.freshness,
                safety=quality.safety,
                active_binding_ids=evaluation.active_binding_ids,
                completeness=evaluation.completeness,
                required_evidence=_required_evidence(field_schema),
                reasons=reasons,
            )
        )

    required_fields_ready = all(
        result.status == EvidenceGateStatus.PASS
        for result in field_results
        if result.required
    )
    if not required_fields_ready:
        status = EvidenceGateStatus.BLOCKED
    elif any(result.status == EvidenceGateStatus.DEGRADED for result in field_results):
        status = EvidenceGateStatus.DEGRADED
    else:
        status = EvidenceGateStatus.PASS
    return EvidenceGateResult(
        gate_id=f"evidence:{contract.contract_id}",
        contract_id=contract.contract_id,
        schema_id=schema.schema_id,
        schema_version=schema.version,
        status=status,
        required_fields_ready=required_fields_ready,
        fields=tuple(field_results),
    )
