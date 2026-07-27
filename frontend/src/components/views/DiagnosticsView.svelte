<script lang="ts">
  import { Clock3, Database, GitBranch, ShieldAlert, Users } from "@lucide/svelte";
  import type { CoreContractsStore } from "../../lib/core-contracts/store.svelte";
  import Panel from "../../lib/ui/Panel.svelte";
  import StatusBadge from "../../lib/ui/StatusBadge.svelte";
  import EmptyState from "../../lib/ui/EmptyState.svelte";
  import { formatDateTime, formatDuration, labelForSchema } from "../../lib/core-contracts/format";

  let { store }: { store: CoreContractsStore } = $props();
</script>

<div class="view">
  <div class="view-intro"><p>Jedes Feld behält seine eigene Qualität. Ein globaler Contract-Status ersetzt keine brauchbare Teilinformation.</p><StatusBadge status="info" label="Feldbezogene Evidence" /></div>
  {#if !store.diagnostics.length}
    <EmptyState title="Keine Diagnoseprojektionen" message="Die read-only Runtime hat noch keine Contract-Diagnosen geliefert." />
  {:else}
    <div class="diagnostic-grid">
      {#each store.diagnostics as diagnostic (diagnostic.projection_id)}
        <Panel eyebrow={labelForSchema(diagnostic.schema_id)} title={diagnostic.contract_id}>
          <div class="diagnostic-head"><StatusBadge status={diagnostic.health} /><span class="muted">Stand {formatDateTime(diagnostic.generated_at)}</span></div>
          <div class="diagnostic-fields">
            {#each diagnostic.fields as field (field.field)}
              <article class="diagnostic-field">
                <div class="field-title"><strong>{field.field}</strong><div class="badges"><StatusBadge status={field.health} /><StatusBadge status={field.freshness} /></div></div>
                <div class="field-facts">
                  <span><Database size={14} strokeWidth={2} aria-hidden="true" />{field.active_source_entities.join(", ") || "keine aktive Quelle"}</span>
                  <span><GitBranch size={14} strokeWidth={2} aria-hidden="true" />{field.completeness ? "vollständige Evidence" : "Evidence unvollständig"}</span>
                  <span><Users size={14} strokeWidth={2} aria-hidden="true" />{field.consumer_effect}</span>
                </div>
                {#if field.root_causes.length}
                  <div class="causes">
                    {#each field.root_causes as cause (cause.code)}
                      <div class="cause"><ShieldAlert size={14} strokeWidth={2} aria-hidden="true" /><div><strong>{cause.code}</strong><p>{cause.message}</p><small><Clock3 size={12} strokeWidth={2} aria-hidden="true" />seit {formatDateTime(cause.since)} · {formatDuration(cause.duration_seconds)}</small></div></div>
                    {/each}
                  </div>
                {:else}
                  <div class="clear-cause"><span class="dot"></span>Keine Root Cause gemeldet</div>
                {/if}
              </article>
            {/each}
          </div>
        </Panel>
      {/each}
    </div>
  {/if}
</div>

<style>
  .view { display: grid; gap: var(--space-6); }
  .view-intro { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
  .view-intro p { margin: 0; max-width: 760px; color: var(--color-text-secondary); font-size: 0.84rem; line-height: 1.55; }
  .diagnostic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-6); align-items: start; }
  .diagnostic-head, .field-title { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
  .diagnostic-head { margin-bottom: var(--space-4); font-size: 0.7rem; }
  .diagnostic-fields { display: grid; gap: var(--space-2); }
  .diagnostic-field { display: grid; gap: var(--space-3); padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-background); }
  .field-title strong { font-size: 0.84rem; }
  .badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-1); }
  .field-facts { display: grid; gap: var(--space-2); color: var(--color-text-secondary); font-size: 0.7rem; }
  .field-facts span, .cause small, .cause { display: flex; align-items: flex-start; gap: var(--space-2); }
  .field-facts :global(svg), .cause > :global(svg) { flex: 0 0 auto; color: var(--color-info); }
  .causes { display: grid; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
  .cause { color: var(--color-warning-foreground); font-size: 0.72rem; }
  .cause strong { color: var(--color-warning); font-size: 0.7rem; }
  .cause p { margin: var(--space-1) 0; color: var(--color-text-secondary); line-height: 1.4; }
  .cause small { align-items: center; color: var(--color-text-muted); font-size: 0.66rem; }
  .cause small :global(svg) { color: var(--color-text-muted); }
  .clear-cause { display: flex; align-items: center; gap: var(--space-2); padding-top: var(--space-2); color: var(--color-success-foreground); font-size: 0.72rem; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-success); }
  @media (max-width: 1000px) { .diagnostic-grid { grid-template-columns: 1fr; } }
  @media (max-width: 560px) { .view-intro { align-items: flex-start; flex-direction: column; } .field-title { align-items: flex-start; flex-direction: column; } .badges { justify-content: flex-start; } }
</style>
