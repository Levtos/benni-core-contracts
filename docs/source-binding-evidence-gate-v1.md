# Source Binding Evidence Gate v1

Stand: 2026-07-23. Gate Pack v1 und Contract Evidence Gate v1 bleiben
unverändert. Dieses Gate beantwortet ausschließlich die Frage, welche
technischen Quellen später als Evidence für benni_core_contracts geprüft
werden können.

Es gibt in diesem Schritt:

- keine Migration,
- keinen Consumer-Cutover,
- keinen Published-Modus,
- keine Entity-Allowlist-Freigabe,
- keine ConfigEntry-Aktivierung,
- keinen Registry-Zugriff,
- keine Services, Actuation oder Policy-Entscheidung,
- keine Änderung an anderen Repositories.

Die vollständige Matrix steht in
[source-binding-matrix-v1.md](source-binding-matrix-v1.md). Der normative
Datensatz ist source_binding_matrix_v1() in
custom_components/benni_core_contracts/source_binding_evidence.py.

Das nachgelagerte Owner-/Required-Field-Gate für diesen Evidence-Slice steht
in [benni-owner-required-field-gate-v1.md](benni-owner-required-field-gate-v1.md).
Es beschränkt den produktiven Ziel-Scope auf Benni; Eltern bleibt
`parent_future`/`out_of_scope`.

Die nachgelagerte feldgenaue, read-only Benni-Auswertung steht in
[benni-shadow-contract-verification-v1.md](benni-shadow-contract-verification-v1.md).
Sie wertet nur explizit vorgelegte aktuelle Source-Observations aus;
`LIVE_VERIFIZIERT` aus dieser Matrix ist kein automatischer Live-Pass.

## Evidence-Klassen

Jeder Datensatz verwendet ausschließlich eine dieser Klassen:

| Klasse | Bedeutung |
| --- | --- |
| IMPLEMENTIERT | Der interne Evidence-/Gate-Mechanismus ist im Repository implementiert; daraus folgt keine konkrete Produktionsquelle |
| KONFIGURIERT | Eine konkrete Quelle ist in einer lokal geprüften Konfiguration/Importdatei genannt; Live-Existenz ist nicht bewiesen |
| LIVE_VERIFIZIERT | Eine konkrete Entity wurde am 2026-07-23 read-only im zuständigen HA-State bzw. in der Domain-Suche gefunden; Gerätezeitstempel sind damit nicht bewiesen |
| DOKUMENTIERT | Eine Quelle ist nur in Dokumentation oder einer ausgeschlossenen historischen/policybezogenen Beschreibung belegt |
| OFFEN | Es wurde keine konkrete Quelle belegt; source_entity bleibt None |
| ANNAHME | Darf nur in synthetischen Planungsfixtures verwendet werden und ist keine Produktions-Evidence |

LIVE_VERIFIZIERT bedeutet Entity-/State-/Attribut-Evidence, nicht
Produktionsfreigabe. KONFIGURIERT wird nie zu LIVE_VERIFIZIERT hochgestuft,
ohne einen getrennten Live-Nachweis.

## Freshness-Gate

Die Matrix übernimmt die Gate-Pack-Regeln unverändert:

1. device_timestamp darf innerhalb des Feld-TTLs fresh ergeben, wenn ein
   echter Gerätezeitstempel und plausible Zeitrichtung belegt sind.
2. ha_timestamp ist nur bei einem echten, nicht-retained HA-State-Ereignis
   verwendbar.
3. received_at, last_updated oder ein bloßer Poll-/Ingest-Zeitpunkt begründen
   allein niemals fresh.
4. retained MQTT bleibt mindestens suspect/stale, niemals automatisch fresh.
5. Restore bleibt restored, niemals fresh.
6. unbekannte, zukünftige oder unplausible Zeitstempel bleiben unknown.
7. Batterie-, Lade- oder Verfügbarkeitswerte sind kein Ersatz für einen
   Gerätezeitstempel des fachlichen Zustands.

Für Safety-Felder ist die Grenze explizit:

| Feldklasse | Zugelassene Beobachtung für v1 | Gerätezeitstempel |
| --- | --- | --- |
| Opening-Kontakte | echter, nicht-retained HA-State-Change oder echter Gerätezeitstempel innerhalb TTL | im aktuellen Schema kann HA-Event genügen; Gerätezeitstempel bleibt bevorzugt und ist offen |
| Cover-Position | nur Gerätezeitstempel | im Evidence-Sonderfall zwingend erforderlich |
| Lock-State | nur Gerätezeitstempel | zwingend erforderlich; HA-only genügt nicht |
| Room-/Environment-Messwert | Gerätezeitstempel oder echter HA-State-Change | je realer Integration klären |

## Physische Zustände und Fallback

Die folgenden Regeln sind hart:

- fehlende, stale, retained, restaurierte oder widersprüchliche Opening-
  Evidence ergibt opening_state=unknown und is_open=unknown;
- fehlende Lock-Evidence ergibt unknown, niemals locked oder unlocked;
- fehlende Positions-Evidence ergibt unknown, niemals eine Position;
- opening_state, is_open, lock_state und cover_position verwenden zwingend
  fallback=reject;
- safe_default ist für physische Zustände, Locks und Positionen verboten;
- available=false darf als technische Verfügbarkeitsaussage bestehen, aber
  kein Required-Evidence-Gate passieren lassen;
- fachlicher State, health, quality, freshness, safety und
  Evidence-Gültigkeit bleiben getrennt.

Die Matrix enthält für available, wo das Schema es ausdrücklich erlaubt, eine
interne safe_default=false-Availability-Projektion. Das ist keine Aussage über
einen physischen Zustand.

`active_candidates()` bedeutet ab diesem Gate ausschließlich
Benni-Produktions-Scope. Eltern-Evidence bleibt über
`parent_future_records()` für gemeinsame Fixtures sichtbar, ist aber nicht
aktivierbar.

## Profilgrenze

Benni und Eltern benutzen dieselben Funktionen und dieselben Contract-Schemas.
Unterschiede liegen ausschließlich in Quelle, Raum, Binding-Evidence,
Ausstattung und optionaler Fähigkeit. Es gibt keine getrennten Profil-
Logikbäume.

Die lokale Matrix enthält:

- Benni Room Climate, Opening, Weather/Environment und den technischen
  Rollo-Sonderfall;
- Eltern Room Climate, Opening, Outdoor-/Weather-Kandidaten und die offenen
  technischen/Lock-/Cover-Felder;
- den Benni-Lock-ID-Konflikt zwischen lokaler Importdatei und Live-Entity;
- den Eltern-Weather-Konflikt zwischen weather.forecast_home und
  weather.pirateweather.

## Contract- und Consumer-Grenze

Die vier v1-Contracts bleiben technische Beobachtungsverträge:

- room_climate.v1: Rohraumtemperatur, Rohfeuchte, beobachteter
  Thermostat-Setpoint, Roh-HVAC-State, technische Availability.
- opening.v1: Rohkontakt-Evidence, daraus intern fusionierter Opening-State,
  is_open als Projektion, Availability und Diagnosezählung.
- weather_environment.v1: Außenmesswerte und Weather-State, ohne
  Wetter-/Hitze-/Rollo-Policy-Ziel.
- technical_device.v1: technischer Gerätezustand, Versorgung, Leistung,
  Batterie und Laden; keine Zielposition, Privatsphäre, Hitze, Schutz- oder
  Notification-Policy.

Policy-Ziele und Zwischenwerte werden nicht als Binding-Felder eingeführt.
Historische öffentliche Master-/Combined-/Atomic-Entities werden nicht als
neue Quellen übernommen. Dokumentierte Legacy-/Policy-IDs bleiben in der
Matrix höchstens als DOKUMENTIERT/excluded sichtbar, damit ein Konflikt nicht
versehentlich wieder aktiv wird.

## ConfigEntry- und Entity-Grenze

SourceBindingEvidenceMatrix ist absichtlich nicht ConfigModel. Die
Evidence-Funktion:

- liest keine ConfigEntry,
- schreibt keinen HA-Store,
- erzeugt keine SourceBinding-Objekte für eine aktive Konfiguration,
- setzt production_binding_allowed für jeden Datensatz auf false,
- aktiviert keine Listener und keine Entity-Projektion.

Der produktive ConfigEntry bleibt deshalb leer. Die öffentliche Allowlist bleibt
leer; der Shadow-Modus erzeugt weiterhin **0 HA-Entities**.

## Tatsächliche Evidence-Lage

### Benni

Live verifiziert sind die im Matrix-Datensatz aufgeführten Rohkontakte,
Climate-Quellen, DWD-/Garten-/Helligkeitsquellen und das Rollo. Die Live-Abfrage
lieferte Zustände und HA-Zeitmetadaten, aber keinen belastbaren Gerätezeit-
stempel. Die kanonische aktuelle Lock-Entity ist
lock.flur_aqara_smart_lock_u200. Die lokal konfigurierte Import-ID
lock.aqara_smart_lock_u200 wurde live nicht gefunden und wird im Modell nur
noch als historical_source_entity geführt, niemals als aktuelle Binding-ID.
Dasselbe gilt für die historische Batterie-ID.

### Eltern

Live verifiziert sind die lokalen Raumtemperatur-/Feuchte-/Druckquellen,
Garten-/Helligkeitsquellen, Kontakte und Matter-Thermostate. Die Rohquellen
liegen in lokalen Z2M-/Matter-YAMLs; retained MQTT ist deshalb möglich. Es
wurden keine Cover- oder Lock-Entities gefunden. Die beiden Weather-Entities
liefern beide live State/Attribute und bleiben bis zur Owner-Entscheidung
Konfliktkandidaten. Kein Gerätezeitstempel wurde im geprüften State-Snapshot
belegt.

## Offene Produktionsfragen

1. Welche konkreten SourceBindings werden nach dem Evidence Gate tatsächlich
   in die ConfigEntry übernommen?
2. Welche Integrationen liefern reale Gerätezeitstempel und über welchen
   Attribut-/Eventpfad?
3. Welche Required-Felder gelten final für Climate, Opening und Safety?
4. Ist ein echter, nicht-retained HA-State-Change für jedes Safety-Feld
   ausreichend oder muss die Quelle Gerätezeit liefern?
5. Welche Weather-Quelle ist bei Eltern kanonisch?
6. Wie werden kanonische Benni-Lock-ID, Source-Ownership und der belastbare
   Gerätezeitpfad read-only erneut gegen Registry-/Live-Evidence bestätigt?
7. Gibt es bei Eltern später eine belegte Cover-/Lock-Fähigkeit?
8. Welche spätere Entity-Allowlist wird ausdrücklich freigegeben?
9. Welche Auth-/Admin-Grenze gilt später für Config-Schreibbefehle, ohne die
   read-only WebSocket-Payloads zu vermischen?

## Vorgeschlagene nächste Live-Evidence-Schritte

Diese Schritte sind nur Vorschläge und wurden nicht ausgeführt:

1. Für je eine Benni- und Eltern-Rohquelle einen echten Gerätebericht bzw.
   non-retained State-Change mit Transport-/Eventkontext erfassen.
2. Für jeden Opening-Kontakt einen kontrollierten State-Change gegen
   last_changed/last_reported und den Gerätebericht korrelieren.
3. Den Benni-Lock-ID-/Batterie-ID-Konflikt in der zuständigen Registry-/Import-
   Dokumentation read-only auflösen und den Gerätezeitpfad verifizieren.
4. Für Eltern den Weather-Owner und die Required-Attribute, insbesondere
   Pressure und Weather-State, festlegen.
5. Erst danach eine getrennte fachliche Entscheidung zu produktiven
   ConfigEntry-Bindings vorbereiten. Keine Entity- oder Consumer-Projektion
   ist Bestandteil dieses Evidence-Schritts.

## Gate-Resultat

Das Source Binding Evidence Gate v1 ist als lokaler, read-only Evidence- und
Test-Slice umgesetzt. Die Matrix zeigt konkrete spätere Kandidaten, markiert
aber fehlende Timestamp-, Owner- und ID-Evidence als offen/conflict. Es gibt
keine produktive Aktivierung und weiterhin **0 HA-Entities**.
