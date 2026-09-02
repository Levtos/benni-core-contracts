"""Read-only WebSocket API foundation for internal contracts and diagnostics."""

from __future__ import annotations

from typing import Any

from .const import (
    DOMAIN,
    REGISTRY_SERVICE_KEY,
    WS_COMMANDS,
    WS_GET_CONTRACT,
    WS_GET_DIAGNOSTICS,
    WS_GET_GRAPH,
    WS_GET_HEALTH,
    WS_LIST_CONTRACTS,
    WS_REGISTERED,
    WS_REGISTRY_BINDING_CREATE,
    WS_REGISTRY_BINDING_DELETE,
    WS_REGISTRY_BINDING_SET_ENABLED,
    WS_REGISTRY_BINDING_UPDATE,
    WS_REGISTRY_CONTRACT_INSTANCE_CREATE,
    WS_REGISTRY_CONTRACT_INSTANCE_DELETE,
    WS_REGISTRY_CONTRACT_INSTANCE_UPDATE,
    WS_REGISTRY_DRAFT_CREATE,
    WS_REGISTRY_DRAFT_DISCARD,
    WS_REGISTRY_DRAFT_GET,
    WS_REGISTRY_DRAFT_SAVE,
    WS_REGISTRY_DRAFT_VALIDATE,
    WS_REGISTRY_GET_ACTIVE,
    WS_REGISTRY_LIST_REVISIONS,
    WS_REGISTRY_ROLLBACK,
    WS_WRITE_REGISTERED,
    WEBSOCKET_PAYLOAD_VERSION,
)
from .registry import (
    ConcurrencyConflict,
    RegistryLoadResult,
    RegistryRevision,
    RegistryValidationError,
    RevisionNotFound,
    RevisionStateError,
    RevisionValidationFailed,
)
from .registry_service import (
    BackendUnavailableError,
    DraftNotFoundError,
    DraftValidationError,
    InvalidReferenceError,
    PermissionDeniedError,
    RegistryDraft,
    RegistryDomainService,
    RegistryServiceError,
    ValidationReport,
    public_load_result_dict,
    public_revision_dict,
)
from .registry_store import PostgresUnavailableError
from .shadow import ShadowRuntime


def build_read_only_payload(
    runtime: ShadowRuntime,
    command: str,
    contract_id: str | None = None,
    *,
    since_revision: int | None = None,
) -> dict[str, Any]:
    """Pure command dispatcher used by tests and the HA adapter."""

    if command not in WS_COMMANDS:
        raise ValueError(f"unsupported WebSocket command: {command}")
    return runtime.websocket_payload(
        command,
        contract_id,
        since_revision=since_revision,
    )


def build_read_only_error(
    command: str,
    code: str,
    message: str,
    *,
    request_id: int | None = None,
) -> dict[str, Any]:
    """Return the stable application-level error shape for pure clients."""

    payload: dict[str, Any] = {
        "payload_version": WEBSOCKET_PAYLOAD_VERSION,
        "command": command,
        "error": {"code": code, "message": message},
    }
    if request_id is not None:
        payload["id"] = request_id
    return payload


async def async_register_websocket_api(
    hass: Any,
    runtime: ShadowRuntime,
    *,
    registry_service: RegistryDomainService | None = None,
) -> None:
    """Register read-only commands when the integration runs inside HA.

    The imports are lazy so the graph remains testable without Home Assistant.
    This function registers only the existing read-only command family; the
    optional registry write family is registered separately below.
    """

    from homeassistant.components import websocket_api
    import voluptuous as vol

    registry = hass.data.setdefault(DOMAIN, {})
    if registry.get(WS_REGISTERED):
        if registry_service is not None:
            await async_register_registry_write_api(hass, registry_service)
        return

    def register(command: str) -> None:
        # Home Assistant's websocket_command decorator accepts a raw
        # voluptuous mapping (or vol.All with a mapping as its first
        # validator). A vol.Schema instance is not accepted by current HA:
        # the decorator reads the command from ``schema.validators[0]``.
        schema = {
            vol.Required("id"): int,
            vol.Required("type"): command,
            vol.Optional("contract_id"): str,
            vol.Optional("entry_id"): str,
            vol.Optional("since_revision"): int,
        }

        @websocket_api.websocket_command(schema)
        @websocket_api.async_response
        async def handle(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
            try:
                selected_runtime = registry.get(msg.get("entry_id"))
                if not isinstance(selected_runtime, ShadowRuntime):
                    selected_runtime = next(
                        (
                            value
                            for key, value in registry.items()
                            if key != WS_REGISTERED and isinstance(value, ShadowRuntime)
                        ),
                        None,
                    )
                if selected_runtime is None:
                    raise KeyError("no active core-contracts runtime")
                payload = build_read_only_payload(
                    selected_runtime,
                    command,
                    msg.get("contract_id"),
                    since_revision=msg.get("since_revision"),
                )
            except KeyError as err:
                connection.send_error(msg["id"], "not_found", str(err))
                return
            except ValueError as err:
                connection.send_error(msg["id"], "invalid_command", str(err))
                return
            connection.send_result(msg["id"], payload)

        websocket_api.async_register_command(hass, handle)

    for command in (
        WS_LIST_CONTRACTS,
        WS_GET_CONTRACT,
        WS_GET_DIAGNOSTICS,
        WS_GET_GRAPH,
        WS_GET_HEALTH,
    ):
        register(command)
    registry[WS_REGISTERED] = True
    if registry_service is not None:
        await async_register_registry_write_api(hass, registry_service)


def _is_admin(connection: Any) -> bool:
    user = getattr(connection, "user", None)
    return user is not None and getattr(user, "is_admin", False) is True


def _actor_id(connection: Any) -> str:
    user = getattr(connection, "user", None)
    value = getattr(user, "id", None) or getattr(user, "name", None)
    return str(value) if value is not None else "ha_admin"


def build_registry_write_error(
    command: str,
    error: Exception,
    *,
    request_id: int | None = None,
) -> dict[str, Any]:
    """Build a stable structured error without exposing backend details."""

    if isinstance(error, PermissionDeniedError):
        code = error.code
        message = "administrator permission is required"
    elif isinstance(error, ConcurrencyConflict):
        code = "revision_conflict"
        message = "registry base revision has changed"
    elif isinstance(error, (DraftValidationError, RegistryValidationError, RevisionValidationFailed)):
        code = "validation_error"
        message = "registry validation failed"
    elif isinstance(error, InvalidReferenceError):
        code = error.code
        message = str(error)
    elif isinstance(error, DraftNotFoundError):
        code = error.code
        message = "registry draft was not found"
    elif isinstance(error, RevisionNotFound):
        code = "revision_not_found"
        message = "registry revision was not found"
    elif isinstance(error, (BackendUnavailableError, PostgresUnavailableError)):
        code = error.code
        message = "registry backend is unavailable"
    elif isinstance(error, RevisionStateError):
        code = "revision_state_error"
        message = "registry revision cannot be used for this operation"
    elif isinstance(error, RegistryServiceError):
        code = error.code
        message = str(error)
    else:
        code = "registry_error"
        message = "registry operation failed"

    details = dict(getattr(error, "details", {}) or {})
    if isinstance(error, ConcurrencyConflict):
        details.update(
            {
                "expected_base_revision": error.expected_base_revision,
                "actual_base_revision": error.actual_base_revision,
            }
        )
    if isinstance(error, RevisionValidationFailed):
        details.update({"revision": error.revision, "reason": error.reason})
    if isinstance(error, DraftValidationError) and error.issues:
        details["issues"] = [issue.as_dict() for issue in error.issues]
    payload = {
        "payload_version": WEBSOCKET_PAYLOAD_VERSION,
        "command": command,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }
    if request_id is not None:
        payload["id"] = request_id
    return payload


def _send_registry_error(connection: Any, request_id: int, command: str, error: Exception) -> None:
    payload = build_registry_write_error(command, error, request_id=request_id)
    error_data = payload["error"]
    try:
        connection.send_error(
            request_id,
            error_data["code"],
            error_data["message"],
            error_data["details"],
        )
    except TypeError:  # Lightweight test doubles may implement the old 3-arg form.
        connection.send_error(request_id, error_data["code"], error_data["message"])


def _registry_write_result(command: str, result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "payload_version": WEBSOCKET_PAYLOAD_VERSION,
        "command": command,
    }
    if isinstance(result, RegistryLoadResult):
        payload["registry"] = public_load_result_dict(result)
    elif isinstance(result, RegistryDraft):
        payload["draft"] = result.as_dict()
    elif isinstance(result, ValidationReport):
        payload["validation"] = result.as_dict()
    elif isinstance(result, RegistryRevision):
        payload["revision"] = public_revision_dict(result)
    elif isinstance(result, tuple):
        payload["revisions"] = [public_revision_dict(item) for item in result]
    elif isinstance(result, bool):
        payload["discarded"] = result
    else:
        payload["result"] = result
    return payload


async def async_dispatch_registry_write(
    service: RegistryDomainService,
    command: str,
    msg: dict[str, Any],
    *,
    actor_id: str,
) -> Any:
    """Dispatch one explicit command; all calls are draft or revision actions."""

    profile = msg.get("profile", "benni")
    draft_id = msg.get("draft_id")
    if command == WS_REGISTRY_GET_ACTIVE:
        return await service.async_read_active(profile)
    if command == WS_REGISTRY_LIST_REVISIONS:
        return await service.async_list_revisions(profile)
    if command == WS_REGISTRY_DRAFT_CREATE:
        return await service.async_open_draft(
            profile,
            actor_id=actor_id,
            expected_base_revision=msg.get("expected_base_revision"),
        )
    if command == WS_REGISTRY_DRAFT_GET:
        return await service.async_get_draft(draft_id, actor_id=actor_id)
    if command == WS_REGISTRY_DRAFT_VALIDATE:
        return await service.async_validate_draft(draft_id, actor_id=actor_id)
    if command == WS_REGISTRY_DRAFT_SAVE:
        return await service.async_save_draft(
            draft_id,
            expected_base_revision=msg.get("expected_base_revision"),
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_DRAFT_DISCARD:
        return await service.async_discard_draft(draft_id, actor_id=actor_id)
    if command == WS_REGISTRY_ROLLBACK:
        return await service.async_rollback(
            profile,
            msg["revision_id"],
            expected_base_revision=msg.get("expected_base_revision"),
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_BINDING_CREATE:
        return await service.async_create_binding(
            draft_id,
            msg["binding"],
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_BINDING_UPDATE:
        return await service.async_update_binding(
            draft_id,
            msg["binding_id"],
            msg["binding"],
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_BINDING_DELETE:
        return await service.async_delete_binding(
            draft_id,
            msg["binding_id"],
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_BINDING_SET_ENABLED:
        return await service.async_set_binding_enabled(
            draft_id,
            msg["binding_id"],
            msg["enabled"],
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_CONTRACT_INSTANCE_CREATE:
        return await service.async_create_contract_instance(
            draft_id,
            msg["instance"],
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_CONTRACT_INSTANCE_UPDATE:
        return await service.async_update_contract_instance(
            draft_id,
            msg["contract_id"],
            msg["instance"],
            actor_id=actor_id,
        )
    if command == WS_REGISTRY_CONTRACT_INSTANCE_DELETE:
        return await service.async_delete_contract_instance(
            draft_id,
            msg["contract_id"],
            actor_id=actor_id,
        )
    raise RegistryServiceError(
        "unsupported registry write command",
        code="invalid_command",
        details={"command": command},
    )


async def async_register_registry_write_api(
    hass: Any,
    service: RegistryDomainService | None = None,
) -> None:
    """Register the admin-only registry write command family.

    Registration is opt-in through a configured service so the legacy
    read-only command registration remains byte-for-byte compatible for
    installations that have not configured a PostgreSQL backend yet.
    """

    from homeassistant.components import websocket_api
    import voluptuous as vol

    registry = hass.data.setdefault(DOMAIN, {})
    selected_service = service or registry.get(REGISTRY_SERVICE_KEY)
    if selected_service is None:
        return
    registry.setdefault(REGISTRY_SERVICE_KEY, selected_service)
    if registry.get(WS_WRITE_REGISTERED):
        return

    field_schemas: dict[str, dict[str, Any]] = {
        WS_REGISTRY_GET_ACTIVE: {vol.Optional("profile"): str},
        WS_REGISTRY_LIST_REVISIONS: {vol.Optional("profile"): str},
        WS_REGISTRY_DRAFT_CREATE: {
            vol.Optional("profile"): str,
            vol.Optional("expected_base_revision"): int,
        },
        WS_REGISTRY_DRAFT_GET: {vol.Required("draft_id"): str},
        WS_REGISTRY_DRAFT_VALIDATE: {vol.Required("draft_id"): str},
        WS_REGISTRY_DRAFT_SAVE: {
            vol.Required("draft_id"): str,
            vol.Optional("expected_base_revision"): int,
        },
        WS_REGISTRY_DRAFT_DISCARD: {vol.Required("draft_id"): str},
        WS_REGISTRY_ROLLBACK: {
            vol.Required("revision_id"): str,
            vol.Required("profile"): str,
            vol.Optional("expected_base_revision"): int,
        },
        WS_REGISTRY_BINDING_CREATE: {
            vol.Required("draft_id"): str,
            vol.Required("binding"): dict,
        },
        WS_REGISTRY_BINDING_UPDATE: {
            vol.Required("draft_id"): str,
            vol.Required("binding_id"): str,
            vol.Required("binding"): dict,
        },
        WS_REGISTRY_BINDING_DELETE: {
            vol.Required("draft_id"): str,
            vol.Required("binding_id"): str,
        },
        WS_REGISTRY_BINDING_SET_ENABLED: {
            vol.Required("draft_id"): str,
            vol.Required("binding_id"): str,
            vol.Required("enabled"): bool,
        },
        WS_REGISTRY_CONTRACT_INSTANCE_CREATE: {
            vol.Required("draft_id"): str,
            vol.Required("instance"): dict,
        },
        WS_REGISTRY_CONTRACT_INSTANCE_UPDATE: {
            vol.Required("draft_id"): str,
            vol.Required("contract_id"): str,
            vol.Required("instance"): dict,
        },
        WS_REGISTRY_CONTRACT_INSTANCE_DELETE: {
            vol.Required("draft_id"): str,
            vol.Required("contract_id"): str,
        },
    }

    for command, fields in field_schemas.items():
        schema = {
            vol.Required("id"): int,
            vol.Required("type"): command,
        }
        schema.update(fields)

        @websocket_api.websocket_command(schema)
        @websocket_api.async_response
        async def handle(
            hass: Any,
            connection: Any,
            msg: dict[str, Any],
            *,
            _command: str = command,
        ) -> None:
            request_id = msg["id"]
            if not _is_admin(connection):
                _send_registry_error(
                    connection,
                    request_id,
                    _command,
                    PermissionDeniedError("administrator permission is required"),
                )
                return
            selected = hass.data.setdefault(DOMAIN, {}).get(REGISTRY_SERVICE_KEY)
            if selected is None:
                _send_registry_error(
                    connection,
                    request_id,
                    _command,
                    BackendUnavailableError("registry service is not configured"),
                )
                return
            try:
                result = await async_dispatch_registry_write(
                    selected,
                    _command,
                    msg,
                    actor_id=_actor_id(connection),
                )
            except Exception as err:
                _send_registry_error(connection, request_id, _command, err)
                return
            connection.send_result(request_id, _registry_write_result(_command, result))

        websocket_api.async_register_command(hass, handle)
    registry[WS_WRITE_REGISTERED] = True
