import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.buildings import load_buildings
from app.config.model_parameters import (
    CAMPUS_ELECTRIC_EUI_KWH_FT2,
    INTERVALS_PER_DAY,
    INTERVAL_MINUTES,
)
from app.services.profile_model import (
    COMPONENTS,
    _download_comstock_rows,
    annual_target_kwh,
    generate_all_friday_profiles,
    generate_annual_profile,
)


def test_authoritative_campus_inventory_has_50_buildings():
    buildings = load_buildings()
    assert len(buildings) == 50
    assert {"serc", "beury", "engineering"} <= {b.slug for b in buildings}
    assert all(not b.area_is_estimated for b in buildings)
    assert all(b.floor_area_ft2 > 0 for b in buildings)
    assert all(b.roof_area_ft2 > 0 for b in buildings)
    assert all(len(b.footprint) >= 6 and len(b.footprint) % 2 == 0 for b in buildings)
    assert all("Temple University ArcGIS" in b.geometry_source for b in buildings)


def test_actual_comstock_files_download_for_all_campus_archetypes():
    for building_type in {b.comstock_type for b in load_buildings()}:
        rows = _download_comstock_rows(building_type)
        assert len(rows) > 30_000


def test_each_building_has_96_ordered_friday_intervals():
    buildings = load_buildings()
    profiles = generate_all_friday_profiles()
    assert set(profiles) == {b.slug for b in buildings}
    assert len(profiles) == 50
    for rows in profiles.values():
        assert len(rows) == INTERVALS_PER_DAY
        assert [row.interval_index for row in rows] == list(range(INTERVALS_PER_DAY))
        assert all(row.minute in {0, 15, 30, 45} for row in rows)


def test_all_values_nonnegative_and_components_sum_to_demand():
    profiles = generate_all_friday_profiles()
    for rows in profiles.values():
        for row in rows:
            components = [getattr(row, component) for component in COMPONENTS]
            assert all(value >= 0 for value in components)
            assert row.demand_kw >= 0
            assert math.isclose(sum(components), row.demand_kw, rel_tol=1e-10)


def test_campus_contains_multiple_distinct_load_shapes():
    profiles = generate_all_friday_profiles()
    normalized = {}
    for slug, rows in profiles.items():
        total = sum(row.demand_kw for row in rows)
        normalized[slug] = [row.demand_kw / total for row in rows]

    unique_shapes = {
        tuple(round(value, 8) for value in shape)
        for shape in normalized.values()
    }
    assert len(unique_shapes) >= 4


def test_annual_scaling_uses_reported_electricity_or_temple_anchor():
    interval_hours = INTERVAL_MINUTES / 60.0
    reported_count = 0
    modeled_count = 0

    for building in load_buildings():
        annual = generate_annual_profile(building)
        modeled_kwh = sum(row.demand_kw * interval_hours for row in annual)
        target_kwh = annual_target_kwh(building)
        assert math.isclose(modeled_kwh, target_kwh, rel_tol=1e-9)

        if building.annual_electricity_kwh is not None:
            reported_count += 1
            assert math.isclose(
                target_kwh,
                building.annual_electricity_kwh,
                rel_tol=1e-12,
            )
        else:
            modeled_count += 1
            assert math.isclose(
                target_kwh / building.floor_area_ft2,
                CAMPUS_ELECTRIC_EUI_KWH_FT2,
                rel_tol=1e-12,
            )

    assert reported_count > 0
    assert modeled_count > 0
