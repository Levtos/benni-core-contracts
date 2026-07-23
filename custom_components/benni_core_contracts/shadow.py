"""Shadow runtime and explicit public-entity boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .const import WEBSOCKET_PAYLOAD_VERSION
from .models import (
    ConfigModel,
    DiagnosticProjection,
    ProfileId,
    PublishedContract,
    RuntimeMode,
)
from .graph import SignalGraph


@dataclass(frozen=True)
class EntityAllowlist:
    """Exact entity IDs only; no wildcard or inferred public projections."""

    entity_ids: frozenset[str] = frozenset()

    def allows(self, entity_id: str) -> bool:
        return entity_id in self.entity_ids


class EntityProjectionGate:
    """One explicit gate for any future public entity projection."""

    def __init__(self, mode: RuntimeMode, allowlist: EntityAllowlist) -> None:
        if mode != RuntimeMode.SHADOW_ONLY:
            raise ValueError("only shadow_only entity projection is available")
        self.mode = mode
        self.allowlist = allowlist

    def projectable(self, candidate_entity_ids: Iterable[str]) -> tuple[str, ...]:
        return ()


class ShadowRuntime:
    """Runtime facade with no entity platform and no actuation surface."""

    def __init__(self, config: ConfigModel, graph: SignalGraph) -> None:
        if config.mode != RuntimeMode.SHADOW_ONLY:
            raise ValueError("ShadowRuntime requires mode=shadow_only")
        if config.profile != ProfileId.BENNI:
            raise ValueError("parent_future is outside the Benni shadow runtime")
        if config.entity_allowlist:
            raise ValueError("shadow_only runtime cannot carry a public allowlist")
        self.config = config
        self.graph = graph
        self.entity_gate = EntityProjectionGate(
            config.mode,
            EntityAllowlist(frozenset(config.entity_allowlist)),
        )
        self._unsubscribers: list = []

    @property
    def mode(self) -> RuntimeMode:
        return self.config.mode

    def public_entity_ids(self, candidates: Iterable[str] = ()) -> tuple[str, ...]:
        return self.entity_gate.projectable(candidates)

    def contracts(self) -> tuple[PublishedContract, ...]:
        return self.graph.contracts()

    def diagnostics(self) -> tuple[DiagnosticProjection, ...]:
        return self.graph.diagnostics()

    def benni_contract_verification(self, *, now: datetime):
        """Return the internal Benni Evidence Gate projection in shadow mode.

        Signals are copied into an explicit, read-only source-observation map.
        Their original TemporalEvidence is retained, so restore, retained MQTT
        and missing timestamps cannot become fresh through this facade.
        """

        if self.config.profile != ProfileId.BENNI:
            raise ValueError("parent_future is outside the Benni shadow gate")
        if self.mode != RuntimeMode.SHADOW_ONLY:
            raise ValueError("Benni contract verification is shadow-only")
        from .shadow_verification import (
            ShadowSourceObservation,
            verify_benni_shadow_report,
        )

        observations = {}
        for binding in self.graph.bindings():
            signal = self.graph.signal(binding.binding_id)
            if signal is None:
                continue
            observations[binding.entity_id] = ShadowSourceObservation(
                source_entity=binding.entity_id,
                state=signal.value,
                attributes={"binding_id": binding.binding_id},
                evidence=signal.evidence,
            )
        return verify_benni_shadow_report(
            self.contracts(),
            self.graph.registry,
            source_bindings=self.graph.bindings(),
            source_observations=observations,
            now=now,
        )

    def add_unsubscribe(self, unsubscribe) -> None:
        self._unsubscribers.append(unsubscribe)

    def unload(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    def websocket_payload(
        self,
        command: str,
        contract_id: str | None = None,
        *,
        since_revision: int | None = None,
    ) -> dict:
        revision = self.graph.revision
        if since_revision is not None and since_revision < 0:
            raise ValueError("since_revision must be non-negative")
        payload = {
            "payload_version": WEBSOCKET_PAYLOAD_VERSION,
            "command": command,
            "revision": revision,
            "delta": {
                "supported": True,
                "mode": "revision_reconciliation",
                "since_revision": since_revision,
                "unchanged": since_revision is not None and since_revision == revision,
            },
        }
        if command.endswith("/list_contracts"):
            payload["contracts"] = [contract.as_dict() for contract in self.contracts()]
            return payload
        if command.endswith("/get_contract"):
            if not contract_id:
                raise ValueError("contract_id is required")
            contract = self.graph.contract(contract_id)
            if contract is None:
                raise KeyError(contract_id)
            payload["contract"] = contract.as_dict()
            return payload
        if command.endswith("/get_diagnostics"):
            if contract_id:
                diagnostic = self.graph.diagnostic(contract_id)
                if diagnostic is None:
                    raise KeyError(contract_id)
                payload["diagnostics"] = [diagnostic.as_dict()]
                return payload
            payload["diagnostics"] = [item.as_dict() for item in self.diagnostics()]
            return payload
        if command.endswith("/get_graph"):
            payload["graph"] = self.graph.snapshot().as_dict()
            return payload
        if command.endswith("/get_health"):
            payload["health"] = [
                {
                    "contract_id": contract.contract_id,
                    "schema_id": contract.schema_id,
                    "health": contract.health.value,
                }
                for contract in self.contracts()
            ]
            return payload
        raise ValueError(f"unsupported read-only command: {command}")
