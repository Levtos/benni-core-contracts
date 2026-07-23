# UX-/WebSocket-Anforderungen

Die React/Vite-Oberfläche ist in diesem Slice noch nicht gebaut. Die
WebSocket-API liefert jedoch bereits die read-only Grundlage, damit die
spätere UX nicht aus internen Python-Details lesen muss.

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
