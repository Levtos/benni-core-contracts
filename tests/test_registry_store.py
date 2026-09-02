from __future__ import annotations

import asyncio
import copy
import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from custom_components.benni_core_contracts.models import (
    Fusion,
    ProfileId,
    SourceBinding,
)
from custom_components.benni_core_contracts.quality import HealthStatus
from custom_components.benni_core_contracts.registry import (
    ConcurrencyConflict,
    RegistryPayload,
    RegistrySource,
    RevisionStateError,
    RevisionStatus,
    RevisionValidationFailed,
)
from custom_components.benni_core_contracts.registry_store import (
    InMemoryLastKnownGoodCache,
    LastKnownGoodCodec,
    PostgresRegistryRepository,
    PostgresUnavailableError,
    REGISTRY_MIGRATION_SQL,
)


UTC = timezone.utc


class _Transaction:
    def __init__(self, connection: "_PostgresFake") -> None:
        self.connection = connection
        self.snapshot: tuple[dict[str, dict], int] | None = None

    async def __aenter__(self):
        self.snapshot = (copy.deepcopy(self.connection.rows), self.connection.next_revision)
        return self

    async def __aexit__(self, exc_type, _exc, _traceback) -> None:
        if exc_type is not None and self.snapshot is not None:
            self.connection.rows, self.connection.next_revision = self.snapshot


class _PostgresFake:
    """Small SQL-shaped fake; the production repository still speaks PostgreSQL SQL."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.next_revision = 1
        self.unavailable = False
        self.fail_activation = False

    def transaction(self) -> _Transaction:
        return _Transaction(self)

    def _check_available(self) -> None:
        if self.unavailable:
            raise ConnectionError("database unavailable")

    @staticmethod
    def _copy(row: dict | None) -> dict | None:
        return copy.deepcopy(row) if row is not None else None

    async def execute(self, query: str, *args):
        self._check_available()
        normalized = " ".join(query.lower().split())
        if normalized.startswith("select pg_advisory_xact_lock"):
            return "SELECT 1"
        if "set status = 'rejected'" in normalized:
            self.rows[str(args[0])]["status"] = "rejected"
            return "UPDATE 1"
        if "set status = 'superseded'" in normalized:
            self.rows[str(args[0])]["status"] = "superseded"
            return "UPDATE 1"
        if normalized.startswith("create table") or normalized.startswith("create unique"):
            return "CREATE"
        raise AssertionError(f"unexpected execute query: {query}")

    async def fetchrow(self, query: str, *args):
        self._check_available()
        normalized = " ".join(query.lower().split())
        if normalized.startswith("insert into"):
            revision_id, profile, schema_version, payload, status, created_at, checksum, created_by = args
            row = {
                "id": str(revision_id),
                "revision": self.next_revision,
                "profile": profile,
                "schema_version": schema_version,
                "payload": json.loads(payload),
                "status": status,
                "created_at": created_at,
                "activated_at": None,
                "checksum": checksum,
                "created_by": created_by,
            }
            self.next_revision += 1
            self.rows[row["id"]] = row
            return self._copy(row)
        if "status = 'active'" in normalized and "where profile =" in normalized:
            profile = str(args[0])
            active = [
                row
                for row in self.rows.values()
                if row["profile"] == profile and row["status"] == "active"
            ]
            return self._copy(max(active, key=lambda row: row["revision"])) if active else None
        if "set status = 'active'" in normalized:
            if self.fail_activation:
                raise ConnectionError("activation write failed")
            revision_id, activated_at = args
            row = self.rows.get(str(revision_id))
            if row is None or row["status"] not in {"draft", "superseded"}:
                return None
            row["status"] = "active"
            row["activated_at"] = activated_at
            return self._copy(row)
        if "where id =" in normalized:
            return self._copy(self.rows.get(str(args[0])))
        raise AssertionError(f"unexpected fetchrow query: {query}")

    async def fetch(self, query: str, *args):
        self._check_available()
        normalized = " ".join(query.lower().split())
        if "where profile =" in normalized:
            rows = [row for row in self.rows.values() if row["profile"] == str(args[0])]
        else:
            rows = list(self.rows.values())
        return [self._copy(row) for row in sorted(rows, key=lambda row: (row["profile"], row["revision"]))]


def good_payload() -> RegistryPayload:
    return RegistryPayload(
        profile=ProfileId.BENNI,
        bindings=(
            SourceBinding(
                binding_id="living_temperature",
                source_id="climate.living",
                entity_id="sensor.living_temperature",
                field="temperature",
                capability="room_climate",
            ),
        ),
        fusions=(
            Fusion(
                fusion_id="fusion.living_temperature",
                contract_id="room.living",
                field="temperature",
                input_binding_ids=("living_temperature",),
            ),
        ),
    )


def invalid_payload() -> RegistryPayload:
    return RegistryPayload(
        profile=ProfileId.BENNI,
        fusions=(
            Fusion(
                fusion_id="fusion.invalid",
                contract_id="room.living",
                field="temperature",
                input_binding_ids=("missing_binding",),
            ),
        ),
    )


class RegistryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 2, 20, 0, tzinfo=UTC)
        self.database = _PostgresFake()
        self.cache = InMemoryLastKnownGoodCache()
        self.store = PostgresRegistryRepository(
            self.database,
            lkg_cache=self.cache,
            now_factory=lambda: self.now,
        )

    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def test_create_and_read_revision(self) -> None:
        draft = self.run_async(self.store.create_revision(good_payload(), created_by="benni"))

        self.assertEqual(draft.status, RevisionStatus.DRAFT)
        self.assertEqual(draft.payload, good_payload())
        self.assertEqual(len(draft.checksum), 64)
        read = self.run_async(self.store.read_revision(draft.id))
        self.assertEqual(read, draft)
        self.assertEqual(self.run_async(self.store.list_revisions()), (draft,))

    def test_successful_activation_is_atomic_and_populates_lkg(self) -> None:
        draft = self.run_async(self.store.create_revision(good_payload()))

        active = self.run_async(self.store.activate_revision(draft.id, expected_base_revision=0))

        self.assertEqual(active.status, RevisionStatus.ACTIVE)
        self.assertEqual(self.run_async(self.store.get_active_revision(ProfileId.BENNI)), active)
        cached = self.run_async(self.cache.async_load(ProfileId.BENNI))
        self.assertEqual(cached, active)
        self.assertIn("JSONB", REGISTRY_MIGRATION_SQL)
        self.assertIn("status IN ('draft', 'active', 'superseded', 'rejected')", REGISTRY_MIGRATION_SQL)

    def test_failed_activation_rejects_candidate_and_preserves_previous_active(self) -> None:
        first = self.run_async(self.store.create_revision(good_payload()))
        first_active = self.run_async(self.store.activate_revision(first.id, 0))
        bad = self.run_async(self.store.create_revision(invalid_payload()))

        with self.assertRaises(RevisionValidationFailed):
            self.run_async(self.store.activate_revision(bad.id, first_active.revision))

        self.assertEqual(self.run_async(self.store.get_active_revision(ProfileId.BENNI)), first_active)
        rejected = self.run_async(self.store.get_revision(bad.id))
        self.assertIsNotNone(rejected)
        self.assertEqual(rejected.status, RevisionStatus.REJECTED)

    def test_database_failure_during_activation_rolls_back_partial_status_changes(self) -> None:
        first = self.run_async(self.store.create_revision(good_payload()))
        first_active = self.run_async(self.store.activate_revision(first.id, 0))
        candidate = self.run_async(self.store.create_revision(good_payload()))
        self.database.fail_activation = True

        with self.assertRaises(PostgresUnavailableError):
            self.run_async(self.store.activate_revision(candidate.id, first_active.revision))

        self.assertEqual(self.run_async(self.store.get_active_revision(ProfileId.BENNI)), first_active)
        self.assertEqual(self.run_async(self.store.get_revision(candidate.id)).status, RevisionStatus.DRAFT)

    def test_rollback_keeps_revision_history_and_reactivates_previous_good_revision(self) -> None:
        first = self.run_async(self.store.create_revision(good_payload()))
        first_active = self.run_async(self.store.activate_revision(first.id, 0))
        second = self.run_async(self.store.create_revision(good_payload()))
        second_active = self.run_async(
            self.store.activate_revision(second.id, first_active.revision)
        )

        rolled_back = self.run_async(
            self.store.rollback_revision(first.id, second_active.revision)
        )

        self.assertEqual(rolled_back.id, first.id)
        self.assertEqual(rolled_back.status, RevisionStatus.ACTIVE)
        self.assertEqual(self.run_async(self.store.get_revision(second.id)).status, RevisionStatus.SUPERSEDED)
        self.assertEqual(len(self.run_async(self.store.list_revisions(ProfileId.BENNI))), 2)

    def test_expected_base_revision_conflict_leaves_draft_and_active_unchanged(self) -> None:
        first = self.run_async(self.store.create_revision(good_payload()))
        first_active = self.run_async(self.store.activate_revision(first.id, 0))
        winner = self.run_async(self.store.create_revision(good_payload()))
        stale = self.run_async(self.store.create_revision(good_payload()))
        winner_active = self.run_async(
            self.store.activate_revision(winner.id, first_active.revision)
        )

        with self.assertRaises(ConcurrencyConflict) as context:
            self.run_async(self.store.activate_revision(stale.id, first_active.revision))

        self.assertEqual(context.exception.actual_base_revision, winner_active.revision)
        self.assertEqual(self.run_async(self.store.get_active_revision(ProfileId.BENNI)), winner_active)
        self.assertEqual(self.run_async(self.store.get_revision(stale.id)).status, RevisionStatus.DRAFT)

    def test_postgres_unavailable_uses_validated_lkg_with_degraded_health(self) -> None:
        draft = self.run_async(self.store.create_revision(good_payload()))
        active = self.run_async(self.store.activate_revision(draft.id, 0))
        self.database.unavailable = True

        result = self.run_async(self.store.load_active(ProfileId.BENNI))

        self.assertEqual(result.revision, active)
        self.assertEqual(result.source, RegistrySource.LAST_KNOWN_GOOD)
        self.assertEqual(result.health, HealthStatus.DEGRADED)
        self.assertEqual(result.reason, "postgres_unavailable")
        self.assertTrue(result.used_last_known_good)

    def test_postgres_unavailable_without_lkg_is_blocked_not_empty_healthy(self) -> None:
        self.database.unavailable = True

        result = self.run_async(self.store.load_active(ProfileId.BENNI))

        self.assertIsNone(result.revision)
        self.assertEqual(result.source, RegistrySource.NONE)
        self.assertEqual(result.health, HealthStatus.BLOCKED)
        self.assertEqual(result.reason, "postgres_unavailable_no_last_known_good")

    def test_corrupted_lkg_is_blocked_and_never_silently_activated(self) -> None:
        draft = self.run_async(self.store.create_revision(good_payload()))
        self.run_async(self.store.activate_revision(draft.id, 0))
        self.cache.data["revisions"]["benni"]["checksum"] = "0" * 64
        self.database.unavailable = True

        result = self.run_async(self.store.load_active(ProfileId.BENNI))

        self.assertIsNone(result.revision)
        self.assertEqual(result.source, RegistrySource.NONE)
        self.assertEqual(result.health, HealthStatus.BLOCKED)
        self.assertEqual(result.reason, "last_known_good_invalid")

    def test_graph_invalid_lkg_is_blocked_even_when_checksum_is_valid(self) -> None:
        invalid = self.run_async(self.store.create_revision(invalid_payload()))
        invalid_active_snapshot = replace(
            invalid,
            status=RevisionStatus.ACTIVE,
            activated_at=self.now,
        )
        self.cache.data = LastKnownGoodCodec.encode((invalid_active_snapshot,))
        self.database.unavailable = True

        result = self.run_async(self.store.load_active(ProfileId.BENNI))

        self.assertIsNone(result.revision)
        self.assertEqual(result.health, HealthStatus.BLOCKED)
        self.assertEqual(result.reason, "last_known_good_invalid")

    def test_runtime_cache_codec_accepts_only_active_revision_snapshots(self) -> None:
        draft = self.run_async(self.store.create_revision(good_payload()))
        active = self.run_async(self.store.activate_revision(draft.id, 0))
        encoded = LastKnownGoodCodec.encode((active,))

        decoded = LastKnownGoodCodec.decode(encoded, ProfileId.BENNI)

        self.assertEqual(decoded, active)
        self.assertEqual(encoded["revisions"]["benni"]["status"], "active")

    def test_runtime_cache_codec_rejects_draft_as_last_known_good(self) -> None:
        draft = self.run_async(self.store.create_revision(good_payload()))

        with self.assertRaises(RevisionStateError):
            LastKnownGoodCodec.encode((draft,))

    def test_registry_payload_rejects_runtime_state_fields(self) -> None:
        with self.assertRaises(ValueError):
            RegistryPayload.from_dict({"runtime_state": {"signals": []}})


if __name__ == "__main__":
    unittest.main()
