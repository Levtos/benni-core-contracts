# Registry v1 — Bootstrap, Betrieb und Recovery

## Einmaliger Bootstrap

Core Contracts 0.2.0 verwendet den bestehenden `PostgresRegistryRepository` mit
einem begrenzten, verzögert aufgebauten asyncpg-Pool. Es gibt keinen zweiten Store.
Zugangsdaten gehören in HA-Secrets; sie werden nicht im ConfigEntry, Registry-
Payload, Export, WebSocket oder Log ausgegeben.

```yaml
# configuration.yaml — einmaliger technischer Bootstrap, kein Binding-Speicher
benni_core_contracts:
  database_url: !secret core_contracts_database_url
  migrate: true
```

Der Secret-Wert ist eine `postgresql://`-URL zur dedizierten Datenbank. Ohne
explizites `sslmode` wird `verify-full` angefügt: gültige CA und passender Hostname
sind erforderlich. Ein abweichender TLS-Modus muss bewusst serverseitig gesetzt
werden; unverschlüsselte Verbindungen sind keine Empfehlung für Produktion.
Die Datenbank sollte per Netzsegment/Firewall auf den HA-Host beschränkt sein.

`migrate: true` führt die bestehende idempotente Migration
`migrations/001_registry_revision.sql` einmal beim ersten Verbindungsaufbau aus,
innerhalb einer Transaktion und unter einem PostgreSQL-Advisory-Lock. Danach
`migrate: false` setzen und DDL-Rechte des Laufzeitbenutzers entziehen. Alternativ
führt der DB-Administrator die unveränderte SQL-Datei vorab aus. Laufzeitrechte:
SELECT/INSERT/UPDATE auf der Revisionstabelle und USAGE/SELECT auf deren Sequence;
kein DELETE erforderlich. Keine zusätzliche Migration für 0.2.0.

In HA eine ConfigEntry je benötigtem Profil `benni` / `eltern` mit dem expliziten
internen Modus `shadow_only` anlegen. Dieser historische Name bedeutet keine
Public-Entity-Projektion; Registry und ConsumerApi sind damit produktiv nutzbar.
ConfigEntries speichern keine produktiven Bindings. Ohne aktive Registry bleibt
die ConsumerApi ausdrücklich `runtime_not_ready`; historische Evidence wird nicht
als Ersatzkonfiguration importiert. Der separate Published-Opening-Pilot behält
seine alten exakten Sicherheitsgates.

## Betrieb und Aktivierung

Registry → Binding/Fusion/Contract-Instanz bearbeiten → Prüfen → Speichern.
Drafts liegen nur im Service-Arbeitsspeicher und sind an den Admin-Akteur gebunden.
Ein HA-Neustart verwirft ungespeicherte Drafts; produktive Revisionen bleiben in
PostgreSQL. Es gibt kein Autosave, auch nicht beim Schließen eines Editors.

Validierung umfasst Profile, Referenzen, Schema-/Feldtypen, DAG/Zyklen, Fallback-
Regeln und vollständige Graph-Auswertung. Fehlende reale Evidence kann fachlich
blocked ergeben, ist aber nicht automatisch ein ungültiger Graph. Eine Ausnahme
im Graph-Probelauf verhindert die Aktivierung. Schema-/Safety-Grenzen können
nicht durch ein Binding aufgeweicht werden; Binding-TTL kann Schema-TTL verkürzen.

Speichern erzeugt eine neue Revision; PostgreSQL prüft `expected_base_revision`
unter dem profilbezogenen Transaktionslock. Bei Conflict bleibt der Draft erhalten.
Der aktive Runtime-Snapshot wird erst nach erfolgreichem Commit ausgetauscht.
Eine interne Service-Sperre verhindert, dass ein früher gestarteter DB-Read einen
späteren Runtime-Commit wieder überschreibt; sie ersetzt nicht PostgreSQL-OCC.

Unveränderte Quellen behalten beim Graphwechsel ihre tatsächliche Evidence
einschließlich Zeitstempel. Geänderte Entity/Source/Field oder deaktivierte
Bindings übernehmen keine Werte. Ein HA-State-Read erfindet keine neue Messung.
Boolean-/Zahlen-Normalisierung ist schemageführt; `home`/`not_home` gelten nur für
Presence-Capability. Ungültige Zeitstempel und nicht endliche Zahlen sind keine
frischen gültigen Messwerte.

## Ausfall, LKG und Wiederanlauf

Der HA-Store `benni_core_contracts.registry_lkg` hält die checksum-validierten
aktiven Revisionen getrennt nach Profil. Konkurrierende lokale Cache-Saves sind
serialisiert; eine beschädigte Benni-Revision sperrt nicht das Eltern-LKG und
umgekehrt. Ein fremdes Profil wird niemals als Fallback verwendet.

Bei PostgreSQL-Ausfall wird das eigene LKG genutzt und der Registry-Status
degradiert. Es gibt keinen automatischen Reset, kein leeres Überschreiben und
keine Offline-Speicherung. Ohne gültiges eigenes LKG bleibt die API eindeutig
nicht bereit. Connection/Acquire sind auf 5 Sekunden begrenzt, DB-Kommandos auf
10 Sekunden. Poolgröße maximal vier; beim HA-Stop wird geschlossen.

Pro geladenem Profil werden Contracts alle fünf Sekunden rein lesend auf
Freshness neu bewertet. Alle zwölf Ticks wird der kanonische Stand erneut gelesen;
damit erfolgt Recovery nach DB-Rückkehr ohne Benutzer-Write. Diese Reads ändern
keine Registry-Konfiguration; nur der lokale LKG-Cache kann aktualisiert werden.
Unveränderte Revisionen bauen keinen neuen Graphen. Unload entfernt Listener,
Timer, Profil-Snapshot und beim letzten Profil die ConsumerApi/Seitenleiste.

## Rollback und Sicherung

Vor Upgrade reguläres PostgreSQL-Backup und HA-Backup einschließlich LKG erstellen.
Ein Export ist ein Konfigurationstransfer, kein Backup der gesamten Revisionstabelle.
Registry → Revisionshistorie → gültige frühere Revision → Rollback bestätigen.
Auch Rollback braucht aktuelle Basisrevision und Admin-Rechte. Er betrifft nur das
Zielprofil und löscht keine Historie. Bei Conflict erst den aktuellen Stand lesen;
niemals OCC abschalten. Bei beschädigter Historie zuerst DB-Backup in separater
Umgebung prüfen, nicht das gültige LKG überschreiben.

## Logging und Sicherheit

Aktivierung und Rollback loggen Profil/Revision. Die Admin-Grenze loggt erfolgreiche
Kommandotypen sowie abgewiesene Fehlercodes (einschließlich Validation/OCC/Backend).
LKG-Quellenwechsel und Recovery-Ausfälle sind nachvollziehbar. Konfiguration,
DSN, Passwörter und interne DB-Ausnahmen gehören nicht in diese Meldungen.
Consumer-Diagnosen unterscheiden missing/schema/version/blocked explizit.

## Abnahmegrenze

Unit-/Frontend-/SQL-Integrationstests sind technische Evidence, kein HA-Live-Test.
Deployment, Secrets-Provisionierung, Reload/Restart und die echte Abnahme auf
Einhornzentrale oder Eltern erfolgen separat durch Benni. Kein Consumer-Cutover
und keine neue Shadow-Instanz werden durch diesen Release angelegt.
