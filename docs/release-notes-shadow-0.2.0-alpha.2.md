# Shadow-only Alpha `0.2.0-alpha.2`

## Fix

- Das Core-Contracts-Panel berechnet den Cache-Parameter jetzt ausschließlich
  aus der Release-Version.
- Die Panel-Initialisierung traversiert das gebündelte Frontend-Verzeichnis
  nicht mehr synchron im Home-Assistant-Eventloop.
- Die View-Tests prüfen den stabilen Versions-Parameter als Regression gegen
  erneute Dateisystem-Scans.

## Grenzen

Der Release bleibt read-only und shadow-only. Er erzeugt keine HA-Entities,
Services, Policy-Entscheidungen oder Actuation und schreibt keine ConfigEntry-
Daten. Die öffentliche Projektion bleibt bei **0 HA-Entities**. Die UX
verwendet weiterhin ausschließlich die fünf vorhandenen
Core-Contracts-WebSocket-Kommandos. Screenshots und Browser-Testinfrastruktur
sind nicht Bestandteil dieses Patch-Releases. `parent_future` bleibt
`out_of_scope`.

## Nachweis

Der Release verwendet den bestehenden GitLab-MR-, Tag-, Mirror-, GitHub-
Pre-Release- und HACS-Weg. Die fachliche Live-Abnahme erfolgt nach kontrollierter
HA-Aktivierung durch Benni auf Desktop und Lenovo M11.
