from __future__ import annotations

import asyncio
import sys
import types
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    Fusion,
    ProfileId,
    RuntimeMode,
    SourceBinding,
)
from custom_components.benni_core_contracts.quality import FreshnessStatus
from custom_components.benni_core_contracts.registry import (
    ConcurrencyConflict,
    RegistryPayload,
    RevisionNotFound,
    RevisionStatus,
)
from custom_components.benni_core_contracts.registry_service import (
    BackendUnavailableError,
    DraftNotFoundError,
    DraftValidationError,
    InvalidReferenceError,
    RegistryDomainService,
)
from custom_components.benni_core_contracts.registry_store import (
    InMemoryLastKnownGoodCache,
    PostgresRegistryRepository,
)
from custom_components.benni_core_contracts.shadow import ShadowRuntime
from tests.test_registry_store import _PostgresFake


UTC = timezone.utc


def binding_data(
    binding_id: str = "living_temperature",
    *,
    entity_id: str = "sensor.living_temperature",
) -> dict:
    return {
        "binding_id": binding_id,
        "source_id": f"source.{binding_id}",
        "entity_id": entity_id,
        "field": "temperature",
        "capability": "room_climate",
        "display_name": "Living temperature",
    }


class RegistryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 2, 20, 0, tzinfo=UTC)
        self.database = _PostgresFake()
        self.store = PostgresRegistryRepository(
            self.database,
            lkg_cache=InMemoryLastKnownGoodCache(),
            now_factory=lambda: self.now,
        )
        self.service = RegistryDomainService(
            self.store,
            now_factory=lambda: self.now,
        )

    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def test_binding_create_update_delete_and_enable_disable_are_draft_only(self) -> None:
        draft = self.run_async(self.service.create_draft())
        draft = self.run_async(
            self.service.create_binding(draft.draft_id, binding_data())
        )
        self.assertEqual(draft.payload.bindings[0].display_name, "Living temperature")
        self.assertTrue(draft.payload.bindings[0].enabled)
        self.assertEqual(self.database.rows, {})

        draft = self.run_async(
            self.service.update_binding(
                draft.draft_id,
                "living_temperature",
                {"entity_id": "sensor.living_temperature_new"},
            )
        )
        self.assertEqual(
            draft.payload.bindings[0].entity_id,
            "sensor.living_temperature_new",
        )
        draft = self.run_async(
            self.service.set_binding_enabled(
                draft.draft_id,
                "living_temperature",
                False,
            )
        )
        self.assertFalse(draft.payload.bindings[0].enabled)
        draft = self.run_async(
            self.service.set_binding_enabled(
                draft.draft_id,
                "living_temperature",
                True,
            )
        )
        self.assertTrue(draft.payload.bindings[0].enabled)
        draft = self.run_async(
            self.service.delete_binding(draft.draft_id, "living_temperature")
        )
        self.assertEqual(draft.payload.bindings, ())
        self.assertEqual(self.database.rows, {})

    def test_binding_id_is_stable_and_referenced_delete_is_rejected(self) -> None:
        draft = self.run_async(self.service.create_draft())
        draft = self.run_async(
            self.service.create_binding(draft.draft_id, binding_data())
        )
        with self.assertRaises(InvalidReferenceError):
            self.run_async(
                self.service.update_binding(
                    draft.draft_id,
                    "living_temperature",
                    {"binding_id": "another_id"},
                )
            )

        payload = replace(
            draft.payload,
            fusions=(
                Fusion(
                    fusion_id="fusion.living_temperature",
                    contract_id="room.living",
                    field="temperature",
                    input_binding_ids=("living_temperature",),
                ),
            ),
        )
        draft = self.run_async(
            self.service.replace_draft(draft.draft_id, payload)
        )
        with self.assertRaises(InvalidReferenceError):
            self.run_async(
                self.service.delete_binding(draft.draft_id, "living_temperature")
            )

    def test_contract_instance_crud_uses_the_code_defined_schema_registry(self) -> None:
        draft = self.run_async(self.service.create_draft())
        draft = self.run_async(
            self.service.create_contract_instance(
                draft.draft_id,
                {
                    "contract_id": "room.living",
                    "schema_id": "room_climate",
                    "schema_version": 1,
                    "display_name": "Living room",
                },
            )
        )
        self.assertEqual(draft.payload.contract_instances[0]["contract_id"], "room.living")
        draft = self.run_async(
            self.service.update_contract_instance(
                draft.draft_id,
                "room.living",
                {"display_name": "Living room climate"},
            )
        )
        self.assertEqual(
            draft.payload.contract_instances[0]["display_name"],
            "Living room climate",
        )
        draft = self.run_async(
            self.service.delete_contract_instance(draft.draft_id, "room.living")
        )
        self.assertEqual(draft.payload.contract_instances, ())

    def test_validate_does_not_persist_or_activate_and_reports_graph_probe(self) -> None:
        draft = self.run_async(
            self.service.create_binding(
                self.run_async(self.service.create_draft()).draft_id,
                binding_data(),
            )
        )
        report = self.run_async(self.service.validate_draft(draft.draft_id))

        self.assertTrue(report.valid)
        self.assertIsNotNone(report.graph_probe_revision)
        self.assertEqual(self.database.rows, {})
        self.assertIsNone(self.service.runtime.active(ProfileId.BENNI))

    def test_invalid_draft_is_rejected_before_repository_write(self) -> None:
        base = self.run_async(self.service.create_draft())
        base = self.run_async(
            self.service.create_binding(base.draft_id, binding_data())
        )
        active = self.run_async(self.service.save_draft(base.draft_id, 0))
        draft = self.run_async(self.service.create_draft())
        invalid = replace(
            draft.payload,
            fusions=(
                Fusion(
                    fusion_id="fusion.invalid",
                    contract_id="room.living",
                    field="temperature",
                    input_binding_ids=("missing_binding",),
                ),
            ),
        )
        draft = self.run_async(self.service.replace_draft(draft.draft_id, invalid))

        report = self.run_async(self.service.validate_draft(draft.draft_id))
        self.assertFalse(report.valid)
        with self.assertRaises(DraftValidationError):
            self.run_async(
                self.service.save_draft(
                    draft.draft_id,
                    expected_base_revision=active.revision,
                )
            )
        self.assertEqual(len(self.database.rows), 1)
        self.assertEqual(
            self.run_async(self.store.get_active_revision(ProfileId.BENNI)),
            active,
        )
        self.assertEqual(self.service.runtime.active(ProfileId.BENNI).revision, active)

    def test_successful_save_activates_revision_and_runtime_graph(self) -> None:
        draft = self.run_async(self.service.create_draft())
        draft = self.run_async(
            self.service.create_binding(draft.draft_id, binding_data())
        )
        active = self.run_async(
            self.service.save_draft(draft.draft_id, expected_base_revision=0)
        )

        self.assertEqual(active.status, RevisionStatus.ACTIVE)
        runtime = self.service.runtime.active(ProfileId.BENNI)
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.revision.id, active.id)
        self.assertEqual(runtime.graph.binding("living_temperature").entity_id, "sensor.living_temperature")
        self.assertEqual(self.run_async(self.store.get_active_revision(ProfileId.BENNI)), active)

    def test_expected_base_revision_conflict_keeps_active_and_stale_draft(self) -> None:
        first_draft = self.run_async(self.service.create_draft())
        first_draft = self.run_async(
            self.service.create_binding(first_draft.draft_id, binding_data())
        )
        first = self.run_async(self.service.save_draft(first_draft.draft_id, 0))
        stale = self.run_async(self.service.create_draft())
        winner = self.run_async(self.service.create_draft())
        winner = self.run_async(
            self.service.update_binding(
                winner.draft_id,
                "living_temperature",
                {"entity_id": "sensor.living_temperature_winner"},
            )
        )
        winning_revision = self.run_async(
            self.service.save_draft(winner.draft_id, first.revision)
        )

        with self.assertRaises(ConcurrencyConflict) as context:
            self.run_async(self.service.save_draft(stale.draft_id, first.revision))

        self.assertEqual(context.exception.expected_base_revision, first.revision)
        self.assertEqual(context.exception.actual_base_revision, winning_revision.revision)
        self.assertEqual(
            self.run_async(self.store.get_active_revision(ProfileId.BENNI)),
            winning_revision,
        )
        self.assertEqual(
            self.run_async(self.service.get_draft(stale.draft_id)).base_revision,
            first.revision,
        )

    def test_discard_removes_only_the_in_memory_draft(self) -> None:
        draft = self.run_async(self.service.create_draft())
        self.assertTrue(self.run_async(self.service.discard_draft(draft.draft_id)))
        with self.assertRaises(DraftNotFoundError):
            self.run_async(self.service.get_draft(draft.draft_id))
        self.assertEqual(self.database.rows, {})

    def test_rollback_reuses_issue16_history_and_updates_runtime(self) -> None:
        first_draft = self.run_async(self.service.create_draft())
        first_draft = self.run_async(
            self.service.create_binding(first_draft.draft_id, binding_data())
        )
        first = self.run_async(self.service.save_draft(first_draft.draft_id, 0))
        second_draft = self.run_async(self.service.create_draft())
        second_draft = self.run_async(
            self.service.update_binding(
                second_draft.draft_id,
                "living_temperature",
                {"entity_id": "sensor.living_temperature_second"},
            )
        )
        second = self.run_async(
            self.service.save_draft(second_draft.draft_id, first.revision)
        )

        rolled_back = self.run_async(
            self.service.rollback(ProfileId.BENNI, first.id, expected_base_revision=second.revision)
        )

        self.assertEqual(rolled_back.id, first.id)
        self.assertEqual(rolled_back.status, RevisionStatus.ACTIVE)
        self.assertEqual(
            self.run_async(self.store.get_revision(second.id)).status,
            RevisionStatus.SUPERSEDED,
        )
        self.assertEqual(
            self.service.runtime.graph(ProfileId.BENNI).binding("living_temperature").entity_id,
            "sensor.living_temperature",
        )

    def test_missing_revision_and_backend_unavailable_are_distinct(self) -> None:
        with self.assertRaises(RevisionNotFound):
            self.run_async(
                self.service.rollback(ProfileId.BENNI, "missing-revision")
            )

        self.database.unavailable = True
        with self.assertRaises(BackendUnavailableError):
            self.run_async(self.service.create_draft())

    def test_active_read_uses_issue16_lkg_and_installs_it_in_runtime(self) -> None:
        draft = self.run_async(self.service.create_draft())
        draft = self.run_async(
            self.service.create_binding(draft.draft_id, binding_data())
        )
        active = self.run_async(self.service.save_draft(draft.draft_id, 0))
        self.database.unavailable = True

        result = self.run_async(self.service.read_active(ProfileId.BENNI))

        self.assertEqual(result.revision, active)
        self.assertTrue(result.used_last_known_good)
        self.assertEqual(self.service.runtime.active(ProfileId.BENNI).revision, active)
        self.assertEqual(self.database.rows[next(iter(self.database.rows))]["status"], "active")

    def test_runtime_events_have_no_registry_write_path(self) -> None:
        self.assertEqual(self.database.rows, {})
        from custom_components.benni_core_contracts.source_listener import (
            async_attach_source_listeners,
            observation_from_state,
        )

        observation_from_state(
            type("Binding", (), {
                "source_id": "source",
                "entity_id": "sensor.value",
            })(),
            type("State", (), {"state": "21", "attributes": {}})(),
            received_at=self.now,
        )
        self.assertEqual(self.database.rows, {})

        binding = SourceBinding(
            binding_id="runtime_temperature",
            source_id="source.runtime_temperature",
            entity_id="sensor.runtime_temperature",
            field="temperature",
            capability="room_climate",
        )
        graph = SignalGraph(now_factory=lambda: self.now)
        graph.add_binding(binding)
        runtime = ShadowRuntime(
            ConfigModel(mode=RuntimeMode.SHADOW_ONLY, bindings=(binding,)),
            graph,
        )
        callbacks = []

        def track_state_change(_hass, _entity_ids, callback):
            callbacks.append(callback)
            return lambda: None

        hass = types.SimpleNamespace(
            states=types.SimpleNamespace(
                get=lambda _entity_id: types.SimpleNamespace(
                    state="21.0",
                    last_updated=self.now,
                    attributes={},
                )
            )
        )
        event_module = types.ModuleType("homeassistant.helpers.event")
        event_module.async_track_state_change_event = track_state_change
        homeassistant = types.ModuleType("homeassistant")
        helpers = types.ModuleType("homeassistant.helpers")
        helpers.event = event_module
        homeassistant.helpers = helpers
        with patch.dict(
            sys.modules,
            {
                "homeassistant": homeassistant,
                "homeassistant.helpers": helpers,
                "homeassistant.helpers.event": event_module,
            },
        ):
            asyncio.run(async_attach_source_listeners(hass, runtime))

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(
            graph.signal("runtime_temperature").quality.freshness,
            FreshnessStatus.UNKNOWN,
        )
        graph.evaluate_contract("room.runtime", "room_climate", schema_version=1)
        self.assertEqual(self.database.rows, {})

    def test_sensitive_metadata_is_not_accepted_by_the_write_service(self) -> None:
        draft = self.run_async(self.service.create_draft())
        with self.assertRaises(Exception) as context:
            self.run_async(
                self.service.replace_draft(
                    draft.draft_id,
                    RegistryPayload(
                        profile=ProfileId.BENNI,
                        registry_metadata={"postgres_password": "do-not-store"},
                    ),
                )
            )
        self.assertIn("credentials", str(context.exception))


if __name__ == "__main__":
    unittest.main()
