"""Real PostgreSQL gate, enabled only with an explicit disposable test DSN.

Each test owns a unique schema; no application/public schema is modified.
GitHub Actions provisions a disposable PostgreSQL service for this suite.
"""
import asyncio
import os
import unittest
from uuid import uuid4

from custom_components.benni_core_contracts.models import ProfileId
from custom_components.benni_core_contracts.registry import ConcurrencyConflict, RegistryPayload
from custom_components.benni_core_contracts.registry_store import PostgresRegistryRepository


@unittest.skipUnless(os.environ.get('CORE_CONTRACTS_TEST_DSN'), 'disposable PostgreSQL DSN not configured')
class RealPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg
        self.schema = 'core_contracts_test_' + uuid4().hex
        self.admin = await asyncpg.connect(os.environ['CORE_CONTRACTS_TEST_DSN'])
        await self.admin.execute(f'CREATE SCHEMA "{self.schema}"')
        self.pool = await asyncpg.create_pool(os.environ['CORE_CONTRACTS_TEST_DSN'], min_size=1,
            max_size=4, server_settings={'search_path':self.schema}, command_timeout=10)
        self.repository = PostgresRegistryRepository(self.pool)
        await self.repository.async_migrate()

    async def asyncTearDown(self):
        await self.pool.close()
        # Only the exact UUID-named schema created in asyncSetUp is recoverably
        # disposable test data. Never target public or application tables.
        assert self.schema.startswith('core_contracts_test_') and len(self.schema) == 52
        await self.admin.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.admin.close()

    async def test_concurrent_activation_has_one_winner_and_profile_isolation(self):
        parent = await self.repository.create_revision(RegistryPayload(profile=ProfileId.ELTERN))
        parent = await self.repository.activate_revision(parent.id, 0)
        candidates = [await self.repository.create_revision(RegistryPayload(profile=ProfileId.BENNI))
                      for _ in range(2)]
        results = await asyncio.gather(*(self.repository.activate_revision(item.id, 0)
                                        for item in candidates), return_exceptions=True)
        self.assertEqual(sum(isinstance(item, ConcurrencyConflict) for item in results), 1)
        active = await self.repository.get_active_revision(ProfileId.BENNI)
        self.assertIn(active.id, {item.id for item in candidates})
        self.assertEqual(await self.repository.get_active_revision(ProfileId.ELTERN), parent)
        newer = await self.repository.create_revision(RegistryPayload(profile=ProfileId.BENNI))
        newer = await self.repository.activate_revision(newer.id, active.revision)
        restored = await self.repository.rollback_revision(active.id, expected_base_revision=newer.revision)
        self.assertEqual(restored.id, active.id)
        self.assertEqual(await self.repository.get_active_revision(ProfileId.ELTERN), parent)
