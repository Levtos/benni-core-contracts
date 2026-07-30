from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.benni_core_contracts import async_setup_entry
from custom_components.benni_core_contracts.contracts import OPENING_V1
from custom_components.benni_core_contracts.const import (
    DOMAIN,
    PILOT_OPENING_CONTRACT_ID,
    PILOT_OPENING_ENTITY_ID,
    PILOT_OPENING_SOURCE_ENTITY_IDS,
)
from custom_components.benni_core_contracts.evidence_gate import EvidenceGateStatus, evaluate_contract_evidence
from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.models import (
    ConfigModel,
    ProfileId,
    RawObservation,
    RuntimeMode,
)
from custom_components.benni_core_contracts.published import pilot_opening_bindings
from custom_components.benni_core_contracts.quality import (
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    SafetyStatus,
    TemporalEvidence,
    ValueState,
)
from custom_components.benni_core_contracts.shadow import (
    EntityAllowlist,
    EntityProjectionGate,
    PublishedRuntime,
    ShadowRuntime,
)
from custom_components.benni_core_contracts import sensor as sensor_platform


UTC = timezone.utc
NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)


def published_config(
    *,
    open_entity: str = PILOT_OPENING_SOURCE_ENTITY_IDS[0],
    tilt_entity: str = PILOT_OPENING_SOURCE_ENTITY_IDS[1],
) -> ConfigModel:
    bindings = pilot_opening_bindings(open_entity, tilt_entity)
    return ConfigModel(
        profile=ProfileId.BENNI,
        mode=RuntimeMode.PUBLISHED,
        entity_allowlist=(PILOT_OPENING_ENTITY_ID,),
        published_contracts=(PILOT_OPENING_CONTRACT_ID,),
        bindings=bindings,
    )


def evidence(
    *,
    origin: FreshnessOrigin = FreshnessOrigin.HA_TIMESTAMP,
    age_seconds: int = 1,
    retained: bool = False,
    restored: bool = False,
    state_event: bool = True,
) -> TemporalEvidence:
    timestamp = NOW - timedelta(seconds=age_seconds)
    return TemporalEvidence(
        received_at=NOW,
        origin=origin,
        ha_timestamp=timestamp if origin == FreshnessOrigin.HA_TIMESTAMP else None,
        retained=retained,
        restored=restored,
        ha_state_event=state_event,
    )


def evaluate_opening(
    open_value: str | None = None,
    tilt_value: str | None = None,
    *,
    source_evidence: TemporalEvidence | None = None,
):
    config = published_config()
    graph = SignalGraph.from_config(config)
    if open_value is not None:
        binding = config.bindings[0]
        graph.ingest(
            binding.binding_id,
            RawObservation(
                source_id=binding.source_id,
                entity_id=binding.entity_id,
                value=open_value,
                evidence=source_evidence or evidence(),
            ),
            now=NOW,
        )
    if tilt_value is not None:
        binding = config.bindings[1]
        graph.ingest(
            binding.binding_id,
            RawObservation(
                source_id=binding.source_id,
                entity_id=binding.entity_id,
                value=tilt_value,
                evidence=source_evidence or evidence(),
            ),
            now=NOW,
        )
    return graph.evaluate_contract(PILOT_OPENING_CONTRACT_ID, "opening", now=NOW)


class PublishedOpeningContractTests(unittest.TestCase):
    def test_published_mode_requires_exact_verified_sources_and_benni(self) -> None:
        config = published_config()
        self.assertEqual(config.profile, ProfileId.BENNI)
        self.assertEqual(config.mode, RuntimeMode.PUBLISHED)
        self.assertEqual(config.entity_allowlist, (PILOT_OPENING_ENTITY_ID,))
        self.assertEqual(
            tuple(binding.entity_id for binding in config.bindings),
            PILOT_OPENING_SOURCE_ENTITY_IDS,
        )
        self.assertEqual(ConfigModel.from_dict(config.as_dict()), config)

        with self.assertRaises(ValueError):
            SignalGraph.from_config(
                published_config(
                    open_entity="binary_sensor.not_verified_open",
                    tilt_entity=PILOT_OPENING_SOURCE_ENTITY_IDS[1],
                )
            )
        with self.assertRaises(ValueError):
            ConfigModel(
                profile=ProfileId.ELTERN,
                mode=RuntimeMode.PUBLISHED,
                entity_allowlist=(PILOT_OPENING_ENTITY_ID,),
                published_contracts=(PILOT_OPENING_CONTRACT_ID,),
                bindings=pilot_opening_bindings(*PILOT_OPENING_SOURCE_ENTITY_IDS),
            )

    def test_valid_opening_states_are_fused_from_raw_contacts(self) -> None:
        expected = {
            ("off", "off"): ("closed", False),
            ("off", "on"): ("tilted", False),
            ("on", "off"): ("open", True),
        }
        for raw_values, contract_values in expected.items():
            with self.subTest(raw_values=raw_values):
                contract = evaluate_opening(*raw_values)
                self.assertEqual(contract.values["opening_state"], contract_values[0])
                self.assertEqual(contract.values["is_open"], contract_values[1])
                self.assertTrue(contract.values["available"])
                self.assertEqual(
                    contract.field_quality["opening_state"].freshness,
                    FreshnessStatus.FRESH,
                )
                self.assertEqual(
                    contract.field_quality["opening_state"].health,
                    HealthStatus.HEALTHY,
                )
                self.assertEqual(
                    contract.field_quality["opening_state"].safety,
                    SafetyStatus.VALID,
                )

    def test_missing_evidence_is_unknown_and_blocks_required_opening_gate(self) -> None:
        contract = evaluate_opening()
        self.assertEqual(contract.values["opening_state"], "unknown")
        self.assertEqual(contract.values["is_open"], "unknown")
        self.assertFalse(contract.values["available"])
        self.assertEqual(contract.field_states["opening_state"], ValueState.UNKNOWN)
        self.assertEqual(contract.field_quality["opening_state"].health, HealthStatus.BLOCKED)
        self.assertEqual(contract.field_quality["opening_state"].safety, SafetyStatus.UNKNOWN)
        self.assertEqual(contract.health, HealthStatus.BLOCKED)
        self.assertIn(
            "source_unavailable",
            {reason.code for reason in contract.field_quality["opening_state"].reasons},
        )

    def test_initial_state_without_state_event_is_not_fresh(self) -> None:
        contract = evaluate_opening(
            "off",
            "off",
            source_evidence=evidence(state_event=False),
        )
        self.assertEqual(contract.values["opening_state"], "unknown")
        self.assertEqual(contract.values["is_open"], "unknown")
        self.assertFalse(contract.values["available"])
        self.assertEqual(
            contract.field_quality["opening_state"].freshness,
            FreshnessStatus.UNKNOWN,
        )

    def test_stale_retained_and_restored_evidence_never_claims_physical_state(self) -> None:
        cases = (
            ("stale", evidence(age_seconds=601), FreshnessStatus.STALE),
            (
                "retained",
                evidence(origin=FreshnessOrigin.RETAINED_MQTT, retained=True),
                FreshnessStatus.SUSPECT,
            ),
            (
                "restore",
                evidence(
                    origin=FreshnessOrigin.RESTORE,
                    restored=True,
                    state_event=False,
                ),
                FreshnessStatus.RESTORED,
            ),
        )
        for name, source_evidence, expected_freshness in cases:
            with self.subTest(case=name):
                contract = evaluate_opening(
                    "off",
                    "off",
                    source_evidence=source_evidence,
                )
                self.assertEqual(contract.values["opening_state"], "unknown")
                self.assertEqual(contract.values["is_open"], "unknown")
                self.assertFalse(contract.values["available"])
                self.assertEqual(
                    contract.field_quality["opening_state"].freshness,
                    expected_freshness,
                )
                self.assertNotIn(
                    contract.values["opening_state"],
                    {"closed", "tilted", "open"},
                )

    def test_conflicting_fresh_contacts_are_unknown_and_not_available(self) -> None:
        contract = evaluate_opening("on", "on")
        self.assertEqual(contract.values["opening_state"], "unknown")
        self.assertEqual(contract.values["is_open"], "unknown")
        self.assertFalse(contract.values["available"])
        self.assertEqual(
            contract.field_quality["opening_state"].health,
            HealthStatus.BLOCKED,
        )
        self.assertEqual(
            contract.field_quality["opening_state"].safety,
            SafetyStatus.UNKNOWN,
        )
        self.assertIn(
            "source_conflict",
            {reason.code for reason in contract.field_quality["opening_state"].reasons},
        )

    def test_required_evidence_gate_passes_only_for_complete_healthy_opening(self) -> None:
        valid_gate = evaluate_contract_evidence(
            evaluate_opening("off", "off"),
            OPENING_V1,
        )
        blocked_gate = evaluate_contract_evidence(
            evaluate_opening("on", "on"),
            OPENING_V1,
        )
        self.assertEqual(valid_gate.status, EvidenceGateStatus.PASS)
        self.assertTrue(valid_gate.required_fields_ready)
        self.assertEqual(blocked_gate.status, EvidenceGateStatus.BLOCKED)
        self.assertFalse(blocked_gate.required_fields_ready)
        self.assertIn("opening_state", blocked_gate.blocked_fields)
        self.assertIn("available", blocked_gate.blocked_fields)

    def test_projection_gate_never_projects_internal_graph_objects(self) -> None:
        candidates = (
            "binary_sensor.kitchen_patio_door_open_contact",
            "atomic:benni.opening.kitchen_patio_door.open_contact",
            "fusion:benni.opening.kitchen_patio_door:opening_state",
            "diagnostic:benni.opening.kitchen_patio_door",
            PILOT_OPENING_ENTITY_ID,
        )
        shadow_gate = EntityProjectionGate(
            RuntimeMode.SHADOW_ONLY,
            EntityAllowlist(frozenset((PILOT_OPENING_ENTITY_ID,))),
        )
        published_gate = EntityProjectionGate(
            RuntimeMode.PUBLISHED,
            EntityAllowlist(frozenset((PILOT_OPENING_ENTITY_ID,))),
        )
        self.assertEqual(shadow_gate.projectable(candidates), ())
        self.assertEqual(published_gate.projectable(candidates), (PILOT_OPENING_ENTITY_ID,))

    def test_sensor_platform_adds_one_entity_only_for_published_runtime(self) -> None:
        config = published_config()
        published_runtime = PublishedRuntime(config, SignalGraph.from_config(config))
        shadow_config = ConfigModel(mode=RuntimeMode.SHADOW_ONLY)
        shadow_runtime = ShadowRuntime(shadow_config, SignalGraph.from_config(shadow_config))

        class FakeHass:
            def __init__(self, runtime):
                self.data = {DOMAIN: {"entry": runtime}}

        async def collect(hass, runtime):
            added = []
            await sensor_platform.async_setup_entry(
                FakeHass(runtime),
                SimpleNamespace(entry_id="entry"),
                added.extend,
            )
            return added

        published_entities = asyncio.run(collect(None, published_runtime))
        shadow_entities = asyncio.run(collect(None, shadow_runtime))
        self.assertEqual(len(published_entities), 1)
        self.assertIsInstance(published_entities[0], sensor_platform.OpeningContractSensor)
        self.assertEqual(shadow_entities, [])

    def test_sensor_platform_has_no_service_actuation_or_policy_surface(self) -> None:
        source = Path(sensor_platform.__file__).read_text(encoding="utf-8")
        self.assertIn("PublishedRuntime", source)
        self.assertIn("PILOT_OPENING_ENTITY_ID", source)
        self.assertNotIn("async_call", source)
        self.assertNotIn("call_service", source)
        self.assertNotIn("hass.services", source)
        self.assertNotIn("core_devices", source)
        self.assertNotIn("policy", source.lower())

    def test_published_setup_forwards_only_sensor_platform(self) -> None:
        config = published_config()
        entry = SimpleNamespace(
            entry_id="entry",
            data=config.as_dict(),
            options={},
            async_on_unload=lambda callback: None,
        )
        forwarded = []

        class ConfigEntries:
            async def async_forward_entry_setups(self, entry, platforms):
                forwarded.append((entry.entry_id, platforms))

        class FakeHass:
            def __init__(self):
                self.data = {}
                self.config_entries = ConfigEntries()

        async def no_op(*args, **kwargs):
            return None

        import custom_components.benni_core_contracts as integration

        with patch.object(integration, "async_register_websocket_api", no_op), patch.object(
            integration, "async_attach_source_listeners", no_op
        ), patch.object(integration, "async_setup_view", no_op), patch.object(
            integration, "HomeAssistantStorage", lambda *args: SimpleNamespace(async_load=no_op)
        ):
            self.assertTrue(asyncio.run(async_setup_entry(FakeHass(), entry)))
        self.assertEqual(forwarded, [("entry", ["sensor"])])
