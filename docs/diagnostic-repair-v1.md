# Diagnose → Binding-Reparatur (#23)

Die vorhandene read-only Diagnoseprojektion wird um aktives Profil, Registry-
Revision/ID, Feldwert, Fallback, Binding-IDs (auch bei vollständig fehlenden
Beobachtungen), konfigurierte Kandidaten und Consumer-Impact ergänzt. Health,
Quality, Freshness, Safety, aktive Quellen und Root Causes bleiben die vorhandenen
Graph-/Quality-Modelle. Degradierungsdauer wird aus deren Ursachenzeitpunkten
abgeleitet; unbekannte Dauer wird nicht als Null behauptet.

Die read-only Diagnose wertet die konfigurierten Contract-Instanzen im bestehenden
Runtime-Graphen aus. Sie erzeugt weder Draft noch Registry-Write. Historische
Pilotprojektionen ohne passenden Registry-Graphen erhalten keine erfundene Revision.

Administratoren können „Binding bearbeiten: <ID>“ wählen. Der Editor öffnet exakt
diese ID im passenden Profil. Veralteter Revisionskontext wird angezeigt und muss
aktualisiert werden; ein Dirty-Editor wird nicht still ersetzt. Dann:

Entity ändern → Prüfen → Speichern → neue atomare Revision → Runtime-Neubewertung
→ aktualisierte Diagnose. Auch Rollback stößt ein read-only Frontend-Refresh an.
Ein ungültiger Repair lässt die aktive Revision unverändert. State-/Freshness-/
Quality-/Health-Ereignisse dürfen Bindings niemals automatisch ersetzen,
deaktivieren oder speichern. Consumer-Impact ist ausschließlich diagnostisch.

Tests beweisen den synthetischen Eltern-Repair einschließlich fehlender Source,
stabiler ID, Validation ohne Write, abgewiesener Änderung, erfolgreichem Save,
neuem Wert/Revision und unveränderten Registry-Daten bei wiederholter Diagnose.
Frontend-Tests prüfen exakte Direktnavigation und stale Revision ohne Save.
Keine HA-Live-/Deployment-Abnahme und kein externer Consumer-Cutover.
