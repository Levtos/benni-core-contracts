<script lang="ts">
  import { Tooltip } from "bits-ui";
  import type { Component } from "svelte";

  let {
    label,
    icon: Icon,
    onclick,
    disabled = false,
  }: {
    label: string;
    icon: Component<{ size?: number; strokeWidth?: number }>;
    onclick?: () => void;
    disabled?: boolean;
  } = $props();
</script>

<Tooltip.Provider>
  <Tooltip.Root>
    <Tooltip.Trigger class="icon-button" {disabled} aria-label={label} {onclick}>
      <Icon size={18} strokeWidth={2} />
    </Tooltip.Trigger>
    <Tooltip.Content class="tooltip" side="bottom">{label}</Tooltip.Content>
  </Tooltip.Root>
</Tooltip.Provider>

<style>
  :global(.icon-button) { display: inline-grid; min-width: 44px; min-height: 44px; place-items: center; border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface-elevated); color: var(--color-text-secondary); transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast); }
  :global(.icon-button:hover:not(:disabled)) { border-color: var(--color-info-border); background: var(--color-info-hover); color: var(--color-info-foreground); }
  :global(.icon-button:disabled) { cursor: not-allowed; color: var(--color-text-muted); opacity: 0.55; }
  :global(.tooltip) { z-index: 20; padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface-elevated); color: var(--color-text-primary); box-shadow: var(--shadow-panel); font-size: 0.75rem; }
</style>
