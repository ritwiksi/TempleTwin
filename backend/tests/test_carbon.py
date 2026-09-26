import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.model_parameters import EGRID_RFCE_CO2E_KG_PER_KWH


def test_egrid_rfce_factor_conversion():
    # EPA eGRID2023 RFCE: 599.170 lb CO2e/MWh.
    expected = 599.170 * 0.45359237 / 1000.0
    assert math.isclose(EGRID_RFCE_CO2E_KG_PER_KWH, expected, rel_tol=1e-12)


def test_interval_carbon_calculation_is_reasonable():
    demand_kw = 400.0
    interval_kwh = demand_kw * 0.25
    carbon_kg = interval_kwh * EGRID_RFCE_CO2E_KG_PER_KWH
    assert 20.0 < carbon_kg < 35.0
