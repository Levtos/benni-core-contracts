"""Real TLS contexts/certificates, no HA instance or production database."""
import asyncio
from contextlib import asynccontextmanager, ExitStack
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import ssl
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import asyncpg
from asyncpg import connect_utils
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from custom_components.benni_core_contracts.registry_bootstrap import (
    RegistryDatabase, _prepare_ssl_context, _verified_url, bootstrap_repository,
    validate_settings,
)
from custom_components.benni_core_contracts.models import ProfileId
from custom_components.benni_core_contracts.registry import RegistryPayload, RegistrySource
from custom_components.benni_core_contracts.registry_store import (
    PostgresRegistryRepository, InMemoryLastKnownGoodCache,
)
from tests.test_registry_store import _PostgresFake


def parse_connection(url, context=None):
    """Exercise the exact pinned parser also used on pool connection creation."""
    return connect_utils._parse_connect_dsn_and_args(
        dsn=url, host=None, port=None, user=None, password=None, passfile=None,
        database=None, ssl=context, service=None, servicefile=None,
        direct_tls=None, server_settings=None, target_session_attrs=None,
        krbsrvname=None, gsslib=None,
    )[1]


class RegistryTlsTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Public synthetic fixtures, generated before IsolatedAsyncio's loop.
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Registry test CA')])
        now = datetime.now(timezone.utc)
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=30))
              .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
              .sign(key, hashes.SHA256()))
        cls.ca = cls.root/'root.crt'
        cls.ca.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cert = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]))
                .issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=30))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
                .sign(key, hashes.SHA256()))
        cls.cert = cls.root/'client.crt'
        cls.cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        cls.key = cls.root/'client.key'
        cls.key.write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b'test-only')))
        cls.crl = cls.root/'root.crl'
        cls.crl.write_bytes(x509.CertificateRevocationListBuilder().issuer_name(name)
            .last_update(now-timedelta(hours=1)).next_update(now+timedelta(days=1))
            .sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
        cls.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.server_context.load_cert_chain(cls.cert, cls.key, password='test-only')
        cls.service = cls.root/'pg_service.conf'
        cls.service.write_text('[registry_test]\nsslrootcert='+str(cls.ca)+'\nssl_min_protocol_version=TLSv1.3\n')

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def url(self, **options):
        return 'postgresql://test:test-only@localhost/test?' + urlencode(
            {'sslrootcert': str(self.ca), **options})

    async def context(self, **options):
        return await asyncio.to_thread(_prepare_ssl_context, _verified_url(self.url(**options)))

    async def test_default_and_explicit_verify_full(self):
        for url in (self.url(), self.url(sslmode='verify-full')):
            context = await asyncio.to_thread(_prepare_ssl_context, _verified_url(url))
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            self.assertGreater(context.cert_store_stats()['x509_ca'], 0)
        with patch.dict(os.environ, {'PGSSLMODE': 'disable'}):
            self.assertTrue((await self.context()).check_hostname)

    async def test_weak_or_empty_modes_are_rejected_not_silently_ignored(self):
        for mode in ('disable', 'allow', 'prefer', 'require', 'verify-ca', ''):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_settings({'database_url': self.url(sslmode=mode)})
        self.assertIn('sslmode=verify-full', _verified_url('postgresql://localhost/db#fragment'))

    async def test_ca_client_key_password_crl_and_protocol_options(self):
        context = await self.context(sslcert=str(self.cert), sslkey=str(self.key),
            sslpassword='test-only', sslcrl=str(self.crl),
            ssl_min_protocol_version='TLSv1.2', ssl_max_protocol_version='TLSv1.3')
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.maximum_version, ssl.TLSVersion.TLSv1_3)
        self.assertTrue(context.verify_flags & ssl.VERIFY_CRL_CHECK_CHAIN)
        self.assertGreater(context.cert_store_stats()['crl'], 0)
        with self.assertRaises(ssl.SSLError):
            await self.context(sslcert=str(self.cert), sslkey=str(self.key), sslpassword='wrong')

    async def test_environment_and_postgresql_default_ca_are_preserved(self):
        url = _verified_url('postgresql://test:test-only@localhost/test')
        with patch.dict(os.environ, {'PGSSLROOTCERT':str(self.ca), 'PGSSLCERT':str(self.cert),
                                    'PGSSLKEY':str(self.key)}):
            context = await asyncio.to_thread(_prepare_ssl_context, url+'&sslpassword=test-only')
            self.assertTrue(context.check_hostname)
        with patch.object(connect_utils, '_dot_postgresql_path', side_effect=lambda name:self.root/name):
            self.assertTrue((await asyncio.to_thread(_prepare_ssl_context, url)).check_hostname)
        with patch.dict(os.environ, {'PGSERVICEFILE':str(self.service)}):
            service_context = await asyncio.to_thread(_prepare_ssl_context, url+'&service=registry_test')
            self.assertEqual(service_context.minimum_version, ssl.TLSVersion.TLSv1_3)
        with patch.dict(os.environ, {'PGSSLROOTCERT':str(self.root/'missing')}):
            self.assertTrue((await self.context()).check_hostname)  # DSN wins

    async def test_real_tls_handshake_accepts_ca_and_rejects_wrong_hostname(self):
        context = await self.context()
        # SSL MemoryBIO exercises OpenSSL chain/hostname verification without
        # sockets, PostgreSQL protocol fakes, or mocking certificate validation.
        def handshake(hostname):
            client_in, client_out, server_in, server_out = [ssl.MemoryBIO() for _ in range(4)]
            client = context.wrap_bio(client_in, client_out, server_hostname=hostname)
            server = self.server_context.wrap_bio(server_in, server_out, server_side=True)
            for _ in range(20):
                for side, outgoing, incoming in ((client,client_out,server_in), (server,server_out,client_in)):
                    try:
                        side.do_handshake()
                    except ssl.SSLWantReadError:
                        pass
                    chunk = outgoing.read()
                    if chunk:
                        incoming.write(chunk)
                if client.version() and server.version():
                    return client.selected_alpn_protocol()
            self.fail('TLS handshake did not complete')
        self.assertIsNone(handshake('localhost'))  # no HTTP ALPN
        with self.assertRaises(ssl.SSLCertVerificationError):
            handshake('wrong-host.invalid')
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # untrusted CA
        with self.assertRaises(ssl.SSLCertVerificationError):
            handshake('localhost')

    async def test_all_ssl_file_loading_is_off_loop_and_context_reused(self):
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        loads, jobs, pools, contexts = [], [], [], []

        def guard(name, original):
            def call(context, *args, **kwargs):
                self.assertNotEqual(threading.get_ident(), loop_thread, name)
                loads.append(name)
                return original(context, *args, **kwargs)
            return call

        async def executor(function, *args):
            jobs.append(function)
            return await asyncio.to_thread(function, *args)

        class Pool:
            @asynccontextmanager
            async def acquire(inner, **kwargs):
                self.assertIs(asyncio.get_running_loop(), loop)
                contexts.append(parse_connection(database._url, database._ssl_context).ssl)
                yield object()

            async def close(inner):
                self.assertIs(asyncio.get_running_loop(), loop)

        async def factory(url, **kwargs):
            self.assertIs(asyncio.get_running_loop(), loop)
            pools.append(kwargs)
            return Pool()

        database = RegistryDatabase(self.url(), pool_factory=factory, executor_job=executor)
        self.assertEqual(jobs, [])
        self.assertEqual(pools, [])
        with ExitStack() as stack:
            for name in ('load_verify_locations','load_cert_chain','load_default_certs','set_default_verify_paths'):
                stack.enter_context(patch.object(ssl.SSLContext, name, guard(name, getattr(ssl.SSLContext,name))))
            async def acquire():
                async with database.acquire():
                    pass
            await asyncio.gather(acquire(), acquire(), acquire())
            await database.close()
            await acquire()  # rebuilding a closed pool still reuses the context
        self.assertIn('load_verify_locations', loads)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(pools), 2)
        self.assertTrue(all(c is pools[0]['ssl'] for c in contexts))
        self.assertEqual(pools[0]['min_size'], 0)

    async def test_bootstrap_wires_home_assistant_executor(self):
        executor = lambda *args: asyncio.to_thread(*args)
        hass = SimpleNamespace(async_add_executor_job=executor)
        with patch('custom_components.benni_core_contracts.registry_bootstrap.HomeAssistantLastKnownGoodCache'):
            _, database = bootstrap_repository(hass, {'database_url':self.url()})
        self.assertIs(database._executor_job, executor)
        self.assertIsNone(database._pool)
        self.assertIsNone(database._ssl_context)

    async def test_ca_failure_retries_without_pool_or_insecure_fallback(self):
        factory_calls = []
        async def factory(*args, **kwargs):
            factory_calls.append(kwargs)
        database = RegistryDatabase(self.url(sslrootcert=str(self.root/'missing')), pool_factory=factory)
        for _ in range(2):
            with self.assertRaises(FileNotFoundError):
                async with database.acquire():
                    self.fail('missing trust must fail')
        self.assertEqual(factory_calls, [])
        self.assertIsNone(database._ssl_context)

    async def test_unavailable_database_uses_lkg_then_recovers_same_context(self):
        backend = _PostgresFake()
        seed = PostgresRegistryRepository(backend)
        draft = await seed.create_revision(RegistryPayload(profile=ProfileId.BENNI))
        active = await seed.activate_revision(draft.id, 0)
        cache = InMemoryLastKnownGoodCache()
        await cache.async_save(active)
        contexts = []
        class Pool:
            @asynccontextmanager
            async def acquire(inner, **kwargs):
                yield backend
        async def factory(url, **kwargs):
            contexts.append(kwargs['ssl'])
            if len(contexts) == 1:
                raise ConnectionError('offline')
            return Pool()
        database = RegistryDatabase(self.url(), pool_factory=factory)
        repository = PostgresRegistryRepository(database, lkg_cache=cache)
        failed = await repository.load_active(ProfileId.BENNI)
        self.assertEqual(failed.source, RegistrySource.LAST_KNOWN_GOOD)
        self.assertEqual(failed.revision, active)
        recovered = await repository.load_active(ProfileId.BENNI)
        self.assertEqual(recovered.source, RegistrySource.POSTGRESQL)
        self.assertEqual(recovered.revision, active)
        self.assertIs(contexts[0], contexts[1])

    async def test_explicit_context_prevents_real_asyncpg_lazy_ssl_rebuild(self):
        # Real pool + real connection parsing; the unreachable local port means
        # no DB is required. SSL loaders on the loop are fail-fast sentinels.
        database = RegistryDatabase(self.url())
        database._ssl_context = await self.context()
        database._url = database._url.replace('@localhost/', '@127.0.0.1:1/')
        with ExitStack() as stack:
            for name in ('load_verify_locations','load_cert_chain','load_default_certs','set_default_verify_paths'):
                stack.enter_context(patch.object(ssl.SSLContext,name,side_effect=AssertionError('SSL I/O on loop')))
            with self.assertRaises((OSError, TimeoutError)):
                async with database.acquire():
                    self.fail('unreachable database yielded a connection')
        self.assertIsNotNone(database._pool)
        await database.close()
