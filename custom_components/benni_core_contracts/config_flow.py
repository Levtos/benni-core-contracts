"""ConfigEntry flow for an explicit, read-only shadow-only installation."""

from __future__ import annotations

from typing import Any

from .const import (
    CONFIG_SCHEMA_VERSION,
    DEFAULT_PROFILE,
    DOMAIN,
    MODE_SHADOW_ONLY,
    SUPPORTED_CONFIG_PROFILES,
    SUPPORTED_MODES,
)
from .models import ConfigModel

try:  # Home Assistant is available only when the integration is installed.
    import voluptuous as vol
    from homeassistant.config_entries import ConfigFlow, OptionsFlow

    HA_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by the stdlib-only test environment
    HA_AVAILABLE = False

    class ConfigFlow:  # type: ignore[no-redef]
        pass

    class OptionsFlow:  # type: ignore[no-redef]
        pass


if HA_AVAILABLE:

    class BenniCoreContractsConfigFlow(ConfigFlow, domain=DOMAIN):
        VERSION = CONFIG_SCHEMA_VERSION

        async def async_step_user(self, user_input: dict[str, Any] | None = None):
            if user_input is not None:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                config = ConfigModel.from_dict(
                    {
                        "schema_version": CONFIG_SCHEMA_VERSION,
                        "profile": user_input["profile"],
                        "mode": user_input["mode"],
                        "entity_allowlist": (),
                        "bindings": (),
                    }
                )
                return self.async_create_entry(
                    title=f"Core Contracts ({config.profile.value})",
                    data=config.as_dict(),
                )

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile", default=DEFAULT_PROFILE): vol.In(
                            SUPPORTED_CONFIG_PROFILES
                        ),
                        vol.Required("mode"): vol.In(SUPPORTED_MODES),
                    }
                ),
            )

        @staticmethod
        def async_get_options_flow(config_entry):
            return BenniCoreContractsOptionsFlow()


    class BenniCoreContractsOptionsFlow(OptionsFlow):
        async def async_step_init(self, user_input: dict[str, Any] | None = None):
            if user_input is not None:
                return self.async_create_entry(
                    title="",
                    data={"mode": user_input["mode"]},
                )
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {vol.Required("mode"): vol.In(SUPPORTED_MODES)}
                ),
            )

else:

    class BenniCoreContractsConfigFlow(ConfigFlow):  # type: ignore[no-redef]
        VERSION = CONFIG_SCHEMA_VERSION

    class BenniCoreContractsOptionsFlow(OptionsFlow):  # type: ignore[no-redef]
        pass
