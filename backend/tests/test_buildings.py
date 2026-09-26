import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.buildings import load_buildings


def test_building_table_has_full_campus_and_core_buildings():
    buildings = load_buildings()
    slugs = {b.slug for b in buildings}

    assert len(buildings) == 50
    assert {"serc", "beury", "engineering"} <= slugs
    assert all(b.floor_area_ft2 > 0 for b in buildings)
    assert all(b.roof_area_ft2 > 0 for b in buildings)
    assert all(not b.area_is_estimated for b in buildings)
    assert all(
        b.data_confidence in {
            "reported-electricity",
            "authoritative-area-modeled-electricity",
        }
        for b in buildings
    )


def test_area_and_geometry_provenance_is_present():
    for building in load_buildings():
        assert building.area_source.strip()
        assert building.geometry_source.strip()
        assert building.electricity_source.strip()
        assert building.model_notes.strip()
        assert len(building.footprint) >= 6


def test_campus_inventory_has_50_distinct_current_physical_buildings():
    buildings = load_buildings()
    names = {b.display_name.replace("\n", " ").strip().lower() for b in buildings}

    # Current Temple names replace obsolete aliases for the same physical assets.
    assert "anderson hall" not in names
    assert "paley library" not in names
    assert "mazur hall" in names
    assert "paley hall" in names
    assert "facilities management" in names

    # No two modeled assets may occupy the exact same authoritative GIS centroid.
    coordinate_pairs = {
        (round(b.latitude, 7), round(b.longitude, 7))
        for b in buildings
    }
    assert len(coordinate_pairs) == len(buildings) == 50


def test_campus_energy_provenance_counts_are_explicit():
    buildings = load_buildings()
    reported = [b for b in buildings if b.data_confidence == "reported-electricity"]
    calibrated = [
        b for b in buildings
        if b.data_confidence == "authoritative-area-modeled-electricity"
    ]

    assert len(reported) == 23
    assert len(calibrated) == 27
    assert len(reported) + len(calibrated) == 50
    assert all(b.annual_electricity_kwh is not None for b in reported)
    assert all(b.annual_electricity_kwh is None for b in calibrated)
