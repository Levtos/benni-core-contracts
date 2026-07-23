"""Synthetic inputs for the Benni Shadow Contract Verification Gate.

They translate only the local graph fixtures into explicit read-only source
observations.  No helper reads a Home Assistant registry, writes a ConfigEntry
or represents a public entity.
"""

from __future__ import annotations

from typing import Any, Mapping

from custom_components.benni_core_contracts.shadow_verification import (
    ShadowSourceObservation,
    verify_benni_shadow_contract,
)

from fixtures import EvidenceFixture, build_fixture_graph


def source_observations_for_fixture(
    fixture: EvidenceFixture,
    *,
    state_overrides: Mapping[str, Any] | None = None,
) -> dict[str, ShadowSourceObservation]:
    """Create read-only source-state evidence keyed by exact entity ID."""

    state_overrides = state_overrides or {}
    return {
        item.observation.entity_id: ShadowSourceObservation(
            source_entity=item.observation.entity_id,
            state=state_overrides.get(item.binding_id, item.observation.value),
            attributes={"fixture": fixture.name, "binding_id": item.binding_id},
            evidence=item.observation.evidence,
        )
        for item in fixture.observations
    }


def shadow_result_for_fixture(
    fixture: EvidenceFixture,
    *,
    source_observations: Mapping[str, ShadowSourceObservation] | None = None,
):
    """Evaluate an existing generic fixture using the Benni shadow projection."""

    graph = build_fixture_graph(fixture)
    contract = graph.evaluate_contract(
        fixture.contract_id,
        fixture.schema_id,
        now=fixture.now,
    )
    return graph, contract, verify_benni_shadow_contract(
        contract,
        graph.registry.get(fixture.schema_id),
        source_bindings=fixture.bindings,
        source_observations=(
            source_observations
            if source_observations is not None
            else source_observations_for_fixture(fixture)
        ),
        now=fixture.now,
    )
