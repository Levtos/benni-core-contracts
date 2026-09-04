# Benni Core Contracts `0.1.1`

Historische Benni-only Release Notes. Die damalige `parent_future`-/
`out_of_scope`-Grenze beschreibt nur diesen alten Shadow-Stand und ist durch
Issue #21 für die aktuelle Registry-/Runtime-Foundation superseded.

## Stabiler Shadow-only-Refresh-Fix

Dieser stabile Patch-Release hält die Live-UX während der zyklischen
read-only Synchronisation ruhig. Hintergrundabfragen wechseln den sichtbaren
Verbindungsstatus nicht mehr bei jedem Poll zwischen `connected` und
`reconnecting`.

- Das Panel bleibt während erfolgreicher Hintergrund-Refreshes layout-stabil.
- Ein bestehender Fehler bleibt bis zur erfolgreichen Folgeabfrage sichtbar,
  statt bei jedem Retry kurz zu verschwinden.
- Die Refresh-Reconciliation, die fünf read-only WebSocket-Kommandos und die
  Grenze von **0 HA-Entities** bleiben unverändert.

Der Release ist vollständig und nicht als Pre-Release markiert. `0.1.1`
bleibt innerhalb der `0.x`-Entwicklungsreihe; `parent_future` bleibt
`out_of_scope`.

Die lokale technische Prüfung bleibt maßgeblich. Es werden keine Screenshots,
keine Browser-Automation und keine neue CI-Infrastruktur eingeführt. Die
fachliche und visuelle Abnahme erfolgt nach der technischen Bereitstellung
durch Benni auf Desktop und Lenovo M11; control#59 bleibt bis dahin auf
`status/testing`.
