#!/usr/bin/env python3
"""Create the Tiger schema and seed Temple Twin's Milestone 3 modeled profiles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.buildings import load_buildings
from app.config.model_parameters import MODELED_EUI_KWH_FT2
from app.database import get_connection
from app.services.profile_model import generate_friday_profile


SCHEMA = BACKEND / "app" / "schema.sql"


def initialize_schema(conn) -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def upsert_buildings(conn) -> dict[str, int]:
    ids = {}
    with conn.cursor() as cur:
        for building in load_buildings():
            cur.execute(
                """
                INSERT INTO buildings (
                    slug, name, floor_area_ft2, latitude, longitude,
                    approx_height_m, building_type, area_source,
                    area_is_estimated, modeled_annual_eui_kwh_ft2, model_notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    floor_area_ft2 = EXCLUDED.floor_area_ft2,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    approx_height_m = EXCLUDED.approx_height_m,
                    building_type = EXCLUDED.building_type,
                    area_source = EXCLUDED.area_source,
                    area_is_estimated = EXCLUDED.area_is_estimated,
                    modeled_annual_eui_kwh_ft2 = EXCLUDED.modeled_annual_eui_kwh_ft2,
                    model_notes = EXCLUDED.model_notes
                RETURNING id
                """,
                (
                    building.slug,
                    building.display_name,
                    building.floor_area_ft2,
                    building.latitude,
                    building.longitude,
                    building.approx_height_m,
                    building.building_type,
                    building.area_source,
                    building.area_is_estimated,
                    MODELED_EUI_KWH_FT2[building.slug],
                    building.model_notes,
                ),
            )
            ids[building.slug] = cur.fetchone()["id"]
    conn.commit()
    return ids


def seed_profiles(conn, building_ids: dict[str, int]) -> None:
    with conn.cursor() as cur:
        for building in load_buildings():
            rows = generate_friday_profile(building.slug)
            cur.execute(
                """
                DELETE FROM building_hourly_state
                WHERE building_id = %s AND scenario_id = 'baseline'
                """,
                (building_ids[building.slug],),
            )
            for row in rows:
                intensity = row.demand_kw * 1000.0 / building.floor_area_ft2
                cur.execute(
                    """
                    INSERT INTO building_hourly_state (
                        timestamp, building_id, scenario_id,
                        hvac_kw, lighting_kw, process_kw, other_kw,
                        demand_kw, solar_kw, grid_import_kw,
                        energy_intensity_w_ft2, carbon_kg
                    )
                    VALUES (
                        %s, %s, 'baseline',
                        %s, %s, %s, %s,
                        %s, 0, %s, %s, NULL
                    )
                    """,
                    (
                        row.timestamp,
                        building_ids[building.slug],
                        row.hvac_kw,
                        row.lighting_kw,
                        row.process_kw,
                        row.other_kw,
                        row.demand_kw,
                        row.demand_kw,
                        intensity,
                    ),
                )
    conn.commit()


def verify(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT b.slug, COUNT(*) AS row_count,
                   MIN(s.timestamp) AS first_ts,
                   MAX(s.timestamp) AS last_ts
            FROM buildings b
            JOIN building_hourly_state s ON s.building_id = b.id
            WHERE s.scenario_id = 'baseline'
            GROUP BY b.slug
            ORDER BY b.slug
            """
        )
        rows = cur.fetchall()
    expected = {"serc", "beury", "engineering"}
    found = {row["slug"] for row in rows}
    if found != expected or any(row["row_count"] != 24 for row in rows):
        raise RuntimeError(f"Tiger seed verification failed: {rows}")
    for row in rows:
        print(
            f"{row['slug']}: {row['row_count']} rows "
            f"({row['first_ts']} -> {row['last_ts']})"
        )


def main() -> None:
    with get_connection() as conn:
        initialize_schema(conn)
        building_ids = upsert_buildings(conn)
        seed_profiles(conn, building_ids)
        verify(conn)
    print("Tiger Data seed complete.")


if __name__ == "__main__":
    main()
