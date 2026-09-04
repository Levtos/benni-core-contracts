"""ConfigEntry flow for shared profiles and the explicit Benni pilot gate."""

from __future__ import annotations

from typing import Any

from .const import (
    CONFIG_SCHEMA_VERSION,
    DEFAULT_PROFILE,
    DOMAIN,
    CONF_BINDINGS,
    CONF_ENTITY_ALLOWLIST,
    CONF_PUBLISHED_CONTRACTS,
    PILOT_OPENING_CONTRACT_ID,
    PILOT_OPENING_ENTITY_ID,
    PILOT_OPENING_OPEN_SOURCE_ENTITY_ID,
    PILOT_OPENING_TILT_SOURCE_ENTITY_ID,
    SUPPORTED_CONFIG_PROFILES,
    SUPPORTED_MODES,
)
from .models import ConfigModel
from .published import pilot_opening_bindings

try:  # Home Assistant is available only when the integration is installed.
    import voluptuous as vol
    from homeassistant.config_entries import ConfigFlow, OptionsFlow
    from homeassistant.helpers import selector

    HA_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by the stdlib-only test environment
    HA_AVAILABLE = False

    class ConfigFlow:  # type: ignore[no-redef]
        pass

    class OptionsFlow:  # type: ignore[no-redef]
        pass


if HA_AVAILABLE:

    def _opening_source_schema():
        """Select only the two read-only sources verified for this pilot."""

        return vol.Schema(
            {
                vol.Required("opening_open_source"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="binary_sensor",
                        include_entities=[
                            PILOT_OPENING_OPEN_SOURCE_ENTITY_ID,
                        ],
                    )
                ),
                vol.Required("opening_tilt_source"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="binary_sensor",
                        include_entities=[
                            PILOT_OPENING_TILT_SOURCE_ENTITY_ID,
                        ],
                    )
                ),
            }
        )


    class BenniCoreContractsConfigFlow(ConfigFlow, domain=DOMAIN):
        VERSION = CONFIG_SCHEMA_VERSION

        async def async_step_user(self, user_input: dict[str, Any] | None = None):
            if user_input is not None:
                # Permit one bootstrap entry per profile while still rejecting
                # duplicate entries for the same profile.
                await self.async_set_unique_id(f"{DOMAIN}:{user_input['profile']}")
                self._abort_if_unique_id_configured()
                if user_input["mode"] == "published":
                    self._selected_profile = user_input["profile"]
                    return await self.async_step_published()
                config = ConfigModel.from_dict(
                    {
                        "schema_version": CONFIG_SCHEMA_VERSION,
                        "profile": user_input["profile"],
                        "mode": user_input["mode"],
                        CONF_ENTITY_ALLOWLIST: (),
                        CONF_PUBLISHED_CONTRACTS: (),
                        CONF_BINDINGS: (),
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

        async def async_step_published(self, user_input: dict[str, Any] | None = None):
            """Require two explicitly selected raw sources for the pilot."""

            if user_input is not None:
                bindings = pilot_opening_bindings(
                    user_input["opening_open_source"],
                    user_input["opening_tilt_source"],
                )
                config = ConfigModel.from_dict(
                    {
                        "schema_version": CONFIG_SCHEMA_VERSION,
                        "profile": self._selected_profile,
                        "mode": "published",
                        CONF_ENTITY_ALLOWLIST: (PILOT_OPENING_ENTITY_ID,),
                        CONF_PUBLISHED_CONTRACTS: (PILOT_OPENING_CONTRACT_ID,),
                        CONF_BINDINGS: tuple(binding.as_dict() for binding in bindings),
                    }
                )
                return self.async_create_entry(
                    title=f"Core Contracts ({config.profile.value})",
                    data=config.as_dict(),
                )

            return self.async_show_form(
                step_id="published",
                data_schema=_opening_source_schema(),
            )

        @staticmethod
        def async_get_options_flow(config_entry):
            return BenniCoreContractsOptionsFlow(config_entry)


    class BenniCoreContractsOptionsFlow(OptionsFlow):
        def __init__(self, config_entry=None) -> None:
            self._config_entry = config_entry

        async def async_step_init(self, user_input: dict[str, Any] | None = None):
            if user_input is not None:
                if user_input["mode"] == "published":
                    return await self.async_step_published()
                return self.async_create_entry(
                    title="",
                    data={
                        "mode": user_input["mode"],
                        CONF_ENTITY_ALLOWLIST: (),
                        CONF_PUBLISHED_CONTRACTS: (),
                        CONF_BINDINGS: (),
                    },
                )
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {vol.Required("mode"): vol.In(SUPPORTED_MODES)}
                ),
            )

        async def async_step_published(self, user_input: dict[str, Any] | None = None):
            if user_input is not None:
                bindings = pilot_opening_bindings(
                    user_input["opening_open_source"],
                    user_input["opening_tilt_source"],
                )
                return self.async_create_entry(
                    title="",
                    data={
                        "mode": "published",
                        CONF_ENTITY_ALLOWLIST: (PILOT_OPENING_ENTITY_ID,),
                        CONF_PUBLISHED_CONTRACTS: (PILOT_OPENING_CONTRACT_ID,),
                        CONF_BINDINGS: tuple(binding.as_dict() for binding in bindings),
                    },
                )
            return self.async_show_form(
                step_id="published",
                data_schema=_opening_source_schema(),
            )

else:

    class BenniCoreContractsConfigFlow(ConfigFlow):  # type: ignore[no-redef]
        VERSION = CONFIG_SCHEMA_VERSION

    class BenniCoreContractsOptionsFlow(OptionsFlow):  # type: ignore[no-redef]
        pass
