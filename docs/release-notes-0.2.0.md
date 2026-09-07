# Core Contracts 0.2.0 — Registry & Exchange Foundation v1

## Änderungen

- #18: Svelte-5-Registry/Binding-UX, expliziter Draft-Lifecycle, Entity-Auswahl,
  stabile IDs, OCC, History/Rollback, Admin/read-only und Consumer-Nutzung.
- #19: Fusion CRUD/Editor, generische Boolean-Strategien einschließlich `all_true`,
  nested Fusion, DAG-Validierung und gemeinsames Presence-Schema.
- #22: versionierter strikter JSON-Import/Export, Bulk-Kandidaten und rein lesende
  Migrationsvorschläge; keine automatische Aktivierung.
- #23: profilbezogene Diagnose mit Binding-/Revisionskontext und direktem Repair.
- #24: PostgreSQL-Bootstrap, LKG-/Runtime-/Listener-Hardening, Contract-Instanz-UX,
  Security-/Typprüfungen, Graph-Probelauf, Evidence-Kontinuität, CI mit echtem
  PostgreSQL und vollständige Entwickler-/Betriebsdokumentation.

Die bereits gemergten #16/#17/#20/#21 bleiben die gemeinsame Architektur. Es gibt
keine zweite Registry, ConsumerApi oder Eltern-Engine. Die bestehende read-only
API und der geschützte einzelne Benni-Opening-Pilot bleiben erhalten.

## Upgrade

Siehe [Bootstrap/Recovery](registry-operations-v1.md). Neue Laufzeitabhängigkeit:
`asyncpg==0.31.0`. Die vorhandene Registry-SQL-Migration bleibt unverändert.
Es erfolgt kein automatischer Import von ConfigEntry-/Evidence-Bindings in die
produktive Registry. Bindings werden ausdrücklich über den Draft gespeichert.
Schema- und Registry-Formatversion bleiben 1; Paketversion bleibt unter 1.0.

## Gates

Lokale/CI-Ergebnisse und Merge-/Tag-SHAs werden im Abschluss-PR und in #24
protokolliert. Der Release entsteht ausschließlich über den bestehenden
GitHub-Actions-HACS-Workflow, nicht durch manuelles Anlegen eines GitHub Release.
HA-Live-Deployment und Consumer-Cutovers bleiben separat und sind hier nicht
als durchgeführt behauptet.
