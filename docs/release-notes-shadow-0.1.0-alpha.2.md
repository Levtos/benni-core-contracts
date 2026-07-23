# Shadow-only Alpha `0.1.0-alpha.2`

## Zweck

Diese korrigierte Shadow-only-Alpha enthält den WebSocket-Kompatibilitätsfix
für aktuelle Home-Assistant-Versionen. Die read-only Integration übergibt die
Command-Schemas im von Home Assistant erwarteten Mapping-Format.

## Grenzen

- ausschließlich `profile=benni` und ausdrücklich `mode=shadow_only`;
- keine öffentliche HA-Entity, keine Entity-Plattform und weiterhin 0 HA-Entities;
- keine Services, Actuation, Policy-Imports, Migration oder Consumer-Umstellung;
- keine automatische SourceBinding-Aktivierung;
- Eltern bleibt `parent_future`/`out_of_scope`;
- Lock und Cover-Position bleiben Evidence-only;
- keine Live-Evidence-Freigabe durch Installation oder Release.

Die lokale Suite umfasst 125 Tests. Die Alpha benötigt weiterhin einen
separat freizugebenden, read-only Benni-Shadow-Schritt.
