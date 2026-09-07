"""Release-gate regressions; no HA live system or production database used."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
import sys
import ssl
from unittest.mock import AsyncMock, Mock, patch

from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.models import ProfileId, RawObservation, SourceBinding
from custom_components.benni_core_contracts.quality import FreshnessOrigin, TemporalEvidence
from custom_components.benni_core_contracts.registry_bootstrap import RegistryDatabase, validate_settings
from custom_components.benni_core_contracts.source_listener import observation_from_state
from custom_components.benni_core_contracts.registry import RegistryPayload, RegistryCorruptionError
from custom_components.benni_core_contracts.registry_store import (
    PostgresRegistryRepository, PersistentLastKnownGoodCache, LastKnownGoodCodec)
from tests.test_registry_store import _PostgresFake
from custom_components.benni_core_contracts import async_setup_entry, async_unload_entry
from custom_components.benni_core_contracts.const import DOMAIN, REGISTRY_SERVICE_KEY, CONSUMER_API_KEY
from custom_components.benni_core_contracts.registry_service import RegistryDomainService


class BootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_lazy_pool_migrates_once_and_closes(self):
        calls = []

        class Connection:
            @asynccontextmanager
            async def transaction(self):
                yield self

            async def execute(self, sql):
                calls.append(sql)

        class Pool:
            @asynccontextmanager
            async def acquire(self, **kwargs):
                self.kwargs = kwargs
                yield Connection()

            async def close(self):
                calls.append('closed')

        async def factory(url, **kwargs):
            calls.append(('pool', kwargs))
            return Pool()

        database = RegistryDatabase('postgresql://test', migrate=True, pool_factory=factory)
        database._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(calls, [])
        for _ in range(2):
            async with database.acquire():
                pass
        self.assertEqual(len(calls), 3)  # pool, advisory lock, existing migration
        self.assertEqual(calls[0][1]['command_timeout'], 10)
        await database.close()
        self.assertEqual(calls[-1], 'closed')
        self.assertIsNone(database._pool)

    async def test_failed_pool_can_retry(self):
        async def unavailable(*args, **kwargs):
            raise ConnectionError('offline')
        database = RegistryDatabase('postgresql://test', pool_factory=unavailable)
        database._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                async with database.acquire():
                    self.fail('unavailable pool yielded a connection')
            self.assertIsNone(database._pool)

    def test_settings_fail_closed_without_echoing_credentials(self):
        for settings in ({'database_url': 'secret'}, {'database_url':'postgresql://test', 'migrate':'true'},
                         {'database_url':'postgresql://test', 'unknown':True}):
            with self.assertRaises(ValueError) as caught:
                validate_settings(settings)
            self.assertNotIn('secret', str(caught.exception))


class LastKnownGoodIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_saves_preserve_both_profiles_and_corruption_is_local(self):
        class Backend:
            data = None

            async def async_load(self):
                await asyncio.sleep(0)
                return self.data

            async def async_save(self, data):
                await asyncio.sleep(0)
                self.data = data

        backend = Backend()
        cache = PersistentLastKnownGoodCache(backend)
        repository = PostgresRegistryRepository(_PostgresFake())
        revisions = []
        for profile in (ProfileId.BENNI, ProfileId.ELTERN):
            draft = await repository.create_revision(RegistryPayload(profile=profile))
            revisions.append(await repository.activate_revision(draft.id, 0))
        await asyncio.gather(*(cache.async_save(revision) for revision in revisions))
        self.assertEqual(set(backend.data['revisions']), {'benni', 'eltern'})
        backend.data['revisions']['benni']['checksum'] = 'corrupt'
        self.assertEqual(await cache.async_load(ProfileId.ELTERN), revisions[1])
        with self.assertRaises(RegistryCorruptionError):
            await cache.async_load(ProfileId.BENNI)
        await cache.async_save(revisions[1])
        self.assertEqual(backend.data['revisions']['benni']['checksum'], 'corrupt')
        self.assertEqual(LastKnownGoodCodec.decode(backend.data, ProfileId.ELTERN), revisions[1])


class ConfigEntryLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_profiles_recovery_and_unload_keep_shared_panel_until_last(self):
        database = _PostgresFake()
        repository = PostgresRegistryRepository(database)
        service = RegistryDomainService(repository)
        hass = SimpleNamespace(data={DOMAIN:{REGISTRY_SERVICE_KEY:service}})
        timers, entries = [], []
        def track(_hass, callback, interval):
            self.assertEqual(interval.total_seconds(), 5)
            timers.append(callback)
            return Mock()
        event_module = SimpleNamespace(async_track_time_interval=track)
        package = 'custom_components.benni_core_contracts.'
        with (patch.dict(sys.modules, {'homeassistant.helpers.event':event_module}),
              patch(package+'HomeAssistantStorage', return_value=SimpleNamespace(async_load=AsyncMock(return_value=None))),
              patch(package+'async_register_websocket_api', new=AsyncMock()),
              patch(package+'async_attach_source_listeners', new=AsyncMock()),
              patch(package+'async_setup_view', new=AsyncMock()),
              patch(package+'async_remove_view') as remove_view):
            for profile in (ProfileId.BENNI, ProfileId.ELTERN):
                candidate = await repository.create_revision(RegistryPayload(profile=profile))
                await repository.activate_revision(candidate.id, 0)
                callbacks = []
                entry = SimpleNamespace(entry_id=profile.value, data={'profile':profile.value,'mode':'shadow_only'},
                    options={}, async_on_unload=callbacks.append, callbacks=callbacks)
                entries.append(entry)
                self.assertTrue(await async_setup_entry(hass, entry))
                self.assertEqual(hass.data[DOMAIN][entry.entry_id].graph.profile, profile)
            before = dict(database.rows)
            for _ in range(12):
                await timers[0](None)
            self.assertEqual(database.rows, before)
            api = hass.data[DOMAIN][CONSUMER_API_KEY]
            await async_unload_entry(hass, entries[0])
            for callback in entries[0].callbacks:
                callback()
            remove_view.assert_not_called()
            self.assertIsNone(service.runtime.active(ProfileId.BENNI))
            self.assertIsNotNone(service.runtime.active(ProfileId.ELTERN))
            self.assertIs(hass.data[DOMAIN][CONSUMER_API_KEY], api)
            await timers[0](None)  # an already queued callback cannot reinstall it
            self.assertIsNone(service.runtime.active(ProfileId.BENNI))
            await async_unload_entry(hass, entries[1])
            for callback in entries[1].callbacks:
                callback()
            remove_view.assert_called_once()
            self.assertNotIn(CONSUMER_API_KEY, hass.data[DOMAIN])
            self.assertEqual(service.runtime._listeners, [])


class EvidenceContinuityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.binding = SourceBinding('temperature', 'source.temperature', 'sensor.temperature',
                                     'temperature', 'room_climate')
        self.graph = SignalGraph(profile=ProfileId.BENNI)
        self.graph.add_binding(self.binding)
        self.evidence = TemporalEvidence(received_at=self.now, origin=FreshnessOrigin.DEVICE_TIMESTAMP,
                                         device_timestamp=self.now)
        self.graph.ingest(self.binding.binding_id, RawObservation(self.binding.source_id,
            self.binding.entity_id, 21.5, self.evidence))

    def test_same_source_carries_value_without_refreshing_evidence(self):
        graph = SignalGraph(profile=ProfileId.BENNI)
        graph.add_binding(replace(self.binding, display_name='New label'))
        graph.seed_unchanged_sources(self.graph)
        self.assertEqual(graph.signal('temperature').value, 21.5)
        self.assertEqual(graph.signal('temperature').evidence, self.evidence)
        self.assertEqual(self.graph.signal('temperature').evidence, self.evidence)

    def test_changed_source_or_profile_never_inherits_evidence(self):
        for binding, profile in ((replace(self.binding, entity_id='sensor.replacement'), ProfileId.BENNI),
                                 (replace(self.binding, profile_id=ProfileId.ELTERN), ProfileId.ELTERN),
                                 (replace(self.binding, enabled=False), ProfileId.BENNI)):
            graph = SignalGraph(profile=profile)
            graph.add_binding(binding)
            graph.seed_unchanged_sources(self.graph)
            self.assertIsNone(graph.signal('temperature'))

    def test_ha_adapter_normalizes_typed_values_but_not_fake_timestamps(self):
        state = SimpleNamespace(state='21.5', attributes={'device_timestamp':'invalid'}, last_updated=self.now)
        observation = observation_from_state(self.binding, state, received_at=self.now, value_type='number')
        self.assertEqual(observation.value, 21.5)
        self.assertIsNone(observation.evidence.device_timestamp)
        self.assertFalse(observation.evidence.ha_state_event)
        for invalid in ('nan', 'inf', 'unavailable'):
            state.state = invalid
            self.assertEqual(observation_from_state(self.binding, state, received_at=self.now,
                                                   value_type='number').value, invalid)
        self.assertIsNone(observation_from_state(self.binding, None, received_at=self.now).value)

    def test_presence_normalization_is_capability_scoped(self):
        state = SimpleNamespace(state='home', attributes={}, last_updated=self.now)
        presence = replace(self.binding, capability='presence', field='present')
        self.assertIs(observation_from_state(presence, state, received_at=self.now, value_type='boolean').value, True)
        self.assertEqual(observation_from_state(self.binding, state, received_at=self.now, value_type='boolean').value, 'home')

    def test_binding_inputs_are_strict_and_numbers_must_be_finite(self):
        from custom_components.benni_core_contracts.schema import ContractFieldSchema, ValueType
        for changes in ({'unknown':True}, {'required':'false'}, {'read_only':'true'},
                        {'freshness_ttl_seconds':True}, {'freshness_ttl_seconds':1.5}, {'consumer_ids':'consumer'}):
            with self.assertRaises((TypeError, ValueError)):
                SourceBinding.from_dict({**self.binding.as_dict(), **changes})
        field = ContractFieldSchema('temperature', ValueType.NUMBER)
        for invalid in (float('nan'),float('inf'),float('-inf'),True):
            self.assertFalse(field.validate(invalid))
        self.assertTrue(field.validate(21.5))
