# Shadow RC `0.1.0b1`

## Inhalt

- expliziter read-only ConfigEntry-Modus `shadow_only`;
- kein impliziter Modus-Default und keine aktivierbare `published`-Variante;
- Benni-only Runtime-Scope; Eltern bleibt `parent_future`/`out_of_scope`;
- leere SourceBinding- und Entity-Allowlist im initialen Shadow-Eintrag;
- read-only State-Listener und versionierte interne Contract-/Diagnose-/WS-
  Grundlagen;
- harte Boundary gegen Entity-Plattform, Services, Actuation, Policy-Imports,
  Registry- und Consumer-Änderungen;
- Paket-/HACS-Metadaten und lokale Installationsdokumentation für einen
  späteren Shadow-Test.

## Nicht enthalten

Diese Version ist nicht produktiv veröffentlicht und nicht über HACS
installiert. Sie enthält keine Migration, keinen Consumer-Cutover, keine
öffentlichen HA-Entities, keine Entity-Allowlist-Freigabe, keine Policy-
Entscheidung und keine Live-Konfiguration.

## Bekannte Evidence-Lücken

Die Live-State-API war ohne bereitgestellte Authentifizierung mit HTTP 401
nicht lesbar. Deshalb bleiben aktuelle Source-States, Ownership,
Gerätezeitstempel, retained-/restore-/stale-Herkunft, Konfliktfreiheit sowie
die Lock-Revalidierung offen. Fixtures und lokale Shadow-Tests sind keine
Live-Freigabe.
