# Benni Core Contracts — Shadow-only Release v1

Stand: 2026-07-31. Release-Version: `0.1.4`.

Dieses Dokument beschreibt ausschließlich die historische Release-Identität
und die damaligen Benni-Evidence-Grenzen. Issue #21 supersediert die daraus
abgeleitete globale Eltern-Sperre für den aktuellen profilisolierten
Registry-/Runtime-/Consumer-Pfad.

## Release-Identität

- GitHub-HACS-Repository: `Levtos/benni-core-contracts`
- Git-Tag: `v0.1.4`
- HA-Domain: `benni_core_contracts`
- einziger aktivierbarer Modus: `shadow_only`
- einziges produktives Shadow-Profil dieses historischen Tags: `benni`

Der Tag ist ein installierbarer vollständiger Shadow-only-Release. Er darf
über HACS bezogen werden, bleibt wegen der ausdrücklich read-only/shadow-only
Fachgrenzen aber keine produktive Contract-Veröffentlichung und keine Freigabe
für Live-Verbraucher.

## Harte Release-Grenzen

Der Release erzeugt standardmäßig und auch mit leerem Shadow-ConfigEntry
keine HA-Entities: weiterhin **0 HA-Entities**. Es wird keine Entity-Plattform geladen, kein Service
registriert, keine Actuation ausgeführt und keine Policy importiert. Es gibt
keine automatische SourceBinding-Aktivierung, keine Registry-Änderung, keine
Migration und keinen Consumer-Cutover.

Innerhalb dieses historischen Tags bleibt `parent_future`/Eltern vollständig
`out_of_scope`. Gemeinsamer Graph-, Schema- und Fixture-Code darf vorhanden
sein; ein Eltern-ConfigEntry wurde in diesem Release nicht aktiviert. Lock und
Cover-Position bleiben Evidence-only. Die aktuelle gemeinsame Engine kann
`benni` und `eltern` dagegen über die produktive Registry getrennt betreiben.

## HACS-Voraussetzungen

1. HACS muss das Repository `Levtos/benni-core-contracts` als Custom
   Integration verwenden.
2. Für diesen Release muss der Tag `v0.1.4` ausgewählt werden.
3. HACS muss die Integration unter `custom_components/benni_core_contracts`
   installieren; `hacs.json` verwendet dafür `content_in_root=false` und
   `zip_release=false`.
4. Die technische Bereitstellung endet bei einer installierbaren HACS-
   Version. Reload, Neustart und ConfigEntry-Aktivierung bleiben ein
   ausdrücklich read-only Benni-Schritt.

## Nach der Installation

Nach dem Laden des expliziten ConfigEntry steht das Sidebar-Panel `Core
Contracts` zur Verfügung. Es pollt die fünf bestehenden read-only
WebSocket-Kommandos, zeigt Revision, Contract-/Feld-Health, Quellen,
Freshness, Safety, Fallback, Root Cause und Consumer-Effekt und führt keine
Aktion aus. Die fachliche und visuelle Abnahme erfolgt durch Benni in HA auf
Desktop und Lenovo M11.

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
