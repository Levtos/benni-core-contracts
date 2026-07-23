# Benni Core Contracts — Shadow-only Alpha v1

Stand: 2026-07-24. Release-Version: `0.1.0-alpha.2`.

## Release-Identität

- GitLab-Quelle: `ha-platform/core-contracts`
- GitHub-HACS-Mirror: `Levtos/benni-core-contracts`
- Git-Tag: `v0.1.0-alpha.2`
- HA-Domain: `benni_core_contracts`
- einziger aktivierbarer Modus: `shadow_only`
- einziges produktives Shadow-Profil: `benni`

Der Tag ist ein installierbarer Alpha-/Shadow-only-Pre-Release. Er darf über
HACS bezogen werden, ist aber keine produktive Contract-Veröffentlichung und
keine Freigabe für Live-Verbraucher.

## Harte Release-Grenzen

Der Release erzeugt standardmäßig und auch mit leerem Shadow-ConfigEntry
keine HA-Entities: weiterhin **0 HA-Entities**. Es wird keine Entity-Plattform geladen, kein Service
registriert, keine Actuation ausgeführt und keine Policy importiert. Es gibt
keine automatische SourceBinding-Aktivierung, keine Registry-Änderung, keine
Migration und keinen Consumer-Cutover.

`parent_future`/Eltern bleibt vollständig `out_of_scope`. Gemeinsamer
Graph-, Schema- und Fixture-Code darf vorhanden sein; ein Eltern-ConfigEntry
wird nicht aktiviert. Lock und Cover-Position bleiben Evidence-only.

## HACS-Voraussetzungen

1. HACS muss das Repository `Levtos/benni-core-contracts` als Custom
   Integration verwenden.
2. Für diese Alpha muss der Tag `v0.1.0-alpha.2` ausgewählt werden.
3. HACS muss die Integration unter `custom_components/benni_core_contracts`
   installieren; `hacs.json` verwendet dafür `content_in_root=false` und
   `zip_release=false`.
4. Die Installation auf Home Assistant ist ein separat auszuführender,
   ausdrücklich read-only Benni-Schritt. Codex hat keine Live-Installation,
   keinen Reload und keine ConfigEntry-Aktivierung durchgeführt.

## Nach der Installation

Die zuständige Person darf ausschließlich auf Benni/Einhornzentrale einen
ConfigEntry mit folgenden Werten anlegen:

```text
profile = benni
mode    = shadow_only
```

Der initiale Eintrag enthält keine SourceBindings und keine Entity-Allowlist.
Die Shadow-Auswertung darf nur bestehende States read-only beobachten. Ein
fehlender Zugriff bleibt `OPEN`/`blocked`; es werden keine Werte geschätzt.
Opening, Lock und Cover-Position behaupten ohne belastbare Evidence keinen
positiven physischen Zustand.

Nach dem Evidence-Test muss der Eintrag deaktiviert oder entfernt werden. Die
Deinstallation, eine spätere Binding-Auswahl und jede öffentliche Entity-
Allowlist gehören zu separaten, ausdrücklich freizugebenden Gates.

## Offene Gates

- aktuelle read-only Source- und Registry-Evidence für Benni;
- Source-Ownership und belastbare Gerätezeitstempel;
- retained-/restore-/stale-/conflict-Abgrenzung im Live-System;
- Lock-Revalidierung der kanonischen Kandidaten-ID;
- fachliche Freigabe eines späteren Shadow-ConfigEntry-Tests.

Die Release-Installation selbst schließt keines dieser Live-Evidence-Gates.
