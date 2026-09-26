from dataclasses import dataclass
from pathlib import Path
import csv
import json


@dataclass(frozen=True)
class Building:
    slug: str
    display_name: str
    latitude: float
    longitude: float
    floor_area_ft2: float
    roof_area_ft2: float
    approx_height_m: float
    building_type: str
    archetype: str
    comstock_type: str
    area_source: str
    area_is_estimated: bool
    data_confidence: str
    geometry_source: str
    annual_electricity_kwh: float | None
    electricity_source: str
    model_notes: str
    footprint: tuple[float, ...]


DATA_PATH = Path(__file__).parent / "data" / "buildings.csv"
GEOMETRY_PATH = Path(__file__).parent / "data" / "building_geometry.json"


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def load_buildings() -> list[Building]:
    geometry = json.loads(GEOMETRY_PATH.read_text(encoding="utf-8"))
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        result = []
        for row in rows:
            slug = row["slug"]
            footprint = tuple(float(v) for v in geometry.get(slug, []))
            if len(footprint) < 6 or len(footprint) % 2:
                raise RuntimeError(f"Missing/invalid footprint for {slug}")
            result.append(
                Building(
                    slug=slug,
                    display_name=row["display_name"].replace("\n", " ").strip(),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    floor_area_ft2=float(row["floor_area_ft2"]),
                    roof_area_ft2=float(row["roof_area_ft2"]),
                    approx_height_m=float(row["approx_height_m"]),
                    building_type=row["building_type"],
                    archetype=row["archetype"],
                    comstock_type=row["comstock_type"],
                    area_source=row["area_source"],
                    area_is_estimated=row["area_is_estimated"].lower() == "true",
                    data_confidence=row["data_confidence"],
                    geometry_source=row["geometry_source"],
                    annual_electricity_kwh=_optional_float(row["annual_electricity_kwh"]),
                    electricity_source=row["electricity_source"],
                    model_notes=row["model_notes"],
                    footprint=footprint,
                )
            )
        return result


def get_building(slug: str) -> Building:
    for building in load_buildings():
        if building.slug == slug:
            return building
    raise KeyError(f"Unknown building: {slug}")
