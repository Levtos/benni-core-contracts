from __future__ import annotations

import unittest
from datetime import datetime, timezone

from custom_components.benni_core_contracts.config_io import ConfigCodec
from custom_components.benni_core_contracts.const import CONFIG_SCHEMA_VERSION, STORAGE_SCHEMA_VERSION
from custom_components.benni_core_contracts.models import (
    AtomicSignal,
    ConfigModel,
    ProfileId,
    RuntimeMode,
    SourceBinding,
)
from custom_components.benni_core_contracts.quality import (
    FallbackAction,
    FieldQuality,
    FreshnessOrigin,
    FreshnessStatus,
    HealthStatus,
    SafetyStatus,
    TemporalEvidence,
)
from custom_components.benni_core_contracts.storage import (
    RestoreMarker,
    StorageCodec,
    StorageError,
    restored_evidence,
)


UTC = timezone.utc


class StorageTests(unittest.TestCase):
    def test_config_entry_is_the_only_config_import_export_boundary(self) -> None:
        config = ConfigModel(
            profile=ProfileId.BENNI,
            mode=RuntimeMode.SHADOW_ONLY,
            bindings=(
                SourceBinding(
                    binding_id="climate_temperature",
                    source_id="living_temperature",
                    entity_id="sensor.living_temperature",
                    field="temperature",
                    capability="room_climate",
                ),
            ),
        )
        exported = ConfigCodec.export_config(config)
        self.assertEqual(exported["config_version"], CONFIG_SCHEMA_VERSION)
        self.assertNotIn("runtime_state", exported)
        imported = ConfigCodec.import_config(exported)
        self.assertEqual(imported.bindings[0].binding_id, "climate_temperature")

    def test_runtime_storage_contains_no_config(self) -> None:
        encoded = StorageCodec.encode()
        self.assertEqual(encoded["storage_version"], STORAGE_SCHEMA_VERSION)
        self.assertNotIn("config", encoded)
        self.assertEqual(encoded["runtime_state"], {"signals": [], "restore_markers": [], "diagnostics": []})

    def test_runtime_signal_keeps_original_evidence_as_history_only(self) -> None:
        evidence = TemporalEvidence(
            received_at=datetime(2026, 7, 22, 19, 0, tzinfo=UTC),
            origin=FreshnessOrigin.DEVICE_TIMESTAMP,
            device_timestamp=datetime(2026, 7, 22, 18, 59, tzinfo=UTC),
        )
        signal = AtomicSignal(
            signal_id="atomic:x",
            binding_id="x",
            field="value",
            value=42,
            evidence=evidence,
            quality=FieldQuality(
                health=HealthStatus.HEALTHY,
                freshness=FreshnessStatus.FRESH,
                safety=SafetyStatus.VALID,
                fallback=FallbackAction.NONE,
            ),
        )
        marker = RestoreMarker(
            binding_id="x",
            restored_at=datetime(2026, 7, 22, 20, 0, tzinfo=UTC),
        )
        payload = StorageCodec.encode((signal,), (marker,), ({"field": "value"},))
        envelope = StorageCodec.decode(payload)
        self.assertEqual(envelope.signals[0].original_evidence.origin, FreshnessOrigin.DEVICE_TIMESTAMP)
        self.assertEqual(envelope.signals[0].value, 42)
        self.assertEqual(envelope.restore_markers[0].binding_id, "x")
        self.assertEqual(envelope.diagnostics[0]["field"], "value")

        restored = restored_evidence(datetime(2026, 7, 22, 20, 0, tzinfo=UTC))
        self.assertEqual(restored.freshness(datetime(2026, 7, 22, 20, 0, tzinfo=UTC), 60)[0], FreshnessStatus.RESTORED)

    def test_config_contamination_and_future_storage_version_are_rejected(self) -> None:
        with self.assertRaises(StorageError):
            StorageCodec.decode({"storage_version": STORAGE_SCHEMA_VERSION, "config": {}})
        with self.assertRaises(StorageError):
            StorageCodec.decode(
                {"storage_version": 99, "runtime_state": {"signals": []}}
            )
        with self.assertRaises(ValueError):
            ConfigCodec.import_config(
                {
                    "config_version": CONFIG_SCHEMA_VERSION,
                    "config": {},
                    "runtime_state": {},
                }
            )
