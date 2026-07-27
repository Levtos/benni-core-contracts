## Repository scope

`core-contracts` is a read-only Home Assistant foundation integration. The
workspace rules in `D:\Dokumente\GitHub\AGENTS.md` remain authoritative.

The UX standard is binding:

- read `ha-platform/control#58` and
  `ha-platform/control:docs/adr/0001-ux-frontend-standard.md` before UX work;
- keep the Svelte UX statically bundled, typed, and split into shared shell,
  token/component, transport, and Core-Contracts feature layers;
- expose only read-only contract, graph, health, and diagnostic data;
- do not add HA entities, services, actuation, policy logic, secrets, tokens,
  or ConfigEntry write paths;
- keep `benni_core_contracts` independent from historical Core Devices models.

The matching integration contract is `docs/ux-contract.md`; technical changes
are tracked in `ha-platform/control`.
