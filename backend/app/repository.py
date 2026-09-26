from __future__ import annotations

from app.buildings import load_buildings
from app.database import get_connection


def _metadata_by_slug() -> dict[str, object]:
    return {building.slug: building for building in load_buildings()}


def _enrich_building(row: dict) -> dict:
    building = _metadata_by_slug().get(row["slug"])
    if building is None:
        return row
    result = dict(row)
    result.update(
        {
            "roof_area_ft2": building.roof_area_ft2,
            "archetype": building.archetype,
            "comstock_type": building.comstock_type,
            "data_confidence": building.data_confidence,
            "geometry_source": building.geometry_source,
            "annual_electricity_kwh": building.annual_electricity_kwh,
            "electricity_source": building.electricity_source,
            "footprint": list(building.footprint),
        }
    )
    return result


def list_buildings() -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, slug, name, floor_area_ft2, latitude, longitude,
                   approx_height_m, building_type, area_source,
                   area_is_estimated, modeled_annual_eui_kwh_ft2, model_notes
            FROM buildings
            ORDER BY name
            """
        )
        return [_enrich_building(dict(row)) for row in cur.fetchall()]


def get_building(slug: str) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, slug, name, floor_area_ft2, latitude, longitude,
                   approx_height_m, building_type, area_source,
                   area_is_estimated, modeled_annual_eui_kwh_ft2, model_notes
            FROM buildings
            WHERE slug = %s
            """,
            (slug,),
        )
        row = cur.fetchone()
        return _enrich_building(dict(row)) if row else None


def get_profile(
    slug: str,
    scenario: str = "baseline",
    date: str | None = None,
) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.timestamp, EXTRACT(HOUR FROM s.timestamp)::int AS hour,
                   s.hvac_kw, s.lighting_kw, s.process_kw, s.other_kw,
                   s.demand_kw, s.solar_kw, s.grid_import_kw,
                   s.energy_intensity_w_ft2, s.carbon_kg
            FROM building_hourly_state s
            JOIN buildings b ON b.id = s.building_id
            WHERE b.slug = %s AND s.scenario_id = %s
              AND (%s IS NULL OR s.timestamp::date = %s::date)
            ORDER BY s.timestamp
            """,
            (slug, scenario, date, date),
        )
        return list(cur.fetchall())


def get_all_profiles(
    scenario: str = "baseline",
    date: str | None = None,
) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT b.slug, s.timestamp,
                   EXTRACT(HOUR FROM s.timestamp)::int AS hour,
                   s.hvac_kw, s.lighting_kw, s.process_kw, s.other_kw,
                   s.demand_kw, s.solar_kw, s.grid_import_kw,
                   s.energy_intensity_w_ft2, s.carbon_kg
            FROM building_hourly_state s
            JOIN buildings b ON b.id = s.building_id
            WHERE s.scenario_id = %s
              AND (%s IS NULL OR s.timestamp::date = %s::date)
            ORDER BY b.slug, s.timestamp
            """,
            (scenario, date, date),
        )
        return list(cur.fetchall())


def get_state(
    slug: str,
    hour: int,
    scenario: str = "baseline",
    date: str | None = None,
) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.timestamp, EXTRACT(HOUR FROM s.timestamp)::int AS hour,
                   s.hvac_kw, s.lighting_kw, s.process_kw, s.other_kw,
                   s.demand_kw, s.solar_kw, s.grid_import_kw,
                   s.energy_intensity_w_ft2, s.carbon_kg
            FROM building_hourly_state s
            JOIN buildings b ON b.id = s.building_id
            WHERE b.slug = %s
              AND s.scenario_id = %s
              AND EXTRACT(HOUR FROM s.timestamp)::int = %s
              AND (%s IS NULL OR s.timestamp::date = %s::date)
            ORDER BY s.timestamp
            LIMIT 1
            """,
            (slug, scenario, hour, date, date),
        )
        return cur.fetchone()


def get_weather(date: str | None = None) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT timestamp, temperature_f, relative_humidity_pct,
                   cloud_cover_pct, ghi_w_m2, dni_w_m2, weather_code, source
            FROM weather_hourly
            WHERE (%s IS NULL OR timestamp::date = %s::date)
            ORDER BY timestamp
            """,
            (date, date),
        )
        return list(cur.fetchall())
