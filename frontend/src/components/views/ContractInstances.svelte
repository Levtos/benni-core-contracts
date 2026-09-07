<script lang="ts">
  import type { RegistryEditor } from '../../lib/core-contracts/registry.svelte';
  import Panel from '../../lib/ui/Panel.svelte';
  let { registry }: {registry:RegistryEditor}=$props();
</script>

<Panel title="Contracts" eyebrow="Instanzen · Schemata bleiben code-definiert">
  {#if registry.admin}<button disabled={registry.busy} onclick={()=>registry.selectInstance(null)}>Contract-Instanz anlegen</button>{/if}
  {#each registry.instances as instance (String(instance.contract_id))}
    <article><div><strong>{String(instance.display_name ?? instance.contract_id)}</strong><code>{String(instance.contract_id)}</code><span>{String(instance.schema_id)} v{String(instance.schema_version ?? 1)} · {registry.profile}</span></div>
      {#if registry.admin}<div class="actions"><button disabled={registry.busy} onclick={()=>registry.selectInstance(instance)}>Contract bearbeiten</button><button disabled={registry.busy} onclick={()=>{if(window.confirm('Contract-Instanz aus dem Entwurf löschen? Referenzierte Instanzen werden vom Backend geschützt.')) void registry.removeInstance(instance);}}>Contract löschen</button></div>{/if}
    </article>
  {/each}
  {#if !registry.instances.length}<p>Noch keine Contract-Instanzen konfiguriert.</p>{/if}
  {#if registry.instanceEditor && registry.admin}
    <form onsubmit={event=>{event.preventDefault(); void registry.applyInstance();}}>
      <fieldset disabled={registry.busy}>
        <label>Contract-ID (geschützt)<input value={String(registry.instanceEditor.contract_id)} readonly /></label>
        <label>Contract-Anzeigename<input value={String(registry.instanceEditor.display_name ?? '')} oninput={event=>{if(registry.instanceEditor)registry.instanceEditor.display_name=event.currentTarget.value;}} required /></label>
        <label>Contract-Schema<select value={`${registry.instanceEditor.schema_id}:${registry.instanceEditor.schema_version}`} disabled={!!registry.originalInstance} onchange={event=>{const schema=registry.view?.schemas?.find(s=>`${s.schema_id}:${s.version}`===event.currentTarget.value);if(schema && registry.instanceEditor){registry.instanceEditor.schema_id=schema.schema_id;registry.instanceEditor.schema_version=schema.version;}}} required><option value="">Schema auswählen</option>{#each registry.view?.schemas ?? [] as schema}<option value={`${schema.schema_id}:${schema.version}`}>{schema.schema_id} v{schema.version}</option>{/each}</select></label>
        <button type="submit">Contract in Entwurf übernehmen</button>
      </fieldset>
    </form>
  {/if}
  <p>Keine Aktivierung ohne explizites Speichern. Felder und Schema-Versionen werden durch die Engine validiert.</p>
</Panel>

<style>
  article,.actions {display:flex;flex-wrap:wrap;gap:var(--space-3);align-items:center;justify-content:space-between;}
  article {padding:var(--space-3) 0;border-bottom:1px solid var(--color-border);}
  article>div:first-child,label {display:grid;gap:var(--space-2);overflow-wrap:anywhere;}
  fieldset {border:0;display:grid;gap:var(--space-3);padding:var(--space-3) 0;}
  input,select,button {min-height:44px;min-width:0;background:var(--color-background);color:var(--color-text-primary);border:1px solid var(--color-border);border-radius:var(--radius-control);padding:8px 12px;font:inherit;}
  button {cursor:pointer;} button:disabled {opacity:.5;cursor:default;} p,code,span {color:var(--color-text-secondary);}
</style>
