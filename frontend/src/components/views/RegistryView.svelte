<script lang="ts">
  import type { CoreContractsStore } from '../../lib/core-contracts/store.svelte';
  import type { Profile } from '../../lib/core-contracts/registry.svelte';
  import Panel from '../../lib/ui/Panel.svelte';
  import FusionEditor from './FusionEditor.svelte';
  import RegistryTransfer from './RegistryTransfer.svelte';
  import ContractInstances from './ContractInstances.svelte';
  let { store }: { store: CoreContractsStore } = $props();
  let registry = $derived(store.registry);
  let fallbackError = $derived(registry.fallbackError);
</script>

<div class="registry">
  <div class="toolbar">
    <label>Profil<select value={registry.profile} disabled={registry.busy} onchange={(e) => { void store.switchProfile(e.currentTarget.value as Profile); e.currentTarget.value = registry.profile; }}><option value="benni">Benni</option><option value="eltern">Eltern</option></select></label>
    <button onclick={() => registry.refresh()} disabled={registry.busy}>Aktualisieren</button>
    {#if registry.admin}
      <button onclick={() => registry.validate()} disabled={registry.busy || !!fallbackError}>Prüfen</button>
      <button class="primary" onclick={() => registry.save()} disabled={registry.busy || !registry.dirty || !!fallbackError}>Speichern</button>
      <button onclick={() => registry.discard()} disabled={registry.busy || (!registry.dirty && !registry.draft && !registry.importText)}>Änderungen verwerfen</button>
    {:else}<span>Read-only · Schreiben nur für Administratoren</span>{/if}
  </div>
  <div aria-live="polite">
    <p>Basisrevision {registry.base} · Aktiv {registry.view?.registry.revision?.revision ?? '—'} · {registry.dirty ? 'Ungespeicherte Änderungen' : 'Keine ungespeicherten Änderungen'}</p>
    {#if registry.view?.registry.used_last_known_good}<p class="warning">Degradiert: Last Known Good aktiv. PostgreSQL ist derzeit nicht verfügbar. Speichern benötigt das Backend.</p>{/if}
    {#if registry.view?.registry.reason}<p>Registry-Status: {registry.view.registry.reason}</p>{/if}
    {#if registry.notice}<p>{registry.notice}</p>{/if}
    {#if registry.busy}<p>Abfrage läuft …</p>{/if}
    {#if registry.error}<p class="error" role="alert">{registry.error.code}: {registry.error.message}</p>
      {#if registry.error.code === 'revision_conflict'}<p>Eigene Änderungen bleiben erhalten. „Aktualisieren“ lädt den aktiven Stand zum Vergleich. Erst nach bewusstem Verwerfen wird dessen neue Basis übernommen.</p>{/if}
    {/if}
    {#if registry.validation}<p class:warning={!registry.validation.valid}>{registry.validation.valid ? 'Prüfung erfolgreich – noch nicht gespeichert.' : 'Prüfung fehlgeschlagen – aktive Registry unverändert.'}</p>{#each registry.validation.errors as issue}<p>{issue.path ?? ''}: {issue.message}</p>{/each}{/if}
  </div>
  <Panel title="Bindings" eyebrow="Registry">
    <div class="toolbar"><label>Bindings filtern<input type="search" bind:value={registry.filter} placeholder="Name, ID, Entity oder Rolle" /></label>{#if registry.admin}<button disabled={registry.busy} onclick={() => registry.select(null)}>Binding anlegen</button>{/if}</div>
    {#if !registry.filteredBindings.length}<p>Keine Bindings vorhanden oder kein Filtertreffer.</p>{/if}
    <div class="bindings">{#each registry.filteredBindings as binding (binding.binding_id)}
      <article><div><strong>{binding.display_name ?? binding.binding_id}</strong><code>{binding.binding_id}</code><span>{binding.entity_id} → {binding.field}</span><small>{binding.capability} · {binding.profile_id} · {binding.enabled === false ? 'Deaktiviert' : 'Aktiv'} · TTL {binding.freshness_ttl_seconds}s · {binding.required ? 'Required' : 'Optional'}</small><small>Verwendet von: {registry.consumers(binding).join(', ') || 'Keine deklarierten Consumer'}</small></div>
        {#if registry.admin}<div class="toolbar"><button disabled={registry.busy} onclick={() => registry.select(binding)}>Bearbeiten</button><button disabled={registry.busy} onclick={() => registry.toggle(binding)}>{binding.enabled === false ? 'Aktivieren' : 'Deaktivieren'}</button><button disabled={registry.busy} onclick={() => { if (window.confirm(`Binding ${binding.binding_id} aus dem Entwurf löschen? Erst Speichern aktiviert die Änderung.`)) void registry.remove(binding); }}>Löschen</button></div>{/if}
      </article>
    {/each}</div>
  </Panel>
  {#if registry.editor && registry.admin}
    <Panel title={registry.original ? 'Binding bearbeiten' : 'Neues Binding'} eyebrow="Entwurf · kein Autosave">
      <form onsubmit={(event) => { event.preventDefault(); if (!fallbackError) void registry.apply(); }}>
        <fieldset disabled={registry.busy}>
          <label>Anzeigename<input bind:value={registry.editor.display_name} required /></label>
          <label>Technische ID (geschützt)<input value={registry.editor.binding_id} readonly /></label>
          <label>Source-ID (geschützt)<input value={registry.editor.source_id} readonly /></label>
          <label>Profil<input value={registry.editor.profile_id} readonly /></label>
          <label>Home-Assistant-Entity<input list="registry-ha-entities" bind:value={registry.editor.entity_id} required placeholder="Entity suchen und ausdrücklich auswählen" /></label>
          <datalist id="registry-ha-entities">{#each registry.entities as entity (entity.entity_id)}<option value={entity.entity_id}>{entity.attributes.friendly_name ?? entity.entity_id}</option>{/each}</datalist>
          <label>Capability<input bind:value={registry.editor.capability} required /></label>
          <label>Rolle / Feld<input bind:value={registry.editor.field} required /></label>
          <label>Freshness TTL (Sekunden)<input type="number" min="1" step="1" bind:value={registry.editor.freshness_ttl_seconds} required /></label>
          <label>Fallback<select bind:value={registry.editor.fallback.action}><option value="none">Keiner</option><option value="hold_last">Letzten Wert halten</option><option value="safe_default">Sicherer Standardwert</option><option value="reject">Ablehnen</option></select></label>
          <label>Fallback-Wert (JSON)<input value={registry.fallbackText} oninput={(e) => registry.setFallback(e.currentTarget.value)} aria-invalid={!!fallbackError} /></label>
          <label>Fallback-Begründung<input bind:value={registry.editor.fallback.reason} /></label>
          <label class="check"><input type="checkbox" bind:checked={registry.editor.required} />Required</label>
          <label class="check"><input type="checkbox" bind:checked={registry.editor.enabled} />Enabled</label>
        </fieldset>
        {#if fallbackError}<p class="error" role="alert">{fallbackError}</p>{/if}
        <p>Die Entity-Auswahl ändert keine technische Identität. Erst „Speichern“ aktiviert die neue Revision.</p>
        <button type="submit" disabled={registry.busy || !!fallbackError}>In Entwurf übernehmen</button>
      </form>
    </Panel>
  {/if}
  <FusionEditor {registry} {store} />
  <ContractInstances {registry} />
  <RegistryTransfer {registry} />
  <Panel title="Einstellungen" eyebrow="Bootstrap · read-only">
    <p>Profil: {registry.profile} · Registry-Quelle: {registry.view?.registry.source ?? 'Nicht bereit'}.</p>
    <p>PostgreSQL wird serverseitig konfiguriert. Zugangsdaten gehören ausschließlich in Home-Assistant-Secrets, niemals in Registry, Import oder Frontend. ConfigEntry wählt das Profil; Bindings und Fusionen werden hier im Entwurf verwaltet.</p>
    <p>Consumer-Zuordnungen entstehen aus deklarierten Requirements. Keine manuelle Override-UX. Interne Werte werden nicht automatisch als HA-Entities veröffentlicht.</p>
  </Panel>
  <Panel title="Revisionshistorie" eyebrow="Profilbezogen">
    {#if registry.view?.history_error}<p class="warning">Historie derzeit nicht verfügbar. Vorhandener LKG-Stand bleibt lesbar.</p>{/if}
    {#each registry.view?.revisions ?? [] as revision (revision.id)}<article><div><strong>Revision {revision.revision}</strong><span>{revision.status} · {revision.created_at}</span></div>{#if registry.admin && ['active', 'superseded'].includes(revision.status)}<button disabled={registry.busy || registry.dirty || revision.id === registry.view?.registry.revision?.id} onclick={() => { if (window.confirm(`Revision ${revision.revision} für ${registry.profile} wiederherstellen?`)) void registry.rollback(revision.id); }}>Rollback</button>{/if}</article>{/each}
  </Panel>
</div>

<style>
  .registry { display:grid; gap:var(--space-4); }
  .toolbar { display:flex; flex-wrap:wrap; align-items:end; gap:var(--space-3); }
  label { display:grid; gap:var(--space-2); color:var(--color-text-secondary); font-size:.85rem; }
  input,select,button { min-height:44px; border:1px solid var(--color-border); border-radius:var(--radius-control); padding:8px 12px; background:var(--color-background); color:var(--color-text-primary); font:inherit; min-width:0; }
  button { cursor:pointer; } button:disabled { opacity:.5; cursor:default; } button:hover:not(:disabled),.primary { border-color:var(--color-info); }
  input:read-only { color:var(--color-text-muted); } .warning { color:var(--color-warning); } .error { color:var(--color-danger); }
  article { display:flex; flex-wrap:wrap; gap:var(--space-3); align-items:center; justify-content:space-between; padding:var(--space-4) 0; border-bottom:1px solid var(--color-border); }
  article>div:first-child { display:grid; gap:4px; overflow-wrap:anywhere; } small,code,p { color:var(--color-text-secondary); } code { font-size:.75rem; }
  fieldset { border:0; padding:0; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:var(--space-4); }
  .check { display:flex; align-items:center; } .check input { min-height:24px; width:24px; }
  @media(max-width:700px) { fieldset { grid-template-columns:1fr; } .toolbar label { width:100%; } }
</style>
