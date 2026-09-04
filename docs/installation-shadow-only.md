# Geplante Benni-Installation: Shadow-only v1

Diese Anleitung ist die historische Benni-only Installationsprozedur für den
Release-Kandidaten `0.1.4`. Sie ist kein aktueller Ausschluss des
profilisolierten `eltern`-Registry-/Runtime-Pfads aus Issue #21.

Diese Anleitung beschreibt die Voraussetzungen und den kontrollierten Ablauf
für die ausdrücklich read-only Shadow-Installation des stabilen Releases
`0.1.4`.
Der Release ist über den öffentlichen GitHub-Mirror als HACS-Quelle
installierbar. Die Installation wurde von Codex nicht auf Home Assistant
ausgeführt; sie aktiviert weder ConfigEntry noch SourceBindings automatisch.

## Vorbedingungen

Vor einer Installation müssen alle folgenden Punkte separat bestätigt sein:

1. Der HACS-Eintrag `Levtos/benni-core-contracts` und der Tag `v0.1.4`
   zeigen auf denselben geprüften Commit. HACS muss benutzerseitig den
   stabilen Release auswählen.
2. Für diese historische Prozedur erfolgt die Installation ausschließlich auf
   Benni/Einhornzentrale. Das Elternprofil bleibt in diesem Release-
   Gate `parent_future` und wird nicht installiert oder aktiviert.
3. Der Zugriff auf HA ist autorisiert und read-only. Es werden keine Tokens,
   Cookies oder vollständigen State-Dumps im Repository abgelegt.
4. Die erlaubten Kandidaten, Snapshot-Felder, Prüfzeit und
   Deinstallations-/Deaktivierungsfrist sind vorab festgelegt.

## ConfigEntry

Im Config Flow müssen explizit gesetzt werden:

```text
profile = benni
mode    = shadow_only
```

`mode` darf nicht fehlen. `shadow`, `published`, `eltern` und eine öffentliche
Entity-Allowlist werden abgewiesen. Der initiale Eintrag enthält keine
SourceBindings; die Matrix wird nicht automatisch aktiviert. Explizite
Bindings dürfen nur über einen separat geprüften Konfigurationsimport in die
ConfigEntry gelangen und bleiben read-only.

Für den aktuellen produktiven Registry-/Exchange-Bootstrap akzeptiert der
ConfigEntry beide Profile. Historische Matrix-/Evidence-Datensätze bleiben
auch dort nicht autoritativ.

## Verifikation nach einer freigegebenen Installation

Die zuständige Person prüft read-only:

- ConfigEntry ist vorhanden, Profil ist `benni`, Modus ist `shadow_only`;
- die SourceBinding-Liste ist genau die ausdrücklich freigegebene Liste;
- keine Entity-Plattform und keine HA-Entity wurden erzeugt;
- keine Services sind registriert und keine Actuation wurde ausgeführt;
- die Rohsource-, Fallback-, Fusion-, Diagnose- und Policy-Zwischenwerte
  erscheinen nicht als Entities;
- fehlender Zugriff führt zu `OPEN`/`blocked` und nicht zu erfundenen States;
- das Sidebar-Panel `Core Contracts` zeigt reale Payloads aus den fünf
  erlaubten read-only-WebSocket-Kommandos; eine lokale Preview-Fixture wird in
  Home Assistant nicht verwendet;
- Desktop und Lenovo M11 bleiben innerhalb der Bedienbarkeitsprüfung frei von
  Aktionen, Services und öffentlichen HA-Entities;
- Opening, Lock und Cover-Position bleiben bei fehlender, stale, retained,
  restaurierter oder konfliktärer Evidence `unknown` und verwenden `reject`.

Zu jeder geprüften Source werden nur minimierte, sanitizierte Evidence-Felder
übernommen: Entity-ID, Domain, State, relevante Attribute, Availability,
`last_changed`, `last_updated`, Gerätezeitstempel, Herkunft, Owner und
retained-/restore-/stale-/conflict-Hinweise. Secrets und unnötige vollständige
HA-Zustände werden nicht gespeichert.

## Deaktivierung und Entfernung

Nach dem Evidence-Test muss die Shadow-ConfigEntry deaktiviert oder entfernt
und der temporäre Paketstand nach dem freigegebenen Betriebsablauf entfernt
werden. Es darf keine Entity-Allowlist, kein Consumer-Cutover und kein
produktiver Published-Modus aus diesem Test entstehen. Die Deaktivierung und
Entfernung gehören zu einem separaten, ausdrücklich freigegebenen Live-
Schritt; sie wurden hier nicht ausgeführt.

## Aktuelle Evidence-Gates

- Der direkte State-API-Zugriff auf Einhornzentrale liefert ohne
  Authentifizierung HTTP 401.
- Die beiden konkreten Quellen des Opening-Piloten wurden am 30.07.2026
  zusätzlich read-only als MQTT-Entities revalidiert:
  `binary_sensor.kitchen_patio_door_open_contact` und
  `binary_sensor.kitchen_patio_door_tilt_contact`. Das ist keine automatische
  ConfigEntry-Aktivierung und kein Freshness-Pass für den Setup-Snapshot.
- Eine aktuelle Registry-/Live-Revalidierung der kanonischen Lock-ID
  `lock.flur_aqara_smart_lock_u200` fehlt.
- Gerätezeitstempel und explizite nicht-retained Event-Herkunft sind für die
  Pilotquellen noch nicht aus dem State-Snapshot belegt; für die übrigen
  produktiven Kandidaten bleiben sie ebenfalls offen.
- Die Installation liefert noch keine Live-Evidence-Freigabe. Source-Owner,
  Gerätezeitstempel, nicht-retained State-Change-Evidence und Lock-
  Revalidierung bleiben vor dem nächsten Published-Live-Schritt offen.
