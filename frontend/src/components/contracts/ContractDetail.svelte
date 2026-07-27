<script lang="ts">
  import { Database, Eye, GitCommitHorizontal, ShieldAlert } from "@lucide/svelte";
  import type { Contract, DiagnosticProjection } from "../../lib/core-contracts/types";
  import { formatDateTime, formatValue, labelForSchema, labelForStrategy } from "../../lib/core-contracts/format";
  import StatusBadge from "../../lib/ui/StatusBadge.svelte";

  let { contract, diagnostic }: { contract: Contract; diagnostic: DiagnosticProjection | null } = $props();
  let fields = $derived(Object.keys(contract.field_quality));
  let fieldDiagnostic = (field: string) => diagnostic?.fields.find((item) => item.field === field) ?? null;
</script>

<div class="detail">
  <div class="detail-head">
    <div>
      <div class="eyebrow">{labelForSchema(contract.schema_id)} · Schema v{contract.schema_version}</div>
      <h2>{contract.contract_id}</h2>
      <p class="muted">Generiert {formatDateTime(contract.generated_at)} · Contract bleibt intern und read-only.</p>
    </div>
    <StatusBadge status={contract.health} />
  </div>

  <div class="detail-meta">
    <div><span class="meta-label">Contract-ID</span><span class="mono">{contract.contract_id}</span></div>
    <div><span class="meta-label">Schema</span><span class="mono">{contract.schema_id}.v{contract.schema_version}</span></div>
    <div><span class="meta-label">Felder</span><span>{fields.length}</span></div>
  </div>

  <div class="field-list">
    {#each fields as field (field)}
      {@const quality = contract.field_quality[field]}
      {@const evaluation = contract.field_evaluations[field]}
      {@const diag = fieldDiagnostic(field)}
      <article class="field-row">
        <div class="field-main">
          <div class="field-name"><strong>{field}</strong>{#if evaluation?.strategy}<span class="strategy mono">{labelForStrategy(evaluation.strategy)}</span>{/if}</div>
          <div class="field-value mono">{formatValue(contract.values[field])}</div>
        </div>
        <div class="field-statuses"><StatusBadge status={quality.health} /><StatusBadge status={quality.freshness} /><StatusBadge status={quality.safety} /></div>
        <div class="field-context">
          <span><Database size={14} strokeWidth={2} aria-hidden="true" />{diag?.active_source_entities?.join(", ") || "keine aktive Quelle"}</span>
          <span><GitCommitHorizontal size={14} strokeWidth={2} aria-hidden="true" />{quality.fallback === "none" ? "Kein Fallback aktiv" : `Fallback: ${quality.fallback}`}</span>
          <span><Eye size={14} strokeWidth={2} aria-hidden="true" />{diag?.consumer_effect || "field quality only"}</span>
        </div>
        {#if quality.reasons.length}
          <div class="reason"><ShieldAlert size={14} strokeWidth={2} aria-hidden="true" /><span>{quality.reasons[0].message}</span></div>
        {/if}
      </article>
    {/each}
  </div>
</div>

<style>
  .detail { display: grid; gap: var(--space-6); }
  .detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); }
  .detail-head h2 { margin: var(--space-1) 0 var(--space-2); font-size: 1.25rem; letter-spacing: -0.03em; }
  .detail-head p { margin: 0; font-size: 0.75rem; }
  .detail-meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface-elevated); }
  .detail-meta div { display: grid; gap: var(--space-1); min-width: 0; color: var(--color-text-primary); font-size: 0.76rem; }
  .meta-label { color: var(--color-text-muted); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.08em; }
  .field-list { display: grid; gap: var(--space-2); }
  .field-row { display: grid; gap: var(--space-3); padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-background); }
  .field-main { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .field-name { display: flex; align-items: center; gap: var(--space-2); }
  .field-name strong { font-size: 0.84rem; }
  .strategy { color: var(--color-text-muted); font-size: 0.62rem; }
  .field-value { color: var(--color-text-primary); font-size: 0.82rem; }
  .field-statuses { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .field-context { display: grid; gap: var(--space-2); color: var(--color-text-secondary); font-size: 0.72rem; }
  .field-context span, .reason { display: flex; align-items: center; gap: var(--space-2); min-width: 0; }
  .field-context span :global(svg), .reason :global(svg) { flex: 0 0 auto; color: var(--color-info); }
  .reason { padding-top: var(--space-2); border-top: 1px solid var(--color-border); color: var(--color-warning-foreground); font-size: 0.72rem; }
  @media (max-width: 560px) { .detail-head { flex-direction: column; } .detail-meta { grid-template-columns: 1fr; } .field-main { align-items: flex-start; flex-direction: column; } }
</style>
