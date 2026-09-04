"""Canonical registry configuration and revision-domain primitives.

The registry stores configuration only.  Runtime signals, quality, freshness,
and diagnostics remain owned by the existing signal graph and runtime store.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping

from .const import REGISTRY_SCHEMA_VERSION
from .models import ConfigModel, Fusion, ProfileId, SourceBinding
from .quality import HealthStatus, utc_now


class RegistryError(ValueError):
    """Base error for invalid registry data or lifecycle operations."""


class RegistryValidationError(RegistryError):
    """A registry payload cannot be built into a valid signal graph."""


class RegistryCorruptionError(RegistryError):
    """Persisted registry or Last-Known-Good data failed integrity checks."""


class RevisionNotFound(RegistryError):
    """The requested registry revision does not exist."""


class RevisionStateError(RegistryError):
    """The requested revision state transition is not allowed."""


class ConcurrencyConflict(RegistryError):
    """The active revision changed since the caller created its draft."""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected_base_revision = expected
        self.actual_base_revision = actual
        super().__init__(
            "registry revision conflict: "
            f"expected base {expected}, actual base {actual}"
        )


class RevisionValidationFailed(RegistryError):
    """A draft was rejected during activation validation."""

    def __init__(self, revision: int, reason: str) -> None:
        self.revision = revision
        self.reason = reason
        super().__init__(f"registry revision {revision} rejected: {reason}")


class RevisionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RegistrySource(str, Enum):
    POSTGRESQL = "postgresql"
    LAST_KNOWN_GOOD = "last_known_good"
    NONE = "none"


def _json_clone(value: Any, *, label: str) -> Any:
    """Validate JSONB-compatible values and return an isolated JSON copy."""

    def validate(node: Any, path: str) -> None:
        if node is None or isinstance(node, (str, int, bool)):
            return
        if isinstance(node, float):
            if node != node or node in (float("inf"), float("-inf")):
                raise ValueError(f"{label} contains a non-finite number at {path}")
            return
        if isinstance(node, Mapping):
            for key, child in node.items():
                if not isinstance(key, str):
                    raise ValueError(f"{label} object keys must be strings at {path}")
                validate(child, f"{path}.{key}")
            return
        if isinstance(node, (list, tuple)):
            for index, child in enumerate(node):
                validate(child, f"{path}[{index}]")
            return
        raise ValueError(
            f"{label} contains a non-JSON value at {path}: {type(node).__name__}"
        )

    validate(value, label)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{label} must contain JSONB-compatible values") from err


def _record_sequence(
    value: Any,
    *,
    label: str,
    identity_key: str,
) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        records: list[Any] = []
        for key, record in value.items():
            if not isinstance(record, Mapping):
                raise ValueError(f"{label} entries must be objects")
            normalized = dict(record)
            normalized.setdefault(identity_key, str(key))
            records.append(normalized)
    else:
        if isinstance(value, (str, bytes)):
            raise ValueError(f"{label} must be a sequence of objects")
        try:
            records = list(value)
        except TypeError as err:
            raise ValueError(f"{label} must be a sequence of objects") from err
    normalized_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError(f"{label} entries must be objects")
        normalized_records.append(
            _json_clone(dict(record), label=f"{label} entry")
        )
    return tuple(normalized_records)


@dataclass(frozen=True)
class RegistryPayload:
    """One complete profile configuration stored in a registry revision."""

    profile: ProfileId = ProfileId.BENNI
    schema_version: int = REGISTRY_SCHEMA_VERSION
    bindings: tuple[SourceBinding, ...] = ()
    fusions: tuple[Fusion, ...] = ()
    contract_instances: tuple[dict[str, Any], ...] = ()
    consumer_overrides: Mapping[str, Any] = field(default_factory=dict)
    registry_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ProfileId):
            raise ValueError("registry profile must be a supported ProfileId")
        if self.schema_version != REGISTRY_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported registry schema version: {self.schema_version}"
            )

        bindings = tuple(self.bindings)
        if any(not isinstance(binding, SourceBinding) for binding in bindings):
            raise ValueError("registry bindings must be SourceBinding objects")
        mismatched_bindings = tuple(
            binding.binding_id
            for binding in bindings
            if binding.profile_id != self.profile
        )
        if mismatched_bindings:
            raise ValueError(
                "registry bindings must belong to the selected profile: "
                + ", ".join(mismatched_bindings)
            )
        binding_ids = [binding.binding_id for binding in bindings]
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("registry binding IDs must be unique")

        fusions = tuple(self.fusions)
        if any(not isinstance(fusion, Fusion) for fusion in fusions):
            raise ValueError("registry fusions must be Fusion objects")
        fusion_ids = [fusion.fusion_id for fusion in fusions]
        if len(set(fusion_ids)) != len(fusion_ids):
            raise ValueError("registry fusion IDs must be unique")

        contract_instances = _record_sequence(
            self.contract_instances,
            label="contract_instances",
            identity_key="contract_id",
        )
        mismatched_instances = tuple(
            str(instance.get("contract_id") or instance.get("id"))
            for instance in contract_instances
            if "profile" in instance
            and ProfileId(str(instance["profile"])) != self.profile
        )
        if mismatched_instances:
            raise ValueError(
                "registry contract instances must belong to the selected profile: "
                + ", ".join(mismatched_instances)
            )
        overrides = self.consumer_overrides
        if not isinstance(overrides, Mapping):
            raise ValueError("consumer_overrides must be an object")
        metadata = self.registry_metadata
        if not isinstance(metadata, Mapping):
            raise ValueError("registry_metadata must be an object")

        object.__setattr__(self, "bindings", bindings)
        object.__setattr__(self, "fusions", fusions)
        object.__setattr__(
            self,
            "contract_instances",
            contract_instances,
        )
        object.__setattr__(
            self,
            "consumer_overrides",
            _json_clone(dict(overrides), label="consumer_overrides"),
        )
        object.__setattr__(
            self,
            "registry_metadata",
            _json_clone(dict(metadata), label="registry_metadata"),
        )
        # Validate every persisted field, including nested extension metadata.
        _json_clone(self.as_dict(), label="registry payload")

    @classmethod
    def from_config(
        cls,
        config: ConfigModel,
        *,
        fusions: Iterable[Fusion] = (),
        contract_instances: Iterable[Mapping[str, Any]] = (),
        consumer_overrides: Mapping[str, Any] | None = None,
        registry_metadata: Mapping[str, Any] | None = None,
    ) -> "RegistryPayload":
        """Project existing bootstrap models into the registry payload shape."""

        return cls(
            profile=config.profile,
            bindings=config.bindings,
            fusions=tuple(fusions),
            contract_instances=_record_sequence(
                contract_instances,
                label="contract_instances",
                identity_key="contract_id",
            ),
            consumer_overrides=consumer_overrides or {},
            registry_metadata=registry_metadata or {},
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RegistryPayload":
        if not isinstance(data, Mapping):
            raise ValueError("registry payload must be an object")
        allowed_keys = {
            "profile",
            "schema_version",
            "bindings",
            "fusions",
            "contract_instances",
            "consumer_overrides",
            "registry_metadata",
        }
        unknown = set(data) - allowed_keys
        if unknown:
            raise ValueError(
                "registry payload contains unknown fields: "
                + ", ".join(sorted(str(value) for value in unknown))
            )

        profile = ProfileId(str(data.get("profile", ProfileId.BENNI.value)))
        binding_records = _record_sequence(
            data.get("bindings", ()),
            label="bindings",
            identity_key="binding_id",
        )
        bindings = tuple(
            SourceBinding.from_dict(
                dict(record),
                default_profile=profile,
            )
            for record in binding_records
        )
        fusion_records = _record_sequence(
            data.get("fusions", ()),
            label="fusions",
            identity_key="fusion_id",
        )
        fusions = tuple(Fusion.from_dict(dict(record)) for record in fusion_records)

        return cls(
            profile=profile,
            schema_version=int(
                data.get("schema_version", REGISTRY_SCHEMA_VERSION)
            ),
            bindings=bindings,
            fusions=fusions,
            contract_instances=_record_sequence(
                data.get("contract_instances", ()),
                label="contract_instances",
                identity_key="contract_id",
            ),
            consumer_overrides=data.get("consumer_overrides", {}),
            registry_metadata=data.get("registry_metadata", {}),
        )

    def as_dict(self) -> dict[str, Any]:
        return _json_clone(
            {
                "profile": self.profile.value,
                "schema_version": self.schema_version,
                "bindings": [binding.as_dict() for binding in self.bindings],
                "fusions": [fusion.as_dict() for fusion in self.fusions],
                "contract_instances": [
                    dict(value) for value in self.contract_instances
                ],
                "consumer_overrides": dict(self.consumer_overrides),
                "registry_metadata": dict(self.registry_metadata),
            },
            label="registry payload",
        )


def canonical_registry_json(payload: RegistryPayload | Mapping[str, Any]) -> str:
    normalized = (
        payload if isinstance(payload, RegistryPayload) else RegistryPayload.from_dict(payload)
    )
    return json.dumps(
        normalized.as_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def registry_checksum(payload: RegistryPayload | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_registry_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RegistryRevision:
    """A persisted registry payload and its lifecycle metadata."""

    id: str
    revision: int
    profile: ProfileId
    schema_version: int
    payload: RegistryPayload
    status: RevisionStatus
    created_at: datetime
    activated_at: datetime | None = None
    checksum: str = ""
    created_by: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("registry revision id is required")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ValueError("registry revision must be an integer")
        if self.revision <= 0:
            raise ValueError("registry revision must be positive")
        if not isinstance(self.profile, ProfileId):
            raise ValueError("revision profile must be a supported ProfileId")
        if not isinstance(self.status, RevisionStatus):
            raise ValueError("revision status must be a supported RevisionStatus")
        if not isinstance(self.payload, RegistryPayload):
            raise ValueError("revision payload must be a RegistryPayload")
        if self.profile != self.payload.profile:
            raise ValueError("revision profile does not match its payload")
        if self.schema_version != REGISTRY_SCHEMA_VERSION:
            raise ValueError("unsupported persisted registry schema version")
        if self.schema_version != self.payload.schema_version:
            raise ValueError("revision schema version does not match its payload")
        for label, timestamp in (
            ("created_at", self.created_at),
            ("activated_at", self.activated_at),
        ):
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError(f"{label} must be timezone-aware")
        if self.status in {RevisionStatus.ACTIVE, RevisionStatus.SUPERSEDED}:
            if self.activated_at is None:
                raise ValueError(f"{self.status.value} revision needs activated_at")
        elif self.activated_at is not None:
            raise ValueError(f"{self.status.value} revision cannot have activated_at")
        expected_checksum = registry_checksum(self.payload)
        if self.checksum and self.checksum != expected_checksum:
            raise ValueError("registry revision checksum mismatch")
        object.__setattr__(self, "checksum", self.checksum or expected_checksum)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RegistryRevision":
        if not isinstance(data, Mapping):
            raise RegistryCorruptionError("persisted registry revision must be an object")
        required = {
            "id",
            "revision",
            "profile",
            "schema_version",
            "payload",
            "status",
            "created_at",
            "activated_at",
            "checksum",
            "created_by",
        }
        missing = required - set(data)
        if missing:
            raise RegistryCorruptionError(
                "Last-Known-Good revision is missing fields: "
                + ", ".join(sorted(missing))
            )
        try:
            created_at = datetime.fromisoformat(str(data["created_at"]))
            activated_raw = data["activated_at"]
            activated_at = (
                datetime.fromisoformat(str(activated_raw))
                if activated_raw is not None
                else None
            )
            return cls(
                id=str(data["id"]),
                revision=int(data["revision"]),
                profile=ProfileId(str(data["profile"])),
                schema_version=int(data["schema_version"]),
                payload=RegistryPayload.from_dict(data["payload"]),
                status=RevisionStatus(str(data["status"])),
                created_at=created_at,
                activated_at=activated_at,
                checksum=str(data["checksum"]),
                created_by=(
                    str(data["created_by"])
                    if data["created_by"] is not None
                    else None
                ),
            )
        except RegistryCorruptionError:
            raise
        except (KeyError, TypeError, ValueError) as err:
            raise RegistryCorruptionError(
                f"invalid Last-Known-Good revision: {err}"
            ) from err

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "revision": self.revision,
            "profile": self.profile.value,
            "schema_version": self.schema_version,
            "payload": self.payload.as_dict(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "activated_at": self.activated_at.isoformat()
            if self.activated_at
            else None,
            "checksum": self.checksum,
            "created_by": self.created_by,
        }

    def as_cache_dict(self) -> dict[str, Any]:
        if self.status != RevisionStatus.ACTIVE:
            raise RevisionStateError(
                "only an active revision can be stored as Last-Known-Good"
            )
        return self.as_dict()


def validate_registry_payload(
    payload: RegistryPayload | Mapping[str, Any],
    *,
    schema_registry: Any | None = None,
) -> RegistryPayload:
    """Validate topology and typed contract instances before activation."""

    from .contracts import default_schema_registry
    from .graph import GraphError, SignalGraph
    from .profiles import profile_definition

    try:
        normalized = (
            payload
            if isinstance(payload, RegistryPayload)
            else RegistryPayload.from_dict(payload)
        )
        profile_definition(normalized.profile).validate_bindings(normalized.bindings)
        graph = SignalGraph(
            registry=schema_registry or default_schema_registry(),
            profile=normalized.profile,
        )
        for binding in normalized.bindings:
            graph.add_binding(binding)
        graph.add_fusions(normalized.fusions)

        instances_by_id: dict[str, Mapping[str, Any]] = {}
        for instance in normalized.contract_instances:
            contract_id = instance.get("contract_id") or instance.get("id")
            schema_id = instance.get("schema_id")
            if not isinstance(contract_id, str) or not contract_id:
                raise ValueError("contract instance needs a contract_id")
            if contract_id in instances_by_id:
                raise ValueError(f"duplicate contract instance: {contract_id}")
            if not isinstance(schema_id, str) or not schema_id:
                raise ValueError(
                    f"contract instance {contract_id} needs a schema_id"
                )
            schema_version = instance.get("schema_version")
            registry = schema_registry or default_schema_registry()
            registry.get(
                schema_id,
                int(schema_version) if schema_version is not None else None,
            )
            if "profile" in instance and ProfileId(str(instance["profile"])) != normalized.profile:
                raise ValueError(
                    f"contract instance {contract_id} belongs to another profile"
                )
            instances_by_id[contract_id] = instance

        if instances_by_id:
            registry = schema_registry or default_schema_registry()
            for fusion in normalized.fusions:
                instance = instances_by_id.get(fusion.contract_id)
                if instance is None:
                    raise ValueError(
                        f"fusion {fusion.fusion_id} references unknown contract "
                        f"instance {fusion.contract_id}"
                    )
                schema = registry.get(
                    str(instance["schema_id"]),
                    int(instance["schema_version"])
                    if instance.get("schema_version") is not None
                    else None,
                )
                schema.field(fusion.field)
    except (GraphError, KeyError, TypeError, ValueError) as err:
        raise RegistryValidationError(str(err)) from err
    return normalized


@dataclass(frozen=True)
class RegistryLoadResult:
    """Active configuration plus its source and degraded-health state."""

    profile: ProfileId
    revision: RegistryRevision | None
    source: RegistrySource
    health: HealthStatus
    reason: str | None = None

    @property
    def used_last_known_good(self) -> bool:
        return self.source == RegistrySource.LAST_KNOWN_GOOD

    @property
    def configuration_available(self) -> bool:
        return self.revision is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "revision": self.revision.as_dict() if self.revision else None,
            "source": self.source.value,
            "health": self.health.value,
            "reason": self.reason,
            "used_last_known_good": self.used_last_known_good,
        }


def new_draft_revision(
    payload: RegistryPayload | Mapping[str, Any],
    *,
    revision_id: str,
    revision: int,
    created_by: str | None = None,
    now: datetime | None = None,
) -> RegistryRevision:
    """Build a draft for adapters that allocate IDs outside PostgreSQL."""

    normalized = (
        payload if isinstance(payload, RegistryPayload) else RegistryPayload.from_dict(payload)
    )
    return RegistryRevision(
        id=revision_id,
        revision=revision,
        profile=normalized.profile,
        schema_version=normalized.schema_version,
        payload=normalized,
        status=RevisionStatus.DRAFT,
        created_at=now or utc_now(),
        created_by=created_by,
    )


# Descriptive aliases keep callers from having to depend on one spelling of
# the lifecycle errors/model while preserving a single implementation.
RegistryConfiguration = RegistryPayload
RevisionValidationError = RevisionValidationFailed
RegistryConcurrencyError = ConcurrencyConflict
