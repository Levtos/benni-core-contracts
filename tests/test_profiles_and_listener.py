from __future__ import annotations

import asyncio
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    ProfileId,
    RuntimeMode,
    SourceBinding,
)
from custom_components.benni_core_contracts.profiles import profile_definition
from custom_components.benni_core_contracts.quality import FreshnessOrigin, FreshnessStatus
from custom_components.benni_core_contracts.shadow import ShadowRuntime
from custom_components.benni_core_contracts.source_listener import (
    async_attach_source_listeners,
    observation_from_state,
)


UTC = timezone.utc


@dataclass
class FakeState:
    state: object
    last_updated: datetime
    attributes: dict


@dataclass
class FakeEvent:
    data: dict
    time_fired: datetime


class FakeStates:
    def __init__(self, state):
        self.state = state

    def get(self, entity_id):
        return self.state


class FakeHass:
    def __init__(self, state):
        self.states = FakeStates(state)


class ProfileAndListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
        self.binding = SourceBinding(
            binding_id="room_temperature",
            source_id="room_temperature_source",
            entity_id="sensor.room_temperature",
            field="temperature",
            capability="room_climate",
            profile_id=ProfileId.BENNI,
        )

    def test_benni_and_eltern_share_profile_rules_without_separate_graph_logic(self) -> None:
        benni = ConfigModel(
            profile=ProfileId.BENNI,
            mode=RuntimeMode.SHADOW_ONLY,
            bindings=(self.binding,),
        )
        eltern_binding = SourceBinding.from_dict(
            {
                **self.binding.as_dict(),
                "profile_id": ProfileId.ELTERN.value,
                "binding_id": "parent_room_temperature",
                "source_id": "parent_room_temperature_source",
                "entity_id": "sensor.parent_room_temperature",
            },
            default_profile=ProfileId.ELTERN,
        )
        eltern = ConfigModel(
            profile=ProfileId.ELTERN,
            mode=RuntimeMode.SHADOW_ONLY,
            bindings=(eltern_binding,),
        )
        self.assertEqual(
            profile_definition(benni.profile).schema_ids,
            profile_definition(eltern.profile).schema_ids,
        )
        self.assertEqual(benni.bindings[0].field, eltern.bindings[0].field)
        self.assertEqual(benni.bindings[0].freshness_ttl_seconds, eltern.bindings[0].freshness_ttl_seconds)

        with self.assertRaises(ValueError):
            ConfigModel(
                profile=ProfileId.ELTERN,
                mode=RuntimeMode.SHADOW_ONLY,
                bindings=(self.binding,),
            )

    def test_initial_state_is_not_an_ha_observation_event(self) -> None:
        state = FakeState(
            state="21.0",
            last_updated=self.now,
            attributes={},
        )
        initial = observation_from_state(
            self.binding,
            state,
            received_at=self.now,
            state_event=False,
        )
        event = observation_from_state(
            self.binding,
            state,
            received_at=self.now,
            state_event=True,
        )
        self.assertEqual(initial.evidence.origin, FreshnessOrigin.HA_TIMESTAMP)
        self.assertFalse(initial.evidence.ha_state_event)
        self.assertEqual(initial.evidence.freshness(self.now, 60)[0], FreshnessStatus.UNKNOWN)
        self.assertTrue(event.evidence.ha_state_event)
        self.assertEqual(event.evidence.freshness(self.now, 60)[0], FreshnessStatus.FRESH)

    def test_listener_marks_only_state_changes_as_ha_events(self) -> None:
        initial_state = FakeState("21.0", self.now, {})
        changed_state = FakeState("21.1", self.now, {})
        callbacks = []

        def track_state_change(hass, entity_ids, callback):
            callbacks.append(callback)

            def unsubscribe():
                return None

            return unsubscribe

        fake_event_module = types.ModuleType("homeassistant.helpers.event")
        fake_event_module.async_track_state_change_event = track_state_change
        fake_homeassistant = types.ModuleType("homeassistant")
        fake_helpers = types.ModuleType("homeassistant.helpers")
        fake_homeassistant.helpers = fake_helpers
        fake_helpers.event = fake_event_module
        graph = SignalGraph(now_factory=lambda: self.now)
        graph.add_binding(self.binding)
        runtime = ShadowRuntime(
            ConfigModel(mode=RuntimeMode.SHADOW_ONLY, bindings=(self.binding,)),
            graph,
        )
        hass = FakeHass(initial_state)

        with patch.dict(
            sys.modules,
            {
                "homeassistant": fake_homeassistant,
                "homeassistant.helpers": fake_helpers,
                "homeassistant.helpers.event": fake_event_module,
            },
        ):
            asyncio.run(async_attach_source_listeners(hass, runtime))
            initial_signal = graph.signal(self.binding.binding_id)
            self.assertIsNotNone(initial_signal)
            self.assertFalse(initial_signal.evidence.ha_state_event)
            self.assertEqual(
                initial_signal.evidence.freshness(self.now, 60)[0],
                FreshnessStatus.UNKNOWN,
            )
            asyncio.run(
                callbacks[0](
                    FakeEvent(
                        data={"old_state": initial_state, "new_state": changed_state},
                        time_fired=self.now,
                    )
                )
            )

        changed_signal = graph.signal(self.binding.binding_id)
        self.assertTrue(changed_signal.evidence.ha_state_event)
        self.assertEqual(
            changed_signal.evidence.freshness(self.now, 60)[0],
            FreshnessStatus.FRESH,
        )

    def test_retained_attribute_wins_over_ha_event(self) -> None:
        retained = observation_from_state(
            self.binding,
            FakeState("21.0", self.now, {"retained": True}),
            received_at=self.now,
            state_event=True,
        )
        self.assertEqual(retained.evidence.origin, FreshnessOrigin.RETAINED_MQTT)
        self.assertEqual(retained.evidence.freshness(self.now, 60)[0], FreshnessStatus.SUSPECT)
