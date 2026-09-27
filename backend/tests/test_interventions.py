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


def test_led_reduction_is_exactly_configured_fraction():
    result = simulate(led=True)
    for row in result:
        assert math.isclose(row["lighting_kw"], 25.0, rel_tol=1e-12)


def test_hvac_reduction_is_exactly_configured_fraction():
    result = simulate(hvac=True)
    for row in result:
        assert math.isclose(row["hvac_kw"], 90.0, rel_tol=1e-12)


def test_solar_is_zero_at_night_and_positive_during_day():
    result = simulate(solar=True)
    night_indices = list(range(0, 8 * 4)) + list(range(18 * 4, 96))
    assert all(math.isclose(result[index]["solar_kw"], 0.0, abs_tol=1e-12) for index in night_indices)
    assert any(row["solar_kw"] > 0 for row in result[8 * 4 : 18 * 4])


def test_solar_never_changes_end_use_or_building_demand():
    base = baseline_profile()
    solar = simulate(solar=True)
    for before, after in zip(base, solar):
        assert math.isclose(after["hvac_kw"], before["hvac_kw"], rel_tol=1e-12)
        assert math.isclose(after["lighting_kw"], before["lighting_kw"], rel_tol=1e-12)
        assert math.isclose(after["process_kw"], before["process_kw"], rel_tol=1e-12)
        assert math.isclose(after["other_kw"], before["other_kw"], rel_tol=1e-12)
        assert math.isclose(after["demand_kw"], before["demand_kw"], rel_tol=1e-12)


def test_combined_interventions_stack_without_cross_talk():
    base = baseline_profile()
    result = simulate(led=True, hvac=True, solar=True)
    daytime = 12 * 4

    assert math.isclose(result[daytime]["lighting_kw"], base[daytime]["lighting_kw"] * 0.5, rel_tol=1e-12)
    assert math.isclose(result[daytime]["hvac_kw"], base[daytime]["hvac_kw"] * 0.9, rel_tol=1e-12)
    assert math.isclose(result[daytime]["process_kw"], base[daytime]["process_kw"], rel_tol=1e-12)
    assert math.isclose(result[daytime]["other_kw"], base[daytime]["other_kw"], rel_tol=1e-12)
    assert result[daytime]["solar_kw"] > 0
    assert result[daytime]["grid_import_kw"] <= result[daytime]["demand_kw"]


def test_all_interventions_off_exactly_restore_baseline_operating_values():
    base = baseline_profile()
    result = simulate(led=False, hvac=False, solar=False)
    for before, after in zip(base, result):
        for field in (
            "hvac_kw",
            "lighting_kw",
            "process_kw",
            "other_kw",
            "demand_kw",
            "grid_import_kw",
            "energy_intensity_w_ft2",
        ):
            assert math.isclose(float(after[field]), float(before[field]), rel_tol=1e-12)


def test_carbon_tracks_grid_import_for_every_interval():
    result = simulate(led=True, hvac=True, solar=True)
    from app.config.model_parameters import EGRID_RFCE_CO2E_KG_PER_KWH

    for row in result:
        expected = row["grid_import_kw"] * 0.25 * EGRID_RFCE_CO2E_KG_PER_KWH
        assert math.isclose(row["carbon_kg"], expected, rel_tol=1e-12)


def test_larger_roof_produces_more_solar_under_same_weather():
    small_roof = apply_interventions(
        "small",
        baseline_profile(),
        weather_profile(),
        100000.0,
        10000.0,
        solar=True,
    )
    large_roof = apply_interventions(
        "large",
        baseline_profile(),
        weather_profile(),
        300000.0,
        50000.0,
        solar=True,
    )
    noon = 12 * 4
    assert large_roof[noon]["solar_kw"] > small_roof[noon]["solar_kw"]


def test_energy_intensity_respects_building_floor_area():
    small = apply_interventions(
        "small",
        baseline_profile(),
        weather_profile(),
        100000.0,
        10000.0,
    )
    large = apply_interventions(
        "large",
        baseline_profile(),
        weather_profile(),
        300000.0,
        10000.0,
    )
    noon = 12 * 4
    assert small[noon]["energy_intensity_w_ft2"] > large[noon]["energy_intensity_w_ft2"]
