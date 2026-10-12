"""
TRITON Smart Water Digital Twin - Main Entrypoint
Script: main.py

Launches the interactive Streamlit dashboard or runs a headless demo benchmark.
Usage:
    python main.py              # Launches the Streamlit Web Application
    python main.py --demo       # Runs a quick CLI demo benchmark
"""

from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

# Ensure root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_cli_demo():
    """Runs a quick end-to-end benchmark from terminal."""
    print("=" * 60)
    print("🌊 TRITON Smart Water Digital Twin - Headless Demo Benchmark")
    print("=" * 60)

    from src.engine.wntr_runner import create_simple_network
    from src.scenarios.injector import ScenarioType, ScenarioConfig, execute_scenario
    from src.ai.detector import evaluate_triton_detector
    from src.ai.metrics import (
        calculate_hydraulic_and_sustainability_metrics,
        compute_triton_evidence_vector,
    )

    # 1. Physical Network
    print("\n[Phase 1] Initializing network model...")
    wn = create_simple_network(duration_hours=48)
    print(f"Network loaded: {wn.num_nodes} nodes, {wn.num_links} links.")

    # 2. Baseline & Scenario Simulation
    print("[Phase 1] Simulating Baseline hydraulic state...")
    cfg_base = ScenarioConfig(scenario_type=ScenarioType.BASELINE, duration_hours=48)
    res_base = execute_scenario(wn, cfg_base)

    print("[Phase 2] Simulating FDI Sensor Spoofing Cyberattack...")
    cfg_attack = ScenarioConfig(
        scenario_type=ScenarioType.SENSOR_SPOOF,
        spoof_node="J1",
        spoof_bias_m=18.0,
        event_start_hour=12,
        event_end_hour=24,
        duration_hours=48
    )
    res_attack = execute_scenario(wn, cfg_attack)

    # 3. AI Layer & Twin Comparator
    print("[Phase 3] AI Inference: Evaluating Physical vs Cyber Twin consistency...")
    ai_eval = evaluate_triton_detector(res_base, res_attack, sensor_nodes=["J1", "J2", "J3"])
    print(f"  AI Anomaly F1 Score: {ai_eval['f1']:.2f}")
    print(f"  Cyberattack Precision: {ai_eval['cyber_precision'] * 100:.1f}%")
    print(f"  Cyberattack Recall:    {ai_eval['cyber_recall'] * 100:.1f}%")

    # 4. Sustainability & Scorecard
    print("[Phase 4] Calculating Sustainability Metrics & TRITON Scorecard...")
    metrics = calculate_hydraulic_and_sustainability_metrics(res_attack)
    scorecard = compute_triton_evidence_vector(metrics, ai_eval)

    print(f"  Pump Energy: {metrics['pump_energy_kwh']:.1f} kWh")
    print(f"  Service Availability (>=20m): {metrics['service_availability_pct']:.1f}%")
    print(f"  Telemetry Physics Residual RMSE: {metrics['telemetry_physics_residual_rmse_m']:.2f} m")

    print("\n" + "=" * 60)
    print("📋 TRITON Framework Evidence Scorecard Preview:")
    print("=" * 60)
    print(scorecard[["Code", "Axis", "Domain Indicator", "Value", "Status"]].to_string(index=False))
    print("\n✅ Demo completed successfully!\n")


def launch_streamlit():
    """Launches the Streamlit interactive dashboard."""
    ui_script = PROJECT_ROOT / "app" / "ui.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(ui_script)]
    print(f"🚀 Launching TRITON Dashboard: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 TRITON Dashboard stopped.")


def main():
    parser = argparse.ArgumentParser(description="TRITON Smart Water Digital Twin Launcher")
    parser.add_argument("--demo", action="store_true", help="Run a quick terminal benchmark demo without UI")
    args = parser.parse_args()

    if args.demo:
        run_cli_demo()
    else:
        launch_streamlit()


if __name__ == "__main__":
    main()
