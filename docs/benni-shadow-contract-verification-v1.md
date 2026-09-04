# Benni Read-Only Shadow Contract Verification Gate v1

Stand: 2026-07-23. Dieses historische Gate prüft ausschließlich das Profil
`benni` gegen
explizit vorgelegte, read-only Source-Evidence. Es erzeugt weder eine
produktive SourceBinding noch eine ConfigEntry-Aktivierung, HA-Entity,
Allowlist-Freigabe, Service, Actuation, Policy-Entscheidung oder
Consumer-Umstellung.

Innerhalb dieser historischen Shadow-Auswertung bleibt Eltern vollständig
`parent_future` und `out_of_scope`. Gemeinsame Schema-, Graph- und Fixture-
Logik darf Eltern enthalten; ein Eltern-Profil oder eine Eltern-Binding wird
vor dieser Benni-Evidence-Auswertung abgewiesen. Das ist keine Sperre für die
produktive RegistryRuntime.

## Einordnung und Datenfluss

Die Auswertung ist eine zusätzliche read-only Projektion des bestehenden
internen Graphen:

```text
SourceBinding -> AtomicSignal -> Fusion -> PublishedContract
                                      |             |
                                      +--> DiagnosticProjection
                                                    |
                                                    +--> Shadow Contract Verification v1
```

`ShadowRuntime.benni_contract_verification()` kopiert vorhandene interne
Signale in explizite `ShadowSourceObservation`-Datensätze. Die originale
`TemporalEvidence` bleibt erhalten. Ein Restore, retained MQTT, `received_at`,
Batterieprozente oder bloßes HA-`last_updated` kann dadurch nicht nachträglich
zu frischer Geräte-Evidence werden.

Die Projektion ist kein Published-Modus:

```text
mode = shadow_only
activation_allowed = false
config_entry_activated = false
entity_ids = []
```

## Versioniertes Ergebnisformat

`BenniShadowVerificationReport` und `ShadowContractVerification` verwenden
`verification_version=1`. Pro Contract und Feld enthält das Ergebnis:

- `contract_id`, `schema_id`, `schema_version`, `profile` und Feldname;
- Ergebnis `pass`, `degraded` oder `blocked` sowie Wert oder `unknown`;
- `active_binding_ids`, `active_source_entity`, `source_entities`,
  `source_state`, `source_attributes` und `source_observations`;
- `fallback_chain`, zum Beispiel `first_healthy`,
  `fallback_to:<binding_id>`, `reject`;
- `quality`, `health`, `freshness`, `safety`, Vollständigkeit und
  `physical_claim_allowed`;
- Root Cause, Reason-Codes, betroffene und nicht betroffene Fähigkeiten und
  Consumer-Auswirkung.

Die stabilen IDs sind Contract-ID, Schema-Version, Feldname, Binding-ID und
konkrete Source-Entity. Eine spätere WebSocket-Projektion kann diese Struktur
als Payload verwenden, ohne daraus eine HA-Entity abzuleiten. Dieses Gate fügt
keinen neuen WebSocket-Befehl und keine Schreib- oder Admin-Schnittstelle hinzu.

## Benni-Required-Feldregeln

Die aktuelle Produktionsentscheidung ist für jede fehlende **aktuelle**
read-only Source-Observation `blocked`/`OFFEN`. Die im Source-Binding-Gate
erfassten Entity-/State-Snapshots sind historische Evidenz, nicht automatisch
ein neuer Freshness-Nachweis dieses Gates.

| Contract / Feld | Required | `pass` | `degraded` | `blocked` / ohne aktuelle Evidence | Fallback / Safety |
| --- | --- | --- | --- | --- | --- |
| `room_climate.v1:temperature` je living, kitchen, bathroom | ja | gültiger Wert mit Gerätezeitstempel oder ausdrücklich akzeptiertem echten, nicht-retained HA-State-Event innerhalb TTL | nur feldlokale optionale Zusatz-Evidence | `unknown`; Raum-Gate nicht bereit | `reject`; safety-relevant |
| `room_climate.v1:available` je Raum | ja | aus bestandenem Temperatur-Evidence-Gate abgeleitet | abgeleitete Zusatz-Evidence degradiert | `unknown` oder technisches `false`; nie Required-ready | `safe_default=false` nur technisch |
| `opening.v1:opening_state` | ja | `open`, `closed` oder `tilted` nur mit vollständiger, konfliktfreier frischer Evidence | nicht Required-ready | immer `unknown`; niemals `open` oder `closed` | `reject`; consumer-critical |
| `opening.v1:available` | ja | aus bestandenem Opening-Gate abgeleitet | abgeleitete Zusatz-Evidence degradiert | `unknown` oder technisches `false`; nie Required-ready | `safe_default=false` nur technisch |
| `weather_environment.v1:outdoor_temperature` | ja | gültige frische Temperatur-Evidence | nur feldlokale optionale Abweichung | `unknown`; Required-Gate nicht bereit | `reject`; safety-relevant |
| `weather_environment.v1:available` | ja | aus bestandenem Outdoor-Temperatur-Gate abgeleitet | abgeleitete Zusatz-Evidence degradiert | `unknown` oder technisches `false`; nie Required-ready | `safe_default=false` nur technisch |
| `technical_device.v1:available` | ja | aus frischer technischer Device-State-Evidence abgeleitet | technische Zusatzfelder können degradiert bleiben | `unknown` oder technisches `false`; nicht bereit | `safe_default=false`; keine Positions-/Policy-Aussage |

Die übrigen Schemafelder bleiben sichtbar und feldbezogen. Ein retained
`outdoor_humidity` degradiert nur dieses Wetterfeld; gültige Outdoor-Temperatur
und technische Device-Fakten bleiben unabhängig. Cover, Lock und andere
Evidence-only-Fälle werden durch einen Weather-Fehler nicht verändert.

## Freshness, Availability und physische Zustände

- `device_timestamp` ist innerhalb TTL zulässig, wenn der Gerätezeitpfad
  selbst belegt ist.
- `ha_timestamp` ist nur bei einem echten nicht-retained HA-State-Event
  zulässig, wenn das Feld dies erlaubt.
- `received_at`, Batterieprozente, Restore und `last_updated` allein begründen
  niemals `fresh`.
- retained MQTT ist `suspect`, Restore `restored`, unbekannte Zeit `unknown`;
  alle drei bestehen kein Required-Gate.
- zukünftige oder unplausible Zeitstempel bestehen ebenfalls nicht.

Für `opening_state`, Lock-State und Cover-Position wird nie ein positiver
physischer Zustand aus fehlender, stale, retained, restaurierter oder
widersprüchlicher Evidence abgeleitet. Der Shadow-Wert lautet dann `unknown`,
`physical_claim_allowed=false` und die Fallback-Kette endet bei `reject`.
`available=false` ist ausschließlich technische Verfügbarkeit, nie ein
Evidence-Pass.

`health`, `quality`, `freshness`, `safety` und fachlicher Wert bleiben
getrennt. Ein `blocked` Opening behauptet nicht, dass das Fenster offen,
geschlossen oder sicher sei. Ein Fehler in einem Weather-Feld macht weder einen
validen technischen Device-State noch eine Cover-Evidence ungültig.

## Aktueller Benni-Status

In diesem Gate stand keine neue read-only Registry-/Live-Abfrage zur Verfügung.
Es wurde deshalb keine aktuelle Event-, State-, Gerätezeit- oder Ownership-
Evidence geschätzt oder aus den Fixtures übernommen.

| Bereich | Gate-Status | Begründung |
| --- | --- | --- |
| Room Climate: drei Temperatur-/Availability-Instanzen | `blocked` / `OFFEN` | aktuelle nicht-retained Event- oder Gerätezeit-Evidence fehlt diesem Lauf |
| Opening-State und Availability | `blocked` / `OFFEN` | aktuelle vollständige Kontakt-, Zeit- und Konflikt-Evidence fehlt diesem Lauf |
| Outdoor-Temperatur und Availability | `blocked` / `OFFEN` | aktuelle Source-Event-/Zeit-Evidence fehlt diesem Lauf |
| technische Device-Availability | `blocked` / `OFFEN` | aktuelle Device-State-/Zeit-Evidence fehlt diesem Lauf |
| Lock-State | `blocked` / `conflict`, Evidence-only | siehe Lock-Revalidierung |
| Cover-Position | `blocked` / `OPEN`, Evidence-only | Gerätezeitpfad fehlt |

Die Tests enthalten positive synthetische Benni-Evidence für den `pass`-Pfad,
aktive Quellen und Fusion-Fallbacks. Das ist kein Live-Pass und befüllt keine
produktive ConfigEntry.

## Lock- und Cover-Evidence-only

Die historische Lock-ID `lock.aqara_smart_lock_u200` ist keine aktuelle
SourceBinding und wird nicht akzeptiert. Die aus dem vorherigen read-only
Snapshot stammende kanonische Kandidaten-ID lautet:

`lock.flur_aqara_smart_lock_u200`

Sie bleibt als aktuelle Matrix-`source_entity` geführt, muss aber vor einer
späteren Contract-Entscheidung erneut read-only gegen Registry-/Live-Evidence
bestätigt werden. Ohne bestätigte Source-Ownership und belegten
Gerätezeitstempel ergibt `verify_evidence_only_binding()` `blocked`,
`conflict`, `unknown`; es entsteht keine positive Lock-Aussage. Eine Batterie
ist nur Diagnosedaten und kein Lock-Freshness-Nachweis.

`cover.wohnbereich_thermo_verdunklungsrollo` und seine Position bleiben
Evidence-only. Die Position benötigt einen Gerätezeitstempel. Weder Lock noch
Cover-Position werden zu Published Contract, HA-Entity oder Policy-Ziel.

## Test-Evidence

Die synthetischen Fixtures und Tests belegen lokal ohne Live-System:

- normale gültige Benni-Evidence für Room Climate, Opening, Weather und
  Technical Device;
- fehlende Source, `unavailable`, `unknown`, stale, retained MQTT, Restore
  und widersprüchliche Quellen;
- `first_healthy`-Fallback auf eine frische alternative Temperaturquelle;
- partielle Weather-Degradierung ohne Degradierung eines gültigen technischen
  Device-Contracts;
- Lock ohne Gerätezeit-/Ownership-Evidence und Ablehnung der alten Lock-ID;
- Ablehnung eines Eltern-Profils oder einer Eltern-Binding;
- 0 HA-Entities, keine ConfigEntry-Aktivierung, keine Entity-Plattform,
  Services, Actuation oder Policy-Imports.

## Offene Live-Evidence-Gaps

1. Neue read-only Registry-/Live-Revalidierung der kanonischen Lock-ID,
   Ownership, State-Semantik und Gerätezeitpfad.
2. Pro Benni-Required-Quelle ein nachweisbar echtes, nicht-retained
   State-Change-Ereignis oder ein echter Gerätezeitstempel.
3. Vollständige Opening-Kontaktmenge und Konfliktregel.
4. Technische Device-State-/Availability-Abhängigkeit des Rollo.
5. Gerätezeitpfad für Cover-Position.
6. Erst separat: Entity-Allowlist, Published-Modus sowie WebSocket-Auth- und
   Admin-Grenzen.

Bis diese Evidenz vorliegt, bleibt Issue `ha-platform/control#57` auf
`status/testing`.
