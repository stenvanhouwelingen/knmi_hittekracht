# KNMI Hittekracht (Heat Force Index) Custom Component

A local, pure-physics calculation engine for Home Assistant that calculates the Wet Bulb Globe Temperature (WBGT) and maps it into the Royal Netherlands Meteorological Institute (KNMI) **Heat Force Index (Hittekracht)**.

---

## 1. The Science of Hittekracht

The KNMI Hittekracht index is a 0–10 scale designed to communicate the physiological heat stress imposed by the environment. It is derived directly from the **Wet Bulb Globe Temperature (WBGT)**, which is the international standard for evaluating heat stress in occupational health, athletics, and military training (NEN-EN-ISO 7243:2017).

### Hittekracht vs. Hittefit: Environmental Load vs. Personal Fitness
An important concept in the KNMI TR-26-04 framework is the clear division between **environmental heat load** and **individual fitness**:
- **Hittekracht (Heat Force)** describes the **external load** on the human body. It is completely independent of the person and depends solely on weather parameters: temperature, humidity, wind, and solar radiation.
- **Hittefit (Heat Fitness)** describes the **internal capacity** of an individual to cope with that load. It depends on personal factors such as age, health conditions, level of acclimatization, hydration, clothing, and physical activity.

Together, Hittekracht and Hittefit determine the actual heat-related health risk for a specific person. This integration calculates the **Hittekracht** (external load).

---

## 2. 3-Tier Progressive Accuracy System

Since measuring all four meteorological parameters (Temperature, Humidity, Wind, and Solar) requires specialized hardware, the integration uses an **adaptive fallback architecture** that dynamically adjusts its calculation scenario based on your available Home Assistant entities:

| Tier | Scenario | Hardware Required | Calculation Method | Accuracy |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Scenario A** | Temp + Humidity + Wind + Solar sensors | **Full Liljegren Physics Engine**: Resolves the full heat-balance equations iteratively. | **Highest** (Gold Standard) |
| **Tier 2** | **Scenario B** | Temp + Humidity + Wind sensors | **Solar Estimation Hybrid**: Calculates the Cosine of the Solar Zenith Angle (COSZA) and estimates clear-sky Global Horizontal Irradiance (GHI), passing it to the Liljegren engine. | **High** (Excellent for open areas) |
| **Tier 3** | **Scenario C** | Temp + Humidity sensors | **Statistical Fallback**: Executes the Australian Bureau of Meteorology (BOM) empirical formula. | **Moderate** (Standard shade profile) |

*Note: You can also explicitly toggle the **Force Shaded / Night Profile** in the configuration, which forces Solar to 0 W/m² and Wind to 0.5 m/s at 2m (0.62 m/s standard 10m height) to simulate a shaded outdoor setting using the Full Physics Engine.*

---

## 3. Configuration & Setup

### Requirements
* **Air Temperature**: Required. Filtered in the UI to match `temperature` sensors, weather, or climate entities.
* **Relative Humidity**: Required. Filtered in the UI to match `humidity` sensors, weather, or climate entities.
* **Wind Speed**: Optional. Filtered in the UI to match `wind_speed` sensors or weather entities.
* **Solar Radiation**: Optional. Filtered in the UI to match `irradiance` (solar radiation) sensors.

### Steps
1. Copy the `knmi_hittekracht` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. In the Home Assistant UI, go to **Settings** -> **Devices & Services** -> **Helpers** tab (or **Add Integration**) and click **Create Helper** (or search) for **KNMI Hittekracht**.
4. Link your temperature and humidity entities, and optionally wind and solar entities.
5. Since this is a helper entity, you can update your entity selections or toggle the **Force Shaded** option at any time by selecting the helper in the **Helpers** tab list and clicking **Configure**.

---

## 4. Academic References

The calculations implemented in this integration follow these scientific models:

1. Marghidan, C. P., van der Schrier, G., van den Besselaar, E., Vrolijk, M., Boonstra, R., van Ekris, J., Nuijens, W., Mokkenstorm, L., Siegmund, P., Reiling, M., Groeneweg, F., Matters, I., Camps, J., van Paassen, J., & Sluijter, R. (2026). *Van Wet Bulb Globe Temperature (WBGT) naar hittekracht* (Technical Report No. TR-26-04). Koninklijk Nederlands Meteorologisch Instituut (KNMI). https://www.knmi.nl/research/publications/van-wet-bulb-globe-temperature-wbgt-naar-hittekracht
2. Liljegren, J. C., Carhart, R. A., Lawday, P., Tschopp, S., & Sharp, R. (2008). Modeling Wet Bulb Globe Temperature Using Standard Meteorological Measurements. *Journal of Occupational and Environmental Hygiene*, *5*(10), 645–655. https://doi.org/10.1080/15459620802310770
3. Buck, A. L. (1981). New Equations for Computing Vapor Pressure and Enhancement Factor. *Journal of Applied Meteorology*, *20*(12), 1527–1532. https://doi.org/10.1175/1520-0450(1981)020%3C1527:NEFCVP%3E2.0.CO;2
4. Australian Bureau of Meteorology. (n.d.). *Wet Bulb Globe Temperature (WBGT) shade/low-wind empirical approximation*. https://www.bom.gov.au/info/thermal_stress/

## 5. Disclaimer

> [!WARNING]
> **Unofficial Integration:** This project is a community-developed, unofficial integration. It is not affiliated with, endorsed by, or in any way officially connected to the Koninklijk Nederlands Meteorologisch Instituut (KNMI).
>
> This integration provides environmental heat load estimates (Hittekracht / WBGT) calculated locally from standard meteorological variables. These values are estimates and should not be used as a replacement for official weather warnings, professional medical advice, or occupational health safety plans. Individual physiological heat stress (Hittefit) varies based on physical health, age, activity level, hydration, and clothing. Always exercise caution and consult official guidelines during heat events.
