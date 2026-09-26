from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_connection
from app import repository
from app.services.intervention_model import apply_interventions

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


@app.get("/api/buildings/{slug}")
def building(slug: str):
    row = repository.get_building(slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return row


@app.get("/api/buildings/{slug}/profile")
def profile(slug: str, scenario: str = Query("baseline", min_length=1)):
    if repository.get_building(slug) is None:
        raise HTTPException(status_code=404, detail="Building not found")
    rows = repository.get_profile(slug, scenario)
    if not rows:
        raise HTTPException(status_code=404, detail="Profile not found")
    return rows


@app.get("/api/buildings/{slug}/state")
def state(
    slug: str,
    hour: int = Query(..., ge=0, le=23),
    scenario: str = Query("baseline", min_length=1),
):
    if repository.get_building(slug) is None:
        raise HTTPException(status_code=404, detail="Building not found")
    row = repository.get_state(slug, hour, scenario)
    if row is None:
        raise HTTPException(status_code=404, detail="State not found")
    return row


@app.get("/api/weather")
def weather():
    rows = repository.get_weather()
    if not rows:
        raise HTTPException(status_code=404, detail="Weather cache not found")
    return rows


class InterventionRequest(BaseModel):
    led: bool = False
    hvac: bool = False
    solar: bool = False


@app.post("/api/buildings/{slug}/simulate")
def simulate(slug: str, request: InterventionRequest):
    building_row = repository.get_building(slug)
    if building_row is None:
        raise HTTPException(status_code=404, detail="Building not found")

    profile_rows = repository.get_profile(slug, "baseline")
    weather_rows = repository.get_weather()

    if not profile_rows:
        raise HTTPException(status_code=404, detail="Baseline profile not found")
    if len(weather_rows) != 24:
        raise HTTPException(status_code=503, detail="Weather cache unavailable")

    return apply_interventions(
        slug,
        profile_rows,
        weather_rows,
        floor_area_ft2=float(building_row["floor_area_ft2"]),
        led=request.led,
        hvac=request.hvac,
        solar=request.solar,
    )
