# Benni Core Contracts `0.1.3`

Historische Benni-only Release Notes. Die damalige `parent_future`-/
`out_of_scope`-Grenze beschreibt nur diesen alten Shadow-Stand und ist durch
Issue #21 für die aktuelle Registry-/Runtime-Foundation superseded.

## Release-Fix

Dieser stabile Patch-Release synchronisiert die Paket-, Laufzeit- und
Frontend-Versionsmetadaten auf `0.1.3`. Damit stimmen Manifest, Git-Tag
`v0.1.3`, PyProject, Runtime-Version und die UX-Version wieder überein.

Der Release enthält keine fachliche Änderung am Published-Opening-Slice.
Core Contracts bleibt standardmäßig Shadow-only (`shadow_only`), read-only und erzeugt ohne
explizite Published-Freigabe **0 HA-Entities**. `parent_future` bleibt
`out_of_scope`.

Die einzige mögliche veröffentlichte Pilot-Entity bleibt
`sensor.benni_opening_kitchen_patio_door`; Home Assistant, ConfigEntry und
Live-Aktivierung werden durch die Paketveröffentlichung nicht verändert.
