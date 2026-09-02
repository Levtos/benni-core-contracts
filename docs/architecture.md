# Architektur und Gate Pack v1

## Zielgrenze

Der Gate-Pack-v1-Slice ist ein interner, read-only Signalgraph. Eine Quelle wird
beobachtet, normalisiert und bewertet; sie wird dadurch nicht zu einer
öffentlichen HA-Entity. Verträge sind in diesem Repository Python-/JSON-
Modelle und WebSocket-Antworten. Eine öffentliche Entity-Projektion ist ein
separater, späterer Schritt und benötigt eine exakte Allowlist.

```text
raw HA state (read-only)
        |
        v
SourceBinding -- evidence/freshness --> AtomicSignal
        |
        v
Fusion (field-scoped selection/fallback)
        |
        v
PublishedContract (versioned internal result)
        |
        +--> DiagnosticProjection (field/capability/root cause)
```

Im `shadow_only`-Modus gibt es keine Entity-Plattform-Weiterleitung, keine
Service-Calls, keine Aktuation und keine Policy-Auswertung. Der aktuelle
Architekturstand enthält zusätzlich einen separat validierten Published-
Pilotpfad: Nur `opening.v1` für die Benni-Küchen-Terrassentür darf bei einer
expliziten ConfigEntry-Allowlist die `sensor`-Plattform weiterleiten. Dieser
Pfad bleibt außerhalb des Shadow-Defaults und veröffentlicht keine internen
Graphobjekte.

Der HA-Adapter liest für konfigurierte Bindings initiale Zustände und reine
State-Change-Events. Initiale Zustände erhalten keine Beobachtungs-Freshness;
nur ein echtes nicht-retained State-Change-Event darf `ha_timestamp` als
Beobachtungszeit verwenden. Ausdrücklich vorhandene Gerätezeit-/Retained-
Attribute bleiben getrennte Evidence. Der Listener besitzt keinen Schreibpfad.

## Die fünf Modelle

### SourceBinding

Beschreibt exakt eine konkrete HA-Quell-Entity und ihre interne Aufgabe:
`source_id`, `entity_id`, `field`, `capability`, optionalen Anzeigenamen,
Required-Status, Freshness-TTL und bekannte Consumer. `enabled` steuert den
aktiven Beobachtungspfad, ohne die technische Binding-ID zu ändern. Wildcards
werden abgelehnt. `read_only` ist eine harte Modellinvariante.

### AtomicSignal

Ist ein einzelnes normalisiertes Feldsignal mit Quellbindung, Wert,
TemporalEvidence, feldbezogener Quality und `real_change_at`. Es ist kein
Sensor- oder Device-Modell.

### Fusion

Beschreibt für genau ein Contract-Feld die Eingangsbindungen und die
Auswahlstrategie. Der Slice kennt `first_healthy`, `latest` und `any_true` als
Graph-Metadaten; die Ausführung bleibt eine reine Datenauswahl ohne Policy-
oder Aktuatorwirkung.

### PublishedContract

Ist das versionierte Ergebnis des Graphen. Werte und `FieldQuality` bleiben
zusammen sichtbar. Ein degradierter Temperaturwert löscht deshalb nicht den
gleichzeitig belastbaren Humidity- oder Availability-Wert.

### DiagnosticProjection

Projiziert pro Feld Quell-Entity, Root Causes, Fehlerdauer und Consumer-
Auswirkung. Der Headline-Health-Wert ist eine Zusammenfassung und ersetzt
keine Felddiagnose.

### Contract Evidence Gate

Das `EvidenceGateResult` prüft nach der internen Contract-Auswertung, ob die
Required-Felder mit gültiger, frischer, sicherer und vollständiger Evidence
belegt sind. Es ist eine read-only Prüfprojektion ohne Veröffentlichung,
Entity-Projektion, Consumer-Cutover oder Policy-/Actuation-Entscheidung.

Das nachgelagerte Owner-/Required-Field-Gate v1 begrenzt diesen Scope auf
Benni (`benni_production`). Eltern bleibt als gemeinsames Profil im Graphen,
aber vollständig `parent_future`/`out_of_scope`; es erhält keine produktive
SourceBinding, Allowlist, ConfigEntry-Aktivierung oder Published Entity. Die
verbindlichen Required-Feld-Regeln und `pass`/`degraded`/`blocked`-Semantik
stehen in
[Benni Owner-/Required-Field-Gate v1](benni-owner-required-field-gate-v1.md).

Das Benni Read-Only Shadow Contract Verification Gate v1 erzeugt danach eine
feldgenaue Evidence-Projektion aus Contract, aktiver Quelle und expliziter
Source-Observation. Es bleibt bei `mode=shadow_only`, `activation_allowed=false`
und 0 HA-Entities; fehlende aktuelle Live-Evidence wird `blocked`/`OFFEN`,
nicht aus historischen Snapshots oder Fixtures geschätzt. Details stehen in
[Benni Shadow Contract Verification v1](benni-shadow-contract-verification-v1.md).

Das nachgelagerte Benni Live Evidence Acquisition Gate v1 nimmt nur
explizite, sanitizierte read-only Snapshots entgegen. Es besitzt keinen
Netzwerk-, Credential-, Registry- oder Schreibpfad. Ein unerreichbarer
State-API-Zugriff wird als OPEN dokumentiert; Required-Contracts bleiben
dadurch blocked. Die konkrete Probe und die Snapshot-Lücken stehen in
[Benni Live Evidence Acquisition v1](benni-live-evidence-acquisition-v1.md).

## Freshness und Restore

Nur ein echter Gerätezeitstempel oder ein HA-Zeitstempel kann innerhalb des
Feld-TTLs `fresh` ergeben. `received_at` allein genügt nicht.

- `device_timestamp`: fachlich stärkste Zeitquelle für eine Geräteänderung.
- `ha_timestamp`: HA-Zeitstempel, getrennt vom Gerätezeitstempel.
- `retained_mqtt`: explizit `suspect`, nie automatisch `fresh`.
- `unknown`: `unknown`, nie automatisch `fresh`.
- `restore`: `restored`, nie `fresh`, auch wenn der gespeicherte Wert alt
  aussah oder die Wiederherstellung gerade erfolgt.

`last_real_change` wird nur aus echter Geräte-/HA-Messzeitevidenz bei einer
Wertänderung fortgeschrieben. Persistenz- und Retained-Ereignisse zählen nicht
als neue echte Messung.

## Quality, Fallback und Safety

Quality ist feldbezogen. `healthy`, `degraded`, `blocked` und `unknown` werden
für jedes Contract-Feld gespeichert. Fallbacks sind Datenverhalten:

- `reject`: kein Wert; bei Required-Feldern wird das Feld blockiert.
- `safe_default`: ein expliziter konservativer Wert mit Diagnose.
- `hold_last`: hält nur innerhalb des internen Datenmodells und bleibt
  degradiert; es wird nicht als frisch ausgegeben.

Safety beschreibt die Verbrauchbarkeit des Feldes, nicht eine Aktion. Ein
Safety-relevantes Feld ohne belastbare Evidence wird konservativ, unsafe,
unknown oder blockiert gekennzeichnet. Physische Zustandsfelder geben bei
fehlender Evidence keinen positiven physischen Zustand aus. Policies bleiben
außerhalb dieses Repositories.

## ConfigEntry und Storage

Die ConfigEntry trägt `ConfigModel` Version 1 als schlanken HA-Bootstrap:
Profil, Modus, exakte Allowlist, freigegebene Contract-IDs und die expliziten
Pilot-SourceBindings. Der Flow verlangt immer einen expliziten Modus.
`shadow_only` ist der sichere Default ohne Allowlist und ohne Bindings.
`published` ist nur für Benni, exakt
`benni.opening.kitchen_patio_door`, exakt
`sensor.benni_opening_kitchen_patio_door` und genau die zwei read-only
verifizierten Küchen-Terrassentür-Quellen zulässig. Es gibt keinen impliziten
Published-Modus und keine automatische Binding-Übernahme.

Der HA-Store hat Version 2. Er speichert ausschließlich Runtime-Signale,
Restore-Marker sowie Diagnose-/Shadow-Daten. Konfigurationsdaten im Store
werden abgewiesen. Beim Restore wird die originale Evidence nicht wieder als
aktuell verwendet; der Graph erzeugt neue `restore`-Evidence.

Die kanonische produktive Registry-Konfiguration liegt davon getrennt in
PostgreSQL. `RegistryPayload` verwendet die bestehenden `SourceBinding`- und
`Fusion`-Modelle und ergänzt Contract-Instanzen, Consumer-Overrides und
Registry-Metadaten. `PostgresRegistryRepository` persistiert jede Änderung als
JSONB-Revision und aktiviert sie nur innerhalb einer atomaren Transaktion nach
Graph-Validierung. Die lokale letzte gültige Revision ist ein separater
Last-Known-Good-Cache; Details zu Schema, Migration, Rollback und
Optimistic-Concurrency stehen in
[Registry Storage v1](registry-storage-v1.md).

Issue #17 legt darüber den `RegistryDomainService`. Drafts sind flüchtige
Edit-Stände und werden nur über eine explizite Save-Aktion als neue Revision
gespeichert. `validate` führt den vollständigen Graph-Probeaufbau ohne
Persistenz aus; `RegistryRuntime` tauscht den aktiven Graph-Snapshot erst nach
erfolgreicher PostgreSQL-Aktivierung atomar aus. Die getrennte Admin-Write-
WebSocket-Grenze ist in [Registry Backend-Service v1](registry-service-v1.md)
dokumentiert. Consumer-API, Fusion-Editor, Svelte-UX und Consumer-Cutover sind
bewusst nicht Teil dieses Slice.

## Entity-Grenze

Die einzige Projektionsstelle ist `EntityProjectionGate`. Im
`shadow_only`-Modus liefert sie immer eine leere Menge. Im expliziten
Published-Pilot akzeptiert sie ausschließlich die konkrete Allowlist-Entity;
der Sensor-Adapter wird nur für diesen ConfigEntry-Modus weitergeleitet. Es
gibt keine implizite Entity für:

- eine Rohquelle,
- einen Fallback,
- eine Fusion,
- ein Diagnosefeld,
- einen Policy-Zwischenwert.

Der erste konkrete Published-Pilot ist in
[Published Opening Contract v1](published-opening-contract-v1.md)
dokumentiert. Lock, Cover-Position, alle anderen Contract-Typen, Eltern,
Consumer-Cutovers und Policies bleiben außerhalb der Veröffentlichung.

## Contract-Versionen

Der erste Registry-Satz ist:

- `room_climate.v1`
- `opening.v1`
- `weather_environment.v1`
- `technical_device.v1`

Die Felddefinitionen und Versionen liegen in `contracts.py`; kein Schema
referenziert historische Core-Devices-Klassen oder Entity-IDs. Die
verbindliche Freshness-, Restore-, Fallback-, Config- und WebSocket-Regelung
steht in [Gate Pack v1](gate-pack-v1.md).
