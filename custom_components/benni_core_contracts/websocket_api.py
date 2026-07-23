"""Read-only WebSocket API foundation for internal contracts and diagnostics."""

from __future__ import annotations

from typing import Any

from .const import (
    DOMAIN,
    WS_COMMANDS,
    WS_GET_CONTRACT,
    WS_GET_DIAGNOSTICS,
    WS_GET_GRAPH,
    WS_GET_HEALTH,
    WS_LIST_CONTRACTS,
    WS_REGISTERED,
    WEBSOCKET_PAYLOAD_VERSION,
)
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


async def async_register_websocket_api(hass: Any, runtime: ShadowRuntime) -> None:
    """Register read-only commands when the integration runs inside HA.

    The imports are lazy so the graph remains testable without Home Assistant.
    There is intentionally no command that mutates configuration or calls an
    HA service.
    """

    from homeassistant.components import websocket_api
    import voluptuous as vol

    registry = hass.data.setdefault(DOMAIN, {})
    if registry.get(WS_REGISTERED):
        return

    def register(command: str) -> None:
        schema = vol.Schema(
            {
                vol.Required("id"): int,
                vol.Required("type"): command,
                vol.Optional("contract_id"): str,
                vol.Optional("entry_id"): str,
                vol.Optional("since_revision"): int,
            }
        )

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
