<script lang="ts">
  import type { Snippet } from "svelte";
  import type { ConnectionState } from "../../lib/ui/state";
  import type { NavItem } from "./types";
  import Sidebar from "./Sidebar.svelte";
  import TopBar from "./TopBar.svelte";

  let {
    activeView,
    navItems,
    title,
    eyebrow,
    subline,
    search,
    searchLabel,
    searchPlaceholder,
    previewStatus,
    connectionState,
    errorMessage,
    onViewChange,
    onSearch,
    onRefresh,
    scopeLabel,
    scopeHint,
    versionLabel,
    children,
  }: {
    activeView: string;
    navItems: NavItem[];
    title: string;
    eyebrow: string;
    subline: string;
    search: string;
    searchLabel?: string;
    searchPlaceholder?: string;
    previewStatus?: boolean;
    connectionState: ConnectionState;
    errorMessage: string | null;
    onViewChange: (view: string) => void;
    onSearch: (value: string) => void;
    onRefresh: () => void;
    scopeLabel?: string;
    scopeHint?: string;
    versionLabel?: string;
    children?: Snippet;
  } = $props();
</script>

<div class="app-shell">
  <Sidebar {activeView} {navItems} {onViewChange} {scopeLabel} {scopeHint} {versionLabel} />
  <div class="workspace">
    <TopBar
      {title}
      {eyebrow}
      {subline}
      {search}
      {searchLabel}
      {searchPlaceholder}
      connectionState={previewStatus ? "connected" : connectionState}
      status={previewStatus ? "unknown" : connectionState === "connected" ? "healthy" : connectionState}
      statusLabel={previewStatus ? "Preview" : connectionState === "connected" ? "Live verbunden" : connectionState}
      {errorMessage}
      {onSearch}
      {onRefresh}
    />
    <main class="content" tabindex="-1">{@render children?.()}</main>
  </div>
</div>

<style>
  .app-shell { display: flex; min-height: 100vh; background: radial-gradient(circle at top right, var(--color-surface-elevated), transparent 36%), var(--color-background); }
  .workspace { display: flex; flex: 1; min-width: 0; flex-direction: column; }
  .content { width: 100%; max-width: 1540px; margin: 0 auto; padding: 0 var(--space-8) var(--space-12); }
  @media (max-width: 860px) { .content { padding-inline: var(--space-6); } }
  @media (max-width: 560px) { .app-shell { padding-bottom: 68px; } .content { padding-inline: var(--space-4); padding-bottom: var(--space-8); } }
</style>
