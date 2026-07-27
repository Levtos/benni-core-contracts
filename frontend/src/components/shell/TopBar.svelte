<script lang="ts">
  import { RefreshCw, Search } from "@lucide/svelte";
  import type { ConnectionState } from "../../lib/ui/state";
  import StatusBadge from "../../lib/ui/StatusBadge.svelte";
  import StateBanner from "../../lib/ui/StateBanner.svelte";
  import IconButton from "../../lib/ui/IconButton.svelte";

  let {
    eyebrow,
    title,
    subline,
    search,
    searchLabel = "Filtern",
    searchPlaceholder = "Filtern …",
    connectionState,
    status,
    statusLabel,
    errorMessage,
    onSearch,
    onRefresh,
  }: {
    eyebrow: string;
    title: string;
    subline: string;
    search: string;
    searchLabel?: string;
    searchPlaceholder?: string;
    connectionState: ConnectionState;
    status: string;
    statusLabel: string;
    errorMessage: string | null;
    onSearch: (value: string) => void;
    onRefresh: () => void;
  } = $props();
</script>

<header class="topbar">
  <div class="heading">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{title}</h1>
    <p>{subline}</p>
  </div>
  <div class="top-actions">
    <div class="search-wrap">
      <Search size={16} strokeWidth={2} aria-hidden="true" />
      <input aria-label={searchLabel} placeholder={searchPlaceholder} value={search} oninput={(event) => onSearch(event.currentTarget.value)} />
      {#if search}<button class="clear-search" type="button" aria-label="Filter löschen" onclick={() => onSearch("")}>×</button>{/if}
    </div>
    <IconButton label="Read-only synchronisieren" icon={RefreshCw} onclick={onRefresh} disabled={connectionState === "loading" || connectionState === "reconnecting"} />
    <StatusBadge {status} label={statusLabel} />
  </div>
</header>

{#if errorMessage}
  <div class="top-error"><StateBanner state={connectionState} message={errorMessage} /></div>
{/if}

<style>
  .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-6); padding: var(--space-8) var(--space-8) var(--space-4); }
  .heading h1 { margin: var(--space-1) 0 0; font-size: clamp(1.35rem, 2vw, 1.8rem); letter-spacing: -0.04em; }
  .heading p { margin: var(--space-2) 0 0; color: var(--color-text-muted); font-size: 0.8rem; }
  .top-actions { display: flex; align-items: center; justify-content: flex-end; gap: var(--space-2); padding-top: var(--space-2); }
  .search-wrap { display: flex; align-items: center; gap: var(--space-2); width: min(260px, 32vw); min-height: 44px; padding: 0 var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface); color: var(--color-text-muted); }
  .search-wrap input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--color-text-primary); font-size: 0.78rem; }
  .search-wrap input::placeholder { color: var(--color-text-muted); }
  .clear-search { border: 0; background: transparent; color: var(--color-text-muted); font-size: 1.1rem; line-height: 1; }
  .top-error { padding: 0 var(--space-8) var(--space-4); }
  @media (max-width: 860px) { .topbar { padding: var(--space-6) var(--space-6) var(--space-4); } .topbar { flex-direction: column; } .top-actions { width: 100%; justify-content: flex-start; } .search-wrap { width: min(340px, 100%); } .top-error { padding-inline: var(--space-6); } }
  @media (max-width: 560px) { .topbar { padding: var(--space-4) var(--space-4) var(--space-3); } .top-actions { flex-wrap: wrap; } .search-wrap { order: 3; width: 100%; } .top-error { padding-inline: var(--space-4); } }
</style>
