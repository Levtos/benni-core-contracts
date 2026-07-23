"""Versioned runtime storage; ConfigEntry remains the only config owner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Protocol

from .const import STORAGE_SCHEMA_VERSION
from .models import AtomicSignal
from .quality import TemporalEvidence, utc_now


class StorageError(ValueError):
    """Invalid, stale, or configuration-contaminated runtime storage."""


@dataclass(frozen=True)
class StoredSignal:
    binding_id: str
    value: Any
    original_evidence: TemporalEvidence
    stored_at: datetime


@dataclass(frozen=True)
class RestoreMarker:
    binding_id: str
    restored_at: datetime
    reason: str = "config_entry_reload"

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "restored_at": self.restored_at.isoformat(),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class StorageEnvelope:
    storage_version: int
    signals: tuple[StoredSignal, ...] = ()
    restore_markers: tuple[RestoreMarker, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()


class StorageCodec:
    """Encode/decode Runtime-State only.

    A ``config`` key is rejected deliberately. Config import/export belongs to
    ``ConfigCodec`` and the ConfigEntry, never to the HA Store.
    """

    @staticmethod
    def encode(
        signals: Iterable[AtomicSignal] = (),
        restore_markers: Iterable[RestoreMarker] = (),
        diagnostics: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        return {
            "storage_version": STORAGE_SCHEMA_VERSION,
            "runtime_state": {
                "signals": [
                    {
                        "binding_id": signal.binding_id,
                        "value": signal.value,
                        "original_evidence": signal.evidence.as_dict(),
                        "stored_at": signal.evidence.received_at.isoformat(),
                    }
                    for signal in signals
                ],
                "restore_markers": [marker.as_dict() for marker in restore_markers],
                "diagnostics": list(diagnostics),
            },
        }

    @staticmethod
    def decode(data: dict[str, Any] | None) -> StorageEnvelope:
        if not data:
            raise StorageError("empty storage payload")
        if "config" in data or "config_entry" in data:
            raise StorageError("config_source_forbidden_in_runtime_store")
        version = int(data.get("storage_version", 0))
        if version != STORAGE_SCHEMA_VERSION:
            raise StorageError(f"unsupported runtime storage version: {version}")
        runtime_state = data.get("runtime_state")
        if not isinstance(runtime_state, dict):
            raise StorageError("runtime_state object is required")
        allowed_keys = {"signals", "restore_markers", "diagnostics"}
        if set(runtime_state) - allowed_keys:
            raise StorageError("runtime_state contains configuration or unknown fields")
        try:
            signals = tuple(
                StoredSignal(
                    binding_id=str(value["binding_id"]),
                    value=value.get("value"),
                    original_evidence=TemporalEvidence.from_dict(value["original_evidence"]),
                    stored_at=datetime.fromisoformat(value["stored_at"]),
                )
                for value in runtime_state.get("signals", ())
            )
            markers = tuple(
                RestoreMarker(
                    binding_id=str(value["binding_id"]),
                    restored_at=datetime.fromisoformat(value["restored_at"]),
                    reason=str(value.get("reason", "config_entry_reload")),
                )
                for value in runtime_state.get("restore_markers", ())
            )
        except (KeyError, TypeError, ValueError) as err:
            raise StorageError(f"invalid runtime storage payload: {err}") from err
        diagnostics = tuple(
            value for value in runtime_state.get("diagnostics", ()) if isinstance(value, dict)
        )
        return StorageEnvelope(version, signals, markers, diagnostics)


def restored_evidence(now: datetime | None = None) -> TemporalEvidence:
    """Create explicit non-fresh evidence for a restored shadow value."""

    from .quality import FreshnessOrigin

    return TemporalEvidence(
        received_at=now or utc_now(),
        origin=FreshnessOrigin.RESTORE,
        restored=True,
    )


class AsyncStorageBackend(Protocol):
    async def async_load(self) -> dict[str, Any] | None: ...

    async def async_save(self, data: dict[str, Any]) -> None: ...


class InMemoryStorageBackend:
    """Small test backend for the HA Store adapter contract."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data

    async def async_load(self) -> dict[str, Any] | None:
        return self.data

    async def async_save(self, data: dict[str, Any]) -> None:
        self.data = data


class HomeAssistantStorage:
    """Lazy adapter around Home Assistant's Store, kept out of the domain model."""

    def __init__(self, hass: Any, key: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store(hass, STORAGE_SCHEMA_VERSION, key)

    async def async_load(self) -> dict[str, Any] | None:
        return await self._store.async_load()

    async def async_save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)
