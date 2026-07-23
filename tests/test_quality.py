from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from custom_components.benni_core_contracts.quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessOrigin,
    FreshnessRequirement,
    FreshnessStatus,
    QualityStatus,
    SafetyClass,
    TemporalEvidence,
    assess_field_quality,
)


UTC = timezone.utc


class QualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 22, 20, 0, tzinfo=UTC)

    def test_device_timestamp_can_be_fresh_within_field_ttl(self) -> None:
        evidence = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.DEVICE_TIMESTAMP,
            device_timestamp=self.now - timedelta(seconds=10),
        )
        self.assertEqual(evidence.freshness(self.now, 60)[0], FreshnessStatus.FRESH)
        self.assertTrue(evidence.is_real_measurement_evidence)

    def test_ha_timestamp_requires_a_real_non_retained_state_event(self) -> None:
        initial_state = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.HA_TIMESTAMP,
            ha_timestamp=self.now - timedelta(seconds=10),
        )
        state_event = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.HA_TIMESTAMP,
            ha_timestamp=self.now - timedelta(seconds=10),
            ha_state_event=True,
        )
        self.assertEqual(
            initial_state.freshness(self.now, 60)[0], FreshnessStatus.UNKNOWN
        )
        self.assertEqual(state_event.freshness(self.now, 60)[0], FreshnessStatus.FRESH)
        self.assertFalse(initial_state.is_real_measurement_evidence)
        self.assertTrue(state_event.is_real_measurement_evidence)

    def test_received_at_alone_never_makes_a_value_fresh(self) -> None:
        evidence = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.UNKNOWN,
        )
        self.assertEqual(evidence.freshness(self.now, 60)[0], FreshnessStatus.UNKNOWN)

    def test_retained_mqtt_is_not_fresh(self) -> None:
        evidence = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.RETAINED_MQTT,
            retained=True,
        )
        self.assertEqual(
            evidence.freshness(self.now, 60),
            (FreshnessStatus.SUSPECT, "retained_mqtt_is_not_fresh_evidence"),
        )

    def test_suspect_evidence_degrades_but_does_not_erase_a_value(self) -> None:
        evidence = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.RETAINED_MQTT,
            retained=True,
        )
        quality = assess_field_quality(
            field="value",
            source_entity="sensor.value",
            evidence=evidence,
            has_value=True,
            required=False,
            safety_class=SafetyClass.INFORMATIONAL,
            fallback=FallbackPolicy(),
            ttl_seconds=60,
            now=self.now,
        )
        self.assertEqual(quality.health.value, "degraded")
        self.assertEqual(quality.quality, QualityStatus.SUSPECT)

    def test_restore_is_not_fresh_even_immediately_after_restore(self) -> None:
        evidence = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.RESTORE,
            restored=True,
        )
        self.assertEqual(
            evidence.freshness(self.now, 60)[0], FreshnessStatus.RESTORED
        )

    def test_unknown_and_future_timestamps_are_not_fresh(self) -> None:
        unknown = TemporalEvidence(received_at=self.now, origin=FreshnessOrigin.UNKNOWN)
        future = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.DEVICE_TIMESTAMP,
            device_timestamp=self.now + timedelta(seconds=1),
        )
        self.assertEqual(unknown.freshness(self.now, 60)[0], FreshnessStatus.UNKNOWN)
        self.assertEqual(future.freshness(self.now, 60)[0], FreshnessStatus.SUSPECT)

    def test_safety_field_can_require_a_real_device_timestamp(self) -> None:
        ha_event = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.HA_TIMESTAMP,
            ha_timestamp=self.now,
            ha_state_event=True,
        )
        self.assertEqual(
            ha_event.freshness(
                self.now,
                60,
                FreshnessRequirement.DEVICE_TIMESTAMP_REQUIRED,
            )[0],
            FreshnessStatus.UNKNOWN,
        )

    def test_stale_safety_field_is_degraded_but_value_can_remain_visible(self) -> None:
        evidence = TemporalEvidence(
            received_at=self.now,
            origin=FreshnessOrigin.DEVICE_TIMESTAMP,
            device_timestamp=self.now - timedelta(hours=2),
        )
        quality = assess_field_quality(
            field="opening_state",
            source_entity="binary_sensor.example_window",
            evidence=evidence,
            has_value=True,
            required=True,
            safety_class=SafetyClass.CONSUMER_CRITICAL,
            fallback=FallbackPolicy(action=FallbackAction.REJECT),
            ttl_seconds=60,
            now=self.now,
            physical_state=True,
        )
        self.assertEqual(quality.freshness, FreshnessStatus.STALE)
        self.assertEqual(quality.safety.value, "unsafe")
        self.assertEqual(quality.health.value, "degraded")
        self.assertEqual(quality.quality, QualityStatus.STALE)
