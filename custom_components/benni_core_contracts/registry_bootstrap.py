"""HA bootstrap for the existing PostgreSQL repository, never frontend config."""
import asyncio
from contextlib import asynccontextmanager
import logging

from .registry_store import PostgresRegistryRepository, HomeAssistantLastKnownGoodCache, REGISTRY_MIGRATION_SQL

LOGGER = logging.getLogger(__name__)


class RegistryDatabase:
    """Bounded lazy pool: startup with an unreachable DB can still load LKG."""
    def __init__(self, database_url, *, migrate=False, pool_factory=None):
        self._url = database_url
        self._migrate = migrate
        self._factory = pool_factory
        self._pool = None
        self._lock = asyncio.Lock()
        self._migration_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            if self._pool is None:
                if self._factory is None:
                    import asyncpg
                    self._factory = asyncpg.create_pool
                self._pool = await self._factory(self._url, min_size=0, max_size=4,
                                                 timeout=5, command_timeout=10)
        async with self._pool.acquire(timeout=5) as connection:
            async with self._migration_lock:
                if self._migrate:
                    async with connection.transaction():
                        await connection.execute("SELECT pg_advisory_xact_lock(hashtext('core_contracts_migration'))")
                        await connection.execute(REGISTRY_MIGRATION_SQL)
                    self._migrate = False
                    LOGGER.info('registry schema migration completed')
            yield connection

    async def close(self):
        if self._pool is not None:
            try:
                await asyncio.wait_for(self._pool.close(), timeout=10)
            except TimeoutError:
                self._pool.terminate()
            finally:
                self._pool = None


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) - {'database_url','migrate'}:
        raise ValueError('invalid Core Contracts backend settings')
    url = settings.get('database_url')
    if not isinstance(url,str) or not url.startswith(('postgresql://','postgres://')):
        raise ValueError('Core Contracts requires a PostgreSQL database URL')
    if type(settings.get('migrate',False)) is not bool:
        raise ValueError('migrate must be boolean')
    return settings


def bootstrap_repository(hass, settings):
    settings = validate_settings(settings)
    url = settings['database_url']
    if 'sslmode=' not in url:
        url += ('&' if '?' in url else '?') + 'sslmode=verify-full'
    database = RegistryDatabase(url, migrate=settings.get('migrate',False))
    repository = PostgresRegistryRepository(database,
        lkg_cache=HomeAssistantLastKnownGoodCache(hass,'benni_core_contracts.registry_lkg'))
    return repository, database
