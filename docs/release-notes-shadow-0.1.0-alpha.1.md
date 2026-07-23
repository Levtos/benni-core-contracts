# Shadow-only Alpha `0.1.0-alpha.1`

## Zweck

Der erste installierbare Pre-Release von `benni_core_contracts` dient
ausschließlich einer ausdrücklich read-only Shadow-Installation auf Benni.
Er ist kein Published-Modus, keine produktive Contract-Veröffentlichung und
keine Live-Freigabe.

## Enthalten

- expliziter ConfigEntry-Modus `shadow_only` ohne impliziten Default;
- Benni-only Runtime-Scope; Eltern bleibt `parent_future`/`out_of_scope`;
- leere Default-SourceBindings und leere Entity-Allowlist;
- read-only State-Listener und versionierte interne Contract-/Diagnose-/WS-
  Grundlagen;
- harte Boundary gegen Entity-Plattform, Services, Actuation, Policy-Imports,
  Registry-, Migrations- und Consumer-Änderungen;
- HACS-Metadaten, GitLab-CI-Mirror-Gate und GitHub-Pre-Release-Workflow.

## Nicht enthalten

Diese Alpha aktiviert keine ConfigEntry, SourceBinding, Entity-Plattform,
öffentliche HA-Entity, Policy-Entscheidung, Actuation, Migration oder
Consumer-Umstellung. Lock und Cover-Position bleiben Evidence-only. Die
Installation verändert keine Home-Assistant-Registry und erzeugt weiterhin
0 HA-Entities.

## Evidence-Status

Die Installation ist nur ein Transport-/Paket-Gate. Aktuelle Source-States,
Ownership, Gerätezeitstempel, retained-/restore-/stale-Herkunft,
Konfliktfreiheit sowie die Lock-Revalidierung bleiben offene Live-Evidence-
Gates. Fixtures und lokale Shadow-Tests sind keine Live-Freigabe.
