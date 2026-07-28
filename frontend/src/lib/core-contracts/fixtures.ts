import type {
  Contract,
  DiagnosticProjection,
  GraphSnapshot,
  HealthItem,
  QualityReason,
} from "./types";

const now = "2026-07-27T09:00:00.000Z";
const since = "2026-07-27T08:42:00.000Z";

function reason(field: string, code: string, message: string, source: string | null): QualityReason {
  return {
    code,
    message,
    field,
    source_entity: source,
    since,
    duration_seconds: 1080,
    blocking: false,
    consumer_effect: "field_degraded_consumer_must_check_quality",
  };
}

function healthyQuality() {
  return {
    health: "healthy" as const,
    freshness: "fresh" as const,
    safety: "valid" as const,
    fallback: "none" as const,
    quality: "good" as const,
    last_real_change: "2026-07-27T08:58:14.000Z",
    reasons: [],
  };
}

export function previewData(): {
  contracts: Contract[];
  diagnostics: DiagnosticProjection[];
  graph: GraphSnapshot;
  health: HealthItem[];
} {
  const humidityQuality = {
    health: "degraded" as const,
    freshness: "stale" as const,
    safety: "conservative" as const,
    fallback: "reject" as const,
    quality: "stale" as const,
    last_real_change: "2026-07-26T22:11:02.000Z",
    reasons: [reason("humidity", "freshness_ttl_exceeded", "freshness ttl exceeded", "sensor.living_humidity")],
  };
  const living: Contract = {
    contract_id: "room.living",
    schema_id: "room_climate",
    schema_version: 1,
    values: { temperature: 21.8, humidity: null, available: true, device_state: "active" },
    field_states: { temperature: "valid", humidity: "unknown", available: "valid", device_state: "valid" },
    field_quality: {
      temperature: healthyQuality(),
      humidity: humidityQuality,
      available: healthyQuality(),
      device_state: healthyQuality(),
    },
    health: "degraded",
    generated_at: now,
    lineage: { temperature: ["binding.living.temperature"], humidity: [], available: ["binding.living.temperature"], device_state: ["binding.living.state"] },
    field_evaluations: {
      temperature: { field: "temperature", state: "valid", active_binding_ids: ["binding.living.temperature"], candidate_binding_ids: ["binding.living.temperature"], completeness: true, strategy: "first_healthy", note: null },
      humidity: { field: "humidity", state: "unknown", active_binding_ids: [], candidate_binding_ids: ["binding.living.humidity"], completeness: false, strategy: "first_healthy", note: "no_fresh_valid_source" },
      available: { field: "available", state: "valid", active_binding_ids: ["binding.living.temperature"], candidate_binding_ids: ["binding.living.temperature"], completeness: true, strategy: "first_healthy", note: null },
      device_state: { field: "device_state", state: "valid", active_binding_ids: ["binding.living.state"], candidate_binding_ids: ["binding.living.state"], completeness: true, strategy: "first_healthy", note: null },
    },
  };
  const livingDiagnostics: DiagnosticProjection = {
    projection_id: "diagnostic:room.living",
    contract_id: "room.living",
    schema_id: "room_climate",
    health: "degraded",
    generated_at: now,
    fields: [
      { field: "temperature", state: "valid", health: "healthy", quality: "good", freshness: "fresh", safety: "valid", source_entities: ["sensor.living_temperature"], active_source_entities: ["sensor.living_temperature"], completeness: true, root_causes: [], consumer_effect: "available_to_declared_consumers" },
      { field: "humidity", state: "unknown", health: "degraded", quality: "stale", freshness: "stale", safety: "conservative", source_entities: ["sensor.living_humidity"], active_source_entities: [], completeness: false, root_causes: humidityQuality.reasons, consumer_effect: "field_degraded_consumer_must_check_quality" },
      { field: "available", state: "valid", health: "healthy", quality: "good", freshness: "fresh", safety: "valid", source_entities: ["sensor.living_temperature"], active_source_entities: ["sensor.living_temperature"], completeness: true, root_causes: [], consumer_effect: "available_to_declared_consumers" },
      { field: "device_state", state: "valid", health: "healthy", quality: "good", freshness: "fresh", safety: "valid", source_entities: ["sensor.living_climate_state"], active_source_entities: ["sensor.living_climate_state"], completeness: true, root_causes: [], consumer_effect: "available_to_declared_consumers" },
    ],
  };
  const opening: Contract = {
    contract_id: "opening.front_door",
    schema_id: "opening",
    schema_version: 1,
    values: { opening_state: "unknown", is_open: "unknown", available: false, source_quality: "blocked" },
    field_states: { opening_state: "unknown", is_open: "unknown", available: "unknown", source_quality: "unknown" },
    field_quality: {
      opening_state: { health: "blocked", freshness: "unknown", safety: "unknown", fallback: "reject", quality: "unavailable", last_real_change: null, reasons: [reason("opening_state", "source_unavailable", "source unavailable", "binary_sensor.front_door") ] },
      is_open: { health: "blocked", freshness: "unknown", safety: "unknown", fallback: "reject", quality: "unavailable", last_real_change: null, reasons: [reason("is_open", "source_unavailable", "source unavailable", "binary_sensor.front_door") ] },
      available: { health: "blocked", freshness: "unknown", safety: "blocked", fallback: "reject", quality: "unavailable", last_real_change: null, reasons: [reason("available", "source_unavailable", "source unavailable", "binary_sensor.front_door") ] },
      source_quality: { health: "unknown", freshness: "unknown", safety: "unknown", fallback: "reject", quality: "unknown", last_real_change: null, reasons: [] },
    },
    health: "blocked",
    generated_at: now,
    lineage: { opening_state: [], is_open: [], available: [], source_quality: [] },
    field_evaluations: {
      opening_state: { field: "opening_state", state: "unknown", active_binding_ids: [], candidate_binding_ids: [], completeness: false, strategy: "first_healthy", note: "source_unavailable" },
      is_open: { field: "is_open", state: "unknown", active_binding_ids: [], candidate_binding_ids: [], completeness: false, strategy: "first_healthy", note: "source_unavailable" },
      available: { field: "available", state: "unknown", active_binding_ids: [], candidate_binding_ids: [], completeness: false, strategy: "first_healthy", note: "source_unavailable" },
      source_quality: { field: "source_quality", state: "unknown", active_binding_ids: [], candidate_binding_ids: [], completeness: false, strategy: "none", note: null },
    },
  };
  const openingDiagnostics: DiagnosticProjection = {
    projection_id: "diagnostic:opening.front_door",
    contract_id: "opening.front_door",
    schema_id: "opening",
    health: "blocked",
    generated_at: now,
    fields: [
      { field: "opening_state", state: "unknown", health: "blocked", quality: "unavailable", freshness: "unknown", safety: "unknown", source_entities: ["binary_sensor.front_door"], active_source_entities: [], completeness: false, root_causes: opening.field_quality.opening_state.reasons, consumer_effect: "consumer_blocked" },
      { field: "is_open", state: "unknown", health: "blocked", quality: "unavailable", freshness: "unknown", safety: "unknown", source_entities: ["binary_sensor.front_door"], active_source_entities: [], completeness: false, root_causes: opening.field_quality.is_open.reasons, consumer_effect: "consumer_blocked" },
      { field: "available", state: "unknown", health: "blocked", quality: "unavailable", freshness: "unknown", safety: "blocked", source_entities: ["binary_sensor.front_door"], active_source_entities: [], completeness: false, root_causes: opening.field_quality.available.reasons, consumer_effect: "consumer_blocked" },
      { field: "source_quality", state: "unknown", health: "unknown", quality: "unknown", freshness: "unknown", safety: "unknown", source_entities: [], active_source_entities: [], completeness: false, root_causes: [], consumer_effect: "field_degraded_consumer_must_check_quality" },
    ],
  };
  const weather: Contract = {
    contract_id: "weather.outdoor",
    schema_id: "weather_environment",
    schema_version: 1,
    values: { outdoor_temperature: 17.4, humidity: 66, condition: "partlycloudy", available: true, source_quality: "good" },
    field_states: { outdoor_temperature: "valid", humidity: "valid", condition: "valid", available: "valid", source_quality: "valid" },
    field_quality: Object.fromEntries(["outdoor_temperature", "humidity", "condition", "available", "source_quality"].map((field) => [field, healthyQuality()])),
    health: "healthy",
    generated_at: now,
    lineage: { outdoor_temperature: ["binding.weather.temperature"], humidity: ["binding.weather.humidity"], condition: ["binding.weather.condition"], available: ["binding.weather.temperature"], source_quality: ["binding.weather.temperature"] },
    field_evaluations: {},
  };
  const diagnostics = [livingDiagnostics, openingDiagnostics];
  const graph: GraphSnapshot = {
    revision: 18,
    bindings: [
      { binding_id: "binding.living.temperature", source_id: "climate.living", entity_id: "sensor.living_temperature", field: "temperature", capability: "room_climate", profile_id: "benni", required: true, freshness_ttl_seconds: 300, consumer_ids: ["climate_contract"], fallback: { action: "reject", default_value: null, reason: "no_valid_observation" }, read_only: true },
      { binding_id: "binding.living.humidity", source_id: "climate.living", entity_id: "sensor.living_humidity", field: "humidity", capability: "room_climate", profile_id: "benni", required: false, freshness_ttl_seconds: 900, consumer_ids: ["climate_contract"], fallback: { action: "reject", default_value: null, reason: "no_valid_observation" }, read_only: true },
      { binding_id: "binding.front-door", source_id: "opening.front_door", entity_id: "binary_sensor.front_door", field: "opening_state", capability: "opening", profile_id: "benni", required: true, freshness_ttl_seconds: 300, consumer_ids: ["opening_contract"], fallback: { action: "reject", default_value: null, reason: "no_valid_observation" }, read_only: true },
      { binding_id: "binding.weather.temperature", source_id: "weather.home", entity_id: "sensor.outdoor_temperature", field: "outdoor_temperature", capability: "weather_environment", profile_id: "benni", required: true, freshness_ttl_seconds: 900, consumer_ids: ["weather_contract"], fallback: { action: "reject", default_value: null, reason: "no_valid_observation" }, read_only: true },
    ],
    signals: [],
    fusions: [
      { fusion_id: "fusion.living.temperature", contract_id: "room.living", field: "temperature", input_binding_ids: ["binding.living.temperature"], input_fusion_ids: [], strategy: "first_healthy", consumer_ids: ["climate_contract"] },
      { fusion_id: "fusion.front-door", contract_id: "opening.front_door", field: "opening_state", input_binding_ids: ["binding.front-door"], input_fusion_ids: [], strategy: "first_healthy", consumer_ids: ["opening_contract"] },
    ],
    contracts: [living, opening, weather],
    diagnostics,
  };
  return {
    contracts: [living, opening, weather],
    diagnostics,
    graph,
    health: [
      { contract_id: living.contract_id, schema_id: living.schema_id, health: living.health },
      { contract_id: opening.contract_id, schema_id: opening.schema_id, health: opening.health },
      { contract_id: weather.contract_id, schema_id: weather.schema_id, health: weather.health },
    ],
  };
}
