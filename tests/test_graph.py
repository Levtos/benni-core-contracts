from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from custom_components.benni_core_contracts.contracts import ROOM_CLIMATE_V1
from custom_components.benni_core_contracts.graph import GraphError, SignalGraph
from custom_components.benni_core_contracts.models import (
    Fusion,
    RawObservation,
    SourceBinding,
)
from custom_components.benni_core_contracts.quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessOrigin,
    HealthStatus,
    TemporalEvidence,
    ValueState,
)
from custom_components.benni_core_contracts.schema import (
    ContractFieldSchema,
    ContractSchema,
    SchemaRegistry,
    ValueType,
)


UTC = timezone.utc


def bool_schema(
    schema_id: str = "bool_contract",
    *,
    required: bool = False,
    fallback: FallbackPolicy | None = None,
    ttl: int = 300,
) -> ContractSchema:
    return ContractSchema(
        schema_id=schema_id,
        version=1,
        fields=(
            ContractFieldSchema(
                name="value",
                value_type=ValueType.BOOLEAN,
                required=required,
                fallback=fallback or FallbackPolicy(),
                freshness_ttl_seconds=ttl,
            ),
        ),
    )


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 22, 20, 0, tzinfo=UTC)
        self.graph = SignalGraph(now_factory=lambda: self.now)
        for field in ("temperature", "humidity", "available"):
            binding = SourceBinding(
                binding_id=f"living_{field}",
                source_id=f"living_{field}_source",
                entity_id=f"sensor.living_{field}",
                field=field,
                capability="room_climate",
                required=field in {"temperature", "available"},
            )
            self.graph.add_binding(binding)
            self.graph.add_fusion(
                Fusion(
                    fusion_id=f"fusion_living_{field}",
                    contract_id="room.living",
                    field=field,
                    input_binding_ids=(binding.binding_id,),
                )
            )

    def ingest(
        self,
        binding_id: str,
        value,
        *,
        age_seconds: int = 1,
        received_at: datetime | None = None,
    ) -> None:
        binding = self.graph.binding(binding_id)
        timestamp = self.now - timedelta(seconds=age_seconds)
        self.graph.ingest(
            binding_id,
            RawObservation(
                source_id=binding.source_id,
                entity_id=binding.entity_id,
                value=value,
                evidence=TemporalEvidence(
                    received_at=received_at or self.now,
                    origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                    device_timestamp=timestamp,
                ),
            ),
            now=self.now,
        )

    def test_field_quality_does_not_erase_other_factual_fields(self) -> None:
        self.ingest("living_temperature", 21.5)
        self.ingest("living_humidity", 48.0, age_seconds=7200)
        self.ingest("living_available", True)

        contract = self.graph.evaluate_contract(
            "room.living", ROOM_CLIMATE_V1.schema_id, now=self.now
        )

        self.assertEqual(contract.values["temperature"], 21.5)
        self.assertIsNone(contract.values["humidity"])
        self.assertTrue(contract.values["available"])
        self.assertEqual(contract.field_quality["temperature"].health, HealthStatus.HEALTHY)
        self.assertEqual(contract.field_quality["humidity"].health, HealthStatus.UNKNOWN)
        self.assertEqual(contract.field_quality["humidity"].freshness.value, "stale")
        self.assertEqual(contract.health, HealthStatus.DEGRADED)

    def test_missing_required_field_blocks_only_that_contract_result(self) -> None:
        self.ingest("living_available", True)
        contract = self.graph.evaluate_contract("room.living", ROOM_CLIMATE_V1.schema_id, now=self.now)
        self.assertIsNone(contract.values["temperature"])
        self.assertEqual(contract.field_states["temperature"], ValueState.BLOCKED)
        self.assertEqual(contract.field_quality["temperature"].health, HealthStatus.BLOCKED)
        self.assertTrue(contract.values["available"])
        self.assertEqual(contract.health, HealthStatus.BLOCKED)

    def test_optional_missing_field_is_unavailable_without_blocking_other_fields(self) -> None:
        self.ingest("living_temperature", 21.5)
        self.ingest("living_available", True)
        contract = self.graph.evaluate_contract(
            "room.living", ROOM_CLIMATE_V1.schema_id, now=self.now
        )
        self.assertEqual(contract.field_states["humidity"], ValueState.UNAVAILABLE)
        self.assertEqual(contract.field_quality["humidity"].health, HealthStatus.UNKNOWN)
        self.assertEqual(contract.field_quality["temperature"].health, HealthStatus.HEALTHY)

    def test_real_change_timestamp_is_only_advanced_by_real_evidence(self) -> None:
        self.ingest("living_temperature", 21.5)
        first = self.graph.signal("living_temperature")
        self.assertIsNotNone(first)
        self.assertIsNone(first.real_change_at)

        self.ingest("living_temperature", 22.0)
        second = self.graph.signal("living_temperature")
        self.assertIsNotNone(second)
        self.assertIsNotNone(second.real_change_at)

    def _technical_graph(self, *, ttl: int = 300) -> SignalGraph:
        schema = bool_schema("technical_test", ttl=ttl)
        graph = SignalGraph(
            registry=SchemaRegistry((schema,)),
            now_factory=lambda: self.now,
        )
        for binding_id, entity_id in (("first", "sensor.first"), ("second", "sensor.second")):
            graph.add_binding(
                SourceBinding(
                    binding_id=binding_id,
                    source_id=f"{binding_id}_source",
                    entity_id=entity_id,
                    field="value",
                    capability="technical_device",
                )
            )
        return graph

    def _ingest_bool(
        self,
        graph: SignalGraph,
        binding_id: str,
        value,
        *,
        timestamp: datetime,
        received_at: datetime | None = None,
        origin: FreshnessOrigin = FreshnessOrigin.DEVICE_TIMESTAMP,
    ) -> None:
        binding = graph.binding(binding_id)
        graph.ingest(
            binding_id,
            RawObservation(
                source_id=binding.source_id,
                entity_id=binding.entity_id,
                value=value,
                evidence=TemporalEvidence(
                    received_at=received_at or self.now,
                    origin=origin,
                    device_timestamp=timestamp if origin == FreshnessOrigin.DEVICE_TIMESTAMP else None,
                    ha_timestamp=timestamp if origin == FreshnessOrigin.HA_TIMESTAMP else None,
                    ha_state_event=origin == FreshnessOrigin.HA_TIMESTAMP,
                ),
            ),
            now=self.now,
        )

    def test_first_healthy_uses_priority_then_falls_back_and_records_source(self) -> None:
        graph = self._technical_graph()
        graph.add_fusion(
            Fusion(
                fusion_id="priority",
                contract_id="test.device",
                field="value",
                input_binding_ids=("first", "second"),
                strategy="first_healthy",
            )
        )
        self._ingest_bool(graph, "first", True, timestamp=self.now - timedelta(seconds=301))
        self._ingest_bool(graph, "second", False, timestamp=self.now - timedelta(seconds=1))

        contract = graph.evaluate_contract("test.device", "technical_test", now=self.now)
        self.assertFalse(contract.values["value"])
        self.assertEqual(contract.lineage["value"], ("second",))
        self.assertEqual(
            contract.field_evaluations["value"].candidate_binding_ids,
            ("first", "second"),
        )
        self.assertEqual(
            contract.field_evaluations["value"].active_binding_ids,
            ("second",),
        )

    def test_conflicting_fresh_sources_keep_priority_and_emit_diagnostic(self) -> None:
        graph = self._technical_graph()
        graph.add_fusion(
            Fusion(
                fusion_id="conflict",
                contract_id="test.device",
                field="value",
                input_binding_ids=("first", "second"),
                strategy="first_healthy",
            )
        )
        self._ingest_bool(graph, "first", True, timestamp=self.now - timedelta(seconds=1))
        self._ingest_bool(graph, "second", False, timestamp=self.now - timedelta(seconds=2))
        contract = graph.evaluate_contract("test.device", "technical_test", now=self.now)
        self.assertTrue(contract.values["value"])
        self.assertEqual(contract.field_quality["value"].quality.value, "conflict")
        self.assertTrue(
            any(
                issue.code == "conflicting_fresh_sources"
                for issue in contract.field_quality["value"].reasons
            )
        )

    def test_latest_uses_observation_time_not_received_at_and_ignores_younger_stale(self) -> None:
        graph = self._technical_graph(ttl=300)
        graph.add_fusion(
            Fusion(
                fusion_id="latest",
                contract_id="test.device",
                field="value",
                input_binding_ids=("first", "second"),
                strategy="latest",
            )
        )
        self._ingest_bool(
            graph,
            "first",
            True,
            timestamp=self.now - timedelta(seconds=30),
            received_at=self.now - timedelta(hours=1),
        )
        self._ingest_bool(
            graph,
            "second",
            False,
            timestamp=self.now - timedelta(seconds=301),
            received_at=self.now,
        )
        contract = graph.evaluate_contract("test.device", "technical_test", now=self.now)
        self.assertTrue(contract.values["value"])
        self.assertEqual(contract.lineage["value"], ("first",))

    def test_any_true_has_explicit_unknown_and_completeness_semantics(self) -> None:
        schema = bool_schema("any_true_test", fallback=FallbackPolicy(action=FallbackAction.REJECT))

        def make_graph() -> SignalGraph:
            graph = SignalGraph(registry=SchemaRegistry((schema,)), now_factory=lambda: self.now)
            for binding_id in ("true", "false", "unknown"):
                graph.add_binding(
                    SourceBinding(
                        binding_id=binding_id,
                        source_id=f"{binding_id}_source",
                        entity_id=f"binary_sensor.{binding_id}",
                        field="value",
                        capability="technical_device",
                    )
                )
            graph.add_fusion(
                Fusion(
                    fusion_id="any_true",
                    contract_id="test.any",
                    field="value",
                    input_binding_ids=("true", "false", "unknown"),
                    strategy="any_true",
                )
            )
            return graph

        graph = make_graph()
        self._ingest_bool(graph, "true", True, timestamp=self.now - timedelta(seconds=1))
        self._ingest_bool(graph, "false", False, timestamp=self.now - timedelta(seconds=1))
        self._ingest_bool(graph, "unknown", "unknown", timestamp=self.now - timedelta(seconds=1))
        with_unknown = graph.evaluate_contract("test.any", "any_true_test", now=self.now)
        self.assertTrue(with_unknown.values["value"])
        self.assertEqual(with_unknown.field_states["value"], ValueState.VALID)
        self.assertFalse(with_unknown.field_evaluations["value"].completeness)
        self.assertEqual(with_unknown.field_quality["value"].health, HealthStatus.DEGRADED)
        self.assertTrue(
            any(
                issue.code == "incomplete_any_true_sources"
                for issue in with_unknown.field_quality["value"].reasons
            )
        )
        diagnostic = graph.diagnostic("test.any")
        self.assertIsNotNone(diagnostic)
        self.assertTrue(
            any(
                issue.code == "incomplete_any_true_sources"
                for issue in diagnostic.fields[0].root_causes
            )
        )

        false_graph = make_graph()
        self._ingest_bool(false_graph, "true", False, timestamp=self.now - timedelta(seconds=1))
        self._ingest_bool(false_graph, "false", False, timestamp=self.now - timedelta(seconds=1))
        false_result = false_graph.evaluate_contract("test.any", "any_true_test", now=self.now)
        self.assertFalse(false_result.values["value"])
        self.assertEqual(false_result.field_states["value"], ValueState.VALID)
        self.assertTrue(false_result.field_evaluations["value"].completeness)

        unknown_graph = make_graph()
        self._ingest_bool(unknown_graph, "false", False, timestamp=self.now - timedelta(seconds=1))
        self._ingest_bool(unknown_graph, "unknown", "unknown", timestamp=self.now - timedelta(seconds=1))
        unknown_result = unknown_graph.evaluate_contract("test.any", "any_true_test", now=self.now)
        self.assertIsNone(unknown_result.values["value"])
        self.assertEqual(unknown_result.field_states["value"], ValueState.UNKNOWN)

    def test_hold_last_is_internal_degraded_and_becomes_stale(self) -> None:
        schema = bool_schema(
            "hold_test",
            required=True,
            fallback=FallbackPolicy(
                action=FallbackAction.HOLD_LAST,
                reason="hold only for internal continuity",
            ),
            ttl=10,
        )
        graph = SignalGraph(registry=SchemaRegistry((schema,)), now_factory=lambda: self.now)
        graph.add_binding(
            SourceBinding(
                binding_id="held",
                source_id="held_source",
                entity_id="sensor.held",
                field="value",
                capability="technical_device",
            )
        )
        graph.add_fusion(
            Fusion(
                fusion_id="held_fusion",
                contract_id="held.contract",
                field="value",
                input_binding_ids=("held",),
            )
        )
        self._ingest_bool(graph, "held", True, timestamp=self.now - timedelta(seconds=1))
        fresh = graph.evaluate_contract("held.contract", "hold_test", now=self.now)
        self.assertTrue(fresh.values["value"])

        stale = graph.evaluate_contract(
            "held.contract",
            "hold_test",
            now=self.now + timedelta(seconds=20),
        )
        self.assertTrue(stale.values["value"])
        self.assertEqual(stale.field_states["value"], ValueState.UNKNOWN)
        self.assertEqual(stale.field_quality["value"].freshness.value, "stale")
        self.assertEqual(stale.field_quality["value"].health, HealthStatus.DEGRADED)

    def test_restore_after_reload_is_not_fresh(self) -> None:
        schema = bool_schema(
            "restore_test",
            required=True,
            fallback=FallbackPolicy(action=FallbackAction.REJECT),
        )
        graph = SignalGraph(registry=SchemaRegistry((schema,)), now_factory=lambda: self.now)
        binding = SourceBinding(
            binding_id="restored",
            source_id="restored_source",
            entity_id="sensor.restored",
            field="value",
            capability="technical_device",
        )
        graph.add_binding(binding)
        graph.add_fusion(
            Fusion(
                fusion_id="restore_fusion",
                contract_id="restore.contract",
                field="value",
                input_binding_ids=(binding.binding_id,),
            )
        )
        graph.restore_signal(binding.binding_id, True, restored_at=self.now)
        contract = graph.evaluate_contract("restore.contract", "restore_test", now=self.now)
        self.assertIsNone(contract.values["value"])
        self.assertEqual(contract.field_quality["value"].freshness.value, "restored")
        self.assertEqual(contract.field_states["value"], ValueState.BLOCKED)

    def test_graph_rejects_cycles_and_cross_field_fusions(self) -> None:
        graph = SignalGraph(now_factory=lambda: self.now)
        graph.add_binding(
            SourceBinding(
                binding_id="available",
                source_id="available_source",
                entity_id="sensor.available",
                field="available",
                capability="technical_device",
            )
        )
        with self.assertRaises(GraphError):
            graph.add_fusion(
                Fusion(
                    fusion_id="wrong_field",
                    contract_id="device.one",
                    field="available",
                    input_binding_ids=("available",),
                    input_fusion_ids=("missing",),
                )
            )

        cycle_graph = SignalGraph(now_factory=lambda: self.now)
        with self.assertRaises(GraphError):
            cycle_graph.add_fusions(
                (
                    Fusion(
                        fusion_id="a",
                        contract_id="device.a",
                        field="value",
                        input_binding_ids=(),
                        input_fusion_ids=("b",),
                    ),
                    Fusion(
                        fusion_id="b",
                        contract_id="device.b",
                        field="value",
                        input_binding_ids=(),
                        input_fusion_ids=("a",),
                    ),
                )
            )
