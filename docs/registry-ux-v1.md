# Registry- und Binding-UX (#18)

Die Svelte-5-Oberfläche verwendet denselben RegistryDomainService für Benni und
Eltern. Der ConfigEntry ist kein Editor und keine zweite Registry. Die neue
Registry-Ansicht ergänzt die bestehenden read-only Contract-/Diagnoseansichten.

## Ablauf

- Profil auswählen; aktuelle Registry, Quelle/Health und Historie lesen.
- Binding anlegen oder bearbeiten. Die Entity-Auswahl durchsucht die tatsächlich
  von HA gelieferten Entities einschließlich Anzeigenamen. Keine Zuordnung wird
  anhand eines Namens oder einer Domain automatisch übernommen.
- Anzeigename, Entity, Capability, Rolle/Feld, Required, TTL, Fallback und Enabled
  bearbeiten. Binding-ID, Source-ID und Profil bleiben geschützt. Neue IDs werden
  einmalig generiert. Ein Gerätewechsel ändert die Entity, nicht die Identität.
- „In Entwurf übernehmen“ bestätigt die Eingabe ausschließlich im serverseitigen
  In-Memory-Draft. „Prüfen“ übernimmt offene Eingaben und ruft Backend-Validate auf.
- Ausschließlich „Speichern“ verwendet den bestehenden atomaren Save-/Activate-
  Pfad. Kein Autosave, auch nicht durch einen State- oder Health-Refresh.
- „Änderungen verwerfen“ verwirft den Draft, nicht die aktive Registry.
- Ein bestätigter Rollback verwendet Revisions-ID, Profil und erwartete Basis.

Die Basisrevision wird bereits beim Öffnen eines lokalen Editors festgehalten.
Ein OCC-Konflikt bewahrt Entwurf und Eingaben. „Aktualisieren“ zeigt den aktuellen
Stand, ohne automatisch zu rebasen. Erst bewusstes Verwerfen erlaubt das erneute
Bearbeiten auf neuer Basis. Dirty-Profilwechsel und Dirty-Rollback werden blockiert.
Interne Navigation erhält den Editor; Verlassen der Seite nutzt beforeunload.
Auch ungültiger JSON-Fallback-Text bleibt Bestandteil der UI-Sitzung.

## API und Security

Die vorhandenen Admin-Kommandos `registry/draft/*`, `registry/binding/*` und
`registry/rollback` bleiben autoritativ. Frontend-Rechte ersetzen keine
Backend-Prüfung. Nichtadministratoren können lesen, aber keine Drafts erzeugen.

`benni_core_contracts/registry/view` ist eine separate read-only Abfrage mit
`profile=benni|eltern`. Sie liefert bereinigte Registry/Revisionen und ausschließlich
profilbezogene Consumer-Requirements aus der vorhandenen ConsumerApi. Sie erzeugt
keinen Draft und installiert keinen Runtime-Graphen. Bei Backendausfall bleibt
der vorhandene profilbezogene LKG lesbar; Historie wird als nicht verfügbar markiert.
Die bestehenden fünf read-only Kommandos erhalten einen optionalen Profilselektor.
Ein explizit fehlender ConfigEntry oder ein Profil-Mismatch fällt niemals auf den
anderen Haushalt zurück. Aufrufe ohne Selektor bleiben kompatibel.

Consumer-Nutzung wird read-only aus deklarierten Rollen und dem Fusion-DAG
abgeleitet. Es gibt keine manuelle Consumer-Zuordnung oder Override-UX.

## Abnahmegrenze

Store-Tests decken beide Profile, CRUD/Enabled, echte Entity-Kandidaten, ID-Schutz,
Dirty-State, Validate/Save, Fehler/OCC, Discard, Refresh, Profilwechsel, Historie,
Rollback, LKG, Admin und Consumer-Nutzung ab. Svelte-Komponententests prüfen die
gerenderte Rechte-/ID-Grenze und DOM-/Eingabeerhalt bei Updates. Python-Tests prüfen
read-only Runtime-Erhalt, Profilselektion, Consumer-Filter und LKG ohne Historie.
Responsive Layout: Formular zweispaltig, unter 700 px einspaltig; Controls 44 px.

Keine HA-Live-/Deployment-Abnahme. Fusion-Editor (#19), Import/Export (#22) und
Diagnose-Reparatur (#23) sind nicht Teil dieses Commits.
