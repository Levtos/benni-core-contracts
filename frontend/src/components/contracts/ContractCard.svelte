<script lang="ts">
  import { ArrowUpRight, CircleDot } from "@lucide/svelte";
  import type { Contract } from "../../lib/core-contracts/types";
  import { labelForSchema } from "../../lib/core-contracts/format";
  import StatusBadge from "../../lib/ui/StatusBadge.svelte";

  let { contract, selected = false, onclick }: { contract: Contract; selected?: boolean; onclick?: () => void } = $props();
  let fields = $derived(Object.keys(contract.field_quality));
  let healthyFields = $derived(fields.filter((field) => contract.field_quality[field]?.health === "healthy").length);
</script>

<button class:selected type="button" class="contract-card" onclick={onclick} aria-pressed={selected}>
  <div class="card-topline"><span class="eyebrow">{labelForSchema(contract.schema_id)} · v{contract.schema_version}</span><ArrowUpRight size={17} strokeWidth={2} aria-hidden="true" /></div>
  <div class="card-title"><strong>{contract.contract_id}</strong><StatusBadge status={contract.health} /></div>
  <div class="field-summary"><CircleDot size={14} strokeWidth={2} aria-hidden="true" /><span>{healthyFields} von {fields.length} Feldern gesund</span><span class="mono revision">{contract.generated_at.slice(11, 19)}Z</span></div>
  <div class="field-meter" aria-label={`${healthyFields} von ${fields.length} Feldern gesund`}><span style={`width: ${fields.length ? (healthyFields / fields.length) * 100 : 0}%`}></span></div>
</button>

<style>
  .contract-card { display: grid; gap: var(--space-3); width: 100%; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface); color: var(--color-text-primary); text-align: left; transition: border-color var(--transition-fast), background var(--transition-fast), transform var(--transition-fast); }
  .contract-card:hover { border-color: var(--color-info-border); background: var(--color-surface-elevated); transform: translateY(-1px); }
  .contract-card.selected { border-color: var(--color-info); background: var(--color-info-subtle); }
  .card-topline, .card-title, .field-summary { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
  .card-topline { color: var(--color-text-muted); }
  .card-title strong { overflow: hidden; text-overflow: ellipsis; font-size: 0.96rem; }
  .field-summary { justify-content: flex-start; color: var(--color-text-secondary); font-size: 0.74rem; }
  .revision { margin-left: auto; color: var(--color-text-muted); font-size: 0.66rem; }
  .field-meter { height: 4px; overflow: hidden; border-radius: 999px; background: var(--color-border); }
  .field-meter span { display: block; height: 100%; border-radius: inherit; background: var(--color-success); transition: width var(--transition-fast); }
</style>
