<script lang="ts">
  import type { RegistryEditor } from '../../lib/core-contracts/registry.svelte';
  import type { CoreContractsStore } from '../../lib/core-contracts/store.svelte';
  import Panel from '../../lib/ui/Panel.svelte';
  let { registry, store }: {registry: RegistryEditor; store: CoreContractsStore} = $props();
  const strategies=['first_healthy','latest','any_true','all_true','opening_contacts','opening_is_open','opening_available','opening_source_count'];
  let selectedSchema=$derived(registry.view?.schemas?.find(s=>`${s.schema_id}:${s.version}`===registry.fusionSchema));
  function input(kind: 'input_binding_ids' | 'input_fusion_ids', id: string, checked: boolean) {
    if (registry.fusionEditor) registry.fusionEditor[kind]=checked ? [...registry.fusionEditor[kind],id] : registry.fusionEditor[kind].filter(v=>v!==id);
  }
  function earlier(index: number) {
    const ids=registry.fusionEditor?.input_binding_ids;
    if (!ids || index===0) return;
    [ids[index-1],ids[index]]=[ids[index],ids[index-1]];
  }
</script>

<Panel eyebrow="Registry · derselbe Entwurf" title="Fusionen">
  <p>Reine Datenfusion, keine Policy. Inputs können Bindings oder andere Fusionen desselben Profils und Felds sein.</p>
  {#if registry.admin}<button disabled={registry.busy} onclick={()=>registry.selectFusion(null)}>Fusion anlegen</button>{/if}
  {#if !registry.fusions.length}<p>Keine Fusionen konfiguriert.</p>{/if}
  {#each registry.fusions as fusion (fusion.fusion_id)}
    {@const diagnostic=store.diagnostics.find(d=>d.contract_id===fusion.contract_id)?.fields.find(f=>f.field===fusion.field)}
    <article><strong>{fusion.contract_id}.{fusion.field}</strong><code>{fusion.fusion_id}</code><span>{fusion.strategy} · Bindings: {fusion.input_binding_ids.join(', ') || '—'} · Fusionen: {fusion.input_fusion_ids.join(', ') || '—'}</span>
      <small>Runtime: {diagnostic?.health ?? 'Noch nicht berechnet'} · Quality: {diagnostic?.quality ?? '—'} · Freshness: {diagnostic?.freshness ?? '—'}</small>
      {#if diagnostic}<small>Aktive Quellen: {diagnostic.active_source_entities.join(', ') || '—'} · Kandidaten: {diagnostic.source_entities.join(', ') || '—'}</small>{/if}
      {#if registry.admin}<div class="actions"><button disabled={registry.busy} onclick={()=>registry.selectFusion(fusion)}>Fusion bearbeiten</button><button disabled={registry.busy} onclick={()=>{if(window.confirm(`Fusion ${fusion.fusion_id} aus dem Entwurf löschen?`)) void registry.removeFusion(fusion);}}>Fusion löschen</button></div>{/if}
    </article>
  {/each}
  {#if registry.fusionEditor && registry.admin}
    <form onsubmit={(e)=>{e.preventDefault(); void registry.applyFusion();}}>
      <fieldset disabled={registry.busy}>
        <label>Fusion-ID (geschützt)<input readonly value={registry.fusionEditor.fusion_id} /></label>
        <label>Profil<input readonly value={registry.profile} /></label>
        <label>Contract-Instanz<input list="fusion-contracts" required bind:value={registry.fusionEditor.contract_id} onchange={()=>{const instance=registry.instances.find(i=>i.contract_id===registry.fusionEditor?.contract_id); if(instance) registry.fusionSchema=`${instance.schema_id}:${instance.schema_version ?? 1}`;}} /></label>
        <datalist id="fusion-contracts">{#each registry.instances as instance}<option value={String(instance.contract_id)}>{String(instance.schema_id)}</option>{/each}</datalist>
        <label>Schema (für neue Instanz)<select bind:value={registry.fusionSchema} disabled={registry.instances.some(i=>i.contract_id===registry.fusionEditor?.contract_id)} required><option value="">Schema auswählen</option>{#each registry.view?.schemas ?? [] as schema}<option value={`${schema.schema_id}:${schema.version}`}>{schema.schema_id}.v{schema.version}</option>{/each}</select></label>
        <label>Contract-Feld<select bind:value={registry.fusionEditor.field} required><option value="">Feld auswählen</option>{#each selectedSchema?.fields ?? [] as field}<option value={field.name}>{field.name} ({field.value_type})</option>{/each}</select></label>
        <label>Strategie<select bind:value={registry.fusionEditor.strategy}>{#each strategies as strategy}<option value={strategy}>{strategy}</option>{/each}</select></label>
      </fieldset>
      <fieldset disabled={registry.busy}><legend>Binding-Inputs – ausdrücklich auswählen</legend>{#each registry.bindings as binding (binding.binding_id)}<label class="check"><input type="checkbox" checked={registry.fusionEditor.input_binding_ids.includes(binding.binding_id)} onchange={(e)=>input('input_binding_ids',binding.binding_id,e.currentTarget.checked)} />{binding.display_name ?? binding.binding_id} · {binding.field} · {binding.enabled===false?'deaktiviert':'aktiv'}</label>{/each}</fieldset>
      <ol>{#each registry.fusionEditor.input_binding_ids as id,index (id)}<li>{id}<button type="button" disabled={index===0 || registry.busy} onclick={()=>earlier(index)}>Priorität erhöhen</button></li>{/each}</ol>
      <fieldset disabled={registry.busy}><legend>Fusion-Inputs</legend>{#each registry.fusions.filter(f=>f.fusion_id!==registry.fusionEditor?.fusion_id) as fusion (fusion.fusion_id)}<label class="check"><input type="checkbox" checked={registry.fusionEditor.input_fusion_ids.includes(fusion.fusion_id)} onchange={(e)=>input('input_fusion_ids',fusion.fusion_id,e.currentTarget.checked)} />{fusion.contract_id}.{fusion.field} · {fusion.strategy}</label>{/each}</fieldset>
      <p>Eine neue Contract-ID erzeugt beim Übernehmen eine Instanz des ausgewählten Schemas im Draft. Zyklen, falsche Inputs und Strategien werden im Backend abgewiesen. Keine Aktivierung ohne „Speichern“.</p>
      <button disabled={registry.busy} type="submit">Fusion in Entwurf übernehmen</button>
    </form>
  {/if}
</Panel>

<style>
  p,small,code { color:var(--color-text-secondary); } article { display:grid; gap:8px; padding:16px 0; border-bottom:1px solid var(--color-border); overflow-wrap:anywhere; }
  .actions { display:flex; gap:8px; flex-wrap:wrap; } fieldset { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); border:0; padding:16px 0; gap:16px; } label { display:grid; gap:8px; font-size:.85rem; } .check { display:flex; align-items:center; }
  input,select,button { min-height:44px; min-width:0; border:1px solid var(--color-border); border-radius:var(--radius-control); padding:8px 12px; color:var(--color-text-primary); background:var(--color-background); font:inherit; } button { cursor:pointer; } button:disabled { opacity:.5; cursor:default; } input:read-only { color:var(--color-text-muted); } .check input { width:24px; min-height:24px; } li button { margin:4px 12px; }
  @media(max-width:700px) { fieldset { grid-template-columns:1fr; } }
</style>
