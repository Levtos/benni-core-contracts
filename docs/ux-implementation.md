# Core Contracts UX – technische Bereitstellung

Stand: 2026-07-27. Dieser Slice liefert eine echte, statisch gebündelte
Svelte-5-Ansicht für die bereits vorhandene read-only WebSocket-API von
`benni_core_contracts`. Die Ansicht ist kein Preview-Ersatz für Home
Assistant: In der installierten Panel-Instanz werden nur reale Antworten der
aktiven HA-Verbindung dargestellt. Die Umsetzung ist in
[ha-platform/control#59](https://gitlab.b-struck.de/ha-platform/control/-/work_items/59)
dokumentiert; der Code läuft über
[GitLab-MR !4](https://gitlab.b-struck.de/ha-platform/core-contracts/-/merge_requests/4).

## Schichten und Eigentum

```text
frontend/src/styles/                 Graphite-Dark-Tokens und globale Zustände
frontend/src/lib/ui/                 wiederverwendbare UI-Primitiven
frontend/src/components/shell/       App-Shell, Navigation, Topbar, Status
frontend/src/components/views/       Core-Contracts-Ansichten
frontend/src/components/contracts/   fachliche Contract-/Feld-Darstellung
frontend/src/lib/core-contracts/     Typen, WS-Adapter, Store, Preview-Fixture
custom_components/.../view.py        statischer HA-Pfad und Sidebar-Panel
```

Die Shell kennt nur die Store-Oberfläche und globale Zustände. Der
Core-Contracts-Adapter kennt ausschließlich die fünf erlaubten Commands:

```text
benni_core_contracts/list_contracts
benni_core_contracts/get_contract
benni_core_contracts/get_diagnostics
benni_core_contracts/get_graph
benni_core_contracts/get_health
```

Es gibt keinen Client-Command für ConfigEntry-Schreiben, Services,
Actuation, Policy oder Entity-Projektion. Der Store fragt zyklisch alle
read-only Payloads ab, übergibt die letzte Graph-Revision, reconciliert
Collections über stabile IDs und bewahrt Filter sowie Auswahl. Die
Detailansicht nutzt `get_contract` zusätzlich für den ausgewählten Contract.

## Ansichten und Zustände

- **Übersicht:** Contract-Liste, Revision, Gesamt-Health und feldbezogenes
  Detail mit Werten, Quellen, Freshness, Safety, Fallback und Consumer-Effekt.
- **Diagnose:** Root Cause, konkrete Quell-Entity, Beginn/Dauer und
  Feldvollständigkeit; globales `degraded` ersetzt keine Feldbewertung.
- **Signalgraph:** read-only SourceBinding-/Fusion-/Contract-Richtung.
- **Health:** zusammengefasste Health- und Reconciliation-Sicht.

Loading, ready, empty, stale, degraded, unavailable, reconnecting, offline,
error und blocked werden jeweils sichtbar dargestellt. Ein leerer oder
blockierter Runtime-Graph wird nicht durch erfundene Werte ersetzt.

Die lokale Vorschau ist ausschließlich für die Entwicklung verfügbar:

```text
npm run dev -- --open
http://127.0.0.1:4173/?preview=fixture
```

Sie trägt im UI einen deutlichen Nicht-live-Hinweis. `previewData()` wird im
Production-Build nicht automatisch gewählt; die HA-Panel-Instanz hat keinen
Fixture-Schalter. Tokens, Cookies und `SUPERVISOR_TOKEN` werden weder in den
Bundle-Code übernommen noch in LocalStorage/URL gespeichert.

## Build und Paketgrenze

Der reproduzierbare Build läuft im `frontend/`-Verzeichnis:

```text
npm ci
npm run check
npm test
npm run build
```

Vite schreibt das statische Artefakt nach
`custom_components/benni_core_contracts/frontend/app/`. Die HA-Integration
serviert es unter `/benni_core_contracts_app` und registriert nach dem
expliziten Benni-ConfigEntry das Sidebar-Panel `Core Contracts`. Das Paket
bleibt ohne `sensor.py`/`binary_sensor.py`, ohne Services und ohne öffentliche
HA-Entities.

## Technische Bereitstellung und Live-Prüfung

Die Release-Reihenfolge ist:

1. Den dokumentierten lokalen grünen Teststand als technischen Nachweis
   verwenden und den GitLab-MR regulär mergen. Eine Pipeline ist für diesen
   Core-Contracts-Slice weder Merge- noch Release- oder Abnahme-Gate.
2. Die Minor-Alpha `v0.2.0-alpha.1` auf dem GitLab-Default-Branch taggen.
3. Den bestehenden GitLab-Mirror-Job und den GitHub-HACS-Pre-Release prüfen;
   es gibt keinen manuellen GitHub-Push oder manuellen GitHub-Release.
4. Auf **Einhornzentrale** (`192.168.178.106:8123`) die installierbare
   HACS-Version auswählen und anschließend den expliziten ConfigEntry mit
   `profile=benni` und `mode=shadow_only` laden.

Die fachliche Abnahme bleibt auf `status/testing`, bis Benni die reale
Ansicht in Home Assistant auf Desktop und Lenovo M11 geprüft hat. Screenshots
sind dafür nicht erforderlich; es wird keine zusätzliche Screenshot-,
Browser-Automations- oder visuelle Testinfrastruktur eingeführt.

Für die Abnahme sind insbesondere zu prüfen:

- Panel lädt und zeigt den echten Runtime-Snapshot beziehungsweise einen
  ehrlichen `empty`/`blocked`-Zustand;
- Revision und wiederkehrende Aktualisierung funktionieren;
- Contract-Auswahl, Filter, Diagnose, Graph und Health sind bedienbar;
- Freshness, Safety, Root Cause, Quelle, Fallback, Dauer und Consumer-Effekt
  bleiben feldbezogen sichtbar;
- Touch-Ziele und responsive Navigation sind auf dem Lenovo M11 nutzbar;
- es existieren weiterhin 0 öffentliche HA-Entities und keine Aktion.

Der aktuelle Backend-Live-Evidence-Gate bleibt unabhängig von der UX offen,
wenn die Einhornzentrale keine autorisierte State-API-Evidence liefert. Die
UX darf diesen Mangel anzeigen, aber nicht mit historischen Fixtures
überdecken.

## Rollback

Der UX-Release kann ohne Datenmigration zurückgenommen werden:

1. Als unmittelbaren lokalen Stop den ConfigEntry deaktivieren/entfernen,
   falls Benni ihn für den Test angelegt hat. Dieser Schritt wird nicht
   automatisch von der UX ausgeführt.
2. Für einen dauerhaften Release-Rollback einen normalen GitLab-Revert-MR
   erstellen, mergen und den revertierten Zustand als neuen Patch-/Alpha-Tag
   veröffentlichen; die HACS-Mirror- und GitHub-Actions-Prüfungen laufen erneut
   über den bestehenden Workflow. Es gibt keinen Force-Push, keine Tag-Löschung
   und keine manuelle GitHub-Änderung.
3. Nach der geprüften Revert-Version die Einhornzentrale im freigegebenen
   Betriebsablauf aktualisieren/neuladen und prüfen, dass das Sidebar-Panel
   verschwunden ist und weiterhin keine Entities oder Services vorhanden sind.

Rollback verändert keine Contract-Storage-Daten als Teil dieses Releases und
führt keinen Consumer-Cutover aus. Eine Rückkehr von `testing` zu einem
vorherigen installierbaren Tag wird im Control-Issue mit Tag, Commit und
Prüfergebnis dokumentiert.
