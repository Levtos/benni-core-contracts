# Benni Live Evidence Acquisition Gate v1

Stand: 2026-07-23. Dieses Gate prüft ausschließlich read-only, ob für die
bereits in der Source-Binding-Matrix v1 benannten Benni-Quellen ein aktueller,
sanitizierter State-Snapshot mit belastbarer Zeit- und Ownership-Evidence
vorliegt. Es aktiviert keine SourceBinding, verändert keine ConfigEntry,
veröffentlicht keinen Contract und erzeugt keine HA-Entity.

Eltern bleibt vollständig "parent_future" und "out_of_scope". Die gemeinsame
Graph-, Schema- und Fixture-Logik bleibt erhalten; dieses Gate erzeugt keinen
separaten Eltern-Pfad.

## Ergebnis dieses Laufs

Die lokale Read-only-Prüfung konnte die Benni-HA-Frontend-Adresse erreichen,
aber keinen State-API-Zugriff durchführen:

| Probe | Ergebnis |
| --- | --- |
| GET http://192.168.178.106:8123/ | HTTP 200, HA-Frontend erreichbar |
| GET http://192.168.178.106:8123/api/ | HTTP 401 |
| GET http://192.168.178.106:8123/api/states | HTTP 401 |
| GET http://192.168.178.106:8123/api/config | HTTP 401 |
| nutzbarer Live-Connector / read-only Token | nicht verfügbar / nicht verwendet |
| Prüfzeitpunkt der HTTP-Probe | 2026-07-23, 13:10 CEST |

Es wurden keine Tokens, Cookies oder Secrets verwendet oder gespeichert. Nach
dem 401 wurden keine Entity-States geschätzt. Die aktuelle Acquisition-
Bewertung lautet deshalb OPEN; für Required-Felder bleibt das nachgelagerte
Contract-Gate blocked.

Die lokale Konfiguration und Dokumentation liefern nur Kandidaten-Evidence:

- einhornzentrale/benni_core_devices/import.yaml enthält die unten genannten
  Raw-Entity-Referenzen und die alte Lock-Import-ID.
- einhornzentrale/custom/homekit.yaml bestätigt zusätzliche lokale
  Referenzen, ist aber kein Live-State und keine ConfigEntry dieser
  Integration.
- einhornzentrale/docs/integrations.md dokumentiert weather.dwd_home als
  DWD-Quelle; die aktuelle Ownership- und Timestamp-Semantik ist damit nicht
  live verifiziert.
- Im lokalen Einhornzentrale-Checkout wurde kein Registry- oder .storage-
  Artefakt gefunden.
- Die alte Core-Devices-Opening-Konfiguration enthält abgeleitete
  closed-/Stale-Semantik. Sie wird nicht als Evidence in den neuen Graphen
  übernommen; bei fehlender aktueller Evidence bleibt Opening unknown.

## Evidence-Klassen und Statusgrenze

Die Matrix-Evidence und die aktuelle Acquisition-Evidence werden getrennt
geführt:

| Klasse | Bedeutung in diesem Gate |
| --- | --- |
| IMPLEMENTIERT | Regel oder interne Projektion ist im Repository implementiert |
| KONFIGURIERT | Entity-ID steht in lokaler Konfiguration; kein aktueller State-Nachweis |
| LIVE_VERIFIZIERT | nur bei einem aktuellen, nachvollziehbaren read-only Snapshot |
| DOKUMENTIERT | lokale Dokumentation, zum Beispiel DWD-Owner-Hinweis |
| OFFEN | aktuelle Erhebung fehlt oder ist technisch blockiert |
| ANNAHME | ausschließlich synthetische Testannahme, nie Live-Freigabe |

Die in Matrix v1 vorhandenen früheren LIVE_VERIFIZIERT-Einträge stammen aus
einem älteren Snapshot. Dieses Gate hebt keinen davon erneut auf einen
aktuellen Pass. Die neue Acquisition-Schicht in
custom_components/benni_core_contracts/live_evidence.py akzeptiert nur einen
explizit übergebenen, sanitisierten Snapshot und hat keinen Netzwerk- oder
Schreibpfad.

## Aktuelle Benni-Quellübersicht

Für jede unten aufgeführte konkrete Entity gilt in diesem Lauf:

- aktueller State und relevante Attribute: OPEN, nicht ermittelt;
- Availability: OPEN, nicht ermittelt;
- last_changed und last_updated: OPEN, nicht ermittelt;
- Gerätezeitstempel: OPEN, nicht ermittelt;
- Event-/Update-Herkunft: OPEN, nicht ermittelt;
- retained/restored/stale: nicht entscheidbar, daher kein Freshness-Nachweis;
- Source-Owner: OPEN, sofern nicht ausdrücklich als reine Dokumentation
  gekennzeichnet;
- aktuelle Evidence-Klasse: OFFEN für die Acquisition dieses Laufs;
- mögliche Konkurrenten werden nicht implizit ausgewählt.

Die Tabelle ist absichtlich vollständig pro konkreter Source-Entity. Ein
fehlender Wert ist kein Platzhalter-State und wird nicht in einen positiven
Contract-Wert umgedeutet.

### Room Climate

| Entity-ID | Domain | Profil / Raum | Rolle / Contract | Pfad | Lokale Provenienz | Aktuelle Live-Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| sensor.living_climate_temperature | sensor | Benni / living | temperature / room_climate.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| sensor.living_climate_humidity | sensor | Benni / living | humidity / room_climate.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| climate.eve_thermo_20ebp1701 | climate | Benni / living | target_temperature, hvac_mode / room_climate.v1 | attributes.temperature, state | KONFIGURIERT | State, Attribute, Zeit, Owner: OPEN |
| sensor.kitchen_climate_temperature | sensor | Benni / kitchen | temperature / room_climate.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| sensor.kitchen_climate_humidity | sensor | Benni / kitchen | humidity / room_climate.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| climate.eve_thermo_20ebp1701_2 | climate | Benni / kitchen | target_temperature, hvac_mode / room_climate.v1 | attributes.temperature, state | KONFIGURIERT | State, Attribute, Zeit, Owner: OPEN |
| sensor.bath_climate_temperature | sensor | Benni / bathroom | temperature / room_climate.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| sensor.bath_climate_humidity | sensor | Benni / bathroom | humidity / room_climate.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| climate.eve_thermo_20ebp1701_3 | climate | Benni / bathroom | target_temperature, hvac_mode / room_climate.v1 | attributes.temperature, state | KONFIGURIERT | State, Attribute, Zeit, Owner: OPEN |

Kein Thermostat-Setpoint wird als Policy-Ziel interpretiert. Die drei
Room-Climate-Temperaturen und ihre Availability-Gates bleiben ohne aktuelle
State-/Zeit-Evidence blocked beziehungsweise OPEN.

### Opening

| Entity-ID | Domain | Profil / Raum | Rolle / Contract | Pfad | Lokale Provenienz | Aktuelle Live-Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| binary_sensor.living_window_left_open_contact | binary_sensor | Benni / living | open contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| binary_sensor.living_window_left_tilt_contact | binary_sensor | Benni / living | tilt contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| binary_sensor.living_window_right_open_contact | binary_sensor | Benni / living | open contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| binary_sensor.living_window_right_tilt_contact | binary_sensor | Benni / living | tilt contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| binary_sensor.kitchen_patio_door_open_contact | binary_sensor | Benni / kitchen | open contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| binary_sensor.kitchen_patio_door_tilt_contact | binary_sensor | Benni / kitchen | tilt contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| binary_sensor.hall_entry_door_contact | binary_sensor | Benni / hall | entry contact / opening.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |

Opening verwendet weiterhin fallback=reject. Fehlende, stale, retained,
restaurierte oder widersprüchliche Contact-Evidence erzeugt unknown, nie
open oder closed; is_open wird nicht aus einem technischen Default
abgeleitet. Die Availability-Projektion ist kein bestandenes Required-
Evidence-Gate.

### Weather / Environment

| Entity-ID | Domain | Profil / Raum | Rolle / Contract | Pfad | Lokale Provenienz | Aktuelle Live-Evidence / Konkurrenten |
| --- | --- | --- | --- | --- | --- | --- |
| sensor.garden_climate_temperature | sensor | Benni / outdoor | outdoor_temperature / weather_environment.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| weather.dwd_home | weather | Benni / outdoor | outdoor_humidity, pressure, weather_state / weather_environment.v1 | attributes.humidity, attributes.pressure, state | KONFIGURIERT + DWD DOKUMENTIERT | State, Attribute, Zeit, Owner: OPEN; konkurrierende aktuelle Quelle nicht geprüft |
| sensor.garden_light_sensor_illuminance | sensor | Benni / outdoor | illuminance / weather_environment.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |

weather.dwd_home wird nicht allein wegen der lokalen DWD-Dokumentation als
aktueller Weather-Owner ausgewählt. Für die v1-Benni-Matrix ist keine zweite
aktuelle Benni-Wetterquelle eingetragen; Ownership und retained-/stale-Risiko
bleiben trotzdem zu verifizieren. Wetterfehler bleiben feldbezogen und
blockieren nicht künstlich Cover- oder technische Device-Fakten.

### Technical Device

| Entity-ID | Domain | Profil / Raum | Rolle / Contract | Pfad | Lokale Provenienz | Aktuelle Live-Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| cover.wohnbereich_thermo_verdunklungsrollo | cover | Benni / living | device_state / technical_device.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |
| sensor.wohnbereich_thermo_verdunklungsrollo_battery | sensor | Benni / living | battery_level / technical_device.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN; Batterie ist kein Freshness-Nachweis |
| binary_sensor.wohnbereich_thermo_verdunklungsrollo_charging_status | binary_sensor | Benni / living | charging / technical_device.v1 | state | KONFIGURIERT | State, Availability, Zeit, Owner: OPEN |

Die technische Availability bleibt aus dem Required-Device-Evidence-Gate
abgeleitet. Es gibt keine Inferenz von is_powered oder power_w aus Cover-
State, Batterie oder Charging.

### Lock und Cover-Position: Evidence-only

| Entity-ID | Domain | Profil / Raum | Rolle | Pfad | Aktuelle Bewertung |
| --- | --- | --- | --- | --- | --- |
| cover.wohnbereich_thermo_verdunklungsrollo | cover | Benni / living | cover_position | attributes.current_position | OPEN; Gerätezeit-/Quality-Evidence fehlt; keine Veröffentlichung |
| lock.flur_aqara_smart_lock_u200 | lock | Benni / hall | lock_state | state | Kandidaten-ID; Registry-/Live-Revalidierung OPEN; ohne Gerätezeit/Ownership blocked/conflict |
| sensor.flur_aqara_smart_lock_u200_batterie | sensor | Benni / hall | lock_battery | state | OPEN; Batterie ist nur Diagnose und kein Lock-Freshness-Nachweis |
| cover.living_blackout_blind | cover | Benni / living | dokumentierter Policy-Identifier | attributes.current_position | DOKUMENTIERT/excluded; kein neues Raw-Source-Binding |

Die historische ID lock.aqara_smart_lock_u200 steht ausschließlich als
historische lokale Import-Referenz. Sie ist nicht in dieser Tabelle als
aktuelle Entity enthalten und wird vom Acquisition-Modell abgewiesen. Die
kanonische Kandidaten-ID wird nicht ungeprüft als live bestätigt.

## Derived Fields ohne eigene Entity

Die Matrix enthält zusätzlich interne Felder ohne konkrete Entity:

- Room Climate: available je Raum;
- Opening: is_open, available, source_count;
- Weather: available;
- Technical Device: available, is_powered, power_w;
- Lock: historische Import-Referenz und Batterie-Referenz.

Diese Felder erhalten keine erfundene Source-ID. Ohne die zugrunde liegende
aktuelle Raw-Evidence bleiben Required-Availability-Gates blocked; kein
Safe Default behauptet einen physischen Zustand.

## Freshness- und Timestamp-Befunde

Im aktuellen Lauf wurde kein State-Payload gelesen. Daher sind für jede
geprüfte Source unbekannt:

- echter Gerätezeitstempel und konkreter Attributpfad;
- verwertbares echtes, nicht-retained HA-State-Change-Ereignis;
- retained-/restored-/stale-Markierung;
- Source-Ownership und Geräte-/Transportherkunft;
- Konfliktfreiheit gegenüber einer konkurrierenden Quelle.

Die Regeln bleiben verbindlich:

- device_timestamp darf nur mit belegtem Pfad und innerhalb des TTL fresh
  ergeben;
- ha_timestamp darf nur mit explizitem nicht-retained State-Change-Event
  verwendet werden;
- received_at, Batterieprozente und HA-last_updated allein sind kein
  Freshness-Nachweis;
- retained MQTT ist höchstens suspect, Restore ist restored, unbekannte
  Herkunft bleibt unknown;
- zukünftige oder unplausible Zeitstempel bestehen kein Gate.

## Implementierte Acquisition- und Fixture-Grenze

ReadOnlySourceSnapshot akzeptiert nur eine konkrete Entity-ID und
sanitisierte, ausgewählte Attribute. Credential-artige Attribute werden
abgewiesen. assess_live_source() liefert pro Matrix-Feld:

- Acquisition-Status pass, degraded, blocked oder OPEN;
- getrennten gate_status, sodass ein Required-Feld trotz OPEN eindeutig
  blocked bleibt;
- Source-State/Attribute, Availability und alle relevanten Zeitfelder;
- Source-Owner, mögliche Konkurrenzquellen, Evidence-Klasse, Freshness,
  Quality, Health, Safety, Root Cause, Reason-Codes, Fallback-Kette und
  Consumer-Auswirkung;
- keinen positiven physischen Wert bei nicht bestandener Evidence.

Sanitisierte synthetische Fixtures liegen in
tests/live_evidence_fixtures.py. Sie decken HA-Event-Pass, Gerätezeit mit
belegtem Pfad, fehlende Zeit, retained Weather, stale/restore/conflict Opening,
Lock ohne Timestamp, historische Lock-ID und den realen API-OPEN-Blocker ab.
Die synthetischen Pass-Fälle tragen ANNAHME und sind ausdrücklich keine
Live-Freigabe.

## Noch benötigte read-only Snapshots

Für jeden Required-Pfad wird später ein minimierter Snapshot benötigt, ohne
vollständigen HA-State:

1. GET /api/states/<entity_id> oder ein autorisiertes read-only State-Event
   für jede konkrete Climate-, Opening-, Weather- und Technical-Entity aus
   dieser Matrix;
2. nur state, für den Feldpfad relevante Attribute, Availability,
   last_changed, last_updated und die eventuelle Gerätezeit;
3. Herkunft des Updates: echter State-Change oder Initial-/Restore-/retained-
   Pfad;
4. Source-Owner beziehungsweise Integration-/Gerätezuordnung;
5. für Opening, Lock und Cover-Position zusätzlich Konfliktfreiheit und
   belastbarer Gerätezeitpfad;
6. für lock.flur_aqara_smart_lock_u200 eine erneute read-only Registry-
   beziehungsweise Live-Revalidierung; die alte ID darf nicht als Fallback
   dienen.

Bis diese Snapshots vorliegen, bleibt die Matrix unverändert und die Shadow-
Auswertung erhält keine aktuelle Live-Observation.

## Nicht aktiviert

- HA-Entities erzeugt: **0**;
- Entity-Plattform: keine;
- ConfigEntry-/SourceBinding-Aktivierung: keine;
- Services oder Actuation: keine;
- Policy-Imports und Consumer-Cutover: keine;
- Registry-, Home-Assistant-, Migration-, Deployment-, Release-, Commit- oder
  Push-Änderung: keine.

Issue ha-platform/control#57 bleibt auf status/testing.
