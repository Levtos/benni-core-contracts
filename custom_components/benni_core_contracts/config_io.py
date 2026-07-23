"""Explicit ConfigEntry import/export boundary."""

from __future__ import annotations

from typing import Any

from .const import CONFIG_SCHEMA_VERSION
from .models import ConfigModel


class ConfigCodec:
    """Serialize only the canonical ConfigEntry configuration."""

    @staticmethod
    def export_config(config: ConfigModel) -> dict[str, Any]:
        return {
            "config_version": CONFIG_SCHEMA_VERSION,
            "config": config.as_dict(),
        }

    @staticmethod
    def import_config(payload: dict[str, Any]) -> ConfigModel:
        if set(payload) != {"config_version", "config"}:
            raise ValueError("config import may contain only config_version and config")
        if int(payload["config_version"]) != CONFIG_SCHEMA_VERSION:
            raise ValueError("unsupported config import version")
        if not isinstance(payload["config"], dict):
            raise ValueError("config import body must be an object")
        allowed_keys = {
            "schema_version",
            "profile",
            "mode",
            "entity_allowlist",
            "bindings",
        }
        if set(payload["config"]) - allowed_keys:
            raise ValueError("config import contains runtime or unknown fields")
        return ConfigModel.from_dict(payload["config"])
