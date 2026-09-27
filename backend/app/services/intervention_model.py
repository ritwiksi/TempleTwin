"""Temple Twin intervention simulation.

Interventions are transparent scenario calculations over the calibrated ComStock
baseline. They are not measured Temple retrofit savings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config.model_parameters import (
    ASHRAE_TARGET_LPD_W_FT2,
    EGRID_RFCE_CO2E_KG_PER_KWH,
    FT2_TO_M2,
    PNNL_HVAC_CONTROLS_WHOLE_BUILDING_SAVINGS_FRACTION,
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


def lighting_target_category(
    building_type: str | None,
    archetype: str | None,
    comstock_type: str | None,
) -> str:
    """Map Temple metadata to the closest ASHRAE Building Area Method category."""
    bt = (building_type or "").strip().lower()
    arch = (archetype or "").strip().lower()
    comstock = (comstock_type or "").strip().lower()

    if "garage" in arch or (bt == "operations" and comstock == "warehouse"):
        return "parking_garage"
    if bt == "athletic":
        return "sports_arena"
    if "retail" in arch or comstock == "retailstandalone":
        return "retail"
    if "residential" in arch or comstock == "largehotel":
        return "hotel"
    if "office" in arch or comstock in {"mediumoffice", "largeoffice"}:
        return "office"
    if comstock == "warehouse":
        return "warehouse"
    return "school_university"


def lighting_retrofit_assumptions(
    profile: list[dict[str, Any]],
    floor_area_ft2: float,
    building_type: str | None = None,
    archetype: str | None = None,
    comstock_type: str | None = None,
) -> dict[str, float | str]:
    """Derive LED reduction from modeled baseline LPD and an ASHRAE target LPD.

    The baseline LPD is a calibrated-ComStock proxy:
      max modeled lighting kW * 1000 / gross floor area.
    If that modeled baseline is already at or below the target, no LED energy
    reduction is credited.
    """
    if floor_area_ft2 <= 0:
        raise ValueError("floor_area_ft2 must be positive")
    peak_lighting_kw = max((float(row["lighting_kw"]) for row in profile), default=0.0)
    baseline_lpd = peak_lighting_kw * 1000.0 / floor_area_ft2
    category = lighting_target_category(building_type, archetype, comstock_type)
    target_lpd = ASHRAE_TARGET_LPD_W_FT2[category]

    if baseline_lpd <= 0:
        reduction = 0.0
    else:
        reduction = max(0.0, min(1.0, 1.0 - target_lpd / baseline_lpd))

    return {
        "category": category,
        "baseline_lpd_w_ft2": baseline_lpd,
        "target_lpd_w_ft2": target_lpd,
        "reduction_fraction": reduction,
    }


def hvac_controls_assumptions(
    profile: list[dict[str, Any]],
) -> dict[str, float]:
    """Translate a PNNL whole-building controls benchmark into HVAC-only savings.

    PNNL reports ~6% whole-building energy savings for limiting heating/cooling
    to likely occupied periods. For the active day, Temple Twin computes the
    HVAC reduction required to reach that benchmark from the modeled HVAC share:

      target_savings_kWh = 0.06 * baseline_building_kWh
      hvac_reduction_fraction = target_savings_kWh / baseline_HVAC_kWh

    The fraction is bounded to [0, 1]; if HVAC energy is too small to supply the
    full benchmark, the scenario saves only the available HVAC energy.
    """
    total_energy_kwh = sum(float(row["demand_kw"]) * INTERVAL_HOURS for row in profile)
    hvac_energy_kwh = sum(float(row["hvac_kw"]) * INTERVAL_HOURS for row in profile)
    target_savings_kwh = (
        total_energy_kwh * PNNL_HVAC_CONTROLS_WHOLE_BUILDING_SAVINGS_FRACTION
    )

    if hvac_energy_kwh <= 0:
        reduction = 0.0
    else:
        reduction = max(0.0, min(1.0, target_savings_kwh / hvac_energy_kwh))

    achieved_savings_kwh = min(target_savings_kwh, hvac_energy_kwh)
    achieved_whole_building_fraction = (
        achieved_savings_kwh / total_energy_kwh if total_energy_kwh > 0 else 0.0
    )
    return {
        "target_whole_building_savings_fraction": (
            PNNL_HVAC_CONTROLS_WHOLE_BUILDING_SAVINGS_FRACTION
        ),
        "hvac_reduction_fraction": reduction,
        "achieved_whole_building_savings_fraction": achieved_whole_building_fraction,
    }


def apply_interventions(
    slug: str,
    profile: list[dict[str, Any]],
    weather_rows: list[dict[str, Any]],
    floor_area_ft2: float,
    roof_area_ft2: float,
    *,
    building_type: str | None = None,
    archetype: str | None = None,
    comstock_type: str | None = None,
    led: bool = False,
    hvac: bool = False,
    solar: bool = False,
) -> list[dict[str, Any]]:
    lighting_assumptions = lighting_retrofit_assumptions(
        profile,
        floor_area_ft2,
        building_type,
        archetype,
        comstock_type,
    )
    hvac_assumptions = hvac_controls_assumptions(profile)

    lighting_reduction = float(lighting_assumptions["reduction_fraction"]) if led else 0.0
    hvac_reduction = float(hvac_assumptions["hvac_reduction_fraction"]) if hvac else 0.0

    result = []
    for baseline in profile:
        lighting_kw = float(baseline["lighting_kw"]) * (1.0 - lighting_reduction)
        hvac_kw = float(baseline["hvac_kw"]) * (1.0 - hvac_reduction)
        process_kw = float(baseline["process_kw"])
        other_kw = float(baseline["other_kw"])

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
                "carbon_kg": (
                    grid_import_kw * INTERVAL_HOURS * EGRID_RFCE_CO2E_KG_PER_KWH
                ),
                "led_reduction_fraction": lighting_reduction,
                "led_baseline_lpd_w_ft2": lighting_assumptions["baseline_lpd_w_ft2"],
                "led_target_lpd_w_ft2": lighting_assumptions["target_lpd_w_ft2"],
                "led_target_category": lighting_assumptions["category"],
                "hvac_reduction_fraction": hvac_reduction,
                "hvac_controls_target_savings_fraction": (
                    hvac_assumptions["target_whole_building_savings_fraction"]
                ),
                "hvac_controls_achieved_savings_fraction": (
                    hvac_assumptions["achieved_whole_building_savings_fraction"]
                ),
            }
        )
        result.append(row)
    return result
