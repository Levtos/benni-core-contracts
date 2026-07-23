from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from custom_components.benni_core_contracts.contracts import default_schema_registry
from custom_components.benni_core_contracts.models import ConfigModel, RuntimeMode
from custom_components.benni_core_contracts.shadow import EntityAllowlist, EntityProjectionGate, ShadowRuntime
from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.websocket_api import (
    build_read_only_error,
    build_read_only_payload,
)
from custom_components.benni_core_contracts.const import (
    WS_GET_CONTRACT,
    WS_GET_DIAGNOSTICS,
    WS_GET_GRAPH,
    WS_GET_HEALTH,
    WS_LIST_CONTRACTS,
    WEBSOCKET_PAYLOAD_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "benni_core_contracts"


class ContractAndBoundaryTests(unittest.TestCase):
    def test_first_registry_is_explicitly_versioned(self) -> None:
        registry = default_schema_registry()
        self.assertEqual(
            [(schema.schema_id, schema.version) for schema in registry.all()],
            [
                ("opening", 1),
                ("room_climate", 1),
                ("technical_device", 1),
                ("weather_environment", 1),
            ],
        )

    def test_shadow_mode_never_projects_entities_even_with_allowlist(self) -> None:
        gate = EntityProjectionGate(
            RuntimeMode.SHADOW_ONLY,
            EntityAllowlist(frozenset({"sensor.allowed_contract"})),
        )
        self.assertEqual(gate.projectable(("sensor.allowed_contract",)), ())
        with self.assertRaises(ValueError):
            ConfigModel(
                mode=RuntimeMode.SHADOW_ONLY,
                entity_allowlist=("sensor.allowed_contract",),
            )

    def test_published_mode_is_not_available_in_shadow_release_candidate(self) -> None:
        with self.assertRaises(ValueError):
            ConfigModel.from_dict(
                {
                    "profile": "benni",
                    "mode": "published",
                }
            )

    def test_websocket_foundation_is_read_only(self) -> None:
        runtime = ShadowRuntime(
            ConfigModel(mode=RuntimeMode.SHADOW_ONLY),
            SignalGraph(),
        )
        payload = build_read_only_payload(runtime, WS_LIST_CONTRACTS)
        self.assertEqual(payload["payload_version"], WEBSOCKET_PAYLOAD_VERSION)
        self.assertEqual(payload["command"], WS_LIST_CONTRACTS)
        self.assertEqual(payload["contracts"], [])
        self.assertTrue(payload["delta"]["supported"])
        self.assertTrue(payload["delta"]["unchanged"] is False)
        self.assertEqual(
            build_read_only_payload(runtime, WS_LIST_CONTRACTS, since_revision=runtime.graph.revision)["delta"]["unchanged"],
            True,
        )
        with self.assertRaises(ValueError):
            build_read_only_payload(runtime, "benni_core_contracts/actuate")
        self.assertEqual(
            build_read_only_error(WS_LIST_CONTRACTS, "invalid_command", "nope")["error"]["code"],
            "invalid_command",
        )

    def test_websocket_commands_remain_separate_and_versioned(self) -> None:
        runtime = ShadowRuntime(
            ConfigModel(mode=RuntimeMode.SHADOW_ONLY),
            SignalGraph(),
        )
        for command in (
            WS_LIST_CONTRACTS,
            WS_GET_CONTRACT,
            WS_GET_DIAGNOSTICS,
            WS_GET_GRAPH,
            WS_GET_HEALTH,
        ):
            if command == WS_GET_CONTRACT:
                with self.assertRaises(ValueError):
                    build_read_only_payload(runtime, command)
                continue
            payload = build_read_only_payload(runtime, command)
            self.assertEqual(payload["payload_version"], 1)
            self.assertEqual(payload["command"], command)
            self.assertIn("revision", payload)

    def test_websocket_registration_uses_home_assistant_mapping_schema(self) -> None:
        """The HA decorator must receive a mapping, not vol.Schema."""

        from custom_components.benni_core_contracts.websocket_api import (
            async_register_websocket_api,
        )

        registered_schemas = []
        registered_handlers = []

        websocket_api = types.ModuleType("homeassistant.components.websocket_api")

        def websocket_command(schema):
            self.assertIsInstance(schema, dict)
            self.assertIn("type", schema)
            registered_schemas.append(schema)

            def decorate(handler):
                return handler

            return decorate

        def async_response(handler):
            return handler

        def async_register_command(_hass, handler):
            registered_handlers.append(handler)

        websocket_api.websocket_command = websocket_command
        websocket_api.async_response = async_response
        websocket_api.async_register_command = async_register_command

        homeassistant = types.ModuleType("homeassistant")
        components = types.ModuleType("homeassistant.components")
        components.websocket_api = websocket_api
        homeassistant.components = components

        runtime = ShadowRuntime(
            ConfigModel(mode=RuntimeMode.SHADOW_ONLY),
            SignalGraph(),
        )
        hass = types.SimpleNamespace(data={})
        with patch.dict(
            sys.modules,
            {
                "homeassistant": homeassistant,
                "homeassistant.components": components,
                "homeassistant.components.websocket_api": websocket_api,
            },
        ):
            asyncio.run(async_register_websocket_api(hass, runtime))

        self.assertEqual(
            [schema["type"] for schema in registered_schemas],
            [
                WS_LIST_CONTRACTS,
                WS_GET_CONTRACT,
                WS_GET_DIAGNOSTICS,
                WS_GET_GRAPH,
                WS_GET_HEALTH,
            ],
        )
        self.assertEqual(len(registered_handlers), 5)

    def test_no_entity_platform_or_actuator_surface_exists_in_first_slice(self) -> None:
        self.assertFalse((PACKAGE / "sensor.py").exists())
        self.assertFalse((PACKAGE / "binary_sensor.py").exists())
        forbidden = ("async_add_entities", "async_call", "call_service")
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, source, f"forbidden surface {token} in {path.name}")
        manifest = (PACKAGE / "manifest.json").read_text(encoding="utf-8")
        self.assertNotIn('"sensor"', manifest)
        self.assertNotIn('"binary_sensor"', manifest)

    def test_contract_metadata_is_explicit_and_contains_no_policy_targets(self) -> None:
        policy_names = {
            "heating_profile",
            "window_blockade",
            "blind_target_position",
            "privacy",
            "heat",
            "volume",
            "plug_protection",
            "notification_routing",
        }
        for schema in default_schema_registry().all():
            for field in schema.fields:
                self.assertTrue(field.value_type.value)
                self.assertIsInstance(field.required, bool)
                self.assertGreater(field.freshness_ttl_seconds, 0)
                self.assertTrue(field.fallback.action.value)
                self.assertTrue(field.safety_class.value)
                metadata = field.as_dict()
                for key in (
                    "value_type",
                    "unit",
                    "required",
                    "unknown_allowed",
                    "unavailable_allowed",
                    "freshness_requirement",
                    "freshness_ttl_seconds",
                    "safety_class",
                    "fallback",
                    "physical_state",
                ):
                    self.assertIn(key, metadata)
                self.assertNotIn(field.name, policy_names)
                if field.fallback.action.value == "safe_default":
                    self.assertTrue(field.safe_default_allowed)
                    self.assertTrue(field.safe_default_note)

    def test_new_package_does_not_reference_historical_core_devices_models(self) -> None:
        forbidden = ("benni_core_devices", "combined.py", "master.py", "DeviceConfigV2")
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, source, f"historical model reference {token} in {path.name}")
