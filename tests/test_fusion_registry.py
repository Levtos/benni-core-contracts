import unittest
from datetime import datetime, timezone

from custom_components.benni_core_contracts.models import Fusion, ProfileId, RawObservation
from custom_components.benni_core_contracts.quality import TemporalEvidence, FreshnessOrigin
from custom_components.benni_core_contracts.registry_service import RegistryDomainService, DraftValidationError, InvalidReferenceError
from custom_components.benni_core_contracts.registry_store import PostgresRegistryRepository, InMemoryLastKnownGoodCache
from tests.test_registry_store import _PostgresFake


class FusionRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = _PostgresFake()
        self.service = RegistryDomainService(PostgresRegistryRepository(self.db, lkg_cache=InMemoryLastKnownGoodCache()))
        self.draft = await self.service.async_open_draft('eltern')
        for name in ('mutter', 'vater', 'other'):
            await self.service.async_create_binding(self.draft.draft_id, {
                'binding_id':name, 'source_id':name, 'entity_id':f'binary_sensor.{name}',
                'field':'present', 'capability':'presence', 'profile_id':'eltern'})
        for contract in ('household', 'nested'):
            await self.service.async_create_contract_instance(self.draft.draft_id, {
                'contract_id':contract, 'schema_id':'presence', 'schema_version':1, 'profile':'eltern'})

    def fusion(self, strategy='any_true', **changes):
        return {'fusion_id':'household', 'contract_id':'household', 'field':'present',
                'input_binding_ids':['mutter','vater'], 'strategy':strategy, **changes}

    async def graph(self, strategy, values, *, nested=False):
        await self.service.async_put_fusion(self.draft.draft_id, self.fusion(strategy))
        if nested:
            await self.service.async_put_fusion(self.draft.draft_id, self.fusion(
                'all_true', fusion_id='nested', contract_id='nested', input_binding_ids=['other'], input_fusion_ids=['household']))
        await self.service.async_save_draft(self.draft.draft_id, expected_base_revision=0)
        graph = self.service.runtime.graph('eltern')
        now = datetime.now(timezone.utc)
        for name, value in values.items():
            graph.ingest(name, RawObservation(source_id=name, entity_id=f'binary_sensor.{name}', value=value,
                evidence=TemporalEvidence(received_at=now, origin=FreshnessOrigin.DEVICE_TIMESTAMP, device_timestamp=now)), now=now)
        return graph, now

    async def test_parents_presence_and_actual_nested_strategies(self):
        graph, now = await self.graph('any_true', {'mutter':True, 'vater':False, 'other':True}, nested=True)
        result = graph.evaluate_contract('nested', 'presence', now=now)
        # Flattening all leaves into all_true would incorrectly produce false.
        self.assertIs(result.values['present'], True)
        self.assertEqual(set(result.lineage['present']), {'mutter','other'})
        self.assertIsNone(self.service.runtime.graph('benni'))
        self.assertEqual({s['binding_id'] for s in graph.snapshot().signals}, {'mutter', 'vater', 'other'})

    async def test_all_true_and_missing_input(self):
        graph, now = await self.graph('all_true', {'mutter':True})
        self.assertIsNone(graph.evaluate_contract('household','presence',now=now).values['present'])
        binding = graph.binding('vater')
        graph.ingest('vater', RawObservation(source_id=binding.source_id, entity_id=binding.entity_id, value=True,
            evidence=TemporalEvidence(received_at=now, origin=FreshnessOrigin.DEVICE_TIMESTAMP, device_timestamp=now)), now=now)
        self.assertIs(graph.evaluate_contract('household','presence',now=now).values['present'], True)

    async def test_any_true_missing_is_not_false(self):
        graph, now = await self.graph('any_true', {'mutter':False})
        self.assertIsNone(graph.evaluate_contract('household','presence',now=now).values['present'])

    async def test_all_true_false_with_missing_input_is_degraded_not_true(self):
        graph, now = await self.graph('all_true', {'mutter':False})
        result = graph.evaluate_contract('household','presence',now=now)
        self.assertIs(result.values['present'], False)
        self.assertFalse(result.field_evaluations['present'].completeness)
        self.assertEqual(result.health.value, 'degraded')

    async def test_indirect_cycle_and_referenced_delete_preserve_draft(self):
        await self.service.async_put_fusion(self.draft.draft_id, self.fusion())
        await self.service.async_put_fusion(self.draft.draft_id, self.fusion(
            fusion_id='nested', contract_id='nested', input_binding_ids=[], input_fusion_ids=['household']))
        before = await self.service.async_get_draft(self.draft.draft_id)
        with self.assertRaises(DraftValidationError):
            await self.service.async_put_fusion(self.draft.draft_id, {'input_fusion_ids':['nested']}, fusion_id='household')
        with self.assertRaises(InvalidReferenceError):
            await self.service.async_delete_fusion(self.draft.draft_id, 'household')
        after = await self.service.async_get_draft(self.draft.draft_id)
        self.assertEqual(before.payload, after.payload)

    async def test_crud_invalid_topology_and_identity_are_draft_only(self):
        await self.service.async_put_fusion(self.draft.draft_id, self.fusion())
        await self.service.async_put_fusion(self.draft.draft_id, {'strategy':'all_true'}, fusion_id='household')
        for changes in ({'strategy':'policy'}, {'input_binding_ids':[]}, {'input_binding_ids':['benni_missing']}, {'input_binding_ids':[], 'input_fusion_ids':['missing']}, {'input_fusion_ids':['household']}, {'profile':'benni'}):
            with self.subTest(changes=changes):
                with self.assertRaises((DraftValidationError, ValueError, InvalidReferenceError)):
                    await self.service.async_put_fusion(self.draft.draft_id, changes, fusion_id='household')
        with self.assertRaises(InvalidReferenceError):
            await self.service.async_put_fusion(self.draft.draft_id, {'fusion_id':'rename'}, fusion_id='household')
        await self.service.async_delete_fusion(self.draft.draft_id,'household')
        draft=await self.service.async_get_draft(self.draft.draft_id)
        self.assertEqual(draft.payload.fusions, ())
        self.assertEqual(self.db.rows,{})


if __name__ == '__main__': unittest.main()
