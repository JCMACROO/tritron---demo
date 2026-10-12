"""
TRITON Digital Twin - Metrics & Sustainability Engine
Module: src.ai.metrics

Computes hydraulic performance, sustainability metrics (m3 lost, pump kWh),
telemetry integrity residuals, and maps evidence to the canonical TRITON Framework
(Cybersecurity CI, Sustainability SO, Artificial Intelligence IA).
"""

from __future__ import annotations
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd


def calculate_hydraulic_and_sustainability_metrics(
    sim_result: Dict[str, Any],
    required_pressure_m: float = 20.0,
    timestep_hours: float = 1.0
) -> Dict[str, Any]:
    """
    Computes sustainability and hydraulic resilience metrics.

    Args:
        sim_result: Output from run_hydraulic_simulation or execute_scenario.
        required_pressure_m: Minimum pressure required for satisfactory service.
        timestep_hours: Simulation timestep in hours.

    Returns:
        Dictionary with sustainability and hydraulic metrics.
    """
    p_df = sim_result["pressure"]
    d_df = sim_result["demand"]
    leak_df = sim_result["leak"]
    dt_seconds = timestep_hours * 3600.0

    # Pressure analysis
    p_phys = p_df["pressure_m"].to_numpy(dtype=float)
    p_obs = p_df["observed_pressure_m"].to_numpy(dtype=float)
    telemetry_residual = p_obs - p_phys

    mean_pressure = float(np.mean(p_phys)) if len(p_phys) > 0 else 0.0
    min_pressure = float(np.min(p_phys)) if len(p_phys) > 0 else 0.0
    service_pct = float(np.mean(p_phys >= required_pressure_m) * 100.0) if len(p_phys) > 0 else 0.0
    low_node_hours = float(np.sum(p_phys < required_pressure_m) * timestep_hours)

    # Volumetric water balance
    delivered_m3 = float(np.clip(d_df["delivered_m3s"].to_numpy(dtype=float), a_min=0, a_max=None).sum() * dt_seconds)
    requested_m3 = float(np.clip(d_df["requested_m3s"].to_numpy(dtype=float), a_min=0, a_max=None).sum() * dt_seconds)
    leak_m3 = float(np.clip(leak_df["leak_m3s"].to_numpy(dtype=float), a_min=0, a_max=None).sum() * dt_seconds)

    # Account for illicit demand burst (unregistered consumption / commercial NRW)
    burst_m3 = 0.0
    cfg = sim_result.get("config")
    if cfg is not None and getattr(cfg, "scenario_type", "") == "demand_burst":
        dt_burst_hours = max(0, getattr(cfg, "event_end_hour", 0) - getattr(cfg, "event_start_hour", 0))
        burst_m3 = float(getattr(cfg, "burst_flow_m3s", 0.0) * 3600.0 * dt_burst_hours)

    total_loss_m3 = leak_m3 + burst_m3
    demand_satisfaction_pct = float(min(100.0, (100.0 * delivered_m3 / max(requested_m3, 1e-9))))
    water_loss_pct = float(100.0 * total_loss_m3 / max(delivered_m3 + total_loss_m3, 1e-9))

    # Energy calculations
    pump_energy_kwh = float(sim_result.get("pump_energy_kwh", 0.0))
    specific_energy = float(pump_energy_kwh / max(delivered_m3, 1e-6))  # kWh / m^3

    # Telemetry physics residual: global RMSE, max residual, and active sensor RMSE
    telemetry_abs_residual = np.abs(telemetry_residual)
    residual_rmse = float(np.sqrt(np.mean(telemetry_residual ** 2))) if len(telemetry_residual) > 0 else 0.0
    max_residual_m = float(np.max(telemetry_abs_residual)) if len(telemetry_abs_residual) > 0 else 0.0

    spoofed_points = telemetry_residual[telemetry_abs_residual > 0.05]
    active_sensor_rmse = float(np.sqrt(np.mean(spoofed_points ** 2))) if len(spoofed_points) > 0 else residual_rmse

    return {
        "mean_pressure_m": round(mean_pressure, 2),
        "min_pressure_m": round(min_pressure, 2),
        "service_availability_pct": round(service_pct, 2),
        "demand_satisfaction_pct": round(demand_satisfaction_pct, 2),
        "low_pressure_node_hours": round(low_node_hours, 1),
        "delivered_water_m3": round(delivered_m3, 2),
        "requested_water_m3": round(requested_m3, 2),
        "leak_volume_m3": round(total_loss_m3, 2),
        "burst_volume_m3": round(burst_m3, 2),
        "water_loss_pct": round(water_loss_pct, 2),
        "pump_energy_kwh": round(pump_energy_kwh, 2),
        "specific_energy_kwh_per_m3": round(specific_energy, 4),
        "telemetry_physics_residual_rmse_m": round(residual_rmse, 3),
        "max_telemetry_residual_m": round(max_residual_m, 2),
        "active_sensor_residual_rmse_m": round(active_sensor_rmse, 2),
    }


def compute_triton_evidence_vector(
    base_metrics: Dict[str, Any],
    ai_eval: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Constructs the structured TRITON Framework Evidence Scorecard,
    mapping calculated metrics into Cybersecurity (CI), Sustainability (SO),
    and Artificial Intelligence (IA) domains.
    """
    records = []

    # 1. Cybersecurity Controls (CI)
    # Evaluates integrity using the targeted/maximum sensor error to avoid dilution
    max_res = base_metrics.get("max_telemetry_residual_m", base_metrics["telemetry_physics_residual_rmse_m"])
    active_rmse = base_metrics.get("active_sensor_residual_rmse_m", max_res)
    effective_cyber_error = max(active_rmse, max_res)
    ci01_score = max(0.0, 100.0 - (effective_cyber_error * 4.0))
    status_ci01 = "Optimal" if effective_cyber_error < 0.5 else ("Warning" if effective_cyber_error < 2.0 else "Compromised")
    records.append({
        "Axis": "Cybersecurity",
        "Code": "CI-01",
        "Domain Indicator": "Data Protection & Integrity",
        "Value": f"{ci01_score:.1f} / 100",
        "Status": status_ci01,
        "Description": f"Desviación sensorial máx: {effective_cyber_error:.2f} m (RMSE de red: {base_metrics['telemetry_physics_residual_rmse_m']:.2f} m)"
    })

    if ai_eval:
        cyber_att = ai_eval["cyber_recall"]
        records.append({
            "Axis": "Cybersecurity",
            "Code": "CI-02",
            "Domain Indicator": "Access Control & Spoofing Defense",
            "Value": f"{ai_eval['cyber_precision'] * 100:.1f}% Prec | {cyber_att * 100:.1f}% Rec",
            "Status": "Optimal" if cyber_att >= 0.9 else "Attentive",
            "Description": "FDI and sensor tampering discrimination capability"
        })

    records.append({
        "Axis": "Cybersecurity",
        "Code": "CI-10",
        "Domain Indicator": "Real-time Telemetry Monitoring",
        "Value": "Active",
        "Status": "Optimal",
        "Description": "SCADA/IoT monitoring loop continuously observing pressure field"
    })

    # 2. Sustainability Indicators (SO)
    leak_vol = base_metrics["leak_volume_m3"]
    loss_pct = base_metrics["water_loss_pct"]
    records.append({
        "Axis": "Sustainability",
        "Code": "SO-01",
        "Domain Indicator": "Efficient Water Use (Water Losses)",
        "Value": f"{leak_vol:.1f} m³ ({loss_pct:.1f}%)",
        "Status": "Optimal" if leak_vol < 1.0 else "Warning",
        "Description": "Total volume lost through physical leaks and burst orifices"
    })

    energy_kwh = base_metrics["pump_energy_kwh"]
    specific_e = base_metrics["specific_energy_kwh_per_m3"]
    records.append({
        "Axis": "Sustainability",
        "Code": "SO-03",
        "Domain Indicator": "Energy Efficiency in Pumping",
        "Value": f"{energy_kwh:.1f} kWh ({specific_e:.4f} kWh/m³)",
        "Status": "Optimal",
        "Description": "Total electricity consumption and energy intensity per m³"
    })

    serv_pct = base_metrics["service_availability_pct"]
    records.append({
        "Axis": "Sustainability",
        "Code": "SO-06",
        "Domain Indicator": "Supply Service Continuity (≥20m)",
        "Value": f"{serv_pct:.1f}%",
        "Status": "Optimal" if serv_pct >= 95.0 else ("Warning" if serv_pct >= 80.0 else "Critical"),
        "Description": "Percentage of network junction-hours meeting service pressure"
    })

    # 3. Artificial Intelligence Capabilities (IA)
    if ai_eval:
        f1 = ai_eval["f1"]
        rec = ai_eval["recall"]
        records.append({
            "Axis": "AI & Analytics",
            "Code": "IA-03",
            "Domain Indicator": "Anomaly Detection (Isolation Forest & Twins)",
            "Value": f"F1: {f1:.2f} (Recall: {rec:.2f})",
            "Status": "Optimal" if f1 >= 0.8 else ("Warning" if f1 >= 0.5 else "Suboptimal"),
            "Description": "Multivariate isolation & counterfactual twin anomaly detection"
        })

        records.append({
            "Axis": "AI & Analytics",
            "Code": "IA-05",
            "Domain Indicator": "Real-time Hydraulic Analytics",
            "Value": f"Residual Thresh: {ai_eval['physics_threshold_m']:.2f} m",
            "Status": "Active",
            "Description": "Dynamic residual tracking between cyber observations and physical twin"
        })

    return pd.DataFrame(records)
