import os

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_connection
from app import repository
from app.services.intervention_model import apply_interventions
from app.services.snowflake_service import (
    SnowflakeConfigurationError,
    complete_with_cortex,
    connection_diagnostics,
)
from app.config.model_parameters import (
    INTERVAL_MINUTES,
    INTERVALS_PER_DAY,
    SIMULATION_END_DATE,
    SIMULATION_INTERVALS,
    SIMULATION_START_DATE,
)

app = FastAPI(
    title="Temple Twin API",
    version="0.4.0",
    description="Tiger-backed API for the Temple Twin digital twin.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        database_ok = check_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Tiger Data unavailable: {exc}")
    return {"status": "ok", "database": "tiger", "database_ok": database_ok}


@app.get("/api/buildings")
def buildings():
    return repository.list_buildings()


@app.get("/api/simulation")
def simulation():
    return {
        "start_date": SIMULATION_START_DATE,
        "end_date": SIMULATION_END_DATE,
        "interval_minutes": INTERVAL_MINUTES,
        "intervals_per_day": INTERVALS_PER_DAY,
        "total_intervals": SIMULATION_INTERVALS,
    }


@app.get("/api/profiles")
def profiles(
    scenario: str = Query("baseline", min_length=1),
    date: str = Query(SIMULATION_START_DATE, min_length=10, max_length=10),
):
    rows = repository.get_all_profiles(scenario, date)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        item = dict(row)
        slug = item.pop("slug")
        grouped.setdefault(slug, []).append(item)
    return grouped


@app.get("/api/buildings/{slug}")
def building(slug: str):
    row = repository.get_building(slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return row


@app.get("/api/buildings/{slug}/profile")
def profile(
    slug: str,
    scenario: str = Query("baseline", min_length=1),
    date: str = Query(SIMULATION_START_DATE, min_length=10, max_length=10),
):
    if repository.get_building(slug) is None:
        raise HTTPException(status_code=404, detail="Building not found")
    rows = repository.get_profile(slug, scenario, date)
    if not rows:
        raise HTTPException(status_code=404, detail="Profile not found")
    return rows


@app.get("/api/buildings/{slug}/state")
def state(
    slug: str,
    hour: int = Query(..., ge=0, le=23),
    scenario: str = Query("baseline", min_length=1),
    date: str = Query(SIMULATION_START_DATE, min_length=10, max_length=10),
):
    if repository.get_building(slug) is None:
        raise HTTPException(status_code=404, detail="Building not found")
    row = repository.get_state(slug, hour, scenario, date)
    if row is None:
        raise HTTPException(status_code=404, detail="State not found")
    return row


@app.get("/api/weather")
def weather(
    date: str = Query(SIMULATION_START_DATE, min_length=10, max_length=10),
):
    rows = repository.get_weather(date)
    if not rows:
        raise HTTPException(status_code=404, detail="Weather cache not found")
    return rows


class InterventionRequest(BaseModel):
    led: bool = False
    hvac: bool = False
    solar: bool = False


def _daily_building_profile(slug: str, date: str) -> list[dict]:
    """Return one building's daily baseline profile with a campus-query fallback."""
    rows = repository.get_profile(slug, "baseline", date)
    if rows:
        return [dict(row) for row in rows]

    # Campus playback already depends on this query. Falling back to it keeps
    # interventions/chat aligned with the exact data source shown on the map.
    return [
        dict(row)
        for row in repository.get_all_profiles("baseline", date)
        if str(row["slug"]) == slug
    ]


@app.post("/api/buildings/{slug}/simulate")
def simulate(
    slug: str,
    request: InterventionRequest,
    date: str = Query(SIMULATION_START_DATE, min_length=10, max_length=10),
):
    building_row = repository.get_building(slug)
    if building_row is None:
        raise HTTPException(status_code=404, detail="Building not found")

    profile_rows = _daily_building_profile(slug, date)
    weather_rows = repository.get_weather(date)

    if not profile_rows:
        raise HTTPException(status_code=404, detail="Baseline profile not found")
    if len(weather_rows) != 24:
        raise HTTPException(
            status_code=503,
            detail=f"Weather cache unavailable for {date}",
        )

    return apply_interventions(
        slug,
        profile_rows,
        weather_rows,
        floor_area_ft2=float(building_row["floor_area_ft2"]),
        roof_area_ft2=float(building_row["roof_area_ft2"]),
        led=request.led,
        hvac=request.hvac,
        solar=request.solar,
    )


@app.get("/api/ask-temple-twin/status")
def ask_temple_twin_status():
    if os.getenv("ENABLE_DIAGNOSTICS", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return connection_diagnostics()
    except SnowflakeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Snowflake diagnostic failed: {exc}",
        )


class AskTempleTwinRequest(BaseModel):
    question: str
    building_slug: str | None = None
    date: str = SIMULATION_START_DATE
    hour: int = 12


def _resolve_building_slug(question: str, explicit_slug: str | None) -> str | None:
    if explicit_slug:
        return explicit_slug

    query = question.lower()
    for item in repository.list_buildings():
        slug = str(item["slug"])
        name = str(item["name"]).replace("\n", " ").strip().lower()
        if slug.lower() in query or name in query:
            return slug

        short_name = name.replace(" building", "").replace(" hall", "")
        if len(short_name) >= 4 and short_name in query:
            return slug

    return None


def _campus_snapshot(date: str, hour: int) -> dict:
    rows = repository.get_all_profiles("baseline", date)
    hour_rows = [
        dict(row)
        for row in rows
        if int(row["hour"]) == hour
        and getattr(row["timestamp"], "minute", 0) == 0
    ]
    if not hour_rows:
        hour_rows = [
            dict(row)
            for row in rows
            if int(row["hour"]) == hour
        ][:50]

    if not hour_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No campus energy state found for {date} at hour {hour}",
        )

    total_demand_kw = sum(float(row["demand_kw"]) for row in hour_rows)
    total_grid_import_kw = sum(
        float(row.get("grid_import_kw", row["demand_kw"]))
        for row in hour_rows
    )
    end_use_breakdown_kw = {
        "hvac": round(sum(float(row.get("hvac_kw", 0.0)) for row in hour_rows), 2),
        "lighting": round(sum(float(row.get("lighting_kw", 0.0)) for row in hour_rows), 2),
        "process": round(sum(float(row.get("process_kw", 0.0)) for row in hour_rows), 2),
        "other": round(sum(float(row.get("other_kw", 0.0)) for row in hour_rows), 2),
    }
    top = sorted(
        hour_rows,
        key=lambda row: float(row["demand_kw"]),
        reverse=True,
    )[:5]

    names = {
        item["slug"]: item["name"]
        for item in repository.list_buildings()
    }

    return {
        "scope": "campus",
        "date": date,
        "hour": hour,
        "units": {
            "demand": "kW",
            "grid_import": "kW",
            "end_use": "kW",
            "energy_intensity": "W/ft²",
        },
        "building_count": len(hour_rows),
        "campus_demand_kw": round(total_demand_kw, 2),
        "campus_grid_import_kw": round(total_grid_import_kw, 2),
        "end_use_breakdown_kw": end_use_breakdown_kw,
        "highest_demand_buildings": [
            {
                "slug": row["slug"],
                "name": names.get(row["slug"], row["slug"]),
                "demand_kw": round(float(row["demand_kw"]), 2),
                "energy_intensity_w_ft2": round(
                    float(row["energy_intensity_w_ft2"]), 3
                ),
            }
            for row in top
        ],
    }


def _building_context(slug: str, date: str, hour: int) -> dict:
    building_row = repository.get_building(slug)
    if building_row is None:
        raise HTTPException(status_code=404, detail="Building not found")

    profile_rows = _daily_building_profile(slug, date)

    state_row = repository.get_state(slug, hour, "baseline", date)
    if state_row is None and profile_rows:
        state_row = next(
            (
                row
                for row in profile_rows
                if int(row["hour"]) == hour
                and getattr(row["timestamp"], "minute", 0) == 0
            ),
            next((row for row in profile_rows if int(row["hour"]) == hour), None),
        )
    if state_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Building state not found for {slug} on {date} at hour {hour}",
        )

    weather_rows = repository.get_weather(date)
    weather_row = next(
        (
            dict(row)
            for row in weather_rows
            if getattr(row["timestamp"], "hour", -1) == hour
        ),
        None,
    )

    state = dict(state_row)

    intervention_snapshot = {}
    if len(weather_rows) == 24 and profile_rows:
        profile_dicts = [dict(row) for row in profile_rows]
        weather_dicts = [dict(row) for row in weather_rows]
        scenario_flags = {
            "led": {"led": True},
            "hvac": {"hvac": True},
            "solar": {"solar": True},
            "combined": {"led": True, "hvac": True, "solar": True},
        }
        for scenario_name, flags in scenario_flags.items():
            simulated = apply_interventions(
                slug,
                profile_dicts,
                weather_dicts,
                floor_area_ft2=float(building_row["floor_area_ft2"]),
                roof_area_ft2=float(building_row["roof_area_ft2"]),
                **flags,
            )
            scenario_row = next(
                (
                    row
                    for row in simulated
                    if int(row["hour"]) == hour
                    and getattr(row["timestamp"], "minute", 0) == 0
                ),
                next((row for row in simulated if int(row["hour"]) == hour), None),
            )
            if scenario_row is not None:
                intervention_snapshot[scenario_name] = {
                    "demand_kw": round(float(scenario_row["demand_kw"]), 2),
                    "grid_import_kw": round(float(scenario_row["grid_import_kw"]), 2),
                    "solar_kw": round(float(scenario_row["solar_kw"]), 2),
                    "carbon_kg_per_interval": round(float(scenario_row["carbon_kg"]), 3),
                }

    return {
        "scope": "building",
        "date": date,
        "hour": hour,
        "units": {
            "demand": "kW",
            "grid_import": "kW",
            "end_use": "kW",
            "solar": "kW",
            "energy_intensity": "W/ft²",
            "carbon": "kg CO2e per 15-minute interval",
        },
        "building": {
            "slug": building_row["slug"],
            "name": building_row["name"],
            "building_type": building_row["building_type"],
            "floor_area_ft2": building_row["floor_area_ft2"],
            "roof_area_ft2": building_row.get("roof_area_ft2"),
            "archetype": building_row.get("archetype"),
            "data_confidence": building_row.get("data_confidence"),
            "annual_electricity_kwh": building_row.get("annual_electricity_kwh"),
            "electricity_source": building_row.get("electricity_source"),
            "model_notes": building_row.get("model_notes"),
        },
        "state": {
            "timestamp": state["timestamp"],
            "demand_kw": state["demand_kw"],
            "hvac_kw": state["hvac_kw"],
            "lighting_kw": state["lighting_kw"],
            "process_kw": state["process_kw"],
            "other_kw": state["other_kw"],
            "grid_import_kw": state["grid_import_kw"],
            "energy_intensity_w_ft2": state["energy_intensity_w_ft2"],
            "carbon_kg": state["carbon_kg"],
        },
        "weather": weather_row,
        "intervention_snapshot": intervention_snapshot,
        "model_assumptions": {
            "interval_minutes": INTERVAL_MINUTES,
            "profile_source": "NREL ComStock Philadelphia County",
            "weather_source": "Open-Meteo historical weather",
            "carbon_source": "EPA eGRID RFCE",
        },
    }


@app.post("/api/ask-temple-twin")
def ask_temple_twin(request: AskTempleTwinRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    if request.hour < 0 or request.hour > 23:
        raise HTTPException(status_code=422, detail="Hour must be between 0 and 23")

    slug = _resolve_building_slug(question, request.building_slug)
    context = (
        _building_context(slug, request.date, request.hour)
        if slug
        else _campus_snapshot(request.date, request.hour)
    )

    try:
        answer = complete_with_cortex(question, context)
    except SnowflakeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Snowflake Cortex request failed: {exc}",
        )

    return {
        "answer": answer,
        "model": "llama3.1-8b",
        "building_slug": slug,
        "date": request.date,
        "hour": request.hour,
    }
