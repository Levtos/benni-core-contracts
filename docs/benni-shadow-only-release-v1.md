# Benni Shadow-Only Release Candidate v1

Stand: 2026-07-23. Dieser installierbare Shadow-only-Alpha trägt die Version
`0.1.0-alpha.2`, den HA-Domain-Namen `benni_core_contracts` und den einzigen
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

- Nur `profile=benni` darf als Runtime-ConfigEntry gestartet werden.
- `parent_future`/Eltern bleibt vollständig `out_of_scope`; der gemeinsame
  Graph-/Fixture-Code darf Eltern weiterhin beschreiben.
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

Der aktuelle lokale Stand enthält keine neue Live-Evidence: Der direkte
Einhornzentrale-State-Zugriff war ohne bereitgestellte Authentifizierung mit
HTTP 401 blockiert. Es wurden keine Tokens, Cookies oder vollständigen HA-
Zustände gespeichert.

## Paket- und HACS-Status

Manifest, `pyproject.toml` und die Shadow-Alpha-Dokumentation verwenden
`0.1.0-alpha.2`. `hacs.json` beschreibt das Paket und aktiviert absichtlich
kein Release-Zip (`zip_release=false`); HACS verwendet den öffentlichen
GitHub-Mirror als Installationsquelle. GitLab-Quelle, GitHub-Mirror, Tag und
Pre-Release müssen auf denselben Commit zeigen.

Die Alpha ist installierbar, aber nicht automatisch aktiviert. Für eine
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
