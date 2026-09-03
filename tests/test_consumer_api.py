from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from custom_components.benni_core_contracts import async_setup_registry_service
from custom_components.benni_core_contracts.const import CONSUMER_API_KEY, DOMAIN
from custom_components.benni_core_contracts.consumer_api import (
    ConsumerAccessStatus,
    ConsumerApi,
    ConsumerBindingAmbiguousError,
    ConsumerContractMissingError,
    ConsumerEventKind,
    ConsumerFieldMissingError,
    ConsumerRequirement,
    ConsumerRuntimeNotReadyError,
    ConsumerSchemaMismatchError,
    ConsumerVersionIncompatibleError,
)
from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.models import (
    Fusion,
    ProfileId,
    PublishedContract,
    RawObservation,
    SourceBinding,
)
from custom_components.benni_core_contracts.quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    TemporalEvidence,
    ValueState,
)
from custom_components.benni_core_contracts.registry import (
    RegistryPayload,
    RegistryRevision,
    RevisionStatus,
)
from custom_components.benni_core_contracts.registry_service import RegistryRuntime
from custom_components.benni_core_contracts.schema import (
    ContractFieldSchema,
    ContractSchema,
    SchemaRegistry,
    ValueType,
)


UTC = timezone.utc
CONTRACT_ID = "media.activity.v1"


def make_schema_registry() -> SchemaRegistry:
    field = ContractFieldSchema(
        name="value",
        value_type=ValueType.BOOLEAN,
        required=True,
        fallback=FallbackPolicy(action=FallbackAction.REJECT),
        freshness_ttl_seconds=60,
    )
    additive_field = ContractFieldSchema(
        name="source_label",
        value_type=ValueType.TEXT,
        required=False,
        fallback=FallbackPolicy(action=FallbackAction.REJECT),
        freshness_ttl_seconds=60,
    )
    return SchemaRegistry(
        (
            ContractSchema(schema_id="media_activity", version=1, fields=(field,)),
            ContractSchema(
                schema_id="media_activity",
                version=2,
                fields=(field, additive_field),
            ),
        )
    )


def binding(
    binding_id: str = "media_activity_source",
    *,
    entity_id: str = "sensor.media_activity",
) -> SourceBinding:
    return SourceBinding(
        binding_id=binding_id,
        source_id=f"source.{binding_id}",
        entity_id=entity_id,
        field="value",
        capability="media_activity",
        profile_id=ProfileId.BENNI,
    )


def payload_for(
    bindings: tuple[SourceBinding, ...],
    *,
    schema_version: int = 1,
    include_instance: bool = True,
) -> RegistryPayload:
    fusions = (
        Fusion(
            fusion_id="media_activity_fusion",
            contract_id=CONTRACT_ID,
            field="value",
            input_binding_ids=tuple(item.binding_id for item in bindings),
            strategy="first_healthy",
        ),
    ) if bindings else ()
    return RegistryPayload(
        profile=ProfileId.BENNI,
        bindings=bindings,
        fusions=fusions,
        contract_instances=(
            {
                "contract_id": CONTRACT_ID,
                "schema_id": "media_activity",
                "schema_version": schema_version,
                "profile": "benni",
            },
        )
        if include_instance
        else (),
    )


def revision(payload: RegistryPayload, number: int, revision_id: str) -> RegistryRevision:
    now = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
    return RegistryRevision(
        id=revision_id,
        revision=number,
        profile=ProfileId.BENNI,
        schema_version=1,
        payload=payload,
        status=RevisionStatus.ACTIVE,
        created_at=now,
        activated_at=now,
    )


def graph_for(
    payload: RegistryPayload,
    registry: SchemaRegistry,
    now: datetime,
    *,
    values: tuple[bool, ...] = (True,),
    age_seconds: int = 1,
    evaluate: bool = True,
) -> SignalGraph:
    graph = SignalGraph(registry=registry, now_factory=lambda: now)
    for item in payload.bindings:
        graph.add_binding(item)
    graph.add_fusions(payload.fusions)
    for item, value in zip(payload.bindings, values):
        graph.ingest(
            item.binding_id,
            RawObservation(
                source_id=item.source_id,
                entity_id=item.entity_id,
                value=value,
                evidence=TemporalEvidence(
                    received_at=now,
                    origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                    device_timestamp=now - timedelta(seconds=age_seconds),
                ),
            ),
            now=now,
        )
    if evaluate:
        configured_version = next(
            (
                item.get("schema_version")
                for item in payload.contract_instances
                if item.get("contract_id") == CONTRACT_ID
            ),
            1,
        )
        graph.evaluate_contract(
            CONTRACT_ID,
            "media_activity",
            schema_version=int(configured_version),
            now=now,
        )
    return graph


class MinimalTestConsumer:
    """Small fixture that mirrors the next integration's intended usage."""

    consumer_id = "test_consumer"

    def __init__(self, api: ConsumerApi) -> None:
        self.api = api
        self.declaration = api.register_consumer(
            self.consumer_id,
            (
                ConsumerRequirement(
                    contract_id=CONTRACT_ID,
                    schema_id="media_activity",
                    min_supported_schema_version=1,
                    required_fields=("value",),
                ),
            ),
        )


class ConsumerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
        self.schema_registry = make_schema_registry()
        self.source_binding = binding()
        self.payload = payload_for((self.source_binding,))
        self.graph = graph_for(self.payload, self.schema_registry, self.now)
        self.runtime = RegistryRuntime(schema_registry=self.schema_registry)
        self.runtime.activate(revision(self.payload, 1, "revision-1"), self.graph)
        self.api = ConsumerApi(self.runtime, now_factory=lambda: self.now)
        self.consumer = MinimalTestConsumer(self.api)

    def tearDown(self) -> None:
        self.api.close()

    def test_minimal_consumer_reads_snapshot_field_quality_freshness_and_lineage(self) -> None:
        snapshot = self.api.get_contract_snapshot(
            CONTRACT_ID,
            schema_id="media_activity",
            min_supported_schema_version=1,
            required_fields=("value",),
        )
        self.assertEqual(snapshot.status, ConsumerAccessStatus.HEALTHY)
        self.assertTrue(snapshot.consumable)
        self.assertEqual(snapshot.registry_revision, 1)
        self.assertEqual(snapshot.revision.revision_id, "revision-1")
        self.assertEqual(snapshot.schema_version, 1)

        field = self.api.get_field(CONTRACT_ID, "value")
        self.assertTrue(field.value)
        self.assertEqual(field.state, ValueState.VALID)
        self.assertEqual(self.api.get_quality(CONTRACT_ID, "value").health, HealthStatus.HEALTHY)
        self.assertEqual(self.api.get_freshness(CONTRACT_ID, "value"), FreshnessStatus.FRESH)
        self.assertEqual(self.api.get_health(CONTRACT_ID), HealthStatus.HEALTHY)
        self.assertEqual(field.lineage.active_binding_ids, (self.source_binding.binding_id,))
        self.assertEqual(field.lineage.active_entity_ids, (self.source_binding.entity_id,))

        copied_value = field.as_dict()
        copied_value["value"] = False
        self.assertTrue(self.api.get_field(CONTRACT_ID, "value").value)

    def test_binding_role_resolution_uses_stable_technical_binding_and_reports_ambiguity(self) -> None:
        resolved = self.api.resolve_binding("media_activity")
        self.assertEqual(resolved.binding_id, self.source_binding.binding_id)
        self.assertTrue(resolved.read_only)
        self.assertEqual(self.api.resolve_binding(self.source_binding.binding_id).entity_id, "sensor.media_activity")

        ambiguous_binding = binding("media_activity_backup", entity_id="sensor.media_activity_backup")
        ambiguous_payload = payload_for((self.source_binding, ambiguous_binding))
        ambiguous_graph = graph_for(
            ambiguous_payload,
            self.schema_registry,
            self.now,
            values=(True, False),
        )
        self.runtime.activate(revision(ambiguous_payload, 2, "revision-2"), ambiguous_graph)
        with self.assertRaises(ConsumerBindingAmbiguousError) as context:
            self.api.resolve_binding("media_activity")
        self.assertEqual(context.exception.status, ConsumerAccessStatus.BINDING_AMBIGUOUS)

    def test_contract_statuses_and_typed_errors_are_distinct(self) -> None:
        missing = self.api.lookup_contract("missing.contract")
        self.assertEqual(missing.status, ConsumerAccessStatus.MISSING)
        with self.assertRaises(ConsumerContractMissingError):
            self.api.get_contract_snapshot("missing.contract")

        field_missing = self.api.lookup_contract(CONTRACT_ID, required_fields=("missing",))
        self.assertEqual(field_missing.status, ConsumerAccessStatus.FIELD_MISSING)
        with self.assertRaises(ConsumerFieldMissingError):
            self.api.get_field(CONTRACT_ID, "missing")

        schema_mismatch = self.api.lookup_contract(CONTRACT_ID, schema_id="other_schema")
        self.assertEqual(schema_mismatch.status, ConsumerAccessStatus.SCHEMA_MISMATCH)
        with self.assertRaises(ConsumerSchemaMismatchError):
            self.api.get_contract_snapshot(CONTRACT_ID, schema_id="other_schema")

        version_mismatch = self.api.lookup_contract(CONTRACT_ID, expected_schema_version=2)
        self.assertEqual(version_mismatch.status, ConsumerAccessStatus.VERSION_INCOMPATIBLE)
        with self.assertRaises(ConsumerVersionIncompatibleError):
            self.api.get_contract_snapshot(CONTRACT_ID, expected_schema_version=2)

        additive_payload = payload_for((self.source_binding,), schema_version=2)
        additive_graph = graph_for(additive_payload, self.schema_registry, self.now)
        self.runtime.activate(revision(additive_payload, 2, "revision-additive"), additive_graph)
        additive = self.api.lookup_contract(
            CONTRACT_ID,
            schema_id="media_activity",
            min_supported_schema_version=1,
            required_fields=("value",),
        )
        self.assertEqual(additive.snapshot.schema_version, 2)
        self.assertNotEqual(additive.status, ConsumerAccessStatus.VERSION_INCOMPATIBLE)

        not_ready_runtime = RegistryRuntime(schema_registry=self.schema_registry)
        not_ready_api = ConsumerApi(not_ready_runtime, now_factory=lambda: self.now)
        try:
            result = not_ready_api.lookup_contract(CONTRACT_ID)
            self.assertEqual(result.status, ConsumerAccessStatus.RUNTIME_NOT_READY)
            with self.assertRaises(ConsumerRuntimeNotReadyError):
                not_ready_api.get_revision()
        finally:
            not_ready_api.close()

    def test_degraded_and_blocked_contracts_remain_readable_with_explicit_health(self) -> None:
        backup = binding("media_activity_backup", entity_id="sensor.media_activity_backup")
        degraded_payload = payload_for((self.source_binding, backup))
        degraded_graph = graph_for(
            degraded_payload,
            self.schema_registry,
            self.now,
            values=(True, False),
        )
        degraded_runtime = RegistryRuntime(schema_registry=self.schema_registry)
        degraded_runtime.activate(revision(degraded_payload, 2, "revision-degraded"), degraded_graph)
        degraded_api = ConsumerApi(degraded_runtime, now_factory=lambda: self.now)
        try:
            degraded = degraded_api.get_contract_snapshot(CONTRACT_ID)
            self.assertEqual(degraded.status, ConsumerAccessStatus.DEGRADED)
            self.assertEqual(degraded.health, HealthStatus.DEGRADED)
        finally:
            degraded_api.close()

        blocked_payload = payload_for((self.source_binding,))
        blocked_graph = graph_for(
            blocked_payload,
            self.schema_registry,
            self.now,
            values=(),
            evaluate=False,
        )
        blocked_runtime = RegistryRuntime(schema_registry=self.schema_registry)
        blocked_runtime.activate(revision(blocked_payload, 3, "revision-blocked"), blocked_graph)
        blocked_api = ConsumerApi(blocked_runtime, now_factory=lambda: self.now)
        try:
            blocked = blocked_api.lookup_contract(CONTRACT_ID)
            self.assertEqual(blocked.status, ConsumerAccessStatus.BLOCKED)
            self.assertEqual(blocked.require_snapshot().health, HealthStatus.BLOCKED)
        finally:
            blocked_api.close()

    def test_requirement_declaration_and_dependency_impact(self) -> None:
        impact = self.api.impact_for(self.consumer.consumer_id)
        self.assertEqual(impact.status, ConsumerAccessStatus.HEALTHY)
        self.assertTrue(impact.satisfied)
        self.assertTrue(impact.requirements[0].satisfied)

        self.api.register_consumer(
            "missing_consumer",
            (ConsumerRequirement(contract_id="missing.contract"),),
        )
        missing_impact = self.api.consumer_impact("missing_consumer")
        self.assertEqual(missing_impact.status, ConsumerAccessStatus.MISSING)
        self.assertEqual(missing_impact.affected_contract_ids, ("missing.contract",))

        self.api.register_consumer(
            "role_consumer",
            (ConsumerRequirement(role="media_activity"),),
        )
        self.assertEqual(self.api.impact_for("role_consumer").status, ConsumerAccessStatus.HEALTHY)

    def test_subscription_gets_relevant_value_and_quality_freshness_updates(self) -> None:
        updates = []
        subscription = self.api.subscribe(
            self.consumer.consumer_id,
            updates.append,
            contract_id=CONTRACT_ID,
        )
        self.assertTrue(subscription.active)
        self.assertEqual(self.api.subscription_count(self.consumer.consumer_id), 1)

        self.graph.ingest(
            self.source_binding.binding_id,
            RawObservation(
                source_id=self.source_binding.source_id,
                entity_id=self.source_binding.entity_id,
                value=False,
                evidence=TemporalEvidence(
                    received_at=self.now,
                    origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                    device_timestamp=self.now - timedelta(seconds=1),
                ),
            ),
            now=self.now,
        )
        self.assertTrue(updates)
        self.assertIn(ConsumerEventKind.VALUE_CHANGED, updates[-1].event_kinds)
        self.assertEqual(updates[-1].snapshot.field("value").value, False)

        updates.clear()
        self.graph.ingest(
            self.source_binding.binding_id,
            RawObservation(
                source_id=self.source_binding.source_id,
                entity_id=self.source_binding.entity_id,
                value=False,
                evidence=TemporalEvidence(
                    received_at=self.now,
                    origin=FreshnessOrigin.RETAINED_MQTT,
                    retained=True,
                ),
            ),
            now=self.now,
        )
        self.assertTrue(updates)
        self.assertIn(ConsumerEventKind.QUALITY_CHANGED, updates[-1].event_kinds)
        self.assertIn(ConsumerEventKind.FRESHNESS_CHANGED, updates[-1].event_kinds)
        self.assertEqual(updates[-1].snapshot.health, HealthStatus.BLOCKED)

        self.assertTrue(subscription.unsubscribe())
        self.assertFalse(subscription.active)
        self.assertEqual(self.api.subscription_count(), 0)

    def test_role_subscription_tracks_contracts_using_the_resolved_binding(self) -> None:
        self.api.register_consumer(
            "role_subscription_consumer",
            (ConsumerRequirement.binding_role("media_activity"),),
        )
        updates = []
        self.api.subscribe(
            "role_subscription_consumer",
            updates.append,
            role="media_activity",
        )
        self.graph.ingest(
            self.source_binding.binding_id,
            RawObservation(
                source_id=self.source_binding.source_id,
                entity_id=self.source_binding.entity_id,
                value=False,
                evidence=TemporalEvidence(
                    received_at=self.now,
                    origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                    device_timestamp=self.now - timedelta(seconds=1),
                ),
            ),
            now=self.now,
        )
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].contract_id, CONTRACT_ID)
        self.assertIn(ConsumerEventKind.VALUE_CHANGED, updates[0].event_kinds)

    def test_registry_activation_filters_irrelevant_revision_and_reports_relevant_change(self) -> None:
        updates = []
        self.api.subscribe(self.consumer.consumer_id, updates.append, contract_id=CONTRACT_ID)

        same_payload_graph = graph_for(self.payload, self.schema_registry, self.now)
        self.runtime.activate(revision(self.payload, 2, "revision-same"), same_payload_graph)
        self.assertEqual(updates, [])

        changed_binding = replace(self.source_binding, entity_id="sensor.media_activity_new")
        changed_payload = payload_for((changed_binding,))
        changed_graph = graph_for(changed_payload, self.schema_registry, self.now)
        self.runtime.activate(revision(changed_payload, 3, "revision-relevant"), changed_graph)
        self.assertTrue(updates)
        self.assertIn(ConsumerEventKind.REVISION_CHANGED, updates[-1].event_kinds)
        self.assertEqual(
            updates[-1].snapshot.field("value").lineage.active_entity_ids,
            ("sensor.media_activity_new",),
        )

    def test_subscription_reports_available_and_unavailable_transitions(self) -> None:
        runtime = RegistryRuntime(schema_registry=self.schema_registry)
        api = ConsumerApi(runtime, now_factory=lambda: self.now)
        api.register_consumer("availability_consumer", (ConsumerRequirement(contract_id=CONTRACT_ID),))
        updates = []
        api.subscribe("availability_consumer", updates.append, contract_id=CONTRACT_ID)
        runtime.activate(revision(self.payload, 1, "revision-available"), self.graph)
        self.assertTrue(updates)
        self.assertIn(ConsumerEventKind.AVAILABLE, updates[-1].event_kinds)

        unavailable_payload = payload_for((), include_instance=False)
        unavailable_graph = graph_for(
            unavailable_payload,
            self.schema_registry,
            self.now,
            values=(),
            evaluate=False,
        )
        runtime.activate(revision(unavailable_payload, 2, "revision-unavailable"), unavailable_graph)
        self.assertIn(ConsumerEventKind.UNAVAILABLE, updates[-1].event_kinds)
        api.close()

    def test_duplicate_subscription_cleanup_and_callback_failure_are_isolated(self) -> None:
        events = []

        def failing(_update) -> None:
            raise RuntimeError("consumer failure")

        self.api.subscribe(self.consumer.consumer_id, failing, contract_id=CONTRACT_ID)
        callback = events.append
        healthy_subscription = self.api.subscribe(
            self.consumer.consumer_id,
            callback,
            contract_id=CONTRACT_ID,
        )
        duplicate = self.api.subscribe(
            self.consumer.consumer_id,
            callback,
            contract_id=CONTRACT_ID,
        )
        self.assertEqual(healthy_subscription.token, duplicate.token)
        self.assertEqual(self.api.subscription_count(), 2)

        with self.assertLogs(
            "custom_components.benni_core_contracts.consumer_api",
            level="ERROR",
        ):
            self.graph.ingest(
                self.source_binding.binding_id,
                RawObservation(
                    source_id=self.source_binding.source_id,
                    entity_id=self.source_binding.entity_id,
                    value=False,
                    evidence=TemporalEvidence(
                        received_at=self.now,
                        origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                        device_timestamp=self.now - timedelta(seconds=1),
                    ),
                ),
                now=self.now,
            )
        self.assertEqual(len(events), 1)
        self.assertEqual(self.api.cleanup_consumer(self.consumer.consumer_id), 2)
        self.assertFalse(healthy_subscription.active)

    def test_consumer_boundary_has_no_repository_dependency_or_transport_entity(self) -> None:
        source = Path(__file__).resolve().parents[1] / "custom_components" / "benni_core_contracts" / "consumer_api.py"
        text = source.read_text(encoding="utf-8")
        self.assertNotIn("PostgresRegistryRepository", text)
        self.assertNotIn("registry_store", text)
        self.assertNotIn("async_add_entities", text)

        package = source.parent
        self.assertFalse((package / "button.py").exists())
        self.assertFalse((package / "switch.py").exists())

    def test_consumer_snapshot_does_not_return_published_contract_or_graph(self) -> None:
        snapshot = self.api.get_contract_snapshot(CONTRACT_ID)
        self.assertNotIsInstance(snapshot, PublishedContract)
        self.assertFalse(hasattr(snapshot, "graph"))
        self.assertNotIsInstance(snapshot.fields[0].lineage, SourceBinding)

    def test_home_assistant_setup_exposes_the_shared_runtime_consumer_api(self) -> None:
        hass = SimpleNamespace(data={})
        with patch(
            "custom_components.benni_core_contracts.async_register_registry_write_api",
            new=AsyncMock(),
        ):
            service = asyncio.run(
                async_setup_registry_service(
                    hass,
                    object(),
                    schema_registry=self.schema_registry,
                )
            )
        api = hass.data[DOMAIN][CONSUMER_API_KEY]
        try:
            self.assertIsInstance(api, ConsumerApi)
            self.assertIs(api._runtime, service.runtime)
        finally:
            api.close()


if __name__ == "__main__":
    unittest.main()
