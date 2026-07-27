<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    title,
    eyebrow,
    class: className = "",
    children,
  }: {
    title?: string;
    eyebrow?: string;
    class?: string;
    children?: Snippet;
  } = $props();
</script>

<section class={`surface-card panel ${className}`}>
  {#if title || eyebrow}
    <header class="panel-header">
      <div>
        {#if eyebrow}<div class="eyebrow">{eyebrow}</div>{/if}
        {#if title}<h2>{title}</h2>{/if}
      </div>
    </header>
  {/if}
  <div class="panel-body">{@render children?.()}</div>
</section>

<style>
  .panel { overflow: hidden; }
  .panel-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); padding: var(--space-4) var(--space-6) 0; }
  .panel-header h2 { margin: var(--space-1) 0 0; font-size: 1rem; letter-spacing: -0.01em; }
  .panel-body { padding: var(--space-6); }
</style>
