"""Centralized Milestone 3 modeling assumptions.

Nothing in this file is a measured Temple building meter value.
All building-level electricity values are modeled estimates.
"""

CAMPUS_ELECTRICITY_MMBTU_FY2025 = 612_025.0
KWH_PER_MMBTU = 293.071
CAMPUS_GROSS_AREA_FT2_FY2025 = 11_122_267.0
CAMPUS_ELECTRIC_EUI_KWH_FT2 = (
    CAMPUS_ELECTRICITY_MMBTU_FY2025
    * KWH_PER_MMBTU
    / CAMPUS_GROSS_AREA_FT2_FY2025
)

# Modeled electricity-only EUIs. These are calibration assumptions, not measured
# building values. They intentionally differ from the 16.1 campus-wide anchor
# because laboratory/research buildings carry higher ventilation/process loads.
MODELED_EUI_KWH_FT2 = {
    "serc": 28.0,
    "beury": 23.0,
    "engineering": 17.5,
}

# Prototype end-use schedule parameters. These compact schedules are a
# transparent representative fixture for validating the ComStock-shaped
# pipeline. scripts/prepare_comstock.py replaces them with exported ComStock
# hourly shapes when raw NREL data is supplied.
ARCHETYPE_PARAMETERS = {
    "research_lab": {
        "base_process": 0.62,
        "occupied_process": 0.38,
        "night_lighting": 0.10,
        "day_lighting": 0.90,
        "night_hvac": 0.42,
        "day_hvac": 0.58,
        "other_base": 0.36,
        "other_day": 0.64,
    },
    "mixed_lab_classroom": {
        "base_process": 0.50,
        "occupied_process": 0.50,
        "night_lighting": 0.08,
        "day_lighting": 0.92,
        "night_hvac": 0.36,
        "day_hvac": 0.64,
        "other_base": 0.30,
        "other_day": 0.70,
    },
    "engineering_academic": {
        "base_process": 0.28,
        "occupied_process": 0.72,
        "night_lighting": 0.06,
        "day_lighting": 0.94,
        "night_hvac": 0.30,
        "day_hvac": 0.70,
        "other_base": 0.24,
        "other_day": 0.76,
    },
}

# Annual component shares used to decompose each building's target annual kWh.
# Shares sum to exactly 1.0 for every archetype.
COMPONENT_SHARES = {
    "research_lab": {
        "hvac_kw": 0.37,
        "lighting_kw": 0.13,
        "process_kw": 0.40,
        "other_kw": 0.10,
    },
    "mixed_lab_classroom": {
        "hvac_kw": 0.39,
        "lighting_kw": 0.16,
        "process_kw": 0.34,
        "other_kw": 0.11,
    },
    "engineering_academic": {
        "hvac_kw": 0.42,
        "lighting_kw": 0.20,
        "process_kw": 0.25,
        "other_kw": 0.13,
    },
}

# Mild seasonal HVAC multipliers. Weather-based corrections are deliberately
# deferred to Milestone 6.
MONTHLY_HVAC_MULTIPLIER = {
    1: 1.18, 2: 1.13, 3: 1.02, 4: 0.88, 5: 0.95, 6: 1.12,
    7: 1.24, 8: 1.20, 9: 1.05, 10: 0.90, 11: 1.01, 12: 1.15,
}

FRIDAY_MONTH = 9
FRIDAY_DAY = 18
