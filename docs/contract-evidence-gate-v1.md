# Contract Evidence Gate v1

Stand: 2026-07-23. Das Contract Evidence Gate ist eine rein interne,
read-only Prüfung des aktuellen `PublishedContract`-Ergebnisses. Es prüft,
ob die deklarierte Evidence für Required-Felder ausreicht, ändert den Graphen
nicht und veröffentlicht nichts nach Home Assistant.

Es gibt weiterhin:

- keine Migration und keinen Consumer-Cutover;
- keinen Published-Modus und keine öffentliche HA-Entity;
- keine Policy- oder Apply-Entscheidung;
- keinen Service-, Actuation-, Registry- oder Live-Systemzugriff.

## 1. Gate-Entscheidung

Das Gate erzeugt ein internes `EvidenceGateResult` mit stabiler ID
`evidence:<contract_id>` und einer Entscheidung pro Feld:

| Gate-Status | Bedeutung |
| --- | --- |
| `pass` | Alle Required-Felder sind fachlich gültig, fresh, sicher, vollständig und ohne Quality-Konflikt. |
| `degraded` | Required-Felder sind ausreichend, mindestens ein Optional-Feld ist aber unbekannt, unavailable, stale, suspect, restored, konfliktbehaftet oder unvollständig. |
| `blocked` | Mindestens ein Required-Feld ist nicht als gültige, fresh, sichere und vollständige Evidence belegt. |

`pass` bedeutet ausschließlich ausreichende interne Evidence. Es ist keine
Freigabe für Entity-Projektion, Consumer-Nutzung, Policy oder Actuation.

Ein Required-Feld besteht nur, wenn gleichzeitig gilt:

- `ValueState=valid`;
- `health=healthy`;
- `quality=good`;
- `freshness=fresh`;
- `safety=valid`;
- `completeness=true`.

Bei Optional-Feldern bleibt eine Abwesenheit zulässig. Ihre Degradierung wird
im Gate-Ergebnis und in `DiagnosticProjection` sichtbar, blockiert aber nicht
die Required-Evidence des Contracts.

## 2. Evidence-Regel

Für jedes v1-Feld gilt `freshness_requirement=device_or_ha_event`:

- ein gültiger, nicht zukünftiger `device_timestamp` innerhalb des Feld-TTLs
  genügt;
- alternativ genügt ein echter, nicht-retained HA-State-Change mit
  `ha_timestamp` und `ha_state_event=true`;
- `received_at` allein genügt niemals;
- retained MQTT ist `suspect`, Restore ist `restored`, unknown bleibt
  `unknown`; keines davon besteht das Required-Evidence-Gate;
- ein Zeitstempel in der Zukunft ist nicht fresh.

Die Regel ist pro Feld im Schema gespeichert. Ein künftiges Feld, das einen
echten Gerätezeitstempel zwingend braucht, muss explizit
`device_timestamp_required` deklarieren; das Gate rät diese strengere Regel
nicht aus dem Feldnamen ab.

## 3. Feldverträge

Die folgenden Tabellen sind die Evidence-Gate-Matrix. `valid` bedeutet den
normalen Datentyp bzw. bei Enum einen erlaubten Enum-Wert. Für alle Felder
sind die Sentinels `unknown` und `unavailable` als getrennte Eingangssemantik
zulässig, sofern die Schema-Metadaten dies nicht künftig abschalten:

- `unknown`: die fachliche Lage ist nicht bekannt; sie bleibt unknown;
- `unavailable`: die Quelle oder Beobachtung fehlt; sie bleibt unavailable;
- Required plus `reject`: kein ausgabefähiger Wert, Feld blocked oder bei
  unbekannter Lage unknown;
- Optional plus `reject`: kein Wert, Feld unavailable/unknown;
- ein Feldfehler löscht keine anderen validen Felder.

`fresh -> healthy/good`; suspect, stale, restored oder unbekannte Zeit ->
mindestens degraded. Für physische Zustandsfelder wird kein unsicherer
Fachwert gehalten: fehlende oder ungültige Evidence führt zu
`ValueState=unknown`, `safety=unknown` oder `unsafe` und bei Required-Feldern
zu `health=blocked`. `safe_default` ist nur für ausdrücklich technische
Verfügbarkeitsaussagen zulässig, immer degraded und trägt einen
feldspezifischen Diagnosegrund.

Die Achsen bleiben eindeutig getrennt:

- `ValueState` beschreibt den fachlichen Feldwert (`valid`, `unknown`,
  `unavailable`, `blocked`, `invalid`);
- `health` beschreibt die Betriebs-/Gate-Fähigkeit (`healthy`, `degraded`,
  `blocked`, `unknown`);
- `quality` beschreibt die Evidence-Qualität einschließlich Konflikt,
  Suspect- und Stale-Zustand;
- `freshness` beschreibt ausschließlich die zeitliche Evidence;
- `safety` beschreibt die Verbrauchbarkeit der Evidence (`valid`,
  `conservative`, `unsafe`, `blocked`, `unknown`) und löst keine Aktion aus.

### `room_climate.v1`

| Feld | Typ / Einheit | Req. | Zulässige States | Evidence | Quality / Health | Safety | Fallback |
| --- | --- | :---: | --- | --- | --- | --- | --- |
| `temperature` | number / °C | ja | valid number; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; sonst degraded, Required-Gate blocked | safety-relevant | `reject` |
| `humidity` | number / % | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `target_temperature` | number / °C | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `hvac_mode` | text / – | nein | valid text; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `available` | boolean / – | ja | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; Safe Default degraded | safety-relevant | `safe_default=false` |

Heizprofile, Fensterblockade, Zieltemperatur-Entscheidungen und andere
Policy-Ziele sind nicht Teil dieses Contracts. `target_temperature` ist nur
eine beobachtete technische Quelle.

### `opening.v1`

| Feld | Typ / Einheit | Req. | Zulässige States | Evidence | Quality / Health | Safety | Fallback |
| --- | --- | :---: | --- | --- | --- | --- | --- |
| `opening_state` | enum / – | ja | `closed`, `tilted`, `open`, `unknown`; unavailable | `device_or_ha_event`, TTL 600 s | nur fresh + konfliktfreie Evidence -> valid/healthy; fehlend, stale, retained, restored oder Konflikt -> `unknown`, blocked/degraded, Gate blocked | consumer-critical; physischer Zustand | `reject` |
| `available` | boolean / – | ja | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 600 s | `false` ist bei fehlender Quelle als technische Verfügbarkeit zulässig, bleibt degraded und besteht das Required-Gate nicht | consumer-critical; technische Verfügbarkeit | `safe_default=false` |
| `is_open` | boolean / – | nein | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 600 s | nur fresh + konfliktfreie Evidence -> valid; fehlend, stale, retained, restored oder Konflikt -> `unknown`, degraded, kein physischer `true`-Claim | safety-relevant; physischer Zustand | `reject` |
| `source_count` | number / count | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |

Für `opening_state` und `is_open` gilt die physische Safe-Default-Sperre
unabhängig von Priorität oder Profil: Fehlende, stale, retained, restaurierte
oder widersprüchliche Quellen dürfen niemals `opening_state=open` oder
`is_open=true` erzeugen. Das Ergebnis ist jeweils `unknown` mit
`fallback=reject`. Die stabile Diagnoseursache ist:

- `source_unavailable` bei fehlenden Quellen;
- `source_stale` bei stale oder retained MQTT Evidence;
- `source_restored` bei Restore-Evidence;
- `source_conflict` bei widersprüchlichen belastbaren Quellen.

Bei diesen Fällen bleibt `available=false` als technische Aussage zulässig,
aber `ValueState=unknown` und das Required-Evidence-Gate bleibt `blocked`.
`safe_default` ist generell für physische Zustände, Lock-Zustände und
Positionen verboten. Dieses Gate führt keine Fensterblockade,
Rollo-Zielposition, Privatsphäre- oder Hitzeentscheidung aus.

### `weather_environment.v1`

| Feld | Typ / Einheit | Req. | Zulässige States | Evidence | Quality / Health | Safety | Fallback |
| --- | --- | :---: | --- | --- | --- | --- | --- |
| `outdoor_temperature` | number / °C | ja | valid number; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; sonst Required-Gate blocked | safety-relevant | `reject` |
| `outdoor_humidity` | number / % | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `pressure` | number / hPa | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 3600 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `illuminance` | number / lx | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `weather_state` | text / – | nein | valid text; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `available` | boolean / – | ja | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 1800 s | fresh -> good/healthy; Safe Default degraded | safety-relevant | `safe_default=false` |

Hitze-, Licht-, Blind- oder sonstige Umgebungsentscheidungen bleiben außerhalb
des Contracts.

### `technical_device.v1`

| Feld | Typ / Einheit | Req. | Zulässige States | Evidence | Quality / Health | Safety | Fallback |
| --- | --- | :---: | --- | --- | --- | --- | --- |
| `available` | boolean / – | ja | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; Safe Default degraded | safety-relevant | `safe_default=false` |
| `device_state` | text / – | nein | valid text; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `is_powered` | boolean / – | nein | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `power_w` | number / W | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `battery_level` | number / % | nein | valid number; unknown; unavailable | `device_or_ha_event`, TTL 3600 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |
| `charging` | boolean / – | nein | valid boolean; unknown; unavailable | `device_or_ha_event`, TTL 900 s | fresh -> good/healthy; fehlend optional degraded | informational | `reject` |

Plug-Schutz, Lautstärke, Notification Routing und Apply-Entscheidungen sind
keine technischen Device-Felder.

## 4. Fixture-Katalog

Alle Fixtures liegen in `tests/fixtures.py`, verwenden synthetische Entity-
IDs und werden mit demselben generischen Graph-Builder erzeugt:

| Fixture | Contract / Zweck | Erwartetes Gate |
| --- | --- | --- |
| `benni_room_climate` | vollständige Benni-Room-Climate-Evidence | `pass` |
| `eltern_room_climate` | identische Regeln mit Eltern-Profil | `pass` |
| `opening` | gültiger Opening-Zustand und Quelle | `pass` |
| `opening_missing_sources` | keine Opening-Evidence | `blocked`, beide physischen Felder `unknown`, `source_unavailable` |
| `opening_stale` | Opening-Quelle außerhalb TTL | `blocked`, beide physischen Felder `unknown`, `source_stale` |
| `opening_retained_mqtt` | retained Opening-Quelle | `blocked`, beide physischen Felder `unknown`, `source_stale` |
| `opening_restore` | restaurierte Opening-Quelle | `blocked`, beide physischen Felder `unknown`, `source_restored` |
| `opening_conflict` | widersprüchliche Opening-Quellen | `blocked`, beide physischen Felder `unknown`, `source_conflict` |
| `weather_environment` | vollständige Wetter-/Umweltwerte | `pass` |
| `technical_device` | vollständiger technischer Device-Contract | `pass` |
| `rollo_partial_failure` | `device_state=partial_failure`, keine Zielposition/Policy | `degraded`, Required-Evidence bereit |
| `missing_sources` | keine Required-Quelle vorhanden | `blocked` |
| `retained_mqtt` | retained Availability-Wert | `blocked`, niemals fresh |
| `restore` | restaurierter Availability-Wert | `blocked`, `restored` |
| `conflicting_sources` | zwei frische, widersprüchliche Quellen | `blocked`, Konfliktdiagnose |

Die Fixtures beweisen nur das lokale Modellverhalten. Sie sind keine Aussage
über konkrete produktive Entity-IDs, Gerätehersteller oder reale
Quellintegrationen.

## 5. Offene Produktionsfragen

Vor jedem Live-Shadow oder einer Consumer-/Entity-Entscheidung müssen separat
belegt und entschieden werden:

1. Welche konkreten SourceBindings existieren pro Profil und Contract?
2. Welche Quellintegrationen liefern einen echten Gerätezeitstempel und wie
   wird er zuverlässig von HA-`last_updated`, retained MQTT und Restore
   unterschieden?
3. Welche Felder sind fachlich Required für Climate, Opening und Safety?
4. Gibt es echte Profilunterschiede oder nur unterschiedliche Bindings?
5. Welche exakt erlaubten Contract-Projektionen dürfen später in die
   Entity-Allowlist aufgenommen werden?
6. Welche Authentifizierungs- und Admin-Grenzen gelten für spätere
   WebSocket-Config-Schreibbefehle?

Diese Fragen sind Evidence-Gaps, keine stillschweigenden Defaults des Gates.

## 6. Repository-Audit und reproduzierbare Prüfung

Der Contract-Evidence-Gate-Audit prüft den vollständigen lokalen Python-Code
gegen `docs/architecture.md`, `docs/gate-pack-v1.md`,
`docs/implementation-status.md` und `docs/ux-contract.md`. Die Regeltests
prüfen zusätzlich alle Contract-Feldnamen und die fünf WebSocket-Befehle in
dieser Dokumentation.

Reproduzierbare lokale Befehle:

```text
python -m compileall -q custom_components tests
python -m unittest discover -s tests -p "test_*.py" -v
python -m json.tool custom_components/benni_core_contracts/manifest.json
python -m json.tool custom_components/benni_core_contracts/strings.json
python -m json.tool custom_components/benni_core_contracts/translations/de.json
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"
```

Die erwartete Entity-Grenze bleibt **0**: keine Entity-Plattform, keine
Sensor-/Binary-Sensor-Datei, keine Services, keine Actuation, keine Policy-
Imports und keine Live-Zugriffe.

### Tatsächliches Ergebnis dieses Gates

- `python -m compileall -q custom_components tests`: erfolgreich;
- `python -m unittest discover -s tests -p "test_*.py" -v`: **52 Tests
  erfolgreich**;
- Manifest-, Strings- und Übersetzungs-JSON: erfolgreich validiert;
- `pyproject.toml`: erfolgreich mit `tomllib` gelesen;
- Trailing-Whitespace-Prüfung: ohne Befund;
- HA-Entities: **0**.

Die fachliche Abweichung im Opening-Contract wurde in diesem Gate behoben:
Die alte Safe-Default-Aussage für `opening_state`/`is_open` war nicht mit dem
Evidence-Sicherheitsziel vereinbar. Code, Schema, Tests und Gate-Pack-
Dokumentation verwenden nun gemeinsam `fallback=reject`, physisches
`unknown`, feldbezogene Reason-Codes und ein blockierendes Required-Gate.
Eine rein redaktionelle Korrektur des `received_at`-Tippfehlers in
`docs/gate-pack-v1.md` wurde ebenfalls vorgenommen.
