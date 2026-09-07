# Fusion-Editor und generische Strategien (#19)

Fusionen sind Datenkonfiguration im bestehenden Registry-Draft. Die Registry-
Ansicht bietet Liste, Details, Status, CRUD, ausdrückliche Input-Auswahl und
Strategiewahl. „Fusion in Entwurf übernehmen“ schreibt nur den In-Memory-Draft;
Prüfen/Speichern/Verwerfen und OCC gelten gemeinsam für Bindings und Fusionen.
Ein neues Ziel kann über die vorhandene Contract-Instance-API als Instanz eines
im Python-Code definierten Schemas angelegt werden. Schema-Code wird nicht editiert.

Admin-WebSocket-Kommandos: `registry/fusion/create`, `registry/fusion/update`,
`registry/fusion/delete`. Sie verwenden RegistryDomainService, dessen Draft-
Eigentümerprüfung und vorhandene Revision-Aktivierung. IDs bleiben stabil.
Ein ungültiges Fusion-Update ersetzt weder den bisherigen Draft-Payload noch
die aktive Registry. Referenzierte Fusionen können nicht gelöscht werden.

## Strategien

- `first_healthy`: erste frische schema-gültige Quelle in konfigurierter Reihenfolge;
  widersprüchliche frische Quellen bleiben als Konflikt diagnostizierbar.
- `latest`: jüngste belastbare Beobachtung, nicht die jüngste Empfangszeit.
- `any_true`: mindestens ein frisches True ergibt True; False nur, wenn alle
  Inputs frisch und False sind. Fehlend/unknown/stale gilt nicht als False.
- `all_true`: alle Inputs frisch und True ergibt True; ein belastbares False
  ergibt False. Bei unvollständigen Inputs bleibt das Ergebnis degradiert;
  True plus unbekannter Input ergibt keinen gültigen True-Claim.
- `opening_contacts`, `opening_is_open`, `opening_available`,
  `opening_source_count` bleiben unveränderte Rohkontakt-Normalisierung mit
  ihren physischen Evidence-/Fallback-Sperren. Sie akzeptieren keine Nested-Inputs.

Nested Fusionen verwenden tatsächlich das Ergebnis ihrer Kindstrategie, nicht
eine flach zusammengeführte Rohinput-Liste. Inputs müssen dasselbe Feld adressieren;
verschiedene Contract-Instanzen sind zulässig. Alle Referenzen werden ausschließlich
innerhalb des profilierten Payloads aufgelöst. Zyklen, Duplikate, fehlende Inputs,
unbekannte IDs, unpassende Felder/Strategien und Profil-Mismatch werden abgewiesen.
Bindings werden vor den separaten Fusion-Inputs ausgewertet; Binding-Priorität
ist im Editor explizit sortierbar. Keine synthetischen Zwischenwerte werden im
Signalstore oder als HA-Entities veröffentlicht. Lineage enthält echte Binding-IDs.

## Eltern-Referenz

Das profilunabhängige Schema `presence.v1` enthält `present: boolean` (required,
TTL 300 s, device_or_ha_event, reject). Zwei explizit konfigurierte Binding-Inputs
Mutter/Vater werden durch `any_true` in der Instanz `household` zusammengeführt.
Benni kann dasselbe Schema mit eigenen Bindings verwenden. Es gibt keine
Anwesenheits-Hold-, Wake-, CoreState- oder Heizpolicy in diesem Schema.

Historische Source-Binding-/Owner-Evidence ist weiterhin nicht autoritativ.
Die feste alte Benni-Owner-Matrix wird nicht um erfundene Presence-Evidence
erweitert. Produktive Konfiguration entsteht ausschließlich durch Registry-Save.

Tests prüfen CRUD, stabilen Draft bei Fehlern, indirekte Zyklen, Referenzen,
Nested `all_true(any_true(...), ...)`, fehlende Boolean-Evidence und die Eltern-
Presence. Bestehende Opening-, Quality-, Freshness- und Owner-Gates bleiben geprüft.
Keine HA-Live-/Deployment- oder Consumer-Cutover-Abnahme.
