<script lang="ts">
  import { ArrowRight, Boxes, GitBranch, Radio, Workflow } from "@lucide/svelte";
  import type { CoreContractsStore } from "../../lib/core-contracts/store.svelte";
  import Panel from "../../lib/ui/Panel.svelte";
  import EmptyState from "../../lib/ui/EmptyState.svelte";
  import StatusBadge from "../../lib/ui/StatusBadge.svelte";
  import { labelForSchema, labelForStrategy } from "../../lib/core-contracts/format";

  let { store }: { store: CoreContractsStore } = $props();
  let graph = $derived(store.graph);
</script>

<div class="view">
  <div class="view-intro"><p>Der Graph zeigt die read-only Signalrichtung: SourceBinding → AtomicSignal → Fusion → Contract. Policy- und Apply-Layer sind bewusst nicht Teil dieses Bildes.</p><StatusBadge status="info" label={`Revision ${store.revision || "—"}`} /></div>
  {#if !graph}
    <EmptyState title="Kein Graph-Snapshot" message="Der aktuelle WebSocket-Runtime-Stand liefert noch keinen Graph-Snapshot." />
  {:else}
    <div class="graph-metrics"><div><span>Bindings</span><strong>{graph.bindings.length}</strong></div><div><span>Signals</span><strong>{graph.signals.length}</strong></div><div><span>Fusions</span><strong>{graph.fusions.length}</strong></div><div><span>Contracts</span><strong>{graph.contracts.length}</strong></div></div>
    <Panel eyebrow="Signalfluss" title="Internes Modell">
      <div class="flow-head"><div><Radio size={16} strokeWidth={2} aria-hidden="true" /><span>Raw Source</span></div><ArrowRight size={16} strokeWidth={2} aria-hidden="true" /><div><Workflow size={16} strokeWidth={2} aria-hidden="true" /><span>Fusion</span></div><ArrowRight size={16} strokeWidth={2} aria-hidden="true" /><div><Boxes size={16} strokeWidth={2} aria-hidden="true" /><span>Contract</span></div></div>
      <div class="graph-columns">
        <section><div class="column-title">Source Bindings <span>{graph.bindings.length}</span></div>{#each graph.bindings as binding (binding.binding_id)}<article class="node"><div class="node-title"><strong>{binding.field}</strong><StatusBadge status={binding.read_only ? "healthy" : "danger"} label={binding.read_only ? "read-only" : "prüfen"} /></div><span class="mono">{binding.entity_id}</span><small>{binding.capability} · {binding.profile_id}</small></article>{:else}<div class="column-empty">Keine Bindings</div>{/each}</section>
        <section><div class="column-title">Fusion <span>{graph.fusions.length}</span></div>{#each graph.fusions as fusion (fusion.fusion_id)}<article class="node fusion"><div class="node-title"><strong>{fusion.field}</strong><span class="mono">{labelForStrategy(fusion.strategy)}</span></div><span class="mono">{fusion.fusion_id}</span><small>{fusion.input_binding_ids.length} Input-Binding(s)</small></article>{:else}<div class="column-empty">Keine Fusionen</div>{/each}</section>
        <section><div class="column-title">Published Contract <span>{graph.contracts.length}</span></div>{#each graph.contracts as contract (contract.contract_id)}<button class="node contract" type="button" onclick={() => store.selectContract(contract.contract_id)}><div class="node-title"><strong>{contract.contract_id}</strong><StatusBadge status={contract.health} /></div><span>{labelForSchema(contract.schema_id)} · v{contract.schema_version}</span><small>intern · nicht als Entity projiziert</small></button>{:else}<div class="column-empty">Keine Contracts</div>{/each}</section>
      </div>
    </Panel>
  {/if}
</div>

<style>
  .view { display: grid; gap: var(--space-6); }
  .view-intro { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
  .view-intro p { margin: 0; max-width: 780px; color: var(--color-text-secondary); font-size: 0.84rem; line-height: 1.55; }
  .graph-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); }
  .graph-metrics > div { display: grid; gap: var(--space-1); padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-card); background: var(--color-surface); }
  .graph-metrics span { color: var(--color-text-muted); font-size: 0.68rem; } .graph-metrics strong { font-size: 1.35rem; }
  .flow-head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-6); color: var(--color-text-muted); font-size: 0.72rem; }
  .flow-head div { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface-elevated); color: var(--color-text-secondary); }
  .graph-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }
  .graph-columns section { display: grid; align-content: start; gap: var(--space-2); min-width: 0; }
  .column-title { display: flex; align-items: center; justify-content: space-between; padding-bottom: var(--space-2); border-bottom: 1px solid var(--color-border); color: var(--color-text-secondary); font-size: 0.76rem; font-weight: 700; }
  .column-title span { color: var(--color-text-muted); font-size: 0.68rem; }
  .node { display: grid; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-background); color: var(--color-text-secondary); text-align: left; }
  button.node { width: 100%; transition: border-color var(--transition-fast), background var(--transition-fast); } button.node:hover { border-color: var(--color-info-border); background: var(--color-info-subtle); }
  .node.fusion { border-color: var(--color-automation-border); } .node.contract { border-color: var(--color-success-border); }
  .node-title { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); } .node-title strong { overflow: hidden; color: var(--color-text-primary); font-size: 0.76rem; text-overflow: ellipsis; white-space: nowrap; }
  .node > span { overflow: hidden; color: var(--color-text-secondary); font-size: 0.68rem; text-overflow: ellipsis; white-space: nowrap; } .node small { color: var(--color-text-muted); font-size: 0.65rem; }
  .column-empty { padding: var(--space-4); color: var(--color-text-muted); font-size: 0.72rem; }
  @media (max-width: 900px) { .graph-columns { grid-template-columns: 1fr; } }
  @media (max-width: 560px) { .view-intro { align-items: flex-start; flex-direction: column; } .graph-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .flow-head { flex-wrap: wrap; } .flow-head > :global(svg) { display: none; } }
</style>
