# Shadow-only Alpha `0.2.0-alpha.1`

## Core-Contracts-UX

Diese Alpha ergänzt die read-only Foundation aus control#57 um eine reale,
statisch gebündelte Svelte-5-/Vite-UX für control#59:

- Core Contracts, Diagnose, Signalgraph und Health als HA-Sidebar-Panel;
- typed Adapter für die fünf bestehenden read-only WebSocket-Kommandos;
- Graph-Revision und stabile IDs für inkrementelle Reconciliation;
- sichtbare Feldwerte, Health, Freshness, Safety, Fallback, Root Cause,
  Quellen, Degradierungsdauer und Consumer-Effekt;
- Graphite-Dark-Tokenlayer, responsive Shell und touch-fähige Navigation;
- lokale Fixture-Vorschau nur im Development-Modus mit sichtbarem Nicht-live-
  Hinweis.

## Grenzen

- weiterhin `profile=benni` und ausdrücklich `mode=shadow_only`;
- weiterhin 0 HA-Entities, keine Entity-Plattform, keine Services,
  Actuation, Policy-Imports oder öffentlichen Contract-Entities;
- keine ConfigEntry-Schreibbefehle, kein zentrales Gateway, keine Umbrella UX
  und kein fleet-weites Frontend-Refactoring;
- `parent_future`/Eltern bleibt `out_of_scope`;
- keine Screenshot- oder Browser-Automationsinfrastruktur;
- keine Live-Abnahme durch den Release selbst. Die fachliche und visuelle
  Abnahme erfolgt nach Installation durch Benni auf Desktop und Lenovo M11.

## Prüfungen

Die Release-Kandidatenprüfung umfasst Python-Standardlib-Tests,
Repository-/Boundary-Checks sowie `npm run check`, `npm test` und
`npm run build`. Die installierte Version muss auf Einhornzentrale separat
geladen und dort mit realen HA-WebSocket-Payloads geprüft werden.
