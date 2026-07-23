from __future__ import annotations

import unittest
from datetime import datetime, timezone

from custom_components.benni_core_contracts.contracts import OPENING_V1, ROOM_CLIMATE_V1, TECHNICAL_DEVICE_V1
from custom_components.benni_core_contracts.graph import SignalGraph
from custom_components.benni_core_contracts.quality import FallbackAction, FallbackPolicy
from custom_components.benni_core_contracts.schema import ContractFieldSchema, ValueType


class SchemaAndFallbackTests(unittest.TestCase):
    def test_contract_validation_preserves_explicit_unknown_unavailable_semantics(self) -> None:
        self.assertEqual(
            ROOM_CLIMATE_V1.validate_values({"temperature": "unknown", "available": False}),
            (),
        )
        self.assertEqual(
            ROOM_CLIMATE_V1.validate_values({"temperature": "unavailable", "available": False}),
            (),
        )
        self.assertEqual(
            ROOM_CLIMATE_V1.validate_values({"temperature": None, "available": False}),
            ("invalid value for field: temperature",),
        )

    def test_safe_default_requires_explicit_field_permission_and_reason(self) -> None:
        with self.assertRaises(ValueError):
            ContractFieldSchema(
                name="value",
                value_type=ValueType.BOOLEAN,
                fallback=FallbackPolicy(action=FallbackAction.SAFE_DEFAULT, default_value=False),
            )
        with self.assertRaises(ValueError):
            ContractFieldSchema(
                name="opening_state",
                value_type=ValueType.ENUM,
                allowed_values=("closed", "open"),
                fallback=FallbackPolicy(action=FallbackAction.SAFE_DEFAULT, default_value="closed"),
                safe_default_allowed=True,
                safe_default_note="invalid conservative choice",
                physical_state=True,
            )
        with self.assertRaises(ValueError):
            ContractFieldSchema(
                name="physical_position",
                value_type=ValueType.NUMBER,
                fallback=FallbackPolicy(action=FallbackAction.HOLD_LAST),
                physical_state=True,
            )
        with self.assertRaises(ValueError):
            ContractFieldSchema(
                name="lock_state",
                value_type=ValueType.ENUM,
                allowed_values=("locked", "unlocked"),
                fallback=FallbackPolicy(action=FallbackAction.SAFE_DEFAULT, default_value=False),
                safe_default_allowed=True,
                safe_default_note="locks are never defaulted",
            )
        with self.assertRaises(ValueError):
            ContractFieldSchema(
                name="target_position",
                value_type=ValueType.NUMBER,
                fallback=FallbackPolicy(action=FallbackAction.SAFE_DEFAULT, default_value=0),
                safe_default_allowed=True,
                safe_default_note="positions are never defaulted",
            )

    def test_safe_default_is_diagnosed_and_does_not_claim_freshness(self) -> None:
        now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
        graph = SignalGraph(now_factory=lambda: now)
        opening = graph.evaluate_contract("opening.empty", OPENING_V1.schema_id, now=now)
        self.assertEqual(opening.values["opening_state"], "unknown")
        self.assertEqual(opening.values["is_open"], "unknown")
        self.assertEqual(opening.values["available"], False)
        self.assertEqual(opening.field_quality["opening_state"].freshness.value, "unknown")
        self.assertEqual(opening.field_quality["opening_state"].health.value, "blocked")
        self.assertEqual(opening.field_quality["opening_state"].safety.value, "unknown")
        self.assertTrue(
            any(
                issue.code == "source_unavailable"
                for issue in opening.field_quality["opening_state"].reasons
            )
        )

        technical = graph.evaluate_contract("device.empty", TECHNICAL_DEVICE_V1.schema_id, now=now)
        self.assertFalse(technical.values["available"])
        self.assertEqual(technical.field_quality["available"].health.value, "degraded")
        self.assertEqual(technical.field_quality["available"].freshness.value, "unknown")
