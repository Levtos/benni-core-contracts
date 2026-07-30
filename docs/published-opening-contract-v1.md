# Benni Published Opening Contract v1

## Zweck und Freigabegrenze

Dieses Dokument beschreibt den ersten ausdrücklich veröffentlichbaren
`PublishedContract` in `benni_core_contracts`. Es ist ein einzelner Benni-
Pilot für `opening.v1`, nicht die allgemeine Freigabe der Integration.

Der Datenweg bleibt:

```text
binary_sensor.* (read-only)
  -> SourceBinding
  -> AtomicSignal
  -> opening_* Fusion
  -> benni.opening.kitchen_patio_door
  -> sensor.benni_opening_kitchen_patio_door
```

Nur eine ConfigEntry mit allen folgenden Bedingungen darf die Entity-
Plattform `sensor` weiterleiten:

- `profile=benni`
- `mode=published` ausdrücklich gesetzt
- `published_contracts=["benni.opening.kitchen_patio_door"]`
- `entity_allowlist=["sensor.benni_opening_kitchen_patio_door"]`
- genau zwei read-only SourceBindings
- die beiden aktuell read-only verifizierten Quellen sind ausgewählt

Der Default bleibt `shadow_only`. Er lädt keine Entity-Plattform und erzeugt
keine HA-Entity. Matrix- und Fixture-Daten werden niemals automatisch in eine
ConfigEntry übernommen.

## Verifizierte Pilotquellen

Die am 30.07.2026 read-only gegen Einhornzentrale beobachteten Quellen sind:

| Binding-Feld | Entity | Domain | Plattform | Beobachteter Zustand |
| --- | --- | --- | --- | --- |
| `open_contact` | `binary_sensor.kitchen_patio_door_open_contact` | `binary_sensor` | MQTT | `off` |
| `tilt_contact` | `binary_sensor.kitchen_patio_door_tilt_contact` | `binary_sensor` | MQTT | `on` |

Beide Quellen besitzen eine MQTT-ConfigEntry und konkrete `last_changed`/
`last_updated`-Werte. Es wurde kein belastbarer Gerätezeitstempel und kein
explizites Retained-Attribut aus dem HA-State-Eintrag ermittelt. Deshalb wird
ein beim Setup gelesener Zustand nicht als fresh gewertet. Erst ein echtes,
nicht-retained HA-State-Change-Event darf als Beobachtungs-Freshness dienen.

Die Quell-Entity-IDs sind im Config Flow als Auswahl auf diesen verifizierten
Pilot begrenzt. Ändert sich die reale Geräte-/Entity-Zuordnung, bleibt die
Freigabe blockiert, bis eine neue Evidence-Prüfung und eine neue explizite
Binding-Entscheidung vorliegt.

## Fachliche Zustände

Die Fusion normalisiert die beiden MQTT-Rohzustände, ohne sie als bereits
fertige Contract-Werte zu behandeln:

| Öffnungskontakt | Kippkontakt | `opening_state` | `is_open` |
| --- | --- | --- | --- |
| `off` | `off` | `closed` | `false` |
| `off` | `on` | `tilted` | `false` |
| `on` | `off` | `open` | `true` |
| `on` | `on` | `unknown` | `unknown` |

Für fehlende, initial gelesene, stale, retained, restaurierte oder
widersprüchliche Evidence gilt immer:

- `opening_state=unknown`
- `is_open=unknown`
- kein Safe Default für einen physischen Zustand
- `fallback=reject` für die physischen Felder
- `health=blocked` oder `degraded` und passende Quality-/Freshness-/Safety-
  Attribute
- eine feldbezogene Diagnose mit Root Cause, statt einer positiven Aussage

`available=false` ist nur die technische Aussage, dass das Opening-Evidence-
Gate nicht bestanden ist. Es ist keine Behauptung, dass die Tür geschlossen
ist. Bei einem Konflikt wird auch die Contract-Verfügbarkeit nicht positiv
ausgegeben; die Rohquellen bleiben in der Diagnose sichtbar.

## Entity-Projektion

Die einzige Entity des Piloten ist:

```text
sensor.benni_opening_kitchen_patio_door
```

Ihr State ist ausschließlich `closed`, `tilted`, `open` oder `unknown`.
Quality, Health, Freshness, Safety, `is_open`, Quell-Entity-IDs und die
feldbezogene Diagnose werden als Attribute beziehungsweise über die bestehende
read-only WebSocket-/UX-Struktur bereitgestellt. Die Entity kann die
konfigurierten Pilot-Quellen mit ihrem zuletzt beobachteten Roh-State und
Evidence-Umschlag als `source_snapshots` ausweisen. Es gibt keine Entity für:

- die beiden Rohquellen,
- AtomicSignals,
- Fusionen,
- Fallbacks,
- Diagnosefelder,
- Policy-Zwischenwerte oder
- andere Contracts.

Die bisherige UX-/WebSocket-Struktur bleibt bestehen. Eine separate
`UpdateEntity`-/`update.py`-Plattform ist im aktuellen Repository-Stand nicht
vorhanden; es wurde keine bestehende Update-Entity entfernt oder umgebaut.

## Aktueller Live-Status

Die laufende Einhornzentrale-ConfigEntry ist weiterhin der bestehende
Shadow-Stand mit leerer Allowlist. Der Code dieses Branches wurde nicht in HA
aktiviert, und die Live-Registry wurde nicht verändert. Daher ist die oben
genannte Entity aktuell **noch nicht live erzeugt**.

Für eine spätere technische Prüfung muss Benni die Integration ausdrücklich
über den Options-/Config-Flow in den Published-Pilot-Modus setzen, die beiden
angezeigten Quellen auswählen und anschließend den normalen HA-Reload/Restart-
Weg ausführen. Das ist eine separate Aktivierung und keine automatische
Freigabe. Erst danach darf geprüft werden, ob genau eine Entity erscheint und
ob ein echtes State-Change-Event einen fachlichen Zustand liefert.

## Grenzen

Es gibt weiterhin keine Services, Actuation, Policy-Imports, Migration,
Consumer-Umstellung, Core-Devices-Änderung, Lock-/Cover-Veröffentlichung oder
Eltern-Aktivierung. Eltern bleibt `parent_future`/`out_of_scope`.
