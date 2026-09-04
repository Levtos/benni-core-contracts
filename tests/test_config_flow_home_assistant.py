from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.benni_core_contracts import config_flow
from custom_components.benni_core_contracts.const import (
    PILOT_OPENING_OPEN_SOURCE_ENTITY_ID,
    PILOT_OPENING_TILT_SOURCE_ENTITY_ID,
)


class _FakeRequired(str):
    def __new__(cls, key: str):
        value = super().__new__(cls, key)
        value.key = key  # type: ignore[attr-defined]
        return value


class _FakeSchema:
    def __init__(self, schema):
        self.schema = schema


class _FakeVoluptuous(types.ModuleType):
    Schema = _FakeSchema

    @staticmethod
    def Required(key: str):
        return _FakeRequired(key)

    @staticmethod
    def In(values):
        return values


class _FakeEntitySelectorConfig:
    def __init__(self, *, domain: str, include_entities):
        self.domain = domain
        self.include_entities = include_entities


class _FakeEntitySelector:
    def __init__(self, config):
        self.config = config


class _FakeConfigFlow:
    def __init__(self):
        self.unique_id = None

    def __init_subclass__(cls, **kwargs):
        kwargs.pop("domain", None)
        super().__init_subclass__(**kwargs)

    def async_show_form(self, *, step_id, data_schema):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id
        return None

    def _abort_if_unique_id_configured(self):
        return None


class _FakeOptionsFlow:
    def async_show_form(self, *, step_id, data_schema):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}


@contextmanager
def _home_assistant_imports():
    voluptuous = _FakeVoluptuous("voluptuous")
    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = _FakeConfigFlow
    config_entries.OptionsFlow = _FakeOptionsFlow
    helpers = types.ModuleType("homeassistant.helpers")
    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.EntitySelector = _FakeEntitySelector
    selector.EntitySelectorConfig = _FakeEntitySelectorConfig
    helpers.selector = selector
    homeassistant.config_entries = config_entries
    homeassistant.helpers = helpers

    fake_modules = {
        "voluptuous": voluptuous,
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.selector": selector,
    }
    with patch.dict(sys.modules, fake_modules):
        yield


def _selector_for(schema: _FakeSchema, field: str) -> _FakeEntitySelector:
    for key, value in schema.schema.items():
        if str(key) == field:
            return value
    raise AssertionError(f"selector field not found: {field}")


class HomeAssistantConfigFlowRegressionTests(unittest.TestCase):
    def test_shadow_bootstrap_is_profile_specific_and_accepts_both_profiles(self) -> None:
        try:
            with _home_assistant_imports():
                loaded = importlib.reload(config_flow)
                for profile in ("benni", "eltern"):
                    flow = loaded.BenniCoreContractsConfigFlow()
                    result = asyncio.run(
                        flow.async_step_user(
                            {"profile": profile, "mode": "shadow_only"}
                        )
                    )
                    self.assertEqual(flow.unique_id, f"benni_core_contracts:{profile}")
                    self.assertEqual(result["type"], "create_entry")
                    self.assertEqual(result["data"]["profile"], profile)
        finally:
            importlib.reload(config_flow)

    def test_published_options_transition_builds_home_assistant_selectors(self) -> None:
        try:
            with _home_assistant_imports():
                loaded = importlib.reload(config_flow)
                flow = loaded.BenniCoreContractsOptionsFlow(SimpleNamespace())
                result = asyncio.run(flow.async_step_init({"mode": "published"}))

                self.assertEqual(result["type"], "form")
                self.assertEqual(result["step_id"], "published")
                schema = result["data_schema"]
                self.assertIsInstance(schema, _FakeSchema)

                open_selector = _selector_for(schema, "opening_open_source")
                tilt_selector = _selector_for(schema, "opening_tilt_source")
                self.assertEqual(open_selector.config.domain, "binary_sensor")
                self.assertEqual(tilt_selector.config.domain, "binary_sensor")
                self.assertIsInstance(open_selector.config.include_entities, list)
                self.assertIsInstance(tilt_selector.config.include_entities, list)
                self.assertEqual(
                    open_selector.config.include_entities,
                    [PILOT_OPENING_OPEN_SOURCE_ENTITY_ID],
                )
                self.assertEqual(
                    tilt_selector.config.include_entities,
                    [PILOT_OPENING_TILT_SOURCE_ENTITY_ID],
                )
        finally:
            importlib.reload(config_flow)


if __name__ == "__main__":
    unittest.main()
