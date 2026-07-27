export type ConnectionState =
  | "loading"
  | "connected"
  | "reconnecting"
  | "offline"
  | "error"
  | "unavailable";

export type DataState =
  | "loading"
  | "ready"
  | "empty"
  | "stale"
  | "degraded"
  | "blocked";
