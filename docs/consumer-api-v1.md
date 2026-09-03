# Interne Consumer API v1

Issue #20 stellt eine typisierte, interne Austauschgrenze über dem bestehenden
`RegistryRuntime` bereit. Consumer-Integrationen lesen fachliche Contracts und
abonnieren relevante Änderungen über diese API. Sie kennen weder PostgreSQL,
`PostgresRegistryRepository`, Registry-Tabellen, die mutable
`SignalGraph`-Struktur noch die konkreten Home-Assistant-Rohentitäten.

## Architekturgrenze

```text
Owner-Integration
    -> SourceBinding/Fusion/Contract-Instance
    -> RegistryDomainService (#17)
    -> RegistryRuntime (aktivierter Snapshot)
    -> ConsumerApi (#20)
    -> Consumer-Integration
```

Die Owner-Integration liefert die fachliche Wahrheit über die bereits
vorhandenen `SourceBinding`-, `Fusion`- und Contract-Modelle. Der
`RegistryDomainService` validiert und aktiviert die Konfiguration. Die
`ConsumerApi` projiziert daraus defensive DTOs. Sie besitzt keinen eigenen
Store und keinen Schreibpfad in die Registry.

Runtime-, State-, Freshness-, Quality-, Discovery- und Health-Ereignisse
aktualisieren ausschließlich den bestehenden Graphen. Die Consumer-Grenze
beobachtet diesen Graphen; sie kann keine Registry-Konfiguration schreiben.

## Consumer deklarieren Requirements

Jeder Consumer verwendet eine stabile technische ID und registriert seine
fachlichen Abhängigkeiten selbst:

```python
from custom_components.benni_core_contracts.consumer_api import (
    ConsumerApi,
    ConsumerRequirement,
)

requirement = ConsumerRequirement.contract(
    "media.activity.v1",
    schema_id="media_activity",
    min_supported_schema_version=1,
    required_fields=("active",),
)
api.register_consumer("core_state", (requirement,))
```

Alternativ akzeptiert `register_consumer()` eine vollständige
`ConsumerDeclaration`. Eine Registrierung mit derselben ID ist ein Fehler,
sofern nicht ausdrücklich `replace_existing=True` verwendet wird. Die
Requirement wird dabei an die technische Consumer-ID gebunden; Anzeigenamen
sind nicht Teil der Identität.

`ConsumerRequirement.binding_role("media_activity")` deklariert statt eines
Contracts eine logische Binding-/Rollenauflösung. Diese Anforderung liefert
eine sichere `ConsumerBinding`-Projektion und keine `SourceBinding`-Instanz.

Der Dependency-Stand ist diagnostisch abfragbar:

```python
impact = api.impact_for("core_state")
for requirement_state in impact.requirements:
    print(requirement_state.status, requirement_state.reason)
```

Damit lässt sich erkennen, welcher Consumer von einem fehlenden, degradierten,
blockierten oder inkompatiblen Contract betroffen ist. `all_impacts()` liefert
den Report für alle registrierten Consumer.

## Snapshot, Feld und Quality

Ein Consumer lädt zuerst einen Snapshot und liest danach einzelne Felder:

```python
snapshot = api.get_contract_snapshot(requirement=requirement)
field = snapshot.field("active")

value = field.value
quality = field.quality
freshness = field.freshness
health = snapshot.health
lineage = field.lineage
revision = snapshot.revision
```

Die Rückgaben sind typisierte, eingefrorene Consumer-DTOs. Werte werden an der
Grenze defensiv kopiert. Revision-Metadaten enthalten nur Profil, Revisions-ID,
Registry-Schema-Version, Quelle (`postgresql` oder `last_known_good`), Registry-
Health und Graph-Revision; die Registry-Payload wird nicht ausgegeben.

`ConsumerLineage` macht für Diagnosezwecke aktive und Kandidaten-Binding-,
Source- und Entity-IDs sichtbar. Ein Contract-Consumer muss daraus keine
Rohquelle verwenden. Die fachliche Abhängigkeit bleibt der Contract.

`get_field()`, `get_quality()`, `get_freshness()`, `get_health()` und
`get_lineage()` sind Convenience-Aufrufe über denselben Snapshot-Zugriff.
`resolve_binding()` bzw. `resolve_role()` lösen eine Rolle oder Capability auf
eine eindeutige stabile Binding-ID auf. Kein Aufruf gibt interne Repository-
oder Graphobjekte zurück.

## Eindeutige Fehler- und Statussemantik

`lookup_contract()` liefert ein `ContractLookup` mit einem expliziten
`ConsumerAccessStatus`. Die Convenience-Methoden werfen die jeweils typisierte
`ConsumerApiError`-Unterklasse. Dadurch ist `None` nicht die gemeinsame
Bedeutung für alle Fehler:

| Status | Bedeutung |
| --- | --- |
| `healthy` | Contract vorhanden und fachlich gesund |
| `degraded` | Contract vorhanden; Quality/Fallback ist degradiert |
| `blocked` | Contract-Snapshot vorhanden, aber nicht konsumierbar |
| `unknown` | Contract vorhanden, Health ist nicht entscheidbar |
| `missing` | Contract ist im aktiven Runtime-Stand nicht vorhanden |
| `field_missing` | Ein vom Consumer gefordertes Feld fehlt |
| `schema_mismatch` | `schema_id` passt nicht |
| `version_incompatible` | Erwartete Version oder Mindestversion passt nicht |
| `runtime_not_ready` | Für das Profil ist noch kein aktiver Snapshot bereit |
| `binding_ambiguous` | Eine logische Rolle passt auf mehrere Bindings |

Ein `degraded` Snapshot bleibt lesbar und trägt seine Quality-/Freshness-
Information. Ein `blocked` Snapshot bleibt als Diagnose sichtbar, wird aber
über `.consumable == False` eindeutig vom gesunden/degradierten Ergebnis
unterschieden. Bei fehlendem Contract oder nicht bereitem Runtime-Stand gibt es
keinen künstlichen leeren gesunden Wert.

## Schema- und Versionskompatibilität

Consumer können `schema_id`, `expected_schema_version` oder
`min_supported_schema_version` deklarieren:

- `expected_schema_version` ist exakt und lehnt jede andere Version ab.
- `min_supported_schema_version` akzeptiert die Mindestversion und neuere
  Versionen, sofern alle `required_fields` vorhanden sind.
- Eine additive neuere Version ist damit für Consumer mit Mindestversion
  kompatibel; benötigte Felder bleiben explizit zu deklarieren.
- Ein anderer `schema_id`, eine zu alte Version oder ein fehlendes Requirement-
  Feld führt zu einem expliziten Status bzw. einer typisierten Exception.

Es gibt keinen stillen Fallback auf eine inkompatible Version. Ein Contract-
Producer muss bei einer inkompatiblen fachlichen Änderung eine neue
Schema-Version liefern; die bestehende Revision-/Aktivierungssemantik bleibt
bei `RegistryDomainService` und `PostgresRegistryRepository`.

## Subscriptions

Der Consumer liest zuerst den aktuellen Stand und abonniert danach relevante
Updates. Die Subscription ersetzt den Snapshot-Zugriff nicht und sendet beim
Anlegen keinen impliziten Initial-Callback:

```python
def on_update(update):
    print(update.event_kinds, update.changed_fields)
    if update.snapshot is not None:
        active = update.snapshot.field("active").value

subscription = api.subscribe(
    "core_state",
    on_update,
    contract_id="media.activity.v1",
    fields=("active",),
)

# Beim Consumer-Unload:
subscription.unsubscribe()
# oder: api.cleanup_consumer("core_state")
```

Unterstützte semantische Ereignisse sind:

- `VALUE_CHANGED`
- `QUALITY_CHANGED`
- `FRESHNESS_CHANGED`
- `HEALTH_CHANGED`
- `REVISION_CHANGED`
- `AVAILABLE` / `UNAVAILABLE`

Subscriptions können auf einen Contract, eine logische Rolle und optional auf
Felder oder Ereignistypen gefiltert werden. Eine neue Registry-Revision löst
nur dann aus, wenn sich die beobachtete Contract-Definition oder ihr
veröffentlichtes Ergebnis für die Subscription relevant ändert. Eine
identische Revision mit lediglich neuer Revisionsnummer feuert keinen
fachlich unnötigen Consumer-Callback. Ein Binding-Austausch für denselben
Contract verändert dagegen die Definition/Lineage und kann
`REVISION_CHANGED`, Quality- oder Availability-Ereignisse liefern.

Callback-Fehler werden protokolliert und isoliert. Weitere Consumer, der
Runtime-Listener und Core Contracts bleiben funktionsfähig. Synchrone und
asynchrone Callbacks werden unterstützt; `ConsumerSubscription` ist
idempotent schließbar und kann als Context Manager verwendet werden. `close()`
bzw. `unload()` der API entfernt Runtime-/Graph-Listener und alle
Subscriptions, sodass kein Callback-Leak zurückbleibt.

## Owner-/Consumer-Beispiel

Eine spätere `MediaState`-Integration produziert den fachlichen Contract
`media.activity.v1`. Sie konfiguriert dafür Bindings und Fusions im Registry-
Write-Pfad. `CoreState` deklariert und konsumiert anschließend denselben
Contract:

```text
MediaState / Owner
    -> media.activity.v1
    -> Core Contracts ConsumerApi
    -> CoreState
```

`CoreState` kennt in diesem Ablauf keine `media_player`-Rohentitäten für PS5,
TV, PC oder Switch. Es verwendet nur Contract-Feld, Quality, Freshness,
Health, Revision und bei Diagnosebedarf die Lineage-Projektion.

## Public-Entity-Grenze

Die Consumer API ist der Standardtransport für interne Integrationen. Dieser
Slice erzeugt keine neuen Home-Assistant-Transport-Entities. Eine öffentliche
Entity-Projektion bleibt eine ausdrücklich freigegebene Ausnahme für
Dashboard, normale HA-Automationen, Entwickleranzeige oder externe Consumer
und wird nicht automatisch aus AtomicSignals, Fusions oder Consumer-Updates
abgeleitet.

## Overrides und Folge-Slices

`ConsumerOverride`/`set_override()` bilden nur die typisierte In-Memory-Grenze
für einen optionalen Advanced-Block. Es gibt in Issue #20 keine UI und keinen
zusätzlichen Persistenzpfad; PostgreSQL-, Draft-, Save-, OCC- und Last-Known-
Good-Semantik bleiben vollständig in #16/#17.

Nicht Bestandteil dieses Slices sind #18 Svelte Registry UX, #19 Fusion Editor,
#21 Elternprofil, #22 Import/Export, #23 Diagnose-Repair-UX sowie CoreState-,
MediaState-, Climate- und Blind-Cutovers. Diese Integrationen können die hier
dokumentierte API in eigenen Folgeaufträgen verwenden.
