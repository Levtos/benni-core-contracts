# Benni Core Contracts `0.1.4`

Diese Release Notes sind historische Notizen zum Benni-only Shadow-/Published-
Pilot. Die darin genannte Eltern-Grenze beschreibt nicht die aktuelle
profilisolierte Registry-/Runtime-Freigabe aus Issue #21.

## Published-Options-Flow-Fix

Dieser Patch-Release korrigiert den Home-Assistant-spezifischen Published-
Options-Flow. Die beiden verifizierten Opening-Quellen werden in den
`EntitySelectorConfig`-Objekten jetzt als Listen übergeben, wie es Home
Assistant für `include_entities` erwartet.

Der Regressionstest führt den tatsächlichen Übergang
`OptionsFlow.async_step_init({"mode": "published"})` zu
`async_step_published` mit Home-Assistant-Testdoubles aus und prüft die
erzeugten Selector-Konfigurationen für:

- `binary_sensor.kitchen_patio_door_open_contact`
- `binary_sensor.kitchen_patio_door_tilt_contact`

Core Contracts bleibt standardmäßig Shadow-only, read-only und erzeugt ohne
explizite Published-Freigabe **0 HA-Entities**. Es gibt keine Services,
Actuation, Policy-Imports, Migration oder Consumer-Umstellung. Die mögliche
Pilot-Entity bleibt `sensor.benni_opening_kitchen_patio_door` und wird durch
die Paketveröffentlichung nicht automatisch aktiviert. Innerhalb dieses
historischen Piloten bleibt Eltern `parent_future`/`out_of_scope`; produktive
Eltern-Bindings entstehen heute ausschließlich über einen expliziten
Registry-Write.
