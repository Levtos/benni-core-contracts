<script lang="ts">
  import { Boxes } from "@lucide/svelte";
  let { title, message }: { title: string; message: string } = $props();
</script>

<div class="empty-state">
  <div class="empty-icon"><Boxes size={22} strokeWidth={1.8} aria-hidden="true" /></div>
  <h3>{title}</h3>
  <p>{message}</p>
</div>

<style>
  .empty-icon { display: grid; width: 48px; height: 48px; place-items: center; border: 1px solid var(--color-border); border-radius: 12px; background: var(--color-surface-elevated); color: var(--color-text-muted); }
</style>
