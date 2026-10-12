from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from triton_dt.core import run_simulation
from triton_dt.metrics import calculate_metrics


def test_lite_baseline_runs():
    r = run_simulation(backend="lite", scenario="baseline", duration_hours=24)
    m = calculate_metrics(r)
    assert len(r["pressure"]) > 0
    assert m["delivered_water_m3"] > 0
    assert m["minimum_pressure_m"] >= 0


def test_lite_leak_produces_loss():
    r = run_simulation(backend="lite", scenario="leak", duration_hours=24,
                       event_start_hour=4, event_end_hour=12)
    m = calculate_metrics(r)
    assert m["leak_volume_m3"] > 0
