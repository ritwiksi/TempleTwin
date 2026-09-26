#!/usr/bin/env python3
"""Create/update Tiger schema, cache weather, and seed weather-adjusted 15-minute profiles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.buildings import load_buildings
from app.config.model_parameters import (
    CAMPUS_ELECTRIC_EUI_KWH_FT2,
    EGRID_RFCE_CO2E_KG_PER_KWH,
    INTERVAL_MINUTES,
    INTERVALS_PER_DAY,
)
from app.database import get_connection
from app.services.profile_model import generate_friday_profile
from app.services.weather_service import (
    WeatherHour,
    adjust_hvac_kw,
    fetch_open_meteo_weather,
    interpolate_temperature,
    weather_with_fallback,
)

SCHEMA = BACKEND / "app" / "schema.sql"


def initialize_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
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
                    CAMPUS_ELECTRIC_EUI_KWH_FT2,
                    building.model_notes,
                ),
            )
            ids[building.slug] = cur.fetchone()["id"]
    conn.commit()
    return ids


def read_cached_weather(conn) -> list[WeatherHour]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT timestamp, temperature_f, relative_humidity_pct,
                   cloud_cover_pct, ghi_w_m2, dni_w_m2, weather_code, source
            FROM weather_hourly
            ORDER BY timestamp
            """
        )
        rows = cur.fetchall()
    return [
        WeatherHour(
            timestamp=row["timestamp"].strftime("%Y-%m-%dT%H:%M"),
            temperature_f=row["temperature_f"],
            relative_humidity_pct=row["relative_humidity_pct"],
            cloud_cover_pct=row["cloud_cover_pct"],
            ghi_w_m2=row["ghi_w_m2"],
            dni_w_m2=row["dni_w_m2"],
            weather_code=row["weather_code"],
            source=row["source"],
        )
        for row in rows
    ]


def cache_weather(conn, rows: list[WeatherHour]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM weather_hourly")
        for row in rows:
            cur.execute(
                """
                INSERT INTO weather_hourly (
                    timestamp, temperature_f, relative_humidity_pct,
                    cloud_cover_pct, ghi_w_m2, dni_w_m2, weather_code, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row.timestamp,
                    row.temperature_f,
                    row.relative_humidity_pct,
                    row.cloud_cover_pct,
                    row.ghi_w_m2,
                    row.dni_w_m2,
                    row.weather_code,
                    row.source,
                ),
            )
    conn.commit()


def load_weather(conn) -> list[WeatherHour]:
    rows, used_cache = weather_with_fallback(
        fetch_open_meteo_weather,
        lambda: read_cached_weather(conn),
    )
    if not used_cache:
        cache_weather(conn, rows)
        print("Weather: refreshed from Open-Meteo and cached in Tiger.")
    else:
        print("Weather: Open-Meteo unavailable; using Tiger cache.")
    return rows


def seed_profiles(conn, building_ids: dict[str, int], weather: list[WeatherHour]) -> None:
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
                temperature_f = interpolate_temperature(weather, row.timestamp)
                adjusted_hvac_kw = adjust_hvac_kw(row.hvac_kw, temperature_f)
                demand_kw = (
                    adjusted_hvac_kw
                    + row.lighting_kw
                    + row.process_kw
                    + row.other_kw
                )
                intensity = demand_kw * 1000.0 / building.floor_area_ft2
                interval_kwh = demand_kw * (INTERVAL_MINUTES / 60.0)
                carbon_kg = interval_kwh * EGRID_RFCE_CO2E_KG_PER_KWH

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
                        %s, 0, %s, %s, %s
                    )
                    """,
                    (
                        row.timestamp,
                        building_ids[building.slug],
                        adjusted_hvac_kw,
                        row.lighting_kw,
                        row.process_kw,
                        row.other_kw,
                        demand_kw,
                        demand_kw,
                        intensity,
                        carbon_kg,
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
        cur.execute("SELECT COUNT(*) AS weather_count FROM weather_hourly")
        weather_count = cur.fetchone()["weather_count"]

    expected = {"serc", "beury", "engineering"}
    found = {row["slug"] for row in rows}
    if found != expected or any(row["row_count"] != INTERVALS_PER_DAY for row in rows):
        raise RuntimeError(f"Tiger seed verification failed: {rows}")
    if weather_count != 24:
        raise RuntimeError(f"Expected 24 cached weather rows, got {weather_count}")

    for row in rows:
        print(
            f"{row['slug']}: {row['row_count']} 15-minute rows "
            f"({row['first_ts']} -> {row['last_ts']})"
        )
    print(f"weather: {weather_count} hourly rows cached in Tiger")


def main() -> None:
    with get_connection() as conn:
        initialize_schema(conn)
        building_ids = upsert_buildings(conn)
        weather = load_weather(conn)
        seed_profiles(conn, building_ids, weather)
        verify(conn)
    print("Tiger Data seed complete.")


if __name__ == "__main__":
    main()
