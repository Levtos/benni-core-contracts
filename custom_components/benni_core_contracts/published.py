"""Explicit publication gate and graph wiring for the first pilot contract.

Only the kitchen patio-door opening contract is publishable in this slice.
The raw source entities are never defaults: a caller must provide both exact
SourceBindings in the ConfigEntry before ``mode=published`` can validate.
"""

from __future__ import annotations

from typing import Iterable

from .const import (
    PILOT_OPENING_BINDING_OPEN,
    PILOT_OPENING_BINDING_TILT,
    PILOT_OPENING_BINDING_IDS,
    PILOT_OPENING_CONTRACT_ID,
    PILOT_OPENING_SOURCE_ENTITY_IDS,
)
from .models import ConfigModel, Fusion, ProfileId, SourceBinding
from .quality import FallbackAction, FallbackPolicy


def pilot_opening_bindings(
    open_entity_id: str,
    tilt_entity_id: str,
) -> tuple[SourceBinding, SourceBinding]:
    """Build explicit raw bindings from user-selected HA entity IDs."""

    return (
        SourceBinding(
            binding_id=PILOT_OPENING_BINDING_OPEN,
            source_id=f"ha:{open_entity_id}",
            entity_id=open_entity_id,
            field="open_contact",
            capability="opening",
            profile_id=ProfileId.BENNI,
            required=True,
            freshness_ttl_seconds=600,
            consumer_ids=("opening.v1",),
            fallback=FallbackPolicy(
                action=FallbackAction.REJECT,
                reason="opening open-contact evidence is required",
            ),
        ),
        SourceBinding(
            binding_id=PILOT_OPENING_BINDING_TILT,
            source_id=f"ha:{tilt_entity_id}",
            entity_id=tilt_entity_id,
            field="tilt_contact",
            capability="opening",
            profile_id=ProfileId.BENNI,
            required=True,
            freshness_ttl_seconds=600,
            consumer_ids=("opening.v1",),
            fallback=FallbackPolicy(
                action=FallbackAction.REJECT,
                reason="opening tilt-contact evidence is required",
            ),
        ),
    )


def _pilot_bindings(config: ConfigModel) -> tuple[SourceBinding, SourceBinding]:
    by_id = {binding.binding_id: binding for binding in config.bindings}
    missing = [binding_id for binding_id in PILOT_OPENING_BINDING_IDS if binding_id not in by_id]
    if missing:
        raise ValueError(
            "published opening pilot is missing explicit bindings: "
            + ", ".join(missing)
        )
    bindings = tuple(by_id[binding_id] for binding_id in PILOT_OPENING_BINDING_IDS)
    if any(binding.profile_id != ProfileId.BENNI for binding in bindings):
        raise ValueError("published opening pilot bindings must use profile=benni")
    if bindings[0].field != "open_contact" or bindings[1].field != "tilt_contact":
        raise ValueError("published opening pilot bindings must map open and tilt contacts")
    if any(binding.entity_id.split(".", 1)[0] != "binary_sensor" for binding in bindings):
        raise ValueError("published opening pilot requires binary_sensor source entities")
    if tuple(binding.entity_id for binding in bindings) != PILOT_OPENING_SOURCE_ENTITY_IDS:
        raise ValueError(
            "published opening pilot requires the currently verified kitchen patio-door sources"
        )
    return bindings  # type: ignore[return-value]


def build_pilot_fusions(config: ConfigModel) -> tuple[Fusion, ...]:
    """Return only the internal fusions authorized by the pilot allowlist."""

    if config.mode.value != "published":
        return ()
    if config.published_contracts != (PILOT_OPENING_CONTRACT_ID,):
        raise ValueError("only the kitchen patio-door opening pilot is publishable")
    bindings = _pilot_bindings(config)
    binding_ids = tuple(binding.binding_id for binding in bindings)
    return (
        Fusion(
            fusion_id=f"fusion:{PILOT_OPENING_CONTRACT_ID}:opening_state",
            contract_id=PILOT_OPENING_CONTRACT_ID,
            field="opening_state",
            input_binding_ids=binding_ids,
            strategy="opening_contacts",
            consumer_ids=("opening.v1",),
        ),
        Fusion(
            fusion_id=f"fusion:{PILOT_OPENING_CONTRACT_ID}:available",
            contract_id=PILOT_OPENING_CONTRACT_ID,
            field="available",
            input_binding_ids=binding_ids,
            strategy="opening_available",
            consumer_ids=("opening.v1",),
        ),
        Fusion(
            fusion_id=f"fusion:{PILOT_OPENING_CONTRACT_ID}:is_open",
            contract_id=PILOT_OPENING_CONTRACT_ID,
            field="is_open",
            input_binding_ids=binding_ids,
            strategy="opening_is_open",
            consumer_ids=("opening.v1",),
        ),
        Fusion(
            fusion_id=f"fusion:{PILOT_OPENING_CONTRACT_ID}:source_count",
            contract_id=PILOT_OPENING_CONTRACT_ID,
            field="source_count",
            input_binding_ids=binding_ids,
            strategy="opening_source_count",
            consumer_ids=("diagnostics",),
        ),
    )


def pilot_contract_ids() -> tuple[str, ...]:
    """Stable list used by the entity platform; no registry discovery."""

    return (PILOT_OPENING_CONTRACT_ID,)


def has_pilot_contract(config: ConfigModel, contract_id: str) -> bool:
    return contract_id in config.published_contracts


def validate_pilot_binding_ids(bindings: Iterable[SourceBinding]) -> None:
    """Keep the pilot's two raw inputs explicit and uniquely identifiable."""

    ids = {binding.binding_id for binding in bindings}
    missing = set(PILOT_OPENING_BINDING_IDS) - ids
    if missing:
        raise ValueError("missing pilot binding IDs: " + ", ".join(sorted(missing)))
    if PILOT_OPENING_BINDING_OPEN == PILOT_OPENING_BINDING_TILT:
        raise ValueError("pilot binding IDs must be distinct")
