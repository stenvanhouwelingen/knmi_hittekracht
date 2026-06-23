"""Config flow for KNMI Hittekracht custom component.

Based on:
Marghidan, C. P., van der Schrier, G., van den Besselaar, E., Vrolijk, M., Boonstra, R., van Ekris, J., Nuijens, W., Mokkenstorm, L., Siegmund, P., Reiling, M., Groeneweg, F., Matters, I., Camps, J., van Paassen, J., & Sluijter, R. (2026). Van Wet Bulb Globe Temperature (WBGT) naar hittekracht (Technical Report No. TR-26-04). Koninklijk Nederlands Meteorologisch Instituut (KNMI).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_FORCE_SHADE,
    CONF_HUM_ENTITY,
    CONF_SOLAR_ENTITY,
    CONF_TEMP_ENTITY,
    CONF_WIND_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class KNMIHittekrachtConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KNMI Hittekracht."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            unique_id = f"knmi_hittekracht_{user_input[CONF_TEMP_ENTITY]}_{user_input[CONF_HUM_ENTITY]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Retrieve clean name for integration
            temp_name = user_input[CONF_TEMP_ENTITY].split(".")[-1]
            return self.async_create_entry(
                title=f"KNMI Hittekracht ({temp_name})",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_TEMP_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "temperature"},
                            {"domain": "weather"},
                            {"domain": "climate"},
                        ]
                    )
                ),
                vol.Required(CONF_HUM_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "humidity"},
                            {"domain": "weather"},
                            {"domain": "climate"},
                        ]
                    )
                ),
                vol.Optional(CONF_WIND_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "wind_speed"},
                            {"domain": "sensor", "device_class": "speed"},
                            {"domain": "weather"},
                        ]
                    )
                ),
                vol.Optional(CONF_SOLAR_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "irradiance"},
                        ]
                    )
                ),
                vol.Required(
                    CONF_FORCE_SHADE, default=False
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return KNMIHittekrachtOptionsFlowHandler()


class KNMIHittekrachtOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for KNMI Hittekracht."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TEMP_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_TEMP_ENTITY, self.config_entry.data.get(CONF_TEMP_ENTITY)
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "temperature"},
                            {"domain": "weather"},
                            {"domain": "climate"},
                        ]
                    )
                ),
                vol.Required(
                    CONF_HUM_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_HUM_ENTITY, self.config_entry.data.get(CONF_HUM_ENTITY)
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "humidity"},
                            {"domain": "weather"},
                            {"domain": "climate"},
                        ]
                    )
                ),
                vol.Optional(
                    CONF_WIND_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_WIND_ENTITY, self.config_entry.data.get(CONF_WIND_ENTITY)
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "wind_speed"},
                            {"domain": "sensor", "device_class": "speed"},
                            {"domain": "weather"},
                        ]
                    )
                ),
                vol.Optional(
                    CONF_SOLAR_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_SOLAR_ENTITY, self.config_entry.data.get(CONF_SOLAR_ENTITY)
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        filter=[
                            {"domain": "sensor", "device_class": "irradiance"},
                        ]
                    )
                ),
                vol.Required(
                    CONF_FORCE_SHADE,
                    default=self.config_entry.options.get(
                        CONF_FORCE_SHADE,
                        self.config_entry.data.get(CONF_FORCE_SHADE, False),
                    ),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
