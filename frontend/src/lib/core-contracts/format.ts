export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "unknown";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 }).format(value);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin" }).format(date);
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "nicht belegt";
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return remaining ? `${hours} h ${remaining} min` : `${hours} h`;
}

export function labelForSchema(schemaId: string): string {
  const labels: Record<string, string> = {
    room_climate: "Room Climate",
    opening: "Opening",
    weather_environment: "Weather / Environment",
    technical_device: "Technical Device",
  };
  return labels[schemaId] ?? schemaId;
}

export function labelForStrategy(strategy: string): string {
  const labels: Record<string, string> = { first_healthy: "First healthy", latest: "Latest", any_true: "Any true", none: "Nicht konfiguriert" };
  return labels[strategy] ?? strategy;
}
