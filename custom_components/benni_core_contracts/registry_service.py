"""Validated registry domain service for the Issue #17 write boundary.

The service owns only edit-session state and orchestration.  PostgreSQL keeps
the canonical revision history; ``PostgresRegistryRepository`` remains the
single implementation of revision, atomic-activation, concurrency, and LKG
semantics.  Runtime observations never enter this module's write path.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from .contracts import default_schema_registry
from .graph import SignalGraph
from .models import ProfileId, SourceBinding
from .quality import utc_now
from .registry import (
    ConcurrencyConflict,
    RegistryError,
    RegistryLoadResult,
    RegistryPayload,
    RegistryRevision,
    RegistrySource,
    RegistryValidationError,
    RevisionNotFound,
    RevisionStateError,
    RevisionStatus,
    RevisionValidationFailed,
    validate_registry_payload,
)
from .registry_store import PostgresUnavailableError, RegistryStoreError


LOGGER = logging.getLogger(__name__)

_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "connection_string",
    "database_url",
    "postgres",
    "dsn",
)


class RegistryServiceError(RegistryError):
    """Base error with a stable transport code for the write boundary."""

    code = "registry_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code or self.code
        self.details = dict(details or {})
        super().__init__(message)


class DraftNotFoundError(RegistryServiceError):
    code = "draft_not_found"


class InvalidReferenceError(RegistryServiceError):
    code = "invalid_reference"


class PermissionDeniedError(RegistryServiceError):
    code = "permission_denied"


class BackendUnavailableError(RegistryServiceError):
    code = "backend_unavailable"


class RegistrySecurityError(RegistryServiceError):
    code = "secrets_not_allowed"


class DraftValidationError(RegistryServiceError):
    code = "validation_error"

    def __init__(
        self,
        message: str,
        *,
        issues: Iterable["ValidationIssue"] = (),
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.issues = tuple(issues)
        super().__init__(message, details=details)


class RuntimeActivationError(RegistryServiceError):
    code = "runtime_activation_failed"


@dataclass(frozen=True)
class ValidationIssue:
    """One safe, frontend-consumable validation diagnostic."""

    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Result of a draft-only validation and graph probe."""

    draft_id: str
    profile: ProfileId
    base_revision: int
    valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    graph_probe_revision: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "profile": self.profile.value,
            "base_revision": self.base_revision,
            "valid": self.valid,
            "errors": [error.as_dict() for error in self.errors],
            "graph_probe": {
                "performed": self.graph_probe_revision is not None,
                "revision": self.graph_probe_revision,
            },
        }


@dataclass(frozen=True)
class RegistryDraft:
    """An in-memory edit session; it is never an autosaved registry row."""

    draft_id: str
    profile: ProfileId
    base_revision: int
    base_revision_id: str | None
    payload: RegistryPayload
    created_at: datetime
    updated_at: datetime
    owner_id: str | None = None

    def __post_init__(self) -> None:
        if not self.draft_id:
            raise ValueError("draft_id is required")
        if not isinstance(self.profile, ProfileId):
            raise ValueError("draft profile must be a supported ProfileId")
        if (
            isinstance(self.base_revision, bool)
            or not isinstance(self.base_revision, int)
            or self.base_revision < 0
        ):
            raise ValueError("draft base_revision must be non-negative")
        if self.payload.profile != self.profile:
            raise ValueError("draft profile does not match its payload")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("draft timestamps must be timezone-aware")

    def as_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "profile": self.profile.value,
            "base_revision": self.base_revision,
            "base_revision_id": self.base_revision_id,
            # Drafts can originate from a previously persisted payload.  Keep
            # the public representation defensive even when an old row was
            # created before the write-boundary secret guard existed.
            "payload": _public_json(self.payload.as_dict()),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class RegistryRuntimeSnapshot:
    """The validated registry graph currently available to runtime callers."""

    profile: ProfileId
    revision: RegistryRevision
    graph: SignalGraph
    source: RegistrySource

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "revision": self.revision.revision,
            "revision_id": self.revision.id,
            "source": self.source.value,
        }


class RegistryRuntime:
    """Atomic in-process holder for validated registry payloads and graphs.

    ``prepare`` has no side effects.  ``activate`` swaps one immutable
    snapshot only after the repository has committed the corresponding active
    revision.  The holder is intentionally not a consumer API.
    """

    def __init__(self, *, schema_registry: Any | None = None) -> None:
        self.schema_registry = schema_registry or default_schema_registry()
        self._active: dict[ProfileId, RegistryRuntimeSnapshot] = {}
        self._listeners: list[Callable[[RegistryRuntimeSnapshot], None]] = []

    def prepare(
        self,
        payload: RegistryPayload | Mapping[str, Any],
    ) -> tuple[RegistryPayload, SignalGraph]:
        normalized = validate_registry_payload(
            payload,
            schema_registry=self.schema_registry,
        )
        graph = SignalGraph(registry=self.schema_registry)
        for binding in normalized.bindings:
            graph.add_binding(binding)
        graph.add_fusions(normalized.fusions)
        return normalized, graph

    def activate(
        self,
        revision: RegistryRevision,
        graph: SignalGraph | None = None,
        *,
        source: RegistrySource = RegistrySource.POSTGRESQL,
    ) -> RegistryRuntimeSnapshot:
        if revision.status != RevisionStatus.ACTIVE:
            raise RuntimeActivationError(
                "only an active revision can be installed in runtime",
                details={"revision": revision.revision},
            )
        if graph is None:
            _normalized, graph = self.prepare(revision.payload)
        snapshot = RegistryRuntimeSnapshot(
            profile=revision.profile,
            revision=revision,
            graph=graph,
            source=source,
        )
        self._active[revision.profile] = snapshot
        for listener in tuple(self._listeners):
            try:
                listener(snapshot)
            except Exception:  # pragma: no cover - defensive integration hook
                LOGGER.exception(
                    "registry runtime listener failed profile=%s revision=%s",
                    revision.profile.value,
                    revision.revision,
                )
        return snapshot

    def active(self, profile: ProfileId | str) -> RegistryRuntimeSnapshot | None:
        profile_id = _profile_id(profile)
        return self._active.get(profile_id)

    def graph(self, profile: ProfileId | str) -> SignalGraph | None:
        snapshot = self.active(profile)
        return snapshot.graph if snapshot is not None else None

    def snapshots(self) -> tuple[RegistryRuntimeSnapshot, ...]:
        return tuple(self._active.values())

    def add_listener(self, listener: Callable[[RegistryRuntimeSnapshot], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[RegistryRuntimeSnapshot], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)


def _profile_id(value: ProfileId | str) -> ProfileId:
    if isinstance(value, ProfileId):
        return value
    try:
        return ProfileId(str(value))
    except ValueError as err:
        raise RegistryServiceError(
            "profile must be benni or eltern",
            code="validation_error",
            details={"field": "profile"},
        ) from err


def _sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _assert_safe_json(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise RegistryServiceError(
                    "registry object keys must be strings",
                    code="validation_error",
                    details={"path": path},
                )
            if _sensitive_key(key):
                raise RegistrySecurityError(
                    "registry payload cannot contain credentials or secrets",
                    details={"path": f"{path}.{key}"},
                )
            _assert_safe_json(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_safe_json(child, path=f"{path}[{index}]")


def _public_json(value: Any) -> Any:
    """Return a defensive response copy without sensitive metadata."""

    if isinstance(value, Mapping):
        return {
            str(key): _public_json(child)
            for key, child in value.items()
            if isinstance(key, str) and not _sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [_public_json(child) for child in value]
    return deepcopy(value)


def public_revision_dict(revision: RegistryRevision) -> dict[str, Any]:
    data = revision.as_dict()
    data["payload"] = _public_json(data["payload"])
    return data


def public_load_result_dict(result: RegistryLoadResult) -> dict[str, Any]:
    data = result.as_dict()
    if result.revision is not None:
        data["revision"] = public_revision_dict(result.revision)
    return data


def _validation_issue(error: Exception) -> ValidationIssue:
    message = str(error)
    reference_markers = (
        "unknown binding",
        "unknown fusion",
        "references unknown",
        "does not exist",
    )
    code = (
        "invalid_reference"
        if any(marker in message.casefold() for marker in reference_markers)
        else "validation_error"
    )
    return ValidationIssue(code, message)


class RegistryDomainService:
    """Draft and validated-write service over one PostgreSQL repository."""

    def __init__(
        self,
        repository: Any,
        *,
        schema_registry: Any | None = None,
        runtime: RegistryRuntime | None = None,
        now_factory: Callable[[], datetime] = utc_now,
        draft_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.runtime = runtime or RegistryRuntime(schema_registry=schema_registry)
        self.schema_registry = self.runtime.schema_registry
        self._now_factory = now_factory
        self._draft_id_factory = draft_id_factory or (lambda: str(uuid4()))
        self._drafts: dict[str, RegistryDraft] = {}
        self._draft_lock = asyncio.Lock()

    async def _repository_call(self, method_name: str, *args, **kwargs) -> Any:
        method = getattr(self.repository, method_name, None)
        if not callable(method):
            raise BackendUnavailableError(
                "registry repository operation is unavailable",
                details={"operation": method_name},
            )
        try:
            result = method(*args, **kwargs)
            return await result if inspect.isawaitable(result) else result
        except (
            PostgresUnavailableError,
            RegistryStoreError,
            ConnectionError,
            TimeoutError,
        ) as err:
            raise BackendUnavailableError(
                "PostgreSQL registry backend is unavailable",
                details={"operation": method_name},
            ) from err

    def _get_draft(self, draft_id: str, actor_id: str | None = None) -> RegistryDraft:
        draft = self._drafts.get(str(draft_id))
        if draft is None:
            raise DraftNotFoundError(
                f"registry draft not found: {draft_id}",
                details={"draft_id": str(draft_id)},
            )
        if draft.owner_id and actor_id and draft.owner_id != actor_id:
            raise PermissionDeniedError(
                "registry draft belongs to another administrator",
                details={"draft_id": draft.draft_id},
            )
        return draft

    @staticmethod
    def _assert_payload_profile(payload: RegistryPayload, profile: ProfileId) -> None:
        if payload.profile != profile:
            raise RegistryServiceError(
                "registry payload profile does not match the draft",
                code="validation_error",
                details={"profile": profile.value},
            )

    def _prepare_payload(
        self,
        payload: RegistryPayload | Mapping[str, Any],
    ) -> tuple[RegistryPayload, SignalGraph]:
        try:
            normalized = (
                payload
                if isinstance(payload, RegistryPayload)
                else RegistryPayload.from_dict(payload)
            )
            _assert_safe_json(
                normalized.consumer_overrides,
                path="consumer_overrides",
            )
            _assert_safe_json(
                normalized.registry_metadata,
                path="registry_metadata",
            )
            _assert_safe_json(
                normalized.contract_instances,
                path="contract_instances",
            )
            return self.runtime.prepare(normalized)
        except RegistryServiceError:
            raise
        except RegistryValidationError:
            raise
        except (KeyError, TypeError, ValueError) as err:
            raise RegistryValidationError(str(err)) from err

    async def async_read_active(
        self,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> RegistryLoadResult:
        profile_id = _profile_id(profile)
        result = await self._repository_call("load_active", profile_id)
        if not isinstance(result, RegistryLoadResult):
            raise BackendUnavailableError(
                "registry repository returned an invalid active result",
                details={"operation": "load_active"},
            )
        if result.revision is not None:
            try:
                _normalized, graph = self._prepare_payload(result.revision.payload)
                self.runtime.activate(result.revision, graph, source=result.source)
            except RegistryValidationError as err:
                raise DraftValidationError(
                    "active registry cannot be installed in runtime",
                    issues=(ValidationIssue("validation_error", str(err)),),
                ) from err
        return result

    async def get_active(
        self,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> RegistryLoadResult:
        return await self.async_read_active(profile)

    async def read_active(
        self,
        profile: ProfileId | str = ProfileId.BENNI,
    ) -> RegistryLoadResult:
        return await self.async_read_active(profile)

    async def async_open_draft(
        self,
        profile: ProfileId | str = ProfileId.BENNI,
        *,
        actor_id: str | None = None,
        expected_base_revision: int | None = None,
    ) -> RegistryDraft:
        profile_id = _profile_id(profile)
        active_result = await self.async_read_active(profile_id)
        active = active_result.revision
        if active is None:
            if active_result.reason != "no_active_revision":
                raise BackendUnavailableError(
                    "cannot create a draft without a readable registry base",
                    details={"reason": active_result.reason},
                )
            base_revision = 0
            base_revision_id = None
            payload = RegistryPayload(profile=profile_id)
        else:
            base_revision = active.revision
            base_revision_id = active.id
            payload = active.payload
        if (
            expected_base_revision is not None
            and (
                isinstance(expected_base_revision, bool)
                or not isinstance(expected_base_revision, int)
                or expected_base_revision < 0
            )
        ):
            raise RegistryServiceError(
                "expected_base_revision must be a non-negative integer",
                code="validation_error",
            )
        if (
            expected_base_revision is not None
            and expected_base_revision != base_revision
        ):
            raise ConcurrencyConflict(expected_base_revision, base_revision)
        now = self._now_factory()
        draft = RegistryDraft(
            draft_id=self._draft_id_factory(),
            profile=profile_id,
            base_revision=base_revision,
            base_revision_id=base_revision_id,
            payload=payload,
            created_at=now,
            updated_at=now,
            owner_id=str(actor_id) if actor_id is not None else None,
        )
        async with self._draft_lock:
            self._drafts[draft.draft_id] = draft
        return draft

    async def create_draft(
        self,
        profile: ProfileId | str = ProfileId.BENNI,
        *,
        actor_id: str | None = None,
        expected_base_revision: int | None = None,
    ) -> RegistryDraft:
        return await self.async_open_draft(
            profile,
            actor_id=actor_id,
            expected_base_revision=expected_base_revision,
        )

    async def open_draft(
        self,
        profile: ProfileId | str = ProfileId.BENNI,
        *,
        actor_id: str | None = None,
        expected_base_revision: int | None = None,
    ) -> RegistryDraft:
        return await self.async_open_draft(
            profile,
            actor_id=actor_id,
            expected_base_revision=expected_base_revision,
        )

    async def async_get_draft(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        async with self._draft_lock:
            return self._get_draft(draft_id, actor_id)

    async def get_draft(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_get_draft(draft_id, actor_id=actor_id)

    async def _replace_draft_payload(
        self,
        draft: RegistryDraft,
        payload: RegistryPayload,
        *,
        actor_id: str | None,
    ) -> RegistryDraft:
        self._assert_payload_profile(payload, draft.profile)
        async with self._draft_lock:
            current = self._get_draft(draft.draft_id, actor_id)
            updated = replace(
                current,
                payload=payload,
                updated_at=self._now_factory(),
            )
            self._drafts[updated.draft_id] = updated
            return updated

    async def async_replace_draft(
        self,
        draft_id: str,
        payload: RegistryPayload | Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        try:
            normalized = (
                payload
                if isinstance(payload, RegistryPayload)
                else RegistryPayload.from_dict(payload)
            )
            _assert_safe_json(normalized.consumer_overrides, path="consumer_overrides")
            _assert_safe_json(normalized.registry_metadata, path="registry_metadata")
            _assert_safe_json(normalized.contract_instances, path="contract_instances")
        except RegistryServiceError:
            raise
        except (KeyError, TypeError, ValueError) as err:
            raise RegistryServiceError(
                str(err),
                code="validation_error",
            ) from err
        return await self._replace_draft_payload(
            draft,
            normalized,
            actor_id=actor_id,
        )

    async def replace_draft(
        self,
        draft_id: str,
        payload: RegistryPayload | Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_replace_draft(draft_id, payload, actor_id=actor_id)

    async def async_validate_draft(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> ValidationReport:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        try:
            _normalized, graph = self._prepare_payload(draft.payload)
        except RegistrySecurityError as err:
            return ValidationReport(
                draft_id=draft.draft_id,
                profile=draft.profile,
                base_revision=draft.base_revision,
                valid=False,
                errors=(ValidationIssue(err.code, str(err), err.details.get("path")),),
            )
        except (RegistryValidationError, RegistryServiceError, ValueError) as err:
            issue = _validation_issue(err)
            return ValidationReport(
                draft_id=draft.draft_id,
                profile=draft.profile,
                base_revision=draft.base_revision,
                valid=False,
                errors=(issue,),
            )
        return ValidationReport(
            draft_id=draft.draft_id,
            profile=draft.profile,
            base_revision=draft.base_revision,
            valid=True,
            graph_probe_revision=graph.revision,
        )

    async def validate_draft(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> ValidationReport:
        return await self.async_validate_draft(draft_id, actor_id=actor_id)

    async def validate(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> ValidationReport:
        return await self.async_validate_draft(draft_id, actor_id=actor_id)

    @staticmethod
    def _binding_from_input(
        binding: SourceBinding | Mapping[str, Any],
        *,
        profile: ProfileId,
    ) -> SourceBinding:
        if isinstance(binding, SourceBinding):
            result = binding
        else:
            if not isinstance(binding, Mapping):
                raise RegistryServiceError(
                    "binding must be an object",
                    code="validation_error",
                    details={"field": "binding"},
                )
            data = dict(binding)
            if "binding_id" not in data:
                data["binding_id"] = f"binding.{uuid4().hex}"
            data.setdefault("profile_id", profile.value)
            try:
                result = SourceBinding.from_dict(data, default_profile=profile)
            except (KeyError, TypeError, ValueError) as err:
                raise RegistryServiceError(
                    str(err),
                    code="validation_error",
                    details={"field": "binding"},
                ) from err
        if result.profile_id != profile:
            raise RegistryServiceError(
                "binding belongs to another profile",
                code="validation_error",
                details={"binding_id": result.binding_id},
            )
        return result

    async def async_create_binding(
        self,
        draft_id: str,
        binding: SourceBinding | Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        new_binding = self._binding_from_input(binding, profile=draft.profile)
        if any(item.binding_id == new_binding.binding_id for item in draft.payload.bindings):
            raise InvalidReferenceError(
                "binding ID is already used in this draft",
                details={"binding_id": new_binding.binding_id},
            )
        payload = replace(
            draft.payload,
            bindings=draft.payload.bindings + (new_binding,),
        )
        return await self._replace_draft_payload(draft, payload, actor_id=actor_id)

    async def create_binding(
        self,
        draft_id: str,
        binding: SourceBinding | Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_create_binding(draft_id, binding, actor_id=actor_id)

    @staticmethod
    def _updated_binding(
        current: SourceBinding,
        changes: SourceBinding | Mapping[str, Any],
        *,
        profile: ProfileId,
    ) -> SourceBinding:
        if isinstance(changes, SourceBinding):
            if changes.binding_id != current.binding_id:
                raise InvalidReferenceError(
                    "binding_id is stable and cannot be changed",
                    details={"binding_id": current.binding_id},
                )
            result = changes
        else:
            if not isinstance(changes, Mapping):
                raise RegistryServiceError(
                    "binding changes must be an object",
                    code="validation_error",
                    details={"binding_id": current.binding_id},
                )
            data = current.as_dict()
            data.update(dict(changes))
            if "binding_id" in changes and str(changes["binding_id"]) != current.binding_id:
                raise InvalidReferenceError(
                    "binding_id is stable and cannot be changed",
                    details={"binding_id": current.binding_id},
                )
            try:
                result = SourceBinding.from_dict(data, default_profile=profile)
            except (KeyError, TypeError, ValueError) as err:
                raise RegistryServiceError(
                    str(err),
                    code="validation_error",
                    details={"binding_id": current.binding_id},
                ) from err
        if result.binding_id != current.binding_id:
            raise InvalidReferenceError("binding_id is stable and cannot be changed")
        if result.profile_id != profile:
            raise RegistryServiceError(
                "binding belongs to another profile",
                code="validation_error",
                details={"binding_id": current.binding_id},
            )
        return result

    async def async_update_binding(
        self,
        draft_id: str,
        binding_id: str,
        binding: SourceBinding | Mapping[str, Any] | None = None,
        *,
        changes: SourceBinding | Mapping[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        if binding is None:
            binding = changes
        if binding is None:
            raise RegistryServiceError(
                "binding changes are required",
                code="validation_error",
            )
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        current = next(
            (item for item in draft.payload.bindings if item.binding_id == binding_id),
            None,
        )
        if current is None:
            raise InvalidReferenceError(
                "binding does not exist in this draft",
                details={"binding_id": binding_id},
            )
        updated_binding = self._updated_binding(
            current,
            binding,
            profile=draft.profile,
        )
        payload = replace(
            draft.payload,
            bindings=tuple(
                updated_binding if item.binding_id == binding_id else item
                for item in draft.payload.bindings
            ),
        )
        return await self._replace_draft_payload(draft, payload, actor_id=actor_id)

    async def update_binding(
        self,
        draft_id: str,
        binding_id: str,
        binding: SourceBinding | Mapping[str, Any] | None = None,
        *,
        changes: SourceBinding | Mapping[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_update_binding(
            draft_id,
            binding_id,
            binding,
            changes=changes,
            actor_id=actor_id,
        )

    async def async_delete_binding(
        self,
        draft_id: str,
        binding_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        if not any(item.binding_id == binding_id for item in draft.payload.bindings):
            raise InvalidReferenceError(
                "binding does not exist in this draft",
                details={"binding_id": binding_id},
            )
        references = tuple(
            fusion.fusion_id
            for fusion in draft.payload.fusions
            if binding_id in fusion.input_binding_ids
        )
        if references:
            raise InvalidReferenceError(
                "binding is still referenced by a fusion",
                details={"binding_id": binding_id, "fusion_ids": list(references)},
            )
        payload = replace(
            draft.payload,
            bindings=tuple(
                item for item in draft.payload.bindings if item.binding_id != binding_id
            ),
        )
        return await self._replace_draft_payload(draft, payload, actor_id=actor_id)

    async def delete_binding(
        self,
        draft_id: str,
        binding_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_delete_binding(draft_id, binding_id, actor_id=actor_id)

    async def async_set_binding_enabled(
        self,
        draft_id: str,
        binding_id: str,
        enabled: bool,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        if not isinstance(enabled, bool):
            raise RegistryServiceError(
                "enabled must be a boolean",
                code="validation_error",
                details={"binding_id": binding_id},
            )
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        current = next(
            (item for item in draft.payload.bindings if item.binding_id == binding_id),
            None,
        )
        if current is None:
            raise InvalidReferenceError(
                "binding does not exist in this draft",
                details={"binding_id": binding_id},
            )
        return await self.async_update_binding(
            draft_id,
            binding_id,
            replace(current, enabled=enabled),
            actor_id=actor_id,
        )

    async def set_binding_enabled(
        self,
        draft_id: str,
        binding_id: str,
        enabled: bool,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_set_binding_enabled(
            draft_id,
            binding_id,
            enabled,
            actor_id=actor_id,
        )

    async def async_activate_binding(
        self,
        draft_id: str,
        binding_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_set_binding_enabled(
            draft_id,
            binding_id,
            True,
            actor_id=actor_id,
        )

    async def async_deactivate_binding(
        self,
        draft_id: str,
        binding_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_set_binding_enabled(
            draft_id,
            binding_id,
            False,
            actor_id=actor_id,
        )

    async def activate_binding(
        self,
        draft_id: str,
        binding_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_activate_binding(
            draft_id,
            binding_id,
            actor_id=actor_id,
        )

    async def deactivate_binding(
        self,
        draft_id: str,
        binding_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_deactivate_binding(
            draft_id,
            binding_id,
            actor_id=actor_id,
        )

    @staticmethod
    def _contract_instance_from_input(
        instance: Mapping[str, Any],
        *,
        profile: ProfileId,
        schema_registry: Any,
        existing: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(instance, Mapping):
            raise RegistryServiceError(
                "contract instance must be an object",
                code="validation_error",
            )
        data = dict(existing or {})
        data.update(dict(instance))
        if "contract_id" not in data:
            data["contract_id"] = f"contract.{uuid4().hex}"
        data["contract_id"] = str(data["contract_id"])
        if not data["contract_id"].strip():
            raise RegistryServiceError(
                "contract instance needs a non-empty contract_id",
                code="validation_error",
            )
        data.setdefault("profile", profile.value)
        if str(data.get("profile")) != profile.value:
            raise RegistryServiceError(
                "contract instance belongs to another profile",
                code="validation_error",
                details={"contract_id": data["contract_id"]},
            )
        schema_id = data.get("schema_id")
        if not isinstance(schema_id, str) or not schema_id:
            raise RegistryServiceError(
                "contract instance needs a schema_id",
                code="validation_error",
                details={"contract_id": data["contract_id"]},
            )
        try:
            schema_registry.get(
                schema_id,
                int(data["schema_version"])
                if data.get("schema_version") is not None
                else None,
            )
        except (KeyError, TypeError, ValueError) as err:
            raise InvalidReferenceError(
                "contract instance references an unknown schema",
                details={
                    "contract_id": data["contract_id"],
                    "schema_id": schema_id,
                },
            ) from err
        _assert_safe_json(data, path=f"contract_instances.{data['contract_id']}")
        return deepcopy(data)

    async def async_create_contract_instance(
        self,
        draft_id: str,
        instance: Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        new_instance = self._contract_instance_from_input(
            instance,
            profile=draft.profile,
            schema_registry=self.schema_registry,
        )
        contract_id = new_instance["contract_id"]
        if any(item.get("contract_id") == contract_id for item in draft.payload.contract_instances):
            raise InvalidReferenceError(
                "contract instance ID is already used in this draft",
                details={"contract_id": contract_id},
            )
        payload = replace(
            draft.payload,
            contract_instances=draft.payload.contract_instances + (new_instance,),
        )
        return await self._replace_draft_payload(draft, payload, actor_id=actor_id)

    async def create_contract_instance(
        self,
        draft_id: str,
        instance: Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_create_contract_instance(
            draft_id,
            instance,
            actor_id=actor_id,
        )

    async def async_update_contract_instance(
        self,
        draft_id: str,
        contract_id: str,
        instance: Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        current = next(
            (
                item
                for item in draft.payload.contract_instances
                if item.get("contract_id") == contract_id
            ),
            None,
        )
        if current is None:
            raise InvalidReferenceError(
                "contract instance does not exist in this draft",
                details={"contract_id": contract_id},
            )
        changes = dict(instance)
        if "contract_id" in changes and str(changes["contract_id"]) != contract_id:
            raise InvalidReferenceError(
                "contract_id is stable and cannot be changed",
                details={"contract_id": contract_id},
            )
        updated_instance = self._contract_instance_from_input(
            changes,
            profile=draft.profile,
            schema_registry=self.schema_registry,
            existing=current,
        )
        payload = replace(
            draft.payload,
            contract_instances=tuple(
                updated_instance
                if item.get("contract_id") == contract_id
                else item
                for item in draft.payload.contract_instances
            ),
        )
        return await self._replace_draft_payload(draft, payload, actor_id=actor_id)

    async def update_contract_instance(
        self,
        draft_id: str,
        contract_id: str,
        instance: Mapping[str, Any],
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_update_contract_instance(
            draft_id,
            contract_id,
            instance,
            actor_id=actor_id,
        )

    async def async_delete_contract_instance(
        self,
        draft_id: str,
        contract_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        if not any(
            item.get("contract_id") == contract_id
            for item in draft.payload.contract_instances
        ):
            raise InvalidReferenceError(
                "contract instance does not exist in this draft",
                details={"contract_id": contract_id},
            )
        references = tuple(
            fusion.fusion_id
            for fusion in draft.payload.fusions
            if fusion.contract_id == contract_id
        )
        if references:
            raise InvalidReferenceError(
                "contract instance is still referenced by a fusion",
                details={"contract_id": contract_id, "fusion_ids": list(references)},
            )
        payload = replace(
            draft.payload,
            contract_instances=tuple(
                item
                for item in draft.payload.contract_instances
                if item.get("contract_id") != contract_id
            ),
        )
        return await self._replace_draft_payload(draft, payload, actor_id=actor_id)

    async def delete_contract_instance(
        self,
        draft_id: str,
        contract_id: str,
        *,
        actor_id: str | None = None,
    ) -> RegistryDraft:
        return await self.async_delete_contract_instance(
            draft_id,
            contract_id,
            actor_id=actor_id,
        )

    async def async_save_draft(
        self,
        draft_id: str,
        expected_base_revision: int | None = None,
        *,
        actor_id: str | None = None,
    ) -> RegistryRevision:
        draft = await self.async_get_draft(draft_id, actor_id=actor_id)
        expected = (
            draft.base_revision
            if expected_base_revision is None
            else expected_base_revision
        )
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise RegistryServiceError(
                "expected_base_revision must be a non-negative integer",
                code="validation_error",
            )
        if expected != draft.base_revision:
            raise ConcurrencyConflict(expected, draft.base_revision)
        try:
            normalized, graph = self._prepare_payload(draft.payload)
        except RegistrySecurityError:
            raise
        except RegistryValidationError as err:
            raise DraftValidationError(
                "registry draft validation failed",
                issues=(_validation_issue(err),),
            ) from err

        candidate = await self._repository_call(
            "create_revision",
            normalized,
            profile=draft.profile,
            created_by=actor_id,
        )
        try:
            active = await self._repository_call(
                "activate_revision",
                candidate.id,
                expected_base_revision=expected,
            )
        except RevisionValidationFailed as err:
            raise DraftValidationError(
                "registry draft was rejected during activation",
                issues=(ValidationIssue("validation_error", err.reason),),
                details={"revision": err.revision},
            ) from err

        if not isinstance(active, RegistryRevision):
            raise BackendUnavailableError(
                "registry repository returned an invalid active revision",
                details={"operation": "activate_revision"},
            )
        try:
            self.runtime.activate(active, graph, source=RegistrySource.POSTGRESQL)
        except RegistryServiceError:
            raise
        except Exception as err:  # pragma: no cover - defensive runtime boundary
            raise RuntimeActivationError(
                "validated revision could not be installed in runtime",
                details={"revision": active.revision},
            ) from err
        async with self._draft_lock:
            current = self._drafts.get(draft.draft_id)
            if current == draft:
                self._drafts.pop(draft.draft_id, None)
        LOGGER.info(
            "registry revision activated profile=%s revision=%s",
            active.profile.value,
            active.revision,
        )
        return active

    async def save_draft(
        self,
        draft_id: str,
        expected_base_revision: int | None = None,
        *,
        actor_id: str | None = None,
    ) -> RegistryRevision:
        return await self.async_save_draft(
            draft_id,
            expected_base_revision=expected_base_revision,
            actor_id=actor_id,
        )

    async def async_discard_draft(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> bool:
        async with self._draft_lock:
            draft = self._get_draft(draft_id, actor_id)
            self._drafts.pop(draft.draft_id, None)
        return True

    async def discard_draft(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> bool:
        return await self.async_discard_draft(draft_id, actor_id=actor_id)

    async def discard(
        self,
        draft_id: str,
        *,
        actor_id: str | None = None,
    ) -> bool:
        return await self.async_discard_draft(draft_id, actor_id=actor_id)

    async def async_list_revisions(
        self,
        profile: ProfileId | str | None = None,
    ) -> tuple[RegistryRevision, ...]:
        selected = _profile_id(profile) if profile is not None else None
        result = await self._repository_call("list_revisions", selected)
        return tuple(result)

    async def list_revisions(
        self,
        profile: ProfileId | str | None = None,
    ) -> tuple[RegistryRevision, ...]:
        return await self.async_list_revisions(profile)

    async def async_rollback(
        self,
        profile: ProfileId | str,
        revision_id: str,
        *,
        expected_base_revision: int | None = None,
        actor_id: str | None = None,
    ) -> RegistryRevision:
        del actor_id  # retained for audit adapters; repository stores no secret
        profile_id = _profile_id(profile)
        target = await self._repository_call("get_revision", revision_id)
        if target is None:
            raise RevisionNotFound(f"registry revision not found: {revision_id}")
        if target.profile != profile_id:
            raise InvalidReferenceError(
                "rollback revision belongs to another profile",
                details={"revision_id": revision_id, "profile": profile_id.value},
            )
        try:
            _normalized, graph = self._prepare_payload(target.payload)
        except RegistryValidationError as err:
            raise DraftValidationError(
                "rollback target failed graph validation",
                issues=(_validation_issue(err),),
                details={"revision_id": revision_id},
            ) from err
        rolled_back = await self._repository_call(
            "rollback_revision",
            target.id,
            expected_base_revision=expected_base_revision,
        )
        self.runtime.activate(
            rolled_back,
            graph,
            source=RegistrySource.POSTGRESQL,
        )
        LOGGER.info(
            "registry revision rollback activated profile=%s revision=%s",
            rolled_back.profile.value,
            rolled_back.revision,
        )
        return rolled_back

    async def rollback(
        self,
        profile: ProfileId | str,
        revision_id: str,
        *,
        expected_base_revision: int | None = None,
        actor_id: str | None = None,
    ) -> RegistryRevision:
        return await self.async_rollback(
            profile,
            revision_id,
            expected_base_revision=expected_base_revision,
            actor_id=actor_id,
        )


# Descriptive aliases for callers that use the shorter naming convention.
RegistryService = RegistryDomainService
RegistryBackendService = RegistryDomainService
RegistryWriteService = RegistryDomainService
RegistryBackendError = BackendUnavailableError
RegistryDraftNotFound = DraftNotFoundError
RegistryInvalidReference = InvalidReferenceError
