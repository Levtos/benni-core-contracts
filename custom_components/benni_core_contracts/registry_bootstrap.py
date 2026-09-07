"""HA bootstrap for the existing PostgreSQL repository, never frontend config."""
import asyncio
from contextlib import asynccontextmanager
import logging
import ssl
from urllib.parse import parse_qs, urlsplit, urlunsplit

from .registry_store import PostgresRegistryRepository, HomeAssistantLastKnownGoodCache, REGISTRY_MIGRATION_SQL

LOGGER = logging.getLogger(__name__)


def _verified_url(database_url):
    """Keep verify-full explicit, including when PGSSLMODE is set externally."""
    parts = urlsplit(database_url)
    modes = parse_qs(parts.query, keep_blank_values=True).get('sslmode')
    if modes is not None:
        if modes[-1] != 'verify-full':
            raise ValueError('Core Contracts requires sslmode=verify-full')
        return database_url
    query = parts.query + ('&' if parts.query else '') + 'sslmode=verify-full'
    return urlunsplit(parts._replace(query=query))


def _prepare_ssl_context(database_url):
    """Blocking, executor-only: preserve the pinned asyncpg 0.31.0 TLS parser.

    Its public pool API accepts a context, but has no public context builder.
    Reusing this isolated private parser preserves DSN/service/environment CA,
    CRL, client cert/key/password and protocol-version precedence without a
    second TLS implementation. Revalidate this adapter on asyncpg upgrades.
    No socket or pool is created here. Never log the DSN or parser exceptions.
    """
    from asyncpg.connect_utils import _parse_connect_dsn_and_args

    _, params = _parse_connect_dsn_and_args(
        dsn=database_url, host=None, port=None, user=None, password=None,
        passfile=None, database=None, ssl=None, service=None, servicefile=None,
        direct_tls=None, server_settings=None, target_session_attrs=None,
        krbsrvname=None, gsslib=None,
    )
    context = params.ssl
    if (not isinstance(context, ssl.SSLContext)
            or context.verify_mode != ssl.CERT_REQUIRED
            or not context.check_hostname):
        raise ValueError('Core Contracts requires verified TLS with hostname checking')
    return context


class RegistryDatabase:
    """Bounded lazy pool: startup with an unreachable DB can still load LKG."""
    def __init__(self, database_url, *, migrate=False, pool_factory=None,
                 executor_job=None):
        self._url = _verified_url(database_url)
        self._migrate = migrate
        self._factory = pool_factory
        self._pool = None
        self._ssl_context = None
        self._executor_job = executor_job or asyncio.to_thread
        self._lock = asyncio.Lock()
        self._migration_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            if self._pool is None:
                if self._ssl_context is None:
                    self._ssl_context = await self._executor_job(
                        _prepare_ssl_context, self._url)
                if self._factory is None:
                    import asyncpg
                    self._factory = asyncpg.create_pool
                self._pool = await self._factory(self._url, min_size=0, max_size=4,
                                                 timeout=5, command_timeout=10,
                                                 ssl=self._ssl_context)
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
    _verified_url(url)
    return settings


def bootstrap_repository(hass, settings):
    settings = validate_settings(settings)
    database = RegistryDatabase(settings['database_url'], migrate=settings.get('migrate',False),
                                executor_job=hass.async_add_executor_job)
    repository = PostgresRegistryRepository(database,
        lkg_cache=HomeAssistantLastKnownGoodCache(hass,'benni_core_contracts.registry_lkg'))
    return repository, database
