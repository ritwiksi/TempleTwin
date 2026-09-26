"""Open-Meteo historical weather ingestion and bounded HVAC adjustment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config.model_parameters import (
    COOLING_BALANCE_F,
    COOLING_BETA_PER_F,
    HEATING_BALANCE_F,
    HEATING_BETA_PER_F,
    HVAC_WEATHER_FACTOR_MAX,
    HVAC_WEATHER_FACTOR_MIN,
    SIMULATION_WEATHER_HOURS,
    TEMPLE_LATITUDE,
    TEMPLE_LONGITUDE,
    WEATHER_END_DATE,
    WEATHER_START_DATE,
)


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


@dataclass(frozen=True)
class WeatherHour:
    timestamp: str
    temperature_f: float
    relative_humidity_pct: float
    cloud_cover_pct: float
    ghi_w_m2: float
    dni_w_m2: float
    weather_code: int
    source: str = "Open-Meteo historical weather API"


def fetch_open_meteo_weather() -> list[WeatherHour]:
    params = {
        "latitude": TEMPLE_LATITUDE,
        "longitude": TEMPLE_LONGITUDE,
        "start_date": WEATHER_START_DATE,
        "end_date": WEATHER_END_DATE,
        "hourly": (
            "temperature_2m,relative_humidity_2m,cloud_cover,"
            "shortwave_radiation,direct_normal_irradiance,weather_code"
        ),
        "temperature_unit": "fahrenheit",
        "timezone": "America/New_York",
    }
    url = f"{OPEN_METEO_ARCHIVE_URL}?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    if len(times) != SIMULATION_WEATHER_HOURS:
        raise RuntimeError(
            f"Expected {SIMULATION_WEATHER_HOURS} Open-Meteo hourly rows, "
            f"got {len(times)}"
        )

    rows = []
    for index, timestamp in enumerate(times):
        rows.append(
            WeatherHour(
                timestamp=timestamp,
                temperature_f=float(hourly["temperature_2m"][index]),
                relative_humidity_pct=float(hourly["relative_humidity_2m"][index]),
                cloud_cover_pct=float(hourly["cloud_cover"][index]),
                ghi_w_m2=float(hourly["shortwave_radiation"][index] or 0),
                dni_w_m2=float(hourly["direct_normal_irradiance"][index] or 0),
                weather_code=int(hourly["weather_code"][index]),
            )
        )
    return rows


def weather_factor(temperature_f: float) -> float:
    """Return a modest bounded multiplier applied to HVAC only."""
    cooling_degree = max(temperature_f - COOLING_BALANCE_F, 0.0)
    heating_degree = max(HEATING_BALANCE_F - temperature_f, 0.0)
    factor = (
        1.0
        + COOLING_BETA_PER_F * cooling_degree
        + HEATING_BETA_PER_F * heating_degree
    )
    return min(max(factor, HVAC_WEATHER_FACTOR_MIN), HVAC_WEATHER_FACTOR_MAX)


def interpolate_temperature(weather: list[WeatherHour], timestamp: str) -> float:
    """Interpolate hourly weather across the continuous simulation window."""
    if not weather:
        raise ValueError("Weather rows are empty")

    ts = datetime.fromisoformat(timestamp)
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)

    first = datetime.fromisoformat(weather[0].timestamp)
    hours_from_start = (ts - first).total_seconds() / 3600.0
    index = int(hours_from_start)
    fraction = hours_from_start - index

    if index < 0 or index >= len(weather):
        raise ValueError(f"Timestamp {timestamp} is outside cached weather range")

    current = weather[index].temperature_f
    if index + 1 >= len(weather):
        return current
    next_temp = weather[index + 1].temperature_f
    return current + (next_temp - current) * fraction


def adjust_hvac_kw(hvac_kw: float, temperature_f: float) -> float:
    return max(hvac_kw * weather_factor(temperature_f), 0.0)


def weather_with_fallback(fetch_fn, cached_fn):
    """Use Open-Meteo when available; otherwise return cached Tiger weather."""
    try:
        rows = fetch_fn()
        return rows, False
    except Exception:
        cached = cached_fn()
        if not cached:
            raise
        return cached, True
