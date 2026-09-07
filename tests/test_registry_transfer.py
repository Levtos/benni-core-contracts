import unittest
from copy import deepcopy
from types import SimpleNamespace

from custom_components.benni_core_contracts.registry import RegistryPayload, RegistryValidationError
from custom_components.benni_core_contracts.registry_transfer import export_document, decode_document, migration_candidates
from custom_components.benni_core_contracts.registry_service import RegistryDomainService
from custom_components.benni_core_contracts.registry_store import PostgresRegistryRepository, InMemoryLastKnownGoodCache
from tests.test_registry_service import binding_data
from tests.test_registry_store import _PostgresFake


class RegistryTransferTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db=_PostgresFake()
        self.service=RegistryDomainService(PostgresRegistryRepository(self.db,lkg_cache=InMemoryLastKnownGoodCache()))
        draft=await self.service.async_open_draft('eltern')
        await self.service.async_create_binding(draft.draft_id,binding_data())
        await self.service.async_save_draft(draft.draft_id,expected_base_revision=0)

    async def test_roundtrip_preserves_ids_metadata_and_does_not_activate_import(self):
        document=await self.service.async_export_registry('eltern')
        self.assertEqual(decode_document(document,'eltern').as_dict(),document['payload'])
        active=self.service.runtime.active('eltern')
        before=deepcopy(self.db.rows)
        result=await self.service.async_import_registry('eltern',document,expected_base_revision=active.revision.revision)
        self.assertTrue(result['validation']['valid'])
        self.assertEqual(result['draft']['payload'],document['payload'])
        self.assertEqual(self.db.rows,before)
        self.assertIs(self.service.runtime.active('eltern'),active)

    async def test_unknown_nested_fields_versions_types_and_profile_rejected(self):
        original=await self.service.async_export_registry('eltern')
        for mutate in (
            lambda d:d.update(format_version=2),
            lambda d:d.update(extra=True),
            lambda d:d['payload'].update(profile='benni'),
            lambda d:d['payload'].update(schema_version=True),
            lambda d:d['payload']['bindings'][0].update(unknown='ignored?'),
            lambda d:d['payload']['bindings'][0].update(required='false'),
            lambda d:d['payload']['bindings'][0]['fallback'].update(extra=1),
            lambda d:d['payload'].update(contract_instances=[{'contract_id':'x','schema_id':'presence','unknown':1}]),
        ):
            document=deepcopy(original); mutate(document)
            with self.subTest(document=document):
                with self.assertRaises(RegistryValidationError):
                    await self.service.async_import_registry('eltern',document,expected_base_revision=1)
        self.assertFalse(self.service._drafts)

    async def test_import_rejects_topology_errors_before_creating_draft(self):
        document=await self.service.async_export_registry('eltern')
        document['payload']['fusions']=[{'fusion_id':'missing','contract_id':'test','field':'temperature','input_binding_ids':['missing']}]
        with self.assertRaises(RegistryValidationError):
            await self.service.async_import_registry('eltern',document,expected_base_revision=1)
        self.assertFalse(self.service._drafts)

    def test_secrets_are_never_exported(self):
        for metadata in ({'password':'secret'}, {'note':'postgresql://user:password@host/db'}):
            with self.subTest(metadata=metadata):
                with self.assertRaises(RegistryValidationError):
                    export_document(RegistryPayload(registry_metadata=metadata))

    def test_suggestions_are_non_mutating_profile_scoped_and_never_dump_config(self):
        entries=[SimpleNamespace(domain=domain,data={'profile':'eltern','media_entity':'media_player.shared','password':'do-not-expose'},options={}) for domain in ('core_state','media_state')]
        entries.append(SimpleNamespace(domain='benni_only',data={'profile':'benni','entity':'media_player.shared'},options={}))
        entries.append(SimpleNamespace(domain='unscoped',data={'entity':'media_player.shared'},options={}))
        before=deepcopy(entries)
        result=migration_candidates(entries,{'media_player.shared'},'eltern')
        self.assertEqual(entries,before)
        self.assertTrue(result[0]['shared_candidate'])
        self.assertEqual({r['integration'] for r in result[0]['references']},{'core_state','media_state'})
        self.assertNotIn('password',str(result)); self.assertNotIn('do-not-expose',str(result))
        self.assertTrue(result[0]['requires_confirmation'])


if __name__ == '__main__': unittest.main()
