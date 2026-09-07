<script lang="ts">
  import type { RegistryEditor } from '../../lib/core-contracts/registry.svelte';
  import Panel from '../../lib/ui/Panel.svelte';
  let { registry }: {registry: RegistryEditor}=$props();
  let query=$state('');
  let filtered=$derived(registry.entities.filter(e=>`${e.entity_id} ${e.attributes.friendly_name ?? ''}`.toLowerCase().includes(query.toLowerCase())));
  function download() {
    const url=URL.createObjectURL(new Blob([registry.exportText],{type:'application/json'}));
    const link=document.createElement('a'); link.href=url; link.download=`core-contracts-${registry.profile}.json`; link.click(); URL.revokeObjectURL(url);
  }
  async function file(input: HTMLInputElement) {
    const selected=input.files?.[0]; if(!selected) return;
    if(selected.size>2_000_000) {registry.notice='Datei ist größer als 2 MB.'; return;}
    registry.importText=await selected.text();
  }
</script>
{#if registry.admin}
  <Panel title="Import / Export" eyebrow="Versionierte Konfiguration">
    <p>Export enthält nur die aktive Konfiguration des ausgewählten Profils. Import wird geprüft und bleibt ein Draft bis zum ausdrücklichen Speichern.</p>
    <button disabled={registry.busy} onclick={()=>registry.exportRegistry()}>Registry exportieren</button>
    {#if registry.exportText}<button onclick={download}>JSON herunterladen</button><details><summary>Export anzeigen</summary><pre>{registry.exportText}</pre></details>{/if}
    <label>JSON-Datei laden<input type="file" accept="application/json,.json" onchange={(e)=>file(e.currentTarget)} /></label>
    <label>Import-JSON<textarea rows="8" bind:value={registry.importText} spellcheck="false"></textarea></label>
    <button disabled={registry.busy || registry.dirty || !registry.importText.trim()} onclick={()=>registry.importRegistry()}>Import prüfen und als Draft laden</button>
  </Panel>
  <Panel title="Entity-Kandidaten und Migrationsvorschläge" eyebrow="Vorschlag ist niemals Write">
    <label>HA-Entities filtern<input type="search" bind:value={query} /></label>
    <div class="entities">{#each filtered as entity (entity.entity_id)}<label class="check"><input type="checkbox" value={entity.entity_id} bind:group={registry.selectedEntities} />{entity.attributes.friendly_name ?? entity.entity_id} · {entity.entity_id}</label>{/each}</div>
    <button onclick={()=>registry.createCandidates()}>Aus Auswahl Kandidaten erzeugen</button>
    {#each registry.candidateQueue as id (id)}<p>{id} <button disabled={registry.busy} onclick={()=>registry.openCandidate(id)}>Rolle und Capability bestätigen</button></p>{/each}
    <p>ConfigEntry-Analyse berücksichtigt nur Einträge mit ausdrücklich passendem Profil. Nicht profilierte Alt-Konfiguration wird nicht automatisch einem Haushalt zugeordnet.</p>
    <button disabled={registry.busy} onclick={()=>registry.migrationCandidates()}>Migrationsvorschläge analysieren</button>
    {#each registry.migrationHints as hint (hint.entity_id)}<article><strong>{hint.entity_id}</strong><span>{hint.shared_candidate?'Kandidat für gemeinsame Registry-Rolle':'Kandidat prüfen'} · {hint.references.map(r=>`${r.integration}: ${r.field}`).join(', ')}</span><button disabled={registry.busy} onclick={()=>registry.openCandidate(hint.entity_id)}>Als Binding-Eingabe prüfen</button></article>{/each}
  </Panel>
{/if}
<style>
  label,article { display:grid; gap:8px; margin:16px 0; } .check { display:flex; align-items:center; margin:4px 0; } .entities { max-height:260px; overflow:auto; } p,span { color:var(--color-text-secondary); } pre { white-space:pre-wrap; overflow-wrap:anywhere; }
  input,textarea,button { min-height:44px; min-width:0; padding:8px 12px; border:1px solid var(--color-border); border-radius:var(--radius-control); color:var(--color-text-primary); background:var(--color-background); font:inherit; } textarea { width:100%; box-sizing:border-box; } button { cursor:pointer; margin:4px; } button:disabled { opacity:.5; cursor:default; } .check input { min-height:24px; width:24px; }
</style>
