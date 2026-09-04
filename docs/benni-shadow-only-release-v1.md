# Benni Shadow-Only Release v1

> Historischer Release-/Evidence-Gate (Stand 2026-07-28). Seine Benni-only-
> Installationsgrenzen beschreiben den damaligen `0.1.4`-Kandidaten und sind
> keine globale Sperre für den aktuellen profilisolierten Registry-/Runtime-
> Pfad aus Issue #21.

Dieser installierbare Shadow-only-Release trägt die Version
`0.1.4`, den HA-Domain-Namen `benni_core_contracts` und den einzigen
Runtime-Modus `shadow_only`.

## Zweck

Der Kandidat ist für eine ausdrücklich read-only Shadow-Installation auf
Benni vorbereitet. Die Installation darf ausschließlich dazu dienen,
zustands- und zeitbezogene Evidence der bereits definierten Source-Bindings
zu beobachten. Sie ist keine produktive Contract-Veröffentlichung und keine
Freigabe für Consumer, Policies oder Actuation.

Die interne Kette bleibt:

```text
SourceBinding -> AtomicSignal -> Fusion -> PublishedContract
                                      |             |
                                      +--> DiagnosticProjection
                                                    |
                                                    +--> Shadow Evidence
```

Die Matrix und externe, sanitizierte Snapshots sind Evidence/Testdaten. Sie
werden nicht automatisch in eine ConfigEntry übernommen. Ein leerer
`shadow_only`-Eintrag besitzt deshalb keine SourceBindings.

## Harte Grenzen

- Für diesen historischen Release darf nur `profile=benni` als Runtime-
  ConfigEntry gestartet werden.
- `parent_future`/Eltern bleibt innerhalb dieses historischen Gates
  `out_of_scope`; der gemeinsame Graph-/Fixture-Code darf Eltern weiterhin
  beschreiben.
- Ein fehlendes oder unbekanntes `mode` wird abgewiesen. Es gibt keinen
  impliziten Shadow-Default.
- Der einzige akzeptierte Modus ist `mode=shadow_only`. `published` und das
  historische `shadow` sind nicht aktivierbar.
- Eine öffentliche Entity-Allowlist ist im Release-Kandidaten nicht zulässig;
  die Projektionsmenge bleibt immer leer.
- Es gibt keine Entity-Plattform, keine Services, keine Actuation, keine
  Policy-Imports, keine Registry-/Consumer-Änderung und keine Migration.
- Lock und Cover-Position bleiben Evidence-only. Die historische
  `lock.aqara_smart_lock_u200` wird als Quelle abgelehnt; die aktuelle
  Kandidaten-ID `lock.flur_aqara_smart_lock_u200` benötigt weiterhin
  Registry-/Ownership-/Gerätezeit-Revalidierung.

Der aktuelle produktive Registry-/Exchange-Pfad verwendet dagegen dieselbe
ShadowRuntime für `benni` und `eltern`. Historische Evidence dieses Release-
Gates bleibt nicht autoritativ und wird nicht automatisch als Registry-
Konfiguration aktiviert.

## Read-only State-Beobachtung

Der HA-Adapter liest ausschließlich bereits vorhandene States für explizit
konfigurierte Bindings. Er erfasst, soweit HA und die Quelle es bereitstellen:

- Entity-ID, Domain, State und ausgewählte Attribute;
- technische Verfügbarkeit sowie `last_changed`/`last_updated`;
- einen nachgewiesenen Gerätezeitstempel oder ein ausdrücklich echtes,
  nicht-retained HA-State-Change-Ereignis;
- retained-, restored-, stale- und Konflikthinweise sowie Source-Ownership,
  wenn diese im Snapshot belegt sind.

`received_at`, Batterieprozente, Restore und ein bloßes `last_updated` werden
nicht zu Freshness-Evidence aufgewertet. Unklare Herkunft bleibt `OPEN` bzw.
`blocked`. Physische Opening-, Lock- und Positionsfelder dürfen ohne
belastbare Evidence keinen positiven Zustand behaupten.

Der historische HTTP-State-API-Zugriff war ohne bereitgestellte
Authentifizierung mit HTTP 401 blockiert. Eine spätere, begrenzte read-only
Revalidierung belegte die beiden konkreten MQTT-Rohquellen des Opening-Piloten;
Gerätezeitstempel und eine automatische Freigabe folgen daraus nicht. Es
wurden keine Tokens, Cookies oder vollständigen HA-Zustände gespeichert.

## Paket- und HACS-Status

Manifest, `pyproject.toml` und die Shadow-Dokumentation verwenden
`0.1.4`. `hacs.json` beschreibt das Paket und aktiviert absichtlich
kein Release-Zip (`zip_release=false`); HACS verwendet das kanonische
öffentliche GitHub-Repository als Installationsquelle. Repository, Tag und
Stable-Release müssen auf denselben Commit zeigen.

Der Release enthält zusätzlich das statische, read-only Svelte-Panel für die
Live-Prüfung der fünf bestehenden WebSocket-Kommandos. Sie ist installierbar,
aber nicht automatisch aktiviert. Für eine
separat freizugebende Shadow-Installation auf Benni müssen zusätzlich ein
autorisierter read-only HA-Zugriff und ein definierter Snapshot-/Deinstallations-
ablauf vorliegen. Die Installation selbst ist keine Live-Freigabe und ersetzt
keine Evidence-Prüfung.

## Prüfstatus

Der Kandidat wird ausschließlich mit lokalen Unit-/Architekturtests,
Syntax-/Metadatenprüfungen und Boundary-Checks geprüft. Erwartete und aktuell
erzeugte HA-Entities bleiben `0`; auch eine Shadow-ConfigEntry ändert daran
nichts.

Offen bleiben insbesondere aktuelle State-/Registry-Evidence, Source-Owner,
Gerätezeitpfade, retained-/restore-/stale-Abgrenzung, die Lock-Revalidierung
und eine ausdrücklich freigegebene spätere Installation.
