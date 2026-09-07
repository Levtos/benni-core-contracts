# Registry & Exchange v1 — Soll/Ist-Abnahme (#24)

Stand: 2026-09-07. Kanonische Quelle ist das unverändert aus PR #15 übernommene
[Lastenheft](lastenheft-registry-exchange-layer-v1.md). Foundation-Unterbau:
#16/PR #26, #17/PR #27+#29, #20/PR #30, #21/PR #31 (Merge
`2b6f500426cf3a691146f09ab49eb5c94af5877a`). Keine parallele Architektur.

## Phasen-Gates

| Phase | Abgeschlossenes Scope / Commit | Gate vor nächster Phase |
|---|---|---|
| #18 | Binding-/Registry-UX, `aac31cf` | 195 Python-Tests + 6 Subtests; 26 Frontend-Tests; check/build/compile/Validation/diff grün |
| #19 | Fusion CRUD/Strategien/Editor, `1fc9d92` | 201 Python-Tests + 12 Subtests; 29 Frontend-Tests; übrige Gates grün |
| #22 | Transfer/Migrationskandidaten, `f48c573` | 206 Python-Tests + 22 Subtests; 32 Frontend-Tests; übrige Gates grün |
| #23 | Diagnose → Binding-Repair, `c438920` | 207 Python-Tests + 22 Subtests; 33 Frontend-Tests; übrige Gates grün |
| #24 | Hardening, Audit, Doku und Release | Lokal 217 Pytest-Tests + 22 Subtests, unittest 218 mit einem SQL-Skip; 35 Frontend-Tests; check/build/compile/Validation/diff grün, npm audit 0. CI/Release separat im PR. |

## Vollständiger Lastenheft-Abgleich

„Erfüllt“ bezeichnet implementierten Code mit technischer Testabdeckung, nicht
Deployment. Die finale grüne CI und das Actions-Release sind zusätzliche Gates.

| Abschnitt / MUSS-Gruppe | Soll/Ist und Evidence |
|---|---|
| 1–3 Zielbild/Foundation/Grenzen | Erfüllt: bestehende SourceBinding/AtomicSignal/Fusion/PublishedContract-Modelle, RegistryDomainService/Runtime und ConsumerApi. Keine zweite Engine oder Transportarchitektur. |
| 4 Ownership | Erfüllt: reine Source-Normalisierung/Datenfusion, keine Actuation. Owner- und Boundary-Tests bleiben erhalten. Externe Consumer besitzen ihre eigene fachliche Berechnung. |
| 5 Profile | Erfüllt: Benni/Eltern gemeinsamer Code; Binding-/Instance-/Revision-/LKG-/Subscription-Isolation in Profiltests und Hardening-Lifecycle-Test. |
| 6 Persistenz | Erfüllt: PostgreSQL JSONB kanonisch, bestehende Migration, HA-YAML ausschließlich DB-Bootstrap, ConfigEntry nur Profil/Modus. PersistentLKG profilbezogen mit Cache-Schreiblock. |
| 7 Revision/OCC | Erfüllt: Draft→validated candidate→atomic active; previous→superseded, rejected bei Fehlprüfung. Repository-Transaktions-/OCC-Tests, zusätzlich echter paralleler PostgreSQL-Test in CI. |
| 8 UX | Erfüllt: Übersicht, Registry mit Bereichen Bindings/Fusionen/Contracts/Einstellungen, Diagnose, Graph, Health. Eine Svelte5/Vite-Shell, bestehender Store; responsives Layout/44px Controls, Store- und DOM-Tests. Keine Browser-Live-Abnahme behauptet. |
| 9 Kein Autosave | Erfüllt: read Refresh, Validate ohne Persistierung, explizites Save, Discard, Rollback; Dirty-/OCC-Tests erhalten lokale Eingaben und Basis. |
| 10 Bindings | Erfüllt: CRUD/enabled, echte HA-Suche, Benutzerbestätigung, ID/Source-ID geschützt, Anzeigename/Profil/Entity/Capability/Rolle/Required/TTL/Fallback/Consumer-Nutzung/read-only. Schema-Safety bleibt autoritativ. |
| 11 Transfer | Erfüllt: strikter versionierter Import-Draft/Export; Roundtrip, Profil-/Unknown-Field-/Secret-Tests; Bulk-Auswahl und ConfigEntry-Analyse nur Kandidaten. |
| 12 Fusion | Erfüllt: first_healthy/latest/any_true/all_true + Opening; nested DAG, fehlende Referenzen/Zyklen/Profile/Strategien validiert; Liste/Editor/Diagnose. |
| 13 Schemata/Instanzen | Erfüllt: code-definierte versionierte Schemata, gemeinsame Presence-Erweiterung, Instance CRUD über bestehenden Service und eigene UX; kein Endnutzer-Schema-Editor. |
| 14 Consumer API | Erfüllt: typisierte unveränderliche Snapshot-/Field-/Quality-/Freshness-/Revision-/Lineage-Grenze und logische Rollenauflösung ohne DB-Zugang. Consumer-API-/Boundary-Tests. |
| 15 Requirements/Overrides | Erfüllt: selbstdeklarierte Requirements und read-only Nutzung/Impact. Optionaler expliziter API-Block aus #20 bleibt getestet; keine Override-UX. consumer_overrides-Payload bleibt versionierter Transfercontainer, keine heimliche zweite Requirement-Semantik. |
| 16 Updates | Erfüllt: gefilterte Subscriptions, Exception-Isolation/Unsubscribe/Unload; unveränderte Quellen behalten Evidence bei Registrywechsel. Revision allein löst keine irrelevante fachliche Wertänderung aus. |
| 17 Public Entities | Erfüllt: interne API ist Standard, keine neue Entity-Plattform/Projektion. Exakter alter Benni-Opening-Pilot bewusst erhalten; keine automatische Veröffentlichung von Fusion/Atomic/Consumer-Werten. |
| 18 Diagnose/Repair | Erfüllt: feldbezogener Kontext inkl. Quality/Freshness/Safety/Ursache/Quelle/Kandidaten/Fallback/Dauer/Impact/Revision/Binding-ID, Direktnavigation und expliziter geprüfter Save. Repair-/Frontend-Tests. |
| 19 Runtime darf nicht schreiben | Erfüllt: State-/Freshness-/Health-/Discovery-Pfade beobachten ausschließlich; periodische Recovery liest PostgreSQL, ändert nur lokalen LKG-Cache, niemals Registry-Konfiguration. Listener- und API-Boundary-Tests. |
| 20 Activity-Cutover | Foundation-Grenze erfüllt, externer Cutover bewusst offen: MediaState bleibt Owner von media.activity; keine PS5/TV/PC-Erkennung hier oder in einem neuen CoreState-Pfad. |
| 21 Eltern-Referenz | Technisch erfüllt: synthetische Eltern-Registry→Revision→Graph→ConsumerApi parallel zu Benni. Presence any_true Mutter/Vater als reine Fusion getestet. Echte Installation/CoreState-Anbindung ist ausdrücklich späterer Live-/Cutover-Gate. |
| 22 Datenmodell | Erfüllt: unveränderte Revisionstabelle mit JSONB, Profil, Checksums und Lifecycle; Transfer umfasst alle Payload-Sektionen ohne Runtime. |
| 23 Admin Write | Erfüllt: HA-Admin-Prüfung vor jedem Kommando, akteurgebundene Drafts, strukturierte Backend-/Validation-/OCC-/Referenzfehler; read-only WebSocket kompatibel. |
| 24 Logging | Erfüllt: Aktivierung/Rollback/Quellenwechsel, Write-Kommandos und abgewiesene Fehlercodes, Consumer-Requirement-Statuswechsel. Keine DB-Exception-/DSN-/Payload-Logs. |
| 25 Tests | Backend einschließlich historischer Signalgraph/Quality/Freshness/Security-/Profiltests; Frontend Store/DOM; echte PostgreSQL-Service-CI; vollständige Befehlsmatrix unten. |
| 26 Dokumentation | Erfüllt: aktuelles README, kanonisches Lastenheft, Operations/Recovery, Consumer/Service/UX/Fusion/Transfer/Repair und dieser Audit; alte Pilot-Dokumente ausdrücklich historisch. |
| 27 Nicht-Ziele | Erfüllt: keine Heiz-/Licht-/Rollo-/Media-/Wake-Policy, Service-Calls oder Actuation hinzugefügt. Repository-Validation prüft Boundary. |
| 28 DoD | Code-MUSS-Punkte durch obige Gruppen abgedeckt; technische Freigabe erst nach vollständiger Matrix + CI. Deployment ist kein behaupteter Bestandteil. |
| 29 Rollout | Bewusst extern offen: CoreState Eltern zuerst, danach MediaState/Climate/Blind. Kein Cutover im Foundation-Auftrag. |

## Im Audit konkret geschlossene Lücken

- Produktiver asyncpg-/HA-Store-Bootstrap statt nur Repository-Injection für Tests.
- Vollständige Graph-Auswertung vor Aktivierung; Binding-TTL berücksichtigt,
  Fallback validiert ohne Opening-/Physical-Safety-Gates global aufzuweichen.
- LKG-Cache-Saves serialisiert; beschädigtes Fremdprofil blockiert eigenes LKG nicht.
- Service-interne Reihenfolge von Read/Save/Rollback gesichert; PostgreSQL-OCC
  bleibt der einzige prozessübergreifende Commit-Entscheider.
- Evidence-Kontinuität ausschließlich bei gleicher Quelle; alte Listener nach
  Graphwechsel wirkungslos, entfernte HA-State-Quelle wird unavailable.
- Periodische reine Freshness-Auswertung/DB-Recovery und profilkorrekter Unload.
- Typisierte HA-Rohwerte, ungültige Zeitstempel/NaN/Infinity fail-closed.
- Geschützte Source-ID und strikte Binding-Feld-/Boolean-/TTL-Eingaben.
- Contract-Instanz-Verwaltung und read-only Einstellungen als eigene UX-Bereiche.
- Benutzerwechsel verwirft alte asynchrone Antworten und private Session-Puffer.
- Vollständige CI inklusive PostgreSQL, Frontend-Checks und reproduzierbarem Bundle.

## Historische Gates: bewusste Entscheidungen

Superseded als Gesamtziel: Shadow-only, Benni-only Runtime, Eltern parent_future,
read-only-only UX und „Consumer API noch offen“. Historische Evidence bleibt
unverändert non-authoritative. Erhalten: physische Unknown-/Fallback-Regeln,
Owner-/Required-Evidence-Tests und exakte Published-Opening-Allowlist. Keine
historische Matrix wird automatisch zu produktiven Bindings.

## Security und Fehlergrenzen

Admin-Grenze serverseitig, keine Frontend-Vertrauensentscheidung. PostgreSQL-
Credentials nur Bootstrap/Secrets, TLS verify-full als Standard. DB-Pool und
Timeouts begrenzt; Backendfehler als strukturierte neutrale Codes. Import lehnt
unbekannte Felder/Versionen ab. IDs/Profil/OCC können nicht still überschrieben
werden. Consumer sehen keine Mutable-Runtime- oder Repository-Objekte. Keine
neuen Service-Registrierungen oder Transport-Entities. Security-/Boundary-Tests
aus #16/#17/#20/#21 bleiben Bestandteil des Gates.

## Finale technische Matrix

```text
python -m pytest -q
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q custom_components tests scripts
python scripts/validate_repository.py
git diff --check
cd frontend
npm ci
npm run check
npm test
npm run build
npm audit
```

Lokal fehlt eine PostgreSQL-Instanz: ausschließlich der echte SQL-Test wird ohne
`CORE_CONTRACTS_TEST_DSN` übersprungen. CI muss diesen Test mit PostgreSQL 16 grün
ausführen, bevor gemergt wird. SQL-Fake-Tests sind ausdrücklich kein Ersatz.
Release: Manifest/Python/Frontend 0.2.0; vorhandener Actions-HACS-Workflow nach
serverseitigem Merge und stabilem Tag. Exakte Ergebnisse, PR, Merge-SHA, Tag und
Workflow werden auf GitHub dokumentiert, nicht als vorweggenommene Abnahme hier.

## Nächster separater Auftrag

CoreState Eltern: Inputs nach KEEP/CONTRACT/MOVE/REMOVE/OUTPUT inventarisieren,
stabile `core_state`-Requirements profilbezogen deklarieren, Snapshot plus
Subscription aus `docs/consumer-api-v1.md` übernehmen, blocked/missing/stale
bewusst behandeln. Media Activity später ausschließlich vom MediaState-Owner.
Danach eigener HA-Live-Gate; keine neuen Rohentity-Transporthelfer als Zwischenziel.
