from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from custom_components.benni_core_contracts.consumer_api import (
    ConsumerAccessStatus,
    ConsumerApi,
    ConsumerEventKind,
    ConsumerRequirement,
    ConsumerRuntimeNotReadyError,
)
from custom_components.benni_core_contracts.graph import (
    GraphError,
    SignalGraph,
)
from custom_components.benni_core_contracts.models import (
    Fusion,
    ProfileId,
    RawObservation,
    SourceBinding,
)
from custom_components.benni_core_contracts.profiles import profile_definition
from custom_components.benni_core_contracts.quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    TemporalEvidence,
)
from custom_components.benni_core_contracts.registry import (
    RegistryPayload,
    RegistryRevision,
    RegistrySource,
    RevisionStatus,
)
from custom_components.benni_core_contracts.registry_service import (
    RegistryDomainService,
    RegistryRuntime,
    RegistryServiceError,
    RuntimeActivationError,
)
from custom_components.benni_core_contracts.registry_store import (
    InMemoryLastKnownGoodCache,
    PostgresRegistryRepository,
)
from custom_components.benni_core_contracts.schema import (
    ContractFieldSchema,
    ContractSchema,
    SchemaRegistry,
    ValueType,
)
from custom_components.benni_core_contracts.source_binding_evidence import (
    source_binding_matrix_v1,
)

from tests.test_registry_store import _PostgresFake


UTC = timezone.utc
CONTRACT_ID = "media.activity.v1"


def make_schema_registry() -> SchemaRegistry:
    return SchemaRegistry(
        (
            ContractSchema(
                schema_id="media_activity",
                version=1,
                fields=(
                    ContractFieldSchema(
                        name="active",
                        value_type=ValueType.BOOLEAN,
                        required=True,
                        fallback=FallbackPolicy(action=FallbackAction.REJECT),
                        freshness_ttl_seconds=60,
                    ),
                ),
            ),
        )
    )


def make_binding(
    profile: ProfileId,
    *,
    entity_id: str | None = None,
    binding_id: str = "media_activity_source",
) -> SourceBinding:
    return SourceBinding(
        binding_id=binding_id,
        source_id=f"source.{profile.value}.{binding_id}",
        entity_id=entity_id or f"sensor.{profile.value}_media_activity",
        field="active",
        capability="media_activity",
        profile_id=profile,
        required=True,
        freshness_ttl_seconds=60,
    )


def make_payload(
    profile: ProfileId,
    *,
    entity_id: str | None = None,
    binding_id: str = "media_activity_source",
) -> RegistryPayload:
    binding = make_binding(profile, entity_id=entity_id, binding_id=binding_id)
    return RegistryPayload(
        profile=profile,
        bindings=(binding,),
        fusions=(
            Fusion(
                fusion_id=f"{profile.value}.media_activity_fusion",
                contract_id=CONTRACT_ID,
                field="active",
                input_binding_ids=(binding.binding_id,),
            ),
        ),
        contract_instances=(
            {
                "contract_id": CONTRACT_ID,
                "schema_id": "media_activity",
                "schema_version": 1,
                "profile": profile.value,
            },
        ),
    )


def make_graph(
    payload: RegistryPayload,
    schema_registry: SchemaRegistry,
    now: datetime,
    *,
    value: bool,
) -> SignalGraph:
    graph = SignalGraph(
        registry=schema_registry,
        now_factory=lambda: now,
        profile=payload.profile,
    )
    for binding in payload.bindings:
        graph.add_binding(binding)
    graph.add_fusions(payload.fusions)
    for binding in payload.bindings:
        graph.ingest(
            binding.binding_id,
            RawObservation(
                source_id=binding.source_id,
                entity_id=binding.entity_id,
                value=value,
                evidence=TemporalEvidence(
                    received_at=now,
                    origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                    device_timestamp=now - timedelta(seconds=1),
                ),
            ),
            now=now,
        )
    graph.evaluate_contract(
        CONTRACT_ID,
        "media_activity",
        schema_version=1,
        now=now,
    )
    return graph


def make_revision(
    payload: RegistryPayload,
    number: int,
    revision_id: str,
    now: datetime,
) -> RegistryRevision:
    return RegistryRevision(
        id=revision_id,
        revision=number,
        profile=payload.profile,
        schema_version=1,
        payload=payload,
        status=RevisionStatus.ACTIVE,
        created_at=now,
        activated_at=now,
    )


def observation(binding: SourceBinding, value: bool, now: datetime) -> RawObservation:
    return RawObservation(
        source_id=binding.source_id,
        entity_id=binding.entity_id,
        value=value,
        evidence=TemporalEvidence(
            received_at=now,
            origin=FreshnessOrigin.DEVICE_TIMESTAMP,
            device_timestamp=now - timedelta(seconds=1),
        ),
    )


class ProfileIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
        self.schemas = make_schema_registry()

    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def test_benni_and_eltern_are_productive_profiles_of_one_engine(self) -> None:
        benni = profile_definition(ProfileId.BENNI)
        eltern = profile_definition(ProfileId.ELTERN)

        self.assertEqual(benni.schema_ids, eltern.schema_ids)
        for definition in (benni, eltern):
            self.assertTrue(definition.productive_target)
            self.assertTrue(definition.config_activation_allowed)
            self.assertTrue(definition.shadow_runtime_allowed)
        self.assertNotEqual(benni.activation_scope, eltern.activation_scope)

    def test_payload_and_graph_reject_cross_profile_bindings(self) -> None:
        with self.assertRaises(ValueError):
            RegistryPayload(
                profile=ProfileId.ELTERN,
                bindings=(make_binding(ProfileId.BENNI),),
            )
        with self.assertRaises(ValueError):
            RegistryPayload(
                profile=ProfileId.ELTERN,
                contract_instances=(
                    {
                        "contract_id": CONTRACT_ID,
                        "schema_id": "media_activity",
                        "schema_version": 1,
                        "profile": ProfileId.BENNI.value,
                    },
                ),
            )

        graph = SignalGraph(profile=ProfileId.ELTERN)
        with self.assertRaises(GraphError):
            graph.add_binding(make_binding(ProfileId.BENNI))

    def test_runtime_rejects_cross_profile_graph_without_replacing_target(self) -> None:
        parent_payload = make_payload(ProfileId.ELTERN)
        benni_payload = make_payload(ProfileId.BENNI)
        runtime = RegistryRuntime(schema_registry=self.schemas)
        parent_revision = make_revision(parent_payload, 7, "eltern-7", self.now)

        with self.assertRaises(RuntimeActivationError):
            runtime.activate(
                parent_revision,
                make_graph(benni_payload, self.schemas, self.now, value=True),
            )
        self.assertIsNone(runtime.active(ProfileId.ELTERN))
        self.assertIsNone(runtime.active(ProfileId.BENNI))

    def test_registry_service_saves_parent_and_keeps_profile_revisions_separate(self) -> None:
        database = _PostgresFake()
        store = PostgresRegistryRepository(
            database,
            lkg_cache=InMemoryLastKnownGoodCache(),
            schema_registry=self.schemas,
            now_factory=lambda: self.now,
        )
        service = RegistryDomainService(
            store,
            schema_registry=self.schemas,
            now_factory=lambda: self.now,
        )

        parent_payload = make_payload(ProfileId.ELTERN)
        parent_draft = self.run_async(service.create_draft(ProfileId.ELTERN))
        parent_draft = self.run_async(
            service.replace_draft(parent_draft.draft_id, parent_payload)
        )
        validation = self.run_async(service.validate_draft(parent_draft.draft_id))
        self.assertTrue(validation.valid)
        parent_revision = self.run_async(
            service.save_draft(parent_draft.draft_id, expected_base_revision=0)
        )

        benni_payload = make_payload(ProfileId.BENNI)
        benni_draft = self.run_async(service.create_draft(ProfileId.BENNI))
        benni_draft = self.run_async(
            service.replace_draft(benni_draft.draft_id, benni_payload)
        )
        benni_revision = self.run_async(
            service.save_draft(benni_draft.draft_id, expected_base_revision=0)
        )

        self.assertEqual(parent_revision.profile, ProfileId.ELTERN)
        self.assertEqual(benni_revision.profile, ProfileId.BENNI)
        self.assertEqual(
            self.run_async(service.get_active(ProfileId.ELTERN)).revision.revision,
            parent_revision.revision,
        )
        self.assertEqual(
            self.run_async(service.get_active(ProfileId.BENNI)).revision.revision,
            benni_revision.revision,
        )
        self.assertEqual(
            service.runtime.graph(ProfileId.ELTERN).profile,
            ProfileId.ELTERN,
        )
        self.assertEqual(
            service.runtime.graph(ProfileId.BENNI).profile,
            ProfileId.BENNI,
        )
        self.assertEqual(
            {row["profile"] for row in database.rows.values()},
            {ProfileId.BENNI.value, ProfileId.ELTERN.value},
        )

    def test_service_rejects_cross_profile_draft_inputs(self) -> None:
        database = _PostgresFake()
        service = RegistryDomainService(
            PostgresRegistryRepository(database, schema_registry=self.schemas),
            schema_registry=self.schemas,
        )
        draft = self.run_async(service.create_draft(ProfileId.ELTERN))

        with self.assertRaises(RegistryServiceError) as context:
            self.run_async(
                service.create_binding(
                    draft.draft_id,
                    {
                        **make_binding(ProfileId.BENNI).as_dict(),
                        "profile_id": ProfileId.BENNI.value,
                    },
                )
            )
        self.assertEqual(context.exception.code, "validation_error")

        with self.assertRaises(RegistryServiceError) as context:
            self.run_async(service.replace_draft(draft.draft_id, make_payload(ProfileId.BENNI)))
        self.assertEqual(context.exception.code, "validation_error")

    def test_revision_rollback_and_lkg_are_isolated_by_profile(self) -> None:
        database = _PostgresFake()
        cache = InMemoryLastKnownGoodCache()
        store = PostgresRegistryRepository(
            database,
            lkg_cache=cache,
            schema_registry=self.schemas,
            now_factory=lambda: self.now,
        )
        parent_payload = make_payload(ProfileId.ELTERN)
        benni_payload = make_payload(ProfileId.BENNI)

        parent_first = self.run_async(store.create_revision(parent_payload))
        parent_first = self.run_async(
            store.activate_revision(parent_first.id, expected_base_revision=0)
        )
        benni_active = self.run_async(store.create_revision(benni_payload))
        benni_active = self.run_async(
            store.activate_revision(benni_active.id, expected_base_revision=0)
        )
        parent_second = self.run_async(store.create_revision(parent_payload))
        parent_second = self.run_async(
            store.activate_revision(
                parent_second.id,
                expected_base_revision=parent_first.revision,
            )
        )

        rolled_back = self.run_async(
            store.rollback(
                ProfileId.ELTERN,
                parent_first.id,
                expected_base_revision=parent_second.revision,
            )
        )
        self.assertEqual(rolled_back.profile, ProfileId.ELTERN)
        self.assertEqual(
            self.run_async(store.get_active_revision(ProfileId.ELTERN)).id,
            parent_first.id,
        )
        self.assertEqual(
            self.run_async(store.get_active_revision(ProfileId.BENNI)).id,
            benni_active.id,
        )

        database.unavailable = True
        parent_lkg = self.run_async(store.load_active(ProfileId.ELTERN))
        benni_lkg = self.run_async(store.load_active(ProfileId.BENNI))
        self.assertEqual(parent_lkg.source, RegistrySource.LAST_KNOWN_GOOD)
        self.assertEqual(parent_lkg.revision.profile, ProfileId.ELTERN)
        self.assertEqual(benni_lkg.source, RegistrySource.LAST_KNOWN_GOOD)
        self.assertEqual(benni_lkg.revision.profile, ProfileId.BENNI)
        self.assertEqual(parent_lkg.health, HealthStatus.DEGRADED)

        benni_only_cache = InMemoryLastKnownGoodCache()
        self.run_async(benni_only_cache.async_save(benni_active))
        benni_only_store = PostgresRegistryRepository(
            database,
            lkg_cache=benni_only_cache,
            schema_registry=self.schemas,
        )
        missing_parent = self.run_async(benni_only_store.load_active(ProfileId.ELTERN))
        self.assertIsNone(missing_parent.revision)
        self.assertEqual(missing_parent.health, HealthStatus.BLOCKED)

    def test_consumer_api_reads_parent_contract_and_profile_specific_metadata(self) -> None:
        runtime = RegistryRuntime(schema_registry=self.schemas)
        parent_payload = make_payload(ProfileId.ELTERN)
        benni_payload = make_payload(ProfileId.BENNI)
        runtime.activate(
            make_revision(parent_payload, 7, "eltern-7", self.now),
            make_graph(parent_payload, self.schemas, self.now, value=False),
        )
        runtime.activate(
            make_revision(benni_payload, 12, "benni-12", self.now),
            make_graph(benni_payload, self.schemas, self.now, value=True),
        )
        api = ConsumerApi(runtime, now_factory=lambda: self.now)
        try:
            parent_requirement = ConsumerRequirement.contract(
                CONTRACT_ID,
                schema_id="media_activity",
                min_supported_schema_version=1,
                required_fields=("active",),
                profile=ProfileId.ELTERN,
            )
            api.register_consumer("parent_consumer", (parent_requirement,))
            api.register_consumer(
                "benni_consumer",
                (
                    ConsumerRequirement.contract(
                        CONTRACT_ID,
                        schema_id="media_activity",
                        min_supported_schema_version=1,
                        required_fields=("active",),
                        profile=ProfileId.BENNI,
                    ),
                ),
            )

            parent = api.get_contract_snapshot(
                CONTRACT_ID,
                profile=ProfileId.ELTERN,
                required_fields=("active",),
            )
            benni = api.get_contract_snapshot(
                CONTRACT_ID,
                profile=ProfileId.BENNI,
                required_fields=("active",),
            )
            self.assertEqual(parent.status, ConsumerAccessStatus.HEALTHY)
            self.assertFalse(parent.field("active").value)
            self.assertTrue(benni.field("active").value)
            self.assertEqual(parent.revision.profile, ProfileId.ELTERN)
            self.assertEqual(parent.registry_revision, 7)
            self.assertEqual(benni.registry_revision, 12)
            self.assertEqual(api.get_quality(CONTRACT_ID, "active", profile=ProfileId.ELTERN).health, HealthStatus.HEALTHY)
            self.assertEqual(api.get_freshness(CONTRACT_ID, "active", profile=ProfileId.ELTERN), FreshnessStatus.FRESH)
            self.assertEqual(api.get_health(CONTRACT_ID, profile=ProfileId.ELTERN), HealthStatus.HEALTHY)
            self.assertEqual(
                api.resolve_binding("media_activity", profile=ProfileId.ELTERN).profile,
                ProfileId.ELTERN,
            )
            self.assertEqual(
                api.resolve_binding("media_activity", profile=ProfileId.ELTERN).entity_id,
                "sensor.eltern_media_activity",
            )
            self.assertEqual(
                api.impact_for("parent_consumer").requirements[0].status,
                ConsumerAccessStatus.HEALTHY,
            )
        finally:
            api.close()

    def test_parent_and_benni_subscriptions_are_profile_isolated(self) -> None:
        runtime = RegistryRuntime(schema_registry=self.schemas)
        parent_payload = make_payload(ProfileId.ELTERN)
        benni_payload = make_payload(ProfileId.BENNI)
        parent_graph = make_graph(parent_payload, self.schemas, self.now, value=False)
        benni_graph = make_graph(benni_payload, self.schemas, self.now, value=True)
        runtime.activate(make_revision(parent_payload, 7, "eltern-7", self.now), parent_graph)
        runtime.activate(make_revision(benni_payload, 12, "benni-12", self.now), benni_graph)
        api = ConsumerApi(runtime, now_factory=lambda: self.now)
        try:
            api.register_consumer(
                "parent_consumer",
                (ConsumerRequirement.contract(CONTRACT_ID, profile=ProfileId.ELTERN),),
            )
            api.register_consumer(
                "benni_consumer",
                (ConsumerRequirement.contract(CONTRACT_ID, profile=ProfileId.BENNI),),
            )
            parent_updates = []
            benni_updates = []
            parent_subscription = api.subscribe(
                "parent_consumer",
                parent_updates.append,
                profile=ProfileId.ELTERN,
                contract_id=CONTRACT_ID,
            )
            benni_subscription = api.subscribe(
                "benni_consumer",
                benni_updates.append,
                profile=ProfileId.BENNI,
                contract_id=CONTRACT_ID,
            )

            parent_binding = parent_payload.bindings[0]
            benni_binding = benni_payload.bindings[0]
            benni_graph.ingest(
                benni_binding.binding_id,
                observation(benni_binding, False, self.now),
                now=self.now,
            )
            self.assertTrue(benni_updates)
            self.assertFalse(parent_updates)
            self.assertEqual(benni_updates[-1].profile, ProfileId.BENNI)
            self.assertIn(ConsumerEventKind.VALUE_CHANGED, benni_updates[-1].event_kinds)

            parent_graph.ingest(
                parent_binding.binding_id,
                observation(parent_binding, True, self.now),
                now=self.now,
            )
            self.assertTrue(parent_updates)
            self.assertEqual(parent_updates[-1].profile, ProfileId.ELTERN)
            benni_count = len(benni_updates)

            changed_parent_payload = make_payload(
                ProfileId.ELTERN,
                entity_id="sensor.eltern_media_activity_new",
            )
            runtime.activate(
                make_revision(changed_parent_payload, 8, "eltern-8", self.now),
                make_graph(changed_parent_payload, self.schemas, self.now, value=True),
            )
            self.assertGreater(len(parent_updates), 1)
            self.assertEqual(len(benni_updates), benni_count)
            self.assertEqual(parent_updates[-1].profile, ProfileId.ELTERN)

            parent_count = len(parent_updates)
            runtime.activate(
                make_revision(changed_parent_payload, 9, "eltern-9", self.now),
                make_graph(changed_parent_payload, self.schemas, self.now, value=True),
            )
            self.assertEqual(len(parent_updates), parent_count)

            self.assertTrue(parent_subscription.unsubscribe())
            self.assertTrue(benni_subscription.unsubscribe())
            self.assertFalse(parent_subscription.active)
            self.assertFalse(benni_subscription.active)
            parent_graph.ingest(
                parent_binding.binding_id,
                observation(parent_binding, False, self.now),
                now=self.now,
            )
            self.assertEqual(len(parent_updates), parent_count)
        finally:
            api.close()

    def test_consumer_api_reports_profile_runtime_not_ready(self) -> None:
        runtime = RegistryRuntime(schema_registry=self.schemas)
        parent_payload = make_payload(ProfileId.ELTERN)
        runtime.activate(
            make_revision(parent_payload, 7, "eltern-7", self.now),
            make_graph(parent_payload, self.schemas, self.now, value=False),
        )
        api = ConsumerApi(runtime)
        try:
            wrong_profile_requirement = ConsumerRequirement.contract(
                CONTRACT_ID,
                profile=ProfileId.BENNI,
            )
            lookup = api.lookup_requirement(wrong_profile_requirement)
            self.assertEqual(lookup.status, ConsumerAccessStatus.RUNTIME_NOT_READY)
            with self.assertRaises(ConsumerRuntimeNotReadyError):
                api.resolve_binding("media_activity", profile=ProfileId.BENNI)
            with self.assertRaises(ConsumerRuntimeNotReadyError) as context:
                api.get_revision(ProfileId.BENNI)
            self.assertEqual(context.exception.status, ConsumerAccessStatus.RUNTIME_NOT_READY)
        finally:
            api.close()

    def test_historical_parent_evidence_never_becomes_productive_registry_config(self) -> None:
        matrix = source_binding_matrix_v1()
        parent_records = matrix.parent_future_records()
        self.assertTrue(parent_records)
        self.assertTrue(
            all(
                record.activation_scope.value == "parent_future"
                and not record.production_binding_allowed
                and not record.is_activatable_candidate
                for record in parent_records
            )
        )
        self.assertFalse(
            any(record.profile_id == ProfileId.ELTERN for record in matrix.active_candidates())
        )


if __name__ == "__main__":
    unittest.main()
