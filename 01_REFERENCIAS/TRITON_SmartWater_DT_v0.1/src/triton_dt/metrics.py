from __future__ import annotations
import numpy as np


def calculate_metrics(result, required_pressure_m=20.0, timestep_hours=1.0):
    p = result["pressure"]
    d = result["demand"]
    leak = result["leak"]
    dt = timestep_hours * 3600.0

    physical = p["pressure_m"].astype(float)
    observed = p["observed_pressure_m"].astype(float)
    residual = observed - physical
    service_pct = float((physical >= required_pressure_m).mean() * 100.0)
    low_node_hours = float((physical < required_pressure_m).sum() * timestep_hours)
    delivered_m3 = float(d["delivered_m3s"].clip(lower=0).sum() * dt)
    requested_m3 = float(d["requested_m3s"].clip(lower=0).sum() * dt)
    leak_m3 = float(leak["leak_m3s"].clip(lower=0).sum() * dt)
    demand_service_pct = 100.0 * delivered_m3 / max(requested_m3, 1e-9)

    return {
        "mean_pressure_m": float(physical.mean()),
        "minimum_pressure_m": float(physical.min()),
        "service_availability_pct": service_pct,
        "demand_service_pct": min(demand_service_pct, 100.0),
        "low_pressure_node_hours": low_node_hours,
        "delivered_water_m3": delivered_m3,
        "requested_water_m3": requested_m3,
        "leak_volume_m3": leak_m3,
        "pump_energy_kwh": float(result.get("pump_energy_kwh", 0.0)),
        "telemetry_physics_residual_rmse_m": float(np.sqrt(np.mean(residual ** 2))),
    }


def attach_ai(metrics, ai_eval):
    out = dict(metrics)
    out.update({
        "anomaly_precision": ai_eval["precision"],
        "anomaly_recall": ai_eval["recall"],
        "anomaly_f1": ai_eval["f1"],
        "false_positive_rate": ai_eval["false_positive_rate"],
        "anomaly_detection_rate": ai_eval["recall"],
        "physics_consistency_rmse_m": metrics["telemetry_physics_residual_rmse_m"],
        "counterfactual_residual_rmse_m": float(np.sqrt(np.mean(ai_eval["timeline"]["counterfactual_residual_m"] ** 2))),
        "labelled_event_samples": int(ai_eval["timeline"]["truth"].sum()),
    })
    return out
