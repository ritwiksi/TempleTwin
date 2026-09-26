from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class Building:
    slug: str
    display_name: str
    latitude: float
    longitude: float
    floor_area_ft2: float
    approx_height_m: float
    building_type: str
    archetype: str
    area_source: str
    area_is_estimated: bool
    data_confidence: str
    geometry_source: str
    model_notes: str


DATA_PATH = Path(__file__).parent / "data" / "buildings.csv"


def load_buildings() -> list[Building]:
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            Building(
                slug=row["slug"],
                display_name=row["display_name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                floor_area_ft2=float(row["floor_area_ft2"]),
                approx_height_m=float(row["approx_height_m"]),
                building_type=row["building_type"],
                archetype=row["archetype"],
                area_source=row["area_source"],
                area_is_estimated=row["area_is_estimated"].lower() == "true",
                data_confidence=row["data_confidence"],
                geometry_source=row["geometry_source"],
                model_notes=row["model_notes"],
            )
            for row in rows
        ]


def get_building(slug: str) -> Building:
    for building in load_buildings():
        if building.slug == slug:
            return building
    raise KeyError(f"Unknown building: {slug}")
