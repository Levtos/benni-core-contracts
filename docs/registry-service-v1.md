# Registry Backend-Service v1

Issue #17 ergänzt den PostgreSQL-Unterbau aus Issue #16 um den produktiven
Domain-Service und eine klar getrennte Home-Assistant-WebSocket-Schreibgrenze.
Der Service besitzt keine zweite Persistenz- oder Grapharchitektur:
`PostgresRegistryRepository` bleibt die einzige Quelle für Revisionen,
atomare Aktivierung, Optimistic Concurrency und Last-Known-Good.

## Datenbank und Migration

Issue #17 benötigt keine neue Tabelle und keine neue SQL-Migration. Es verwendet
weiterhin `migrations/001_registry_revision.sql` und die JSONB-Payload von
Issue #16. `SourceBinding` ergänzt optionale Edit-Felder; bei den bisherigen
Default-Werten werden diese nicht serialisiert, sodass bestehende Revisionen
und LKG-Checksummen kompatibel bleiben. Die Migration wird weiterhin explizit
über `PostgresRegistryRepository.async_migrate()` ausgeführt.

## Service- und Runtime-Grenze

`RegistryDomainService` verwaltet kurzlebige `RegistryDraft`-Objekte im
Arbeitsspeicher. Ein Draft ist kein PostgreSQL-Row und wird nicht automatisch
gespeichert. Die editierbaren Payloads verwenden weiterhin `SourceBinding`,
`Fusion` und die code-definierten Contract-Schemata.

`RegistryRuntime` ist der atomare In-Process-Holder für den zuletzt erfolgreich
aktivierten Payload und den daraus gebauten `SignalGraph`. `prepare()` validiert
und baut einen Graph-Probe-Stand ohne Seiteneffekt; `activate()` tauscht einen
kompletten validierten Snapshot aus. Die getrennte, read-only Consumer-Grenze
beobachtet diesen Holder; sie ist in [Consumer API v1](consumer-api-v1.md)
dokumentiert und führt keinen Consumer-Cutover aus.

Wenn ein Repository-Service über `async_setup_registry_service()` in Home
Assistant injiziert wird, wird sein Runtime-Holder bei einem ConfigEntry-Start
für den aktiven Registry-Stand verwendet. PostgreSQL-Verbindung und Credentials
werden außerhalb des ConfigEntry bereitgestellt. Die Migration bleibt der
explizite `PostgresRegistryRepository.async_migrate()`-Schritt aus Issue #16.

## Draft-Lifecycle

```text
Draft öffnen
    -> Binding/Contract-Instance im Draft bearbeiten
    -> Prüfen (Graph-Probe, keine Persistenz)
    -> weiter bearbeiten oder Änderungen verwerfen
    -> explizit Speichern
       -> vollständige Validierung
       -> PostgreSQL-Draft-Revision
       -> atomare Aktivierung mit expected_base_revision
       -> Runtime-Snapshot austauschen
```

Bei einem Fehler bleibt der Draft zur Korrektur erhalten. `discard` entfernt
ausschließlich den In-Memory-Draft. Save und Rollback installieren erst nach
erfolgreichem Graph-Probe einen neuen Runtime-Snapshot.

## Schreibbefehle

Die Command-Familie ist von den bestehenden read-only Commands getrennt und
wird nur bei konfiguriertem `RegistryDomainService` registriert:

| Command | Zweck |
| --- | --- |
| `benni_core_contracts/registry/get_active` | Aktive Registry inklusive Quelle/Health lesen |
| `benni_core_contracts/registry/list_revisions` | Revisionshistorie für Rollback-Auswahl lesen |
| `benni_core_contracts/registry/draft/create` | Draft auf Basis des aktiven Standes öffnen |
| `benni_core_contracts/registry/draft/get` | Draft laden |
| `benni_core_contracts/registry/draft/validate` | Validieren und Graph-Probe ausführen |
| `benni_core_contracts/registry/draft/save` | Validieren, neue Revision erzeugen und aktivieren |
| `benni_core_contracts/registry/draft/discard` | Draft verwerfen |
| `benni_core_contracts/registry/rollback` | Historische gültige Revision reaktivieren |
| `benni_core_contracts/registry/binding/create` | SourceBinding anlegen |
| `benni_core_contracts/registry/binding/update` | SourceBinding bearbeiten, ID bleibt stabil |
| `benni_core_contracts/registry/binding/delete` | Nicht referenziertes SourceBinding löschen |
| `benni_core_contracts/registry/binding/set_enabled` | Binding im Draft aktivieren/deaktivieren |
| `benni_core_contracts/registry/contract_instance/create` | Contract-Instance anlegen |
| `benni_core_contracts/registry/contract_instance/update` | Contract-Instance bearbeiten |
| `benni_core_contracts/registry/contract_instance/delete` | Nicht referenzierte Contract-Instance löschen |

Binding- und Contract-Instance-IDs sind technische Identitäten. Ein Entity-
Wechsel ändert nur das Binding, zum Beispiel
`media_player.homepod_old -> media_player.sonos_new`.

## Validierung, Fehler und Sicherheit

`validate` ruft weder `create_revision()` noch `activate_revision()` auf und
verändert auch den Runtime-Holder nicht. Save validiert zusätzlich innerhalb
der Repository-Transaktion erneut. Ein ungültiger Draft kann daher weder die
aktive Revision noch den laufenden Runtime-Graphen ersetzen.

Die WebSocket-Grenze akzeptiert nur Home-Assistant-Administratoren. Die
Antworten verwenden strukturierte Codes für `validation_error`,
`revision_conflict`, `backend_unavailable`, `invalid_reference`,
`revision_not_found`, `draft_not_found` und unzulässige Revision-Zustände.
Ein Conflict enthält `expected_base_revision` und `actual_base_revision`;
Last-Write-Wins ist ausgeschlossen.

Payload-Metadaten mit Credential-/Secret-Feldern werden am Write-Service
abgewiesen. Antworten enthalten keine PostgreSQL-Verbindung, Credentials oder
andere Backend-Interna. Runtime-, State-, Freshness-, Quality-, Discovery- und
Health-Ereignisse kennen weiterhin keinen Repository-Write-Pfad.

## Bewusste Folgegrenzen

Dieser Slice implementiert keine Svelte-Registry-UX (#18), keinen separaten
Fusion-Editor (#19), keinen Import/Export-Workflow (#22) und keinen
CoreState-/MediaState-Cutover. Die Consumer-API und Subscriptions aus #20 sind
in [Consumer API v1](consumer-api-v1.md) beschrieben. Die read-only
WebSocket-Commands, der bestehende Runtime-Store und die vorhandene
Signalgraph-/Quality-/Freshness-Architektur bleiben kompatibel.
