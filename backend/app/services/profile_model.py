"""Temple Twin 15-minute energy profile model.

Each building uses:
- authoritative Temple GIS gross floor area and polygon geometry;
- City of Philadelphia reported annual electricity when an unambiguous
  building-level match exists;
- otherwise Temple's FY2025 campus electricity EUI as the annual calibration;
- NREL ComStock Philadelphia County end-use/load shape for the full annual profile.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from functools import lru_cache
import csv
import io
import urllib.request

from app.buildings import Building, get_building, load_buildings
from app.config.model_parameters import (
    CAMPUS_ELECTRIC_EUI_KWH_FT2,
    COMSTOCK_COUNTY_GISJOIN,
    COMSTOCK_SOURCE_ROOT,
    INTERVAL_MINUTES,
    SIMULATION_END_DATE,
    SIMULATION_INTERVALS,
    SIMULATION_START_DATE,
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
class IntervalState:
    timestamp: str
    hour: int
    minute: int
    interval_index: int
    hvac_kw: float
    lighting_kw: float
    process_kw: float
    other_kw: float
    demand_kw: float

    def to_dict(self) -> dict:
        return asdict(self)


def annual_target_kwh(building: Building) -> float:
    if building.annual_electricity_kwh is not None:
        return building.annual_electricity_kwh
    return CAMPUS_ELECTRIC_EUI_KWH_FT2 * building.floor_area_ft2


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
    url = _source_url(building_type)
    with urllib.request.urlopen(url, timeout=45) as response:
        text = response.read().decode("utf-8")
    rows = tuple(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise RuntimeError(f"ComStock returned no rows: {url}")
    return rows


@lru_cache(maxsize=None)
def _comstock_annual_profile(building_type: str) -> tuple[IntervalState, ...]:
    states: list[IntervalState] = []
    for row in _download_comstock_rows(building_type):
        endpoint = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        start = endpoint - timedelta(minutes=INTERVAL_MINUTES)

        hvac_kwh = sum(_number(row, col) for col in HVAC_COLUMNS)
        lighting_kwh = sum(_number(row, col) for col in LIGHTING_COLUMNS)
        process_kwh = sum(_number(row, col) for col in PROCESS_COLUMNS)
        total_kwh = _number(row, TOTAL_COLUMN)
        other_kwh = max(total_kwh - hvac_kwh - lighting_kwh - process_kwh, 0.0)

        kwh_to_kw = 60.0 / INTERVAL_MINUTES
        values = {
            "hvac_kw": hvac_kwh * kwh_to_kw,
            "lighting_kw": lighting_kwh * kwh_to_kw,
            "process_kw": process_kwh * kwh_to_kw,
            "other_kw": other_kwh * kwh_to_kw,
        }

        states.append(
            IntervalState(
                timestamp=start.isoformat(),
                hour=start.hour,
                minute=start.minute,
                interval_index=start.hour * 4 + start.minute // INTERVAL_MINUTES,
                demand_kw=sum(values.values()),
                **values,
            )
        )
    return tuple(states)


def generate_annual_profile(building: Building) -> list[IntervalState]:
    raw = list(_comstock_annual_profile(building.comstock_type))
    if not raw:
        raise RuntimeError(f"No ComStock annual profile for {building.slug}")

    interval_hours = INTERVAL_MINUTES / 60.0
    raw_annual_kwh = sum(row.demand_kw * interval_hours for row in raw)
    if raw_annual_kwh <= 0:
        raise RuntimeError(f"ComStock profile total is zero for {building.slug}")

    scale = annual_target_kwh(building) / raw_annual_kwh
    scaled = []
    for row in raw:
        values = {c: getattr(row, c) * scale for c in COMPONENTS}
        scaled.append(
            IntervalState(
                timestamp=row.timestamp,
                hour=row.hour,
                minute=row.minute,
                interval_index=row.interval_index,
                demand_kw=sum(values.values()),
                **values,
            )
        )
    return scaled


def generate_simulation_profile(slug: str) -> list[IntervalState]:
    """Return the continuous 15-minute profile for the configured simulation window."""
    building = get_building(slug)
    annual = generate_annual_profile(building)
    selected = [
        row
        for row in annual
        if SIMULATION_START_DATE
        <= datetime.fromisoformat(row.timestamp).date().isoformat()
        <= SIMULATION_END_DATE
    ]
    selected.sort(key=lambda row: datetime.fromisoformat(row.timestamp))

    if len(selected) != SIMULATION_INTERVALS:
        raise RuntimeError(
            f"Expected {SIMULATION_INTERVALS} ComStock simulation rows for {slug}, "
            f"got {len(selected)}"
        )

    return [
        replace(row, interval_index=index)
        for index, row in enumerate(selected)
    ]


def generate_all_simulation_profiles() -> dict[str, list[IntervalState]]:
    return {
        building.slug: generate_simulation_profile(building.slug)
        for building in load_buildings()
    }

def modeled_building_metadata() -> list[dict]:
    result = []
    for building in load_buildings():
        row = asdict(building)
        annual_kwh = annual_target_kwh(building)
        row["modeled_annual_electric_eui_kwh_ft2"] = annual_kwh / building.floor_area_ft2
        row["modeled_annual_electricity_kwh"] = annual_kwh
        result.append(row)
    return result
