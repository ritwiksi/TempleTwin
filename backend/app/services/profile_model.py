"""Temple Twin Milestone 3 building-energy profile model.

The model creates annual component profiles, scales them exactly to a modeled
annual electricity target, and extracts a representative Friday 00:00-23:00.

Building-level outputs are MODELED ESTIMATES, not Temple meter readings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import math

from app.buildings import Building, get_building, load_buildings
from app.config.model_parameters import (
    ARCHETYPE_PARAMETERS,
    COMPONENT_SHARES,
    FRIDAY_DAY,
    FRIDAY_MONTH,
    MODELED_EUI_KWH_FT2,
    MONTHLY_HVAC_MULTIPLIER,
)


COMPONENTS = ("hvac_kw", "lighting_kw", "process_kw", "other_kw")


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


def _occupied_factor(hour: int, weekday: int, archetype: str) -> float:
    """Smooth occupancy proxy used by the representative ComStock-style fixture."""
    is_weekday = weekday < 5
    if not is_weekday:
        return 0.18 if archetype == "engineering_academic" else 0.28

    # Friday retains normal daytime activity but tapers slightly earlier.
    rise = 1.0 / (1.0 + math.exp(-(hour - 7.3) * 1.4))
    fall = 1.0 / (1.0 + math.exp((hour - 18.2) * 1.25))
    occupied = rise * fall
    return max(0.08, min(1.0, occupied))


def _component_shape(
    component: str,
    hour: int,
    weekday: int,
    month: int,
    archetype: str,
) -> float:
    p = ARCHETYPE_PARAMETERS[archetype]
    occ = _occupied_factor(hour, weekday, archetype)

    if component == "process_kw":
        value = p["base_process"] + p["occupied_process"] * occ
    elif component == "lighting_kw":
        value = p["night_lighting"] + p["day_lighting"] * occ
    elif component == "hvac_kw":
        value = (
            p["night_hvac"] + p["day_hvac"] * occ
        ) * MONTHLY_HVAC_MULTIPLIER[month]
    elif component == "other_kw":
        value = p["other_base"] + p["other_day"] * occ
    else:
        raise KeyError(component)

    return max(value, 0.0)


def _raw_annual_shapes(building: Building, year: int = 2026) -> dict[str, list[float]]:
    """Construct 8760 representative hourly shape weights for an archetype."""
    start = datetime(year, 1, 1)
    hours = 365 * 24
    shapes = {component: [] for component in COMPONENTS}

    for offset in range(hours):
        ts = start + timedelta(hours=offset)
        for component in COMPONENTS:
            shapes[component].append(
                _component_shape(
                    component,
                    ts.hour,
                    ts.weekday(),
                    ts.month,
                    building.archetype,
                )
            )
    return shapes


def annual_target_kwh(building: Building) -> float:
    return MODELED_EUI_KWH_FT2[building.slug] * building.floor_area_ft2


def generate_annual_profile(building: Building, year: int = 2026) -> list[HourlyState]:
    """Scale component shapes so their annual sum equals the modeled annual target."""
    shapes = _raw_annual_shapes(building, year)
    target = annual_target_kwh(building)
    shares = COMPONENT_SHARES[building.archetype]

    scaled: dict[str, list[float]] = {}
    for component in COMPONENTS:
        raw = shapes[component]
        component_target_kwh = target * shares[component]
        scale = component_target_kwh / sum(raw)
        scaled[component] = [value * scale for value in raw]

    start = datetime(year, 1, 1)
    states: list[HourlyState] = []
    for idx in range(365 * 24):
        ts = start + timedelta(hours=idx)
        values = {component: scaled[component][idx] for component in COMPONENTS}
        demand = sum(values.values())
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


def generate_friday_profile(slug: str, year: int = 2026) -> list[HourlyState]:
    """Return exactly 24 modeled hourly rows for the selected September Friday."""
    building = get_building(slug)
    annual = generate_annual_profile(building, year)
    target_date = datetime(year, FRIDAY_MONTH, FRIDAY_DAY).date()
    rows = [
        row
        for row in annual
        if datetime.fromisoformat(row.timestamp).date() == target_date
    ]
    if len(rows) != 24:
        raise RuntimeError(f"Expected 24 Friday rows for {slug}, got {len(rows)}")
    return rows


def generate_all_friday_profiles(year: int = 2026) -> dict[str, list[HourlyState]]:
    return {
        building.slug: generate_friday_profile(building.slug, year)
        for building in load_buildings()
    }


def modeled_building_metadata() -> list[dict]:
    result = []
    for building in load_buildings():
        row = asdict(building)
        row["modeled_annual_electric_eui_kwh_ft2"] = MODELED_EUI_KWH_FT2[
            building.slug
        ]
        row["modeled_annual_electricity_kwh"] = annual_target_kwh(building)
        result.append(row)
    return result
