# Core Contracts — Registry & Exchange Foundation

Core Contracts (`benni_core_contracts`) verbindet Home-Assistant-Integrationen
über stabile, versionierte fachliche Contracts: Rohquelle/Owner → Core Contracts
→ Consumer. Die Foundation normalisiert Daten, fusioniert Quellen und liefert
Quality, Freshness, Health und Diagnose. Sie trifft keine Policy-Entscheidung
und führt keine Actuation oder HA-Service-Aufrufe aus.

## Registry, Bindings und Contracts

PostgreSQL ist der kanonische Registry-Store. Profilbezogene JSONB-Revisionen
enthalten SourceBindings, Fusionen, Contract-Instanzen und Metadaten. ConfigEntry
bleibt Bootstrap; Last Known Good (LKG) hält die letzte gültige Konfiguration
bei einem Datenbankausfall verfügbar. LKG ist keine frische Messung.

Ein SourceBinding verbindet eine stabile technische ID und Rolle mit einer
konkreten HA-Entity. Beim Gerätewechsel von HomePod zu Sonos ändert der Benutzer
die Entity, nicht die logische ID oder Consumer-Konfiguration. Anzeigenamen sind
editierbar; technische IDs und Profil sind geschützt.

Fusionen kombinieren Bindings oder andere Fusionen: `first_healthy`, `latest`,
`any_true`, `all_true` sowie die bestehenden Opening-Strategien. Fehlende Inputs,
Zyklen, falsche Typen und Profilverletzungen werden vor Aktivierung abgewiesen.
Contract-Schemata sind code-definiert und versioniert; mehrere Instanzen desselben
Schemas sind konfigurierbar. Fusion ist Datenverarbeitung, keine Heiz-, Licht-,
Media-, Wake- oder Rollo-Policy.

## Benni und Eltern

**Benni und Eltern sind Konfigurationsprofile derselben Core-Contracts-Engine
und keine getrennten Implementierungen.** Registry, Revisionen, Bindings,
Contract-Werte, Consumer-Abos und LKG bleiben strikt profilbezogen.

Historische Source-Binding-Evidence ist nicht autoritativ für die produktive
Registry. `parent_future` und `out_of_scope` in alten Evidence-Dokumenten sind
historische Prüfgrenzen, keine aktuelle Einschränkung des Elternprofils.

## Svelte-5-Verwaltung

Die HA-Seitenleiste enthält Übersicht, Registry mit Bindings, Fusionen,
Contract-Instanzen, Import/Export, Historie und Einstellungen sowie Diagnose,
Graph und Health. Echte HA-Entities sind durchsuchbar; Vorschläge benötigen
immer eine ausdrückliche Auswahl und Rollen-/Capability-Bestätigung.

Es gibt **kein Autosave**:

1. Änderungen im Entwurf bearbeiten.
2. **Prüfen** validiert ohne Persistierung/Aktivierung.
3. **Speichern** validiert erneut, erzeugt eine Revision, führt den Graph-Probelauf
   aus und aktiviert atomar nach erfolgreicher Prüfung.
4. **Verwerfen** verwirft den Entwurf, niemals die aktive Registry.
5. **Aktualisieren** liest; Dirty Values und Basisrevision bleiben erhalten.
6. **Rollback** aktiviert eine gültige historische Revision mit OCC-Prüfung.

Ein veralteter Entwurf erhält `revision_conflict`, niemals Last-Write-Wins.
Schreibaktionen benötigen HA-Admin-Rechte; der Backend-Service bleibt autoritativ.
Live-State, Freshness, Discovery und Health schreiben keine Registry-Konfiguration.

## Diagnose, Reparatur und Transfer

Die feldbezogene Diagnose zeigt Wert, Quality/Freshness/Safety, Ursache, Quellen,
Fallback, Degradierungsdauer, Consumer Impact und Registry-Revision. **Binding
bearbeiten** öffnet genau das betroffene Binding. Erst explizites Speichern
aktiviert die Reparatur; ein ungültiger Repair lässt die aktive Registry intakt.

Versionierter JSON-Export enthält Konfiguration, keine Runtime-Werte oder
Zugangsdaten. Import wird zunächst validierter Entwurf. Unbekannte Felder und
Schema-Versionen werden abgewiesen. Bulk-Auswahl und Migrationsanalyse erzeugen
nur Vorschläge, niemals produktive Zuordnungen.

## Consumer API und Public Entity Boundary

Consumer deklarieren stabile IDs und benötigte Contracts/Rollen selbst. Die
typisierte `ConsumerApi` liefert unveränderliche Snapshots, Felder, Quality,
Freshness, Health, Revision und Lineage; Subscriptions liefern relevante
Änderungen ohne Consumer-Polling. Missing, blocked, schema/version mismatch und
runtime-not-ready sind unterscheidbar. Consumer erhalten keine Repository- oder
PostgreSQL-Objekte und benötigen keine HA-Transport-Entities.

Öffentliche Entities sind eine explizite Ausnahme für Dashboard, normale
HA-Automationen oder externe Consumer. AtomicSignals, Fusion-Zwischenwerte und
Diagnose werden nicht automatisch veröffentlicht. Der historische Published-
Pilot bleibt auf `sensor.benni_opening_kitchen_patio_door` und seine geprüften
Benni-Quellen begrenzt. Der interne Betriebsmodus `shadow_only` bedeutet weiterhin
„keine Public Entities“, nicht „keine produktive Registry“.

## Installation und Entwicklerdokumentation

- [Bootstrap und Recovery](docs/registry-operations-v1.md)
- [Kanonisches Lastenheft](docs/lastenheft-registry-exchange-layer-v1.md)
- [Soll/Ist-Abnahme](docs/v1-acceptance-audit.md)
- [Registry-Storage](docs/registry-storage-v1.md) und [Domain-Service](docs/registry-service-v1.md)
- [Consumer API mit Testconsumer-Vorlage](docs/consumer-api-v1.md)
- [Registry-UX](docs/registry-ux-v1.md), [Fusion-Editor](docs/fusion-editor-v1.md)
- [Import/Export](docs/registry-import-export-v1.md), [Diagnose → Repair](docs/diagnostic-repair-v1.md)
- [Release Notes 0.2.0](docs/release-notes-0.2.0.md)

Version: **0.2.0** (Foundation v1, kein SemVer-1.0-Release). Technische Tests,
GitHub-Release und HA-Live-Abnahme sind getrennte Gates. Installation, Reload,
Deployment und echte HA-Verhaltensprüfung bleiben Benni vorbehalten.
CoreState-/MediaState-/Climate-/Blind-Cutovers sind separate Aufträge.

## Lokale Checks

```text
python -m pytest -q
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q custom_components tests scripts
python scripts/validate_repository.py
git diff --check
cd frontend
npm ci
npm run check
npm test
npm run build
```

Der echte PostgreSQL-Test benötigt eine ausdrücklich gesetzte
`CORE_CONTRACTS_TEST_DSN` zu einer wegwerfbaren Testdatenbank. Ohne diese wird nur
dieser Test übersprungen; CI stellt PostgreSQL 16 bereit. Es wird kein HA-Live-Test
durch einen SQL-Fake oder Frontend-Test ersetzt.
