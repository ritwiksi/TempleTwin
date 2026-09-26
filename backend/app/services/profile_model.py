"""Temple Twin Milestone 3 profile model using ACTUAL NREL ComStock shapes.

Hourly end-use shapes are downloaded from official OEDI ComStock Philadelphia
County aggregate timeseries. Temple-specific annual magnitudes are modeled
estimates and are scaled separately.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
import csv
import io
import math
import urllib.request

from app.buildings import Building, get_building, load_buildings
from app.config.model_parameters import (
    COMSTOCK_BUILDING_TYPE,
    COMSTOCK_COUNTY_GISJOIN,
    COMSTOCK_FRIDAY_DATE,
    COMSTOCK_SOURCE_ROOT,
    MODELED_EUI_KWH_FT2,
)

COMPONENTS = ("hvac_kw", "lighting_kw", "process_kw", "other_kw")

HVAC_COLUMNS = (
    "out.electricity.cooling.energy_consumption",
    "out.electricity.fans.energy_consumption",
    "out.electricity.heat_recovery.energy_consumption",
    "out.electricity.heat_rejection.energy_consumption",
    "out.electricity.heating.energy_consumption",
    "out.electricity.pumps.energy_consumption",
)
LIGHTING_COLUMNS = (
    "out.electricity.interior_lighting.energy_consumption",
    "out.electricity.exterior_lighting.energy_consumption",
)
PROCESS_COLUMNS = (
    "out.electricity.interior_equipment.energy_consumption",
    "out.electricity.refrigeration.energy_consumption",
)
TOTAL_COLUMN = "out.electricity.total.energy_consumption"


@dataclass(frozen=True)
class HourlyState:
    timestamp: str
    hour: int
    hvac_kw: float
    lighting_kw: float
    process_kw: float
    other_kw: float
    demand_kw: float

    def to_dict(self) -> dict:
        return asdict(self)


def annual_target_kwh(building: Building) -> float:
    return MODELED_EUI_KWH_FT2[building.slug] * building.floor_area_ft2


def _source_url(building_type: str) -> str:
    return (
        f"{COMSTOCK_SOURCE_ROOT}/"
        f"{COMSTOCK_COUNTY_GISJOIN}-{building_type}.csv"
    )


def _number(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    if raw in ("", None):
        return 0.0
    return max(float(raw), 0.0)


@lru_cache(maxsize=None)
def _download_comstock_rows(building_type: str) -> tuple[dict[str, str], ...]:
    """Download an official OEDI county/building-type aggregate CSV."""
    url = _source_url(building_type)
    with urllib.request.urlopen(url, timeout=45) as response:
        text = response.read().decode("utf-8")
    rows = tuple(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise RuntimeError(f"ComStock returned no rows: {url}")
    return rows


def _aggregate_to_hourly(building_type: str) -> list[HourlyState]:
    """Aggregate 15-minute ComStock kWh intervals into hourly component kW.

    ComStock timeseries energy fields are kWh per 15-minute interval. Summing
    four intervals gives kWh during one hour, numerically equal to average kW
    over that hour.
    """
    buckets: dict[str, dict[str, float]] = {}

    for row in _download_comstock_rows(building_type):
        timestamp = row["timestamp"]
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        # Published timestamp marks the END of the 15-minute interval.
        # Shift 15 minutes conceptually by assigning :15/:30/:45/:00 to the
        # hour that contains the consumed interval.
        if ts.minute == 0:
            hour_ts = ts.replace(minute=0)
            # 00:00 endpoint belongs to previous hour.
            from datetime import timedelta
            hour_ts -= timedelta(hours=1)
        else:
            hour_ts = ts.replace(minute=0)

        key = hour_ts.isoformat()
        bucket = buckets.setdefault(
            key,
            {c: 0.0 for c in COMPONENTS} | {"demand_kw": 0.0},
        )

        hvac = sum(_number(row, col) for col in HVAC_COLUMNS)
        lighting = sum(_number(row, col) for col in LIGHTING_COLUMNS)
        process = sum(_number(row, col) for col in PROCESS_COLUMNS)
        total = _number(row, TOTAL_COLUMN)
        other = max(total - hvac - lighting - process, 0.0)

        bucket["hvac_kw"] += hvac
        bucket["lighting_kw"] += lighting
        bucket["process_kw"] += process
        bucket["other_kw"] += other
        bucket["demand_kw"] += total

    states = []
    for timestamp in sorted(buckets):
        values = buckets[timestamp]
        ts = datetime.fromisoformat(timestamp)
        components = sum(values[c] for c in COMPONENTS)
        # Use component sum to guarantee decomposition equality; tiny source
        # rounding differences are absorbed into other_kw above.
        demand = components
        states.append(
            HourlyState(
                timestamp=ts.isoformat(),
                hour=ts.hour,
                hvac_kw=values["hvac_kw"],
                lighting_kw=values["lighting_kw"],
                process_kw=values["process_kw"],
                other_kw=values["other_kw"],
                demand_kw=demand,
            )
        )
    return states


@lru_cache(maxsize=None)
def _comstock_annual_profile(slug: str) -> tuple[HourlyState, ...]:
    building_type = COMSTOCK_BUILDING_TYPE[slug]
    return tuple(_aggregate_to_hourly(building_type))


def generate_annual_profile(building: Building) -> list[HourlyState]:
    """Scale actual ComStock component shapes to Temple's modeled annual target."""
    raw = list(_comstock_annual_profile(building.slug))
    if not raw:
        raise RuntimeError(f"No ComStock annual profile for {building.slug}")

    target = annual_target_kwh(building)
    raw_total = sum(row.demand_kw for row in raw)
    if raw_total <= 0:
        raise RuntimeError(f"ComStock profile total is zero for {building.slug}")

    scale = target / raw_total
    scaled = []
    for row in raw:
        values = {
            component: getattr(row, component) * scale
            for component in COMPONENTS
        }
        demand = sum(values.values())
        scaled.append(
            HourlyState(
                timestamp=row.timestamp,
                hour=row.hour,
                hvac_kw=values["hvac_kw"],
                lighting_kw=values["lighting_kw"],
                process_kw=values["process_kw"],
                other_kw=values["other_kw"],
                demand_kw=demand,
            )
        )
    return scaled


def generate_friday_profile(slug: str) -> list[HourlyState]:
    """Extract exactly 24 hourly rows from a real AMY2018 ComStock Friday."""
    building = get_building(slug)
    annual = generate_annual_profile(building)

    rows = [
        row
        for row in annual
        if datetime.fromisoformat(row.timestamp).date().isoformat()
        == COMSTOCK_FRIDAY_DATE
    ]

    # Depending on OEDI timezone/end-interval edge handling, the selected date
    # can contain a boundary duplicate/missing row. Sort and retain one row per
    # clock hour to make the API contract deterministic.
    by_hour = {row.hour: row for row in rows}
    ordered = [by_hour[h] for h in range(24) if h in by_hour]
    if len(ordered) != 24:
        raise RuntimeError(
            f"Expected 24 ComStock Friday rows for {slug}, got {len(ordered)}"
        )
    return ordered


def generate_all_friday_profiles() -> dict[str, list[HourlyState]]:
    return {
        building.slug: generate_friday_profile(building.slug)
        for building in load_buildings()
    }


def modeled_building_metadata() -> list[dict]:
    result = []
    for building in load_buildings():
        row = asdict(building)
        row["comstock_building_type"] = COMSTOCK_BUILDING_TYPE[building.slug]
        row["modeled_annual_electric_eui_kwh_ft2"] = MODELED_EUI_KWH_FT2[
            building.slug
        ]
        row["modeled_annual_electricity_kwh"] = annual_target_kwh(building)
        result.append(row)
    return result
