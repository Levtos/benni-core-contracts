# Implementierungsstatus – control#57

Stand: 2026-07-28, Benni Shadow-only Release `0.1.0`,
UX-Release-Gate in technischer Bereitstellung.

Der Release-Gate enthält keinen Deployment- oder Consumer-Schritt. Die im
vorherigen Source-Binding-Gate dokumentierten
read-only HA-State-/Domain-Snapshots bleiben historische Evidence. Die
aktuelle Probe erreichte das Einhornzentrale-Frontend, aber die read-only
State-API antwortete ohne bereitgestellte Authentifizierung mit HTTP 401.
Es wurde keine neue Live-/Registry-Evidence erfunden oder geschrieben.

## Geänderte Dateien

Neu im Repository `core-contracts`:

- Grundstruktur: `README.md`, `pyproject.toml`, `hacs.json`, `manifest.json`.
- HA-Adapter: `__init__.py`, `config_flow.py`, `websocket_api.py`,
  `source_listener.py`, `strings.json`, `translations/de.json`.
- Domain: `const.py`, `quality.py`, `models.py`, `schema.py`, `contracts.py`,
  `diagnostics.py`, `graph.py`, `storage.py`, `config_io.py`, `profiles.py`,
  `shadow.py`, `evidence_gate.py`, `source_binding_evidence.py`,
  `owner_required_gate.py`, `shadow_verification.py`, `live_evidence.py`.
- Dokumentation: `docs/architecture.md`, `docs/gate-pack-v1.md`,
  `docs/contract-evidence-gate-v1.md`, `docs/source-binding-evidence-gate-v1.md`,
  `docs/source-binding-matrix-v1.md`, `docs/benni-owner-required-field-gate-v1.md`,
  `docs/benni-shadow-contract-verification-v1.md`,
  `docs/benni-live-evidence-acquisition-v1.md`,
  `docs/benni-shadow-only-release-v1.md`, `docs/shadow-release-v1.md`,
  `docs/installation-shadow-only.md`,
  `docs/release-notes-shadow-0.1.0-alpha.1.md`, `docs/ux-contract.md`,
  `.gitlab-ci.yml`, `.github/workflows/hacs-release.yml`, `docs/ux-implementation.md`,
  `docs/ux-frontend-standard.md` und dieses Dokument.
- UX: `frontend/` mit Svelte 5/Vite, Graphite-Dark-Tokenlayer, separater
  App-Shell/Basiskomponenten-Schicht, Core-Contracts-Transportadapter und
  vier read-only Ansichten. Das Build-Artefakt liegt unter
  `custom_components/benni_core_contracts/frontend/app/`.
- Architektur- und Regeltests unter `tests/`, einschließlich der fachlichen
  Fixture-Daten in `tests/fixtures.py` und
  `tests/source_binding_fixtures.py`.
- Der neue Owner-Gate-Test liegt in `tests/test_owner_required_gate.py`.
- Die Shadow-Verifikation nutzt ergänzend
  `tests/shadow_verification_fixtures.py` und
  `tests/test_benni_shadow_contract_verification.py`.
- Das Live-Acquisition-Gate nutzt `tests/live_evidence_fixtures.py` und
  `tests/test_live_evidence_acquisition.py`; die Tests sind sanitisiert und
  greifen nicht auf ein Live-System zu.
- Der Shadow-Only-Release-Candidate-Gate nutzt
  `tests/test_shadow_only_release_candidate.py` für Modus-, ConfigEntry-,
  Paket- und 0-Entity-Boundaries.

## Implementierte Modelle

- LiveEvidenceStatus, ReadOnlySourceSnapshot, LiveFieldEvidence und
  LiveEvidenceAcquisitionReport als versionierte, nicht aktivierende
  Acquisition-Projektion für explizite sanitizierte Benni-Snapshots.
- `SourceBinding`: konkrete, read-only Quellbindung.
- `AtomicSignal`: ein Feldsignal mit TemporalEvidence und FieldQuality.
- `Fusion`: feldbezogene Auswahlstrategie über interne Signale.
- `PublishedContract`: versioniertes internes Contract-Ergebnis.
- `DiagnosticProjection`: feld-/fähigkeitsbezogene Root-Cause-Projektion.
- ConfigEntry-Modell Version 1 und Runtime-Store-Envelope Version 2. Der
  Store enthält keine Konfiguration; Import/Export läuft nur über
  `ConfigCodec` für die ConfigEntry.
- `FreshnessOrigin`, `FreshnessStatus`, `FreshnessRequirement`,
  `HealthStatus`, `QualityStatus`, `ValueState`, `SafetyStatus`,
  `FallbackAction` und `FieldQuality`.
- Opening-Physical-State-Gate: `opening_state` und `is_open` sind als
  `physical_state` markiert, verwenden zwingend `fallback=reject` und geben
  bei fehlender, stale, retained, restaurierter oder widersprüchlicher
  Evidence ausschließlich `unknown` aus. `source_unavailable`,
  `source_stale`, `source_restored` und `source_conflict` werden feldbezogen
  diagnostiziert; `SafetyStatus.UNSAFE` trennt Safety-Verbrauchbarkeit vom
  fachlichen `ValueState`.
- `EntityProjectionGate` mit exakter Allowlist und hartem Shadow-Block.
- Gemeinsame Profile `benni`/`eltern` ohne getrennte Graphlogik.
- Read-only WS-Payload-Version 1 mit fünf getrennten Befehlen,
  stabilen Objekt-IDs, Graph-Revision und revision-basierter Delta-
  Reconciliation.
- `EvidenceGateResult` und `EvidenceFieldResult` als rein interne,
  read-only Contract-Evidence-Prüfung. Required-Evidence kann `pass`,
  `degraded` oder `blocked` sein; daraus folgt keine Consumer- oder
  Entity-Freigabe.
- `BindingEvidenceClass`, `SourceBindingEvidence` und
  `SourceBindingEvidenceMatrix` als versionierte, nicht aktivierende
  Source-Binding-Evidence. Matrix v1 enthält 81 Datensätze, davon 43 im
  `benni_production`- und 38 im `parent_future`-Scope. 27 Benni-Kandidaten
  sind im aktiven Evidence-Scope sichtbar; kein Record autorisiert Aktivierung.
- `ProfileScope` mit `benni_production` für Benni und `parent_future` für Eltern.
- `BenniOwnerRequiredFieldGate` v1 mit elf expliziten Required-Field-Regeln
  aus den vier aktuellen Contract-Schemata. Lock und Cover bleiben außerhalb
  des aktuellen Required-Schemas als Evidence-only-Fälle.
- Konkrete Evidence-Ergebnisse aus früheren read-only Snapshots bleiben
  historische Evidence/Testdaten; die aktuelle RC-Probe hat keine neue
  Live-Evidence erhalten. Die kanonische Benni-Lock-ID ist
  `lock.flur_aqara_smart_lock_u200`; die historische Import-ID bleibt nur als
  `historical_source_entity` und der Lock bleibt wegen fehlender Gerätezeit-
  und Ownership-Evidence blockiert.
- `ShadowSourceObservation`, `ShadowFieldVerification`,
  `ShadowContractVerification`, `BenniShadowVerificationReport` und
  `ShadowEvidenceOnlyVerification` als versionierte, read-only Benni-
  Shadow-Projektionen. Sie enthalten Source-State/Attribute, aktive Quelle,
  Fallback-Kette, Root-Cause/Reason-Codes, Capability-/Consumer-Auswirkung und
  getrennte Quality-/Health-/Freshness-/Safety-Felder; sie können keine
  ConfigEntry aktivieren oder Entity erzeugen.

## Erste Contracts

Die Registry enthält `room_climate.v1`, `opening.v1`,
`weather_environment.v1` und `technical_device.v1`. Sie besitzen keine
historischen Device-/Combined-/Master-Basisklassen und keine automatische
Entity-Projektion.

## Tests

Die Tests sind als stdlib-only `unittest`-Suite angelegt. Ausgeführt wurden
Syntaxkompilierung und 122 Unit-/Architekturtests:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

Ergebnis: **122 Tests grün**; `python -m compileall -q custom_components tests`
war ebenfalls erfolgreich. **4 JSON-Dateien**, **1 TOML-Datei** und **57
Textdateien** wurden ohne Syntax- bzw. Whitespace-Befund geprüft. Der
vollständige Feld-/Fixture-/Boundary-Audit ist in
`docs/source-binding-evidence-gate-v1.md` und
`docs/source-binding-matrix-v1.md` sowie
`docs/benni-owner-required-field-gate-v1.md` und
`docs/benni-shadow-contract-verification-v1.md` sowie
`docs/benni-live-evidence-acquisition-v1.md` dokumentiert.

## Offene Architekturfragen

- Welche konkreten Produktionsquellen dürfen später als SourceBindings in
  welchem Profil eingetragen werden?
- Welche der festgelegten Required-Felder können nach separater Live-Evidence
  tatsächlich als aktuelle SourceBinding beobachtet werden?
- Welche Quellen benötigen künftig `device_timestamp_required` statt der v1-
  Regel `device_or_ha_event`?
- Soll ein späterer Published-Modus nur einzelne Contract-Entities oder
  bewusst aggregierte Projektionen zulassen?
- Welche WS-Payload-Grenzen und Auth-/Admin-Berechtigungsdetails gelten für
  spätere Config-Schreibbefehle und eine künftige Umbrella UX?
- Welche produktiven SourceBindings lassen sich für die synthetischen
  Contract-Evidence-Fixtures tatsächlich belegen?
- Wie werden die festgelegten Required-Felder und Safety-Evidence fachlich
  durch die Owner bestätigt?
- Welche aktuelle read-only Live-Evidence darf im nächsten separaten Schritt
  dem Shadow-Report vorgelegt werden, ohne eine SourceBinding zu aktivieren?

## Evidenzlücken

- Die bisherigen read-only Live-State-/Domain-Snapshots sind zeitlich ältere
  Source-Binding-Evidence. Für dieses Gate stand keine neue Live-/Registry-
  Revalidierung zur Verfügung; daher bleiben aktuelle Required-Felder
  `blocked`/`OFFEN` statt geschätzt.
- Keine produktive ConfigEntry, Registry, Gerätequelle oder bestehender
  Consumer wurde verändert; core-contracts wurde nicht aktiviert.
- Live-Evidence belegt Entity-/State-/Attribut-Existenz, aber keine
  zuverlässigen Gerätezeitstempel und keine Produktionsfreigabe.
- Die kanonische Benni-Live-Lock-ID ist eindeutig in der Matrix; die alte
  Import-ID ist nur historische Evidence. Lock-Ownership und Gerätezeitpfad
  bleiben offen. Eltern hat keine live gefundene Cover-/Lock-Quelle und zwei
  Weather-Konfliktquellen.
- Die Matrix ist Evidence und Testdaten; sie darf nicht stillschweigend als
  ConfigEntry-Konfiguration exportiert oder aktiviert werden.
- Ein Rollo-Teilfehler ist nur als technischer `device_state` abgebildet;
  Zielposition, Privatsphäre, Hitze und andere Policy-Semantik bleiben offen.

## Source Binding Evidence Gate v1

- Evidence-Klassen bleiben auf die sechs festgelegten Werte begrenzt.
- `device_timestamp`, echter non-retained `ha_timestamp`, retained MQTT,
  Restore, unknown und received_at sind getrennt dokumentiert.
- Safety-Regel: Opening darf bei fehlender Evidence nicht `open`/`closed`
  behaupten; Lock und Cover-Position bleiben bei fehlender belastbarer Quelle
  `unknown` und verwenden `reject`.
- Benni und Eltern verwenden dieselben Matrix-/Fixture-Funktionen; nur
  Quellen, Räume, Bindings und Fähigkeiten unterscheiden sich.
- Produktive ConfigEntry-Bindings bleiben **0**; öffentliche Entities bleiben
  **0**.

## Benni Owner-/Required-Field-Gate v1

- Benni ist der einzige produktive Ziel-Scope (`benni_production`); Eltern ist
  vollständig `parent_future`/`out_of_scope`.
- Required-Felder sind festgelegt: drei raumbezogene Climate-Temperaturen und
  Availability-Gates, Opening-State und Availability, Outdoor-Temperatur und
  Availability sowie technische Rollo-Availability.
- `pass` erfordert zulässige frische Evidence; `degraded` bleibt sichtbar und
  nicht bereit; `blocked` gilt bei fehlender, retained, restaurierter, stale,
  konfliktärer oder zeitlich nicht belegter Evidence.
- Physische Zustände bleiben bei nicht bestandener Evidence `unknown`; Lock und
  Cover-Position sind nicht Teil des v1-Required-Schemas und bleiben
  Evidence-only/blockiert.
- Kein Gate-Ergebnis setzt `activation_allowed=true`.

## Benni Read-Only Shadow Contract Verification Gate v1

- `ShadowRuntime.benni_contract_verification()` führt die bestehende
  Signalgraph-Evaluation in eine versionierte, interne Benni-
  Evidence-Projektion über. Das Ergebnis enthält Contract-/Feldstatus,
  tatsächlichen Wert oder `unknown`, Source-State/Attribute, aktive Quelle,
  Fallback-Kette, Quality, Health, Freshness, Safety, Root-Cause,
  Capability-/Consumer-Auswirkung und 0 öffentliche Entity-IDs.
- Ohne aktuelle explizite Source-Observation wird selbst ein vorher gesund
  bewerteter Graph-Contract `blocked` beziehungsweise bei optionalen Feldern
  `degraded`; historische Snapshots und Fixtures werden nicht als Live-Pass
  weiterverwendet.
- Synthetische Tests belegen pass, missing/unavailable/unknown, stale,
  retained MQTT, Restore, Konflikt, `first_healthy`-Fallback, feldlokale
  Weather-Degradierung, Lock-Blocker, Eltern-Ablehnung und die Boundary.
- Lock und Cover-Position bleiben Evidence-only. Die alte Lock-ID wird nicht
  als aktuelle Binding akzeptiert; die kanonische Kandidaten-ID bleibt ohne
  neue Ownership-/Gerätezeit-Evidence `blocked`/`conflict`.

## Benni Live Evidence Acquisition Gate v1

- Die Frontend-Probe gegen Einhornzentrale (192.168.178.106:8123) war
  erreichbar (HTTP 200); /api/, /api/states und /api/config antworteten ohne
  Authentifizierung mit HTTP 401.
- Es wurde kein Token, Cookie oder Live-Connector verwendet. Aktuelle
  Entity-States, last_changed, last_updated, Gerätezeitstempel,
  Event-Herkunft, retained/restore/stale und Source-Ownership bleiben OPEN.
- Lokale import.yaml- und Dokumentationsreferenzen sind KONFIGURIERT oder
  DOKUMENTIERT, aber keine aktuelle Live-Evidence. Die Source-Binding-Matrix
  v1 wurde nicht mit neuen LIVE_VERIFIZIERT-Einträgen ergänzt.
- Room Climate (living, kitchen, bathroom), Opening, Weather/Environment und
  Technical Device bleiben ohne aktuelle Snapshots im Required-Gate blocked.
- Lock bleibt Evidence-only/conflict mit der kanonischen Kandidaten-ID
  lock.flur_aqara_smart_lock_u200. Die historische
  lock.aqara_smart_lock_u200 bleibt unzulässige historische Evidence. Cover-
  Position bleibt ohne Gerätezeit-/Quality-Evidence blocked.
- Die Acquisition-Schicht selbst bleibt read-only: kein Netzwerkpfad, keine
  ConfigEntry-/SourceBinding-Aktivierung, keine Shadow-Live-Übernahme und
  keine Entity-Projektion.
- Benötigt werden minimierte, autorisierte read-only Snapshots für die in
  docs/benni-live-evidence-acquisition-v1.md gelisteten Quellen.

## Benni Shadow-Only Release Candidate v1

- Paketversion: `0.1.0`; Kanal: `shadow_only`; Domain:
  `benni_core_contracts`.
- Der ConfigEntry-Modus muss explizit `shadow_only` sein. Ein fehlender Modus,
  das historische `shadow` und `published` werden nicht als Default oder
  Runtime-Modus akzeptiert.
- Der ConfigEntry-Flow bietet ausschließlich `profile=benni` an. Eltern bleibt
  `parent_future`/`out_of_scope`; gemeinsamer Graph-/Fixture-Code wird nicht
  in einen zweiten Eltern-Logikbaum aufgeteilt.
- Der initiale Shadow-ConfigEntry hat keine SourceBindings und keine
  Entity-Allowlist. Matrix-/Fixture-Evidence wird nicht automatisch zur
  produktiven Konfiguration.
- `async_setup` ohne ConfigEntry sowie ein leerer `shadow_only`-ConfigEntry
  laden keine Entity-Plattform und erzeugen 0 Entities. `ShadowRuntime` und
  `EntityProjectionGate` haben im RC keinen Published-Pfad.
- Der Listener bleibt read-only und verarbeitet nur explizit konfigurierte
  States. Services, Actuation, Registry-/Consumer-Änderungen und Policy-
  Imports bleiben außerhalb des Pakets.
- `manifest.json`, `pyproject.toml` und HACS-Metadaten verwenden konsistent
  `0.1.0`. `zip_release=false` lässt HACS den synchronisierten
  Repository-Stand verwenden. Die GitLab-Pipeline ist für dieses Repository
  kein Merge-, Release- oder Abnahme-Gate; der lokale grüne Teststand ist der
  technische Nachweis. Der bestehende Mirror-/HACS-Weg veröffentlicht den
  GitHub-Stable-Release.
- Eine Installation darf nur auf Benni/Einhornzentrale und nach separater
  read-only Freigabe erfolgen. Nach technischer Bereitstellung bleibt die
  Issue-Abnahme auf `testing`, bis Benni die reale UX in HA bestätigt.

## Shadow-Only Release-Candidate-Prüfung

Die zusätzliche Boundary-Suite prüft explizit fehlenden Modus, Ablehnung von
`published`, leere Default-Bindings, leere Entity-Allowlist, Eltern-
Ablehnung, Setup ohne ConfigEntry, Setup mit leerem Shadow-ConfigEntry,
fehlende Live-Daten ohne erfundene Werte sowie die Paket-/HACS-Version.

Aktueller reproduzierbarer Teststand:

```text
python -m unittest discover -s tests -p "test_*.py" -v
Ran 124 tests ... OK
```

Live-Evidence bleibt wegen HTTP 401 des autorisierten State-API-Zugriffs
offen; der Paket-Release schließt dieses Gate nicht.

Die GitLab-CI-Suite verwendet den dedizierten, projektgebundenen Docker-Runner
`core-contracts-ci` (Runner 2) in LXC 122. Der Runner führt keine ungetaggten
Jobs aus, ist auf 15 Minuten begrenzt und ist in
[`ci-runner-core-contracts.md`](ci-runner-core-contracts.md) dokumentiert.

## HA-Entities

Erzeugt: **0**.

Der Slice lädt keine HA-Entity-Plattform, registriert keine Sensoren oder
Binary Sensors und verwendet im `shadow_only`-Modus eine leere öffentliche
Projektionsmenge. WebSocket-Antworten und Evidence-Gate-Ergebnisse sind keine
HA-Entities. Es gibt keine Policy-Imports und keine Service-/Actuation-Pfade.

## Contract Evidence Gate

Die Fixtures decken Benni, Eltern, Room Climate, Opening einschließlich
fehlender, stale, retained, restaurierter und widersprüchlicher Opening-
Quellen, Weather/Environment, Technical Device, Rollo-Teilfehler, fehlende
Quellen, retained MQTT, Restore und widersprüchliche Quellen ab. Benni und Eltern
verwenden denselben generischen Fixture-/Graph-Builder; nur Profil- und
Binding-Daten unterscheiden sich.

Der Repository-Audit gegen `architecture.md`, `gate-pack-v1.md`, dieses
Dokument und `ux-contract.md` bestätigt die Öffnungs-Härtung: Physische
Opening-Felder haben keinen Safe Default, geben bei fehlender Evidence
`unknown` aus und blockieren das Required-Gate. Die zuvor widersprüchliche
Safe-Default-Aussage in den Dokumenten wurde entfernt; die gemeinsame
`physical_state`-Schema-Invariante verhindert dieselbe Lücke in neuen Feldern.

## Abgrenzung zu control#56 / Notes 488–489

Note 488 ist als Feld-/Capability-Diagnose umgesetzt: Root Cause, Quelle,
Dauer, Consumer-Effekt und betroffene FieldQuality bleiben lokal am Feld.
Note 489 wird nicht durch eine Migration beantwortet; das neue Repository
bleibt unabhängig von Core Devices und lässt den bestehenden Legacy-/Consumer-
Bestand unangetastet. Die Freshness-Unterscheidung folgt der dort belegten
Lücke: Restore, retained MQTT, Gerätezeit und HA-Zeit werden nicht vermischt.

## Repository publication

Das Repository ist als privates GitLab-Projekt unter
`ha-platform/core-contracts` angelegt. Der synchronisierte `main`-Stand vor
diesem Release-Gate ist `b8074e73c8bf6d144efef6835586750d92d8d273`; der
GitHub-Mirror ist `Levtos/benni-core-contracts`. Der Release-Tag wird erst
nach grüner lokaler Suite auf den Release-Commit gesetzt. Diese Publikation
ändert weder Home Assistant, Registry, Deployment noch Consumer; die
fachlichen und Live-Gates bleiben offen.
