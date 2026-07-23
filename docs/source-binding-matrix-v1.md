# Source Binding Evidence Matrix v1

Stand: 2026-07-23. Diese Matrix ist ein Evidence-Artefakt für
ha-platform/control#57. Sie ist keine produktive ConfigEntry und autorisiert
keine Bindung.

Die kanonische, maschinenlesbare Matrix wird durch
source_binding_matrix_v1() in
custom_components/benni_core_contracts/source_binding_evidence.py erzeugt.
Sie ist mit SOURCE_BINDING_EVIDENCE_VERSION = 1 versioniert und enthält 81
stabile Datensätze. Davon liegen 43 im Scope `benni_production`, 38 im Scope
`parent_future`; 27 Benni-Records sind Evidence-Kandidaten für den aktiven
Scope. Kein Record autorisiert eine produktive Aktivierung. Jeder Datensatz
enthält zusätzlich zu den folgenden Gruppentabellen binding_id, ha_domain,
binding_kind, disposition, evidence_note, activation_scope,
historical_source_entity und production_binding_allowed=false.

`active_candidates()` liefert ausschließlich Benni-Records. Eltern-Records
bleiben mit `parent_future_records()` für gemeinsame Fixtures und
Graph-Evidence sichtbar, aber vollständig `out_of_scope`.

Die im Matrixfeld `LIVE_VERIFIZIERT` dokumentierten Snapshots stammen aus dem
vorherigen Source-Binding-Evidence-Gate. Im nachfolgenden Benni Shadow Contract
Verification Gate lag keine neue Registry-/Live-Abfrage vor. Sie dürfen daher
nicht als aktuelle Freshness-, Ownership- oder Aktivierungs-Evidence gelesen
werden; die jeweilige Revalidierung bleibt `OPEN`.

## Spaltenkonventionen

| Spalte | Bedeutung |
| --- | --- |
| Evidence | ausschließlich IMPLEMENTIERT, KONFIGURIERT, LIVE_VERIFIZIERT, DOKUMENTIERT, OFFEN oder ANNAHME |
| Freshness | zulässige Ursprünge; device_timestamp ist nur mit belegtem Gerätepfad gültig, ha_timestamp nur als echtes, nicht-retained HA-State-Event |
| Device TS | false bedeutet: im geprüften State-Snapshot kein Gerätezeitstempel belegt; null bedeutet: keine Quelle vorhanden oder nicht prüfbar |
| HA Event | true beschreibt den technisch nutzbaren Listener-Pfad, nicht automatisch Frische |
| Retained MQTT | true bedeutet, dass der Transportpfad retained MQTT zulassen kann; ein solches Ereignis bleibt suspect/stale |
| Pfad | Wertpfad in state oder attributes.*; last_changed/last_reported sind nur unter der HA-Event-Regel verwendbar |
| Fallback | bei physischen Zuständen und Positionen zwingend reject; Availability darf als technische Aussage safe_default=false verwenden |
| Scope | `benni_production` ist der einzige produktive Ziel-Scope dieses Gates; `parent_future` ist nicht aktivierbar |
| Historische Quelle | alte oder widersprüchliche IDs stehen nur hier und niemals als aktuelle `source_entity` |
| Disposition | candidate ist Evidence-Kandidat; nur Benni liegt im aktiven Scope. derived, conflict, open und excluded sind nicht aktivierbare Ergebnisse |

Die Gruppierung in den folgenden Tabellen fasst nur Datensätze mit identischer
Semantik zusammen. Die einzelnen Quellentity-IDs bleiben in der kanonischen
Matrix und werden nicht zu einem Platzhalter zusammengezogen.

## room_climate.v1

| Profil / Raum | Feld / Rolle | Quellentity | Required | Freshness / Device TS / HA Event / Retained | Pfad / Fallback | Quality / Safety / Consumer | Evidence / Disposition | Offene Frage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benni / living, kitchen, bathroom | temperature / room_temperature | sensor.living_climate_temperature; sensor.kitchen_climate_temperature; sensor.bath_climate_temperature | ja | device oder echtes HA-Event / false / true / unbekannt | state / reject | Messwert, freshness / safety-relevant / climate | LIVE_VERIFIZIERT / candidate | Gerätezeitstempel oder non-retained Event-Semantik bestätigen |
| Benni / living, kitchen, bathroom | humidity / room_humidity | sensor.living_climate_humidity; sensor.kitchen_climate_humidity; sensor.bath_climate_humidity | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | Messwert, replay / informational / climate | LIVE_VERIFIZIERT / candidate | Retained-/Restore-Erkennung und Timestamp-Pfad bestätigen |
| Benni / living, kitchen, bathroom | target_temperature / beobachteter Thermostat-Setpoint | climate.eve_thermo_20ebp1701; climate.eve_thermo_20ebp1701_2; climate.eve_thermo_20ebp1701_3 | nein | device oder echtes HA-Event / false / true / unbekannt | attributes.temperature / reject | technische Beobachtung, kein Policy-Ziel / informational / climate | LIVE_VERIFIZIERT / candidate | Setpoint als Gerätebeobachtung gegen Policy-Ziel abgrenzen |
| Benni / living, kitchen, bathroom | hvac_mode / thermostat state | dieselben drei climate-Quellen | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | Rohvokabular / informational / climate | LIVE_VERIFIZIERT / candidate | Vokabular und Timestamp-Semantik bestätigen |
| Benni / je Raum | available / required-source gate | keine eigene Entity | ja | aus Feld-Evidence / null / null / null | interne Projektion / safe_default=false | abgeleitete Verfügbarkeit / safety-relevant / climate | IMPLEMENTIERT / derived | Required-Feldmenge pro Raum bestätigen |
| Eltern / living, kitchen, bathroom | temperature / room_temperature | sensor.living_room_temperature; sensor.kitchen_temperature; sensor.bathroom_temperature | ja | device oder echtes HA-Event / false / true / true | state / reject | Z2M-Wert, retained möglich / safety-relevant / climate | LIVE_VERIFIZIERT / candidate | pro MQTT-Ereignis retained vs. realer Messwert unterscheiden |
| Eltern / living, kitchen, bathroom | humidity / room_humidity | sensor.living_room_humidity; sensor.kitchen_humidity; sensor.bathroom_humidity | nein | device oder echtes HA-Event / false / true / true | state / reject | Z2M-Wert, replay / informational / climate | LIVE_VERIFIZIERT / candidate | retained-/Restore-Erkennung bestätigen |
| Eltern / living, kitchen, bathroom | target_temperature / beobachteter Thermostat-Setpoint | climate.living_room_thermostat; climate.kitchen_thermostat; climate.bathroom_thermostat | nein | device oder echtes HA-Event / false / true / true | attributes.temperature / reject | technische Beobachtung, kein Policy-Ziel / informational / climate | LIVE_VERIFIZIERT / candidate | Setpoint gegen Policy-Ziel abgrenzen |
| Eltern / living, kitchen, bathroom | hvac_mode / thermostat state | dieselben drei climate-Quellen | nein | device oder echtes HA-Event / false / true / true | state / reject | Rohvokabular / informational / climate | LIVE_VERIFIZIERT / candidate | Vokabular und MQTT-/Matter-Timestamp bestätigen |
| Eltern / je Raum | available / required-source gate | keine eigene Entity | ja | aus Feld-Evidence / null / null / null | interne Projektion / safe_default=false | abgeleitete Verfügbarkeit / safety-relevant / climate | IMPLEMENTIERT / derived | Required-Feldmenge pro Raum bestätigen |

## opening.v1

opening_state wird aus Rohkontakten fusioniert. is_open ist ausschließlich eine
interne Projektion dieses Feldes; es gibt dafür keine zweite Quellbindung.
Fehlende, stale, retained, restaurierte oder konfliktäre Evidence bleibt
unknown; kein Datensatz verwendet einen Safe Default.

| Profil / Raum | Feld / logische Rollen | Quellentity | Required | Freshness / Device TS / HA Event / Retained | Pfad / Fallback | Quality / Safety / Consumer | Evidence / Disposition | Offene Frage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benni / living | opening_state: open + tilt contacts | binary_sensor.living_window_left_open_contact; binary_sensor.living_window_left_tilt_contact; binary_sensor.living_window_right_open_contact; binary_sensor.living_window_right_tilt_contact | ja | device oder echtes HA-Event / false / true / unbekannt | state / reject | Contact/Freshness/Conflict / consumer-critical / climate, blind, safety | LIVE_VERIFIZIERT / candidate | Gerätezeitstempel und Replay-Erkennung bestätigen |
| Benni / kitchen, hall | opening_state: door contacts | binary_sensor.kitchen_patio_door_open_contact; binary_sensor.kitchen_patio_door_tilt_contact; binary_sensor.hall_entry_door_contact | ja | device oder echtes HA-Event / false / true / unbekannt | state / reject | Contact/Freshness/Conflict / consumer-critical / climate, blind, safety | LIVE_VERIFIZIERT / candidate | vollständige Aggregatmenge und Gerätezeit prüfen |
| Benni / alle | is_open / projection; available / gate; source_count / diagnostic | keine eigene Entity | gemäß Schema | aus Rohfeld-Evidence / null / null / null | interne Projektion / reject für physische Projektion, safe_default=false nur für Availability | Feldfehler bleiben feldbezogen / Safety getrennt / Safety- und Diagnoseconsumer | IMPLEMENTIERT / derived | Aggregatdefinition und Diagnosezählung bestätigen |
| Eltern / kitchen, living, bathroom | opening_state: raw contact | binary_sensor.kitchen_window_left_contact; binary_sensor.kitchen_window_right_contact; binary_sensor.living_room_patio_door_contact; binary_sensor.bathroom_window_right_contact | ja | device oder echtes HA-Event / false / true / true | state / reject | Z2M Contact, retained möglich / consumer-critical / climate, blind, safety | LIVE_VERIFIZIERT / candidate | non-retained MQTT-State-Event pro Kontakt belegen |
| Eltern / alle | is_open / projection; available / gate; source_count / diagnostic | keine eigene Entity | gemäß Schema | aus Rohfeld-Evidence / null / null / null | interne Projektion / reject für physische Projektion, safe_default=false nur für Availability | Feldfehler bleiben feldbezogen / Safety getrennt / Safety- und Diagnoseconsumer | IMPLEMENTIERT / derived | vollständige Eltern-Kontaktmenge bestätigen |

## weather_environment.v1

| Profil / Raum | Feld / Rolle | Quellentity | Required | Freshness / Device TS / HA Event / Retained | Pfad / Fallback | Quality / Safety / Consumer | Evidence / Disposition | Offene Frage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benni / outdoor | outdoor_temperature | sensor.garden_climate_temperature | ja | device oder echtes HA-Event / false / true / unbekannt | state / reject | Messwert / safety-relevant / climate, blind | LIVE_VERIFIZIERT / candidate | Timestamp-Evidence der Quelle bestätigen |
| Benni / outdoor | outdoor_humidity, pressure, weather_state | weather.dwd_home | gemäß Schema | device oder echtes HA-Event / false / true / unbekannt | attributes.humidity, attributes.pressure, state / reject | Wetterbeobachtung / informational / climate, weather | LIVE_VERIFIZIERT / candidate | DWD-Attributpfade und non-retained Event-Semantik bestätigen |
| Benni / outdoor | illuminance | sensor.garden_light_sensor_illuminance | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | Messwert / informational / blind, light | LIVE_VERIFIZIERT / candidate | Timestamp-Evidence bestätigen |
| Benni / outdoor | available / gate | keine eigene Entity | ja | aus Feld-Evidence / null / null / null | interne Projektion / safe_default=false | technische Verfügbarkeit / safety-relevant / climate, blind, weather | IMPLEMENTIERT / derived | Required-Feldmenge bestätigen |
| Eltern / outdoor | outdoor_temperature, outdoor_humidity | sensor.garden_temperature_temperature; sensor.garden_temperature_humidity | Temperatur ja, Feuchte nein | device oder echtes HA-Event / false / true / true | state / reject | Z2M-Wert, retained möglich / Temperatur safety-relevant, Feuchte informational / climate, blind | LIVE_VERIFIZIERT / candidate | MQTT-Evidence pro Ereignis bestätigen |
| Eltern / outdoor | illuminance | sensor.garden_brightness_illuminance | nein | device oder echtes HA-Event / false / true / true | state / reject | Z2M-Wert, retained möglich / informational / blind, light | LIVE_VERIFIZIERT / candidate | Keine Helligkeits-Safe-Defaults aus alter YAML übernehmen |
| Eltern / outdoor | pressure | weather.forecast_home; weather.pirateweather | nein | device oder echtes HA-Event / false / true / unbekannt | attributes.pressure / reject | zwei live Quellen / informational / weather | LIVE_VERIFIZIERT / conflict | Einen Weather-Owner entscheiden; nicht implizit fusionieren |
| Eltern / outdoor | weather_state | weather.forecast_home; weather.pirateweather | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | zwei live Quellen / informational / weather | LIVE_VERIFIZIERT / conflict | Einen Weather-Owner entscheiden; nicht implizit fusionieren |
| Eltern / outdoor | available / gate | keine eigene Entity | ja | aus Feld-Evidence / null / null / null | interne Projektion / safe_default=false | technische Verfügbarkeit / safety-relevant / climate, blind, weather | IMPLEMENTIERT / derived | Weather-Owner und Required-Felder bestätigen |

## technical_device.v1

| Profil / Raum | Feld / Rolle | Quellentity | Required | Freshness / Device TS / HA Event / Retained | Pfad / Fallback | Quality / Safety / Consumer | Evidence / Disposition | Offene Frage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benni / living Rollo | device_state / cover state | cover.wohnbereich_thermo_verdunklungsrollo | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | technischer Zustand, keine Zielposition / informational / diagnostics | LIVE_VERIFIZIERT / candidate | Gerätezeitstempel und Vokabular bestätigen |
| Benni / living Rollo | battery_level / cover battery | sensor.wohnbereich_thermo_verdunklungsrollo_battery | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | Diagnose; Batterie ist kein Freshness-Nachweis / informational / diagnostics | LIVE_VERIFIZIERT / candidate | Timestamp-Semantik bestätigen |
| Benni / living Rollo | charging / charging state | binary_sensor.wohnbereich_thermo_verdunklungsrollo_charging_status | nein | device oder echtes HA-Event / false / true / unbekannt | state / reject | Diagnose / informational / diagnostics | LIVE_VERIFIZIERT / candidate | retained/restore getrennt bewerten |
| Benni / living Rollo | available / gate | keine eigene Entity | ja | aus Rollo-Feld-Evidence / null / null / null | interne Projektion / safe_default=false | technische Verfügbarkeit / safety-relevant / diagnostics | IMPLEMENTIERT / derived | Gate-Menge bestätigen |
| Benni / living Rollo | is_powered, power_w | keine Quelle belegt | nein | Quelle offen | keine erfundene Ableitung / reject | kein Inferenzpfad aus Cover/Batterie/Motor / informational / diagnostics | OFFEN / open | Keine Leistung oder Versorgung aus anderen Feldern ableiten |
| Eltern | alle sechs v1-Felder | keine freigegebene technische Device-Quelle belegt | gemäß Schema | Quelle offen | keine erfundene Ableitung / Contract-Fallback | Required-Gate bleibt offen / fachlich getrennt / diagnostics | OFFEN / open | Eigentümer und konkrete technische Gerätequelle benennen |

## Rollo-/Cover- und Lock-Sonderfälle

| Profil | Evidenzfall | Quelle | Freshness-/Safety-Regel | Evidence / Disposition | Entscheidung |
| --- | --- | --- | --- | --- | --- |
| Benni | aktuelle physische Position, außerhalb technical_device.v1 | cover.wohnbereich_thermo_verdunklungsrollo, attributes.current_position | nur device_timestamp; kein HA-only-Ersatz; kein Safe Default | LIVE_VERIFIZIERT / evidence_only | als Evidence beobachten, nicht als Core-Policy-Ziel oder Entity publizieren |
| Benni | konkurrierender dokumentierter Policy-Identifier | cover.living_blackout_blind | kein raw-source Binding | DOKUMENTIERT / excluded | außerhalb des neuen Graphen halten |
| Benni | kanonische live Lock-ID | lock.flur_aqara_smart_lock_u200 | device_timestamp erforderlich; HA-State allein genügt nicht | LIVE_VERIFIZIERT / conflict / `benni_production` | aktuelle ID ist eindeutig, Contract bleibt wegen Timestamp-/Ownership-Evidence blockiert |
| Benni | historische konfigurierte Import-ID | keine aktuelle Quellentity; `historical_source_entity=lock.aqara_smart_lock_u200` | keine Live-Evidence; reject | KONFIGURIERT / open / `benni_production` | niemals als aktuelle Binding-ID verwenden; Registry-/Import-Abgleich offen |
| Benni | kanonische live Lock-Batterie | sensor.flur_aqara_smart_lock_u200_batterie | Batterie ist kein Lock-Freshness-Nachweis | LIVE_VERIFIZIERT / conflict / `benni_production` | Batterie nur Diagnose; historische Import-ID separat halten |
| Benni | historische konfigurierte Lock-Batterie | keine aktuelle Quellentity; `historical_source_entity=sensor.aqara_smart_lock_u200_batterie` | Batterie ist kein Lock-Freshness-Nachweis | KONFIGURIERT / open / `benni_production` | niemals als aktuelle Binding-ID verwenden |
| Eltern | Lock und Cover | keine Entity in der read-only Live-Domain-Suche | unknown; reject; keine Position-/Lock-Behauptung | OFFEN / open | konkrete Quelle und Gerätezeitpunkt später belegen |

## Provenienz

Benni:

- Lokale Konfiguration/Evidence: einhornzentrale/benni_core_devices/import.yaml.
- Read-only Live-Snapshot: einhornzentrale, 2026-07-23.
- Die lokale Import-ID des Locks und die live gefundene Lock-ID weichen ab.
- `lock.flur_aqara_smart_lock_u200` ist die einzige aktuelle `source_entity`
  für den Lock-State; `lock.aqara_smart_lock_u200` bleibt ausschließlich
  historische Evidence.
- last_changed, last_updated und last_reported aus dem Snapshot sind
  HA-Zeitstempel. In den geprüften Attributen wurde kein Gerätezeitstempel
  gefunden.

Eltern:

- Lokale Konfiguration/Evidence: haos_eltern/packages/00_shared/06_mqtt_z2m,
  packages/00_shared/07_matter sowie Weather-/Climate-Pakete.
- Lokales Exportmaterial unter haos_eltern/export ist historisch und wird
  nicht als aktuelle ConfigEntry-Evidence verwendet.
- Read-only Live-Snapshot: haos_eltern_old, 2026-07-23.
- Die Live-Domain-Suche ergab keine Cover- oder Lock-Entity. Sie ergab
  weather.forecast_home und weather.pirateweather; diese werden als
  Konfliktkandidaten geführt, nicht als Auswahl.

Eine konfigurierte Entity ist nicht automatisch live verifiziert. Ein
Live-State ist nicht automatisch ein Gerätezeitstempel. Eine Batterie
begründet niemals Freshness.

## Acquisition-Gate-v1-Overlay (2026-07-23)

Die kanonische Matrix und ihre Version 1 bleiben unverändert. Dieses
Acquisition-Gate hat keine Matrix-Evidence hochgestuft und keine neue
SourceBinding eingetragen. Die in dieser Datei vorhandenen
LIVE_VERIFIZIERT-Einträge sind historische Snapshots des vorherigen
Source-Binding-Gates; sie sind kein aktueller State-, Ownership- oder
Freshness-Nachweis dieses Laufs.

Die neue read-only Probe gegen die Einhornzentrale ergab:

| Probe | Ergebnis |
| --- | --- |
| Frontend / | HTTP 200 |
| /api/, /api/states, /api/config | HTTP 401 |
| aktuelle Entity-States | nicht gelesen |
| Gerätezeitstempel, Event-Herkunft, retained/restore | nicht ermittelt |
| Registry-/Ownership-Revalidierung | OPEN |

Lokale Import- und Dokumentationsreferenzen bleiben KONFIGURIERT oder
DOKUMENTIERT. Für die aktuelle Acquisition gelten die konkreten Benni-Quellen
als OFFEN, bis ein minimierter, authentifizierter read-only Snapshot mit
State, relevanten Attributen, Availability, last_changed, last_updated,
Gerätezeitpfad, Event-Herkunft, retained-/restore-Markierung und
Source-Ownership vorliegt. Die alte Lock-ID bleibt ausschließlich
historical_source_entity; die kanonische Kandidaten-ID wird nicht aus der
alten ID repariert.
