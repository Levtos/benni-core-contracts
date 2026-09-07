import unittest
from copy import deepcopy
from datetime import datetime, timezone

from custom_components.benni_core_contracts.diagnostics import registry_diagnostic_context
from custom_components.benni_core_contracts.models import RawObservation
from custom_components.benni_core_contracts.quality import TemporalEvidence, FreshnessOrigin
from custom_components.benni_core_contracts.registry_service import RegistryDomainService, RegistryServiceError
from custom_components.benni_core_contracts.registry_store import PostgresRegistryRepository, InMemoryLastKnownGoodCache
from tests.test_registry_store import _PostgresFake


class RegistryRepairTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnosis_to_explicit_repair_preserves_ids_and_profile(self):
        db=_PostgresFake()
        service=RegistryDomainService(PostgresRegistryRepository(db,lkg_cache=InMemoryLastKnownGoodCache()))
        draft=await service.async_open_draft('eltern')
        await service.async_create_binding(draft.draft_id,{'binding_id':'mother','source_id':'mother','entity_id':'binary_sensor.old','field':'present','capability':'presence'})
        await service.async_create_contract_instance(draft.draft_id,{'contract_id':'household','schema_id':'presence'})
        await service.async_put_fusion(draft.draft_id,{'fusion_id':'household','contract_id':'household','field':'present','input_binding_ids':['mother']})
        first=await service.async_save_draft(draft.draft_id,expected_base_revision=0)
        graph=service.runtime.graph('eltern')
        graph.evaluate_contract('household','presence')
        base={'diagnostics':[graph.diagnostic('household').as_dict()]}
        before=deepcopy(base); rows=deepcopy(db.rows)
        diagnostic=registry_diagnostic_context(base,service.runtime.active('eltern'))['diagnostics'][0]
        self.assertEqual(base,before); self.assertEqual(db.rows,rows)
        self.assertEqual(diagnostic['profile'],'eltern'); self.assertEqual(diagnostic['registry_revision'],first.revision)
        self.assertEqual(diagnostic['fields'][0]['binding_ids'],['mother'])  # Even without any observation.
        self.assertEqual(diagnostic['fields'][0]['bindings'][0]['entity_id'],'binary_sensor.old')
        edit=await service.async_open_draft('eltern')
        with self.assertRaises(RegistryServiceError):
            await service.async_update_binding(edit.draft_id,'mother',{'entity_id':'not-an-entity'})
        self.assertEqual(service.runtime.active('eltern').revision.id,first.id)
        await service.async_update_binding(edit.draft_id,'mother',{'entity_id':'binary_sensor.new'})
        await service.async_validate_draft(edit.draft_id)
        self.assertEqual(db.rows,rows)
        second=await service.async_save_draft(edit.draft_id,expected_base_revision=first.revision)
        graph=service.runtime.graph('eltern'); now=datetime.now(timezone.utc)
        graph.ingest('mother',RawObservation(source_id='mother',entity_id='binary_sensor.new',value=True,
            evidence=TemporalEvidence(received_at=now,device_timestamp=now,origin=FreshnessOrigin.DEVICE_TIMESTAMP)),now=now)
        graph.evaluate_contract('household','presence',now=now)
        current=registry_diagnostic_context({'diagnostics':[graph.diagnostic('household').as_dict()]},service.runtime.active('eltern'))['diagnostics'][0]
        self.assertEqual(current['registry_revision'],second.revision)
        self.assertIs(current['fields'][0]['value'],True)
        self.assertEqual(current['fields'][0]['bindings'][0]['binding_id'],'mother')
        self.assertEqual(current['fields'][0]['health'],'healthy')
        self.assertIsNone(service.runtime.active('benni'))
        active_rows=deepcopy(db.rows)
        for _ in range(3):
            graph.evaluate_contract('household','presence',now=now)
            registry_diagnostic_context({'diagnostics':[graph.diagnostic('household').as_dict()]},service.runtime.active('eltern'))
        self.assertEqual(db.rows,active_rows)


if __name__ == '__main__': unittest.main()
