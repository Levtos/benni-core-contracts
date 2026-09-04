# Benni Owner-/Required-Field-Gate v1

> Historischer Evidence-Gate (Stand 2026-07-23). Die damalige Eltern-
> `parent_future`-Grenze ist für diesen Gate-Scope erhalten, aber durch Issue
> #21 als globale Registry-/Runtime-Zulassungssperre superseded.

Dieses Gate legt den damaligen produktiven Ziel-Scope und die Required-Feld-
Regeln für `benni_core_contracts` fest. Es ist eine interne,
read-only Evidence-Prüfung innerhalb der Kette

`SourceBinding -> AtomicSignal -> Fusion -> PublishedContract -> DiagnosticProjection`.

Das Gate aktiviert keine SourceBinding, verändert keine ConfigEntry, erzeugt
keine HA-Entity und trifft keine Policy- oder Actuation-Entscheidung.

## 1. Owner-Scope

Benni ist der einzige produktive Zielhaushalt dieses historischen Gates:

| Profil | Aktivierungsscope | Produktives Ziel | ConfigEntry-/Binding-Aktivierung in v1 |
| --- | --- | --- | --- |
| Benni | `benni_production` | ja | nein; nur Gate-Evidence |
| Eltern | `parent_future` | nein | verboten; vollständig `out_of_scope` |

Der Scope ist im Modell als `ProfileScope` und in jedem
`SourceBindingEvidence`-Datensatz festgehalten. `SourceBindingEvidenceMatrix.active_candidates()`
liefert ausschließlich Benni-Records; Eltern-Records bleiben für gemeinsame
Fixtures und Graph-Semantik über `parent_future_records()` sichtbar, sind aber
nicht aktivierbar.

Benni und Eltern verwenden weiterhin dieselben Contract-, Graph- und
Fixture-Funktionen. Unterschiede liegen nur in Quellen, Räumen, Bindings und
optionalen Fähigkeiten. Es gibt keinen getrennten Eltern-Logikbaum.

Für die aktuelle produktive Registry gelten `benni` und `eltern` als Profile
derselben Engine. Produktive Eltern-Bindings entstehen ausschließlich durch
einen expliziten, validierten Registry-Write und nicht aus den Evidence-
Datensätzen dieses Gates.

## 2. Required-Field-Entscheidung

Die Requiredness wird aus den aktuellen v1-Schemas abgeleitet und für Benni
explizit als elf Regeln geführt:

| Contract-Feld | Raum-/Aggregat-Scope | Required | Auswahlregel | zulässige Freshness | Safety/Fallback |
| --- | --- | --- | --- | --- | --- |
| `room_climate.v1:temperature` | living, kitchen, bathroom | ja | je Raum `any_healthy` | `device_timestamp` oder echtes nicht-retained `ha_timestamp` | safety-relevant, `reject` |
| `room_climate.v1:available` | je Raum | ja | interne Ableitung aus Temperatur-Gate | abhängig von der Feld-Evidence | technische Availability, ausdrücklich `safe_default=false` möglich; Gate besteht damit nicht |
| `opening.v1:opening_state` | alle Benni-Kontakte | ja | `all_required` | Gerätezeit oder ausdrücklich akzeptiertes echtes HA-State-Event | consumer-critical, `reject` |
| `opening.v1:available` | Aggregat | ja | interne Ableitung aus Opening-Gate | abhängig von Opening-Evidence | technische Availability, kein physischer Zustand |
| `weather_environment.v1:outdoor_temperature` | outdoor | ja | `any_healthy` | `device_timestamp` oder echtes nicht-retained `ha_timestamp` | safety-relevant, `reject` |
| `weather_environment.v1:available` | outdoor | ja | interne Ableitung aus Temperatur-Gate | abhängig von Temperature-Evidence | technische Availability, kein Wetter-/Policy-Ziel |
| `technical_device.v1:available` | Benni-Rollo-Technical-Device | ja | interne Ableitung aus technischer Device-State-Evidence | abhängig von `device_state`-Evidence | technische Availability, kein Positions- oder Policy-Claim |

Die drei Raumtemperaturen und drei Raum-Availability-Regeln sind jeweils
raumbezogene Instanzen desselben Schemafeldes. `is_open` und `source_count`
sind im Schema optional; `is_open` bleibt ausschließlich eine Projektion von
`opening_state` und erhält keine eigene Rohquelle.

Lock-State und Cover-Position sind in den aktuellen v1-Schemas nicht als
Required-Felder vorgesehen. Sie erscheinen deshalb nur als
`EVIDENCE_ONLY`-/Diagnosefälle der Source-Binding-Matrix. Es wird kein neues
Lock- oder Cover-Contract-Feld erfunden.

## 3. Laufzeitstatus `pass`, `degraded`, `blocked`

Die Required-Field-Regel und die konkrete Laufzeit-Evidence sind getrennt:

| Status | Verbindliche Bedeutung | Required-Gate |
| --- | --- | --- |
| `pass` | Alle für die Regel erforderlichen Quellen liefern gültige Werte mit zulässiger, frischer Evidence; bei physischem State ist die positive Aussage zusätzlich fachlich valide. | Feld darf das Required-Gate bestehen; es bleibt trotzdem nicht aktiviert. |
| `degraded` | Ein verwertbarer Wert/Evidence-Pfad existiert, aber mindestens eine alternative oder ergänzende Evidence ist suspect/stale bzw. qualitativ degradiert. | Required-Feld bleibt nicht bereit; physische positive Claims sind nicht erlaubt. |
| `blocked` | Evidence fehlt, ist nicht zulässig, retained/restored/stale, konfliktär, ohne erforderliche Zeitquelle oder der Wert ist unknown/unavailable/ungültig. | Required-Gate bleibt blockiert. |

Ein Required-Availability-Wert `false` kann als technische Beobachtung im
Contract sichtbar bleiben, besteht aber nie das Required-Gate. Ein fehlender
oder nicht geprüfter Derived-Dependency-Status ergibt
`derived_evidence_not_evaluated` und `blocked`.

Der Gate-Result enthält immer `activation_allowed=false`. Auch ein
synthetischer `pass` ist daher nur eine Evidence-Aussage und keine
Produktionsfreigabe.

## 4. Physische Zustände

Für Opening, Lock und Position gelten unabhängig vom Owner-Gate:

- fehlende, retained, restaurierte, stale oder konfliktäre Evidence darf
  niemals `open`, `closed`, `locked`, `unlocked` oder eine Position behaupten;
- der fachliche Zustand bleibt `unknown`, wenn die physische Evidence nicht
  belastbar ist;
- Health wird `blocked` oder `degraded`, Quality wird feldbezogen
  `unavailable`, `unknown`, `suspect`, `stale` oder `conflict`;
- Safety wird `unknown` oder `unsafe`, niemals durch einen Safe Default
  positiv gemacht;
- `fallback=reject` ist zwingend; `safe_default` ist für physische Zustände,
  Locks und Positionen verboten.

`available=false` ist davon getrennt eine technische Verfügbarkeitsaussage.
Sie darf bestehen bleiben, aber kein Required-Evidence-Gate bestehen lassen.

## 5. Freshness-Evidence

Für die Benni-Required-Felder gilt:

- `device_timestamp` ist nur mit belegtem Gerätezeitpfad und plausibler
  Zeitrichtung fresh;
- `ha_timestamp` ist nur bei einem echten, nicht-retained HA-State-Change
  zulässig, sofern die jeweilige Feldregel HA-Evidence ausdrücklich erlaubt;
- `received_at`, `last_updated`, ein Poll-Zeitpunkt oder ein bloßer
  Listener-Eingang sind allein kein Freshness-Nachweis;
- retained MQTT bleibt mindestens `suspect`/`stale`, Restore bleibt
  `restored`, unbekannte und zukünftige Zeitstempel bleiben `unknown`;
- Batterie-, Lade- und Availability-Werte belegen niemals die Freshness des
  fachlichen Zustands.

Safety-Grenzen:

| Feld | HA-Beobachtungszeitpunkt ausreichend? | Gerätezeitstempel |
| --- | --- | --- |
| Room-/Environment-Messwert | ja, wenn echtes nicht-retained Event explizit akzeptiert ist | weiterhin zu belegen |
| Opening-Aggregat | ja, nach expliziter nicht-retained State-Event-Regel | bevorzugt, aktuell nicht belegt |
| Lock-State | nein | zwingend erforderlich |
| Cover-Position | nein | zwingend erforderlich |

## 6. Kanonische Lock-Evidence

Die im vorherigen read-only Live-/Domain-Snapshot beobachtete aktuelle
Lock-Entity ist:

`lock.flur_aqara_smart_lock_u200`

Sie ist in der Matrix die einzige aktuelle `source_entity` für `lock_state`
und als `LIVE_VERIFIZIERT` dokumentiert. Die alte ID

`lock.aqara_smart_lock_u200`

ist ausschließlich als `historical_source_entity` am Evidence-Datensatz
geführt. Sie ist keine aktuelle Binding-ID, kein aktiver Matrix-Source-Eintrag
und darf nicht in eine ConfigEntry übernommen werden.

Der Lock-Contract ist trotzdem nicht freigegeben: Für die kanonische Entity
fehlt ein belastbarer Gerätezeitstempel, die alte Import-ID und die live
beobachtete ID waren nicht identisch, und der Datensatz bleibt deshalb
`conflict`/`blocked`. Ein Batterie-Wert wird nur diagnostisch geführt und löst
keinen Lock-Freshness-Gate aus.

Für die aktuelle Implementierung liegt keine neue Registry-Schreib- oder
Aktivierung vor. Eine spätere read-only Registry-/Live-Revalidierung muss die
kanonische ID, Ownership, State-Semantik und den Gerätezeitpfad erneut
bestätigen, bevor ein Lock-Contract überhaupt entworfen wird.

## 7. Rollo/Cover

`cover.wohnbereich_thermo_verdunklungsrollo` bleibt ein
`EVIDENCE_ONLY`-Sonderfall für technische Beobachtung und Position. Die
Position verlangt Gerätezeitstempel; bei fehlender Evidence bleibt sie
`unknown`. `cover.living_blackout_blind` ist nur dokumentierte
Policy-/Legacy-Evidence und bleibt `excluded`. Es gibt keinen Rollo-Zielwert,
keine Privatsphäre-/Hitzeentscheidung und keine Actuation im Core-Contract.

## 8. Historisches Eltern-Out-of-Scope-Gate

Für diesen historischen Evidence-Gate bleibt Eltern vollständig
`parent_future`/`out_of_scope`; das ist keine aktuelle Registry-/Runtime-
Sperre:

- Eltern-Fixtures und gemeinsame Graph-Regeln bleiben zulässig;
- Eltern erhält keine produktive SourceBinding;
- Eltern erhält keine produktive Allowlist, keine ConfigEntry-Aktivierung und
  keine Published Entity;
- Eltern-Records dürfen konkrete read-only Evidence oder offene Quellen zeigen,
  sind aber aus dem Benni-Required-Gate und aus `active_candidates()` entfernt;
- neue Eltern-Evidence darf den Benni-Produktionsstatus nicht verändern.

## 9. Offene Evidence-Gaps

- aktuelle read-only Registry-/Live-Revalidierung der kanonischen Lock-ID;
- belastbarer Gerätezeitpfad für Lock und Cover-Position;
- Nachweis echter nicht-retained State-Events für die Benni-Required-Quellen;
- fachliche Bestätigung der vollständigen Opening-Kontaktmenge;
- genaue Dependency-/Availability-Semantik des technischen Rollo-Gates;
- spätere ausdrückliche Entscheidung über eine Entity-Allowlist und einen
  Published-Modus.

Bis diese Lücken geschlossen sind, bleibt die konkrete Laufzeitentscheidung
für nicht vorgelegte Beobachtungen `blocked`/`OFFEN`. Es wird keine Live- oder
Zeitstempel-Evidence erfunden.

## 10. Boundary

Der Gate-Slice erzeugt weiterhin **0 HA-Entities**, besitzt keine
Entity-Plattform, keine Services und keinen Actuation- oder Policy-Import.
Die Matrix und der Gate-Result sind interne Datenmodelle und keine
öffentliche HA-Projektion.
