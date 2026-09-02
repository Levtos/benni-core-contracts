"""Home Assistant adapter for the read-only Core Contracts graph."""

from __future__ import annotations

import asyncio
from typing import Any

from .const import (
    DOMAIN,
    MODE_PUBLISHED,
    MODE_SHADOW_ONLY,
    REGISTRY_RUNTIME_KEY,
    REGISTRY_SERVICE_KEY,
    STORAGE_KEY_PREFIX,
)
from .graph import SignalGraph
from .models import ConfigModel, ProfileId
from .profiles import profile_definition
from .registry_service import RegistryDomainService, RegistryRuntime
from .shadow import PublishedRuntime, ShadowRuntime
from .storage import HomeAssistantStorage, StorageCodec
from .source_listener import async_attach_source_listeners
from .view import async_remove_view, async_setup_view
from .websocket_api import (
    async_register_registry_write_api,
    async_register_websocket_api,
)


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    registry = hass.data.setdefault(DOMAIN, {})
    service = registry.get(REGISTRY_SERVICE_KEY)
    if service is not None:
        await async_register_registry_write_api(hass, service)
    return True


async def async_setup_registry_service(
    hass: Any,
    repository: Any,
    *,
    schema_registry: Any | None = None,
    runtime: RegistryRuntime | None = None,
) -> RegistryDomainService:
    """Install the repository-backed service and its admin write boundary.

    PostgreSQL connection construction and credential provisioning remain
    outside the ConfigEntry.  The caller supplies the already configured
    ``PostgresRegistryRepository``; migration remains the explicit repository
    operation from Issue #16.
    """

    registry = hass.data.setdefault(DOMAIN, {})
    service = RegistryDomainService(
        repository,
        schema_registry=schema_registry,
        runtime=runtime,
    )
    registry[REGISTRY_SERVICE_KEY] = service
    registry[REGISTRY_RUNTIME_KEY] = service.runtime
    await async_register_registry_write_api(hass, service)
    return service


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    config = ConfigModel.from_dict(entry.data, entry.options)
    if config.mode.value not in {MODE_SHADOW_ONLY, MODE_PUBLISHED}:
        return False
    if config.profile != ProfileId.BENNI:
        # Parent remains a shared fixture/profile only; it has no runtime
        # ConfigEntry activation path in the Benni-only release candidate.
        return False
    if not profile_definition(config.profile).shadow_runtime_allowed:
        # Parent remains a shared fixture/profile only; it has no runtime
        # ConfigEntry activation path in the Benni-only owner gate.
        return False
    registry = hass.data.setdefault(DOMAIN, {})
    service = registry.get(REGISTRY_SERVICE_KEY)
    graph = SignalGraph.from_config(config)
    if isinstance(service, RegistryDomainService):
        active_result = await service.async_read_active(config.profile)
        registry[REGISTRY_RUNTIME_KEY] = service.runtime
        registry_graph = service.runtime.graph(config.profile)
        if active_result.revision is not None and registry_graph is not None:
            graph = registry_graph
    storage = HomeAssistantStorage(hass, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}")
    stored_payload = await storage.async_load()
    if stored_payload:
        envelope = StorageCodec.decode(stored_payload)
        for stored_signal in envelope.signals:
            if (
                graph.has_binding(stored_signal.binding_id)
                and graph.binding(stored_signal.binding_id).enabled
            ):
                graph.restore_signal(stored_signal.binding_id, stored_signal.value)
    runtime = (
        PublishedRuntime(config, graph)
        if config.mode.value == MODE_PUBLISHED
        else ShadowRuntime(config, graph)
    )
    registry[entry.entry_id] = runtime
    if isinstance(service, RegistryDomainService):
        async def rebind_sources() -> None:
            runtime.unload()
            await async_attach_source_listeners(hass, runtime)
            refresh = getattr(runtime, "refresh_published_contracts", None)
            if refresh is not None:
                refresh()

        def on_registry_activation(snapshot: Any) -> None:
            runtime.graph = snapshot.graph
            create_task = getattr(hass, "async_create_task", None)
            if callable(create_task):
                create_task(rebind_sources())
            else:
                asyncio.create_task(rebind_sources())

        service.runtime.add_listener(on_registry_activation)
    await async_register_websocket_api(
        hass,
        runtime,
        registry_service=service if isinstance(service, RegistryDomainService) else None,
    )
    await async_attach_source_listeners(hass, runtime)
    if config.mode.value == MODE_PUBLISHED:
        runtime.refresh_published_contracts()
        config_entries = getattr(hass, "config_entries", None)
        if config_entries is None or not hasattr(
            config_entries,
            "async_forward_entry_setups",
        ):
            raise RuntimeError("Home Assistant ConfigEntry platform forwarding is unavailable")
        await config_entries.async_forward_entry_setups(entry, ["sensor"])
    await async_setup_view(hass)
    entry.async_on_unload(lambda: async_remove_view(hass))
    if isinstance(service, RegistryDomainService):
        entry.async_on_unload(
            lambda: service.runtime.remove_listener(on_registry_activation)
        )
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    runtimes = hass.data.get(DOMAIN, {})
    runtime = runtimes.pop(entry.entry_id, None)
    config = ConfigModel.from_dict(entry.data, entry.options)
    if config.mode.value == MODE_PUBLISHED:
        config_entries = getattr(hass, "config_entries", None)
        if config_entries is not None and hasattr(config_entries, "async_unload_platforms"):
            await config_entries.async_unload_platforms(entry, ["sensor"])
    if runtime is not None:
        runtime.unload()
    async_remove_view(hass)
    return True
