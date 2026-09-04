"""Registry UX reads must not create drafts, activate graphs or cross profiles."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.benni_core_contracts.models import ConfigModel, ProfileId, RuntimeMode
from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.shadow import ShadowRuntime
from custom_components.benni_core_contracts.registry_service import RegistryDomainService
from custom_components.benni_core_contracts.registry_store import PostgresRegistryRepository, InMemoryLastKnownGoodCache
from custom_components.benni_core_contracts.websocket_api import registry_view, select_read_runtime
from tests.test_registry_store import _PostgresFake
from tests.test_registry_service import binding_data


class RegistryViewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.database = _PostgresFake()
        self.service = RegistryDomainService(PostgresRegistryRepository(self.database, lkg_cache=InMemoryLastKnownGoodCache()))

    async def test_read_is_not_activation_or_draft_and_is_profile_scoped(self):
        for profile in ProfileId:
            draft = await self.service.async_open_draft(profile)
            await self.service.async_create_binding(draft.draft_id, binding_data(entity_id=f'sensor.{profile.value}'))
            await self.service.async_save_draft(draft.draft_id, expected_base_revision=0)
        before = self.service.runtime.graph(ProfileId.ELTERN)
        listener = Mock()
        self.service.runtime.add_listener(listener)
        view = await registry_view(self.service, None, 'eltern')
        self.assertEqual(view['registry']['profile'], 'eltern')
        self.assertEqual(view['registry']['revision']['payload']['bindings'][0]['entity_id'], 'sensor.eltern')
        self.assertTrue(all(item['profile'] == 'eltern' for item in view['revisions']))
        self.assertIs(before, self.service.runtime.graph(ProfileId.ELTERN))
        listener.assert_not_called()
        self.assertFalse(self.service._drafts)
        await self.service.async_read_active('eltern')
        self.assertIs(before, self.service.runtime.graph(ProfileId.ELTERN))
        listener.assert_not_called()

    async def test_requirements_are_filtered_before_serialization(self):
        def state(profile):
            return SimpleNamespace(requirement=SimpleNamespace(profile=profile, contract_id='activity', role=None), status=SimpleNamespace(value='healthy'))
        api = SimpleNamespace(all_impacts=lambda: [SimpleNamespace(consumer_id='core_state', requirements=[state(ProfileId.BENNI), state(ProfileId.ELTERN)])])
        view = await registry_view(self.service, api, 'eltern')
        self.assertEqual(len(view['requirements']), 1)
        self.assertEqual(view['requirements'][0]['consumer_id'], 'core_state')
        self.assertNotIn('snapshot', view['requirements'][0])

    def test_explicit_runtime_selectors_never_fallback(self):
        runtimes = {p.value: ShadowRuntime(ConfigModel(profile=p, mode=RuntimeMode.SHADOW_ONLY), SignalGraph(profile=p)) for p in ProfileId}
        self.assertIs(select_read_runtime(runtimes, profile='eltern'), runtimes['eltern'])
        self.assertIsNone(select_read_runtime(runtimes, entry_id='missing'))
        self.assertIsNone(select_read_runtime(runtimes, entry_id='benni', profile='eltern'))
        self.assertIsNone(select_read_runtime(runtimes, profile='wrong'))

    async def test_lkg_remains_readable_when_history_backend_is_unavailable(self):
        draft = await self.service.async_open_draft('eltern')
        await self.service.async_save_draft(draft.draft_id, expected_base_revision=0)
        self.database.unavailable = True
        view = await registry_view(self.service, None, 'eltern')
        self.assertTrue(view['registry']['used_last_known_good'])
        self.assertEqual(view['registry']['health'], 'degraded')
        self.assertEqual(view['history_error'], 'backend_unavailable')
        benni = await registry_view(self.service, None, 'benni')
        self.assertIsNone(benni['registry']['revision'])


if __name__ == '__main__':
    unittest.main()
