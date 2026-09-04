# Benni Core Contracts `0.1.0`

Historische Benni-only Release Notes. Die damalige `parent_future`-/
`out_of_scope`-Grenze beschreibt nur diesen alten Shadow-Stand und ist durch
Issue #21 für die aktuelle Registry-/Runtime-Foundation superseded.

## Stabiler Shadow-only-Release

Dieser vollständige, nicht als Pre-Release markierte Release bringt die
live-testbare read-only Svelte-UX für Core Contracts auf Einhornzentrale.
`v0.1.0` ist ein stabiler Release innerhalb der `0.x`-Entwicklungsreihe;
die fachliche Grenze bleibt ausdrücklich shadow-only.

## UX-Fix

- Das HA-Custom-Panel bindet seine globalen und komponentenbezogenen Styles
  direkt im Modul-Bundle ein. Die normale Vite-`index.html` wird im HA-Panel-
  Loader nicht vorausgesetzt.
- Das Custom-Element ist ein vollbreiter Block und nutzt die verfügbare
  Home-Assistant-Panelbreite responsiv auf Desktop und Touch-Geräten.
- Die Shell, Design-Tokens und Core-Contracts-Fachdarstellung bleiben als
  getrennte Schichten erhalten.

## Grenzen

Der Release bleibt read-only und shadow-only. Er erzeugt keine HA-Entities,
Services, Policy-Entscheidungen oder Actuation und schreibt keine ConfigEntry-
Daten. Die öffentliche Projektion bleibt bei **0 HA-Entities**. Die UX
verwendet weiterhin ausschließlich die fünf vorhandenen Core-Contracts-
WebSocket-Kommandos. Es wird keine Screenshot-, Browser-Automations- oder
visuelle Testinfrastruktur eingeführt. `parent_future` bleibt
`out_of_scope`.

## Nachweis und Abnahme

Die Veröffentlichung verwendet den bestehenden GitLab-, Mirror-, GitHub-
Release- und HACS-Weg. Die GitLab-Pipeline ist kein Merge-, Release- oder
Abnahme-Gate; maßgeblich ist der lokal grüne Teststand. Die fachliche und
visuelle Live-Abnahme erfolgt nach der technischen Bereitstellung durch Benni
in Home Assistant auf Desktop und Lenovo M11. Der Status bleibt bis dahin
`testing`.
