# Core Contracts repository context

The workspace-level `D:\Dokumente\GitHub\CLAUDE.md` is the canonical ownership
and workflow context. This repository owns the `benni_core_contracts` read-only
foundation and its narrowly scoped reference UX.

Before changing the frontend, use the binding UX standard from
`ha-platform/control#58` and `docs/adr/0001-ux-frontend-standard.md`. Keep the
shared app shell/design tokens/components separate from the Core-Contracts
module so the structure can later be reused by Umbrella UX work.

The current release remains shadow-only: no entities, services, policy
decisions, actuation, client-side secrets, or fleet-wide frontend migration.
