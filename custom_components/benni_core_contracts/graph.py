"""Internal SourceBinding -> Contract signal graph for Gate Pack v1."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import logging
from typing import Any, Callable, Iterable

from .contracts import default_schema_registry
from .diagnostics import build_diagnostic_projection
from .models import (
    AtomicSignal,
    ConfigModel,
    DiagnosticProjection,
    FieldEvaluation,
    Fusion,
    ProfileId,
    PublishedContract,
    RawObservation,
    SourceBinding,
)
from .quality import (
    FallbackAction,
    FieldQuality,
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    QualityIssue,
    QualityStatus,
    SafetyClass,
    ValueState,
    assess_field_quality,
    aggregate_health,
    utc_now,
)
from .schema import ContractFieldSchema, ContractSchema, SchemaRegistry


LOGGER = logging.getLogger(__name__)


class GraphError(ValueError):
    """Invalid graph topology or observation."""


@dataclass(frozen=True)
class GraphSnapshot:
    revision: int
    bindings: tuple[dict[str, Any], ...]
    signals: tuple[dict[str, Any], ...]
    fusions: tuple[dict[str, Any], ...]
    contracts: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "bindings": list(self.bindings),
            "signals": list(self.signals),
            "fusions": list(self.fusions),
            "contracts": list(self.contracts),
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class _FusionSelection:
    value: Any
    state: ValueState
    selected_signal: AtomicSignal | None
    active_binding_ids: tuple[str, ...]
    candidate_binding_ids: tuple[str, ...]
    completeness: bool
    note: str | None = None
    conflict: bool = False


class SignalGraph:
    """A bounded graph with explicit freshness and cycle gates."""

    def __init__(
        self,
        *,
        registry: SchemaRegistry | None = None,
        now_factory=utc_now,
        profile: ProfileId | str | None = None,
    ) -> None:
        if profile is not None and not isinstance(profile, ProfileId):
            try:
                profile = ProfileId(str(profile))
            except ValueError as err:
                raise ValueError("graph profile must be benni or eltern") from err
        self.registry = registry or default_schema_registry()
        self._profile = profile
        self._now_factory = now_factory
        self._bindings: dict[str, SourceBinding] = {}
        self._signals: dict[str, AtomicSignal] = {}
        self._fusions: dict[tuple[str, str], Fusion] = {}
        self._fusions_by_id: dict[str, Fusion] = {}
        self._contracts: dict[str, PublishedContract] = {}
        self._diagnostics: dict[str, DiagnosticProjection] = {}
        self._revision = 0
        self._change_listeners: list[Callable[["SignalGraph"], None]] = []

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def profile(self) -> ProfileId | None:
        """Profile scope, when the graph was built from profile config.

        Direct unit-test graphs may remain unscoped for backwards
        compatibility; registry/runtime graphs are always profile-scoped.
        """

        return self._profile

    def add_binding(self, binding: SourceBinding) -> None:
        if self._profile is not None and binding.profile_id != self._profile:
            raise GraphError(
                f"binding {binding.binding_id} belongs to profile "
                f"{binding.profile_id.value}, graph belongs to {self._profile.value}"
            )
        if binding.binding_id in self._bindings:
            raise GraphError(f"duplicate binding: {binding.binding_id}")
        self._bindings[binding.binding_id] = binding
        self._revision += 1
        self._notify_change()

    def add_fusion(self, fusion: Fusion) -> None:
        self.add_fusions((fusion,))

    def add_fusions(self, fusions: Iterable[Fusion]) -> None:
        """Register a batch and reject references that would create a cycle."""

        batch = tuple(fusions)
        if not batch:
            return
        all_by_id = dict(self._fusions_by_id)
        all_by_key = dict(self._fusions)
        for fusion in batch:
            if fusion.fusion_id in all_by_id:
                raise GraphError(f"duplicate fusion ID: {fusion.fusion_id}")
            key = (fusion.contract_id, fusion.field)
            if key in all_by_key:
                raise GraphError(f"duplicate fusion for {fusion.contract_id}.{fusion.field}")
            unknown_bindings = [
                binding_id
                for binding_id in fusion.input_binding_ids
                if binding_id not in self._bindings
            ]
            if unknown_bindings:
                raise GraphError(f"fusion references unknown bindings: {unknown_bindings}")
            all_by_id[fusion.fusion_id] = fusion
            all_by_key[key] = fusion
        self._assert_acyclic(all_by_id)
        for fusion in batch:
            if fusion.strategy.startswith("opening_"):
                # The opening pilot fuses two raw contact fields into one
                # contract field.  This is the one deliberate domain
                # normalization exception to the usual same-field rule.
                allowed_input_fields = {"open_contact", "tilt_contact"}
                mismatched_bindings = [
                    binding_id
                    for binding_id in fusion.input_binding_ids
                    if self._bindings[binding_id].field not in allowed_input_fields
                ]
            else:
                mismatched_bindings = [
                    binding_id
                    for binding_id in fusion.input_binding_ids
                    if self._bindings[binding_id].field != fusion.field
                ]
            if mismatched_bindings:
                raise GraphError(
                    f"fusion {fusion.fusion_id} references a different field: "
                    + ", ".join(mismatched_bindings)
                )
            for child_id in fusion.input_fusion_ids:
                child = all_by_id.get(child_id)
                if child is not None and (
                    child.contract_id != fusion.contract_id or child.field != fusion.field
                ):
                    raise GraphError(
                        f"fusion {fusion.fusion_id} references incompatible fusion {child_id}"
                    )
        self._fusions_by_id = all_by_id
        self._fusions = all_by_key
        self._revision += 1
        self._notify_change()

    @staticmethod
    def _assert_acyclic(fusions: dict[str, Fusion]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(fusion_id: str) -> None:
            if fusion_id in visiting:
                raise GraphError(f"fusion cycle detected at {fusion_id}")
            if fusion_id in visited:
                return
            if fusion_id not in fusions:
                raise GraphError(f"fusion references unknown fusion: {fusion_id}")
            visiting.add(fusion_id)
            for child_id in fusions[fusion_id].input_fusion_ids:
                visit(child_id)
            visiting.remove(fusion_id)
            visited.add(fusion_id)

        for fusion_id in fusions:
            visit(fusion_id)

    def has_binding(self, binding_id: str) -> bool:
        return binding_id in self._bindings

    def bindings(self) -> tuple[SourceBinding, ...]:
        return tuple(self._bindings.values())

    def binding(self, binding_id: str) -> SourceBinding:
        return self._bindings[binding_id]

    def signal(self, binding_id: str) -> AtomicSignal | None:
        return self._signals.get(binding_id)

    def add_change_listener(self, listener: Callable[["SignalGraph"], None]) -> None:
        """Register a read-only observer for graph/runtime changes.

        Observers receive the graph only as an internal callback argument;
        consumers use the separate Consumer API and never receive this object.
        Duplicate registrations are ignored so repeated runtime wiring cannot
        multiply update delivery.
        """

        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    def remove_change_listener(self, listener: Callable[["SignalGraph"], None]) -> None:
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    # Short aliases for internal adapters that use the generic observer term.
    add_listener = add_change_listener
    remove_listener = remove_change_listener

    def _notify_change(self) -> None:
        for listener in tuple(self._change_listeners):
            try:
                listener(self)
            except Exception:  # pragma: no cover - defensive integration hook
                LOGGER.exception("signal graph change listener failed")

    def ingest(
        self,
        binding_id: str,
        observation: RawObservation,
        *,
        now: datetime | None = None,
    ) -> AtomicSignal:
        if binding_id not in self._bindings:
            raise GraphError(f"unknown binding: {binding_id}")
        binding = self._bindings[binding_id]
        if not binding.enabled:
            raise GraphError(f"binding is disabled: {binding_id}")
        if observation.source_id != binding.source_id or observation.entity_id != binding.entity_id:
            raise GraphError("observation does not match its SourceBinding")
        reference = now or self._now_factory()
        previous = self._signals.get(binding_id)
        real_change_at = previous.real_change_at if previous else None
        if (
            previous is not None
            and previous.value != observation.value
            and observation.evidence.is_real_measurement_evidence
            and observation.evidence.effective_timestamp is not None
            and observation.evidence.effective_timestamp <= reference
        ):
            real_change_at = observation.evidence.effective_timestamp
        quality = assess_field_quality(
            field=binding.field,
            source_entity=binding.entity_id,
            evidence=observation.evidence,
            has_value=observation.value is not None,
            required=binding.required,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=binding.fallback,
            ttl_seconds=binding.freshness_ttl_seconds,
            now=reference,
            last_real_change=real_change_at,
        )
        signal = AtomicSignal(
            signal_id=f"atomic:{binding_id}",
            binding_id=binding_id,
            field=binding.field,
            value=observation.value,
            evidence=observation.evidence,
            quality=quality,
            real_change_at=real_change_at,
        )
        self._signals[binding_id] = signal
        self._revision += 1
        self._notify_change()
        return signal

    def restore_signal(
        self,
        binding_id: str,
        value: Any,
        *,
        restored_at: datetime | None = None,
    ) -> AtomicSignal:
        """Restore a value with explicit non-fresh restore evidence."""

        from .models import restore_evidence

        binding = self._bindings[binding_id]
        return self.ingest(
            binding_id,
            RawObservation(
                source_id=binding.source_id,
                entity_id=binding.entity_id,
                value=value,
                evidence=restore_evidence(restored_at),
            ),
            now=restored_at,
        )

    def evaluate_contract(
        self,
        contract_id: str,
        schema_id: str,
        *,
        schema_version: int | None = None,
        now: datetime | None = None,
    ) -> PublishedContract:
        reference = now or self._now_factory()
        schema = self.registry.get(schema_id, schema_version)
        values: dict[str, Any] = {}
        states: dict[str, ValueState] = {}
        qualities: dict[str, FieldQuality] = {}
        lineage: dict[str, tuple[str, ...]] = {}
        evaluations: dict[str, FieldEvaluation] = {}

        for field_schema in schema.fields:
            fusion = self._fusions.get((contract_id, field_schema.name))
            candidates = self._candidate_signals(fusion)
            selection = self._select_for_fusion(
                fusion,
                candidates,
                field_schema,
                reference,
            )
            evaluation = FieldEvaluation(
                field=field_schema.name,
                state=selection.state,
                active_binding_ids=selection.active_binding_ids,
                candidate_binding_ids=selection.candidate_binding_ids,
                completeness=selection.completeness,
                strategy=fusion.strategy if fusion else "none",
                note=selection.note,
            )
            source_reason = self._source_reason(
                selection,
                candidates,
                field_schema,
                reference,
            )

            physical_conflict = selection.conflict and field_schema.physical_state
            if (
                selection.selected_signal is not None
                and selection.state == ValueState.VALID
                and not physical_conflict
            ):
                selected = selection.selected_signal
                values[field_schema.name] = selection.value
                states[field_schema.name] = selection.state
                quality = assess_field_quality(
                    field=field_schema.name,
                    source_entity=self._bindings[selected.binding_id].entity_id,
                    evidence=selected.evidence,
                    has_value=True,
                    required=field_schema.required,
                    safety_class=field_schema.safety_class,
                    fallback=field_schema.fallback,
                    ttl_seconds=field_schema.freshness_ttl_seconds,
                    freshness_requirement=field_schema.freshness_requirement,
                    now=reference,
                    last_real_change=selected.real_change_at,
                    physical_state=field_schema.physical_state,
                )
                if selection.conflict:
                    quality = self._annotate_quality(
                        quality,
                        field_schema,
                        "source_conflict",
                        QualityStatus.CONFLICT,
                        selected.evidence.received_at,
                    )
                    quality = replace(
                        quality,
                        health=HealthStatus.DEGRADED,
                        quality=QualityStatus.CONFLICT,
                        reasons=quality.reasons
                        + (
                            QualityIssue(
                                code="conflicting_fresh_sources",
                                message="multiple fresh sources disagree; priority source is active",
                                field=field_schema.name,
                                source_entity=self._bindings[selected.binding_id].entity_id,
                                since=selected.evidence.received_at,
                                consumer_effect="active_source_requires_conflict_awareness",
                            ),
                        ),
                    )
                if not selection.completeness:
                    incomplete_code = (
                        "incomplete_any_true_sources"
                        if selection.note == "incomplete_any_true_sources"
                        else "incomplete_fusion"
                    )
                    quality = replace(
                        quality,
                        health=HealthStatus.DEGRADED,
                        quality=(
                            QualityStatus.CONFLICT
                            if quality.quality == QualityStatus.CONFLICT
                            else QualityStatus.DEGRADED
                        ),
                        reasons=quality.reasons
                        + (
                            QualityIssue(
                                code=incomplete_code,
                                message=(
                                    "any_true has an accepted true but incomplete source coverage"
                                    if incomplete_code == "incomplete_any_true_sources"
                                    else "one or more candidate sources are unknown or unavailable"
                                ),
                                field=field_schema.name,
                                source_entity=self._bindings[selected.binding_id].entity_id,
                                since=selected.evidence.received_at,
                                consumer_effect="consumer_must_check_completeness",
                            ),
                        ),
                    )
                qualities[field_schema.name] = quality
                lineage[field_schema.name] = selection.active_binding_ids
                evaluations[field_schema.name] = evaluation
                continue

            value, state, quality = self._apply_fallback(
                contract_id,
                field_schema,
                candidates,
                selection,
                reference,
                source_reason=source_reason,
                quality_override=(
                    QualityStatus.CONFLICT
                    if physical_conflict
                    else None
                ),
            )
            values[field_schema.name] = value
            states[field_schema.name] = state
            qualities[field_schema.name] = quality
            active_binding_ids = (
                () if field_schema.physical_state else selection.active_binding_ids
            )
            lineage[field_schema.name] = active_binding_ids
            evaluations[field_schema.name] = replace(
                evaluation,
                state=state,
                active_binding_ids=active_binding_ids,
            )

        contract = PublishedContract(
            contract_id=contract_id,
            schema_id=schema.schema_id,
            schema_version=schema.version,
            values=values,
            field_states=states,
            field_quality=qualities,
            health=aggregate_health(qualities.values(), schema.required_fields),
            generated_at=reference,
            lineage=lineage,
            field_evaluations=evaluations,
        )
        self._contracts[contract_id] = contract
        source_entities = {
            field_name: tuple(
                self._bindings[binding_id].entity_id
                for binding_id in evaluation.candidate_binding_ids
            )
            for field_name, evaluation in evaluations.items()
        }
        active_source_entities = {
            field_name: tuple(
                self._bindings[binding_id].entity_id
                for binding_id in evaluation.active_binding_ids
            )
            for field_name, evaluation in evaluations.items()
        }
        self._diagnostics[contract_id] = build_diagnostic_projection(
            contract,
            source_entities,
            active_source_entities,
            now=reference,
        )
        self._revision += 1
        self._notify_change()
        return contract

    def _candidate_signals(self, fusion: Fusion | None) -> tuple[AtomicSignal, ...]:
        if fusion is None:
            return ()
        result: list[AtomicSignal] = []
        seen_bindings: set[str] = set()

        def collect(current: Fusion) -> None:
            for binding_id in current.input_binding_ids:
                if binding_id not in seen_bindings and binding_id in self._signals:
                    result.append(self._signals[binding_id])
                    seen_bindings.add(binding_id)
            for fusion_id in current.input_fusion_ids:
                child = self._fusions_by_id.get(fusion_id)
                if child is not None:
                    collect(child)

        collect(fusion)
        return tuple(result)

    @staticmethod
    def _state_without_fresh_value(
        candidates: tuple[AtomicSignal, ...],
        field_schema: ContractFieldSchema,
    ) -> ValueState:
        states = [field_schema.classify(signal.value) for signal in candidates]
        if ValueState.UNKNOWN in states:
            return ValueState.UNKNOWN
        if ValueState.UNAVAILABLE in states:
            return ValueState.UNAVAILABLE
        if ValueState.INVALID in states:
            return ValueState.INVALID
        return ValueState.UNAVAILABLE

    @staticmethod
    def _select_for_fusion(
        fusion: Fusion | None,
        candidates: tuple[AtomicSignal, ...],
        field_schema: ContractFieldSchema,
        now: datetime,
    ) -> _FusionSelection:
        candidate_ids = tuple(signal.binding_id for signal in candidates)
        strategy = fusion.strategy if fusion else "none"
        if fusion is not None and strategy.startswith("opening_"):
            return SignalGraph._select_opening_contacts(
                fusion,
                candidates,
                field_schema,
                now,
            )
        fresh_valid = tuple(
            signal
            for signal in candidates
            if field_schema.classify(signal.value) == ValueState.VALID
            and signal.evidence.freshness(
                now,
                field_schema.freshness_ttl_seconds,
                field_schema.freshness_requirement,
            )[0]
            == FreshnessStatus.FRESH
        )

        if fusion is None:
            return _FusionSelection(
                value=None,
                state=ValueState.UNAVAILABLE,
                selected_signal=None,
                active_binding_ids=(),
                candidate_binding_ids=candidate_ids,
                completeness=False,
                note="fusion_not_configured",
            )

        if strategy == "first_healthy":
            if not fresh_valid:
                return _FusionSelection(
                    value=None,
                    state=SignalGraph._state_without_fresh_value(candidates, field_schema),
                    selected_signal=None,
                    active_binding_ids=(),
                    candidate_binding_ids=candidate_ids,
                    completeness=False,
                    note="no_fresh_valid_source",
                )
            selected = fresh_valid[0]
            distinct_values = {repr(signal.value) for signal in fresh_valid}
            return _FusionSelection(
                value=selected.value,
                state=ValueState.VALID,
                selected_signal=selected,
                active_binding_ids=(selected.binding_id,),
                candidate_binding_ids=candidate_ids,
                completeness=len(distinct_values) <= 1,
                note="conflicting_fresh_sources" if len(distinct_values) > 1 else None,
                conflict=len(distinct_values) > 1,
            )

        if strategy == "latest":
            if not fresh_valid:
                return _FusionSelection(
                    value=None,
                    state=SignalGraph._state_without_fresh_value(candidates, field_schema),
                    selected_signal=None,
                    active_binding_ids=(),
                    candidate_binding_ids=candidate_ids,
                    completeness=False,
                    note="no_fresh_observation_time",
                )
            selected = max(
                fresh_valid,
                key=lambda signal: signal.evidence.effective_timestamp,
            )
            distinct_values = {repr(signal.value) for signal in fresh_valid}
            return _FusionSelection(
                value=selected.value,
                state=ValueState.VALID,
                selected_signal=selected,
                active_binding_ids=(selected.binding_id,),
                candidate_binding_ids=candidate_ids,
                completeness=len(distinct_values) <= 1,
                note="conflicting_fresh_sources" if len(distinct_values) > 1 else None,
                conflict=len(distinct_values) > 1,
            )

        # any_true: only fresh, schema-valid booleans count as valid values.
        true_signals = tuple(signal for signal in fresh_valid if signal.value is True)
        false_signals = tuple(signal for signal in fresh_valid if signal.value is False)
        uncertain = tuple(signal for signal in candidates if signal not in fresh_valid)
        if true_signals:
            return _FusionSelection(
                value=True,
                state=ValueState.VALID,
                selected_signal=true_signals[0],
                active_binding_ids=tuple(signal.binding_id for signal in true_signals),
                candidate_binding_ids=candidate_ids,
                completeness=not uncertain,
                note="incomplete_any_true_sources" if uncertain else None,
            )
        if false_signals and not uncertain:
            return _FusionSelection(
                value=False,
                state=ValueState.VALID,
                selected_signal=false_signals[0],
                active_binding_ids=tuple(signal.binding_id for signal in false_signals),
                candidate_binding_ids=candidate_ids,
                completeness=True,
            )
        if uncertain:
            return _FusionSelection(
                value=None,
                state=ValueState.UNKNOWN,
                selected_signal=None,
                active_binding_ids=(),
                candidate_binding_ids=candidate_ids,
                completeness=False,
                note="unknown_any_true_source",
            )
        return _FusionSelection(
            value=None,
            state=ValueState.UNAVAILABLE,
            selected_signal=None,
            active_binding_ids=(),
            candidate_binding_ids=candidate_ids,
            completeness=False,
            note="no_valid_boolean_source",
        )

    @staticmethod
    def _select_opening_contacts(
        fusion: Fusion,
        candidates: tuple[AtomicSignal, ...],
        field_schema: ContractFieldSchema,
        now: datetime,
    ) -> _FusionSelection:
        """Normalize the two raw contacts used by the opening pilot.

        The raw MQTT entities expose ``on``/``off``.  They are not contract
        values and therefore must never be passed through the enum schema as
        if they were already ``open``/``closed``.  Every physical opening
        result requires both contact signals to be present, fresh and
        unambiguous.  Missing or degraded evidence deliberately falls through
        to the contract's reject fallback.
        """

        candidate_ids = tuple(signal.binding_id for signal in candidates)
        expected_ids = tuple(fusion.input_binding_ids)
        by_id = {signal.binding_id: signal for signal in candidates}
        missing = tuple(binding_id for binding_id in expected_ids if binding_id not in by_id)

        def contact_value(signal: AtomicSignal) -> bool | None:
            if signal.value is True or signal.value == "on":
                return True
            if signal.value is False or signal.value == "off":
                return False
            return None

        contact_signals = tuple(by_id[binding_id] for binding_id in expected_ids if binding_id in by_id)
        contact_values = tuple(contact_value(signal) for signal in contact_signals)
        fresh = tuple(
            signal
            for signal in contact_signals
            if contact_value(signal) is not None
            and signal.evidence.freshness(
                now,
                field_schema.freshness_ttl_seconds,
                field_schema.freshness_requirement,
            )[0]
            == FreshnessStatus.FRESH
        )
        all_contacts_valid = (
            not missing
            and len(contact_signals) == len(expected_ids)
            and all(value is not None for value in contact_values)
        )
        all_contacts_fresh = len(fresh) == len(expected_ids)
        representative = contact_signals[0] if contact_signals else None

        if fusion.strategy == "opening_source_count":
            if missing:
                return _FusionSelection(
                    value=None,
                    state=ValueState.UNKNOWN,
                    selected_signal=None,
                    active_binding_ids=(),
                    candidate_binding_ids=candidate_ids,
                    completeness=False,
                    note="opening_source_missing",
                )
            return _FusionSelection(
                value=len(contact_signals),
                state=ValueState.VALID,
                selected_signal=representative,
                active_binding_ids=candidate_ids,
                candidate_binding_ids=candidate_ids,
                completeness=True,
            )

        if fusion.strategy == "opening_available":
            if not all_contacts_valid or representative is None:
                return _FusionSelection(
                    value=None,
                    state=ValueState.UNAVAILABLE,
                    selected_signal=None,
                    active_binding_ids=(),
                    candidate_binding_ids=candidate_ids,
                    completeness=False,
                    note="opening_source_unavailable",
                )
            if all_contacts_fresh and all(contact_values):
                # Transport availability is not enough to claim that the
                # aggregate opening evidence is usable when the raw contact
                # pair is physically contradictory.
                return _FusionSelection(
                    value=False,
                    state=ValueState.VALID,
                    selected_signal=representative,
                    active_binding_ids=(),
                    candidate_binding_ids=candidate_ids,
                    completeness=False,
                    note="source_conflict",
                    conflict=True,
                )
            return _FusionSelection(
                value=all_contacts_fresh,
                state=ValueState.VALID,
                selected_signal=representative,
                active_binding_ids=candidate_ids if all_contacts_fresh else (),
                candidate_binding_ids=candidate_ids,
                completeness=all_contacts_fresh,
                note=None if all_contacts_fresh else "opening_source_not_fresh",
            )

        if not all_contacts_valid or not all_contacts_fresh:
            return _FusionSelection(
                value=None,
                state=ValueState.UNKNOWN,
                selected_signal=None,
                active_binding_ids=(),
                candidate_binding_ids=candidate_ids,
                completeness=False,
                note=(
                    "opening_source_missing"
                    if missing
                    else "opening_source_not_fresh"
                ),
            )

        if len(contact_values) != 2:
            return _FusionSelection(
                value=None,
                state=ValueState.UNKNOWN,
                selected_signal=None,
                active_binding_ids=(),
                candidate_binding_ids=candidate_ids,
                completeness=False,
                note="opening_source_incomplete",
            )

        open_contact, tilt_contact = contact_values
        if open_contact and tilt_contact:
            return _FusionSelection(
                value=None,
                state=ValueState.UNKNOWN,
                selected_signal=None,
                active_binding_ids=(),
                candidate_binding_ids=candidate_ids,
                completeness=False,
                note="source_conflict",
                conflict=True,
            )

        if fusion.strategy == "opening_is_open":
            value: Any = open_contact
        else:
            value = "open" if open_contact else "tilted" if tilt_contact else "closed"
        return _FusionSelection(
            value=value,
            state=ValueState.VALID,
            selected_signal=representative,
            active_binding_ids=candidate_ids,
            candidate_binding_ids=candidate_ids,
            completeness=True,
        )

    @staticmethod
    def _source_reason(
        selection: _FusionSelection,
        candidates: tuple[AtomicSignal, ...],
        field_schema: ContractFieldSchema,
        now: datetime,
    ) -> str | None:
        """Map failed source evidence to a stable field-scoped reason."""

        if selection.conflict:
            return "source_conflict"
        if not candidates:
            return "source_unavailable"
        if any(
            signal.evidence.restored
            or signal.evidence.origin == FreshnessOrigin.RESTORE
            for signal in candidates
        ):
            return "source_restored"
        if any(
            signal.evidence.retained
            or signal.evidence.origin == FreshnessOrigin.RETAINED_MQTT
            or signal.evidence.freshness(
                now,
                field_schema.freshness_ttl_seconds,
                field_schema.freshness_requirement,
            )[0]
            in {FreshnessStatus.SUSPECT, FreshnessStatus.STALE}
            for signal in candidates
        ):
            return "source_stale"
        return "source_unavailable"

    @staticmethod
    def _annotate_quality(
        quality: FieldQuality,
        field_schema: ContractFieldSchema,
        source_reason: str | None,
        quality_override: QualityStatus | None = None,
        since: datetime | None = None,
    ) -> FieldQuality:
        if source_reason is None:
            return quality
        if any(reason.code == source_reason for reason in quality.reasons):
            return quality
        return replace(
            quality,
            quality=quality_override or quality.quality,
            reasons=quality.reasons
            + (
                QualityIssue(
                    code=source_reason,
                    message=source_reason.replace("_", " "),
                    field=field_schema.name,
                    since=since,
                    blocking=field_schema.required,
                    consumer_effect=(
                        "physical_state_not_claimed"
                        if field_schema.physical_state
                        else "field_evidence_gate"
                    ),
                ),
            ),
        )

    def _apply_fallback(
        self,
        contract_id: str,
        field_schema: ContractFieldSchema,
        candidates: tuple[AtomicSignal, ...],
        selection: _FusionSelection,
        now: datetime,
        *,
        source_reason: str | None = None,
        quality_override: QualityStatus | None = None,
    ) -> tuple[Any, ValueState, FieldQuality]:
        fallback = field_schema.fallback
        last_signal = next(
            (signal for signal in candidates if signal.value is not None),
            None,
        )
        previous = self._contracts.get(contract_id)
        held_value = (
            previous.values.get(field_schema.name)
            if previous is not None
            else None
        )

        if fallback.action == FallbackAction.HOLD_LAST and held_value is not None:
            quality = assess_field_quality(
                field=field_schema.name,
                source_entity=(
                    self._bindings[last_signal.binding_id].entity_id
                    if last_signal
                    else None
                ),
                evidence=last_signal.evidence if last_signal else None,
                has_value=True,
                required=field_schema.required,
                safety_class=field_schema.safety_class,
                fallback=fallback,
                ttl_seconds=field_schema.freshness_ttl_seconds,
                freshness_requirement=field_schema.freshness_requirement,
                now=now,
                last_real_change=last_signal.real_change_at if last_signal else None,
                fallback_active=True,
                physical_state=field_schema.physical_state,
            )
            return held_value, ValueState.UNKNOWN, quality

        if fallback.action == FallbackAction.SAFE_DEFAULT:
            quality = assess_field_quality(
                field=field_schema.name,
                source_entity=None,
                evidence=last_signal.evidence if last_signal else None,
                has_value=False,
                required=field_schema.required,
                safety_class=field_schema.safety_class,
                fallback=fallback,
                ttl_seconds=field_schema.freshness_ttl_seconds,
                freshness_requirement=field_schema.freshness_requirement,
                now=now,
                fallback_active=True,
                physical_state=field_schema.physical_state,
            )
            quality = self._annotate_quality(
                quality,
                field_schema,
                source_reason,
                quality_override,
                last_signal.evidence.received_at if last_signal else None,
            )
            return fallback.default_value, ValueState.UNKNOWN, quality

        quality = assess_field_quality(
            field=field_schema.name,
            source_entity=None,
            evidence=last_signal.evidence if last_signal else None,
            has_value=False,
            required=field_schema.required,
            safety_class=field_schema.safety_class,
            fallback=fallback,
            ttl_seconds=field_schema.freshness_ttl_seconds,
            freshness_requirement=field_schema.freshness_requirement,
            now=now,
            physical_state=field_schema.physical_state,
        )
        if selection.state == ValueState.UNKNOWN:
            state = ValueState.UNKNOWN
        elif field_schema.required:
            state = ValueState.BLOCKED
        elif selection.state == ValueState.INVALID:
            state = ValueState.UNKNOWN
        else:
            state = ValueState.UNAVAILABLE
        quality = self._annotate_quality(
            quality,
            field_schema,
            source_reason,
            quality_override,
            last_signal.evidence.received_at if last_signal else None,
        )
        if field_schema.physical_state:
            return field_schema.unknown_values[0], ValueState.UNKNOWN, quality
        return None, state, quality

    def contract(self, contract_id: str) -> PublishedContract | None:
        return self._contracts.get(contract_id)

    def diagnostic(self, contract_id: str) -> DiagnosticProjection | None:
        return self._diagnostics.get(contract_id)

    def contracts(self) -> tuple[PublishedContract, ...]:
        return tuple(self._contracts.values())

    def diagnostics(self) -> tuple[DiagnosticProjection, ...]:
        return tuple(self._diagnostics.values())

    def snapshot(self, now: datetime | None = None) -> GraphSnapshot:
        reference = now or self._now_factory()
        return GraphSnapshot(
            revision=self._revision,
            bindings=tuple(binding.as_dict() for binding in self._bindings.values()),
            signals=tuple(signal.as_dict(reference) for signal in self._signals.values()),
            fusions=tuple(fusion.as_dict() for fusion in self._fusions_by_id.values()),
            contracts=tuple(contract.as_dict(reference) for contract in self._contracts.values()),
            diagnostics=tuple(
                diagnostic.as_dict(reference) for diagnostic in self._diagnostics.values()
            ),
        )

    @classmethod
    def from_config(cls, config: ConfigModel) -> "SignalGraph":
        graph = cls(profile=config.profile)
        for binding in config.bindings:
            graph.add_binding(binding)
        if config.mode.value == "published":
            from .published import build_pilot_fusions

            graph.add_fusions(build_pilot_fusions(config))
        return graph
