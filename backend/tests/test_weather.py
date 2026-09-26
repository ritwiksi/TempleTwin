import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.model_parameters import HVAC_WEATHER_FACTOR_MAX, HVAC_WEATHER_FACTOR_MIN
from app.services.weather_service import adjust_hvac_kw, weather_factor, weather_with_fallback


def test_weather_factor_is_bounded_and_modest():
    for temp in (-20, 20, 50, 65, 75, 95, 120):
        factor = weather_factor(temp)
        assert HVAC_WEATHER_FACTOR_MIN <= factor <= HVAC_WEATHER_FACTOR_MAX


def test_weather_changes_hvac_only_by_multiplier():
    base = 100.0
    mild = adjust_hvac_kw(base, 65.0)
    hot = adjust_hvac_kw(base, 90.0)
    assert mild >= 0
    assert hot >= mild
    assert hot <= base * HVAC_WEATHER_FACTOR_MAX


def test_cached_fallback_is_used_when_fetch_fails():
    cached = ["cached-row"]

    def failing_fetch():
        raise RuntimeError("network down")

    rows, used_cache = weather_with_fallback(failing_fetch, lambda: cached)
    assert rows == cached
    assert used_cache is True
