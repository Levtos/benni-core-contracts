<script lang="ts">
  import { CheckCircle2, CircleAlert, CircleX, Clock3, GitCompareArrows, ShieldCheck } from "@lucide/svelte";
  import type { CoreContractsStore } from "../../lib/core-contracts/store.svelte";
  import Panel from "../../lib/ui/Panel.svelte";
  import StatusBadge from "../../lib/ui/StatusBadge.svelte";
  import StateBanner from "../../lib/ui/StateBanner.svelte";
  import EmptyState from "../../lib/ui/EmptyState.svelte";
  import { formatDateTime, labelForSchema } from "../../lib/core-contracts/format";

  let { store }: { store: CoreContractsStore } = $props();
  let healthy = $derived(store.health.filter((item) => item.health === "healthy").length);
  let degraded = $derived(store.health.filter((item) => item.health === "degraded").length);
  let blocked = $derived(store.health.filter((item) => item.health === "blocked").length);
</script>

<div class="view">
  <div class="view-intro"><p>Health ist eine zusammengefasste Orientierung. Die fachliche Bewertung bleibt bei den einzelnen Feld-Quality-/Freshness-/Safety-Werten.</p><StateBanner state={store.connectionState} /></div>
  <div class="health-summary"><div class="summary healthy"><CheckCircle2 size={18} strokeWidth={2} aria-hidden="true" /><span>Healthy</span><strong>{healthy}</strong></div><div class="summary warning"><CircleAlert size={18} strokeWidth={2} aria-hidden="true" /><span>Degradiert</span><strong>{degraded}</strong></div><div class="summary danger"><CircleX size={18} strokeWidth={2} aria-hidden="true" /><span>Blockiert</span><strong>{blocked}</strong></div><div class="summary info"><GitCompareArrows size={18} strokeWidth={2} aria-hidden="true" /><span>Revision</span><strong>{store.revision || "—"}</strong></div></div>
  <Panel eyebrow="Reconciliation" title="Contract Health">
    {#if !store.health.length}<EmptyState title="Kein Health-Snapshot" message="Es liegt noch kein read-only Health-Payload vor." />{:else}<div class="health-list">{#each store.health as item (item.contract_id)}<button class="health-row" type="button" onclick={() => store.selectContract(item.contract_id)}><div class="health-name"><ShieldCheck size={16} strokeWidth={2} aria-hidden="true" /><div><strong>{item.contract_id}</strong><small>{labelForSchema(item.schema_id)}</small></div></div><StatusBadge status={item.health} /><span class="go">Details öffnen</span></button>{/each}</div>{/if}
  </Panel>
  <div class="health-foot"><Clock3 size={15} strokeWidth={2} aria-hidden="true" /><span>Letzte erfolgreiche Abfrage: {formatDateTime(store.lastUpdated)} · zyklische read-only Synchronisation, kein Command-Kanal.</span></div>
</div>

<style>
  .view { display: grid; gap: var(--space-6); }
  .view-intro { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); } .view-intro p { margin: 0; max-width: 780px; color: var(--color-text-secondary); font-size: 0.84rem; line-height: 1.55; }
  .health-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); }
  .summary { display: grid; grid-template-columns: auto 1fr; gap: var(--space-2); align-items: center; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-card); background: var(--color-surface); } .summary span { color: var(--color-text-secondary); font-size: 0.72rem; } .summary strong { grid-column: 2; font-size: 1.25rem; } .summary.healthy { color: var(--color-success); border-color: var(--color-success-border); background: var(--color-success-subtle); } .summary.warning { color: var(--color-warning); border-color: var(--color-warning-border); background: var(--color-warning-subtle); } .summary.danger { color: var(--color-danger); border-color: var(--color-danger-border); background: var(--color-danger-subtle); } .summary.info { color: var(--color-info); border-color: var(--color-info-border); background: var(--color-info-subtle); }
  .health-list { display: grid; gap: var(--space-2); }
  .health-row { display: flex; align-items: center; gap: var(--space-3); width: 100%; min-height: 60px; padding: var(--space-3) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-background); color: var(--color-text-primary); text-align: left; transition: border-color var(--transition-fast), background var(--transition-fast); } .health-row:hover { border-color: var(--color-info-border); background: var(--color-info-subtle); }
  .health-name { display: flex; align-items: center; gap: var(--space-2); min-width: 0; flex: 1; color: var(--color-info); } .health-name div { display: grid; gap: 3px; min-width: 0; } .health-name strong { overflow: hidden; color: var(--color-text-primary); font-size: 0.8rem; text-overflow: ellipsis; white-space: nowrap; } .health-name small { color: var(--color-text-muted); font-size: 0.68rem; }
  .go { color: var(--color-text-muted); font-size: 0.68rem; } .health-foot { display: flex; align-items: center; gap: var(--space-2); color: var(--color-text-muted); font-size: 0.7rem; }
  @media (max-width: 800px) { .health-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } } @media (max-width: 560px) { .view-intro { align-items: flex-start; flex-direction: column; } .health-row { align-items: flex-start; flex-wrap: wrap; } .go { width: 100%; padding-left: 28px; } }
</style>
