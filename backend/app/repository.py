from __future__ import annotations

from datetime import datetime

from app.database import get_connection


def list_buildings() -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, slug, name, floor_area_ft2, latitude, longitude,
                   approx_height_m, building_type, area_source,
                   area_is_estimated, modeled_annual_eui_kwh_ft2, model_notes
            FROM buildings
            ORDER BY id
            """
        )
        return list(cur.fetchall())


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
        return cur.fetchone()


def get_profile(slug: str, scenario: str = "baseline") -> list[dict]:
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
            ORDER BY s.timestamp
            """,
            (slug, scenario),
        )
        return list(cur.fetchall())


def get_state(slug: str, hour: int, scenario: str = "baseline") -> dict | None:
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
            ORDER BY s.timestamp
            LIMIT 1
            """,
            (slug, scenario, hour),
        )
        return cur.fetchone()
