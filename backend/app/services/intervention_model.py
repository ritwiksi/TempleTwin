"""Temple Twin intervention simulation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config.model_parameters import (
    EGRID_RFCE_CO2E_KG_PER_KWH,
    FT2_TO_M2,
    HVAC_EFFICIENCY_IMPROVEMENT_FRACTION,
    LED_LIGHTING_REDUCTION_FRACTION,
    PV_MODULE_POWER_DENSITY_KW_M2,
    PV_SYSTEM_LOSS_FRACTION,
    PV_USABLE_ROOF_FRACTION,
)

INTERVAL_HOURS = 0.25


def pv_capacity_kw(roof_area_ft2: float) -> float:
    roof_m2 = roof_area_ft2 * FT2_TO_M2
    usable_m2 = roof_m2 * PV_USABLE_ROOF_FRACTION
    return usable_m2 * PV_MODULE_POWER_DENSITY_KW_M2


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=None)


def interpolate_ghi(weather_rows: list[dict[str, Any]], timestamp: Any) -> float:
    if not weather_rows:
        raise ValueError("Weather rows are empty")

    ts = _as_datetime(timestamp)
    first = _as_datetime(weather_rows[0]["timestamp"])
    hours_from_start = (ts - first).total_seconds() / 3600.0
    index = int(hours_from_start)
    fraction = hours_from_start - index

    if index < 0 or index >= len(weather_rows):
        raise ValueError(f"Timestamp {timestamp} is outside cached weather range")

    current = max(float(weather_rows[index]["ghi_w_m2"] or 0.0), 0.0)
    if index + 1 >= len(weather_rows):
        return current
    next_ghi = max(float(weather_rows[index + 1]["ghi_w_m2"] or 0.0), 0.0)
    return current + (next_ghi - current) * fraction


def solar_generation_kw(roof_area_ft2: float, ghi_w_m2: float) -> float:
    if ghi_w_m2 <= 0:
        return 0.0
    return max(
        pv_capacity_kw(roof_area_ft2)
        * (ghi_w_m2 / 1000.0)
        * (1.0 - PV_SYSTEM_LOSS_FRACTION),
        0.0,
    )


def apply_interventions(
    slug: str,
    profile: list[dict[str, Any]],
    weather_rows: list[dict[str, Any]],
    floor_area_ft2: float,
    roof_area_ft2: float,
    *,
    led: bool = False,
    hvac: bool = False,
    solar: bool = False,
) -> list[dict[str, Any]]:
    result = []
    for baseline in profile:
        lighting_kw = float(baseline["lighting_kw"])
        hvac_kw = float(baseline["hvac_kw"])
        process_kw = float(baseline["process_kw"])
        other_kw = float(baseline["other_kw"])

        if led:
            lighting_kw *= 1.0 - LED_LIGHTING_REDUCTION_FRACTION
        if hvac:
            hvac_kw *= 1.0 - HVAC_EFFICIENCY_IMPROVEMENT_FRACTION

        demand_kw = hvac_kw + lighting_kw + process_kw + other_kw
        solar_kw = 0.0
        if solar:
            ghi = interpolate_ghi(weather_rows, baseline["timestamp"])
            solar_kw = solar_generation_kw(roof_area_ft2, ghi)

        grid_import_kw = max(demand_kw - solar_kw, 0.0)
        row = dict(baseline)
        row.update(
            {
                "hvac_kw": hvac_kw,
                "lighting_kw": lighting_kw,
                "process_kw": process_kw,
                "other_kw": other_kw,
                "demand_kw": demand_kw,
                "solar_kw": solar_kw,
                "grid_import_kw": grid_import_kw,
                "energy_intensity_w_ft2": demand_kw * 1000.0 / floor_area_ft2,
                "carbon_kg": grid_import_kw * INTERVAL_HOURS * EGRID_RFCE_CO2E_KG_PER_KWH,
            }
        )
        result.append(row)
    return result
