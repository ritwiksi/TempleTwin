"""Centralized Temple Twin modeling inputs.

Load shapes/end uses come from official NREL/OEDI ComStock 15-minute data.
Absolute annual magnitude uses building-level Philadelphia benchmarking where
an unambiguous report exists; other buildings use Temple's published FY2025
campus-wide electricity EUI.
"""

CAMPUS_ELECTRICITY_MMBTU_FY2025 = 612_025.0
KWH_PER_MMBTU = 293.071
CAMPUS_GROSS_AREA_FT2_FY2025 = 11_122_267.0
CAMPUS_ELECTRIC_EUI_KWH_FT2 = (
    CAMPUS_ELECTRICITY_MMBTU_FY2025
    * KWH_PER_MMBTU
    / CAMPUS_GROSS_AREA_FT2_FY2025
)
COMSTOCK_RELEASE = "2021/comstock_amy2018_release_1"
COMSTOCK_STATE = "PA"
COMSTOCK_COUNTY_GISJOIN = "g4201010"
COMSTOCK_SOURCE_ROOT = (
    "https://oedi-data-lake.s3.amazonaws.com/"
    "nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/"
    f"{COMSTOCK_RELEASE}/timeseries_aggregates/by_county/state={COMSTOCK_STATE}"
)

SIMULATION_START_DATE = "2018-09-01"
SIMULATION_END_DATE = "2018-11-30"
INTERVAL_MINUTES = 15
INTERVALS_PER_DAY = 96
SIMULATION_DAYS = 91
SIMULATION_INTERVALS = SIMULATION_DAYS * INTERVALS_PER_DAY
SIMULATION_WEATHER_HOURS = SIMULATION_DAYS * 24


# Temple campus / weather model
TEMPLE_LATITUDE = 39.9819
TEMPLE_LONGITUDE = -75.1543
WEATHER_START_DATE = SIMULATION_START_DATE
WEATHER_END_DATE = SIMULATION_END_DATE

# EPA eGRID2023 RFC East (RFCE) total output CO2e emission rate.
# 599.170 lb CO2e/MWh -> kg CO2e/kWh.
EGRID_RFCE_CO2E_LB_PER_MWH = 599.170
LB_TO_KG = 0.45359237
EGRID_RFCE_CO2E_KG_PER_KWH = (
    EGRID_RFCE_CO2E_LB_PER_MWH * LB_TO_KG / 1000.0
)


# Lighting retrofit targets: ASHRAE 90.1-2019 Building Area Method values
# as updated by Addendum bb. These are target lighting power densities, not
# claimed existing Temple fixture inventories.
ASHRAE_TARGET_LPD_W_FT2 = {
    "school_university": 0.70,
    "office": 0.62,
    "hotel": 0.53,
    "warehouse": 0.45,
    "retail": 0.78,
    "parking_garage": 0.17,
    "sports_arena": 0.73,
}

# HVAC controls scenario: PNNL/DOE found about 6% whole-building energy
# savings from limiting heating/cooling to periods when a building is most
# likely occupied. Temple Twin translates that whole-building benchmark into
# a building/day-specific HVAC reduction using the modeled HVAC share.
PNNL_HVAC_CONTROLS_WHOLE_BUILDING_SAVINGS_FRACTION = 0.06

# Rooftop PV assumptions.
# NREL rooftop technical-potential work used ~60-65% suitable commercial roof
# area and 160 W/m2 module power density. PVWatts default losses are 14%.
PV_USABLE_ROOF_FRACTION = 0.60
PV_MODULE_POWER_DENSITY_KW_M2 = 0.160
PV_SYSTEM_LOSS_FRACTION = 0.14
FT2_TO_M2 = 0.09290304
