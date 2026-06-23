"""KNMI Hittekracht custom component.

Based on:
Marghidan, C. P., van der Schrier, G., van den Besselaar, E., Vrolijk, M., Boonstra, R., van Ekris, J., Nuijens, W., Mokkenstorm, L., Siegmund, P., Reiling, M., Groeneweg, F., Matters, I., Camps, J., van Paassen, J., & Sluijter, R. (2026). Van Wet Bulb Globe Temperature (WBGT) naar hittekracht (Technical Report No. TR-26-04). Koninklijk Nederlands Meteorologisch Instituut (KNMI).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KNMI Hittekracht from a config entry."""
    # Combine data and options to allow options updates to override data
    config = {**entry.data, **entry.options}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = config

    # Register update listener to reload when options change
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
