"""Milestone 8 intervention simulation.

Interventions operate on the already weather-adjusted Tiger baseline profile:
- LED modifies lighting only.
- HVAC modifies HVAC only.
- Solar leaves building demand unchanged and reduces grid import.
"""

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
    ROOF_AREA_FT2,
)

INTERVAL_HOURS = 0.25


def pv_capacity_kw(slug: str) -> float:
    roof_m2 = ROOF_AREA_FT2[slug] * FT2_TO_M2
    usable_m2 = roof_m2 * PV_USABLE_ROOF_FRACTION
    return usable_m2 * PV_MODULE_POWER_DENSITY_KW_M2


def _hourly_ghi(weather_rows: list[dict[str, Any]]) -> list[float]:
    if len(weather_rows) != 24:
        raise ValueError("Expected 24 weather rows")
    return [max(float(row["ghi_w_m2"] or 0.0), 0.0) for row in weather_rows]


def interpolate_ghi(weather_rows: list[dict[str, Any]], timestamp: Any) -> float:
    if isinstance(timestamp, str):
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    else:
        ts = timestamp

    hourly = _hourly_ghi(weather_rows)
    hour = ts.hour
    fraction = ts.minute / 60.0
    current = hourly[hour]
    if hour == 23:
        return current
    return current + (hourly[hour + 1] - current) * fraction


def solar_generation_kw(slug: str, ghi_w_m2: float) -> float:
    if ghi_w_m2 <= 0:
        return 0.0
    irradiance_fraction = ghi_w_m2 / 1000.0
    return max(
        pv_capacity_kw(slug)
        * irradiance_fraction
        * (1.0 - PV_SYSTEM_LOSS_FRACTION),
        0.0,
    )


def apply_interventions(
    slug: str,
    profile: list[dict[str, Any]],
    weather_rows: list[dict[str, Any]],
    *,
    led: bool = False,
    hvac: bool = False,
    solar: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

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
            solar_kw = solar_generation_kw(slug, ghi)

        grid_import_kw = max(demand_kw - solar_kw, 0.0)
        carbon_kg = (
            grid_import_kw
            * INTERVAL_HOURS
            * EGRID_RFCE_CO2E_KG_PER_KWH
        )

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
                "carbon_kg": carbon_kg,
            }
        )
        result.append(row)

    return result
