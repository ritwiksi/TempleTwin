import sys
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

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



SAMPLE_PROFILE_SEP14 = [
    {
        **row,
        "timestamp": row["timestamp"].replace("2018-09-01", "2018-09-14"),
    }
    for row in SAMPLE_PROFILE
]


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


@patch(
    "app.main.repository.get_weather",
    return_value=[
        {
            "timestamp": f"2018-09-14T{hour:02d}:00:00",
            "temperature_f": 70.0,
            "relative_humidity_pct": 50.0,
            "cloud_cover_pct": 20.0,
            "ghi_w_m2": 500.0 if 8 <= hour <= 17 else 0.0,
            "dni_w_m2": 400.0 if 8 <= hour <= 17 else 0.0,
            "weather_code": 1,
            "source": "Open-Meteo historical weather API",
        }
        for hour in range(24)
    ],
)
@patch("app.main.repository.get_profile", return_value=SAMPLE_PROFILE_SEP14)
@patch(
    "app.main.repository.get_building",
    return_value={
        **SAMPLE_BUILDING,
        "roof_area_ft2": 35000.0,
    },
)
def test_simulate_endpoint_honors_date_and_intervention_flags(
    mock_building,
    mock_profile,
    mock_weather,
):
    response = client.post(
        "/api/buildings/serc/simulate?date=2018-09-14",
        json={"led": True, "hvac": True, "solar": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 96
    noon = body[48]
    assert noon["lighting_kw"] < SAMPLE_PROFILE[48]["lighting_kw"]
    assert noon["hvac_kw"] < SAMPLE_PROFILE[48]["hvac_kw"]
    assert noon["led_reduction_fraction"] > 0
    assert noon["hvac_controls_achieved_savings_fraction"] > 0
    assert noon["solar_kw"] > 0
    assert noon["grid_import_kw"] < noon["demand_kw"]

    mock_profile.assert_called_once_with("serc", "baseline", "2018-09-14")
    mock_weather.assert_called_once_with("2018-09-14")


@patch(
    "app.main.repository.get_weather",
    return_value=[
        {
            "timestamp": f"2018-09-14T{hour:02d}:00:00",
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
@patch("app.main.repository.get_profile", return_value=SAMPLE_PROFILE_SEP14)
@patch(
    "app.main.repository.get_building",
    return_value={
        **SAMPLE_BUILDING,
        "roof_area_ft2": 35000.0,
    },
)
def test_simulate_endpoint_can_return_baseline_when_all_flags_off(
    mock_building,
    mock_profile,
    mock_weather,
):
    response = client.post(
        "/api/buildings/serc/simulate?date=2018-09-14",
        json={"led": False, "hvac": False, "solar": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 96
    assert body[40]["demand_kw"] == SAMPLE_PROFILE[40]["demand_kw"]
    assert body[40]["grid_import_kw"] == SAMPLE_PROFILE[40]["grid_import_kw"]


@patch("app.main.complete_with_cortex", return_value="SERC demand is driven mainly by process and HVAC load.")
@patch(
    "app.main.repository.get_weather",
    return_value=[
        {
            "timestamp": datetime(2018, 9, 14, hour, 0),
            "temperature_f": 78.0,
            "relative_humidity_pct": 52.0,
            "cloud_cover_pct": 15.0,
            "ghi_w_m2": 500.0 if 8 <= hour <= 17 else 0.0,
            "dni_w_m2": 400.0 if 8 <= hour <= 17 else 0.0,
            "weather_code": 1,
            "source": "Open-Meteo historical weather API",
        }
        for hour in range(24)
    ],
)
@patch(
    "app.main.repository.get_state",
    return_value={
        **SAMPLE_PROFILE_SEP14[56],
        "timestamp": datetime(2018, 9, 14, 14, 0),
    },
)
@patch(
    "app.main.repository.get_building",
    return_value={
        **SAMPLE_BUILDING,
        "roof_area_ft2": 35000.0,
        "building_type": "ACADEMIC",
        "archetype": "research/laboratory",
        "data_confidence": "reported-electricity",
        "annual_electricity_kwh": 3966580.33,
        "electricity_source": "City of Philadelphia 2024 Building Energy Benchmarking",
        "model_notes": "ComStock load shape anchored to annual electricity.",
    },
)
def test_ask_temple_twin_grounds_cortex_in_tiger_context(
    mock_building,
    mock_state,
    mock_weather,
    mock_complete,
):
    response = client.post(
        "/api/ask-temple-twin",
        json={
            "question": "Why is SERC using so much energy right now?",
            "building_slug": "serc",
            "date": "2018-09-14",
            "hour": 14,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["building_slug"] == "serc"
    assert body["answer"].startswith("SERC demand")
    assert body["date"] == "2018-09-14"
    assert body["hour"] == 14

    question, context = mock_complete.call_args.args
    assert question == "Why is SERC using so much energy right now?"
    assert context["scope"] == "building"
    assert context["building"]["name"] == SAMPLE_BUILDING["name"]
    assert context["state"]["demand_kw"] == SAMPLE_PROFILE_SEP14[56]["demand_kw"]
    assert context["weather"]["temperature_f"] == 78.0


@patch("app.main.complete_with_cortex", return_value="Campus demand is concentrated in the highest-load buildings.")
@patch(
    "app.main.repository.list_buildings",
    return_value=[
        {"slug": "serc", "name": "Science Education and Research Center (SERC)"},
        {"slug": "beury", "name": "Beury Hall"},
    ],
)
@patch(
    "app.main.repository.get_all_profiles",
    return_value=[
        {
            "slug": "serc",
            "timestamp": datetime(2018, 9, 14, 14, 0),
            "hour": 14,
            "demand_kw": 500.0,
            "energy_intensity_w_ft2": 2.0,
        },
        {
            "slug": "beury",
            "timestamp": datetime(2018, 9, 14, 14, 0),
            "hour": 14,
            "demand_kw": 300.0,
            "energy_intensity_w_ft2": 1.5,
        },
    ],
)
def test_ask_temple_twin_can_answer_campus_question(
    mock_profiles,
    mock_buildings,
    mock_complete,
):
    response = client.post(
        "/api/ask-temple-twin",
        json={
            "question": "Which buildings are driving campus load?",
            "date": "2018-09-14",
            "hour": 14,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["building_slug"] is None

    _, context = mock_complete.call_args.args
    assert context["scope"] == "campus"
    assert context["campus_demand_kw"] == 800.0
    assert context["highest_demand_buildings"][0]["slug"] == "serc"
