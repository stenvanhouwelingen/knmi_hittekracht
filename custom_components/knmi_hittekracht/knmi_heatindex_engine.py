"""KNMI Heat Force Index (Hittekracht) Calculation Engine.

Isolated from Home Assistant dependencies, implementing the Liljegren physics algorithm
(2008), Spencer solar position calculations (1971), and the Australian BOM statistical
approximation formula.

Academic Reference:
Marghidan, C. P., van der Schrier, G., van den Besselaar, E., Vrolijk, M., Boonstra, R., van Ekris, J., Nuijens, W., Mokkenstorm, L., Siegmund, P., Reiling, M., Groeneweg, F., Matters, I., Camps, J., van Paassen, J., & Sluijter, R. (2026). Van Wet Bulb Globe Temperature (WBGT) naar hittekracht (Technical Report No. TR-26-04). Koninklijk Nederlands Meteorologisch Instituut (KNMI).
"""

import datetime
import math
from typing import Any


def golden_section_search(f: Any, a: float, b: float, tol: float = 1e-4) -> float:
    """Minimize a single-variable function f over the interval [a, b] using Golden Section Search."""
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    x1 = b - ratio * (b - a)
    x2 = a + ratio * (b - a)
    f1 = f(x1)
    f2 = f(x2)

    while (b - a) > tol:
        if f1 < f2:
            b = x2
            x2 = x1
            f2 = f1
            x1 = b - ratio * (b - a)
            f1 = f(x1)
        else:
            a = x1
            x1 = x2
            f1 = f2
            x2 = a + ratio * (b - a)
            f2 = f(x2)

    return (a + b) / 2.0


def viscosity(Tk: float) -> float:
    """Compute the viscosity of air in kg/(m s) given temperature in Kelvin."""
    omega = (Tk / 97.0 - 2.9) / 0.4 * (-0.034) + 1.048
    return 0.0000026693 * (28.97 * Tk) ** 0.5 / (3.617**2 * omega)


def thermal_cond(Tk: float) -> float:
    """Compute the thermal conductivity of air in W/(m K) given temperature in Kelvin."""
    m_air = 28.97
    r_gas = 8314.34
    r_air = r_gas / m_air
    cp = 1003.5
    return (cp + 1.25 * r_air) * viscosity(Tk)


def esat(Tk: float) -> float:
    """Calculate the saturation vapor pressure in hPa over water given temperature in Kelvin."""
    es = 6.1121 * math.exp(17.502 * (Tk - 273.15) / (Tk - 32.18))
    # Correction for moist air (Buck's 1981 enhancement factor approximation)
    return 1.004 * es


def emis_atm(Tk: float, RH: float) -> float:
    """Calculate the atmospheric emissivity given air temperature in Kelvin and RH fraction (0-1)."""
    e = RH * esat(Tk)
    return 0.575 * (e**0.143)


def diffusivity(Tk: float, Pair: float) -> float:
    """Compute the diffusivity of water vapor in air in m2/s given temperature in Kelvin and pressure in hPa."""
    pcrit13 = (36.4 * 218.0) ** (1.0 / 3.0)
    tcrit512 = (132.0 * 647.3) ** (5.0 / 12.0)
    Tcrit12 = (132.0 * 647.3) ** 0.5
    Mmix = (1.0 / 28.97 + 1.0 / 18.015) ** 0.5
    return (
        0.000364
        * (Tk / Tcrit12) ** 2.334
        * pcrit13
        * tcrit512
        * Mmix
        / (Pair / 1013.25)
        * 0.0001
    )


def h_evap(Tk: float) -> float:
    """Calculate the heat of evaporation in J/kg given temperature in Kelvin."""
    return (313.15 - Tk) / 30.0 * (-71100.0) + 2407300.0


def h_sphere_in_air(
    Tk: float, Pair: float, speed: float, min_speed: float, diam_globe: float
) -> float:
    """Calculate the convective heat transfer coefficient for flow around a sphere, W/(m2 K)."""
    m_air = 28.97
    r_gas = 8314.34
    r_air = r_gas / m_air
    cp = 1003.5
    Pr = cp / (cp + 1.25 * r_air)

    therm_con = thermal_cond(Tk)
    density = Pair * 100.0 / (r_air * Tk)
    if speed < min_speed:
        speed = min_speed

    Re = speed * density * diam_globe / viscosity(Tk)
    Nu = 2.0 + 0.6 * (Re**0.5) * (Pr**0.3333)
    return Nu * therm_con / diam_globe


def h_cylinder_in_air(
    Tk: float, Pair: float, speed: float, min_speed: float, diam_wick: float
) -> float:
    """Calculate the convective heat transfer coefficient for a cylinder in cross flow, W/(m2 K)."""
    m_air = 28.97
    r_gas = 8314.34
    r_air = r_gas / m_air
    cp = 1003.5
    Pr = cp / (cp + 1.25 * r_air)

    therm_con = thermal_cond(Tk)
    density = Pair * 100.0 / (r_air * Tk)
    if speed < min_speed:
        speed = min_speed

    Re = speed * density * diam_wick / viscosity(Tk)
    Nu = 0.281 * (Re**0.6) * (Pr**0.44)
    return Nu * therm_con / diam_wick


def dewp2hurs(tas: float, dewp: float) -> float:
    """Calculate relative humidity (%) from air temperature and dewpoint temperature in degrees Celsius."""
    a1, b1 = 17.368, 238.83
    a2, b2 = 17.856, 245.52
    if tas >= 0:
        hurs = 100.0 * math.exp(((a1 * dewp) / (b1 + dewp)) - ((a1 * tas) / (b1 + tas)))
    else:
        hurs = 100.0 * math.exp(((a2 * dewp) / (b2 + dewp)) - ((a2 * tas) / (b2 + tas)))
    return max(0.0, min(100.0, hurs))


def calculate_cosza_spencer(
    latitude: float, longitude: float, dt_utc: datetime.datetime
) -> tuple[float, float]:
    """Calculate the Cosine of the Solar Zenith Angle (COSZA) and Zenith Angle in degrees.

    Uses the Spencer (1971) Fourier series for declination and equation of time.
    """
    # Ensure timezone is UTC
    if dt_utc.tzinfo is not None:
        dt_utc = dt_utc.astimezone(datetime.UTC)

    # Day of year
    N = dt_utc.timetuple().tm_yday

    # Fractional year in radians
    theta = 2.0 * math.pi * (N - 1) / 365.0

    # Declination in radians (Spencer 1971)
    decl = (
        0.006918
        - 0.399912 * math.cos(theta)
        + 0.070257 * math.sin(theta)
        - 0.006758 * math.cos(2 * theta)
        + 0.000907 * math.sin(2 * theta)
        - 0.002697 * math.cos(3 * theta)
        + 0.00148 * math.sin(3 * theta)
    )

    # Equation of time in minutes (Spencer 1971)
    eqt = 229.18 * (
        0.000075
        + 0.001868 * math.cos(theta)
        - 0.032077 * math.sin(theta)
        - 0.014615 * math.cos(2 * theta)
        - 0.040849 * math.sin(2 * theta)
    )

    # Solar time offset in minutes (using UTC time, timezone offset is 0)
    time_offset = eqt + 4.0 * longitude

    # True solar time in minutes since midnight
    minutes_since_midnight = dt_utc.hour * 60.0 + dt_utc.minute + dt_utc.second / 60.0
    solar_time = minutes_since_midnight + time_offset

    # Hour angle in degrees
    h = (solar_time - 720.0) / 4.0

    # Convert latitude and hour angle to radians
    lat_rad = math.radians(latitude)
    h_rad = math.radians(h)

    # Cosine of zenith angle
    cosza = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(
        decl
    ) * math.cos(h_rad)
    cosza = max(-1.0, min(1.0, cosza))

    # Zenith angle in degrees
    zenith = math.degrees(math.acos(cosza))

    return cosza, zenith


def estimate_clear_sky_ghi(cosza: float) -> float:
    """Estimate clear-sky Global Horizontal Irradiance (GHI) in W/m² using Haurwitz model."""
    if cosza <= 0.0:
        return 0.0
    return 1098.0 * cosza * math.exp(-0.057 / cosza)


def calculate_bom_wbgt(tas: float, relh: float) -> float:
    """Calculate Wet Bulb Globe Temperature (WBGT) using the Australian BOM statistical formula."""
    # Water vapor pressure e in hPa
    e = (relh / 100.0) * 6.1105 * math.exp((17.27 * tas) / (237.7 + tas))
    # Australian BOM formula
    return 0.567 * tas + 0.393 * e + 3.94


def liljegren_wbgt(
    tas: float,
    dewp: float,
    wind: float,
    radiation: float,
    zenith_rad: float,
    propDirect: float = 0.8,
    Pair: float = 1010.0,
    tolerance: float = 1e-4,
) -> tuple[float, float, float]:
    """Calculate Wet Bulb Globe Temperature (WBGT) using the physical model of Liljegren (2008)."""
    min_speed = 0.1
    SurfAlbedo = 0.4

    # Physical constants
    stefanb = 0.000000056696
    cp = 1003.5
    m_air = 28.97
    m_h2o = 18.015
    r_gas = 8314.34
    r_air = r_gas / m_air
    ratio = cp * m_air / m_h2o
    Pr = cp / (cp + 1.25 * r_air)

    # Wick constants
    emis_wick = 0.95
    alb_wick = 0.4
    diam_wick = 0.007
    len_wick = 0.0254

    # Globe constants
    emis_globe = 0.95
    alb_globe = 0.05
    diam_globe = 0.0508

    # Surface constants
    emis_sfc = 0.999
    alb_sfc = SurfAlbedo

    # Fix up out-of-bounds problems with zenith
    if zenith_rad <= 0:
        zenith_rad = 1e-10
    if radiation > 0 and zenith_rad > 1.57:
        zenith_rad = 1.57
    if radiation > 15 and zenith_rad > 1.54:
        zenith_rad = 1.54
    if radiation > 900 and zenith_rad > 1.52:
        zenith_rad = 1.52
    if radiation < 10 and zenith_rad == 1.57:
        radiation = 0.0

    Tair = tas + 273.15
    Tdew = dewp + 273.15
    relh = dewp2hurs(tas, dewp)
    RH = relh * 0.01

    # Calculate vapour pressure
    eair = RH * esat(Tair)

    # Atmospheric emissivity
    emis_atm_val = emis_atm(Tair, RH)
    Tsfc = Tair
    density = Pair * 100.0 / (Tair * r_air)
    cza = math.cos(zenith_rad)

    # Solve for Tg (Globe Temperature)
    def fg_min(Tg_prev: float) -> float:
        Tref = 0.5 * (Tg_prev + Tair)
        h = h_sphere_in_air(Tref, Pair, wind, min_speed, diam_globe)
        Tg_new = (
            0.5 * (emis_atm_val * (Tair**4) + emis_sfc * (Tsfc**4))
            - h / (emis_globe * stefanb) * (Tg_prev - Tair)
            + radiation
            / (2.0 * emis_globe * stefanb)
            * (1.0 - alb_globe)
            * (propDirect * (1.0 / (2.0 * cza) - 1.0) + 1.0 + alb_sfc)
        ) ** 0.25
        return abs(Tg_new - Tg_prev)

    Tg_sol = golden_section_search(fg_min, Tair - 2.0, Tair + 10.0, tol=tolerance)
    Tg = Tg_sol - 273.15

    # Solve for Tnwb (Natural Wet Bulb Temperature)
    def fnwb_min(Tnwb_prev: float) -> float:
        Tref = 0.5 * (Tnwb_prev + Tair)
        Fatm = stefanb * emis_wick * (
            0.5 * (emis_atm_val * (Tair**4) + emis_sfc * (Tsfc**4)) - Tnwb_prev**4
        ) + (1.0 - alb_wick) * radiation * (
            (1.0 - propDirect) * (1.0 + 0.25 * diam_wick / len_wick)
            + ((math.tan(zenith_rad) / 3.1416) + 0.25 * diam_wick / len_wick)
            * propDirect
            + alb_sfc
        )

        Sc = viscosity(Tair) / (density * diffusivity(Tref, Pair))
        h = h_cylinder_in_air(Tnwb_prev, Pair, wind, min_speed, diam_wick)
        ewick = esat(Tnwb_prev)
        evap = h_evap(Tnwb_prev)

        Tnwb_new = (
            Tair
            - evap / ratio * (ewick - eair) / (Pair - ewick) * ((Pr / Sc) ** 0.56)
            + Fatm / h
        )
        return abs(Tnwb_new - Tnwb_prev)

    Tnwb_sol = golden_section_search(fnwb_min, Tdew - 1.0, Tair + 1.0, tol=tolerance)
    Tnwb = Tnwb_sol - 273.15

    wbgt = 0.7 * Tnwb + 0.2 * Tg + 0.1 * tas
    return wbgt, Tnwb, Tg


def wbgt_to_hittekracht(wbgt: float) -> int:
    """Map Wet Bulb Globe Temperature (WBGT) into the 0-10 Hittekracht index."""
    if wbgt < 14.0:
        return 0
    if wbgt >= 32.0:
        return 10
    return int((wbgt - 14.0) // 2.0) + 1


def calculate_hittekracht(
    temperature: float,
    humidity: float,
    wind_speed: float | None = None,
    solar_radiation: float | None = None,
    force_shade: bool = False,
    latitude: float | None = None,
    longitude: float | None = None,
    dt_utc: datetime.datetime | None = None,
    Pair: float = 1010.0,
    tolerance: float = 1e-4,
) -> dict[str, Any]:
    """Execute the progressive fallback architecture to calculate Hittekracht and WBGT."""
    # Convert humidity to dew point (approximate for boundary limits/optimization)
    # Using Arden Buck equation constants
    b = 17.67
    c = 243.5
    gamma = (b * temperature) / (c + temperature) + math.log(
        max(0.01, humidity) / 100.0
    )
    dewpoint = (c * gamma) / (b - gamma)

    # 1. Force Shaded / Night Override
    if force_shade:
        # Force solar to 0 W/m2, wind to 0.62 m/s (standard 10m height equivalent to 0.5 m/s at 2m)
        zenith_rad = 1e-10
        wbgt, tnwb, tg = liljegren_wbgt(
            tas=temperature,
            dewp=dewpoint,
            wind=0.62,
            radiation=0.0,
            zenith_rad=zenith_rad,
            propDirect=0.0,
            Pair=Pair,
            tolerance=tolerance,
        )
        return {
            "wbgt": wbgt,
            "hittekracht_index": wbgt_to_hittekracht(wbgt),
            "scenario": "Force Shaded",
            "estimated_solar": 0.0,
            "estimated_wind": 0.62,
        }

    # 2. Scenario A: All 4 inputs provided -> Full Physics Engine
    if wind_speed is not None and solar_radiation is not None:
        # Calculate zenith if lat/lon/dt available
        if latitude is not None and longitude is not None and dt_utc is not None:
            cosza, zenith_deg = calculate_cosza_spencer(latitude, longitude, dt_utc)
            zenith_rad = math.radians(zenith_deg)
        else:
            cosza, zenith_deg = 1.0, 0.0
            zenith_rad = 1e-10

        # Apply KNMI Limits:
        # Wind Speed Floor (0.62 m/s standard 10m height)
        used_wind = max(wind_speed, 0.62)

        # Solar Zenith Limits
        if zenith_deg > 89.5:
            # Sun below horizon -> force Solar and FDIR to 0
            used_solar = 0.0
            used_fdir = 0.0
        else:
            used_solar = max(solar_radiation, 0.0)
            used_fdir = (
                0.8  # Default FDIR fraction of direct sunlight, bounded [0, 0.9]
            )

        wbgt, tnwb, tg = liljegren_wbgt(
            tas=temperature,
            dewp=dewpoint,
            wind=used_wind,
            radiation=used_solar,
            zenith_rad=zenith_rad,
            propDirect=used_fdir,
            Pair=Pair,
            tolerance=tolerance,
        )
        return {
            "wbgt": wbgt,
            "hittekracht_index": wbgt_to_hittekracht(wbgt),
            "scenario": "Scenario A",
            "estimated_solar": used_solar,
            "estimated_wind": used_wind,
        }

    # 3. Scenario B: Solar missing -> Solar Estimation Hybrid
    if wind_speed is not None and solar_radiation is None:
        if latitude is not None and longitude is not None and dt_utc is not None:
            cosza, zenith_deg = calculate_cosza_spencer(latitude, longitude, dt_utc)
            zenith_rad = math.radians(zenith_deg)

            # Apply KNMI Limits:
            # Wind Speed Floor
            used_wind = max(wind_speed, 0.62)

            # Solar Zenith Limits
            if zenith_deg > 89.5:
                # Sun below horizon -> force Solar and FDIR to 0
                used_solar = 0.0
                used_fdir = 0.0
            else:
                # Estimate GHI using Haurwitz model
                used_solar = estimate_clear_sky_ghi(cosza)
                used_fdir = 0.8

            wbgt, tnwb, tg = liljegren_wbgt(
                tas=temperature,
                dewp=dewpoint,
                wind=used_wind,
                radiation=used_solar,
                zenith_rad=zenith_rad,
                propDirect=used_fdir,
                Pair=Pair,
                tolerance=tolerance,
            )
            return {
                "wbgt": wbgt,
                "hittekracht_index": wbgt_to_hittekracht(wbgt),
                "scenario": "Scenario B",
                "estimated_solar": used_solar,
                "estimated_wind": used_wind,
            }

    # 4. Scenario C: Wind & Solar Missing (or Scenario B fallback when lat/lon/dt missing) -> Statistical Fallback
    wbgt = calculate_bom_wbgt(temperature, humidity)
    return {
        "wbgt": wbgt,
        "hittekracht_index": wbgt_to_hittekracht(wbgt),
        "scenario": "Scenario C",
        "estimated_solar": None,
        "estimated_wind": None,
    }
