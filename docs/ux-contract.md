# UX-/WebSocket-Anforderungen

Die Svelte-5-/Vite-Oberfläche ist als statisch gebündeltes Home-Assistant-
Panel umgesetzt. Sie liest ausschließlich die versionierte read-only
WebSocket-API, damit die UX nicht aus internen Python-Details lesen muss.

## Stabilität bei Live-Updates

Eine spätere UX muss bei Contract-, Graph- und Diagnose-Updates:

- Scrollposition erhalten;
- aktive Filter erhalten;
- ausgewählten Contract beziehungsweise geöffneten Detailbereich erhalten;
- nur tatsächlich geänderte Datensätze neu rendern;
- keinen vollständigen View-Neuaufbau und keinen Sprung an den Seitenanfang
  auslösen.

Die WS-Payloads sind deshalb nach `list_contracts`, `get_contract`,
`get_diagnostics`, `get_graph` und `get_health` getrennt. Jede Antwort ist
mit `payload_version=1`, einer Graph-Revision und revision-basierter
Delta-Reconciliation versehen. Die stabilen IDs liegen an den Objekten und
werden nicht aus Listenpositionen abgeleitet. Die Befehle sind read-only;
Konfiguration und spätere Allowlist-Änderungen bleiben ein separater,
validierter ConfigEntry-/UX-Workflow.

Die Produktionsansicht nutzt keine Preview-Fixtures. Eine lokale Vite-
Vorschau kann ausschließlich mit `?preview=fixture` gestartet werden und wird
im UI sichtbar als nicht-live markiert. Die installierte HA-Ansicht verwendet
die aktive HA-Verbindung und speichert weder Tokens noch Zustände in
LocalStorage oder URL-Parametern.

## UX-Felder

Die Diagnoseansicht muss Contract-Headline und Feld-Details getrennt zeigen:

- Contract- und Schema-Version;
- Feldwert, Health, Freshness und Safety;
- Root Cause und konkrete Quell-Entity;
- Beginn und Dauer der Degradierung;
- betroffene Consumer-Fähigkeit;
- aktive Fallback-Art und konservative Einschränkung.

Ein globales `degraded` darf nicht als Ersatz für die fachlich weiter
brauchbaren Felder angezeigt werden.

Die vollständige normative Payload-, Freshness- und Fallback-Spezifikation
steht in [Gate Pack v1](gate-pack-v1.md).

Die technische Trennung von Shell, Design-Tokens, Basiskomponenten,
Transportadapter und Core-Contracts-Fachmodul ist in
[ux-implementation.md](ux-implementation.md) dokumentiert.
