"""Constants for the KNMI Hittekracht custom component.

Based on:
Marghidan, C. P., van der Schrier, G., van den Besselaar, E., Vrolijk, M., Boonstra, R., van Ekris, J., Nuijens, W., Mokkenstorm, L., Siegmund, P., Reiling, M., Groeneweg, F., Matters, I., Camps, J., van Paassen, J., & Sluijter, R. (2026). Van Wet Bulb Globe Temperature (WBGT) naar hittekracht (Technical Report No. TR-26-04). Koninklijk Nederlands Meteorologisch Instituut (KNMI).
"""

DOMAIN = "knmi_hittekracht"

CONF_TEMP_ENTITY = "temperature_entity"
CONF_HUM_ENTITY = "humidity_entity"
CONF_WIND_ENTITY = "wind_entity"
CONF_SOLAR_ENTITY = "solar_entity"
CONF_FORCE_SHADE = "force_shade"

HITTEKRACHT_LEVELS = {
    0: {
        "en": {"label": "Comfortable", "desc": "Minimal heat load."},
        "nl": {"label": "Comfortabel", "desc": "Minimale belasting."},
    },
    1: {
        "en": {"label": "Comfortable", "desc": "Minimal heat load."},
        "nl": {"label": "Comfortabel", "desc": "Minimale belasting."},
    },
    2: {
        "en": {"label": "Comfortable", "desc": "Minimal heat load."},
        "nl": {"label": "Comfortabel", "desc": "Minimale belasting."},
    },
    3: {
        "en": {"label": "Noticeable Warmth", "desc": "Moderate heat load."},
        "nl": {"label": "Merkbare warmte", "desc": "Matige belasting."},
    },
    4: {
        "en": {"label": "Noticeable Warmth", "desc": "Moderate heat load."},
        "nl": {"label": "Merkbare warmte", "desc": "Matige belasting."},
    },
    5: {
        "en": {"label": "High Heat Load", "desc": "Increased heat stress."},
        "nl": {"label": "Hoge belasting", "desc": "Verhoogde hittestress."},
    },
    6: {
        "en": {"label": "High Heat Load", "desc": "Increased heat stress."},
        "nl": {"label": "Hoge belasting", "desc": "Verhoogde hittestress."},
    },
    7: {
        "en": {"label": "Hazardous", "desc": "Severe heat load."},
        "nl": {"label": "Risicovol", "desc": "Zware belasting."},
    },
    8: {
        "en": {"label": "Hazardous", "desc": "Severe heat load."},
        "nl": {"label": "Risicovol", "desc": "Zware belasting."},
    },
    9: {
        "en": {"label": "Extreme Heat", "desc": "Dangerous conditions."},
        "nl": {"label": "Extreme hitte", "desc": "Gevaarlijke omstandigheden."},
    },
    10: {
        "en": {"label": "Extreme Heat", "desc": "Exceptionally dangerous."},
        "nl": {"label": "Extreme hitte", "desc": "Uitzonderlijk gevaarlijk."},
    },
}
