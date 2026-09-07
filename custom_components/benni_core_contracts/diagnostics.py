"""Diagnostic projections for field-scoped contract health."""

from __future__ import annotations

from datetime import datetime
from copy import deepcopy

from .models import DiagnosticProjection, FieldDiagnostic, PublishedContract
from .quality import HealthStatus, utc_now


def build_diagnostic_projection(
    contract: PublishedContract,
    source_entities: dict[str, tuple[str, ...]],
    active_source_entities: dict[str, tuple[str, ...]],
    now: datetime | None = None,
) -> DiagnosticProjection:
    reference = now or utc_now()
    fields: list[FieldDiagnostic] = []
    for field_name, quality in contract.field_quality.items():
        causes = quality.reasons
        evaluation = contract.field_evaluations[field_name]
        if quality.health == HealthStatus.HEALTHY:
            effect = "available_to_declared_consumers"
        elif quality.health == HealthStatus.BLOCKED:
            effect = "consumer_blocked"
        else:
            effect = "field_degraded_consumer_must_check_quality"
        fields.append(
            FieldDiagnostic(
                field=field_name,
                state=contract.field_states[field_name],
                health=quality.health,
                quality=quality.quality,
                freshness=quality.freshness,
                safety=quality.safety.value,
                source_entities=source_entities.get(field_name, ()),
                active_source_entities=active_source_entities.get(field_name, ()),
                completeness=evaluation.completeness,
                root_causes=causes,
                consumer_effect=effect,
            )
        )
    return DiagnosticProjection(
        projection_id=f"diagnostic:{contract.contract_id}",
        contract_id=contract.contract_id,
        schema_id=contract.schema_id,
        health=contract.health,
        fields=tuple(fields),
        generated_at=reference,
    )


def registry_diagnostic_context(payload, snapshot, consumer_api=None):
    """Add repair context to a copied projection; never mutate configuration."""
    result = deepcopy(payload)
    if snapshot is None:
        return result
    configuration = snapshot.revision.payload
    by_id = {fusion.fusion_id: fusion for fusion in configuration.fusions}
    bindings = {binding.binding_id: binding for binding in configuration.bindings}
    requirements = [state for impact in consumer_api.all_impacts() for state in impact.requirements
                    if state.requirement.profile == snapshot.profile] if consumer_api else []

    def inputs(fusion, visited=None):
        visited = set() if visited is None else visited
        if fusion.fusion_id in visited: return set()
        visited.add(fusion.fusion_id)
        ids = set(fusion.input_binding_ids)
        for child in fusion.input_fusion_ids:
            if child in by_id: ids.update(inputs(by_id[child], visited))
        return ids

    for diagnostic in result.get('diagnostics', []):
        contract_id = diagnostic['contract_id']
        contract = snapshot.graph.contract(contract_id)
        diagnostic.update(profile=snapshot.profile.value, registry_revision=snapshot.revision.revision,
                          registry_revision_id=snapshot.revision.id)
        for field in diagnostic['fields']:
            name = field['field']
            ids = set()
            for fusion in configuration.fusions:
                if fusion.contract_id == contract_id and fusion.field == name:
                    ids.update(inputs(fusion))
            field['binding_ids'] = sorted(ids)
            field['bindings'] = [{'binding_id': key, 'entity_id': bindings[key].entity_id,
                                  'enabled': bindings[key].enabled, 'fallback': bindings[key].fallback.as_dict()}
                                 for key in sorted(ids) if key in bindings]
            field['consumer_impact'] = [{'consumer_id': state.consumer_id, 'status': state.status.value}
                                       for state in requirements
                                       if state.requirement.contract_id == contract_id
                                       or any(state.requirement.role in {bindings[key].field, bindings[key].capability, bindings[key].source_id, key}
                                              for key in ids if key in bindings)]
            durations = [cause.get('duration_seconds') for cause in field['root_causes'] if cause.get('duration_seconds') is not None]
            field['degradation_duration_seconds'] = max(durations) if durations else None
            if contract is not None:
                field['value'] = deepcopy(contract.values.get(name))
                quality = contract.field_quality.get(name)
                field['fallback'] = quality.fallback.value if quality else None
    return result
