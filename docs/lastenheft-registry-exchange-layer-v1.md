# Lastenheft – Core Contracts Registry & Integration Exchange Layer v1

Stand: 2026-09-02

## 1. Zielbild

Core Contracts wird zur zentralen Registry-, Contract-, Quality- und Austauschschicht zwischen Home-Assistant-Integrationen.

Die Integrationen sollen fachliche Informationen bevorzugt über versionierte Contracts und eine interne Core-Contracts-API austauschen, statt dieselben Home-Assistant-Rohentitäten in mehreren Integrationen parallel zu konfigurieren oder erneut auszuwerten.

Leitbild:

```text
Rohquelle / Owner-Integration
        |
        v
Core Contracts
- Registry
- SourceBinding
- Fusion
- Contract
- Quality / Freshness / Fallback
- Diagnose
- interne Consumer API
        |
        v
Consumer-Integration
```

Core Contracts ist das zentrale Wegekreuz, entscheidet aber keine Policies und führt keine Actuation aus.

## 2. Bestehende Foundation erhalten

Die vorhandene Architektur wird weiterentwickelt und nicht neu erfunden. Insbesondere bleiben Grundlage:

- `SourceBinding`
- `AtomicSignal`
- `Fusion`
- versionierte Contract-Schemata und Contract-Resultate
- Quality / Health / Freshness / Safety
- Fallback-Semantik
- `DiagnosticProjection`
- gemeinsame Profile `benni` / `eltern`
- bestehende Svelte-5-/Vite-App-Shell
- bestehende read-only WebSocket-/Revision-Struktur

Refactorings sind zulässig, wenn sie für die produktive Registry notwendig sind. Parallele Legacy-Modelle, neue Master-/Combined-Fassaden oder doppelte Berechnungen sind nicht erwünscht.

## 3. Architekturgrenzen

Core Contracts besitzt drei Verantwortungsbereiche.

### 3.1 Source Registry

Die Registry beantwortet: Welche konkrete Home-Assistant-Entität erfüllt welche stabile logische Rolle?

Beispiel:

```text
Anzeigename: Wohnzimmer Audioplayer
Technische ID: media.audio_player.living_room
Entity: media_player.homepod_wohnzimmer
Capability: audio_player
Profil: benni
```

Wird das Gerät später ausgetauscht, bleibt die technische Rolle stabil. Nur das Binding auf die reale HA-Entity wird geändert.

### 3.2 Signalgraph / Contracts

Rohquellen werden beobachtet, normalisiert, ggf. fusioniert und mit Quality/Freshness/Fallback/Lineage als versionierte fachliche Contract-Werte bereitgestellt.

### 3.3 Integration Exchange Layer

Consumer-Integrationen beziehen fachliche Werte bevorzugt direkt über Core Contracts. Öffentliche Home-Assistant-Entities sind keine Standard-Transportstrecke zwischen Integrationen.

## 4. Ownership

Jede fachliche Wahrheit besitzt exakt einen Owner.

Beispiele:

- Presence / Bio / Day State -> CoreState
- Media Activity -> MediaState
- Environment / Weather -> zuständiger Environment-Owner / Contract
- Heating Policy -> Climate/Heating Policy
- Blind Position Policy -> Blind Policy

Consumer dürfen diese Wahrheit konsumieren, aber nicht parallel aus denselben Rohquellen erneut berechnen.

Zirkuläre Abhängigkeiten sind zu verhindern.

## 5. Profile

Mindestens unterstützt:

- `benni`
- `eltern`

Beide Profile verwenden dieselbe Runtime-, Graph-, Schema-, Fusion-, Quality- und Freshness-Engine. Unterschiedlich sind nur die konkreten Bindings, Geräte, Räume, Contract-Instanzen und profilbezogene Konfiguration.

Das Elternprofil ist im Zielzustand produktiv konfigurierbar und nicht mehr grundsätzlich `parent_future` / `out_of_scope`.

## 6. Persistenz

### 6.1 PostgreSQL als kanonischer Registry Store

Die produktive Registry-Konfiguration wird kanonisch in PostgreSQL gespeichert.

Dazu gehören mindestens:

- Bindings
- Fusionen
- Contract-Instanzen
- Profile
- Capabilities / Rollen
- Consumer Overrides
- Registry-Metadaten
- Registry-Revisionen

Normale Registry-Änderungen benötigen weder YAML noch Git-Pull noch Code-Release.

### 6.2 ConfigEntry

Der Home-Assistant-ConfigEntry bleibt als schlanker Bootstrap erhalten. Er darf technische Integrations-/Bootstrap-Daten enthalten, aber nicht als unübersichtlicher Hauptspeicher der vollständigen Registry missbraucht werden.

### 6.3 Last Known Good

Core Contracts hält lokal die letzte erfolgreich aktivierte Registry-Revision als Last-Known-Good-Cache.

Ist PostgreSQL beim Start oder während des Betriebs temporär nicht erreichbar, bleibt die letzte gültige Registry nutzbar. Health wird entsprechend degradiert; eine leere oder automatisch zurückgesetzte Registry ist nicht zulässig.

## 7. Revisionen und atomare Aktivierung

Jeder produktive Speichervorgang erzeugt eine neue Registry-Revision.

Typische Zustände:

- draft
- active
- superseded
- rejected

Eine neue Revision wird erst aktiv, wenn sie vollständig validiert und der resultierende Graph erfolgreich aufgebaut wurde.

Fehlschläge dürfen die letzte gültige aktive Revision niemals beschädigen oder teilweise überschreiben.

Optimistic Concurrency ist erforderlich: Ein Entwurf auf Basis einer alten Revision darf eine zwischenzeitlich neuere Revision nicht blind überschreiben.

## 8. Svelte-5-UX

Die vorhandene Svelte-5-/Vite-Oberfläche wird erweitert. Keine zweite Frontend-Technologie.

Mindestens folgende Bereiche:

- Übersicht
- Registry
- Bindings
- Fusionen
- Contracts
- Diagnose
- Health
- Einstellungen

Live-Updates dürfen Scrollposition, Filter, Auswahl oder ungespeicherte Formulardaten nicht ungefragt zerstören.

## 9. Kein Autosave

Es gibt ausdrücklich kein Autosave für produktive Registry-Konfiguration.

Die UX arbeitet mit einem Entwurf. Konfiguration wird nur über eine explizite Benutzeraktion gespeichert.

Erforderliche Aktionen:

### Aktualisieren

Read-only. Lädt den aktuellen Backend-/Registry-Stand neu.

Darf niemals aufgrund von Live-Zuständen Bindings ändern, deaktivieren oder entfernen.

Bei ungespeicherten Änderungen muss vor einem Verwerfen gewarnt werden.

### Prüfen

Validiert den aktuellen Entwurf vollständig, ohne ihn zu speichern oder zu aktivieren.

### Speichern

Validiert, persistiert atomar, baut den Graphen neu und aktiviert nur bei Erfolg eine neue Revision.

### Änderungen verwerfen

Verwirft ausschließlich den lokalen Entwurf.

### Rollback

Eine frühere gültige Revision kann nachvollziehbar wieder aktiviert werden, ohne Historie destruktiv zu löschen.

## 10. Source Bindings

Ein Binding muss mindestens abbilden:

- stabile technische ID
- frei editierbarer Anzeigename
- Profil
- konkrete `entity_id`
- Capability / Typ
- fachliche Rolle / Contract-Feld
- Required ja/nein
- Freshness TTL
- Fallback
- Consumer-Metadaten
- read-only Source-Grenze

Bindings müssen über die UX angelegt, bearbeitet, gelöscht und bei Bedarf deaktiviert werden können.

### 10.1 Technische IDs

Technische IDs werden stabil erzeugt. Anzeigenamen dürfen frei geändert werden.

Eine bereits verwendete technische ID darf nicht einfach überschrieben werden. Eine Änderung benötigt eine explizite Referenzmigration.

### 10.2 Entity-Auswahl

Die endgültige reale HA-Entity wird vom Benutzer ausgewählt/bestätigt. Automatische Vorschläge sind erlaubt, automatische produktive Zuordnung ohne Bestätigung nicht.

Das ist insbesondere wegen Dubletten, Legacy-Entities, umbenannten Entities und mehreren ähnlichen Media-/Sensor-Entities erforderlich.

## 11. Import / Export

### 11.1 HA-Entity-Auswahl / Import

Entities können aus Home Assistant gesucht und ausgewählt werden. Mehrfachauswahl ist zulässig. Rolle und Capability werden anschließend bestätigt.

### 11.2 Core-Contracts-Import

Eine vollständige versionierte Registry-Konfiguration kann importiert, geprüft und anschließend explizit gespeichert werden.

Historische Evidence oder Fixtures dürfen nicht stillschweigend produktiv aktiviert werden.

### 11.3 Bestehende Integrationskonfiguration

Wenn technisch sinnvoll, dürfen bestehende ConfigEntries analysiert werden, um Migrationsvorschläge zu erzeugen. Vorschläge benötigen immer Benutzerbestätigung.

### 11.4 Export

Die vollständige Registry-Konfiguration ist exportierbar. Runtime-Zustände und Secrets gehören nicht in den normalen Export.

## 12. Fusionen

Fusion kombiniert mehrere SourceBindings und/oder andere Fusionen zu einem fachlichen Feldwert.

Generische Strategien mindestens:

- `first_healthy`
- `latest`
- `any_true`
- `all_true`

Bestehende fachliche Opening-Strategien bleiben erhalten.

Fusionen müssen über die Svelte-UX angelegt, bearbeitet, gelöscht und diagnostiziert werden können.

Fusion ist Datenverarbeitung, keine Policy. Zeit-, Komfort-, Heiz-, Licht- oder andere Automationsentscheidungen gehören nicht in generische Fusionen.

## 13. Contract-Schemata und Instanzen

Contract-Schemata bleiben typisiert, versioniert und code-definiert.

Bestehende Beispiele:

- `room_climate.v1`
- `opening.v1`
- `weather_environment.v1`
- `technical_device.v1`

Schema-Strukturen werden nicht beliebig durch Endnutzer-CRUD verändert. Inkompatible Schemaänderungen erzeugen eine neue Version.

Der Benutzer darf dagegen mehrere Contract-Instanzen eines Schemas konfigurieren, z. B. mehrere Fenster/Türen/Räume.

## 14. Consumer API

Core Contracts erhält eine stabile interne API für Consumer-Integrationen.

Semantisch mindestens erforderlich:

- Binding auflösen
- Contract-Snapshot holen
- Contract-Feld holen
- Quality holen
- Freshness holen
- relevante Contract-/Registry-Änderungen abonnieren

Consumer sprechen nicht direkt mit PostgreSQL.

Die konkrete API darf implementationstechnisch idiomatisch umgesetzt werden, muss aber stabil dokumentiert und testbar sein.

## 15. Consumer-Deklaration und Overrides

Consumer-Integrationen deklarieren selbst, welche Contracts/Rollen sie benötigen.

Der Benutzer muss im Normalfall nicht manuell pflegen, welcher Consumer ein Binding verwendet.

Die UX zeigt Consumer-Nutzung an.

Ein erweiterter Override-/Sperrmechanismus ist zulässig und soll bei Bedarf explizite Consumer-Freigaben oder Sperren erlauben.

## 16. Subscription / Updates

Neben synchronem Snapshot-Zugriff ist ein Update-/Subscription-Pfad erforderlich, damit Consumer relevante Änderungen ohne permanentes eigenes Polling erhalten können.

Registry- und Contract-Revisionen bleiben nachvollziehbar.

## 17. Öffentliche Home-Assistant-Entities

Interner Integrationsaustausch erfolgt bevorzugt über die Core-Contracts-API.

Öffentliche Entities werden nur explizit projiziert, wenn Werte außerhalb des Integrationsverbunds benötigt werden, z. B. für:

- Dashboard
- normale HA-Automationen
- manuelle Anzeige
- externe Consumer

Keine automatische Entity-Flut für Rohquellen, AtomicSignals, Fusion-Zwischenwerte oder reine Diagnose-/Transportwerte.

## 18. Diagnose und direkte Reparatur

Die bestehende feldbezogene Diagnose wird erhalten und erweitert.

Mindestens sichtbar:

- Contract
- Feld
- Wert
- Health
- Quality
- Freshness
- Safety
- Root Cause
- aktive Source
- Kandidaten
- Fallback
- Degradierungsbeginn/-dauer
- betroffene Consumer
- Registry Revision

Von einem Diagnosefehler muss direkt zum betroffenen Binding navigiert werden können.

Ablauf:

```text
BLOCKED / DEGRADED
  -> Binding bearbeiten
  -> andere Entity auswählen
  -> Prüfen
  -> Speichern
  -> neue Revision / Graph-Auswertung
```

## 19. Harte Regel: Runtime verändert keine Registry

Live-State-/Refresh-Ereignisse dürfen niemals gespeicherte Registry-Konfiguration überschreiben.

Dazu zählen insbesondere:

- unavailable
- unknown
- stale
- retained MQTT
- Restore
- State Refresh
- Discovery
- HA Restart
- Consumer Refresh
- Health Check

Diese Ereignisse beeinflussen ausschließlich Runtime-Wert, Health, Quality, Freshness und Diagnose.

## 20. Activity / Owner-Cutover-Regel

Activity wird nicht durch mehrfach konfigurierte Media-Rohgeräte in CoreState nachgebaut.

Media Activity besitzt einen klaren Owner (MediaState). Ein übergeordneter Core-/Household-Activity-Contract besitzt ebenfalls einen klaren Owner.

CoreState darf Media Activity konsumieren, soll aber PS5/TV/PC/Switch-Erkennung nicht parallel erneut implementieren.

Für spätere Consumer-Cutovers gilt pro bisherigem Feld:

- KEEP – echter Input des Owners
- CONTRACT – zukünftig über Core Contracts
- MOVE – gehört zu anderem Owner
- REMOVE – Legacy / Self-Reference / tot
- OUTPUT – wird vom Owner selbst produziert

## 21. Eltern als Referenz-Abnahmeszenario

Core Contracts muss das Elternprofil produktiv unterstützen.

Späterer End-to-End-Abnahmetest:

```text
Core Contracts installieren
-> Profil Eltern
-> Registry konfigurieren
-> CoreState Eltern anbinden
-> keine Benni-spezifischen Legacy-Inputs
-> keine unnötigen Media-Rohentitäten in CoreState
-> CoreState funktionsfähig
```

Beispiel Presence-Fusion:

```text
person.mutter --\
                any_true -> household.presence
person.vater  --/
```

## 22. PostgreSQL-Datenmodell

Ein revisionsorientierter JSONB-Ansatz ist für den ersten produktiven Stand ausdrücklich zulässig und bevorzugt, sofern er die Anforderungen sauber erfüllt.

Beispielhafte Tabelle:

```text
core_contracts_registry_revision
- id
- profile
- schema_version
- payload JSONB
- status
- created_at
- activated_at
- checksum
- created_by (falls sinnvoll verfügbar)
```

Payload mindestens:

- bindings
- fusions
- contract_instances
- consumer_overrides
- registry_metadata

Eine spätere relationale Aufteilung darf die Consumer-/Registry-API nicht brechen.

## 23. Write API / Berechtigungen

Die bestehende read-only WebSocket-Grenze bleibt erhalten.

Zusätzlich entsteht ein klar getrennter, validierter Schreibpfad für Registry-Änderungen. Schreiboperationen benötigen angemessene Home-Assistant-Admin-Berechtigungen.

Schreibpfad mindestens für:

- Entwurf validieren
- neue Revision speichern / aktivieren
- Rollback
- Binding CRUD
- Fusion CRUD
- Import

## 24. Logging

Wichtige Ereignisse sind nachvollziehbar zu loggen, ohne Secrets:

- Registry Revision aktiviert / abgelehnt
- Rollback
- Binding/Fusion geändert
- PostgreSQL unavailable
- Last Known Good aktiviert
- Consumer Contract missing
- Schema mismatch
- Concurrency Conflict

## 25. Tests

Bestehende Tests bleiben erhalten und werden erweitert.

Mindestens Abdeckung für:

- PostgreSQL Registry Repository
- Revisionen und atomare Aktivierung
- Last Known Good
- PostgreSQL-Ausfall
- Binding CRUD
- Fusion CRUD
- `all_true`
- Benni / Eltern
- Consumer API
- Subscription Events
- Consumer Overrides
- Import / Export
- Rollback
- Concurrency Conflict
- invalid Binding / invalid Fusion
- Runtime verändert Registry nicht
- Svelte Store / Edit Flow
- Prüfen / Speichern / Aktualisieren / Verwerfen
- Diagnose -> Binding Navigation
- ungespeicherte Änderungen
- responsive UX

Erforderliche Qualitätschecks mindestens:

- Python Unit-/Architecture-Tests
- `compileall`
- Repository Validation
- `npm ci`
- `npm run check`
- Frontend Tests
- `npm run build`

## 26. Dokumentation

README und relevante Architekturdokumente werden auf den neuen Zielstand gebracht.

Historische Aussagen zu `Benni-only`, `parent_future`, ausschließlich read-only UX oder Shadow-only als dauerhaftem Ziel werden als historisch/superseded markiert, wenn sie dem neuen Stand widersprechen.

Die Dokumentation erklärt verständlich:

1. Zweck von Core Contracts
2. Registry
3. SourceBinding
4. Fusion
5. Contract
6. Consumer API
7. Profile Benni/Eltern
8. Gerätewechsel
9. Revision / Rollback
10. Public Entity Projection

## 27. Nicht-Ziele

Core Contracts übernimmt keine:

- Heizentscheidung
- Lichtentscheidung
- Rollo-Zielposition
- Media Policy
- Wake Policy
- Automationsaktion
- Geräteaktuation

Core Contracts liefert fachliche Wahrheit, Qualität, Source-Zuordnung, Fusion, Diagnose und Austausch.

## 28. Definition of Done

Dieser Ausbau gilt als fachlich abgeschlossen, wenn:

1. Benni und Eltern produktiv konfigurierbar sind.
2. Registry über Svelte 5 verwaltet werden kann.
3. PostgreSQL kanonischer Registry Store ist.
4. Last-Known-Good funktioniert.
5. Bindings ohne YAML/Git angelegt und geändert werden können.
6. Fusionen über die UX verwaltbar sind.
7. Aktualisieren, Prüfen, Speichern, Verwerfen und Rollback funktionieren.
8. Speichern atomar und revisionsbasiert ist.
9. Consumer API dokumentiert und getestet vorhanden ist.
10. Subscription-/Update-Pfad vorhanden ist.
11. öffentliche Entities optional statt Standard sind.
12. Diagnose direkt zur Binding-Reparatur führen kann.
13. Runtime-Events niemals Registry-Konfiguration überschreiben.
14. bestehende Quality-/Freshness-/Signalgraph-Funktionalität erhalten bleibt.
15. alle Backend-/Frontend-/Repository-Checks grün sind.
16. Dokumentation dem produktiven Zielstand entspricht.

## 29. Rollout nach Core Contracts

Die Consumer-Cutovers sind separate Arbeitspakete und nicht Teil eines einzigen Core-Contracts-Monsterauftrags.

Geplante Reihenfolge nach Fertigstellung der Foundation:

1. CoreState
2. MediaState
3. Climate / Eltern-Heizlogik
4. Blind / weitere Policies
5. weitere Integrationen

Core Contracts selbst muss jedoch so fertiggestellt werden, dass diese Cutovers danach ohne erneuten Architekturumbau beginnen können.
