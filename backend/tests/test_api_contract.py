import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_BUILDING = {
    "id": 1,
    "slug": "serc",
    "name": "Science Education and Research Center (SERC)",
    "floor_area_ft2": 250000.0,
}

SAMPLE_PROFILE = []
for index in range(96):
    hour = index // 4
    minute = (index % 4) * 15
    SAMPLE_PROFILE.append(
        {
            "timestamp": f"2018-09-01T{hour:02d}:{minute:02d}:00",
            "hour": hour,
            "hvac_kw": 100.0,
            "lighting_kw": 50.0,
            "process_kw": 200.0,
            "other_kw": 25.0,
            "demand_kw": 375.0,
            "solar_kw": 0.0,
            "grid_import_kw": 375.0,
            "energy_intensity_w_ft2": 1.5,
            "carbon_kg": None,
        }
    )


@patch("app.main.repository.get_building", return_value=SAMPLE_BUILDING)
@patch("app.main.repository.get_profile", return_value=SAMPLE_PROFILE)
def test_profile_endpoint_returns_daily_window(mock_profile, mock_building):
    response = client.get("/api/buildings/serc/profile")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 96
    assert [row["timestamp"] for row in body] == sorted(row["timestamp"] for row in body)


@patch("app.main.repository.get_building", return_value=SAMPLE_BUILDING)
@patch("app.main.repository.get_state", return_value=SAMPLE_PROFILE[56])
def test_state_endpoint_still_returns_requested_hour(mock_state, mock_building):
    response = client.get("/api/buildings/serc/state?hour=14")
    assert response.status_code == 200
    assert response.json()["hour"] == 14


@patch(
    "app.main.repository.get_weather",
    return_value=[
        {
            "timestamp": f"2018-09-01T{hour:02d}:00:00",
            "temperature_f": 70.0,
            "relative_humidity_pct": 50.0,
            "cloud_cover_pct": 20.0,
            "ghi_w_m2": 0.0,
            "dni_w_m2": 0.0,
            "weather_code": 1,
            "source": "Open-Meteo historical weather API",
        }
        for hour in range(24)
    ],
)
def test_weather_endpoint_returns_cached_day(mock_weather):
    response = client.get("/api/weather")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 24


def test_simulation_endpoint_describes_three_month_window():
    response = client.get("/api/simulation")
    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2018-09-01"
    assert body["end_date"] == "2018-11-30"
    assert body["intervals_per_day"] == 96
    assert body["total_intervals"] == 8736
