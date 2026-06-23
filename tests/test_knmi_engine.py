"""Test suite for the KNMI Heat Index Calculation Engine."""

import datetime
import math
import os
import sys

# Add custom_components/knmi_hittekracht directory to the path so we can import the engine
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../custom_components/knmi_hittekracht")
    ),
)

from knmi_heatindex_engine import (
    calculate_bom_wbgt,
    calculate_cosza_spencer,
    calculate_hittekracht,
    dewp2hurs,
    estimate_clear_sky_ghi,
    liljegren_wbgt,
    wbgt_to_hittekracht,
)


def test_dewp2hurs():
    """Test Dewpoint to Relative Humidity conversion."""
    # 25C air temp, 15C dewpoint
    rh1 = dewp2hurs(25.0, 15.0)
    assert 50.0 < rh1 < 56.0

    # Check boundaries
    assert dewp2hurs(25.0, 26.0) == 100.0
    assert dewp2hurs(25.0, -100.0) >= 0.0


def test_solar_position():
    """Test the Spencer solar position calculations (COSZA & Zenith)."""
    # Amsterdam on June 23, 2026 at 12:00:00 UTC
    dt = datetime.datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.UTC)
    lat = 52.3676
    lon = 4.9041

    cosza, zenith = calculate_cosza_spencer(lat, lon, dt)

    # Zenith angle should be around 29 degrees in late June near solar noon
    assert 28.0 < zenith < 30.0
    assert 0.85 < cosza < 0.90

    # Nighttime test
    dt_night = datetime.datetime(2026, 6, 23, 23, 0, 0, tzinfo=datetime.UTC)
    cosza_night, zenith_night = calculate_cosza_spencer(lat, lon, dt_night)

    assert zenith_night > 90.0
    assert cosza_night < 0.0


def test_clear_sky_ghi():
    """Test Haurwitz clear-sky solar radiation model."""
    # Nighttime
    assert estimate_clear_sky_ghi(-0.5) == 0.0
    assert estimate_clear_sky_ghi(0.0) == 0.0

    # Daytime
    ghi = estimate_clear_sky_ghi(0.87)
    assert 800.0 < ghi < 1000.0


def test_bom_wbgt():
    """Test Australian BOM statistical formula."""
    # tas = 25.0, relh = 50.0%
    wbgt = calculate_bom_wbgt(25.0, 50.0)
    # Vapor pressure e should be around 15.8 hPa
    # WBGT = 0.567 * 25.0 + 0.393 * 15.8 + 3.94 = 14.175 + 6.2 + 3.94 = ~24.3
    assert 23.5 < wbgt < 25.0


def test_hittekracht_mapping():
    """Test WBGT to Hittekracht Index mapping."""
    # < 14 -> 0
    assert wbgt_to_hittekracht(13.9) == 0

    # 14.0 to < 16.0 -> 1
    assert wbgt_to_hittekracht(14.0) == 1
    assert wbgt_to_hittekracht(15.9) == 1

    # 16.0 to < 18.0 -> 2
    assert wbgt_to_hittekracht(16.0) == 2
    assert wbgt_to_hittekracht(17.9) == 2

    # 30.0 to < 32.0 -> 9
    assert wbgt_to_hittekracht(30.0) == 9
    assert wbgt_to_hittekracht(31.9) == 9

    # >= 32.0 -> 10
    assert wbgt_to_hittekracht(32.0) == 10
    assert wbgt_to_hittekracht(35.0) == 10


def test_liljegren_physics():
    """Test Liljegren thermodynamic physics engine."""
    # Warm, humid, windy, sunny day
    wbgt, tnwb, tg = liljegren_wbgt(
        tas=25.0, dewp=15.0, wind=2.0, radiation=800.0, zenith_rad=math.radians(30.0)
    )

    assert 18.0 < tnwb < 22.0
    assert 30.0 < tg < 40.0
    assert 22.0 < wbgt < 26.0


def test_adaptive_scenarios():
    """Test all progressive accuracy scenarios and overrides."""
    # Setup test parameters
    dt = datetime.datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.UTC)
    lat = 52.3676
    lon = 4.9041

    # 1. Force Shaded
    res_shaded = calculate_hittekracht(
        temperature=25.0,
        humidity=50.0,
        wind_speed=2.0,
        solar_radiation=800.0,
        force_shade=True,
        latitude=lat,
        longitude=lon,
        dt_utc=dt,
    )
    assert res_shaded["scenario"] == "Force Shaded"
    assert res_shaded["estimated_solar"] == 0.0
    assert res_shaded["estimated_wind"] == 0.62

    # 2. Scenario A: All 4 inputs provided
    res_a = calculate_hittekracht(
        temperature=25.0,
        humidity=50.0,
        wind_speed=2.0,
        solar_radiation=800.0,
        force_shade=False,
        latitude=lat,
        longitude=lon,
        dt_utc=dt,
    )
    assert res_a["scenario"] == "Scenario A"
    assert res_a["estimated_solar"] == 800.0
    assert res_a["estimated_wind"] == 2.0

    # 3. Scenario B: Solar missing
    res_b = calculate_hittekracht(
        temperature=25.0,
        humidity=50.0,
        wind_speed=2.0,
        solar_radiation=None,
        force_shade=False,
        latitude=lat,
        longitude=lon,
        dt_utc=dt,
    )
    assert res_b["scenario"] == "Scenario B"
    assert (
        res_b["estimated_solar"] > 800.0
    )  # Estimated clear sky GHI should be around 850
    assert res_b["estimated_wind"] == 2.0

    # 4. Scenario C: Wind & Solar missing
    res_c = calculate_hittekracht(
        temperature=25.0,
        humidity=50.0,
        wind_speed=None,
        solar_radiation=None,
        force_shade=False,
        latitude=lat,
        longitude=lon,
        dt_utc=dt,
    )
    assert res_c["scenario"] == "Scenario C"
    assert res_c["estimated_solar"] is None
    assert res_c["estimated_wind"] is None
