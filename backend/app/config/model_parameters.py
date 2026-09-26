"""Centralized Milestone 3 modeling assumptions.

Hourly load SHAPES come from official NREL/OEDI ComStock data.
Building-specific magnitudes remain modeled estimates, not Temple meter values.
"""

CAMPUS_ELECTRICITY_MMBTU_FY2025 = 612_025.0
KWH_PER_MMBTU = 293.071
CAMPUS_GROSS_AREA_FT2_FY2025 = 11_122_267.0
CAMPUS_ELECTRIC_EUI_KWH_FT2 = (
    CAMPUS_ELECTRICITY_MMBTU_FY2025
    * KWH_PER_MMBTU
    / CAMPUS_GROSS_AREA_FT2_FY2025
)

# Temple-specific annual magnitude assumptions. These are still modeled.
MODELED_EUI_KWH_FT2 = {
    "serc": 28.0,
    "beury": 23.0,
    "engineering": 17.5,
}

# ComStock has no dedicated laboratory building type. These proxies are explicit,
# configurable, and use ACTUAL ComStock Philadelphia County load shapes.
COMSTOCK_BUILDING_TYPE = {
    "serc": "largeoffice",
    "beury": "secondaryschool",
    "engineering": "mediumoffice",
}

COMSTOCK_RELEASE = "2021/comstock_amy2018_release_1"
COMSTOCK_STATE = "PA"
COMSTOCK_COUNTY_GISJOIN = "g4201010"  # Philadelphia County, Pennsylvania
COMSTOCK_SOURCE_ROOT = (
    "https://oedi-data-lake.s3.amazonaws.com/"
    "nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/"
    f"{COMSTOCK_RELEASE}/timeseries_aggregates/by_county/state={COMSTOCK_STATE}"
)

# Representative Friday extracted from AMY2018 ComStock.
COMSTOCK_FRIDAY_DATE = "2018-09-14"
