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
