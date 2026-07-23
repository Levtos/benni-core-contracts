# Benni Core Contracts — Shadow RC `0.1.0b1`

`benni_core_contracts` is a new Home Assistant foundation integration built
around an internal signal graph. This local release candidate is deliberately
`shadow_only`: it can read explicitly configured source states, evaluate
versioned internal contracts, and expose diagnostics through a read-only
WebSocket foundation. It does not create Home Assistant entities, call
services, make policy decisions, or perform actuation.

The implementation is intentionally independent of historical device,
combined and master models. A future public boundary may be explicit, but
this release candidate rejects a public entity allowlist and always projects
an empty set.

## Status

This repository is a local, not-yet-released implementation for
`ha-platform/control#57`. The package metadata identifies a pre-release Shadow
RC; it is not currently installable from HACS. No Home Assistant instance,
registry, release, or deployment was changed.

See [the architecture](docs/architecture.md), the
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

The Shadow-RC scope and boundaries are in
[Benni Shadow-Only Release Candidate v1](docs/benni-shadow-only-release-v1.md).
The planned, separately approved installation procedure is in
[installation-shadow-only.md](docs/installation-shadow-only.md); it was not
executed here. Release notes are in
[release-notes-shadow-0.1.0b1.md](docs/release-notes-shadow-0.1.0b1.md).

The Source Binding Evidence Gate contains only versioned, read-only evidence
records. It does not populate the ConfigEntry or activate any binding.
The Benni Owner-/Required-Field-Gate v1 is the only in-scope profile for this
slice; it is not a production activation. Eltern remains
`parent_future`/out_of_scope and cannot be activated.
The Shadow Contract Verification Gate evaluates explicit Benni source evidence
only; absent current live evidence remains blocked and does not create a
ConfigEntry activation or an entity.
The Live Evidence Acquisition Gate documents the current read-only probe and
keeps every source OPEN when state API authentication or ownership evidence is
missing. The ConfigEntry requires `profile=benni` and an explicit
`mode=shadow_only`; there is no implicit mode default, no parent activation,
and no public entity allowlist in this RC.

## Local verification

The tests use only the Python standard library so they can run without a Home
Assistant checkout:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```
