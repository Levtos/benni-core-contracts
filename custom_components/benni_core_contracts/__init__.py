"""Home Assistant adapter for the read-only Core Contracts graph."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN, MODE_PUBLISHED, MODE_SHADOW_ONLY, STORAGE_KEY_PREFIX
from .graph import SignalGraph
from .models import ConfigModel, ProfileId
from .profiles import profile_definition
from .shadow import PublishedRuntime, ShadowRuntime
from .storage import HomeAssistantStorage, StorageCodec
from .source_listener import async_attach_source_listeners
from .view import async_remove_view, async_setup_view
from .websocket_api import async_register_websocket_api


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


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
    graph = SignalGraph.from_config(config)
    storage = HomeAssistantStorage(hass, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}")
    stored_payload = await storage.async_load()
    if stored_payload:
        envelope = StorageCodec.decode(stored_payload)
        for stored_signal in envelope.signals:
            if graph.has_binding(stored_signal.binding_id):
                graph.restore_signal(stored_signal.binding_id, stored_signal.value)
    runtime = (
        PublishedRuntime(config, graph)
        if config.mode.value == MODE_PUBLISHED
        else ShadowRuntime(config, graph)
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await async_register_websocket_api(hass, runtime)
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
