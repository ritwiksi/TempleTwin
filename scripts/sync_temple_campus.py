#!/usr/bin/env python3
"""Build the Temple Twin campus inventory from public authoritative sources.

Sources:
1. Temple University public ArcGIS building services (geometry + facility attrs)
2. City of Philadelphia 2024 Building Energy Benchmarking (reported area/electricity)

This script intentionally refuses to synthesize gross floor area. A building is
eligible for the modeled campus set only when a real gross/floor-area attribute
is available from Temple GIS or the City benchmarking dataset.

The committed output is deterministic source data used by Temple Twin; the app
itself does not call these external services at runtime.
"""

from __future__ import annotations

import csv
import difflib
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "backend" / "app" / "data" / "buildings.csv"
OUT_GEOMETRY = ROOT / "backend" / "app" / "data" / "building_geometry.json"
OUT_REPORT = ROOT / "backend" / "app" / "data" / "campus_sync_report.json"

TEMPLE_SERVICE_ROOT = "https://services.arcgis.com/6fiE7QkLWSPMd0N5/ArcGIS/rest/services"
TEMPLE_SERVICES = (
    "TU_Buildings_2026",
    "Temple_University_Buildings_2024",
    "TU_MainCampus_Buildings",
    "TU_Buildings",
    "Temple_Buildings_Main_Campus_OWL",
)
PHILA_BENCHMARK_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
    "properties_reported_2024/FeatureServer/0/query"
)

# Broad Main Campus envelope. The source layer itself is Temple-specific;
# this removes HSC/Ambler/Center City if present.
MAIN_CAMPUS_BBOX = (-75.1695, 39.9720, -75.1450, 39.9885)

# Known non-Temple/private/non-building items that can appear in campus layers.
EXCLUDE_NAME_PARTS = (
    "septa",
    "subway",
    "regional rail",
    "founder's garden",
    "founders garden",
    "o'connor plaza",
    "oconnor plaza",
    "the edge",
    "university village",
    "kardon",
    "atlantic terminal",
    "street",
    "walkway",
    "sidewalk",
    "lawn",
    "field",
    "court",
    "track",
)

# Priority keeps iconic/current buildings if a source exposes >50 qualifying
# structures. Everything else is filled by gross floor area.
PRIORITY_NAMES = (
    "science education and research",
    "serc",
    "beury",
    "engineering",
    "alter",
    "anderson",
    "annenberg",
    "architecture",
    "biology",
    "charles library",
    "gladfelter",
    "wachman",
    "weiss",
    "tyler",
    "ritter",
    "speakman",
    "sullivan",
    "presser",
    "pearson",
    "mcgonigle",
    "tuttleman",
    "howard gittis",
    "student center",
    "tech center",
    "1300",
    "1940",
    "temple towers",
    "white hall",
    "rock hall",
    "conwell",
    "carnell",
    "shusterman",
    "tomlinson",
    "liacouras center",
    "star complex",
    "morgan hall",
)

NAME_KEYS = (
    "building_name", "buildingname", "bldg_name", "bldgname", "building",
    "facility_name", "facilityname", "facility", "name", "long_name",
    "longname", "label", "common_name", "commonname", "description",
)
AREA_KEYS = (
    "gross_floor_area", "grossfloorarea", "gross_sq_ft", "grosssqft",
    "gross_square_feet", "grosssquarefeet", "gross_area_ft2", "grossareaft2",
    "gross_area", "grossarea", "building_gsf", "buildinggsf", "bldg_gsf",
    "bldggsf", "total_gsf", "totalgsf", "gsf", "floor_area_ft2",
    "floorareaft2", "floor_area", "floorarea", "square_feet", "squarefeet",
    "sq_ft", "sqft",
)
USE_KEYS = (
    "building_type", "buildingtype", "primary_use", "primaryuse", "use_type",
    "usetype", "facility_type", "facilitytype", "category", "use",
)
HEIGHT_KEYS = ("height_m", "heightm", "height", "building_height", "buildingheight")


def request_json(url: str, params: dict[str, Any] | None = None) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TempleTwin/1.0 (+https://github.com/ritwiksi/TempleTwin)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def normalized_name(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\btemple university\b", " ", value)
    value = re.sub(r"\bbuilding\b|\bhall\b|\bcomplex\b|\bcenter\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def slugify(value: str) -> str:
    value = normalized_name(value)
    slug = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return slug[:80] or "building"


def first_value(attrs: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    mapped = {normalized_key(k): v for k, v in attrs.items()}
    for key in candidates:
        v = mapped.get(normalized_key(key))
        if v not in (None, "", " "):
            return v
    return None


def float_value(value: Any) -> float | None:
    if value in (None, "", " "):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return None


def positive_float(value: Any) -> float | None:
    number = float_value(value)
    return number if number is not None and number > 0 else None


def geometry_rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    if not geometry:
        return []
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return coords[:1]
    if kind == "MultiPolygon":
        rings: list[list[list[float]]] = []
        for polygon in coords:
            if polygon:
                rings.append(polygon[0])
        return rings
    return []


def ring_area_ft2(ring: list[list[float]]) -> float:
    if len(ring) < 4:
        return 0.0
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    meters_per_deg_lat = 111_132.0
    meters_per_deg_lon = 111_320.0 * math.cos(lat0)
    pts = [(p[0] * meters_per_deg_lon, p[1] * meters_per_deg_lat) for p in ring]
    area_m2 = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        area_m2 += x1 * y2 - x2 * y1
    return abs(area_m2) * 0.5 * 10.7639104167


def centroid(rings: list[list[list[float]]]) -> tuple[float, float] | None:
    points = [p for ring in rings for p in ring]
    if not points:
        return None
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def flatten_largest_ring(rings: list[list[list[float]]]) -> list[float]:
    if not rings:
        return []
    ring = max(rings, key=ring_area_ft2)
    # ArcGIS closes rings; Cesium does not require repeated final point.
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return [coordinate for point in ring for coordinate in point[:2]]


def in_main_campus(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = MAIN_CAMPUS_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def is_excluded(name: str) -> bool:
    n = name.lower()
    return any(part in n for part in EXCLUDE_NAME_PARTS)


def fetch_service_features(service: str) -> list[dict[str, Any]]:
    root = f"{TEMPLE_SERVICE_ROOT}/{urllib.parse.quote(service)}/FeatureServer"
    metadata = request_json(root, {"f": "json"})
    layers = metadata.get("layers") or []
    features: list[dict[str, Any]] = []
    for layer in layers:
        layer_id = layer["id"]
        query = f"{root}/{layer_id}/query"
        payload = request_json(
            query,
            {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultRecordCount": "2000",
            },
        )
        for feature in payload.get("features", []):
            feature["_temple_service"] = service
            feature["_temple_layer"] = layer.get("name", str(layer_id))
            features.append(feature)
    return features


def fetch_all_temple_features() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_features: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    for service in TEMPLE_SERVICES:
        try:
            rows = fetch_service_features(service)
            diagnostics[service] = {"ok": True, "feature_count": len(rows)}
            all_features.extend(rows)
        except Exception as exc:
            diagnostics[service] = {"ok": False, "error": str(exc)}
    if not all_features:
        raise RuntimeError(f"No Temple GIS service returned features: {diagnostics}")
    return all_features, diagnostics


def fetch_benchmark_rows() -> list[dict[str, Any]]:
    payload = request_json(
        PHILA_BENCHMARK_URL,
        {
            "where": "1=1",
            "outFields": (
                "property_name,street_address,y_lat,x_lon,"
                "total_floor_area_bld_pk_ft2,electric_use_kbtu,"
                "primary_prop_type_epa_calc,num_of_buildings,data_year"
            ),
            "returnGeometry": "false",
            "resultRecordCount": "2000",
            "f": "json",
        },
    )
    return [feature.get("attributes", {}) for feature in payload.get("features", [])]


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lat_mid = math.radians((lat1 + lat2) / 2)
    dx = (lon2 - lon1) * 111_320.0 * math.cos(lat_mid)
    dy = (lat2 - lat1) * 111_132.0
    return math.hypot(dx, dy)


def benchmark_match(
    name: str, lon: float, lat: float, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float | None, float]:
    target = normalized_name(name)
    best: tuple[dict[str, Any] | None, float | None, float] = (None, None, 0.0)
    for row in rows:
        row_lon = float_value(row.get("x_lon"))
        row_lat = float_value(row.get("y_lat"))
        if row_lon is None or row_lat is None:
            continue
        dist = distance_m(lon, lat, row_lon, row_lat)
        if dist > 140:
            continue

        prop = normalized_name(str(row.get("property_name") or ""))
        similarity = difflib.SequenceMatcher(None, target, prop).ratio() if prop else 0.0

        # Nearby + recognizable name is strongest. Extremely close points can
        # match even when the benchmark record uses a campus/property alias.
        score = similarity + max(0.0, (80.0 - dist) / 200.0)
        if (similarity >= 0.34 or dist <= 28.0) and score > best[2]:
            best = (row, dist, score)
    return best


def comstock_type(name: str, use_value: str) -> tuple[str, str]:
    text = f"{name} {use_value}".lower()
    if any(x in text for x in ("residence", "housing", "apartment", "dorm", "towers")):
        return "largehotel", "residential proxy"
    if any(x in text for x in ("student center", "bookstore", "retail", "shops")):
        return "retailstandalone", "student/retail"
    if any(x in text for x in ("recreation", "fitness", "athletic", "gym", "star")):
        return "secondaryschool", "recreation/academic"
    if any(x in text for x in ("library", "learning", "classroom", "education", "school", "college")):
        return "secondaryschool", "academic/classroom"
    if any(x in text for x in ("science", "research", "biology", "engineering", "lab", "beury")):
        return "largeoffice", "research/laboratory"
    if any(x in text for x in ("theater", "theatre", "arts", "music", "presser", "rock hall")):
        return "secondaryschool", "arts/academic"
    if any(x in text for x in ("garage", "parking", "facilities", "maintenance")):
        return "warehouse", "service/garage"
    if any(x in text for x in ("administration", "office", "business", "alter", "sullivan")):
        return "mediumoffice", "office/administration"
    return "secondaryschool", use_value or "academic/mixed"


@dataclass
class Candidate:
    name: str
    lon: float
    lat: float
    footprint: list[float]
    roof_area_ft2: float
    gross_area_ft2: float
    area_source: str
    geometry_source: str
    use_value: str
    height_m: float
    annual_electricity_kwh: float | None
    electricity_source: str
    benchmark_property_name: str | None


def main() -> None:
    temple_features, service_diagnostics = fetch_all_temple_features()
    benchmark_rows = fetch_benchmark_rows()

    service_field_samples: dict[str, list[str]] = {}
    service_attribute_samples: dict[str, dict[str, Any]] = {}
    for feature in temple_features:
        service = feature["_temple_service"]
        attrs = feature.get("properties", {})
        service_field_samples.setdefault(service, sorted(attrs.keys()))
        if service not in service_attribute_samples:
            service_attribute_samples[service] = attrs

    benchmark_field_sample = (
        sorted(benchmark_rows[0].keys()) if benchmark_rows else []
    )
    benchmark_sample = benchmark_rows[0] if benchmark_rows else {}

    # Merge duplicate representations across Temple GIS services by normalized name.
    raw_by_name: dict[str, list[dict[str, Any]]] = {}
    rejected: list[dict[str, Any]] = []

    for feature in temple_features:
        attrs = feature.get("properties", {})
        name_raw = first_value(attrs, NAME_KEYS)
        if not name_raw:
            continue
        name = str(name_raw).strip()
        if len(name) < 3 or is_excluded(name):
            continue

        rings = geometry_rings(feature.get("geometry") or {})
        center = centroid(rings)
        if not rings or not center:
            continue
        lon, lat = center
        if not in_main_campus(lon, lat):
            continue

        raw_by_name.setdefault(normalized_name(name), []).append(feature)

    candidates: list[Candidate] = []

    for normalized, features in raw_by_name.items():
        # Prefer the newest service order listed above and then the largest footprint.
        def feature_rank(feature: dict[str, Any]) -> tuple[int, float]:
            service = feature["_temple_service"]
            service_priority = len(TEMPLE_SERVICES) - TEMPLE_SERVICES.index(service)
            rings = geometry_rings(feature.get("geometry") or {})
            return service_priority, sum(ring_area_ft2(r) for r in rings)

        primary = max(features, key=feature_rank)
        primary_attrs = primary.get("properties", {})
        name = str(first_value(primary_attrs, NAME_KEYS)).strip()
        rings = geometry_rings(primary.get("geometry") or {})
        lon, lat = centroid(rings) or (0.0, 0.0)
        footprint = flatten_largest_ring(rings)
        roof_area = sum(ring_area_ft2(r) for r in rings)

        # Search all duplicate service records for a true gross floor area field.
        gross_area = None
        area_source = ""
        use_value = ""
        height_m = 20.0
        for feature in features:
            attrs = feature.get("properties", {})
            if gross_area is None:
                gross_area = positive_float(first_value(attrs, AREA_KEYS))
                if gross_area:
                    area_source = (
                        f"Temple University ArcGIS {feature['_temple_service']} "
                        f"field attribute"
                    )
            if not use_value:
                use_raw = first_value(attrs, USE_KEYS)
                if use_raw:
                    use_value = str(use_raw)
            height_raw = positive_float(first_value(attrs, HEIGHT_KEYS))
            if height_raw:
                height_m = height_raw

        benchmark, bench_dist, bench_score = benchmark_match(
            name, lon, lat, benchmark_rows
        )
        annual_kwh = None
        electricity_source = "Temple campus FY2025 calibrated EUI"
        benchmark_name = None

        if benchmark:
            benchmark_name = str(benchmark.get("property_name") or "") or None
            bench_area = positive_float(benchmark.get("total_floor_area_bld_pk_ft2"))
            if gross_area is None and bench_area:
                gross_area = bench_area
                area_source = (
                    "City of Philadelphia 2024 Building Energy Benchmarking "
                    f"({benchmark_name or 'matched property'})"
                )

            electric_kbtu = positive_float(benchmark.get("electric_use_kbtu"))
            num_buildings = positive_float(benchmark.get("num_of_buildings"))
            if electric_kbtu and (num_buildings in (None, 1.0)):
                annual_kwh = electric_kbtu * 0.29307107
                electricity_source = (
                    "City of Philadelphia 2024 Building Energy Benchmarking "
                    f"({benchmark_name or 'matched property'})"
                )

            if not use_value and benchmark.get("primary_prop_type_epa_calc"):
                use_value = str(benchmark["primary_prop_type_epa_calc"])

        if gross_area is None:
            rejected.append(
                {
                    "name": name,
                    "reason": "no authoritative gross/floor area attribute",
                    "geometry_source": primary["_temple_service"],
                    "benchmark_match": benchmark_name,
                    "benchmark_distance_m": bench_dist,
                    "benchmark_score": bench_score,
                }
            )
            continue

        candidates.append(
            Candidate(
                name=name,
                lon=lon,
                lat=lat,
                footprint=footprint,
                roof_area_ft2=roof_area,
                gross_area_ft2=gross_area,
                area_source=area_source,
                geometry_source=f"Temple University ArcGIS {primary['_temple_service']}",
                use_value=use_value,
                height_m=height_m,
                annual_electricity_kwh=annual_kwh,
                electricity_source=electricity_source,
                benchmark_property_name=benchmark_name,
            )
        )

    # Deduplicate slugs safely.
    by_slug: dict[str, Candidate] = {}
    for candidate in sorted(candidates, key=lambda c: c.gross_area_ft2, reverse=True):
        base = slugify(candidate.name)
        slug = base
        n = 2
        while slug in by_slug:
            slug = f"{base}-{n}"
            n += 1
        by_slug[slug] = candidate

    def priority(candidate: Candidate) -> tuple[int, float]:
        n = candidate.name.lower()
        rank = 0
        for i, needle in enumerate(PRIORITY_NAMES):
            if needle in n:
                rank = len(PRIORITY_NAMES) - i
                break
        return rank, candidate.gross_area_ft2

    selected_pairs = sorted(by_slug.items(), key=lambda kv: priority(kv[1]), reverse=True)
    if len(selected_pairs) < 50:
        report = {
            "status": "failed",
            "qualified_buildings": len(selected_pairs),
            "required_buildings": 50,
            "service_diagnostics": service_diagnostics,
            "service_field_samples": service_field_samples,
            "service_attribute_samples": service_attribute_samples,
            "benchmark_row_count": len(benchmark_rows),
            "benchmark_field_sample": benchmark_field_sample,
            "benchmark_sample": benchmark_sample,
            "rejected_missing_area": rejected,
        }
        OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError(
            f"Only {len(selected_pairs)} Main Campus buildings have authoritative "
            "gross/floor area. Refusing to fabricate the remainder; see "
            f"{OUT_REPORT.relative_to(ROOT)}"
        )

    selected_pairs = selected_pairs[:50]

    fieldnames = [
        "slug", "display_name", "latitude", "longitude", "floor_area_ft2",
        "roof_area_ft2", "approx_height_m", "building_type", "archetype",
        "comstock_type", "area_source", "area_is_estimated", "data_confidence",
        "geometry_source", "annual_electricity_kwh", "electricity_source",
        "model_notes",
    ]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    geometry: dict[str, list[float]] = {}

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for slug, candidate in sorted(selected_pairs, key=lambda kv: kv[1].name.lower()):
            ctype, archetype = comstock_type(candidate.name, candidate.use_value)
            writer.writerow(
                {
                    "slug": slug,
                    "display_name": candidate.name,
                    "latitude": f"{candidate.lat:.8f}",
                    "longitude": f"{candidate.lon:.8f}",
                    "floor_area_ft2": f"{candidate.gross_area_ft2:.2f}",
                    "roof_area_ft2": f"{candidate.roof_area_ft2:.2f}",
                    "approx_height_m": f"{candidate.height_m:.2f}",
                    "building_type": candidate.use_value or archetype,
                    "archetype": archetype,
                    "comstock_type": ctype,
                    "area_source": candidate.area_source,
                    "area_is_estimated": "false",
                    "data_confidence": (
                        "reported-electricity"
                        if candidate.annual_electricity_kwh
                        else "authoritative-area-modeled-electricity"
                    ),
                    "geometry_source": candidate.geometry_source,
                    "annual_electricity_kwh": (
                        f"{candidate.annual_electricity_kwh:.2f}"
                        if candidate.annual_electricity_kwh
                        else ""
                    ),
                    "electricity_source": candidate.electricity_source,
                    "model_notes": (
                        "Intraday/end-use shape modeled from NREL ComStock; "
                        + (
                            "annual electricity anchored to Philadelphia 2024 "
                            "reported benchmarking."
                            if candidate.annual_electricity_kwh
                            else "annual electricity calibrated using Temple FY2025 "
                            "campus electricity EUI because no building-level reported "
                            "electricity match was available."
                        )
                    ),
                }
            )
            geometry[slug] = candidate.footprint

    OUT_GEOMETRY.write_text(json.dumps(geometry, indent=2), encoding="utf-8")

    actual_electric = sum(
        1 for _, candidate in selected_pairs if candidate.annual_electricity_kwh
    )
    report = {
        "status": "ok",
        "building_count": len(selected_pairs),
        "reported_electricity_count": actual_electric,
        "campus_eui_modeled_count": len(selected_pairs) - actual_electric,
        "service_diagnostics": service_diagnostics,
        "service_field_samples": service_field_samples,
        "benchmark_row_count": len(benchmark_rows),
        "benchmark_field_sample": benchmark_field_sample,
        "rejected_missing_area_count": len(rejected),
        "rejected_missing_area": rejected,
        "sources": {
            "geometry_and_facility_attributes": [
                f"{TEMPLE_SERVICE_ROOT}/{service}/FeatureServer"
                for service in TEMPLE_SERVICES
            ],
            "energy_benchmarking": PHILA_BENCHMARK_URL,
        },
    }
    OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
