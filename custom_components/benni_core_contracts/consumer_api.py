"""Typed internal Consumer API and subscription exchange for Core Contracts.

The exchange is a read-only boundary over :class:`RegistryRuntime`.  It
returns defensive, immutable-at-the-boundary DTOs and never exposes a
repository, PostgreSQL connection, registry payload, or mutable graph object
to a consumer.  Runtime values remain owned by the existing SignalGraph;
this module only projects them for declared consumers.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from .models import (
    FieldEvaluation,
    ProfileId,
    PublishedContract,
    SourceBinding,
)
from .quality import (
    FieldQuality,
    HealthStatus,
    QualityStatus,
    FreshnessStatus,
    ValueState,
    utc_now,
)
from .registry_service import RegistryRuntime, RegistryRuntimeSnapshot


LOGGER = logging.getLogger(__name__)


class ConsumerAccessStatus(str, Enum):
    """Status of a consumer-facing contract lookup."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    MISSING = "missing"
    FIELD_MISSING = "field_missing"
    SCHEMA_MISMATCH = "schema_mismatch"
    VERSION_INCOMPATIBLE = "version_incompatible"
    BINDING_AMBIGUOUS = "binding_ambiguous"
    RUNTIME_NOT_READY = "runtime_not_ready"
    CONSUMER_NOT_REGISTERED = "consumer_not_registered"


class ConsumerEventKind(str, Enum):
    """Semantic updates a consumer may receive from a subscription."""

    VALUE_CHANGED = "value_changed"
    QUALITY_CHANGED = "quality_changed"
    FRESHNESS_CHANGED = "freshness_changed"
    HEALTH_CHANGED = "health_changed"
    REVISION_CHANGED = "revision_changed"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


# Descriptive aliases make integrations tolerant of the two common spellings
# without creating a second event vocabulary.
ContractAccessStatus = ConsumerAccessStatus
SubscriptionEventKind = ConsumerEventKind


class ConsumerApiError(RuntimeError):
    """Base error for an invalid request at the internal consumer boundary."""

    status = ConsumerAccessStatus.UNKNOWN

    def __init__(
        self,
        message: str,
        *,
        status: ConsumerAccessStatus | None = None,
        profile: ProfileId | None = None,
        contract_id: str | None = None,
        field: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.status = status or self.status
        self.profile = profile
        self.contract_id = contract_id
        self.field = field
        self.details = dict(details or {})
        super().__init__(message)


class ConsumerRuntimeNotReadyError(ConsumerApiError):
    status = ConsumerAccessStatus.RUNTIME_NOT_READY


class ConsumerContractMissingError(ConsumerApiError):
    status = ConsumerAccessStatus.MISSING


class ConsumerFieldMissingError(ConsumerApiError):
    status = ConsumerAccessStatus.FIELD_MISSING


class ConsumerSchemaMismatchError(ConsumerApiError):
    status = ConsumerAccessStatus.SCHEMA_MISMATCH


class ConsumerVersionIncompatibleError(ConsumerApiError):
    status = ConsumerAccessStatus.VERSION_INCOMPATIBLE


class ConsumerBindingMissingError(ConsumerApiError):
    status = ConsumerAccessStatus.MISSING


class ConsumerBindingAmbiguousError(ConsumerApiError):
    status = ConsumerAccessStatus.BINDING_AMBIGUOUS


class ConsumerNotRegisteredError(ConsumerApiError):
    status = ConsumerAccessStatus.CONSUMER_NOT_REGISTERED


class ConsumerAlreadyRegisteredError(ConsumerApiError):
    status = ConsumerAccessStatus.CONSUMER_NOT_REGISTERED


class ConsumerApiClosedError(ConsumerApiError):
    status = ConsumerAccessStatus.RUNTIME_NOT_READY


@dataclass(frozen=True)
class ConsumerRequirement:
    """One contract or logical binding role required by a consumer.

    ``expected_schema_version`` requests an exact version.  When omitted,
    ``min_supported_schema_version`` accepts that version or a newer additive
    version, provided all declared ``required_fields`` remain available.
    """

    contract_id: str | None = None
    role: str | None = None
    schema_id: str | None = None
    expected_schema_version: int | None = None
    min_supported_schema_version: int | None = None
    required_fields: tuple[str, ...] = ()
    profile: ProfileId = ProfileId.BENNI
    consumer_id: str | None = None

    def __post_init__(self) -> None:
        if bool(self.contract_id) == bool(self.role):
            raise ValueError("a requirement needs exactly one contract_id or role")
        for name, value in (
            ("contract_id", self.contract_id),
            ("role", self.role),
            ("schema_id", self.schema_id),
            ("consumer_id", self.consumer_id),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.profile, ProfileId):
            raise ValueError("requirement profile must be a supported ProfileId")
        if (
            self.expected_schema_version is not None
            and self.min_supported_schema_version is not None
        ):
            raise ValueError(
                "expected_schema_version and min_supported_schema_version are mutually exclusive"
            )
        for name, value in (
            ("expected_schema_version", self.expected_schema_version),
            ("min_supported_schema_version", self.min_supported_schema_version),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
        fields = tuple(str(value) for value in self.required_fields)
        if any(not value.strip() for value in fields):
            raise ValueError("required_fields must contain non-empty names")
        if len(set(fields)) != len(fields):
            raise ValueError("required_fields must not contain duplicates")
        object.__setattr__(self, "required_fields", fields)

    @property
    def expected_version(self) -> int | None:
        """Short alias for callers that use the contract vocabulary."""

        return self.expected_schema_version

    @property
    def min_supported_version(self) -> int | None:
        """Short alias for callers that use the contract vocabulary."""

        return self.min_supported_schema_version

    @classmethod
    def contract(
        cls,
        contract_id: str,
        *,
        schema_id: str | None = None,
        expected_schema_version: int | None = None,
        min_supported_schema_version: int | None = None,
        required_fields: Iterable[str] = (),
        profile: ProfileId = ProfileId.BENNI,
    ) -> "ConsumerRequirement":
        return cls(
            contract_id=contract_id,
            schema_id=schema_id,
            expected_schema_version=expected_schema_version,
            min_supported_schema_version=min_supported_schema_version,
            required_fields=tuple(required_fields),
            profile=profile,
        )

    @classmethod
    def binding_role(
        cls,
        role: str,
        *,
        profile: ProfileId = ProfileId.BENNI,
    ) -> "ConsumerRequirement":
        return cls(role=role, profile=profile)

    def as_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "contract_id": self.contract_id,
            "role": self.role,
            "schema_id": self.schema_id,
            "expected_schema_version": self.expected_schema_version,
            "min_supported_schema_version": self.min_supported_schema_version,
            "required_fields": list(self.required_fields),
            "profile": self.profile.value,
        }


@dataclass(frozen=True)
class ConsumerDeclaration:
    """Stable consumer identity plus self-declared requirements."""

    consumer_id: str
    requirements: tuple[ConsumerRequirement, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.consumer_id, str) or not self.consumer_id.strip():
            raise ValueError("consumer_id must be a non-empty stable technical ID")
        if not isinstance(self.enabled, bool):
            raise ValueError("consumer declaration enabled must be a boolean")
        requirements = tuple(self.requirements)
        seen: set[tuple[ProfileId, str, str]] = set()
        for requirement in requirements:
            if not isinstance(requirement, ConsumerRequirement):
                raise ValueError("requirements must contain ConsumerRequirement objects")
            if requirement.consumer_id not in {None, self.consumer_id}:
                raise ValueError("requirement consumer_id does not match declaration")
            key = (
                requirement.profile,
                requirement.contract_id or "",
                requirement.role or "",
            )
            if key in seen:
                raise ValueError("duplicate consumer requirement")
            seen.add(key)
        object.__setattr__(self, "requirements", requirements)

    def as_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "enabled": self.enabled,
            "requirements": [requirement.as_dict() for requirement in self.requirements],
        }


@dataclass(frozen=True)
class ConsumerOverride:
    """Optional in-memory block for an advanced consumer override.

    Overrides are deliberately a runtime API boundary in this slice.  They
    are not written to PostgreSQL or exposed through Home Assistant UI; the
    persisted ``consumer_overrides`` payload remains owned by Issue #16/#17.
    """

    consumer_id: str
    contract_id: str | None = None
    role: str | None = None
    profile: ProfileId = ProfileId.BENNI
    blocked: bool = True
    reason: str = "blocked by consumer override"

    def __post_init__(self) -> None:
        if not isinstance(self.consumer_id, str) or not self.consumer_id.strip():
            raise ValueError("override consumer_id is required")
        if bool(self.contract_id) == bool(self.role):
            raise ValueError("an override needs exactly one contract_id or role")
        if not isinstance(self.profile, ProfileId):
            raise ValueError("override profile must be a supported ProfileId")
        if not isinstance(self.blocked, bool):
            raise ValueError("override blocked must be a boolean")
        if not self.reason.strip():
            raise ValueError("override reason must not be empty")


@dataclass(frozen=True)
class ConsumerRevisionSnapshot:
    """Safe revision metadata without the persisted registry payload."""

    profile: ProfileId
    revision: int
    revision_id: str
    registry_schema_version: int
    source: str
    registry_health: HealthStatus
    graph_revision: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "revision": self.revision,
            "revision_id": self.revision_id,
            "registry_schema_version": self.registry_schema_version,
            "source": self.source,
            "registry_health": self.registry_health.value,
            "graph_revision": self.graph_revision,
        }


@dataclass(frozen=True)
class ConsumerLineage:
    """Read-only source lineage for one consumer-facing field."""

    active_binding_ids: tuple[str, ...] = ()
    candidate_binding_ids: tuple[str, ...] = ()
    active_source_ids: tuple[str, ...] = ()
    candidate_source_ids: tuple[str, ...] = ()
    active_entity_ids: tuple[str, ...] = ()
    candidate_entity_ids: tuple[str, ...] = ()

    @property
    def binding_ids(self) -> tuple[str, ...]:
        return self.active_binding_ids

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.active_source_ids

    @property
    def entity_ids(self) -> tuple[str, ...]:
        return self.active_entity_ids

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_binding_ids": list(self.active_binding_ids),
            "candidate_binding_ids": list(self.candidate_binding_ids),
            "active_source_ids": list(self.active_source_ids),
            "candidate_source_ids": list(self.candidate_source_ids),
            "active_entity_ids": list(self.active_entity_ids),
            "candidate_entity_ids": list(self.candidate_entity_ids),
        }


@dataclass(frozen=True)
class ConsumerFieldEvaluation:
    """Defensive field-selection metadata derived from ``FieldEvaluation``."""

    state: ValueState
    active_binding_ids: tuple[str, ...]
    candidate_binding_ids: tuple[str, ...]
    completeness: bool
    strategy: str
    note: str | None = None

    @classmethod
    def from_model(cls, evaluation: FieldEvaluation) -> "ConsumerFieldEvaluation":
        return cls(
            state=evaluation.state,
            active_binding_ids=tuple(evaluation.active_binding_ids),
            candidate_binding_ids=tuple(evaluation.candidate_binding_ids),
            completeness=evaluation.completeness,
            strategy=evaluation.strategy,
            note=evaluation.note,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "active_binding_ids": list(self.active_binding_ids),
            "candidate_binding_ids": list(self.candidate_binding_ids),
            "completeness": self.completeness,
            "strategy": self.strategy,
            "note": self.note,
        }


def _copy_value(value: Any) -> Any:
    """Isolate mutable JSON-like field values from the runtime graph."""

    try:
        return copy.deepcopy(value)
    except (TypeError, ValueError):
        # Contract schemas currently contain JSON-compatible values; retaining
        # an exotic value is safer than handing a runtime-owned object out.
        return value


@dataclass(frozen=True)
class ConsumerFieldSnapshot:
    """One typed, quality-aware field value returned to a consumer."""

    contract_id: str
    schema_id: str
    schema_version: int
    field: str
    value: Any
    state: ValueState
    quality: FieldQuality
    lineage: ConsumerLineage
    evaluation: ConsumerFieldEvaluation
    registry_revision: int
    registry_revision_id: str
    graph_revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _copy_value(self.value))

    @property
    def freshness(self) -> FreshnessStatus:
        return self.quality.freshness

    @property
    def health(self) -> HealthStatus:
        return self.quality.health

    @property
    def quality_status(self) -> QualityStatus:
        return self.quality.quality

    def as_dict(self, now=None) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "field": self.field,
            "value": _copy_value(self.value),
            "state": self.state.value,
            "health": self.health.value,
            "quality": self.quality.quality.value,
            "freshness": self.freshness.value,
            "field_quality": self.quality.as_dict(now),
            "lineage": self.lineage.as_dict(),
            "evaluation": self.evaluation.as_dict(),
            "registry_revision": self.registry_revision,
            "registry_revision_id": self.registry_revision_id,
            "graph_revision": self.graph_revision,
        }


@dataclass(frozen=True)
class ConsumerContractSnapshot:
    """A complete defensive snapshot of one evaluated internal contract."""

    contract_id: str
    schema_id: str
    schema_version: int
    status: ConsumerAccessStatus
    health: HealthStatus
    fields: tuple[ConsumerFieldSnapshot, ...]
    revision: ConsumerRevisionSnapshot
    generated_at: Any

    def __post_init__(self) -> None:
        fields = tuple(self.fields)
        if len({item.field for item in fields}) != len(fields):
            raise ValueError("consumer snapshot fields must be unique")
        object.__setattr__(self, "fields", fields)

    @property
    def available(self) -> bool:
        """Whether a contract result exists, including a blocked result."""

        return self.status in {
            ConsumerAccessStatus.HEALTHY,
            ConsumerAccessStatus.DEGRADED,
            ConsumerAccessStatus.BLOCKED,
            ConsumerAccessStatus.UNKNOWN,
        }

    @property
    def consumable(self) -> bool:
        """Whether the result is present and not blocked at contract level."""

        return self.status in {
            ConsumerAccessStatus.HEALTHY,
            ConsumerAccessStatus.DEGRADED,
        }

    @property
    def registry_revision(self) -> int:
        return self.revision.revision

    @property
    def registry_source(self) -> str:
        return self.revision.source

    def field(self, name: str) -> ConsumerFieldSnapshot:
        for item in self.fields:
            if item.field == name:
                return item
        raise ConsumerFieldMissingError(
            f"field is not present in contract: {name}",
            profile=self.revision.profile,
            contract_id=self.contract_id,
            field=name,
            details={"available_fields": [item.field for item in self.fields]},
        )

    def as_dict(self, now=None) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "status": self.status.value,
            "health": self.health.value,
            "fields": [item.as_dict(now) for item in self.fields],
            "revision": self.revision.as_dict(),
            "generated_at": self.generated_at.isoformat()
            if hasattr(self.generated_at, "isoformat")
            else self.generated_at,
        }


@dataclass(frozen=True)
class ConsumerBinding:
    """Safe binding resolution; no ``SourceBinding`` object crosses the API."""

    binding_id: str
    matched_role: str
    source_id: str
    entity_id: str
    field: str
    capability: str
    profile: ProfileId
    required: bool
    enabled: bool
    read_only: bool
    consumer_ids: tuple[str, ...]

    @classmethod
    def from_model(
        cls,
        binding: SourceBinding,
        *,
        matched_role: str,
    ) -> "ConsumerBinding":
        return cls(
            binding_id=binding.binding_id,
            matched_role=matched_role,
            source_id=binding.source_id,
            entity_id=binding.entity_id,
            field=binding.field,
            capability=binding.capability,
            profile=binding.profile_id,
            required=binding.required,
            enabled=binding.enabled,
            read_only=binding.read_only,
            consumer_ids=tuple(binding.consumer_ids),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "matched_role": self.matched_role,
            "source_id": self.source_id,
            "entity_id": self.entity_id,
            "field": self.field,
            "capability": self.capability,
            "profile": self.profile.value,
            "required": self.required,
            "enabled": self.enabled,
            "read_only": self.read_only,
            "consumer_ids": list(self.consumer_ids),
        }


@dataclass(frozen=True)
class ContractLookup:
    """Typed lookup result; status distinguishes every non-success case."""

    status: ConsumerAccessStatus
    profile: ProfileId
    contract_id: str
    snapshot: ConsumerContractSnapshot | None = None
    reason: str | None = None
    missing_fields: tuple[str, ...] = ()

    @property
    def present(self) -> bool:
        return self.snapshot is not None

    @property
    def available(self) -> bool:
        return self.status in {
            ConsumerAccessStatus.HEALTHY,
            ConsumerAccessStatus.DEGRADED,
            ConsumerAccessStatus.BLOCKED,
            ConsumerAccessStatus.UNKNOWN,
        }

    def require_snapshot(self) -> ConsumerContractSnapshot:
        if self.snapshot is not None and self.status in {
            ConsumerAccessStatus.HEALTHY,
            ConsumerAccessStatus.DEGRADED,
            ConsumerAccessStatus.BLOCKED,
            ConsumerAccessStatus.UNKNOWN,
        }:
            return self.snapshot
        raise _lookup_error(self)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "profile": self.profile.value,
            "contract_id": self.contract_id,
            "snapshot": self.snapshot.as_dict() if self.snapshot else None,
            "reason": self.reason,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class RequirementState:
    """Evaluation of one declared consumer requirement."""

    consumer_id: str
    requirement: ConsumerRequirement
    status: ConsumerAccessStatus
    reason: str | None = None
    snapshot: ConsumerContractSnapshot | None = None
    binding: ConsumerBinding | None = None

    @property
    def satisfied(self) -> bool:
        return self.status == ConsumerAccessStatus.HEALTHY

    @property
    def available(self) -> bool:
        return self.status in {
            ConsumerAccessStatus.HEALTHY,
            ConsumerAccessStatus.DEGRADED,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "requirement": self.requirement.as_dict(),
            "status": self.status.value,
            "satisfied": self.satisfied,
            "available": self.available,
            "reason": self.reason,
            "snapshot": self.snapshot.as_dict() if self.snapshot else None,
            "binding": self.binding.as_dict() if self.binding else None,
        }


@dataclass(frozen=True)
class ConsumerImpact:
    """Diagnostic view of all requirements belonging to one consumer."""

    consumer_id: str
    requirements: tuple[RequirementState, ...]
    registry_revisions: tuple[ConsumerRevisionSnapshot, ...] = ()

    @property
    def status(self) -> ConsumerAccessStatus:
        return _aggregate_status(item.status for item in self.requirements)

    @property
    def satisfied(self) -> bool:
        return bool(self.requirements) and self.status == ConsumerAccessStatus.HEALTHY

    @property
    def affected_contract_ids(self) -> tuple[str, ...]:
        return tuple(
            item.requirement.contract_id
            for item in self.requirements
            if item.requirement.contract_id is not None
            and item.status != ConsumerAccessStatus.HEALTHY
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "status": self.status.value,
            "satisfied": self.satisfied,
            "requirements": [item.as_dict() for item in self.requirements],
            "registry_revisions": [item.as_dict() for item in self.registry_revisions],
            "affected_contract_ids": list(self.affected_contract_ids),
        }


@dataclass(frozen=True)
class ConsumerUpdate:
    """One filtered subscription update with before/after snapshots."""

    consumer_id: str
    profile: ProfileId
    contract_id: str
    event_kinds: frozenset[ConsumerEventKind]
    snapshot: ConsumerContractSnapshot | None
    previous_snapshot: ConsumerContractSnapshot | None
    changed_fields: tuple[str, ...]
    revision: ConsumerRevisionSnapshot | None
    graph_revision: int | None
    reason: str | None = None

    @property
    def events(self) -> frozenset[ConsumerEventKind]:
        return self.event_kinds

    @property
    def kind(self) -> ConsumerEventKind | None:
        return next(iter(self.event_kinds)) if len(self.event_kinds) == 1 else None

    @property
    def available(self) -> bool:
        return self.snapshot is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "profile": self.profile.value,
            "contract_id": self.contract_id,
            "event_kinds": sorted(item.value for item in self.event_kinds),
            "snapshot": self.snapshot.as_dict() if self.snapshot else None,
            "previous_snapshot": self.previous_snapshot.as_dict()
            if self.previous_snapshot
            else None,
            "changed_fields": list(self.changed_fields),
            "revision": self.revision.as_dict() if self.revision else None,
            "graph_revision": self.graph_revision,
            "reason": self.reason,
        }


@dataclass
class _ObservedContract:
    status: ConsumerAccessStatus
    snapshot: ConsumerContractSnapshot | None
    fingerprint: str
    revision: ConsumerRevisionSnapshot | None
    graph_revision: int | None
    reason: str | None = None


@dataclass
class _SubscriptionState:
    token: str
    consumer_id: str
    profile: ProfileId
    callback: Callable[[ConsumerUpdate], Any]
    contract_id: str | None
    role: str | None
    fields: frozenset[str]
    event_kinds: frozenset[ConsumerEventKind]
    active: bool = True


class ConsumerSubscription:
    """Handle returned by ``subscribe``; closing it is idempotent."""

    def __init__(self, api: "ConsumerApi", token: str) -> None:
        self._api = api
        self.token = token

    @property
    def active(self) -> bool:
        return self._api._subscription_active(self.token)

    def unsubscribe(self) -> bool:
        return self._api.unsubscribe(self)

    close = unsubscribe

    def __enter__(self) -> "ConsumerSubscription":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.unsubscribe()


def _aggregate_status(statuses: Iterable[ConsumerAccessStatus]) -> ConsumerAccessStatus:
    order = (
        ConsumerAccessStatus.RUNTIME_NOT_READY,
        ConsumerAccessStatus.MISSING,
        ConsumerAccessStatus.BINDING_AMBIGUOUS,
        ConsumerAccessStatus.SCHEMA_MISMATCH,
        ConsumerAccessStatus.VERSION_INCOMPATIBLE,
        ConsumerAccessStatus.FIELD_MISSING,
        ConsumerAccessStatus.BLOCKED,
        ConsumerAccessStatus.DEGRADED,
        ConsumerAccessStatus.UNKNOWN,
        ConsumerAccessStatus.HEALTHY,
    )
    values = tuple(statuses)
    if not values:
        return ConsumerAccessStatus.HEALTHY
    for candidate in order:
        if candidate in values:
            return candidate
    return ConsumerAccessStatus.UNKNOWN


def _status_from_health(health: HealthStatus) -> ConsumerAccessStatus:
    return {
        HealthStatus.HEALTHY: ConsumerAccessStatus.HEALTHY,
        HealthStatus.DEGRADED: ConsumerAccessStatus.DEGRADED,
        HealthStatus.BLOCKED: ConsumerAccessStatus.BLOCKED,
        HealthStatus.UNKNOWN: ConsumerAccessStatus.UNKNOWN,
    }[health]


def _lookup_error(lookup: ContractLookup) -> ConsumerApiError:
    common = {
        "profile": lookup.profile,
        "contract_id": lookup.contract_id,
        "details": {"status": lookup.status.value},
    }
    message = lookup.reason or f"contract lookup failed: {lookup.status.value}"
    if lookup.status == ConsumerAccessStatus.RUNTIME_NOT_READY:
        return ConsumerRuntimeNotReadyError(message, **common)
    if lookup.status == ConsumerAccessStatus.MISSING:
        return ConsumerContractMissingError(message, **common)
    if lookup.status == ConsumerAccessStatus.FIELD_MISSING:
        return ConsumerFieldMissingError(
            message,
            field=lookup.missing_fields[0] if lookup.missing_fields else None,
            **common,
        )
    if lookup.status == ConsumerAccessStatus.SCHEMA_MISMATCH:
        return ConsumerSchemaMismatchError(message, **common)
    if lookup.status == ConsumerAccessStatus.VERSION_INCOMPATIBLE:
        return ConsumerVersionIncompatibleError(message, **common)
    return ConsumerApiError(message, status=lookup.status, **common)


class ConsumerApi:
    """Stable typed exchange over one existing ``RegistryRuntime``.

    A single instance is intended to be shared by internal integrations for a
    runtime.  It attaches only read-only graph/runtime listeners and owns no
    registry persistence.  ``close()`` removes every listener and subscription.
    """

    def __init__(
        self,
        runtime: RegistryRuntime,
        *,
        now_factory: Callable[[], Any] = utc_now,
    ) -> None:
        if not isinstance(runtime, RegistryRuntime):
            raise TypeError("ConsumerApi requires the existing RegistryRuntime")
        self._runtime = runtime
        self._now_factory = now_factory
        self._consumers: dict[str, ConsumerDeclaration] = {}
        self._overrides: dict[tuple[str, ProfileId, str, str], ConsumerOverride] = {}
        self._subscriptions: dict[str, _SubscriptionState] = {}
        self._observed: dict[tuple[ProfileId, str], _ObservedContract] = {}
        self._graph_callbacks: dict[ProfileId, Callable[[Any], None]] = {}
        self._attached_graphs: dict[ProfileId, Any] = {}
        self._suppress_graph_events = 0
        self._closed = False
        self._runtime_listener = self._on_runtime_activation
        runtime.add_listener(self._runtime_listener)
        for snapshot in runtime.snapshots():
            self._attach_graph(snapshot)

    def _ensure_open(self) -> None:
        if self._closed:
            raise ConsumerApiClosedError("consumer API is closed")

    def register_consumer(
        self,
        declaration_or_id: ConsumerDeclaration | str,
        requirements: Iterable[ConsumerRequirement] = (),
        *,
        enabled: bool = True,
        replace_existing: bool = False,
    ) -> ConsumerDeclaration:
        """Register a stable consumer ID and its self-declared requirements."""

        self._ensure_open()
        if isinstance(declaration_or_id, ConsumerDeclaration):
            declaration = declaration_or_id
            if requirements:
                raise ValueError("requirements cannot be supplied with a declaration")
        else:
            consumer_id = str(declaration_or_id)
            normalized = tuple(
                requirement
                if requirement.consumer_id in {None, consumer_id}
                else requirement
                for requirement in requirements
            )
            normalized = tuple(
                replace(requirement, consumer_id=consumer_id)
                if requirement.consumer_id is None
                else requirement
                for requirement in normalized
            )
            declaration = ConsumerDeclaration(
                consumer_id=consumer_id,
                requirements=normalized,
                enabled=enabled,
            )
        if declaration.consumer_id in self._consumers and not replace_existing:
            raise ConsumerAlreadyRegisteredError(
                "consumer ID is already registered",
                details={"consumer_id": declaration.consumer_id},
            )
        self._consumers[declaration.consumer_id] = declaration
        return declaration

    declare_consumer = register_consumer

    def unregister_consumer(self, consumer_id: str) -> bool:
        self._ensure_open()
        if consumer_id not in self._consumers:
            return False
        for token, subscription in tuple(self._subscriptions.items()):
            if subscription.consumer_id == consumer_id:
                self._remove_subscription(token)
        self._overrides = {
            key: value
            for key, value in self._overrides.items()
            if value.consumer_id != consumer_id
        }
        del self._consumers[consumer_id]
        return True

    def consumer_declaration(self, consumer_id: str) -> ConsumerDeclaration:
        self._ensure_open()
        try:
            return self._consumers[consumer_id]
        except KeyError as err:
            raise ConsumerNotRegisteredError(
                "consumer is not registered",
                details={"consumer_id": consumer_id},
            ) from err

    def consumers(self) -> tuple[ConsumerDeclaration, ...]:
        self._ensure_open()
        return tuple(self._consumers.values())

    def requirements_for(self, consumer_id: str) -> tuple[ConsumerRequirement, ...]:
        return self.consumer_declaration(consumer_id).requirements

    def set_override(self, override: ConsumerOverride) -> ConsumerOverride:
        self._ensure_open()
        self.consumer_declaration(override.consumer_id)
        key = (
            override.consumer_id,
            override.profile,
            override.contract_id or "",
            override.role or "",
        )
        self._overrides[key] = override
        return override

    def clear_override(
        self,
        consumer_id: str,
        *,
        profile: ProfileId = ProfileId.BENNI,
        contract_id: str | None = None,
        role: str | None = None,
    ) -> bool:
        self._ensure_open()
        key = (consumer_id, profile, contract_id or "", role or "")
        return self._overrides.pop(key, None) is not None

    def overrides(self) -> tuple[ConsumerOverride, ...]:
        self._ensure_open()
        return tuple(self._overrides.values())

    def get_revision(self, profile: ProfileId | str = ProfileId.BENNI) -> ConsumerRevisionSnapshot:
        self._ensure_open()
        profile_id = _profile_id(profile)
        snapshot = self._runtime.active(profile_id)
        if snapshot is None:
            raise ConsumerRuntimeNotReadyError(
                "registry runtime is not ready for this profile",
                profile=profile_id,
            )
        return self._revision_snapshot(snapshot)

    revision = get_revision
    get_registry_revision = get_revision

    def resolve_binding(
        self,
        role: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
        consumer_id: str | None = None,
    ) -> ConsumerBinding:
        """Resolve a stable role/capability/field to one active binding."""

        self._ensure_open()
        profile_id = _profile_id(profile)
        snapshot = self._runtime.active(profile_id)
        if snapshot is None:
            raise ConsumerRuntimeNotReadyError(
                "registry runtime is not ready for binding resolution",
                profile=profile_id,
            )
        if not isinstance(role, str) or not role.strip():
            raise ValueError("binding role must be a non-empty string")
        candidates: list[SourceBinding] = []
        for binding in snapshot.graph.bindings():
            if binding.profile_id != profile_id:
                continue
            if not self._binding_matches_role(binding, role, consumer_id):
                continue
            candidates.append(binding)
        if not candidates:
            raise ConsumerBindingMissingError(
                "no binding matches the requested logical role",
                profile=profile_id,
                details={"role": role, "consumer_id": consumer_id},
            )
        if len(candidates) > 1:
            raise ConsumerBindingAmbiguousError(
                "logical role resolves to multiple bindings",
                profile=profile_id,
                details={"role": role, "binding_ids": [item.binding_id for item in candidates]},
            )
        return ConsumerBinding.from_model(candidates[0], matched_role=role)

    resolve_role = resolve_binding
    get_binding = resolve_binding

    def lookup_contract(
        self,
        contract_id: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
        schema_id: str | None = None,
        expected_schema_version: int | None = None,
        min_supported_schema_version: int | None = None,
        required_fields: Iterable[str] = (),
        expected_version: int | None = None,
        min_version: int | None = None,
    ) -> ContractLookup:
        """Return a typed result without collapsing missing/error cases to None."""

        self._ensure_open()
        profile_id = _profile_id(profile)
        expected_schema_version = _coalesce_version(
            expected_schema_version,
            expected_version,
            "expected_schema_version",
        )
        min_supported_schema_version = _coalesce_version(
            min_supported_schema_version,
            min_version,
            "min_supported_schema_version",
        )
        if expected_schema_version is not None and min_supported_schema_version is not None:
            raise ValueError(
                "expected_schema_version and min_supported_schema_version are mutually exclusive"
            )
        required = tuple(str(value) for value in required_fields)
        with self._suppress_graph_capture():
            observed = self._capture_contract(profile_id, str(contract_id), refresh_evaluation=True)
        if observed.snapshot is None:
            return ContractLookup(
                observed.status,
                profile_id,
                str(contract_id),
                reason=observed.reason,
            )
        snapshot = observed.snapshot
        if schema_id is not None and snapshot.schema_id != schema_id:
            return ContractLookup(
                ConsumerAccessStatus.SCHEMA_MISMATCH,
                profile_id,
                str(contract_id),
                snapshot=snapshot,
                reason=(
                    f"consumer expects schema {schema_id}, runtime provides {snapshot.schema_id}"
                ),
            )
        if expected_schema_version is not None and snapshot.schema_version != expected_schema_version:
            return ContractLookup(
                ConsumerAccessStatus.VERSION_INCOMPATIBLE,
                profile_id,
                str(contract_id),
                snapshot=snapshot,
                reason=(
                    f"consumer expects schema version {expected_schema_version}, "
                    f"runtime provides {snapshot.schema_version}"
                ),
            )
        if (
            min_supported_schema_version is not None
            and snapshot.schema_version < min_supported_schema_version
        ):
            return ContractLookup(
                ConsumerAccessStatus.VERSION_INCOMPATIBLE,
                profile_id,
                str(contract_id),
                snapshot=snapshot,
                reason=(
                    f"consumer supports schema versions from {min_supported_schema_version}, "
                    f"runtime provides {snapshot.schema_version}"
                ),
            )
        missing = tuple(field for field in required if not any(item.field == field for item in snapshot.fields))
        if missing:
            return ContractLookup(
                ConsumerAccessStatus.FIELD_MISSING,
                profile_id,
                str(contract_id),
                snapshot=snapshot,
                missing_fields=missing,
                reason="consumer-required contract fields are missing",
            )
        return ContractLookup(
            observed.status,
            profile_id,
            str(contract_id),
            snapshot=snapshot,
            reason=observed.reason,
        )

    def lookup_requirement(self, requirement: ConsumerRequirement) -> ContractLookup:
        if requirement.contract_id is None:
            raise ValueError("binding-role requirements do not have contract snapshots")
        return self.lookup_contract(
            requirement.contract_id,
            profile=requirement.profile,
            schema_id=requirement.schema_id,
            expected_schema_version=requirement.expected_schema_version,
            min_supported_schema_version=requirement.min_supported_schema_version,
            required_fields=requirement.required_fields,
        )

    def get_contract_snapshot(
        self,
        contract_id: str | None = None,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
        requirement: ConsumerRequirement | None = None,
        schema_id: str | None = None,
        expected_schema_version: int | None = None,
        min_supported_schema_version: int | None = None,
        required_fields: Iterable[str] = (),
    ) -> ConsumerContractSnapshot:
        if requirement is not None:
            if contract_id is not None:
                raise ValueError("contract_id cannot be combined with requirement")
            lookup = self.lookup_requirement(requirement)
        else:
            if contract_id is None:
                raise ValueError("contract_id is required")
            lookup = self.lookup_contract(
                contract_id,
                profile=profile,
                schema_id=schema_id,
                expected_schema_version=expected_schema_version,
                min_supported_schema_version=min_supported_schema_version,
                required_fields=required_fields,
            )
        return lookup.require_snapshot()

    snapshot = get_contract_snapshot
    get_contract = get_contract_snapshot

    def get_field(
        self,
        contract_id: str,
        field: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
        requirement: ConsumerRequirement | None = None,
    ) -> ConsumerFieldSnapshot:
        snapshot = self.get_contract_snapshot(
            contract_id if requirement is None else None,
            profile=profile,
            requirement=requirement,
        )
        return snapshot.field(field)

    field = get_field
    get_contract_field = get_field

    def get_quality(
        self,
        contract_id: str,
        field: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> FieldQuality:
        return self.get_field(contract_id, field, profile=profile).quality

    field_quality = get_quality

    def get_freshness(
        self,
        contract_id: str,
        field: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> FreshnessStatus:
        return self.get_field(contract_id, field, profile=profile).freshness

    freshness = get_freshness

    def get_health(
        self,
        contract_id: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> HealthStatus:
        return self.get_contract_snapshot(contract_id, profile=profile).health

    contract_health = get_health

    def get_lineage(
        self,
        contract_id: str,
        field: str,
        *,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> ConsumerLineage:
        return self.get_field(contract_id, field, profile=profile).lineage

    lineage = get_lineage

    def requirement_state(self, requirement: ConsumerRequirement) -> RequirementState:
        consumer_id = requirement.consumer_id
        if consumer_id is None:
            raise ValueError("requirement_state needs a requirement bound to a consumer_id")
        self.consumer_declaration(consumer_id)
        override = self._matching_override(consumer_id, requirement)
        if override is not None and override.blocked:
            return RequirementState(
                consumer_id,
                requirement,
                ConsumerAccessStatus.BLOCKED,
                reason=override.reason,
            )
        if requirement.role is not None:
            try:
                binding = self.resolve_binding(
                    requirement.role,
                    profile=requirement.profile,
                    consumer_id=consumer_id,
                )
            except ConsumerApiError as err:
                return RequirementState(consumer_id, requirement, err.status, reason=str(err))
            if not binding.enabled:
                return RequirementState(
                    consumer_id,
                    requirement,
                    ConsumerAccessStatus.BLOCKED,
                    reason="binding is disabled",
                    binding=binding,
                )
            return RequirementState(
                consumer_id,
                requirement,
                ConsumerAccessStatus.HEALTHY,
                binding=binding,
            )
        lookup = self.lookup_requirement(requirement)
        return RequirementState(
            consumer_id,
            requirement,
            lookup.status,
            reason=lookup.reason,
            snapshot=lookup.snapshot,
        )

    def impact_for(self, consumer_id: str) -> ConsumerImpact:
        declaration = self.consumer_declaration(consumer_id)
        if not declaration.enabled:
            states = tuple(
                RequirementState(
                    consumer_id,
                    requirement,
                    ConsumerAccessStatus.BLOCKED,
                    reason="consumer declaration is disabled",
                )
                for requirement in declaration.requirements
            )
        else:
            states = tuple(
                self.requirement_state(
                    replace(requirement, consumer_id=consumer_id)
                    if requirement.consumer_id is None
                    else requirement
                )
                for requirement in declaration.requirements
            )
        revisions = tuple(
            self.get_revision(profile)
            for profile in sorted(
                {requirement.profile for requirement in declaration.requirements},
                key=lambda item: item.value,
            )
            if self._runtime.active(profile) is not None
        )
        return ConsumerImpact(consumer_id, states, revisions)

    consumer_impact = impact_for

    def all_impacts(self) -> tuple[ConsumerImpact, ...]:
        self._ensure_open()
        return tuple(self.impact_for(consumer_id) for consumer_id in self._consumers)

    dependency_report = all_impacts

    def subscribe(
        self,
        consumer_id: str,
        callback: Callable[[ConsumerUpdate], Any],
        *,
        profile: ProfileId | str = ProfileId.BENNI,
        contract_id: str | None = None,
        role: str | None = None,
        field: str | None = None,
        fields: Iterable[str] = (),
        event_kinds: Iterable[ConsumerEventKind | str] | None = None,
        events: Iterable[ConsumerEventKind | str] | None = None,
    ) -> ConsumerSubscription:
        """Subscribe to relevant semantic changes and return an idempotent handle."""

        self._ensure_open()
        self.consumer_declaration(consumer_id)
        if not callable(callback):
            raise TypeError("subscription callback must be callable")
        profile_id = _profile_id(profile)
        if contract_id is not None and role is not None:
            raise ValueError("subscription cannot combine contract_id and role")
        if role is not None and not role.strip():
            raise ValueError("subscription role must be non-empty")
        selected_fields = {str(value) for value in fields}
        if field is not None:
            selected_fields.add(str(field))
        if any(not value.strip() for value in selected_fields):
            raise ValueError("subscription fields must be non-empty")
        selected_events = events if events is not None else event_kinds
        normalized_events = (
            frozenset(ConsumerEventKind(value) for value in selected_events)
            if selected_events is not None
            else frozenset(ConsumerEventKind)
        )
        if not normalized_events:
            raise ValueError("subscription event_kinds must not be empty")
        fingerprint = (
            consumer_id,
            profile_id,
            contract_id,
            role,
            frozenset(selected_fields),
            normalized_events,
            _callback_identity(callback),
        )
        for subscription in self._subscriptions.values():
            if subscription.active and self._subscription_fingerprint(subscription) == fingerprint:
                return ConsumerSubscription(self, subscription.token)
        token = uuid4().hex
        state = _SubscriptionState(
            token=token,
            consumer_id=consumer_id,
            profile=profile_id,
            callback=callback,
            contract_id=str(contract_id) if contract_id is not None else None,
            role=role,
            fields=frozenset(selected_fields),
            event_kinds=normalized_events,
        )
        self._subscriptions[token] = state
        for watched_profile, watched_contract_id in self._subscription_contracts(state):
            key = (watched_profile, watched_contract_id)
            if key not in self._observed:
                with self._suppress_graph_capture():
                    self._observed[key] = self._capture_contract(
                        watched_profile,
                        watched_contract_id,
                        refresh_evaluation=True,
                    )
        return ConsumerSubscription(self, token)

    subscribe_to_contract = subscribe

    def unsubscribe(self, subscription: ConsumerSubscription | str) -> bool:
        if self._closed:
            return False
        self._ensure_open()
        token = subscription.token if isinstance(subscription, ConsumerSubscription) else str(subscription)
        return self._remove_subscription(token)

    def cleanup_consumer(self, consumer_id: str) -> int:
        self._ensure_open()
        removed = 0
        for token, subscription in tuple(self._subscriptions.items()):
            if subscription.consumer_id == consumer_id and self._remove_subscription(token):
                removed += 1
        return removed

    def subscription_count(self, consumer_id: str | None = None) -> int:
        self._ensure_open()
        return sum(
            subscription.active
            and (consumer_id is None or subscription.consumer_id == consumer_id)
            for subscription in self._subscriptions.values()
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime.remove_listener(self._runtime_listener)
        for profile, callback in tuple(self._graph_callbacks.items()):
            graph = self._attached_graphs.get(profile)
            if graph is not None:
                graph.remove_change_listener(callback)
        self._graph_callbacks.clear()
        self._attached_graphs.clear()
        for subscription in self._subscriptions.values():
            subscription.active = False
        self._subscriptions.clear()
        self._observed.clear()
        self._consumers.clear()
        self._overrides.clear()

    unload = close

    def _subscription_active(self, token: str) -> bool:
        return bool(not self._closed and token in self._subscriptions and self._subscriptions[token].active)

    def _remove_subscription(self, token: str) -> bool:
        subscription = self._subscriptions.pop(token, None)
        if subscription is None:
            return False
        subscription.active = False
        return True

    @staticmethod
    def _subscription_fingerprint(subscription: _SubscriptionState) -> tuple[Any, ...]:
        return (
            subscription.consumer_id,
            subscription.profile,
            subscription.contract_id,
            subscription.role,
            subscription.fields,
            subscription.event_kinds,
            _callback_identity(subscription.callback),
        )

    @staticmethod
    def _watched_contract_ids(subscription: _SubscriptionState) -> tuple[str, ...]:
        if subscription.contract_id is not None:
            return (subscription.contract_id,)
        return ()

    def _subscription_contracts(
        self,
        subscription: _SubscriptionState,
    ) -> tuple[tuple[ProfileId, str], ...]:
        watched: set[tuple[ProfileId, str]] = {
            (subscription.profile, contract_id)
            for contract_id in self._watched_contract_ids(subscription)
        }
        if subscription.role is not None:
            watched.update(
                (subscription.profile, contract_id)
                for contract_id in self._contract_ids_for_role(
                    subscription.profile,
                    subscription.role,
                    subscription.consumer_id,
                )
            )
        elif subscription.contract_id is None:
            declaration = self._consumers.get(subscription.consumer_id)
            if declaration is not None:
                watched.update(
                    (requirement.profile, requirement.contract_id)
                    for requirement in declaration.requirements
                    if requirement.contract_id is not None
                )
        return tuple(sorted(watched, key=lambda item: (item[0].value, item[1])))

    def _watched_contracts(self) -> tuple[tuple[ProfileId, str], ...]:
        watched: set[tuple[ProfileId, str]] = set(self._observed)
        for subscription in self._subscriptions.values():
            if not subscription.active:
                continue
            watched.update(self._subscription_contracts(subscription))
        return tuple(sorted(watched, key=lambda item: (item[0].value, item[1])))

    def _contract_ids_for_role(
        self,
        profile: ProfileId,
        role: str,
        consumer_id: str | None,
    ) -> tuple[str, ...]:
        snapshot = self._runtime.active(profile)
        if snapshot is None:
            return ()
        binding_ids = {
            binding.binding_id
            for binding in snapshot.graph.bindings()
            if self._binding_matches_role(binding, role, consumer_id)
        }
        return tuple(
            sorted(
                {
                    fusion.contract_id
                    for fusion in snapshot.revision.payload.fusions
                    if binding_ids.intersection(fusion.input_binding_ids)
                }
            )
        )

    def _contract_uses_role(
        self,
        profile: ProfileId,
        role: str,
        consumer_id: str | None,
        contract_id: str,
    ) -> bool:
        return contract_id in self._contract_ids_for_role(profile, role, consumer_id)

    @staticmethod
    def _binding_matches_role(
        binding: SourceBinding,
        role: str,
        consumer_id: str | None,
    ) -> bool:
        if role not in {
            binding.binding_id,
            binding.field,
            binding.capability,
            binding.source_id,
        }:
            return False
        return not (
            consumer_id
            and binding.consumer_ids
            and consumer_id not in binding.consumer_ids
        )

    def _matching_override(
        self,
        consumer_id: str,
        requirement: ConsumerRequirement,
    ) -> ConsumerOverride | None:
        key = (
            consumer_id,
            requirement.profile,
            requirement.contract_id or "",
            requirement.role or "",
        )
        return self._overrides.get(key)

    def _attach_graph(self, snapshot: RegistryRuntimeSnapshot) -> None:
        profile = snapshot.profile
        old_callback = self._graph_callbacks.pop(profile, None)
        old_graph = self._attached_graphs.pop(profile, None)
        if old_callback is not None and old_graph is not None:
            old_graph.remove_change_listener(old_callback)

        graph = snapshot.graph

        def on_graph_change(changed_graph: Any, *, expected_graph=graph, selected_profile=profile) -> None:
            if changed_graph is expected_graph:
                self._on_graph_change(selected_profile, changed_graph)

        graph.add_change_listener(on_graph_change)
        self._graph_callbacks[profile] = on_graph_change
        self._attached_graphs[profile] = graph

    def _on_runtime_activation(self, snapshot: RegistryRuntimeSnapshot) -> None:
        if self._closed:
            return
        self._attach_graph(snapshot)
        for profile, contract_id in self._watched_contracts():
            old = self._observed.get((profile, contract_id))
            with self._suppress_graph_capture():
                current = self._capture_contract(
                    profile,
                    contract_id,
                    refresh_evaluation=True,
                )
            self._observed[(profile, contract_id)] = current
            self._dispatch_contract_change(profile, contract_id, old, current, "registry activation")

    def _on_graph_change(self, profile: ProfileId, _graph: Any) -> None:
        if self._closed or self._suppress_graph_events:
            return
        for selected_profile, contract_id in self._watched_contracts():
            if selected_profile != profile:
                continue
            old = self._observed.get((profile, contract_id))
            with self._suppress_graph_capture():
                current = self._capture_contract(
                    profile,
                    contract_id,
                    refresh_evaluation=True,
                )
            self._observed[(profile, contract_id)] = current
            self._dispatch_contract_change(profile, contract_id, old, current, "runtime graph update")

    @contextmanager
    def _suppress_graph_capture(self):
        self._suppress_graph_events += 1
        try:
            yield
        finally:
            self._suppress_graph_events -= 1

    def _capture_contract(
        self,
        profile: ProfileId,
        contract_id: str,
        *,
        refresh_evaluation: bool,
    ) -> _ObservedContract:
        runtime_snapshot = self._runtime.active(profile)
        if runtime_snapshot is None:
            return _ObservedContract(
                ConsumerAccessStatus.RUNTIME_NOT_READY,
                None,
                "runtime-not-ready",
                None,
                None,
                "registry runtime is not ready for this profile",
            )
        graph = runtime_snapshot.graph
        instance = _contract_instance(runtime_snapshot, contract_id)
        contract = graph.contract(contract_id)
        if instance is not None and (contract is None or refresh_evaluation):
            schema_id = instance.get("schema_id")
            schema_version = instance.get("schema_version")
            if not isinstance(schema_id, str) or not schema_id:
                return self._observed_error(
                    runtime_snapshot,
                    contract_id,
                    ConsumerAccessStatus.SCHEMA_MISMATCH,
                    "configured contract instance has no schema_id",
                )
            try:
                contract = graph.evaluate_contract(
                    contract_id,
                    schema_id,
                    schema_version=(int(schema_version) if schema_version is not None else None),
                    now=self._now_factory(),
                )
            except (KeyError, TypeError, ValueError) as err:
                return self._observed_error(
                    runtime_snapshot,
                    contract_id,
                    ConsumerAccessStatus.SCHEMA_MISMATCH,
                    "configured contract instance could not be evaluated",
                    reason_detail=str(err),
                )
        if contract is None:
            return self._observed_error(
                runtime_snapshot,
                contract_id,
                ConsumerAccessStatus.MISSING,
                "contract is not present in the active runtime",
            )
        public = self._public_snapshot(runtime_snapshot, contract)
        return _ObservedContract(
            public.status,
            public,
            self._definition_fingerprint(runtime_snapshot, contract_id, contract),
            public.revision,
            public.revision.graph_revision,
        )

    def _observed_error(
        self,
        runtime_snapshot: RegistryRuntimeSnapshot,
        contract_id: str,
        status: ConsumerAccessStatus,
        reason: str,
        *,
        reason_detail: str | None = None,
    ) -> _ObservedContract:
        if reason_detail:
            reason = f"{reason}: {reason_detail}"
        revision = self._revision_snapshot(runtime_snapshot)
        return _ObservedContract(
            status,
            None,
            self._definition_fingerprint(runtime_snapshot, contract_id, None),
            revision,
            runtime_snapshot.graph.revision,
            reason,
        )

    def _public_snapshot(
        self,
        runtime_snapshot: RegistryRuntimeSnapshot,
        contract: PublishedContract,
    ) -> ConsumerContractSnapshot:
        graph = runtime_snapshot.graph
        revision = self._revision_snapshot(runtime_snapshot)
        field_names: list[str] = []
        for name in (
            *contract.field_states.keys(),
            *contract.field_quality.keys(),
            *contract.values.keys(),
            *contract.lineage.keys(),
            *contract.field_evaluations.keys(),
        ):
            if name not in field_names:
                field_names.append(name)
        fields: list[ConsumerFieldSnapshot] = []
        for name in field_names:
            quality = contract.field_quality.get(name)
            evaluation = contract.field_evaluations.get(name)
            if quality is None or evaluation is None:
                continue
            lineage = self._lineage(graph, contract, evaluation)
            fields.append(
                ConsumerFieldSnapshot(
                    contract_id=contract.contract_id,
                    schema_id=contract.schema_id,
                    schema_version=contract.schema_version,
                    field=name,
                    value=_copy_value(contract.values.get(name)),
                    state=contract.field_states.get(name, evaluation.state),
                    quality=copy.deepcopy(quality),
                    lineage=lineage,
                    evaluation=ConsumerFieldEvaluation.from_model(evaluation),
                    registry_revision=revision.revision,
                    registry_revision_id=revision.revision_id,
                    graph_revision=graph.revision,
                )
            )
        return ConsumerContractSnapshot(
            contract_id=contract.contract_id,
            schema_id=contract.schema_id,
            schema_version=contract.schema_version,
            status=_status_from_health(contract.health),
            health=contract.health,
            fields=tuple(fields),
            revision=revision,
            generated_at=contract.generated_at,
        )

    @staticmethod
    def _lineage(
        graph: Any,
        contract: PublishedContract,
        evaluation: FieldEvaluation,
    ) -> ConsumerLineage:
        active_binding_ids = tuple(contract.lineage.get(evaluation.field, evaluation.active_binding_ids))
        candidate_binding_ids = tuple(evaluation.candidate_binding_ids)

        def values(binding_ids: Iterable[str], attribute: str) -> tuple[str, ...]:
            result: list[str] = []
            for binding_id in binding_ids:
                try:
                    binding = graph.binding(binding_id)
                except (KeyError, TypeError):
                    continue
                value = getattr(binding, attribute)
                if value not in result:
                    result.append(value)
            return tuple(result)

        return ConsumerLineage(
            active_binding_ids=active_binding_ids,
            candidate_binding_ids=candidate_binding_ids,
            active_source_ids=values(active_binding_ids, "source_id"),
            candidate_source_ids=values(candidate_binding_ids, "source_id"),
            active_entity_ids=values(active_binding_ids, "entity_id"),
            candidate_entity_ids=values(candidate_binding_ids, "entity_id"),
        )

    def _revision_snapshot(self, snapshot: RegistryRuntimeSnapshot) -> ConsumerRevisionSnapshot:
        # The existing runtime holder stores the LKG source explicitly.  A LKG
        # read is a usable configuration but remains degraded at registry level.
        source = snapshot.source.value
        registry_health = (
            HealthStatus.DEGRADED if source == "last_known_good" else HealthStatus.HEALTHY
        )
        return ConsumerRevisionSnapshot(
            profile=snapshot.profile,
            revision=snapshot.revision.revision,
            revision_id=snapshot.revision.id,
            registry_schema_version=snapshot.revision.schema_version,
            source=source,
            registry_health=registry_health,
            graph_revision=snapshot.graph.revision,
        )

    @staticmethod
    def _definition_fingerprint(
        runtime_snapshot: RegistryRuntimeSnapshot,
        contract_id: str,
        contract: PublishedContract | None,
    ) -> str:
        payload = runtime_snapshot.revision.payload
        instance = _contract_instance(runtime_snapshot, contract_id)
        fusions = [item.as_dict() for item in payload.fusions if item.contract_id == contract_id]
        binding_ids = {
            binding_id
            for fusion in payload.fusions
            if fusion.contract_id == contract_id
            for binding_id in fusion.input_binding_ids
        }
        bindings = [
            item.as_dict()
            for item in payload.bindings
            if item.binding_id in binding_ids
        ]
        data = {
            "instance": dict(instance) if instance is not None else None,
            "fusions": fusions,
            "bindings": bindings,
            "evaluated_schema": (
                {"schema_id": contract.schema_id, "schema_version": contract.schema_version}
                if contract is not None
                else None
            ),
        }
        encoded = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _dispatch_contract_change(
        self,
        profile: ProfileId,
        contract_id: str,
        old: _ObservedContract | None,
        current: _ObservedContract,
        reason: str,
    ) -> None:
        if old is None:
            old = _ObservedContract(
                ConsumerAccessStatus.RUNTIME_NOT_READY,
                None,
                "unobserved",
                None,
                None,
            )
        changed_fields, base_events = self._diff_observed(old, current)
        if not base_events:
            return
        for subscription in tuple(self._subscriptions.values()):
            if not subscription.active or subscription.profile != profile:
                continue
            if subscription.contract_id is not None and subscription.contract_id != contract_id:
                continue
            if subscription.role is not None and not self._contract_uses_role(
                profile,
                subscription.role,
                subscription.consumer_id,
                contract_id,
            ):
                continue
            selected_fields = (
                changed_fields & subscription.fields if subscription.fields else changed_fields
            )
            selected_events = set(base_events)
            if subscription.fields and not selected_fields:
                # Field filtering suppresses value/quality changes that only
                # belong to another field; contract availability remains useful.
                selected_events.discard(ConsumerEventKind.HEALTH_CHANGED)
                selected_events.discard(ConsumerEventKind.VALUE_CHANGED)
                selected_events.discard(ConsumerEventKind.QUALITY_CHANGED)
                selected_events.discard(ConsumerEventKind.FRESHNESS_CHANGED)
                if changed_fields:
                    selected_events.discard(ConsumerEventKind.REVISION_CHANGED)
            if not selected_events.intersection(subscription.event_kinds):
                continue
            update = ConsumerUpdate(
                consumer_id=subscription.consumer_id,
                profile=profile,
                contract_id=contract_id,
                event_kinds=frozenset(selected_events.intersection(subscription.event_kinds)),
                snapshot=current.snapshot,
                previous_snapshot=old.snapshot,
                changed_fields=tuple(sorted(selected_fields)),
                revision=current.revision,
                graph_revision=current.graph_revision,
                reason=reason,
            )
            self._invoke_callback(subscription, update)

    @staticmethod
    def _diff_observed(
        old: _ObservedContract,
        current: _ObservedContract,
    ) -> tuple[set[str], set[ConsumerEventKind]]:
        changed_fields: set[str] = set()
        events: set[ConsumerEventKind] = set()
        old_present = old.snapshot is not None
        new_present = current.snapshot is not None
        if not old_present and new_present:
            events.add(ConsumerEventKind.AVAILABLE)
        elif old_present and not new_present:
            events.add(ConsumerEventKind.UNAVAILABLE)
        if old.fingerprint != current.fingerprint:
            events.add(ConsumerEventKind.REVISION_CHANGED)
        if old.snapshot is None or current.snapshot is None:
            if old.status != current.status and old_present == new_present:
                events.add(ConsumerEventKind.HEALTH_CHANGED)
            return changed_fields, events
        old_fields = {item.field: item for item in old.snapshot.fields}
        new_fields = {item.field: item for item in current.snapshot.fields}
        for field_name in sorted(set(old_fields) | set(new_fields)):
            before = old_fields.get(field_name)
            after = new_fields.get(field_name)
            if before is None or after is None:
                changed_fields.add(field_name)
                events.update(
                    {
                        ConsumerEventKind.VALUE_CHANGED,
                        ConsumerEventKind.QUALITY_CHANGED,
                        ConsumerEventKind.FRESHNESS_CHANGED,
                    }
                )
                continue
            if not _values_equal(before.value, after.value) or before.state != after.state:
                changed_fields.add(field_name)
                events.add(ConsumerEventKind.VALUE_CHANGED)
            if before.quality != after.quality:
                changed_fields.add(field_name)
                events.add(ConsumerEventKind.QUALITY_CHANGED)
            if before.freshness != after.freshness:
                changed_fields.add(field_name)
                events.add(ConsumerEventKind.FRESHNESS_CHANGED)
            if before.health != after.health:
                changed_fields.add(field_name)
                events.add(ConsumerEventKind.HEALTH_CHANGED)
        if old.snapshot.status != current.snapshot.status or old.snapshot.health != current.snapshot.health:
            events.add(ConsumerEventKind.HEALTH_CHANGED)
        return changed_fields, events

    @staticmethod
    def _invoke_callback(subscription: _SubscriptionState, update: ConsumerUpdate) -> None:
        try:
            result = subscription.callback(update)
            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(result)
                else:
                    task = loop.create_task(result)
                    task.add_done_callback(ConsumerApi._log_callback_task)
        except Exception:  # pragma: no cover - exercised by callback isolation test
            LOGGER.exception(
                "consumer subscription callback failed consumer=%s contract=%s",
                subscription.consumer_id,
                update.contract_id,
            )

    @staticmethod
    def _log_callback_task(task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:  # pragma: no cover - defensive async callback boundary
            LOGGER.exception("consumer subscription task failed")


def _values_equal(left: Any, right: Any) -> bool:
    try:
        result = left == right
        return bool(result)
    except Exception:
        return repr(left) == repr(right)


def _callback_identity(callback: Callable[..., Any]) -> Any:
    """Keep bound-method registrations stable across attribute access."""

    owner = getattr(callback, "__self__", None)
    function = getattr(callback, "__func__", None)
    if owner is not None and function is not None:
        return (id(owner), id(function))
    return id(callback)


def _coalesce_version(
    primary: int | None,
    alias: int | None,
    name: str,
) -> int | None:
    if primary is not None and alias is not None and primary != alias:
        raise ValueError(f"{name} and its alias disagree")
    return primary if primary is not None else alias


def _profile_id(value: ProfileId | str) -> ProfileId:
    if isinstance(value, ProfileId):
        return value
    try:
        return ProfileId(str(value))
    except ValueError as err:
        raise ValueError("profile must be benni or eltern") from err


def _contract_instance(
    snapshot: RegistryRuntimeSnapshot,
    contract_id: str,
) -> Mapping[str, Any] | None:
    for instance in snapshot.revision.payload.contract_instances:
        if str(instance.get("contract_id") or instance.get("id")) == contract_id:
            return instance
    return None


# Descriptive aliases for integrations choosing a domain-specific spelling.
RegistryConsumerAPI = ConsumerApi
InternalConsumerAPI = ConsumerApi
ConsumerExchange = ConsumerApi
ConsumerAPI = ConsumerApi
ConsumerContract = ConsumerContractSnapshot
ConsumerField = ConsumerFieldSnapshot
ConsumerRequirementState = RequirementState


__all__ = [
    "ConsumerAccessStatus",
    "ContractAccessStatus",
    "ConsumerEventKind",
    "SubscriptionEventKind",
    "ConsumerApi",
    "RegistryConsumerAPI",
    "InternalConsumerAPI",
    "ConsumerExchange",
    "ConsumerAPI",
    "ConsumerApiError",
    "ConsumerRuntimeNotReadyError",
    "ConsumerContractMissingError",
    "ConsumerFieldMissingError",
    "ConsumerSchemaMismatchError",
    "ConsumerVersionIncompatibleError",
    "ConsumerBindingMissingError",
    "ConsumerBindingAmbiguousError",
    "ConsumerNotRegisteredError",
    "ConsumerAlreadyRegisteredError",
    "ConsumerApiClosedError",
    "ConsumerRequirement",
    "ConsumerDeclaration",
    "ConsumerOverride",
    "ConsumerRevisionSnapshot",
    "ConsumerLineage",
    "ConsumerFieldEvaluation",
    "ConsumerFieldSnapshot",
    "ConsumerContractSnapshot",
    "ConsumerContract",
    "ConsumerField",
    "ConsumerBinding",
    "ContractLookup",
    "RequirementState",
    "ConsumerRequirementState",
    "ConsumerImpact",
    "ConsumerUpdate",
    "ConsumerSubscription",
]
