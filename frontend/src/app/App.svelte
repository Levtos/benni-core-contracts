<script lang="ts">
  import { onMount } from "svelte";
  import { Activity, GitBranch, LayoutDashboard, Stethoscope } from "@lucide/svelte";
  import AppShell from "../components/shell/AppShell.svelte";
  import DiagnosticsView from "../components/views/DiagnosticsView.svelte";
  import GraphView from "../components/views/GraphView.svelte";
  import HealthView from "../components/views/HealthView.svelte";
  import OverviewView from "../components/views/OverviewView.svelte";
  import type { CoreContractsStore } from "../lib/core-contracts/store.svelte";
  import type { AppView } from "../lib/core-contracts/store.svelte";
  import type { NavItem } from "../components/shell/types";

  let { store }: { store: CoreContractsStore } = $props();
  const navItems: NavItem[] = [
    { id: "overview", label: "Übersicht", hint: "Contracts", icon: LayoutDashboard },
    { id: "diagnostics", label: "Diagnose", hint: "Felder & Quellen", icon: Stethoscope },
    { id: "graph", label: "Signalgraph", hint: "Bindings & Fusion", icon: GitBranch },
    { id: "health", label: "Health", hint: "Revision & Status", icon: Activity },
  ];
  const titles: Record<AppView, string> = {
    overview: "Contract-Übersicht",
    diagnostics: "Feldbezogene Diagnose",
    graph: "Interner Signalgraph",
    health: "Health & Reconciliation",
  };
  let title = $derived(titles[store.activeView]);
  let subline = $derived(store.previewMode ? "Lokale Vorschau · nicht live" : "Benni · Shadow-only · read-only");

  onMount(() => {
    const previewRequested = import.meta.env.DEV && new URLSearchParams(window.location.search).get("preview") === "fixture";
    if (previewRequested) store.usePreview();
    else store.start();
    return () => store.stop();
  });
</script>

<AppShell
  activeView={store.activeView}
  {navItems}
  {title}
  eyebrow="Core Contracts / Benni"
  {subline}
  search={store.search}
  searchLabel="Contracts filtern"
  searchPlaceholder="Contracts filtern …"
  previewStatus={store.previewMode}
  connectionState={store.connectionState}
  errorMessage={store.errorMessage}
  onViewChange={(view) => store.setView(view as AppView)}
  onSearch={(value) => store.setSearch(value)}
  onRefresh={() => void store.refresh()}
  scopeLabel="Shadow-only"
  scopeHint="Keine Entities · keine Aktionen"
  versionLabel="contract payload v1"
>
  {#snippet children()}
    {#if store.activeView === "overview"}<OverviewView {store} />{:else if store.activeView === "diagnostics"}<DiagnosticsView {store} />{:else if store.activeView === "graph"}<GraphView {store} />{:else}<HealthView {store} />{/if}
  {/snippet}
</AppShell>
