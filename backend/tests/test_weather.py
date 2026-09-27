import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.weather_service import weather_with_fallback


def test_cached_fallback_is_used_when_fetch_fails():
    cached = ["cached-row"]

    def failing_fetch():
        raise RuntimeError("network down")

    rows, used_cache = weather_with_fallback(failing_fetch, lambda: cached)
    assert rows == cached
    assert used_cache is True
