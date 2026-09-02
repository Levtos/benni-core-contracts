# Implementierungsstatus – GitHub Issue #1

Stand: 2026-09-02, Benni Shadow-only Release `0.1.4`,
Published Options-Flow-Fix und Published Opening Contract v1 lokal
implementiert; Live-Aktivierung weiterhin ausstehend.

Der nachfolgende historische Issue-#1-Stand wird durch die Registry-Slices aus
Issue #16 und #17 ergänzt: PostgreSQL-Revisionen, atomare Aktivierung, der
validierte Last-Known-Good-Fallback und der `RegistryDomainService` liegen in
`registry.py`, `registry_store.py` und `registry_service.py`. Drafts werden nur
im Service gehalten; die getrennte Admin-Write-WebSocket-Grenze speichert nur
über explizite Save-Aktionen. Consumer-API, Svelte-UX, Fusion-Editor und
Consumer-Cutover sind nicht vorweggenommen.

Der Release-Gate enthält keinen Deployment- oder Consumer-Schritt. Die
laufende Einhornzentrale wurde nur read-only geprüft: Die Integration ist
geladen, die MQTT-Rohquellen für den Küchen-Terrassentür-Pilot sind vorhanden,
aber der aktuelle ConfigEntry bleibt Shadow-only. Es wurde keine Live-
ConfigEntry, Registry oder Home-Assistant-Datei verändert.

## Geänderte Dateien

Neu im Repository `core-contracts`:

- Grundstruktur: `README.md`, `pyproject.toml`, `hacs.json`, `manifest.json`.
- HA-Adapter: `__init__.py`, `config_flow.py`, `websocket_api.py`,
  `source_listener.py`, `published.py`, `sensor.py`, `strings.json`,
  `translations/de.json`.
- Domain: `const.py`, `quality.py`, `models.py`, `schema.py`, `contracts.py`,
  `diagnostics.py`, `graph.py`, `storage.py`, `config_io.py`, `profiles.py`,
  `shadow.py`, `evidence_gate.py`, `source_binding_evidence.py`,
  `owner_required_gate.py`, `shadow_verification.py`, `live_evidence.py`,
  `registry.py`, `registry_store.py`, `registry_service.py`.
- Migration: `migrations/001_registry_revision.sql`.
- Dokumentation: `docs/architecture.md`, `docs/gate-pack-v1.md`,
  `docs/contract-evidence-gate-v1.md`, `docs/source-binding-evidence-gate-v1.md`,
  `docs/source-binding-matrix-v1.md`, `docs/benni-owner-required-field-gate-v1.md`,
  `docs/benni-shadow-contract-verification-v1.md`,
  `docs/benni-live-evidence-acquisition-v1.md`, `docs/registry-storage-v1.md`,
  `docs/published-opening-contract-v1.md`, `docs/registry-service-v1.md`,
  `docs/benni-shadow-only-release-v1.md`, `docs/shadow-release-v1.md`,
  `docs/installation-shadow-only.md`,
  `docs/release-notes-shadow-0.1.0-alpha.1.md`, `docs/ux-contract.md`,
  `.github/workflows/hacs-release.yml`, `docs/ux-implementation.md`,
  `docs/ux-frontend-standard.md` und dieses Dokument.
- Die Repository-Gateprüfung in `scripts/validate_repository.py` erlaubt
  ausschließlich die explizite `sensor.py`-Pilotplattform und prüft weiterhin
  Shadow-0-Entity-, Service-, Actuation- und Policy-Grenzen.
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
- Der Published-Opening-Pilot wird durch `tests/test_published_opening_contract.py`
  gegen Zustandsmapping, Freshness, Konflikt-/Fallback-Semantik, Allowlist,
  Shadow-Grenze und Sensor-Plattform-Forwarding geprüft.
- Der Registry-Storage-v1-Slice wird durch `tests/test_registry_store.py` gegen
  Revisionserzeugung, atomare Aktivierung, Rollback, Concurrency-Konflikt,
  PostgreSQL-Ausfall und validierten Last-Known-Good-Fallback geprüft.
- Der Registry-Backend-Service-v1-Slice wird durch
  `tests/test_registry_service.py` und `tests/test_registry_write_api.py` gegen
  Draft-Lifecycle, Binding-/Contract-Instance-CRUD, Validierung ohne
  Persistenz, Save/Activation, Discard, Rollback, OCC, Fehlertransport,
  Backend-Ausfall und die Admin-Grenze geprüft.

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
- `RegistryPayload`, `RegistryRevision` und `RevisionStatus` für die
  PostgreSQL-Registry mit JSONB-Checksumme, atomarer Aktivierung,
  Optimistic-Concurrency und explizitem Last-Known-Good-Health-Ergebnis.
- `RegistryDraft`, `RegistryDomainService` und `RegistryRuntime` für den
  flüchtigen Edit-Stand, den validierten Save-/Rollback-Pfad und den atomaren
  Runtime-Graph-Snapshot. `SourceBinding` unterstützt dabei weiterhin stabile
  IDs sowie den editierbaren Anzeigenamen und den Aktivierungsstatus.
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
- `PublishedRuntime` und der einzige explizite Pilot
  `benni.opening.kitchen_patio_door`; seine beiden Rohquellen sind nur die
  aktuell read-only verifizierten Küchen-Terrassentür-Kontakte.
- `sensor.benni_opening_kitchen_patio_door` als einzige mögliche Entity-
  Projektion. Interne Signale, Fusionen und Diagnosen bleiben außerhalb der
  Entity-Plattform.
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
Entity-Projektion. Nur der explizite Benni-Opening-Pilot darf über die
Published-Allowlist eine Entity-Projektion anfordern.

## Tests

Die Tests sind als stdlib-only `unittest`-Suite angelegt. Für den aktuellen
Branch werden Syntaxkompilierung und 167 Unit-/Architekturtests ausgeführt:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

Ergebnis: **167 Tests grün**; `python -m compileall -q custom_components tests scripts`
war ebenfalls erfolgreich. Die Repository-Validierung prüfte **7 JSON-Dateien**,
**1 TOML-Datei** und **91 Textdateien** ohne Syntax- bzw. Whitespace-Befund.
Der
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
- Soll der einzelne Published-Pilot nach der separaten Benni-Live-Prüfung
  fachlich bestätigt werden, oder bleibt er zunächst ein technischer Pilot?
- Welche WS-Payload-Grenzen und Auth-/Admin-Berechtigungsdetails gelten für
  spätere Config-Schreibbefehle und eine künftige Umbrella UX?
- Welche produktiven SourceBindings lassen sich für die synthetischen
  Contract-Evidence-Fixtures tatsächlich belegen?
- Wie werden die festgelegten Required-Felder und Safety-Evidence fachlich
  durch die Owner bestätigt?
- Welches echte State-Change-Event und welche nicht-retained Freshness-Evidence
  kann nach der ausdrücklichen Published-ConfigEntry-Aktivierung beobachtet
  werden?

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
- Es wurde kein Token oder Cookie gespeichert. Ein autorisierter read-only
  HA-MCP-Zugriff revalidierte danach die beiden konkreten Opening-Pilot-
  Entities samt MQTT-Ownership, State und HA-Zeitstempeln. Ein Gerätezeit-
  stempel und ein expliziter Retained-Marker bleiben OPEN.
- Lokale import.yaml- und Dokumentationsreferenzen bleiben KONFIGURIERT oder
  DOKUMENTIERT. Die Source-Binding-Matrix v1 enthält für den Pilot ein
  dokumentiertes 30.07.2026-Revalidierungs-Overlay; daraus folgt keine
  ConfigEntry-Aktivierung.
- Room Climate, Weather/Environment und Technical Device bleiben ohne
  vollständige aktuelle Required-Evidence im Gate blocked. Der Opening-Pilot
  hat belegte Quellen, bleibt aber bis zum echten nicht-retained State-Change-
  Event für einen Freshness-/Published-Lauf offen.
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

- Paketversion: `0.1.4`; Kanal: `shadow_only`; Domain:
  `benni_core_contracts`.
- Der ConfigEntry-Modus muss explizit `shadow_only` sein. Ein fehlender Modus,
  das historische `shadow` wird nicht als Default oder Runtime-Modus
  akzeptiert. `published` ist ein separater, explizit eingegrenzter Pilot und
  kein Default.
- Der ConfigEntry-Flow bietet ausschließlich `profile=benni` an. Eltern bleibt
  `parent_future`/`out_of_scope`; gemeinsamer Graph-/Fixture-Code wird nicht
  in einen zweiten Eltern-Logikbaum aufgeteilt.
- Der initiale Shadow-ConfigEntry hat keine SourceBindings und keine
  Entity-Allowlist. Matrix-/Fixture-Evidence wird nicht automatisch zur
  produktiven Konfiguration.
- `async_setup` ohne ConfigEntry sowie ein leerer `shadow_only`-ConfigEntry
  laden keine Entity-Plattform und erzeugen 0 Entities. `ShadowRuntime` bleibt
  vollständig entity-frei; nur `PublishedRuntime` darf die exakt allowlistete
  Pilot-Entity über die `sensor`-Plattform weiterleiten.
- Der Listener bleibt read-only und verarbeitet nur explizit konfigurierte
  States. Services, Actuation, Registry-/Consumer-Änderungen und Policy-
  Imports bleiben außerhalb des Pakets.
- `manifest.json`, `pyproject.toml` und HACS-Metadaten verwenden konsistent
  `0.1.4`. `zip_release=false` lässt HACS den kanonischen GitHub-
  Repository-Stand verwenden. GitHub Actions ist der einzige aktuelle
  CI-/HACS-Workflow; der lokale grüne Teststand ist der technische Nachweis
  dieser Korrektur. Eine Paketpublikation aktiviert weder ConfigEntry noch
  PublishedContract.
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
Ran 137 tests ... OK
```

Die read-only Live-Evidence für die beiden Pilotquellen ist vorhanden, aber
ohne Gerätezeitstempel und ohne expliziten Retained-Nachweis. Der aktuelle
Shadow-ConfigEntry wird deshalb nicht automatisch in den Published-Modus
überführt; das nachgelagerte Live-Event-/Freshness-Gate bleibt offen.

Die frühere Runner-Dokumentation ist historische Provenienz und kein aktiver
CI-Pfad. Für diese Korrektur wurde ausschließlich die lokale Suite ausgeführt;
GitHub bleibt der aktuelle Workflow- und Dokumentationspfad.

## HA-Entities

Im aktuellen laufenden Shadow-ConfigEntry erzeugt: **0**.

Der `shadow_only`-Slice lädt keine HA-Entity-Plattform und verwendet eine
leere öffentliche Projektionsmenge. Der lokale Published-Testpfad erzeugt
genau eine mögliche `sensor.benni_opening_kitchen_patio_door` nur für einen
expliziten `PublishedRuntime`; das ist keine Live-Aktivierung. WebSocket-
Antworten und Evidence-Gate-Ergebnisse sind keine HA-Entities. Es gibt keine
Policy-Imports und keine Service-/Actuation-Pfade.

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

## Benni Published Opening Contract v1

- Der erste vertikale Published-Schnitt ist
  `benni.opening.kitchen_patio_door` auf Basis von `opening.v1`.
- Die read-only Quellen sind
  `binary_sensor.kitchen_patio_door_open_contact` und
  `binary_sensor.kitchen_patio_door_tilt_contact`, beide aus der MQTT-
  Integration. Ihre IDs wurden read-only in Einhornzentrale beobachtet; sie
  sind keine automatisch aktivierten ConfigEntry-Bindings.
- `off/off`, `off/on` und `on/off` werden zu `closed`, `tilted` und `open`;
  `on/on`, fehlende, initiale, stale, retained oder restaurierte Evidence wird
  für physische Felder zu `unknown`. Die physische Opening-Fallback-Kette
  bleibt `reject`.
- Source-Konflikte führen zusätzlich dazu, dass `available=false` nur als
  konservative technische Gate-Aussage ausgegeben wird; sie lassen den
  Required-Evidence-Gate nicht bestehen.
- Die einzige mögliche Entity ist
  `sensor.benni_opening_kitchen_patio_door`. Die Entity-Allowlist ist exakt;
  Rohquellen, AtomicSignals, Fusionen, Fallbacks und Diagnosen werden nicht
  projiziert.
- Im aktuellen HA-Stand ist der ConfigEntry weiterhin Shadow-only und die
  Entity daher live nicht vorhanden. Eine Benni-seitige Published-
  ConfigEntry-Auswahl und der normale Reload/Restart sind für die echte
  Entity-/Event-Prüfung noch erforderlich.
- Eltern bleibt vollständig `parent_future`/`out_of_scope`; Lock, Cover-
  Position, andere Contracts und alle Consumer bleiben außerhalb dieses
  Gates.

## Abgrenzung zu control#56 / Notes 488–489

Note 488 ist als Feld-/Capability-Diagnose umgesetzt: Root Cause, Quelle,
Dauer, Consumer-Effekt und betroffene FieldQuality bleiben lokal am Feld.
Note 489 wird nicht durch eine Migration beantwortet; das neue Repository
bleibt unabhängig von Core Devices und lässt den bestehenden Legacy-/Consumer-
Bestand unangetastet. Die Freshness-Unterscheidung folgt der dort belegten
Lücke: Restore, retained MQTT, Gerätezeit und HA-Zeit werden nicht vermischt.

## Repository publication

Das kanonische Repository ist
[`Levtos/benni-core-contracts`](https://github.com/Levtos/benni-core-contracts),
das korrespondierende Arbeits-Issue ist
[`#1`](https://github.com/Levtos/benni-core-contracts/issues/1). Der vor dieser
Korrektur beobachtete GitHub-`main`-Stand war
`501660ba3a7698db5a0729c4eb896c85eb31f287`; der Published-Opening-Slice wird
über den GitHub-PR-Workflow bereitgestellt. Diese Publikation ändert weder
Home Assistant, Registry, Deployment noch Consumer; die fachlichen und
Live-Gates bleiben offen.
