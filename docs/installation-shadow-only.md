# Geplante Benni-Installation: Shadow-only v1

Diese Anleitung beschreibt nur die Voraussetzungen und den kontrollierten
Ablauf für eine spätere, ausdrücklich freigegebene read-only Installation.
Sie wurde im aktuellen Gate nicht ausgeführt. Es gab keinen Remote-Release,
keinen HACS-Install, keine ConfigEntry-Aktivierung und keinen Zugriff mit
Token oder Cookie.

## Vorbedingungen

Vor einer Installation müssen alle folgenden Punkte separat bestätigt sein:

1. Ein freigegebener Remote-/Paketstand von `benni_core_contracts` mit der
   dokumentierten Shadow-RC-Version `0.1.0b1` liegt vor. Der aktuelle lokale
   Stand ist nicht über HACS installierbar.
2. Die Installation erfolgt ausschließlich auf Benni/Einhornzentrale. Das
   Elternprofil bleibt `parent_future` und wird nicht installiert oder
   aktiviert.
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

## Verifikation nach einer freigegebenen Installation

Die zuständige Person prüft read-only:

- ConfigEntry ist vorhanden, Profil ist `benni`, Modus ist `shadow_only`;
- die SourceBinding-Liste ist genau die ausdrücklich freigegebene Liste;
- keine Entity-Plattform und keine HA-Entity wurden erzeugt;
- keine Services sind registriert und keine Actuation wurde ausgeführt;
- die Rohsource-, Fallback-, Fusion-, Diagnose- und Policy-Zwischenwerte
  erscheinen nicht als Entities;
- fehlender Zugriff führt zu `OPEN`/`blocked` und nicht zu erfundenen States;
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

## Aktuelle Blocker

- Der direkte State-API-Zugriff auf Einhornzentrale liefert ohne
  Authentifizierung HTTP 401.
- Eine aktuelle Registry-/Live-Revalidierung der kanonischen Lock-ID
  `lock.flur_aqara_smart_lock_u200` fehlt.
- Gerätezeitstempel, nicht-retained State-Change-Evidence und Ownership sind
  für die produktiven Kandidaten noch nicht belegt.
- Das Repository ist nicht remote veröffentlicht; HACS kann diesen lokalen
  Arbeitsstand nicht installieren.
