<script lang="ts">
  import { CircleAlert, CircleCheck, CircleX, Info, LoaderCircle, WifiOff } from "@lucide/svelte";
  import type { ConnectionState, DataState } from "./state";

  let { state, message }: { state: ConnectionState | DataState; message?: string | null } = $props();
  const labels: Record<string, string> = {
    loading: "Daten werden geladen",
    connected: "Live verbunden",
    reconnecting: "Live-Daten werden synchronisiert",
    offline: "Verbindung unterbrochen",
    error: "Fehler beim Lesen",
    unavailable: "Nicht verfügbar",
    ready: "Contract-Daten verfügbar",
    empty: "Noch keine Contracts veröffentlicht",
    stale: "Daten sind möglicherweise veraltet",
    degraded: "Ein Teil der Daten ist degradiert",
    blocked: "Ein Contract ist blockiert",
  };
  const icons = { loading: LoaderCircle, connected: CircleCheck, reconnecting: LoaderCircle, offline: WifiOff, error: CircleX, unavailable: Info, ready: CircleCheck, empty: Info, stale: CircleAlert, degraded: CircleAlert, blocked: CircleX };
  let Icon = $derived(icons[state]);
  let tone = $derived(state === "connected" || state === "ready" ? "healthy" : ["error", "blocked", "offline"].includes(state) ? "danger" : ["degraded", "stale", "reconnecting"].includes(state) ? "warning" : "info");
</script>

<div class={`state-banner ${tone}`} role="status">
  <span class:spin={state === "loading" || state === "reconnecting"} aria-hidden="true">
    <Icon size={17} strokeWidth={2} />
  </span>
  <span>{message || labels[state] || state}</span>
</div>

<style>
  .state-banner { display: flex; align-items: center; gap: var(--space-2); min-height: 40px; padding: 0 var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-control); background: var(--color-surface); color: var(--color-text-secondary); font-size: 0.82rem; }
  .state-banner.healthy { border-color: var(--color-success-border); background: var(--color-success-subtle); color: var(--color-success-foreground); }
  .state-banner.warning { border-color: var(--color-warning-border); background: var(--color-warning-subtle); color: var(--color-warning-foreground); }
  .state-banner.danger { border-color: var(--color-danger-border); background: var(--color-danger-subtle); color: var(--color-danger-foreground); }
  .state-banner.info { border-color: var(--color-info-border); background: var(--color-info-subtle); color: var(--color-info-foreground); }
  .spin { animation: spin 1.2s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
