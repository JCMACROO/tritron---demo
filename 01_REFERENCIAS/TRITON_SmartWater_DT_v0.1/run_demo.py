#!/usr/bin/env python
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from triton_dt.core import run_simulation
from triton_dt.metrics import calculate_metrics, attach_ai
from triton_dt.ai import evaluate_anomaly_detector
from triton_dt.io import save_run


def main():
    ap = argparse.ArgumentParser(description="TRITON Smart Water DT v0.1")
    ap.add_argument("--backend", choices=["auto", "lite", "wntr"], default="auto")
    ap.add_argument("--scenario", choices=["baseline", "leak", "sensor_spoof", "pipe_closure"], default="leak")
    ap.add_argument("--inp", default=None, help="EPANET .inp; sólo backend WNTR")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config/default.yaml").read_text(encoding="utf-8"))
    simcfg, scfg, aicfg = cfg["simulation"], cfg["scenarios"], cfg["ai"]
    kwargs = dict(
        duration_hours=simcfg["duration_hours"],
        event_start_hour=scfg["event_start_hour"], event_end_hour=scfg["event_end_hour"],
        leak_node=scfg["leak_node"], leak_diameter_mm=scfg["leak_diameter_mm"],
        spoof_node=scfg["spoof_node"], spoof_bias_m=scfg["spoof_bias_m"],
        close_pipe=scfg["close_pipe"], required_pressure_m=simcfg["required_pressure_m"],
        pump_efficiency=simcfg["pump_efficiency"])
    if args.inp:
        kwargs["inp_path"] = args.inp

    baseline = run_simulation(backend=args.backend, scenario="baseline", **kwargs)
    scenario = run_simulation(backend=args.backend, scenario=args.scenario, **kwargs)
    sensors = cfg["sensors"]["pressure_nodes"]
    ai_eval = evaluate_anomaly_detector(baseline, scenario, sensors,
                                        contamination=aicfg["contamination"],
                                        random_state=aicfg["random_state"])
    metrics = attach_ai(calculate_metrics(scenario, simcfg["required_pressure_m"], simcfg["timestep_hours"]), ai_eval)
    payload = save_run(ROOT / "output", args.scenario, scenario, metrics, ai_eval)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
