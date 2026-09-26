import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.intervention_model import apply_interventions


FLOOR_AREA = 250000.0
ROOF_AREA = 35000.0


def baseline_profile():
    rows = []
    for index in range(96):
        hour = index // 4
        minute = (index % 4) * 15
        rows.append(
            {
                "timestamp": f"2018-09-14T{hour:02d}:{minute:02d}:00",
                "hour": hour,
                "hvac_kw": 100.0,
                "lighting_kw": 50.0,
                "process_kw": 200.0,
                "other_kw": 25.0,
                "demand_kw": 375.0,
                "solar_kw": 0.0,
                "grid_import_kw": 375.0,
                "energy_intensity_w_ft2": 1.5,
                "carbon_kg": 25.0,
            }
        )
    return rows


def weather_profile():
    return [
        {
            "timestamp": f"2018-09-14T{hour:02d}:00:00",
            "ghi_w_m2": 700.0 if 8 <= hour <= 17 else 0.0,
        }
        for hour in range(24)
    ]


def simulate(**kwargs):
    return apply_interventions(
        "serc",
        baseline_profile(),
        weather_profile(),
        FLOOR_AREA,
        ROOF_AREA,
        **kwargs,
    )


def test_led_changes_lighting_only():
    base = baseline_profile()
    row = simulate(led=True)[40]
    assert row["lighting_kw"] < base[40]["lighting_kw"]
    assert row["hvac_kw"] == base[40]["hvac_kw"]
    assert row["process_kw"] == base[40]["process_kw"]
    assert row["other_kw"] == base[40]["other_kw"]
    assert row["demand_kw"] < base[40]["demand_kw"]


def test_hvac_changes_hvac_only():
    base = baseline_profile()
    row = simulate(hvac=True)[40]
    assert row["hvac_kw"] < base[40]["hvac_kw"]
    assert row["lighting_kw"] == base[40]["lighting_kw"]
    assert row["process_kw"] == base[40]["process_kw"]
    assert row["other_kw"] == base[40]["other_kw"]
    assert row["demand_kw"] < base[40]["demand_kw"]


def test_solar_does_not_change_building_demand_but_reduces_grid_import():
    base = baseline_profile()
    daytime = simulate(solar=True)[48]
    assert daytime["solar_kw"] > 0
    assert math.isclose(daytime["demand_kw"], base[48]["demand_kw"])
    assert daytime["grid_import_kw"] < daytime["demand_kw"]
    assert daytime["grid_import_kw"] >= 0


def test_solar_reduces_carbon_and_never_makes_grid_import_negative():
    no_solar = simulate()
    solar = simulate(solar=True)
    assert sum(row["carbon_kg"] for row in solar) < sum(
        row["carbon_kg"] for row in no_solar
    )
    assert all(row["grid_import_kw"] >= 0 for row in solar)


def test_demand_always_equals_end_use_sum():
    result = simulate(led=True, hvac=True, solar=True)
    for row in result:
        expected = (
            row["hvac_kw"]
            + row["lighting_kw"]
            + row["process_kw"]
            + row["other_kw"]
        )
        assert math.isclose(row["demand_kw"], expected, rel_tol=1e-12)
