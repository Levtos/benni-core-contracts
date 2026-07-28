"""Read-only Home Assistant panel for the Core Contracts UX."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .const import (
    DATA_VIEW_PANEL,
    DATA_VIEW_STATIC,
    DOMAIN,
    FRONTEND_DIR_URL,
    FRONTEND_ENTRY,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    RELEASE_VERSION,
)

_APP_DIR = Path(__file__).resolve().parent / "frontend" / "app"


def _cache_bust() -> str:
    """Use the release version without blocking the Home Assistant loop."""

    return RELEASE_VERSION


async def async_setup_view(hass: Any) -> None:
    """Serve and register the static SPA after the read-only entry is loaded."""

    from homeassistant.components.frontend import async_register_built_in_panel
    from homeassistant.components.http import StaticPathConfig

    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(DATA_VIEW_STATIC):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_DIR_URL, str(_APP_DIR), False)]
        )
        data[DATA_VIEW_STATIC] = True

    if data.get(DATA_VIEW_PANEL):
        return
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        require_admin=False,
        config={
            "_panel_custom": {
                "name": PANEL_ELEMENT,
                "module_url": f"{FRONTEND_ENTRY}?{_cache_bust()}",
            }
        },
    )
    data[DATA_VIEW_PANEL] = True


def async_remove_view(hass: Any) -> None:
    """Remove only the custom sidebar panel; no HA state is changed."""

    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(DATA_VIEW_PANEL):
        return
    try:
        from homeassistant.components.frontend import async_remove_panel

        async_remove_panel(hass, PANEL_URL_PATH)
    except (ImportError, RuntimeError):
        pass
    data[DATA_VIEW_PANEL] = False
