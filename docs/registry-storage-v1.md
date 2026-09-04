# Registry Storage v1

Issue #16 implements the persistence substrate for the Core-Contracts registry.
It uses the existing `SourceBinding`, `Fusion`, `SignalGraph`, schema, quality,
and profile models; it does not introduce a second graph or consumer model.

## Canonical store and migration

PostgreSQL is the canonical store for registry configuration. The idempotent
migration is [001_registry_revision.sql](../migrations/001_registry_revision.sql)
and is also exposed as `REGISTRY_MIGRATION_SQL` for an asyncpg-compatible
bootstrap. `PostgresRegistryRepository.async_migrate()` applies it explicitly;
normal reads and writes do not silently migrate the database.

The table is `core_contracts_registry_revision`:

| Column | Purpose |
| --- | --- |
| `id` | Stable UUID of the revision |
| `revision` | Monotonic database revision number |
| `profile` | `benni` or `eltern` |
| `schema_version` | Registry payload schema version, currently `1` |
| `payload` | Complete JSONB `RegistryPayload` |
| `status` | `draft`, `active`, `superseded`, or `rejected` |
| `created_at` | Creation timestamp |
| `activated_at` | Successful activation timestamp |
| `checksum` | SHA-256 of canonical JSON payload |
| `created_by` | Optional non-secret actor metadata |

The partial unique index permits at most one active revision per profile. The
payload contains `bindings`, `fusions`, `contract_instances`,
`consumer_overrides`, and `registry_metadata`, with no runtime signals,
freshness, quality, diagnostics, or secrets.

Every revision, active row, rollback target and LKG cache entry is keyed by its
explicit `profile`. Payload construction and graph validation reject a binding
or contract instance from the other profile. A missing or unavailable Eltern
registry therefore cannot fall back to Benni's revision, and vice versa.

## Revision lifecycle

`create_revision()` persists a new `draft` and never changes the active row.
`activate_revision()` locks the profile, reads the current active revision, and
compares the caller's optional `expected_base_revision` (initial state is `0`).
It then validates the full payload by building the existing signal-graph
topology. A successful activation changes the old active row to `superseded`
and the candidate to `active` in one PostgreSQL transaction.

Validation failure marks a draft `rejected` in the same transaction and leaves
the previous active row untouched. A concurrency conflict leaves the draft
unchanged. A historical `superseded` revision can be activated again for
rollback; history is never deleted.

## Last-Known-Good and degraded reads

After a committed PostgreSQL activation or a valid active read, the repository
updates the local registry-specific Last-Known-Good cache. Cache writes are
post-commit and best-effort, so a cache I/O error cannot falsely report a
failed PostgreSQL commit.

`load_active()` reads PostgreSQL first. If PostgreSQL is unavailable, it loads a
checksum- and payload-validated LKG revision and returns `health=degraded` with
`source=last_known_good`; it never returns an empty healthy registry in that
case. If the cache is absent, corrupt, stale in lifecycle state, or fails graph
validation, the result is explicitly `health=blocked`, `source=none`, and no
revision is activated. A corrupt LKG is therefore never silently used.

The cache uses its own versioned envelope and can be backed by a local async
store such as Home Assistant's `Store`; it is deliberately not the existing
runtime `StorageCodec` envelope.

## Runtime and bootstrap boundary

Runtime state, restore, quality, and freshness events have no write path into
the repository. The existing HA runtime store continues to reject `config` and
`config_entry` data. The ConfigEntry remains a small bootstrap for the selected
`benni` or `eltern` runtime mode/pilot; it is not a registry persistence
fallback and no YAML/Git write is introduced.

## Deliberate follow-up boundaries

Issue #17 adds the backend service, admin authorization, and validated write
WebSocket commands in [Registry Backend-Service v1](registry-service-v1.md).
The repository's revision, atomicity, and LKG contracts remain unchanged.
The typed Consumer API/subscriptions are documented in
[Consumer API v1](consumer-api-v1.md). Svelte registry UX, import/export
workflow, and consumer cutovers remain follow-up work.
