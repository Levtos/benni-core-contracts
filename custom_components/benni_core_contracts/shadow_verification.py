"""Benni-only read-only Shadow Contract Verification Gate v1.

The verification result is an internal evidence projection.  It does not
activate a ConfigEntry, publish an entity, call a Home Assistant service, or
make a policy decision.  A source observation is accepted only when its
declared field value and temporal evidence are both usable for the field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from .evidence_gate import EvidenceGateStatus, evaluate_contract_evidence
from .models import ProfileId, PublishedContract, SourceBinding
from .quality import (
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
    SourceBindingEvidence,
    assess_source_binding_evidence,
)


SHADOW_CONTRACT_VERIFICATION_VERSION = 1
SHADOW_MODE = "shadow_only"

# This is a capability boundary, not a policy list.  The evidence report may
# say which technical consumers are affected; it never computes their target
# or action.  Evidence-only capabilities remain visible as unaffected when a
# different contract fails.
BENNI_SHADOW_CAPABILITIES = frozenset(
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
UNKNOWN_VALUE = "unknown"


@dataclass(frozen=True)
class ShadowSourceObservation:
    """A read-only source state supplied to the shadow evaluator."""

    source_entity: str
    state: Any
    attributes: Mapping[str, Any] = field(default_factory=dict)
    evidence: TemporalEvidence | None = None

    def __post_init__(self) -> None:
        if self.source_entity.count(".") != 1 or "*" in self.source_entity:
            raise ValueError("source_entity must be one concrete entity ID")

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_entity": self.source_entity,
            "state": self.state,
            "attributes": dict(self.attributes),
            "evidence": self.evidence.as_dict() if self.evidence else None,
        }


@dataclass(frozen=True)
class ShadowFieldVerification:
    """Complete field-scoped result required by Shadow Contract Evidence."""

    contract_id: str
    schema_id: str
    schema_version: int
    profile_id: ProfileId
    field: str
    required: bool
    status: EvidenceGateStatus
    value: Any
    active_binding_ids: tuple[str, ...]
    active_source_entity: str | None
    source_entities: tuple[str, ...]
    source_state: Any
    source_attributes: Mapping[str, Any]
    source_observations: tuple[ShadowSourceObservation, ...]
    fallback_chain: tuple[str, ...]
    quality: QualityStatus
    health: HealthStatus
    freshness: FreshnessStatus
    root_causes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    affected_capabilities: tuple[str, ...]
    unaffected_capabilities: tuple[str, ...]
    safety: SafetyStatus
    consumer_impact: str
    completeness: bool
    physical_claim_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "profile": self.profile_id.value,
            "field": self.field,
            "required": self.required,
            "status": self.status.value,
            "value": self.value,
            "active_binding_ids": list(self.active_binding_ids),
            "active_source_entity": self.active_source_entity,
            "source_entities": list(self.source_entities),
            "source_state": self.source_state,
            "source_attributes": dict(self.source_attributes),
            "source_observations": [
                observation.as_dict() for observation in self.source_observations
            ],
            "fallback_chain": list(self.fallback_chain),
            "quality": self.quality.value,
            "health": self.health.value,
            "freshness": self.freshness.value,
            "root_cause": self.root_causes[0] if self.root_causes else None,
            "root_causes": list(self.root_causes),
            "reason_codes": list(self.reason_codes),
            "affected_capabilities": list(self.affected_capabilities),
            "unaffected_capabilities": list(self.unaffected_capabilities),
            "safety": self.safety.value,
            "consumer_impact": self.consumer_impact,
            "completeness": self.completeness,
            "physical_claim_allowed": self.physical_claim_allowed,
        }


@dataclass(frozen=True)
class ShadowContractVerification:
    """Verification of one versioned internal contract in shadow_only mode."""

    version: int
    contract_id: str
    schema_id: str
    schema_version: int
    profile_id: ProfileId
    mode: str
    status: EvidenceGateStatus
    required_fields_ready: bool
    fields: tuple[ShadowFieldVerification, ...]
    generated_at: datetime
    activation_allowed: bool = False
    config_entry_activated: bool = False
    entity_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.version != SHADOW_CONTRACT_VERIFICATION_VERSION:
            raise ValueError("unsupported shadow verification version")
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("Shadow Contract Verification Gate v1 is Benni-only")
        if self.mode != SHADOW_MODE:
            raise ValueError("shadow verification must use mode=shadow_only")
        if self.activation_allowed or self.config_entry_activated:
            raise ValueError("shadow verification cannot activate a ConfigEntry")
        if self.entity_ids:
            raise ValueError("shadow verification cannot create public entities")

    @property
    def blocked_fields(self) -> tuple[str, ...]:
        return tuple(
            field.field
            for field in self.fields
            if field.status == EvidenceGateStatus.BLOCKED
        )

    @property
    def degraded_fields(self) -> tuple[str, ...]:
        return tuple(
            field.field
            for field in self.fields
            if field.status == EvidenceGateStatus.DEGRADED
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "verification_version": self.version,
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "profile": self.profile_id.value,
            "mode": self.mode,
            "status": self.status.value,
            "required_fields_ready": self.required_fields_ready,
            "blocked_fields": list(self.blocked_fields),
            "degraded_fields": list(self.degraded_fields),
            "activation_allowed": self.activation_allowed,
            "config_entry_activated": self.config_entry_activated,
            "entity_ids": list(self.entity_ids),
            "generated_at": self.generated_at.isoformat(),
            "fields": [field.as_dict() for field in self.fields],
        }


@dataclass(frozen=True)
class BenniShadowVerificationReport:
    """Versioned batch projection for the four Benni contract types."""

    version: int
    profile_id: ProfileId
    mode: str
    status: EvidenceGateStatus
    contracts: tuple[ShadowContractVerification, ...]
    generated_at: datetime
    activation_allowed: bool = False
    config_entry_activated: bool = False
    entity_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.version != SHADOW_CONTRACT_VERIFICATION_VERSION:
            raise ValueError("unsupported shadow verification version")
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("Shadow Contract Verification Gate v1 is Benni-only")
        if self.mode != SHADOW_MODE:
            raise ValueError("shadow verification must use mode=shadow_only")
        if self.activation_allowed or self.config_entry_activated or self.entity_ids:
            raise ValueError("shadow report cannot activate or publish anything")

    def as_dict(self) -> dict[str, Any]:
        return {
            "verification_version": self.version,
            "profile": self.profile_id.value,
            "mode": self.mode,
            "status": self.status.value,
            "activation_allowed": self.activation_allowed,
            "config_entry_activated": self.config_entry_activated,
            "entity_ids": list(self.entity_ids),
            "generated_at": self.generated_at.isoformat(),
            "contracts": [contract.as_dict() for contract in self.contracts],
        }


@dataclass(frozen=True)
class ShadowEvidenceOnlyVerification:
    """Evidence-only result for Lock/Cover, never a published Contract."""

    version: int
    profile_id: ProfileId
    field: str
    source_entity: str | None
    status: EvidenceGateStatus
    value: Any
    quality: QualityStatus
    health: HealthStatus
    freshness: FreshnessStatus
    safety: SafetyStatus
    reason_codes: tuple[str, ...]
    evidence_only: bool = True
    activation_allowed: bool = False
    entity_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.version != SHADOW_CONTRACT_VERIFICATION_VERSION:
            raise ValueError("unsupported shadow verification version")
        if self.profile_id != ProfileId.BENNI:
            raise ValueError("evidence-only verification is Benni-only")
        if self.field not in {"lock_state", "cover_position"}:
            raise ValueError("only lock_state and cover_position are evidence-only here")
        if not self.evidence_only or self.activation_allowed or self.entity_ids:
            raise ValueError("evidence-only verification cannot be published")

    def as_dict(self) -> dict[str, Any]:
        return {
            "verification_version": self.version,
            "profile": self.profile_id.value,
            "field": self.field,
            "source_entity": self.source_entity,
            "status": self.status.value,
            "value": self.value,
            "quality": self.quality.value,
            "health": self.health.value,
            "freshness": self.freshness.value,
            "safety": self.safety.value,
            "reason_codes": list(self.reason_codes),
            "evidence_only": self.evidence_only,
            "activation_allowed": self.activation_allowed,
            "entity_ids": list(self.entity_ids),
        }


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return tuple(result)


def _source_bindings_by_id(
    source_bindings: Iterable[SourceBinding],
) -> dict[str, SourceBinding]:
    result: dict[str, SourceBinding] = {}
    for binding in source_bindings:
        if binding.profile_id != ProfileId.BENNI:
            raise ValueError("parent bindings are outside the Benni shadow gate")
        if binding.binding_id in result:
            raise ValueError(f"duplicate source binding: {binding.binding_id}")
        result[binding.binding_id] = binding
    return result


def _field_binding_ids(
    field_schema: ContractFieldSchema,
    schema: ContractSchema,
    evaluation,
    bindings: Mapping[str, SourceBinding],
) -> tuple[str, ...]:
    evaluated = tuple(
        binding_id
        for binding_id in (
            evaluation.candidate_binding_ids
            + evaluation.active_binding_ids
        )
        if binding_id in bindings
    )
    if evaluated:
        return _unique(evaluated)
    return tuple(
        binding.binding_id
        for binding in bindings.values()
        if binding.field == field_schema.name and binding.capability == schema.schema_id
    )


def _freshness_reason(freshness: FreshnessStatus) -> str | None:
    return {
        FreshnessStatus.SUSPECT: "source_retained",
        FreshnessStatus.STALE: "source_stale",
        FreshnessStatus.RESTORED: "source_restored",
        FreshnessStatus.UNKNOWN: "source_freshness_unknown",
    }.get(freshness)


def _quality_for_source_problem(
    *,
    field: ContractFieldSchema,
    required: bool,
    freshness: FreshnessStatus,
    conflict: bool = False,
) -> tuple[EvidenceGateStatus, HealthStatus, QualityStatus, SafetyStatus]:
    status = EvidenceGateStatus.BLOCKED if required else EvidenceGateStatus.DEGRADED
    health = HealthStatus.BLOCKED if required else HealthStatus.DEGRADED
    if conflict:
        quality = QualityStatus.CONFLICT
    else:
        quality = {
            FreshnessStatus.SUSPECT: QualityStatus.SUSPECT,
            FreshnessStatus.STALE: QualityStatus.STALE,
            FreshnessStatus.RESTORED: QualityStatus.UNKNOWN,
            FreshnessStatus.UNKNOWN: QualityStatus.UNKNOWN,
        }.get(freshness, QualityStatus.UNAVAILABLE)
    if field.physical_state:
        safety = SafetyStatus.UNKNOWN
    elif required and field.safety_class != SafetyClass.INFORMATIONAL:
        safety = SafetyStatus.BLOCKED
    elif field.safety_class != SafetyClass.INFORMATIONAL:
        safety = SafetyStatus.CONSERVATIVE
    else:
        safety = SafetyStatus.UNKNOWN
    return status, health, quality, safety


def _source_state_reason(states: Iterable[ValueState]) -> str | None:
    values = tuple(states)
    if not values:
        return "source_unavailable"
    if ValueState.INVALID in values:
        return "source_state_invalid"
    if ValueState.UNKNOWN in values:
        return "source_state_unknown"
    if ValueState.UNAVAILABLE in values:
        return "source_state_unavailable"
    return None


def _fallback_chain(
    field_schema: ContractFieldSchema,
    evaluation,
) -> tuple[str, ...]:
    chain: list[str] = [evaluation.strategy]
    candidates = evaluation.candidate_binding_ids
    active = evaluation.active_binding_ids
    if active and candidates and active[0] != candidates[0]:
        chain.append(f"fallback_to:{active[0]}")
    if field_schema.fallback.action.value != "none":
        chain.append(field_schema.fallback.action.value)
    return tuple(chain)


def _capability_effect(
    field: ContractFieldSchema,
    status: EvidenceGateStatus,
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    affected = tuple(sorted(field.consumer_ids)) if status != EvidenceGateStatus.PASS else ()
    unaffected = tuple(sorted(BENNI_SHADOW_CAPABILITIES.difference(affected)))
    if status == EvidenceGateStatus.PASS:
        impact = "none"
    elif affected:
        qualifier = (
            "blocked" if status == EvidenceGateStatus.BLOCKED else "degraded"
        )
        impact = f"{qualifier}:" + ",".join(affected)
    else:
        impact = "diagnostics_only"
    return affected, unaffected, impact


def _verification_status(
    *,
    field: ContractFieldSchema,
    gate_field,
    contract: PublishedContract,
    observations: tuple[ShadowSourceObservation, ...],
    active_source_available: bool,
    accepted_source_available: bool,
    source_problem: str | None,
    source_freshness: FreshnessStatus,
) -> tuple[
    EvidenceGateStatus,
    Any,
    HealthStatus,
    QualityStatus,
    FreshnessStatus,
    SafetyStatus,
    tuple[str, ...],
]:
    reasons = list(gate_field.reasons)
    if source_problem and source_problem not in reasons:
        reasons.append(source_problem)
    if not observations:
        if "shadow_source_unavailable" not in reasons:
            reasons.append("shadow_source_unavailable")
        if "live_evidence_open" not in reasons:
            reasons.append("live_evidence_open")
        status, health, quality, safety = _quality_for_source_problem(
            field=field,
            required=field.required,
            freshness=FreshnessStatus.UNKNOWN,
        )
        return (
            status,
            UNKNOWN_VALUE,
            health,
            quality,
            FreshnessStatus.UNKNOWN,
            safety,
            tuple(reasons),
        )

    if not accepted_source_available or not active_source_available:
        conflict = "source_conflict" in reasons or gate_field.quality == QualityStatus.CONFLICT
        status, health, quality, safety = _quality_for_source_problem(
            field=field,
            required=field.required,
            freshness=source_freshness,
            conflict=conflict,
        )
        return (
            status,
            UNKNOWN_VALUE,
            health,
            quality,
            source_freshness,
            safety,
            tuple(reasons),
        )

    if field.name == "available" and contract.values.get(field.name) is False:
        if "required_availability_false" not in reasons:
            reasons.append("required_availability_false")
        status, health, quality, safety = _quality_for_source_problem(
            field=field,
            required=field.required,
            freshness=source_freshness,
        )
        return (
            status,
            False,
            health,
            quality,
            source_freshness,
            safety,
            tuple(reasons),
        )

    status = gate_field.status
    value = contract.values.get(field.name, UNKNOWN_VALUE)
    if status != EvidenceGateStatus.PASS:
        value = UNKNOWN_VALUE if field.physical_state else value
    return (
        status,
        value,
        gate_field.health,
        gate_field.quality,
        gate_field.freshness,
        gate_field.safety,
        tuple(reasons),
    )


def verify_benni_shadow_contract(
    contract: PublishedContract,
    schema: ContractSchema,
    *,
    source_bindings: Iterable[SourceBinding],
    source_observations: Mapping[str, ShadowSourceObservation],
    now: datetime,
    profile_id: ProfileId = ProfileId.BENNI,
) -> ShadowContractVerification:
    """Verify one Benni contract against explicitly supplied source evidence.

    ``source_observations`` is intentionally separate from the graph result.
    This prevents a locally restored or otherwise synthetic graph value from
    being mistaken for current read-only source evidence.
    """

    if profile_id != ProfileId.BENNI:
        raise ValueError("parent_future is outside the Benni shadow gate")
    bindings = _source_bindings_by_id(source_bindings)
    if contract.schema_id != schema.schema_id or contract.schema_version != schema.version:
        raise ValueError("contract and shadow schema do not match")
    gate = evaluate_contract_evidence(contract, schema)
    gate_fields = {result.field: result for result in gate.fields}
    fields: list[ShadowFieldVerification] = []
    for field_schema in schema.fields:
        evaluation = contract.field_evaluations[field_schema.name]
        binding_ids = _field_binding_ids(field_schema, schema, evaluation, bindings)
        source_entities = _unique(
            bindings[binding_id].entity_id
            for binding_id in binding_ids
            if binding_id in bindings
        )
        observed = tuple(
            source_observations[entity]
            for entity in source_entities
            if entity in source_observations
        )
        active_binding_ids = tuple(
            binding_id
            for binding_id in evaluation.active_binding_ids
            if binding_id in bindings
        )
        active_entities = _unique(
            bindings[binding_id].entity_id
            for binding_id in active_binding_ids
        )
        active_source = next(iter(active_entities), None)
        active_observed = tuple(
            observation
            for observation in observed
            if observation.source_entity in active_entities
        )
        accepted: list[ShadowSourceObservation] = []
        freshness_values: list[FreshnessStatus] = []
        state_values: list[ValueState] = []
        reason_candidates: list[str] = []
        for observation in observed:
            state = field_schema.classify(observation.state)
            state_values.append(state)
            if observation.evidence is None:
                freshness = FreshnessStatus.UNKNOWN
                reason = "source_evidence_unavailable"
            else:
                freshness, freshness_reason = observation.evidence.freshness(
                    now,
                    field_schema.freshness_ttl_seconds,
                    field_schema.freshness_requirement,
                )
                reason = _freshness_reason(freshness) or freshness_reason
            freshness_values.append(freshness)
            if reason and reason not in reason_candidates:
                reason_candidates.append(reason)
            if state == ValueState.VALID and freshness == FreshnessStatus.FRESH:
                accepted.append(observation)

        source_problem = (
            "source_conflict"
            if "source_conflict" in gate_fields[field_schema.name].reasons
            else next(
                (
                    reason
                    for reason in (
                        "source_restored",
                        "source_retained",
                        "source_stale",
                        "source_freshness_unknown",
                    )
                    if reason in reason_candidates
                ),
                None,
            )
            or _source_state_reason(state_values)
        )
        if source_problem is None and not observed:
            source_problem = "source_unavailable"
        if source_problem and source_problem not in reason_candidates:
            reason_candidates.append(source_problem)

        source_freshness = (
            FreshnessStatus.FRESH
            if accepted
            else max(
                freshness_values,
                key=lambda value: {
                    FreshnessStatus.RESTORED: 5,
                    FreshnessStatus.STALE: 4,
                    FreshnessStatus.SUSPECT: 3,
                    FreshnessStatus.UNKNOWN: 2,
                    FreshnessStatus.FRESH: 1,
                }[value],
                default=FreshnessStatus.UNKNOWN,
            )
        )
        accepted_entities = {observation.source_entity for observation in accepted}
        active_source_available = bool(active_observed) and (
            not active_entities
            or any(
                observation.source_entity in accepted_entities
                for observation in active_observed
            )
        )
        # A graph fallback with a selected source has an active entity.  A
        # physical reject intentionally has no active source and therefore
        # cannot claim a physical state even if stale candidates exist.
        if not active_entities:
            active_source_available = False
        status, value, health, quality, freshness, safety, reasons = _verification_status(
            field=field_schema,
            gate_field=gate_fields[field_schema.name],
            contract=contract,
            observations=observed,
            active_source_available=active_source_available,
            accepted_source_available=bool(accepted),
            source_problem=source_problem,
            source_freshness=source_freshness,
        )
        if not observed:
            # Keep the result explicitly live-evidence gated even if a
            # previously evaluated graph contract happened to be healthy.
            status = (
                EvidenceGateStatus.BLOCKED
                if field_schema.required
                else EvidenceGateStatus.DEGRADED
            )
        if status == EvidenceGateStatus.PASS and not accepted:
            status = (
                EvidenceGateStatus.BLOCKED
                if field_schema.required
                else EvidenceGateStatus.DEGRADED
            )
            value = UNKNOWN_VALUE
        source_observation = next(
            (
                observation
                for observation in observed
                if observation.source_entity == active_source
            ),
            observed[0] if observed else None,
        )
        affected, unaffected, consumer_impact = _capability_effect(
            field_schema,
            status,
        )
        root_causes = _unique(
            tuple(issue.code for issue in contract.field_quality[field_schema.name].reasons)
            + tuple(reasons)
        )
        fields.append(
            ShadowFieldVerification(
                contract_id=contract.contract_id,
                schema_id=schema.schema_id,
                schema_version=schema.version,
                profile_id=ProfileId.BENNI,
                field=field_schema.name,
                required=field_schema.required,
                status=status,
                value=value,
                active_binding_ids=active_binding_ids,
                active_source_entity=active_source,
                source_entities=source_entities,
                source_state=(
                    source_observation.state if source_observation is not None else None
                ),
                source_attributes=(
                    source_observation.attributes if source_observation is not None else {}
                ),
                source_observations=observed,
                fallback_chain=_fallback_chain(field_schema, evaluation),
                quality=quality,
                health=health,
                freshness=freshness,
                root_causes=root_causes,
                reason_codes=_unique(tuple(reasons) + tuple(reason_candidates)),
                affected_capabilities=affected,
                unaffected_capabilities=unaffected,
                safety=safety,
                consumer_impact=consumer_impact,
                completeness=gate_fields[field_schema.name].completeness,
                physical_claim_allowed=(
                    not field_schema.physical_state
                    or (
                        status == EvidenceGateStatus.PASS
                        and value != UNKNOWN_VALUE
                        and safety == SafetyStatus.VALID
                    )
                ),
            )
        )

    fields_tuple = tuple(fields)
    if any(field.status == EvidenceGateStatus.BLOCKED for field in fields_tuple if field.required):
        status = EvidenceGateStatus.BLOCKED
    elif any(field.status == EvidenceGateStatus.DEGRADED for field in fields_tuple):
        status = EvidenceGateStatus.DEGRADED
    else:
        status = EvidenceGateStatus.PASS
    return ShadowContractVerification(
        version=SHADOW_CONTRACT_VERIFICATION_VERSION,
        contract_id=contract.contract_id,
        schema_id=schema.schema_id,
        schema_version=schema.version,
        profile_id=ProfileId.BENNI,
        mode=SHADOW_MODE,
        status=status,
        required_fields_ready=all(
            field.status == EvidenceGateStatus.PASS
            for field in fields_tuple
            if field.required
        ),
        fields=fields_tuple,
        generated_at=now,
    )


def verify_benni_shadow_report(
    contracts: Iterable[PublishedContract],
    registry: SchemaRegistry,
    *,
    source_bindings: Iterable[SourceBinding],
    source_observations: Mapping[str, ShadowSourceObservation],
    now: datetime,
    profile_id: ProfileId = ProfileId.BENNI,
) -> BenniShadowVerificationReport:
    """Verify a batch of Benni contracts without activating their sources."""

    if profile_id != ProfileId.BENNI:
        raise ValueError("parent_future is outside the Benni shadow gate")
    bindings = tuple(source_bindings)
    results = tuple(
        verify_benni_shadow_contract(
            contract,
            registry.get(contract.schema_id, contract.schema_version),
            source_bindings=bindings,
            source_observations=source_observations,
            now=now,
            profile_id=profile_id,
        )
        for contract in contracts
    )
    if any(result.status == EvidenceGateStatus.BLOCKED for result in results):
        status = EvidenceGateStatus.BLOCKED
    elif any(result.status == EvidenceGateStatus.DEGRADED for result in results):
        status = EvidenceGateStatus.DEGRADED
    else:
        status = EvidenceGateStatus.PASS
    return BenniShadowVerificationReport(
        version=SHADOW_CONTRACT_VERIFICATION_VERSION,
        profile_id=ProfileId.BENNI,
        mode=SHADOW_MODE,
        status=status,
        contracts=results,
        generated_at=now,
    )


def verify_evidence_only_binding(
    record: SourceBindingEvidence,
    evidence: TemporalEvidence | None,
    *,
    now: datetime,
    source_ownership_verified: bool = False,
    value: Any = UNKNOWN_VALUE,
    ttl_seconds: int = 900,
) -> ShadowEvidenceOnlyVerification:
    """Verify Lock/Cover evidence without making it a Contract or Entity."""

    if record.profile_id != ProfileId.BENNI:
        raise ValueError("parent_future evidence cannot enter Benni shadow scope")
    if record.field not in {"lock_state", "cover_position"}:
        raise ValueError("record is not an evidence-only physical field")
    assessment = assess_source_binding_evidence(
        record,
        evidence,
        now=now,
        ttl_seconds=ttl_seconds,
    )
    reasons: list[str] = [assessment.reason]
    if record.disposition == BindingDisposition.CONFLICT:
        reasons.append("source_conflict")
    if not source_ownership_verified:
        reasons.append("source_ownership_unverified")
    if record.device_timestamp_present is not True:
        reasons.append("device_timestamp_not_evidenced")
    if record.disposition != BindingDisposition.CANDIDATE:
        reasons.append("evidence_only_not_publishable")
    accepted = (
        assessment.accepted
        and assessment.freshness == FreshnessStatus.FRESH
        and source_ownership_verified
        and record.device_timestamp_present is True
        and record.disposition == BindingDisposition.CANDIDATE
    )
    if accepted:
        status = EvidenceGateStatus.PASS
        quality = QualityStatus.GOOD
        health = HealthStatus.HEALTHY
        safety = SafetyStatus.VALID
        output_value = value
    else:
        status = EvidenceGateStatus.BLOCKED
        health = HealthStatus.BLOCKED
        quality = (
            QualityStatus.CONFLICT
            if "source_conflict" in reasons
            else QualityStatus.UNKNOWN
        )
        safety = SafetyStatus.UNKNOWN
        output_value = UNKNOWN_VALUE
    return ShadowEvidenceOnlyVerification(
        version=SHADOW_CONTRACT_VERIFICATION_VERSION,
        profile_id=ProfileId.BENNI,
        field=record.field,
        source_entity=record.source_entity,
        status=status,
        value=output_value,
        quality=quality,
        health=health,
        freshness=assessment.freshness,
        safety=safety,
        reason_codes=_unique(reasons),
    )
