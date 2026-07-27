<script lang="ts">
  import { CheckCircle2, CircleAlert, CircleX, HelpCircle, ShieldAlert } from "@lucide/svelte";

  type Status = string;
  type Tone = "healthy" | "warning" | "danger" | "info" | "active" | "neutral";

  let { status, label = status }: { status: Status; label?: string } = $props();

  const statusLabel: Record<string, string> = {
    healthy: "Gesund",
    degraded: "Degradiert",
    blocked: "Blockiert",
    unknown: "Unbekannt",
    fresh: "Frisch",
    stale: "Veraltet",
    suspect: "Verdächtig",
    restored: "Restore",
    valid: "Gültig",
    conservative: "Konservativ",
    unsafe: "Unsicher",
    unavailable: "Nicht verfügbar",
    invalid: "Ungültig",
    good: "Gut",
    conflict: "Konflikt",
    none: "Kein Fallback",
    reject: "Reject",
    hold_last: "Hold last",
    safe_default: "Safe default",
  };
  const toneMap: Record<string, Tone> = {
    healthy: "healthy", good: "healthy", fresh: "healthy", valid: "healthy",
    degraded: "warning", suspect: "warning", stale: "warning", conservative: "warning",
    blocked: "danger", unsafe: "danger", conflict: "danger", invalid: "danger",
    unavailable: "info", unknown: "neutral", restored: "neutral", none: "neutral",
    reject: "danger", hold_last: "warning", safe_default: "warning",
  };
  const iconMap = { healthy: CheckCircle2, warning: CircleAlert, danger: CircleX, info: ShieldAlert, active: CheckCircle2, neutral: HelpCircle };
  let tone = $derived(toneMap[String(status)] ?? "neutral");
  let Icon = $derived(iconMap[tone]);
  let text = $derived(label === status ? (statusLabel[String(status)] ?? String(status)) : label);
</script>

<span class={`status-badge ${tone}`}>
  <Icon size={14} strokeWidth={2.2} aria-hidden="true" />
  <span>{text}</span>
</span>
