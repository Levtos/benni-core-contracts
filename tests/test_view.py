from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from custom_components.benni_core_contracts.const import (
    DATA_VIEW_PANEL,
    DATA_VIEW_STATIC,
    DOMAIN,
    FRONTEND_DIR_URL,
    FRONTEND_ENTRY,
    PANEL_ELEMENT,
    PANEL_URL_PATH,
    RELEASE_VERSION,
)
from custom_components.benni_core_contracts.view import async_remove_view, async_setup_view


ROOT = Path(__file__).resolve().parents[1]


class ViewRegistrationTests(unittest.TestCase):
    def test_static_bundle_and_panel_registration_are_idempotent(self) -> None:
        registered_paths: list[object] = []
        registered_panels: list[dict[str, object]] = []
        removed_panels: list[str] = []

        class StaticPathConfig:
            def __init__(self, url_path: str, path: str, cache_headers: bool) -> None:
                self.url_path = url_path
                self.path = path
                self.cache_headers = cache_headers

        async def register_static_paths(paths: list[object]) -> None:
            registered_paths.extend(paths)

        def register_panel(_hass: object, **kwargs: object) -> None:
            registered_panels.append(kwargs)

        def remove_panel(_hass: object, panel_path: str) -> None:
            removed_panels.append(panel_path)

        frontend = types.ModuleType("homeassistant.components.frontend")
        frontend.async_register_built_in_panel = register_panel
        frontend.async_remove_panel = remove_panel
        http = types.ModuleType("homeassistant.components.http")
        http.StaticPathConfig = StaticPathConfig
        components = types.ModuleType("homeassistant.components")
        homeassistant = types.ModuleType("homeassistant")
        homeassistant.components = components
        components.frontend = frontend
        components.http = http
        hass = types.SimpleNamespace(
            data={},
            http=types.SimpleNamespace(async_register_static_paths=register_static_paths),
        )

        with patch.dict(
            sys.modules,
            {
                "homeassistant": homeassistant,
                "homeassistant.components": components,
                "homeassistant.components.frontend": frontend,
                "homeassistant.components.http": http,
            },
        ):
            asyncio.run(async_setup_view(hass))
            asyncio.run(async_setup_view(hass))
            async_remove_view(hass)

        self.assertEqual(len(registered_paths), 1)
        self.assertEqual(registered_paths[0].url_path, FRONTEND_DIR_URL)
        self.assertEqual(registered_paths[0].cache_headers, False)
        self.assertTrue(Path(registered_paths[0].path).is_dir())
        self.assertEqual(len(registered_panels), 1)
        self.assertEqual(registered_panels[0]["frontend_url_path"], PANEL_URL_PATH)
        self.assertEqual(registered_panels[0]["config"]["_panel_custom"]["name"], PANEL_ELEMENT)
        self.assertEqual(
            registered_panels[0]["config"]["_panel_custom"]["module_url"],
            f"{FRONTEND_ENTRY}?{RELEASE_VERSION}",
        )
        self.assertEqual(removed_panels, [PANEL_URL_PATH])
        self.assertFalse(hass.data[DOMAIN][DATA_VIEW_PANEL])
        self.assertTrue(hass.data[DOMAIN][DATA_VIEW_STATIC])


if __name__ == "__main__":
    unittest.main()
