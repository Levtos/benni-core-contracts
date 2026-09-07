# v0.2.1 — PostgreSQL TLS ohne blockierende Zertifikats-I/O

Gezielter Quickfix zu Issue #34. Keine Migration, keine Änderung an Registry-
Payloads, ConsumerApi, Runtime, Bindings oder Frontend. Frontend-Artefakte bleiben
unverändert auf dem 0.2.0-Build; Manifest, Python-Paket und Panel-Cacheversion sind
0.2.1. Installation/Neustart erfolgen durch Benni, nicht durch diesen PR.

## Ursache und Lösung

`bootstrap_repository` → `RegistryDatabase.acquire` → lazy asyncpg-Pool → erster
Connection-Aufbau → `_parse_connect_dsn_and_args`: asyncpg 0.31.0 baut bei einer
SSL-Modus-Zeichenkette den SSLContext synchron. Dabei lädt es CA/CRL mittels
`load_verify_locations` und optionale Client-Zertifikate via `load_cert_chain`.
Das wurde in HA 2026.9.1/Python 3.14 live als Blocking-I/O gemeldet. Auch
`load_default_certs` und `set_default_verify_paths` sind im Regressionstest gegen
einen versehentlichen Aufruf im Event-Loop abgesichert.

Einmalig beim ersten Acquire erstellt `hass.async_add_executor_job` den Context.
Nur diese synchrone Vorbereitung läuft im Worker; `asyncpg.create_pool`, Acquire,
TLS-Handshake, Query und Close bleiben auf dem ursprünglichen Event-Loop.
Die vorhandene Initialisierungssperre verhindert parallele Context-Erzeugung.
Der Context bleibt auch nach DB-Ausfall/Pool-Neuerstellung erhalten. Eine
fehlgeschlagene Context-Erstellung wird nicht gecacht und kann erneut versucht
werden. LKG-/Recovery-Grenzen und Timeouts bleiben unverändert.

## TLS-Kompatibilität und Sicherheitsgrenze

- Fehlender `sslmode` wird weiterhin explizit `verify-full`, unabhängig von
  `PGSSLMODE`. Schwächere/leer gesetzte Modi werden nun fail-closed abgewiesen.
- Der fertige Context muss `CERT_REQUIRED` und `check_hostname=True` besitzen.
- Der unveränderte DSN wird mit `ssl=context` an die öffentliche Pool-API
  übergeben. Der asyncpg-Parser entfernt weiterhin seine TLS-DSN-Optionen, lädt
  beim Connection-Aufbau mit fertigem Context aber keine Zertifikate mehr.
- Die isolierte Adapterfunktion nutzt bewusst den **privaten Parser des auf
  0.31.0 gepinnten asyncpg**: DSN-/Service-/Environment-Präzedenz für `sslrootcert`,
  `sslcrl`, `sslcert`, `sslkey`, `sslpassword`, Mindest-/Höchst-TLS-Version und
  PostgreSQL-Defaultdateien bleiben identisch. Eine asyncpg-Aktualisierung muss
  diesen Adapter und seine Regressionen erneut prüfen.
- Es wird kein neuer systemweiter Trust-Store eingeführt. Eine explizite
  System-CA-Datei bleibt ebenso wie eine private CA-Datei nutzbar. asyncpgs
  `verify-full` verlangt ohne explizite CA weiterhin seinen PostgreSQL-Rootpfad;
  keine stille Ersetzung durch certifi.
- HAs gecachter SSLContext ist hier nicht passend: anderer CA-Auswahlpfad
  (`REQUESTS_CA_BUNDLE`/certifi), Standard-HTTP-ALPN, keine PostgreSQL-DSN-
  Client-Key-/CRL-Semantik. Er wird weder benutzt noch mutiert.
- Kein `CERT_NONE`, keine abgeschaltete Hostname-Prüfung, kein Warning-Filter.
  DSNs/Passwörter/parserinterne Fehler werden nicht zusätzlich geloggt.

## Regressionen

Tests verwenden generierte Test-CA/Client-Key/CRL und echte OpenSSL-Contexts.
MemoryBIO-Handshakes akzeptieren die korrekte CA/Hostname-Kombination und lehnen
falsche Hostnames und fehlendes Vertrauen tatsächlich ab. Weitere Tests prüfen
CA-/Client-Key-Passwort-/CRL-/TLS-Optionen, Environment-/Service-/Defaultpfade,
Executor-Thread, Context-Reuse bei parallelem Acquire, lazy Pool, fehlerhafte CA,
DB-Ausfall mit LKG und Recovery. Ein echter asyncpg-Pool versucht eine Verbindung
zu einem unerreichbaren lokalen Port, während alle SSL-Dateilader im Event-Loop
als Regression fehlschlagen würden. Kein produktiver Datenbankzugriff im Test.

Pflichtchecks: vollständiges pytest und unittest discover, compileall,
Repository Validation und `git diff --check`. Ergebnisnachweise stehen im PR.
Die vorhandene CI prüft zusätzlich PostgreSQL und den unveränderten Frontend-Build.

## Separates Benni-Live-Gate (noch offen)

Nach Installation von 0.2.1 und HA-Neustart:

1. Core Contracts muss geladen sein.
2. Ersten Registry-/DB-Zugriff auslösen; Registry-API antwortet erfolgreich.
3. PostgreSQL-Verbindung bleibt TLS-verifiziert mit gültiger CA und Hostname.
4. Keine **neuen** Core-Contracts-Blocking-Warnungen zu `load_default_certs`,
   `set_default_verify_paths`, `load_verify_locations` oder `load_cert_chain`.

Eine noch leere Registry meldet weiterhin korrekt `no_active_revision`.
Keine automatische Befüllung, kein Consumer-Cutover, keine neue Public Entity.
Rollback des Codes erfolgt bei Bedarf über den bisherigen Release; Datenbank-
Schema und gespeicherte Revisionen werden durch diesen Patch nicht verändert.
