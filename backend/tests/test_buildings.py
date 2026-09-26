import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.buildings import load_buildings


def test_building_table_has_required_tier_one_buildings():
    buildings = load_buildings()
    assert [b.slug for b in buildings] == ["serc", "beury", "engineering"]
    assert all(b.floor_area_ft2 > 0 for b in buildings)
    assert all(b.data_confidence in {"verified", "modeled", "estimated"} for b in buildings)


def test_area_provenance_is_present():
    for building in load_buildings():
        assert building.area_source.strip()
        assert building.model_notes.strip()
