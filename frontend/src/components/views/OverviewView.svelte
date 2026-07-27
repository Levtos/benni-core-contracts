<script lang="ts">
  import { Activity, AlertTriangle, Boxes, Database } from "@lucide/svelte";
  import type { CoreContractsStore } from "../../lib/core-contracts/store.svelte";
  import ContractCard from "../contracts/ContractCard.svelte";
  import ContractDetail from "../contracts/ContractDetail.svelte";
  import Panel from "../../lib/ui/Panel.svelte";
  import StateBanner from "../../lib/ui/StateBanner.svelte";
  import EmptyState from "../../lib/ui/EmptyState.svelte";

  let { store }: { store: CoreContractsStore } = $props();
  let selected = $derived(store.selectedContract);
  let selectedDiagnostic = $derived(store.selectedDiagnostics);
  let degradedCount = $derived(store.contracts.filter((item) => item.health === "degraded").length);
  let blockedCount = $derived(store.contracts.filter((item) => item.health === "blocked").length);
</script>

<div class="view">
  <div class="view-intro">
    <div><p>Stabile, versionierte Signale aus dem internen Graphen — ohne Entitäten und ohne Aktionspfad.</p></div>
    <StateBanner state={store.dataState} />
  </div>

  {#if store.previewMode}<div class="preview-note"><AlertTriangle size={16} strokeWidth={2} aria-hidden="true" /><span>Lokale Vorschau-Daten zur UI-Prüfung. In Home Assistant werden ausschließlich reale WebSocket-Contracts angezeigt.</span></div>{/if}

  <div class="metrics">
    <div class="metric-card"><div class="metric-icon info"><Boxes size={18} strokeWidth={2} aria-hidden="true" /></div><div><span>Contracts</span><strong>{store.contracts.length}</strong></div><small>interne Ergebnisse</small></div>
    <div class="metric-card"><div class="metric-icon success"><Activity size={18} strokeWidth={2} aria-hidden="true" /></div><div><span>Revision</span><strong>{store.revision || "—"}</strong></div><small>Delta-Reconciliation</small></div>
    <div class="metric-card"><div class="metric-icon warning"><AlertTriangle size={18} strokeWidth={2} aria-hidden="true" /></div><div><span>Degradiert</span><strong>{degradedCount}</strong></div><small>Felder bleiben sichtbar</small></div>
    <div class="metric-card"><div class="metric-icon danger"><Database size={18} strokeWidth={2} aria-hidden="true" /></div><div><span>Blockiert</span><strong>{blockedCount}</strong></div><small>keine positive Aussage</small></div>
  </div>

  {#if !store.contracts.length}
    <EmptyState title="Noch keine Core Contracts" message="Die read-only Verbindung steht, aber der aktuelle Runtime-Graph liefert keine veröffentlichten Contracts. Das ist kein ersetzter oder erfundener Zustand." />
  {:else}
    <div class="content-grid">
      <Panel eyebrow="Live-Snapshot" title="Contracts">
        <div class="card-list">
          {#each store.filteredContracts as contract (contract.contract_id)}
            <ContractCard {contract} selected={store.selectedContractId === contract.contract_id} onclick={() => store.selectContract(contract.contract_id)} />
          {:else}
            <div class="filtered-empty">Kein Contract passt zum aktuellen Filter.</div>
          {/each}
        </div>
      </Panel>
      <Panel eyebrow="Feld-Contract" title="Detail">
        {#if selected}<ContractDetail contract={selected} diagnostic={selectedDiagnostic} />{:else}<EmptyState title="Contract auswählen" message="Wähle links einen Contract für die feldbezogene Darstellung." />{/if}
      </Panel>
    </div>
  {/if}
</div>

<style>
  .view { display: grid; gap: var(--space-6); }
  .view-intro { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
  .view-intro p { margin: 0; max-width: 720px; color: var(--color-text-secondary); font-size: 0.84rem; line-height: 1.55; }
  .preview-note { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-3) var(--space-4); border: 1px solid var(--color-warning-border); border-radius: var(--radius-control); background: var(--color-warning-subtle); color: var(--color-warning-foreground); font-size: 0.76rem; line-height: 1.45; }
  .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); }
  .metric-card { display: grid; grid-template-columns: auto 1fr; gap: var(--space-3); padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-card); background: var(--color-surface); }
  .metric-card > div:nth-child(2) { display: grid; gap: 2px; }
  .metric-card span { color: var(--color-text-muted); font-size: 0.68rem; }
  .metric-card strong { font-size: 1.35rem; letter-spacing: -0.04em; }
  .metric-card small { grid-column: 1 / -1; color: var(--color-text-muted); font-size: 0.68rem; }
  .metric-icon { display: grid; width: 36px; height: 36px; place-items: center; border-radius: var(--radius-control); }
  .metric-icon.info { background: var(--color-info-subtle); color: var(--color-info); } .metric-icon.success { background: var(--color-success-subtle); color: var(--color-success); } .metric-icon.warning { background: var(--color-warning-subtle); color: var(--color-warning); } .metric-icon.danger { background: var(--color-danger-subtle); color: var(--color-danger); }
  .content-grid { display: grid; grid-template-columns: minmax(280px, 0.78fr) minmax(0, 1.4fr); gap: var(--space-6); align-items: start; }
  .card-list { display: grid; gap: var(--space-2); }
  .filtered-empty { padding: var(--space-6); color: var(--color-text-muted); font-size: 0.8rem; text-align: center; }
  @media (max-width: 1100px) { .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .content-grid { grid-template-columns: 1fr; } }
  @media (max-width: 560px) { .view-intro { align-items: stretch; flex-direction: column; } .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .metric-card { padding: var(--space-3); } }
</style>
