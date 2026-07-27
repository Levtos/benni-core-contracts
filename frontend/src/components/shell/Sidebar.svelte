<script lang="ts">
  import { Boxes, ShieldCheck } from "@lucide/svelte";
  import type { NavItem } from "./types";

  let {
    activeView,
    navItems,
    onViewChange,
    scopeLabel = "Read-only",
    scopeHint = "Keine Aktionen",
    versionLabel = "",
  }: {
    activeView: string;
    navItems: NavItem[];
    onViewChange: (view: string) => void;
    scopeLabel?: string;
    scopeHint?: string;
    versionLabel?: string;
  } = $props();
</script>

<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark" aria-hidden="true"><Boxes size={21} strokeWidth={2.2} /></div>
    <div>
      <div class="brand-title">Core Contracts</div>
      <div class="brand-subtitle">read-only foundation</div>
    </div>
  </div>

  <nav aria-label="Core Contracts Navigation">
    <div class="nav-label">Arbeitsbereiche</div>
    {#each navItems as item (item.id)}
      {@const Icon = item.icon}
      <button class:active={activeView === item.id} class="nav-item" type="button" onclick={() => onViewChange(item.id)} aria-current={activeView === item.id ? "page" : undefined}>
        <Icon size={18} strokeWidth={2} />
        <span class="nav-copy"><strong>{item.label}</strong><small>{item.hint}</small></span>
      </button>
    {/each}
  </nav>

  <div class="sidebar-footer">
    <div class="scope-card">
      <ShieldCheck size={17} strokeWidth={2} aria-hidden="true" />
      <div><strong>{scopeLabel}</strong><span>{scopeHint}</span></div>
    </div>
    <div class="version mono">{versionLabel}</div>
  </div>
</aside>

<style>
  .sidebar { display: flex; flex-direction: column; width: 252px; min-height: 100vh; padding: var(--space-6) var(--space-3) var(--space-4); border-right: 1px solid var(--color-border); background: color-mix(in srgb, var(--color-surface) 82%, var(--color-background)); }
  .brand { display: flex; align-items: center; gap: var(--space-3); padding: 0 var(--space-3) var(--space-8); }
  .brand-mark { display: grid; width: 40px; height: 40px; place-items: center; border: 1px solid var(--color-info-border); border-radius: 12px; background: var(--color-info-subtle); color: var(--color-info-foreground); }
  .brand-title { font-size: 0.96rem; font-weight: 750; letter-spacing: -0.02em; }
  .brand-subtitle { margin-top: 3px; color: var(--color-text-muted); font-size: 0.71rem; }
  .nav-label { padding: 0 var(--space-3) var(--space-2); color: var(--color-text-muted); font-size: 0.68rem; font-weight: 750; letter-spacing: 0.12em; text-transform: uppercase; }
  .nav-item { display: flex; align-items: center; width: 100%; min-height: 52px; gap: var(--space-3); margin: 2px 0; padding: var(--space-2) var(--space-3); border: 1px solid transparent; border-radius: var(--radius-control); background: transparent; color: var(--color-text-secondary); text-align: left; transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast); }
  .nav-item:hover { border-color: var(--color-border); background: var(--color-surface-elevated); color: var(--color-text-primary); }
  .nav-item.active { border-color: var(--color-info-border); background: var(--color-info-subtle); color: var(--color-info-foreground); }
  .nav-copy { display: grid; gap: 3px; }
  .nav-copy strong { font-size: 0.82rem; font-weight: 700; }
  .nav-copy small { color: var(--color-text-muted); font-size: 0.68rem; }
  .nav-item.active .nav-copy small { color: var(--color-info); }
  .sidebar-footer { display: grid; gap: var(--space-3); margin-top: auto; padding: var(--space-3); }
  .scope-card { display: flex; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--color-success-border); border-radius: var(--radius-control); background: var(--color-success-subtle); color: var(--color-success-foreground); }
  .scope-card div { display: grid; gap: 3px; }
  .scope-card strong { font-size: 0.72rem; }
  .scope-card span { color: var(--color-text-secondary); font-size: 0.66rem; line-height: 1.35; }
  .version { color: var(--color-text-muted); font-size: 0.64rem; }
  @media (max-width: 860px) { .sidebar { width: 76px; padding-inline: var(--space-2); } .brand { justify-content: center; padding-inline: 0; } .brand > div:last-child, .nav-label, .nav-copy, .scope-card div, .version { display: none; } .nav-item { justify-content: center; padding-inline: 0; } .scope-card { justify-content: center; padding: var(--space-2); } }
  @media (max-width: 560px) { .sidebar { position: fixed; z-index: 10; bottom: 0; left: 0; width: 100%; min-height: auto; height: 68px; flex-direction: row; align-items: center; padding: var(--space-2); border-top: 1px solid var(--color-border); border-right: 0; } .brand, .sidebar-footer { display: none; } nav { display: flex; flex: 1; justify-content: space-around; } .nav-item { width: auto; min-width: 56px; min-height: 52px; } }
</style>
