"""Sensor platform for KNMI Hittekracht custom component.

Based on:
Marghidan, C. P., van der Schrier, G., van den Besselaar, E., Vrolijk, M., Boonstra, R., van Ekris, J., Nuijens, W., Mokkenstorm, L., Siegmund, P., Reiling, M., Groeneweg, F., Matters, I., Camps, J., van Paassen, J., & Sluijter, R. (2026). Van Wet Bulb Globe Temperature (WBGT) naar hittekracht (Technical Report No. TR-26-04). Koninklijk Nederlands Meteorologisch Instituut (KNMI).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

from .const import (
    CONF_FORCE_SHADE,
    CONF_HUM_ENTITY,
    CONF_SOLAR_ENTITY,
    CONF_TEMP_ENTITY,
    CONF_WIND_ENTITY,
    DOMAIN,
    HITTEKRACHT_LEVELS,
)
from .knmi_heatindex_engine import calculate_hittekracht

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KNMI Hittekracht sensors from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    coordinator = KNMIHittekrachtData(hass, entry_data)
    coordinator.update_data()

    temp_entity_id = entry_data[CONF_TEMP_ENTITY]
    temp_name = temp_entity_id.split(".")[-1]

    entities = [
        KNMIHittekrachtWBGTSensor(coordinator, entry.entry_id, temp_name),
        KNMIHittekrachtIndexSensor(coordinator, entry.entry_id, temp_name),
    ]

    async_add_entities(entities)

    # Collect all entities we want to listen to for changes
    entity_ids = [entry_data[CONF_TEMP_ENTITY], entry_data[CONF_HUM_ENTITY]]
    if entry_data.get(CONF_WIND_ENTITY):
        entity_ids.append(entry_data[CONF_WIND_ENTITY])
    if entry_data.get(CONF_SOLAR_ENTITY):
        entity_ids.append(entry_data[CONF_SOLAR_ENTITY])

    @callback
    def _async_state_change_listener(event: Any) -> None:
        """Handle tracked state changes."""
        _LOGGER.debug("KNMI Hittekracht: Source entity changed. Re-calculating.")
        coordinator.update_data()
        coordinator.notify_listeners()

    # Track state changes of target entities and trigger updates
    entry.async_on_unload(
        async_track_state_change_event(hass, entity_ids, _async_state_change_listener)
    )


class KNMIHittekrachtData:
    """Manages the state and calculations for the KNMI Hittekracht integration."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        """Initialize the data coordinator."""
        self.hass = hass
        self.entry_data = entry_data

        # Source Entity IDs
        self.temp_entity = entry_data[CONF_TEMP_ENTITY]
        self.hum_entity = entry_data[CONF_HUM_ENTITY]
        self.wind_entity = entry_data.get(CONF_WIND_ENTITY)
        self.solar_entity = entry_data.get(CONF_SOLAR_ENTITY)
        self.force_shade = entry_data.get(CONF_FORCE_SHADE, False)

        # Output values
        self.wbgt: float | None = None
        self.hittekracht_index: int | None = None
        self.scenario: str = "Scenario C"
        self.estimated_solar: float | None = None
        self.estimated_wind: float | None = None

        # List of listeners to notify
        self.listeners: list[Any] = []

    def register_listener(self, listener: Any) -> None:
        """Register a callback listener."""
        self.listeners.append(listener)

    def remove_listener(self, listener: Any) -> None:
        """Remove a callback listener."""
        if listener in self.listeners:
            self.listeners.remove(listener)

    def notify_listeners(self) -> None:
        """Notify all registered listeners."""
        for listener in self.listeners:
            listener()

    def _get_temperature(self) -> float | None:
        """Get the temperature in Celsius from the configured entity."""
        state = self.hass.states.get(self.temp_entity)
        if state is None:
            return None

        val: float | None = None
        source_unit = state.attributes.get("unit_of_measurement")

        # 1. Try state directly (if it's a sensor/climate/weather)
        if state.state not in (None, "unknown", "unavailable"):
            try:
                val = float(state.state)
            except ValueError:
                pass

        # 2. Try attributes (for weather, climate etc.)
        if val is None:
            for attr in ("temperature", "current_temperature"):
                if attr in state.attributes:
                    try:
                        val = float(state.attributes[attr])
                        break
                    except (ValueError, TypeError):
                        pass

        if val is None:
            return None

        # Determine unit
        unit = source_unit
        if unit is None:
            unit = state.attributes.get("temperature_unit")
        if unit is None:
            unit = self.hass.config.units.temperature_unit

        # Convert to Celsius if needed
        if unit != UnitOfTemperature.CELSIUS:
            try:
                val = TemperatureConverter.convert(val, unit, UnitOfTemperature.CELSIUS)
            except Exception as err:
                _LOGGER.error(
                    "Error converting temperature from %s to Celsius: %s", unit, err
                )

        return val

    def _get_humidity(self) -> float | None:
        """Get the humidity from the configured entity."""
        state = self.hass.states.get(self.hum_entity)
        if state is None:
            return None

        val: float | None = None

        # 1. Try state directly
        if state.state not in (None, "unknown", "unavailable"):
            try:
                val = float(state.state)
            except ValueError:
                pass

        # 2. Try attributes
        if val is None:
            if "humidity" in state.attributes:
                try:
                    val = float(state.attributes["humidity"])
                except (ValueError, TypeError):
                    pass

        return val

    def _get_wind_speed(self) -> float | None:
        """Get the wind speed in m/s from the configured entity."""
        if not self.wind_entity:
            return None

        state = self.hass.states.get(self.wind_entity)
        if state is None:
            return None

        val: float | None = None
        source_unit = state.attributes.get("unit_of_measurement")

        # 1. Try state directly (if it's a sensor)
        if state.state not in (None, "unknown", "unavailable"):
            try:
                val = float(state.state)
            except ValueError:
                pass

        # 2. Try attributes (for weather etc.)
        if val is None:
            if "wind_speed" in state.attributes:
                try:
                    val = float(state.attributes["wind_speed"])
                except (ValueError, TypeError):
                    pass

        if val is None:
            return None

        # Determine unit
        unit = source_unit
        if unit is None:
            unit = state.attributes.get("wind_speed_unit")
        if unit is None:
            unit = self.hass.config.units.wind_speed_unit

        # Convert to m/s if needed
        if unit != UnitOfSpeed.METERS_PER_SECOND:
            try:
                val = SpeedConverter.convert(val, unit, UnitOfSpeed.METERS_PER_SECOND)
            except Exception as err:
                _LOGGER.error(
                    "Error converting wind speed from %s to m/s: %s", unit, err
                )

        return val

    def _get_solar_radiation(self) -> float | None:
        """Get solar radiation in W/m² from the configured entity."""
        if not self.solar_entity:
            return None

        state = self.hass.states.get(self.solar_entity)
        if state is None:
            return None

        # Try state directly
        if state.state not in (None, "unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                pass

        return None

    def update_data(self) -> None:
        """Run calculations based on current entity states."""
        # 1. Fetch values
        temp = self._get_temperature()
        hum = self._get_humidity()

        if temp is None or hum is None:
            _LOGGER.warning(
                "KNMI Hittekracht: Temperature or Humidity is unavailable. Calculation skipped."
            )
            self.wbgt = None
            self.hittekracht_index = None
            return

        wind = self._get_wind_speed()
        solar = self._get_solar_radiation()

        # Get coordinates and current time from HA config
        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude
        dt_utc = datetime.datetime.now(datetime.UTC)

        # Run calculation engine
        try:
            result = calculate_hittekracht(
                temperature=temp,
                humidity=hum,
                wind_speed=wind,
                solar_radiation=solar,
                force_shade=self.force_shade,
                latitude=latitude,
                longitude=longitude,
                dt_utc=dt_utc,
            )
            self.wbgt = round(result["wbgt"], 2)
            self.hittekracht_index = result["hittekracht_index"]
            self.scenario = result["scenario"]
            self.estimated_solar = (
                round(result["estimated_solar"], 1)
                if result["estimated_solar"] is not None
                else None
            )
            self.estimated_wind = (
                round(result["estimated_wind"], 2)
                if result["estimated_wind"] is not None
                else None
            )
        except Exception:
            _LOGGER.exception("Error executing KNMI Hittekracht calculation engine")
            self.wbgt = None
            self.hittekracht_index = None


class KNMIHittekrachtWBGTSensor(SensorEntity):
    """Estimated WBGT sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"
    _attr_suggested_display_precision = 2
    _attr_translation_key = "wbgt"
    _attr_icon = "mdi:sun-thermometer"
    _attr_attribution = (
        "Calculated by Sten van Houwelingen using the KNMI TR-26-04 framework"
    )

    def __init__(
        self, coordinator: KNMIHittekrachtData, entry_id: str, temp_name: str
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._temp_name = temp_name
        self._attr_unique_id = f"{entry_id}_estimated_wbgt"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._coordinator.register_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self._coordinator.remove_listener(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.wbgt is not None

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._coordinator.wbgt

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"KNMI Hittekracht ({self._temp_name})",
            manufacturer="Sten van Houwelingen",
            model="Hittekracht Index",
            sw_version="2026.6.23",
        )


class KNMIHittekrachtIndexSensor(SensorEntity):
    """KNMI Hittekracht Index sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 0
    _attr_translation_key = "index"
    _attr_icon = "mdi:sun-thermometer"
    _attr_attribution = (
        "Calculated by Sten van Houwelingen using the KNMI TR-26-04 framework"
    )

    def __init__(
        self, coordinator: KNMIHittekrachtData, entry_id: str, temp_name: str
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._temp_name = temp_name
        self._attr_unique_id = f"{entry_id}_hittekracht_index"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._coordinator.register_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self._coordinator.remove_listener(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.hittekracht_index is not None

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._coordinator.hittekracht_index

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self._coordinator.hittekracht_index is None:
            return {}

        # Get language (nl/en) based on Home Assistant's configuration
        lang = "en"
        if self.hass.config.language == "nl":
            lang = "nl"

        level_info = HITTEKRACHT_LEVELS.get(
            self._coordinator.hittekracht_index, {}
        ).get(lang, {})

        return {
            "level": level_info.get("label"),
            "description": level_info.get("desc"),
            "calculation_scenario": self._coordinator.scenario,
            "estimated_solar_radiation": self._coordinator.estimated_solar,
            "estimated_wind_speed": self._coordinator.estimated_wind,
            "source_temperature_entity": self._coordinator.temp_entity,
            "source_humidity_entity": self._coordinator.hum_entity,
            "source_wind_entity": self._coordinator.wind_entity,
            "source_solar_entity": self._coordinator.solar_entity,
            "force_shade": self._coordinator.force_shade,
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"KNMI Hittekracht ({self._temp_name})",
            manufacturer="Sten van Houwelingen",
            model="Hittekracht Index",
            sw_version="2026.6.23",
        )
