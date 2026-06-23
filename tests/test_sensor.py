"""Test suite for the KNMI Hittekracht Home Assistant sensor platform."""

import datetime
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add custom_components directory to path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../custom_components"))
)

from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import State
from knmi_hittekracht import async_setup_entry, async_unload_entry
from knmi_hittekracht.const import DOMAIN
from knmi_hittekracht.sensor import (
    KNMIHittekrachtData,
    KNMIHittekrachtIndexSensor,
    KNMIHittekrachtWBGTSensor,
)
from knmi_hittekracht.sensor import (
    async_setup_entry as async_setup_sensor_entry,
)


class MockDateTime(datetime.datetime):
    """Mock datetime.datetime to return a fixed noon UTC time."""

    @classmethod
    def now(cls, tz=None):
        """Return a fixed noon UTC datetime for testing."""
        return datetime.datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.UTC)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {}

    # Mock global config values
    hass.config.latitude = 52.3676
    hass.config.longitude = 4.9041
    hass.config.language = "nl"
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS
    hass.config.units.wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    # Mock config entries sub-system
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    # Mock states registry
    states_dict = {}

    def get_state(entity_id):
        return states_dict.get(entity_id)

    hass.states.get = MagicMock(side_effect=get_state)
    hass.states_dict = states_dict

    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry instance."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "temperature_entity": "sensor.temp",
        "humidity_entity": "sensor.hum",
        "wind_entity": "sensor.wind",
        "solar_entity": "sensor.solar",
        "force_shade": False,
    }
    entry.options = {}
    entry.async_on_unload = MagicMock()
    return entry


def test_coordinator_extraction_and_conversion(mock_hass):
    """Test value extraction and unit conversion in KNMIHittekrachtData."""
    entry_data = {
        "temperature_entity": "sensor.temp",
        "humidity_entity": "sensor.hum",
        "wind_entity": "sensor.wind",
        "solar_entity": "sensor.solar",
        "force_shade": False,
    }

    coordinator = KNMIHittekrachtData(mock_hass, entry_data)

    # 1. Setup mock states with different units
    # Temp in Fahrenheit: 77°F = 25.0°C
    mock_hass.states_dict["sensor.temp"] = State(
        "sensor.temp", "77.0", {"unit_of_measurement": UnitOfTemperature.FAHRENHEIT}
    )
    # Humidity: 50%
    mock_hass.states_dict["sensor.hum"] = State(
        "sensor.hum", "50.0", {"unit_of_measurement": "%"}
    )
    # Wind speed in km/h: 18 km/h = 5.0 m/s
    mock_hass.states_dict["sensor.wind"] = State(
        "sensor.wind", "18.0", {"unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR}
    )
    # Solar: 500 W/m²
    mock_hass.states_dict["sensor.solar"] = State(
        "sensor.solar", "500.0", {"unit_of_measurement": "W/m²"}
    )

    # 2. Extract values and assert conversions
    assert coordinator._get_temperature() == 25.0
    assert coordinator._get_humidity() == 50.0
    assert coordinator._get_wind_speed() == 5.0
    assert coordinator._get_solar_radiation() == 500.0

    # 3. Trigger data update and check scenario A with mocked daytime
    with patch("knmi_hittekracht.sensor.datetime.datetime", MockDateTime):
        coordinator.update_data()

    assert coordinator.wbgt is not None
    assert coordinator.hittekracht_index is not None
    assert coordinator.scenario == "Scenario A"
    assert coordinator.estimated_solar == 500.0
    assert coordinator.estimated_wind == 5.0


def test_coordinator_fallback_scenarios(mock_hass):
    """Test fallback calculation scenarios when sensors are missing."""
    entry_data = {
        "temperature_entity": "sensor.temp",
        "humidity_entity": "sensor.hum",
        "wind_entity": None,
        "solar_entity": None,
        "force_shade": False,
    }

    coordinator = KNMIHittekrachtData(mock_hass, entry_data)

    # Setup mock states
    mock_hass.states_dict["sensor.temp"] = State(
        "sensor.temp", "25.0", {"unit_of_measurement": UnitOfTemperature.CELSIUS}
    )
    mock_hass.states_dict["sensor.hum"] = State(
        "sensor.hum", "50.0", {"unit_of_measurement": "%"}
    )

    coordinator.update_data()
    assert coordinator.wbgt is not None
    assert coordinator.hittekracht_index is not None
    assert coordinator.scenario == "Scenario C"  # No wind and no solar -> Scenario C
    assert coordinator.estimated_solar is None
    assert coordinator.estimated_wind is None


def test_sensor_availability(mock_hass):
    """Test sensor availability states based on coordinator calculations."""
    entry_data = {
        "temperature_entity": "sensor.temp",
        "humidity_entity": "sensor.hum",
        "force_shade": False,
    }
    coordinator = KNMIHittekrachtData(mock_hass, entry_data)

    wbgt_sensor = KNMIHittekrachtWBGTSensor(coordinator, "entry_id", "temp")
    index_sensor = KNMIHittekrachtIndexSensor(coordinator, "entry_id", "temp")

    # Before update (no values)
    assert not wbgt_sensor.available
    assert not index_sensor.available

    # Unavailable state in source sensor
    mock_hass.states_dict["sensor.temp"] = State("sensor.temp", "unavailable")
    mock_hass.states_dict["sensor.hum"] = State("sensor.hum", "50.0")
    coordinator.update_data()

    assert not wbgt_sensor.available
    assert not index_sensor.available
    assert wbgt_sensor.native_value is None
    assert index_sensor.native_value is None

    # Recovered state
    mock_hass.states_dict["sensor.temp"] = State("sensor.temp", "25.0")
    coordinator.update_data()

    assert wbgt_sensor.available
    assert index_sensor.available
    assert wbgt_sensor.native_value == coordinator.wbgt
    assert index_sensor.native_value == coordinator.hittekracht_index


@pytest.mark.anyio
async def test_async_setup_and_unload_entry(mock_hass, mock_config_entry):
    """Test config entry loading and unloading."""
    # 1. Setup entry
    assert await async_setup_entry(mock_hass, mock_config_entry)
    assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
    assert mock_config_entry.async_on_unload.call_count == 1

    # 2. Setup sensor platform
    async_add_entities = MagicMock()
    await async_setup_sensor_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 1
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert isinstance(entities[0], KNMIHittekrachtWBGTSensor)
    assert isinstance(entities[1], KNMIHittekrachtIndexSensor)

    # 3. Unload entry
    assert await async_unload_entry(mock_hass, mock_config_entry)
    assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]


@pytest.mark.anyio
async def test_config_flow():
    """Test user setup config flow."""
    from knmi_hittekracht.config_flow import KNMIHittekrachtConfigFlow

    flow = KNMIHittekrachtConfigFlow()
    flow.hass = MagicMock()

    # Test initial form display
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Test form submission
    user_input = {
        "temperature_entity": "sensor.temp",
        "humidity_entity": "sensor.hum",
        "wind_entity": "sensor.wind",
        "solar_entity": "sensor.solar",
        "force_shade": False,
    }

    with (
        patch.object(flow, "async_set_unique_id", return_value=None),
        patch.object(flow, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == "KNMI Hittekracht (temp)"
    assert result["data"] == user_input


@pytest.mark.anyio
async def test_options_flow(mock_config_entry):
    """Test options flow handler."""
    from knmi_hittekracht.config_flow import KNMIHittekrachtOptionsFlowHandler

    flow = KNMIHittekrachtOptionsFlowHandler()
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )
    flow.handler = mock_config_entry.entry_id

    # Test form display
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # Test options update submission
    user_input = {
        "temperature_entity": "sensor.temp_new",
        "humidity_entity": "sensor.hum_new",
        "wind_entity": "sensor.wind_new",
        "solar_entity": "sensor.solar_new",
        "force_shade": True,
    }

    result = await flow.async_step_init(user_input)
    assert result["type"] == "create_entry"
    assert result["title"] == ""
    assert result["data"] == user_input
