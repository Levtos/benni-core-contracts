"""Signal-graph models and the explicit contract publication boundary.

The models remain independent of Home Assistant entity classes. A
``PublishedContract`` becomes a public HA entity only through the exact
allowlist and the separately gated ``published`` pilot mode; shadow-only
runtime evaluation never projects it publicly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .const import (
    CONFIG_SCHEMA_VERSION,
    DEFAULT_PROFILE,
    MODE_SHADOW_ONLY,
    MODE_PUBLISHED,
    PILOT_OPENING_BINDING_IDS,
    PILOT_OPENING_CONTRACT_ID,
    PILOT_OPENING_ENTITY_ID,
)
from .quality import (
    FallbackPolicy,
    FieldQuality,
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    QualityStatus,
    QualityIssue,
    SafetyClass,
    TemporalEvidence,
    ValueState,
    utc_now,
)


class ProfileId(str, Enum):
    BENNI = "benni"
    ELTERN = "eltern"


class ProfileScope(str, Enum):
    """Activation scope for a profile in the current architecture gate."""

    BENNI_PRODUCTION = "benni_production"
    PARENT_FUTURE = "parent_future"


class RuntimeMode(str, Enum):
    SHADOW_ONLY = MODE_SHADOW_ONLY
    PUBLISHED = MODE_PUBLISHED


@dataclass(frozen=True)
class SourceBinding:
    """Maps one raw HA source to one internal field input."""

    binding_id: str
    source_id: str
    entity_id: str
    field: str
    capability: str
    profile_id: ProfileId = ProfileId.BENNI
    required: bool = True
    freshness_ttl_seconds: int = 300
    consumer_ids: tuple[str, ...] = ()
    fallback: FallbackPolicy = field(default_factory=FallbackPolicy)
    read_only: bool = True

    def __post_init__(self) -> None:
        if not self.binding_id or not self.source_id or not self.field or not self.capability:
            raise ValueError("binding_id, source_id, field, and capability are required")
        if not isinstance(self.profile_id, ProfileId):
            raise ValueError("profile_id must be a supported ProfileId")
        if "." not in self.entity_id or "*" in self.entity_id:
            raise ValueError("entity_id must be one concrete Home Assistant entity")
        if self.freshness_ttl_seconds <= 0:
            raise ValueError("freshness_ttl_seconds must be positive")
        if not self.read_only:
            raise ValueError("SourceBinding is read-only by design")

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "source_id": self.source_id,
            "entity_id": self.entity_id,
            "field": self.field,
            "capability": self.capability,
            "profile_id": self.profile_id.value,
            "required": self.required,
            "freshness_ttl_seconds": self.freshness_ttl_seconds,
            "consumer_ids": list(self.consumer_ids),
            "fallback": self.fallback.as_dict(),
            "read_only": self.read_only,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        default_profile: ProfileId = ProfileId.BENNI,
    ) -> "SourceBinding":
        return cls(
            binding_id=str(data["binding_id"]),
            source_id=str(data["source_id"]),
            entity_id=str(data["entity_id"]),
            field=str(data["field"]),
            capability=str(data["capability"]),
            profile_id=ProfileId(str(data.get("profile_id", default_profile.value))),
            required=bool(data.get("required", True)),
            freshness_ttl_seconds=int(data.get("freshness_ttl_seconds", 300)),
            consumer_ids=tuple(str(value) for value in data.get("consumer_ids", ())),
            fallback=FallbackPolicy.from_dict(data.get("fallback")),
            read_only=bool(data.get("read_only", True)),
        )


@dataclass(frozen=True)
class RawObservation:
    """A source value received without making it a public HA entity."""

    source_id: str
    entity_id: str
    value: Any
    evidence: TemporalEvidence


@dataclass(frozen=True)
class AtomicSignal:
    """One normalized field signal and its source lineage."""

    signal_id: str
    binding_id: str
    field: str
    value: Any
    evidence: TemporalEvidence
    quality: FieldQuality
    real_change_at: datetime | None = None

    def as_dict(self, now: datetime | None = None) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "binding_id": self.binding_id,
            "field": self.field,
            "value": self.value,
            "evidence": self.evidence.as_dict(),
            "quality": self.quality.as_dict(now),
            "real_change_at": self.real_change_at.isoformat()
            if self.real_change_at
            else None,
        }


@dataclass(frozen=True)
class Fusion:
    """A contract-field fusion rule over internal signals.

    The opening pilot uses three domain-normalizing strategies.  They remain
    internal data transformations; they are not policy decisions and do not
    create entities by themselves.
    """

    fusion_id: str
    contract_id: str
    field: str
    input_binding_ids: tuple[str, ...] = ()
    input_fusion_ids: tuple[str, ...] = ()
    strategy: str = "first_healthy"
    consumer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.fusion_id or not self.contract_id or not self.field:
            raise ValueError("fusion_id, contract_id, and field are required")
        if not self.input_binding_ids and not self.input_fusion_ids:
            raise ValueError("Fusion needs at least one input binding or fusion")
        if self.strategy not in {
            "first_healthy",
            "any_true",
            "latest",
            "opening_contacts",
            "opening_is_open",
            "opening_available",
            "opening_source_count",
        }:
            raise ValueError(f"unsupported fusion strategy: {self.strategy}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "fusion_id": self.fusion_id,
            "contract_id": self.contract_id,
            "field": self.field,
            "input_binding_ids": list(self.input_binding_ids),
            "input_fusion_ids": list(self.input_fusion_ids),
            "strategy": self.strategy,
            "consumer_ids": list(self.consumer_ids),
        }


@dataclass(frozen=True)
class PublishedContract:
    """A versioned internal contract result, not a HA entity."""

    contract_id: str
    schema_id: str
    schema_version: int
    values: Mapping[str, Any]
    field_states: Mapping[str, ValueState]
    field_quality: Mapping[str, FieldQuality]
    health: HealthStatus
    generated_at: datetime
    lineage: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    field_evaluations: Mapping[str, "FieldEvaluation"] = field(default_factory=dict)

    def as_dict(self, now: datetime | None = None) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "values": dict(self.values),
            "field_states": {
                name: state.value for name, state in self.field_states.items()
            },
            "field_quality": {
                name: quality.as_dict(now) for name, quality in self.field_quality.items()
            },
            "health": self.health.value,
            "generated_at": self.generated_at.isoformat(),
            "lineage": {name: list(ids) for name, ids in self.lineage.items()},
            "field_evaluations": {
                name: evaluation.as_dict() for name, evaluation in self.field_evaluations.items()
            },
        }


@dataclass(frozen=True)
class FieldEvaluation:
    """Selection result separate from quality and factual field state."""

    field: str
    state: ValueState
    active_binding_ids: tuple[str, ...]
    candidate_binding_ids: tuple[str, ...]
    completeness: bool
    strategy: str
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "state": self.state.value,
            "active_binding_ids": list(self.active_binding_ids),
            "candidate_binding_ids": list(self.candidate_binding_ids),
            "completeness": self.completeness,
            "strategy": self.strategy,
            "note": self.note,
        }


@dataclass(frozen=True)
class FieldDiagnostic:
    field: str
    state: ValueState
    health: HealthStatus
    quality: QualityStatus
    freshness: FreshnessStatus
    safety: str
    source_entities: tuple[str, ...]
    active_source_entities: tuple[str, ...]
    completeness: bool
    root_causes: tuple[QualityIssue, ...]
    consumer_effect: str

    def as_dict(self, now: datetime | None = None) -> dict[str, Any]:
        return {
            "field": self.field,
            "state": self.state.value,
            "health": self.health.value,
            "quality": self.quality.value,
            "freshness": self.freshness.value,
            "safety": self.safety,
            "source_entities": list(self.source_entities),
            "active_source_entities": list(self.active_source_entities),
            "completeness": self.completeness,
            "root_causes": [cause.as_dict(now) for cause in self.root_causes],
            "consumer_effect": self.consumer_effect,
        }


@dataclass(frozen=True)
class DiagnosticProjection:
    """Field/capability diagnostic projection for a contract."""

    projection_id: str
    contract_id: str
    schema_id: str
    health: HealthStatus
    fields: tuple[FieldDiagnostic, ...]
    generated_at: datetime

    def as_dict(self, now: datetime | None = None) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "health": self.health.value,
            "fields": [field.as_dict(now) for field in self.fields],
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass(frozen=True)
class ConfigModel:
    """ConfigEntry data model; runtime shadow state lives in StorageEnvelope."""

    schema_version: int = CONFIG_SCHEMA_VERSION
    profile: ProfileId = ProfileId(DEFAULT_PROFILE)
    mode: RuntimeMode | None = None
    entity_allowlist: tuple[str, ...] = ()
    published_contracts: tuple[str, ...] = ()
    bindings: tuple[SourceBinding, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(f"unsupported config schema version: {self.schema_version}")
        if not isinstance(self.profile, ProfileId):
            raise ValueError("profile must be a supported ProfileId")
        if self.mode is None:
            raise ValueError("an explicit runtime mode is required")
        if not isinstance(self.mode, RuntimeMode):
            raise ValueError("mode must be a supported RuntimeMode")
        if self.mode == RuntimeMode.SHADOW_ONLY and self.entity_allowlist:
            raise ValueError("shadow_only does not permit a public entity allowlist")
        if self.mode == RuntimeMode.SHADOW_ONLY and self.published_contracts:
            raise ValueError("shadow_only does not permit published contracts")
        if self.mode == RuntimeMode.PUBLISHED:
            if self.profile != ProfileId.BENNI:
                raise ValueError("published mode is restricted to the Benni profile")
            if set(self.published_contracts) != {PILOT_OPENING_CONTRACT_ID}:
                raise ValueError(
                    "published mode currently permits exactly the verified opening pilot"
                )
            if set(self.entity_allowlist) != {PILOT_OPENING_ENTITY_ID}:
                raise ValueError(
                    "published mode requires the exact opening pilot entity allowlist"
                )
            binding_ids = {binding.binding_id for binding in self.bindings}
            if binding_ids != set(PILOT_OPENING_BINDING_IDS):
                missing = set(PILOT_OPENING_BINDING_IDS) - binding_ids
                extra = binding_ids - set(PILOT_OPENING_BINDING_IDS)
                raise ValueError(
                    "published opening pilot requires exactly its two source bindings; "
                    f"missing={sorted(missing)}, extra={sorted(extra)}"
                )
        if len(set(self.entity_allowlist)) != len(self.entity_allowlist):
            raise ValueError("entity_allowlist must not contain duplicates")
        if len(set(self.published_contracts)) != len(self.published_contracts):
            raise ValueError("published_contracts must not contain duplicates")
        if any("*" in entity_id or "." not in entity_id for entity_id in self.entity_allowlist):
            raise ValueError("entity_allowlist must contain exact entity IDs")
        binding_ids = [binding.binding_id for binding in self.bindings]
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("binding IDs must be unique")
        mismatched = [
            binding.binding_id
            for binding in self.bindings
            if binding.profile_id != self.profile
        ]
        if mismatched:
            raise ValueError(
                "bindings must belong to the selected profile: "
                + ", ".join(mismatched)
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile": self.profile.value,
            "mode": self.mode.value,
            "entity_allowlist": list(self.entity_allowlist),
            "published_contracts": list(self.published_contracts),
            "bindings": [binding.as_dict() for binding in self.bindings],
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any] | None,
        options: Mapping[str, Any] | None = None,
    ) -> "ConfigModel":
        merged = dict(data or {})
        merged.update(options or {})
        profile = ProfileId(str(merged.get("profile", DEFAULT_PROFILE)))
        mode_value = merged.get("mode")
        if mode_value is None:
            raise ValueError("ConfigEntry must specify mode=shadow_only explicitly")
        return cls(
            schema_version=int(merged.get("schema_version", CONFIG_SCHEMA_VERSION)),
            profile=profile,
            mode=RuntimeMode(str(mode_value)),
            entity_allowlist=tuple(str(value) for value in merged.get("entity_allowlist", ())),
            published_contracts=tuple(
                str(value) for value in merged.get("published_contracts", ())
            ),
            bindings=tuple(
                SourceBinding.from_dict(value, default_profile=profile)
                for value in merged.get("bindings", ())
            ),
        )


def restore_evidence(now: datetime | None = None) -> TemporalEvidence:
    """Create explicit non-fresh evidence for a restored shadow value."""

    return TemporalEvidence(
        received_at=now or utc_now(),
        origin=FreshnessOrigin.RESTORE,
        restored=True,
    )
