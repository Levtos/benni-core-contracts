export type HealthStatus = "healthy" | "degraded" | "blocked" | "unknown";
export type QualityStatus =
  | "good"
  | "degraded"
  | "unavailable"
  | "unknown"
  | "conflict"
  | "suspect"
  | "stale";
export type FreshnessStatus = "fresh" | "suspect" | "stale" | "unknown" | "restored";
export type SafetyStatus = "valid" | "conservative" | "unsafe" | "blocked" | "unknown";
export type ValueState = "valid" | "unknown" | "unavailable" | "blocked" | "invalid";
export type FallbackAction = "none" | "hold_last" | "safe_default" | "reject";

export interface QualityReason {
  code: string;
  message: string;
  field: string;
  source_entity: string | null;
  since: string | null;
  duration_seconds: number | null;
  blocking: boolean;
  consumer_effect: string;
}

export interface FieldQuality {
  health: HealthStatus;
  freshness: FreshnessStatus;
  safety: SafetyStatus;
  fallback: FallbackAction;
  quality: QualityStatus;
  last_real_change: string | null;
  reasons: QualityReason[];
}

export interface FieldEvaluation {
  field: string;
  state: ValueState;
  active_binding_ids: string[];
  candidate_binding_ids: string[];
  completeness: boolean;
  strategy: string;
  note: string | null;
}

export interface Contract {
  contract_id: string;
  schema_id: string;
  schema_version: number;
  values: Record<string, unknown>;
  field_states: Record<string, ValueState>;
  field_quality: Record<string, FieldQuality>;
  health: HealthStatus;
  generated_at: string;
  lineage: Record<string, string[]>;
  field_evaluations: Record<string, FieldEvaluation>;
}

export interface DiagnosticField {
  field: string;
  state: ValueState;
  health: HealthStatus;
  quality: QualityStatus;
  freshness: FreshnessStatus;
  safety: SafetyStatus;
  source_entities: string[];
  active_source_entities: string[];
  completeness: boolean;
  root_causes: QualityReason[];
  consumer_effect: string;
}

export interface DiagnosticProjection {
  projection_id: string;
  contract_id: string;
  schema_id: string;
  health: HealthStatus;
  fields: DiagnosticField[];
  generated_at: string;
}

export interface SourceBinding {
  binding_id: string;
  source_id: string;
  entity_id: string;
  field: string;
  capability: string;
  profile_id: string;
  required: boolean;
  freshness_ttl_seconds: number;
  consumer_ids: string[];
  fallback: { action: FallbackAction; default_value: unknown; reason: string };
  read_only: boolean;
}

export interface AtomicSignal {
  signal_id: string;
  binding_id: string;
  field: string;
  value: unknown;
  evidence: {
    received_at: string;
    origin: string;
    device_timestamp: string | null;
    ha_timestamp: string | null;
    retained: boolean;
    restored: boolean;
    ha_state_event: boolean;
  };
  quality: FieldQuality;
  real_change_at: string | null;
}

export interface Fusion {
  fusion_id: string;
  contract_id: string;
  field: string;
  input_binding_ids: string[];
  input_fusion_ids: string[];
  strategy: string;
  consumer_ids: string[];
}

export interface GraphSnapshot {
  revision: number;
  bindings: SourceBinding[];
  signals: AtomicSignal[];
  fusions: Fusion[];
  contracts: Contract[];
  diagnostics: DiagnosticProjection[];
}

export interface HealthItem {
  contract_id: string;
  schema_id: string;
  health: HealthStatus;
}

export interface PayloadBase {
  payload_version: number;
  command: string;
  revision: number;
  delta: {
    supported: boolean;
    mode: string;
    since_revision: number | null;
    unchanged: boolean;
  };
}

export interface ListContractsPayload extends PayloadBase {
  contracts: Contract[];
}

export interface ContractPayload extends PayloadBase {
  contract: Contract;
}

export interface DiagnosticsPayload extends PayloadBase {
  diagnostics: DiagnosticProjection[];
}

export interface GraphPayload extends PayloadBase {
  graph: GraphSnapshot;
}

export interface HealthPayload extends PayloadBase {
  health: HealthItem[];
}

export interface HassConnection {
  sendMessagePromise<T = unknown>(message: Record<string, unknown>): Promise<T>;
}

export interface HassLike {
  connection?: HassConnection;
}
