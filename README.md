# Benni Core Contracts — Shadow-only `0.1.4` / Registry Backend-Service v1

`benni_core_contracts` is a new Home Assistant foundation integration built
around an internal signal graph. This installable stable release is deliberately
`shadow_only`: it can read explicitly configured source states, evaluate
versioned internal contracts, and expose diagnostics through a read-only
WebSocket foundation. It does not create Home Assistant entities, call
services, make policy decisions, or perform actuation. A separate, explicit
Published pilot exists only for the single Benni `opening.v1` contract and is
never enabled by installation or by the default ConfigEntry.

The implementation is intentionally independent of historical device,
combined and master models. The public boundary is explicit and exact: only
`sensor.benni_opening_kitchen_patio_door` may be projected after the Benni
Published pilot has been configured with the two verified raw sources. Raw
sources, AtomicSignals, Fusionen and diagnostics never become entities.

Issue #16 adds the storage foundation for the registry: PostgreSQL is the
canonical store for JSONB registry revisions, with atomic activation,
optimistic concurrency, and a validated local Last-Known-Good fallback. Issue
#17 adds the draft/validate/save/discard/rollback service and an admin-only
validated write boundary. The existing ConfigEntry remains a bootstrap for the
current runtime; it is not used as a second registry store. Consumer API,
subscriptions, and the typed internal exchange boundary are implemented in
Issue #20. Registry UX and consumer cutovers remain follow-up work.

## Status

This is the installable Shadow-only release tracked in
[GitHub issue #1](https://github.com/Levtos/benni-core-contracts/issues/1),
with the first live-testable Svelte UX.
The canonical repository and HACS source is
`Levtos/benni-core-contracts`; the release tag is `v0.1.4`. Installation
is a package distribution step only: it does not activate a ConfigEntry, create
entities, alter a registry, or constitute live approval. The UX becomes
available as a read-only Home Assistant sidebar panel after the integration is
installed and its explicit Benni ConfigEntry is loaded.

See [the architecture](docs/architecture.md), the
[Registry Storage v1](docs/registry-storage-v1.md), the
[Registry Backend-Service v1](docs/registry-service-v1.md), the
[Internal Consumer API v1](docs/consumer-api-v1.md), the
[Gate Pack v1](docs/gate-pack-v1.md), the
[Contract Evidence Gate v1](docs/contract-evidence-gate-v1.md), the
[Source Binding Evidence Gate v1](docs/source-binding-evidence-gate-v1.md),
the [Source Binding Matrix v1](docs/source-binding-matrix-v1.md), the
[Benni Owner-/Required-Field-Gate v1](docs/benni-owner-required-field-gate-v1.md),
the [Benni Shadow Contract Verification v1](docs/benni-shadow-contract-verification-v1.md)
and the
[Benni Live Evidence Acquisition v1](docs/benni-live-evidence-acquisition-v1.md)
as well as the
[implementation status](docs/implementation-status.md).

The read-only UX structure and live-install procedure are in
[ux-implementation.md](docs/ux-implementation.md). The shared standard pointer
is in [ux-frontend-standard.md](docs/ux-frontend-standard.md).

The Shadow-only release scope and boundaries are in
[Benni Shadow-Only Release Candidate v1](docs/benni-shadow-only-release-v1.md).
The separate installation procedure is in
[installation-shadow-only.md](docs/installation-shadow-only.md). Release
details are in [Shadow Release v1](docs/shadow-release-v1.md), and the tag
notes are in [release-notes-shadow-0.1.4.md](docs/release-notes-shadow-0.1.4.md).

The first explicit Published pilot is specified in
[published-opening-contract-v1.md](docs/published-opening-contract-v1.md).
The current live ConfigEntry remains Shadow-only; this branch has not changed
Home Assistant or created the pilot entity live. A later Benni-only test must
select both verified kitchen patio-door contact sources explicitly before any
entity-platform setup is allowed.

## Profiles v1 (#21)

`benni` and `eltern` are configuration profiles of the same Core-Contracts
engine. They share the SignalGraph, contract schemas, fusion, quality,
freshness, RegistryDomainService, RegistryRuntime and ConsumerApi; only their
registry payloads, revisions, bindings, instances and resulting runtime state
are profile-specific. The ConfigEntry is a bootstrap for either profile, while
PostgreSQL remains the canonical registry and the profile-specific LKG remains
the fallback.

The Source Binding Evidence Gate contains only versioned, read-only evidence
records. It does not populate the ConfigEntry or activate any binding.
The Benni Owner-/Required-Field-Gate, Shadow Contract Verification Gate and
Live Evidence Acquisition Gate are historical Benni evidence/pilot gates. Their
`parent_future`/`out_of_scope` records remain useful evidence, but are not
current profile admission and cannot activate productive bindings.
The Shadow Contract Verification Gate evaluates explicit Benni source evidence
only; absent current live evidence remains blocked and does not create a
ConfigEntry activation or an entity.
The Live Evidence Acquisition Gate documents the current read-only probe and
keeps every source OPEN when state API authentication or ownership evidence is
missing. The current ConfigEntry accepts either `profile=benni` or
`profile=eltern` with an explicit `mode=shadow_only`; there is no implicit mode
default and no public entity allowlist in the Shadow default. The separate Published
pilot is limited to the exact kitchen-patio Opening Contract described below.

The historical `v0.1.4` release is not a general public Contract publication.
The current registry/runtime foundation supports both profiles internally.
Room Climate, Weather/Environment and Technical Device results remain
internal and diagnostic. Only the explicitly configured Benni Opening pilot
may be published; Lock and Cover position remain evidence-only. Historical
Source-Binding Evidence is never authoritative product configuration and is
never promoted automatically into a productive RegistryPayload.

## Local verification

The tests use only the Python standard library so they can run without a Home
Assistant checkout:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```
