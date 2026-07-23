# Gate Pack v1 – verbindliche Foundation-Regeln

Stand: 2026-07-23. Diese Spezifikation gilt für den lokalen Shadow-Slice von
`benni_core_contracts`. Sie definiert Datenqualität und interne Verträge; sie
führt keine Migration durch, stellt keinen Consumer um und erzeugt keine
öffentliche Home-Assistant-Entity.

## 1. Architekturgrenze

Der Graph besteht aus fünf neuen, voneinander getrennten Modellen:

```text
SourceBinding -> AtomicSignal -> Fusion -> PublishedContract
                                             |
                                             v
                                    DiagnosticProjection
```

Die Modelle sind keine Geräte-, Combined- oder Master-Modelle. Eine
`SourceBinding` darf nur eine konkrete Entity referenzieren und ist read-only.
`AtomicSignal` enthält eine Beobachtung mit Evidence. Eine `Fusion` wählt
fachliche Rohdaten aus, entscheidet aber keine Policy. `PublishedContract` ist
ein internes, versioniertes Ergebnis. `DiagnosticProjection` erklärt Zustand,
Qualität, Freshness, Safety, Quelle und Consumer-Effekt feldbezogen.

## 2. Freshness und Evidence

`received_at` ist ausschließlich der lokale Eingang einer Beobachtung.
Er beweist weder eine Geräteänderung noch Freshness.

| Evidence | Freshness-Regel | Verwendung |
| --- | --- | --- |
| `device_timestamp` | `fresh`, wenn der Zeitstempel nicht zukünftig/unplausibel ist und sein Alter innerhalb des Feld-TTL liegt; sonst `suspect` oder `stale` | belastbare Gerätebeobachtung |
| `ha_timestamp` | nur mit `ha_state_event=true`, nicht-retained und innerhalb des Feld-TTL `fresh` | Beobachtungszeit eines echten HA-State-Change-Events |
| `received_at` | niemals allein `fresh` | Audit-/Transportzeit, keine fachliche Zeit |
| `retained_mqtt` | mindestens `suspect`, niemals automatisch `fresh` | Transport-Replay; benötigt eine neue belastbare Beobachtung |
| `restore` | immer `restored`, niemals `fresh` | interner Restore-Wert nach Reload |
| `unknown` | immer `unknown` | keine belastbare Zeitinformation |
| zukünftig/unplausibel | nicht `fresh`; Diagnose `freshness_timestamp_in_future` bzw. gleichwertige Evidenzursache | Eingangsfehler oder Uhrproblem |

Ein initial aus `hass.states` gelesener Zustand ist kein State-Change-Event und
darf deshalb auch bei vorhandenem `last_updated` nicht allein Freshness
begründen. Der Listener markiert nur ein echtes Event explizit als
`ha_state_event`. Retained MQTT bleibt auch dann suspect, wenn ein HA-Zeitpunkt
vorhanden ist.

Die zeitliche Auswahl von `latest` darf ausschließlich auf dem belastbaren
`effective_timestamp` beruhen. `received_at` ist kein Ersatz. Ein jüngerer,
aber stale/suspect/restored Wert wird nicht ausgewählt.

### Safety-Felder

Die v1-Schemata akzeptieren für ihre Safety-relevanten Felder entweder einen
gültigen Gerätezeitstempel oder einen echten, nicht-retained HA-State-Change:
`freshness_requirement=device_or_ha_event`. Das ist eine explizite
Beobachtungsregel, keine pauschale Annahme über `received_at`. Noch kein v1-
Feld verlangt zwingend `device_timestamp`; für Quellen mit unzureichender HA-
Beobachtungssemantik wird der Feldvertrag künftig explizit auf
`device_timestamp_required` gesetzt. Diese Änderung benötigt eine neue
Evidenz-/Vertragsentscheidung.

Safety bleibt eine Metadimension. Ein nichtphysisches Feld mit
stale/suspect/restore Evidence kann als Wert sichtbar bleiben, ist aber
mindestens `degraded` und `safety=conservative`; es wird keine Aktion
ausgelöst. Physische Zustandsfelder dürfen den beobachteten Wert in diesen
Fällen nicht als aktuellen Zustand ausgeben: sie liefern `unknown` mit
`safety=unknown` oder `unsafe` und bestehen kein Evidence-Gate.

## 3. Restore

Die ConfigEntry ist die kanonische Konfiguration. Der Store speichert nur
Runtime-State, Restore-Marker sowie Diagnose-/Shadow-Daten. Beim Reload wird
ein gespeichertes Signal mit neuer `restore`-Evidence wieder in den Graphen
gegeben. Die originale Geräte-/HA-Evidence bleibt Audit-Historie und wird
nicht als aktuelle Evidence weiterverwendet.

Restore-Werte dürfen intern für `hold_last` als letzter Wert erhalten bleiben,
aber sie bleiben `restored`/degradiert und werden nie als `fresh` ausgegeben.
Ein Restore erzeugt weder Entity noch Service-Aufruf.

## 4. Fusion

Alle drei Strategien sind reine, deterministische Datenauswahl:

### `first_healthy`

- Die Eingänge werden in der konfigurierten Prioritätsreihenfolge geprüft.
- Akzeptiert werden nur fachlich gültige, verfügbare und `fresh` Werte.
  `stale`, `suspect`, `restored`, `unknown` und `unavailable` werden
  übersprungen.
- Bei einer ungültigen Quelle wird zur nächsten Quelle weitergegangen.
- Die aktive Binding-ID und die vollständige Kandidatenmenge werden im
  `FieldEvaluation` und in der Diagnose gespeichert.
- Mehrere widersprüchliche frische Quellen lassen den priorisierten Wert
  sichtbar, markieren das Feld aber als `degraded`, `quality=conflict` und
  erzeugen eine Conflict-Diagnose.

### `latest`

- Es werden ausschließlich gültige, frische Werte berücksichtigt.
- Auswahl erfolgt nur nach belastbarer Gerätezeit oder expliziter HA-
  Eventzeit.
- `received_at` darf keine jüngere Beobachtung simulieren.
- Gibt es keine belastbare frische Beobachtungszeit, liefert die Fusion keinen
  Wert und fällt in den Feld-Fallback.

### `any_true`

- Ein gültiges `true` ergibt `true`.
- Sind alle gültigen Werte `false`, ergibt die Fusion `false`.
- Gibt es kein gültiges `true`, aber mindestens einen unbekannten,
  unavailable, stale, suspect oder restored Kandidaten, bleibt das Ergebnis
  `unknown`.
- `true` plus unbekannter/unsicherer Kandidat ergibt `true`, aber
  `completeness=false`, `quality=degraded` und eine Diagnose
  `incomplete_any_true_sources`.

`completeness` ist unabhängig vom fachlichen Boolean-Wert und verhindert, dass
ein teilweise beobachteter Zustand wie eine vollständige Quellenabdeckung
wirkt.

Fusionen dürfen nur gleiche Felder verketten. Der Graph weist unbekannte
Inputs und Zyklen zurück.

## 5. Zustände, Health, Quality und Safety

Der fachliche Feldzustand (`ValueState`) ist getrennt von den vier
Bewertungsachsen:

- `health`: `healthy`, `degraded`, `blocked`, `unknown`;
- `quality`: `good`, `degraded`, `unavailable`, `unknown`, `conflict`,
  `suspect`, `stale`;
- `freshness`: `fresh`, `suspect`, `stale`, `unknown`, `restored`;
- `safety`: `valid`, `conservative`, `unsafe`, `blocked`, `unknown`.

Zusätzlich können fachliche Werte `valid`, `unknown`, `unavailable`,
`blocked` oder `invalid` sein. `blocked` bedeutet, dass ein erforderliches
Feld keinen ausgabefähigen Wert hat. `unavailable` bedeutet fehlende
optionale Verfügbarkeit. `unknown` bleibt unbekannt und wird nicht in einen
positiven Zustand umgedeutet.

Die Aggregation eines Contracts darf valide Felder nicht löschen, wenn ein
anderes Feld fehlerhaft ist. Nur das betroffene Feld erhält Degradierung bzw.
Blockierung; der Contract-Headline-Health wird separat aggregiert.

## 6. Fallbacks und sichere Defaults

### `reject`

Es wird kein Wert geliefert. Ein fehlendes erforderliches Feld erhält den
fachlichen Zustand `blocked`; bei unbekannter Evidence bleibt der Zustand
`unknown`. Ein optionales fehlendes Feld bleibt `unavailable`/`unknown`.

### `hold_last`

`hold_last` existiert ausschließlich im internen Graph-/Runtime-Modell. Der
gehaltene Wert erhält `health=degraded`, eine entsprechende Diagnose und wird
nach Ablauf seines TTL als `stale` bewertet. Er darf niemals `fresh` werden.

### `safe_default`

Ein sicherer Default ist nur zulässig, wenn das Feld ihn im Schema explizit
freigibt und einen feldspezifischen Diagnosegrund trägt. Er ist immer
degradiert und ist keine Policy-Entscheidung. Safe Defaults sind generell für
physische Zustände, Lock-Zustände und Positionen verboten.

Für `opening_state` und `is_open` gibt es keinen Safe Default. Beide Felder
verwenden zwingend `fallback=reject`; fehlende, stale, retained, restaurierte
oder widersprüchliche Evidence wird als `unknown` ausgegeben und blockiert
das Required-Evidence-Gate. Nur `available=false` darf als technische
Verfügbarkeitsaussage per Safe Default erscheinen; dieses `false` ist selbst
kein Required-Evidence-Nachweis. Ein Fenster darf daher weder pauschal als
geschlossen noch als offen gemeldet werden. Für Lock-Felder ist ein Default
generell verboten; v1 führt überhaupt kein Lock-Feld ein.

## 7. Config-Besitz

Die Verantwortlichkeit ist verbindlich:

| Bereich | Besitzer | Zulässiger Inhalt |
| --- | --- | --- |
| Konfiguration | ConfigEntry / `ConfigModel` | Schema-Version, Profil, Modus, exakte Allowlist, Bindings |
| Runtime Store | HA Store | Runtime-Signale, Restore-Marker, Shadow-/Diagnosedaten |
| Import/Export | `ConfigCodec` | ausschließlich ConfigEntry-Konfiguration |

Runtime-State darf nicht stillschweigend als Konfiguration exportiert werden.
Der Runtime-Store weist `config` und `config_entry` ausdrücklich zurück. Es
gibt keine zweite konkurrierende Konfigurationsquelle und keine Migration in
diesem Gate Pack.

## 8. Profile und Bindings

`benni` und `eltern` sind Profile derselben Architektur. Sie benutzen dieselbe
Schema-Registry, dieselben Freshness-/Quality-/Fusion-Regeln und dieselben
Allowlist-Grenzen. Profilabhängig sind nur die ConfigEntry-Auswahl und die
zugeordneten Bindings.

Jede Binding-Regel lautet:

- eindeutige `binding_id` und `source_id`;
- genau eine konkrete HA-Entity-ID ohne Wildcard;
- genau ein internes Feld und eine Capability;
- read-only, ohne Service- oder Actuation-Pfad;
- positives Feld-TTL, Fallback und optionale Consumer-IDs;
- `profile_id` muss dem ConfigEntry-Profil entsprechen.

Eine leere Entity-Allowlist ist gültig und bleibt im Shadow-Modus immer leer.
Rohsource, Fallback, Fusion, Diagnosefeld und Policy-Zwischenwert erhalten
keine eigene HA-Entity.

## 9. Contract-Required-Felder v1

Alle Einheiten sind explizite Schema-Metadaten. `unknown` und `unavailable`
sind als Eingangssemantik getrennt: `unknown` bedeutet unbekannte fachliche
Lage, `unavailable` fehlende Quelle/Verfügbarkeit. Required-Felder dürfen
beide Zustände diagnostizieren, liefern bei `reject` aber keinen Wert und
werden blockiert. Optional-Felder bleiben ohne Wert verfügbar/unbekannt.

In den Tabellen bedeutet `D/HA` die explizite Regel
`device_timestamp` oder echter nicht-retained HA-State-Change. `good/fresh`
steht für `health=healthy`, `quality=good`, `freshness=fresh` und – falls
Safety-relevant – `safety=valid`. Jede andere Evidence wird feldbezogen
degradiert; ein fehlendes Required-Feld wird blockiert. `SD` bedeutet der
genannte, ausdrücklich erlaubte Safe Default; `reject` bedeutet kein Wert.

### `room_climate.v1`

| Feld | Typ | Einheit | Req. | Unknown/Unavailable | Freshness | Quality/Safety | Fallback |
| --- | --- | --- | :---: | --- | --- | --- | --- |
| `temperature` | number | °C | ja | beide diagnostizierbar, bei reject kein Wert | TTL 900 s, D/HA | good/fresh; safety-relevant | reject |
| `humidity` | number | % | nein | optional unknown/unavailable | TTL 1800 s, D/HA | good/fresh; informational | reject |
| `target_temperature` | number | °C | nein | optional unknown/unavailable | TTL 1800 s, D/HA | good/fresh; informational | reject |
| `hvac_mode` | text | – | nein | optional unknown/unavailable | TTL 1800 s, D/HA | good/fresh; informational | reject |
| `available` | boolean | – | ja | fehlend/unknown -> `false` mit Diagnose, nicht als frisch | TTL 900 s, D/HA | degraded/conservative bei SD | SD `false` |

Policy-Ziele wie Heizprofile oder Fensterblockade sind nicht enthalten.

### `opening.v1`

| Feld | Typ | Einheit | Req. | Unknown/Unavailable | Freshness | Quality/Safety | Fallback |
| --- | --- | --- | :---: | --- | --- | --- | --- |
| `opening_state` | enum (`closed`, `tilted`, `open`, `unknown`) | – | ja | fehlend, stale, retained, restored oder Konflikt -> `unknown`; keine physische `open`-Behauptung | TTL 600 s, D/HA | consumer-critical/physisch; ohne belastbare Evidence blocked, safety unknown/unsafe | reject |
| `available` | boolean | – | ja | fehlend/unknown -> `false` mit Diagnose; technische Aussage, kein Evidence-Gate-Nachweis | TTL 600 s, D/HA | consumer-critical/technisch; degraded bei SD | SD `false` |
| `is_open` | boolean | – | nein | fehlend, stale, retained, restored oder Konflikt -> `unknown`; niemals physisches `true` ohne Evidence | TTL 600 s, D/HA | safety-relevant/physisch; degraded, safety unknown/unsafe | reject |
| `source_count` | number | count | nein | optional unknown/unavailable | TTL 900 s, D/HA | informational | reject |

Die Opening-Diagnosegründe sind `source_unavailable`, `source_stale`,
`source_restored` und `source_conflict`. `opening_state` und `is_open` haben
jeweils `physical_state=true`; das Schema weist deshalb Safe Default und
`hold_last` für diese Felder zurück.

Rollo-Zielposition, Fensterblockade, Privatsphäre und Hitze bleiben Policy-
Ziele und sind keine Core-Felder.

### `weather_environment.v1`

| Feld | Typ | Einheit | Req. | Unknown/Unavailable | Freshness | Quality/Safety | Fallback |
| --- | --- | --- | :---: | --- | --- | --- | --- |
| `outdoor_temperature` | number | °C | ja | beide diagnostizierbar, bei reject kein Wert | TTL 1800 s, D/HA | safety-relevant | reject |
| `outdoor_humidity` | number | % | nein | optional unknown/unavailable | TTL 1800 s, D/HA | informational | reject |
| `pressure` | number | hPa | nein | optional unknown/unavailable | TTL 3600 s, D/HA | informational | reject |
| `illuminance` | number | lx | nein | optional unknown/unavailable | TTL 1800 s, D/HA | informational | reject |
| `weather_state` | text | – | nein | optional unknown/unavailable | TTL 1800 s, D/HA | informational | reject |
| `available` | boolean | – | ja | fehlend/unknown -> `false` mit Diagnose | TTL 1800 s, D/HA | safety-relevant; SD degraded/conservative | SD `false` |

Hitze- oder Lichtentscheidungen werden nicht vom Contract getroffen.

### `technical_device.v1`

| Feld | Typ | Einheit | Req. | Unknown/Unavailable | Freshness | Quality/Safety | Fallback |
| --- | --- | --- | :---: | --- | --- | --- | --- |
| `available` | boolean | – | ja | fehlend/unknown -> `false` mit Diagnose | TTL 900 s, D/HA | safety-relevant; SD degraded/conservative | SD `false` |
| `device_state` | text | – | nein | optional unknown/unavailable | TTL 900 s, D/HA | informational | reject |
| `is_powered` | boolean | – | nein | optional unknown/unavailable | TTL 900 s, D/HA | informational | reject |
| `power_w` | number | W | nein | optional unknown/unavailable | TTL 900 s, D/HA | informational | reject |
| `battery_level` | number | % | nein | optional unknown/unavailable | TTL 3600 s, D/HA | informational | reject |
| `charging` | boolean | – | nein | optional unknown/unavailable | TTL 900 s, D/HA | informational | reject |

Plug-Schutz, Lautstärke, Notification Routing oder andere Policy-/Apply-
Entscheidungen sind ausdrücklich ausgeschlossen.

## 10. Read-only WebSocket

Die fünf Befehle bleiben getrennt:

- `benni_core_contracts/list_contracts`
- `benni_core_contracts/get_contract`
- `benni_core_contracts/get_diagnostics`
- `benni_core_contracts/get_graph`
- `benni_core_contracts/get_health`

Jede Antwort besitzt `payload_version=1`, `command`, die monotone Graph-
`revision` und ein `delta`-Objekt. `delta.mode=revision_reconciliation` ist
die v1-Delta-Fähigkeit: ein Client darf bei gleicher `since_revision` die
Darstellung unverändert lassen; bei einer anderen Revision erhält er den
vollständigen, stabil identifizierten Snapshot und kann selbst feldweise
reconciliieren. Inkrementelle Patch-Operationen sind nicht Teil von v1.

Stabile Objekt-IDs sind `contract_id`, `projection_id`, `signal_id`,
`binding_id`, `fusion_id` sowie die Kombination aus `schema_id` und
`schema_version`. Sie dürfen nicht aus Listenpositionen abgeleitet werden.

Pure Clients verwenden bei Fehlern dieses Format:

```json
{
  "payload_version": 1,
  "command": "benni_core_contracts/get_contract",
  "error": {"code": "not_found", "message": "..."}
}
```

Der HA-Transport nutzt zusätzlich sein standardisiertes `id`-/`success`-/
`error`-Envelope. v1 registriert ausschließlich read-only Befehle. Spätere
Config-Schreibbefehle benötigen eine getrennte Payload-Version, explizite
Auth-/Admin-Grenze, ConfigEntry-Validierung und eine eigene Freigabe; sie sind
hier nicht vorhanden.

## 11. No-op-Grenzen und Evidenzlage

Der Gate-Pack-Code enthält keine Entity-Plattform, keine Service-Calls,
keine Actuation und keine Policy-Entscheidung. Die öffentliche Allowlist ist
leer; in Shadow Mode werden auch erlaubte Kandidaten nicht projiziert.

Die Tests laufen ohne Home Assistant und ohne Live-System. Offen bleiben die
konkrete produktive Source-Auswahl, reale Gerätezeitstempel pro Quell-
Integration, spätere Authentifizierung und die fachliche Freigabe eines
etwaigen Published-Modus. Diese Punkte sind Evidenz-/Entscheidungslücken und
werden nicht durch Annahmen im Gate Pack geschlossen.
