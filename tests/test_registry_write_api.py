from __future__ import annotations

import asyncio
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from custom_components.benni_core_contracts.const import (
    DOMAIN,
    REGISTRY_SERVICE_KEY,
    WS_REGISTRY_BINDING_CREATE,
    WS_REGISTRY_DRAFT_CREATE,
    WS_REGISTRY_DRAFT_SAVE,
    WS_REGISTRY_DRAFT_VALIDATE,
    WS_WRITE_REGISTERED,
)
from custom_components.benni_core_contracts.registry import (
    ConcurrencyConflict,
    RevisionNotFound,
)
from custom_components.benni_core_contracts.registry_service import (
    BackendUnavailableError,
    RegistryDomainService,
)
from custom_components.benni_core_contracts.registry_store import (
    InMemoryLastKnownGoodCache,
    PostgresRegistryRepository,
)
from custom_components.benni_core_contracts.websocket_api import (
    async_register_registry_write_api,
    build_registry_write_error,
)
from tests.test_registry_store import _PostgresFake


UTC = timezone.utc


@dataclass
class FakeUser:
    id: str
    is_admin: bool


class FakeConnection:
    def __init__(self, user: FakeUser) -> None:
        self.user = user
        self.results: list[tuple[int, dict]] = []
        self.errors: list[tuple] = []

    def send_result(self, request_id: int, payload: dict) -> None:
        self.results.append((request_id, payload))

    def send_error(self, *args) -> None:
        self.errors.append(args)


def binding_data() -> dict:
    return {
        "binding_id": "living_temperature",
        "source_id": "source.living_temperature",
        "entity_id": "sensor.living_temperature",
        "field": "temperature",
        "capability": "room_climate",
    }


class RegistryWriteApiTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 9, 2, 20, 0, tzinfo=UTC)
        database = _PostgresFake()
        self.database = database
        self.service = RegistryDomainService(
            PostgresRegistryRepository(
                database,
                lkg_cache=InMemoryLastKnownGoodCache(),
                now_factory=lambda: now,
            ),
            now_factory=lambda: now,
        )
        self.handlers = {}
        websocket_api = types.ModuleType("homeassistant.components.websocket_api")
        voluptuous = types.ModuleType("voluptuous")
        voluptuous.Required = lambda key: key
        voluptuous.Optional = lambda key: key

        def websocket_command(schema):
            def decorate(handler):
                self.handlers[schema["type"]] = handler
                return handler

            return decorate

        websocket_api.websocket_command = websocket_command
        websocket_api.async_response = lambda handler: handler
        websocket_api.async_register_command = lambda _hass, _handler: None
        homeassistant = types.ModuleType("homeassistant")
        components = types.ModuleType("homeassistant.components")
        components.websocket_api = websocket_api
        homeassistant.components = components
        self.modules = {
            "homeassistant": homeassistant,
            "homeassistant.components": components,
            "homeassistant.components.websocket_api": websocket_api,
            "voluptuous": voluptuous,
        }

    def register(self):
        hass = types.SimpleNamespace(
            data={DOMAIN: {REGISTRY_SERVICE_KEY: self.service}}
        )
        with patch.dict(sys.modules, self.modules):
            asyncio.run(async_register_registry_write_api(hass, self.service))
        self.assertTrue(hass.data[DOMAIN][WS_WRITE_REGISTERED])
        return hass

    def test_write_registration_is_separate_and_admin_protected(self) -> None:
        self.register()
        self.assertIn(WS_REGISTRY_DRAFT_CREATE, self.handlers)

        connection = FakeConnection(FakeUser("viewer", False))
        asyncio.run(
            self.handlers[WS_REGISTRY_DRAFT_CREATE](
                None,
                connection,
                {"id": 1, "type": WS_REGISTRY_DRAFT_CREATE},
            )
        )

        self.assertEqual(self.database.rows, {})
        self.assertEqual(connection.results, [])
        self.assertEqual(connection.errors[0][1], "permission_denied")

    def test_admin_can_use_draft_validate_and_explicit_save_commands(self) -> None:
        hass = self.register()
        connection = FakeConnection(FakeUser("admin", True))
        asyncio.run(
            self.handlers[WS_REGISTRY_DRAFT_CREATE](
                hass,
                connection,
                {"id": 1, "type": WS_REGISTRY_DRAFT_CREATE},
            )
        )
        draft = connection.results[-1][1]["draft"]
        draft_id = draft["draft_id"]

        asyncio.run(
            self.handlers[WS_REGISTRY_BINDING_CREATE](
                hass,
                connection,
                {
                    "id": 2,
                    "type": WS_REGISTRY_BINDING_CREATE,
                    "draft_id": draft_id,
                    "binding": binding_data(),
                },
            )
        )
        asyncio.run(
            self.handlers[WS_REGISTRY_DRAFT_VALIDATE](
                hass,
                connection,
                {
                    "id": 3,
                    "type": WS_REGISTRY_DRAFT_VALIDATE,
                    "draft_id": draft_id,
                },
            )
        )
        self.assertTrue(connection.results[-1][1]["validation"]["valid"])
        self.assertEqual(self.database.rows, {})

        asyncio.run(
            self.handlers[WS_REGISTRY_DRAFT_SAVE](
                hass,
                connection,
                {
                    "id": 4,
                    "type": WS_REGISTRY_DRAFT_SAVE,
                    "draft_id": draft_id,
                    "expected_base_revision": 0,
                },
            )
        )
        self.assertEqual(connection.results[-1][1]["revision"]["status"], "active")
        self.assertEqual(len(self.database.rows), 1)

    def test_structured_errors_do_not_expose_backend_or_revision_internals(self) -> None:
        conflict = build_registry_write_error(
            WS_REGISTRY_DRAFT_SAVE,
            ConcurrencyConflict(42, 43),
            request_id=9,
        )
        self.assertEqual(conflict["error"]["code"], "revision_conflict")
        self.assertEqual(conflict["error"]["details"]["expected_base_revision"], 42)
        self.assertEqual(conflict["error"]["details"]["actual_base_revision"], 43)

        backend = build_registry_write_error(
            WS_REGISTRY_DRAFT_SAVE,
            BackendUnavailableError("secret postgres DSN must not escape"),
        )
        self.assertEqual(backend["error"]["code"], "backend_unavailable")
        self.assertEqual(backend["error"]["message"], "registry backend is unavailable")
        self.assertNotIn("DSN", str(backend))

        missing = build_registry_write_error(
            WS_REGISTRY_DRAFT_SAVE,
            RevisionNotFound("internal row identifier"),
        )
        self.assertEqual(missing["error"]["code"], "revision_not_found")
        self.assertNotIn("internal row", missing["error"]["message"])


if __name__ == "__main__":
    unittest.main()
