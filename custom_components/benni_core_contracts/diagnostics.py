"""Diagnostic projections for field-scoped contract health."""

from __future__ import annotations

from datetime import datetime

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
