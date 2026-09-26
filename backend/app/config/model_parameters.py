"""Centralized Temple Twin modeling inputs.

Load shapes/end uses come from official NREL/OEDI ComStock 15-minute data.
Absolute annual magnitude uses Temple's published campus-wide electricity EUI
uniformly for all three buildings until defensible building-specific annual
energy data or a calibrated physics model is available.
"""

CAMPUS_ELECTRICITY_MMBTU_FY2025 = 612_025.0
KWH_PER_MMBTU = 293.071
CAMPUS_GROSS_AREA_FT2_FY2025 = 11_122_267.0
CAMPUS_ELECTRIC_EUI_KWH_FT2 = (
    CAMPUS_ELECTRICITY_MMBTU_FY2025
    * KWH_PER_MMBTU
    / CAMPUS_GROSS_AREA_FT2_FY2025
)

COMSTOCK_BUILDING_TYPE = {
    "serc": "largeoffice",
    "beury": "secondaryschool",
    "engineering": "mediumoffice",
}

COMSTOCK_RELEASE = "2021/comstock_amy2018_release_1"
COMSTOCK_STATE = "PA"
COMSTOCK_COUNTY_GISJOIN = "g4201010"
COMSTOCK_SOURCE_ROOT = (
    "https://oedi-data-lake.s3.amazonaws.com/"
    "nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/"
    f"{COMSTOCK_RELEASE}/timeseries_aggregates/by_county/state={COMSTOCK_STATE}"
)

COMSTOCK_FRIDAY_DATE = "2018-09-14"
INTERVAL_MINUTES = 15
INTERVALS_PER_DAY = 96


# Temple campus / weather model
TEMPLE_LATITUDE = 39.9819
TEMPLE_LONGITUDE = -75.1543
WEATHER_DATE = COMSTOCK_FRIDAY_DATE

# Simplified bounded HVAC weather normalization.
# These are model coefficients, not measured Temple HVAC sensitivities.
COOLING_BALANCE_F = 70.0
HEATING_BALANCE_F = 55.0
COOLING_BETA_PER_F = 0.008
HEATING_BETA_PER_F = 0.006
HVAC_WEATHER_FACTOR_MIN = 0.90
HVAC_WEATHER_FACTOR_MAX = 1.20


# EPA eGRID2023 RFC East (RFCE) total output CO2e emission rate.
# 599.170 lb CO2e/MWh -> kg CO2e/kWh.
EGRID_RFCE_CO2E_LB_PER_MWH = 599.170
LB_TO_KG = 0.45359237
EGRID_RFCE_CO2E_KG_PER_KWH = (
    EGRID_RFCE_CO2E_LB_PER_MWH * LB_TO_KG / 1000.0
)
