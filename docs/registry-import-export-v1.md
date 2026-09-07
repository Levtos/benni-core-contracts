# Import, Export und Migrationsvorschläge (#22)

Transfer ist kein zweiter Store. PostgreSQL und die vorhandenen Revisions-/OCC-
Regeln bleiben autoritativ. Die Svelte-Registry bietet JSON-Download, Datei-/Text-
Import, HA-Mehrfachauswahl und eine ausdrücklich gestartete ConfigEntry-Analyse.

## Format

```json
{
  "format": "core-contracts-registry",
  "format_version": 1,
  "payload": {
    "profile": "eltern",
    "schema_version": 1,
    "bindings": [],
    "fusions": [],
    "contract_instances": [],
    "consumer_overrides": {},
    "registry_metadata": {}
  }
}
```

Der Export enthält die vollständige aktive Profilkonfiguration einschließlich
stabiler IDs und vorhandener Overrides/Metadata, aber keine Runtime-Beobachtungen,
DB-Verbindung, Zugangsdaten, Aktivierungszustände oder historische Akteursdaten.
Revisionen werden beim Import neu über den kanonischen Store erzeugt; eine Datei
kann keine aktive Revisionsnummer erzwingen. Ein LKG kann explizit exportiert werden.
Konfiguration mit sensiblen Schlüsseln oder Credential-URLs wird abgewiesen,
nicht als vermeintlich vollständiger Export heimlich verändert.

Unbekannte Dokument-/Payload-/Binding-/Fusion-/Instance-/Fallback-Felder und
unbekannte Format-/Schema-Versionen werden abgewiesen. Boolean-/TTL-/ID-Listen
werden typgeprüft, keine Truthiness-Konvertierung von `"false"`. Metadata und
der bestehende Override-Container sind ausdrücklich JSON-Datenbereiche, keine
zusätzlichen ausführbaren Konfigurationsbefehle. Grenze: 2 MB, 32 JSON-Ebenen.

## Import-Lifecycle

1. JSON/Format/Version/Profil prüfen.
2. Vorhandene Registry-/Schema-/Graphvalidierung ausführen.
3. Neue In-Memory-Draft-Session auf der erwarteten Basis öffnen.
4. Validierten Edit-Stand und Prüfergebnis anzeigen.
5. Nur ein nachfolgendes explizites „Speichern“ erzeugt/aktiviert eine Revision.

Ein fehlerhafter Import erzeugt keinen Draft und verändert keine aktive Registry.
Cross-Profile-Import ist verboten; dieselbe Datei darf nicht automatisch auf den
anderen Haushalt umgeschrieben werden. Dirty-Entwürfe müssen vor Import bewusst
gespeichert oder verworfen werden. OCC bleibt bis zur Aktivierung wirksam.

Admin-Kommandos: `registry/export`, `registry/import`,
`registry/migration_candidates`. Die vorhandene Admin-Grenze gilt auch für die
ConfigEntry-Analyse; interne ConfigEntry-Inhalte werden nicht ans Frontend kopiert.

## Kandidaten statt automatischer Migration

Mehrere tatsächlich in HA vorhandene Entities auswählen → Kandidaten erzeugen →
pro Kandidat Binding-Eingabe öffnen → Rolle/Capability ausdrücklich festlegen →
Prüfen → Speichern. Keine Namens-/Domain-Heuristik erzeugt produktive Bindings.

Die Analyse traversiert Daten/Optionen ausschließlich von ConfigEntries mit
ausdrücklich passendem Profil. Sie liefert Entity-ID, Integration und Feldpfad;
mehrfach verwendete Entities werden als mögliche gemeinsame Rolle markiert.
Nicht profilierte Einträge werden nicht einem Haushalt zugeraten. Historische
Source-Binding-Evidence wird nicht importiert oder in produktive Daten konvertiert.
Es werden keine externen Integrationen geändert und keine Consumer migriert.

Backend-Tests: Export/Roundtrip, Import ohne Persist/Activation, Version-/Typ-/
Unknown-Field-Ablehnung, Topologiefehler, Profilgrenzen, Secrets und unverändernde
Migrationsanalyse. Frontend-Tests: Import-/Export-Lifecycle, ungültiges JSON,
Dirty-/Profilguard und Kandidaten ohne Write. Keine Live-/Deployment-Abnahme.
