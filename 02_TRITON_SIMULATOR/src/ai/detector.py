"""
TRITON Digital Twin - AI Anomaly Detection & Twin Comparator
Module: src.ai.detector

Implements:
1. Physical Twin vs Cyber Twin consistency comparator.
2. Isolation Forest multivariate anomaly detection.
3. Counterfactual baseline residual deviation.
4. Tri-state event classification: Normal, Physical Fault, Cyber Attack.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix


def extract_sensor_matrix(
    sim_result: Dict[str, Any],
    sensor_nodes: List[Union[str, int]],
    value_column: str = "observed_pressure_m"
) -> pd.DataFrame:
    """
    Extracts a pivot table of pressure values indexed by hour across sensor nodes.
    """
    p_df = sim_result["pressure"]
    sensor_str_list = [str(s) for s in sensor_nodes]
    
    filtered = p_df[p_df["node"].astype(str).isin(sensor_str_list)]
    matrix = (
        filtered.pivot_table(
            index="hour",
            columns="node",
            values=value_column,
            aggfunc="mean"
        )
        .sort_index()
    )
    # Ensure all sensor columns are represented as strings
    matrix.columns = matrix.columns.astype(str)
    return matrix.interpolate(limit_direction="both").ffill().bfill()


def evaluate_triton_detector(
    baseline_result: Dict[str, Any],
    scenario_result: Dict[str, Any],
    sensor_nodes: Optional[List[Union[str, int]]] = None,
    contamination: float = 0.05,
    random_state: int = 42,
    physics_threshold_override: Optional[float] = None,
    counterfactual_threshold_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Comprehensive TRITON detection and classification:
    - Learns normal multivariate patterns using Isolation Forest on baseline.
    - Evaluates Cyber Twin telemetry against Physical Twin state (FDI / Spoofing).
    - Evaluates Cyber Twin telemetry against Counterfactual baseline (Physical faults).
    - Classifies events into Normal, Physical Fault, or Cyber Attack.

    Args:
        baseline_result: Simulation output for baseline operation.
        scenario_result: Simulation output for current scenario.
        sensor_nodes: List of monitored node IDs (default: auto-select top 5 nodes).
        contamination: Isolation Forest expected outlier proportion.
        random_state: Seed for reproducibility.
        physics_threshold_override: Optional manual threshold for physical residual.
        counterfactual_threshold_override: Optional manual threshold for counterfactual residual.

    Returns:
        Dictionary containing model, timeline DataFrame, metrics, and thresholds.
    """
    # 1. Select sensor nodes if not specified
    if not sensor_nodes:
        # Default to junctions in network summary
        summary = scenario_result.get("summary", {})
        available_nodes = summary.get("junction_names", [])
        if len(available_nodes) <= 5:
            sensor_nodes = available_nodes
        else:
            # Pick 5 evenly spaced junctions
            step = max(1, len(available_nodes) // 5)
            sensor_nodes = available_nodes[::step][:5]

    sensor_str_list = [str(s) for s in sensor_nodes]

    # 2. Extract matrices for baseline and scenario
    xb_obs = extract_sensor_matrix(baseline_result, sensor_str_list, "observed_pressure_m")
    xs_obs = extract_sensor_matrix(scenario_result, sensor_str_list, "observed_pressure_m")
    xb_phys = extract_sensor_matrix(baseline_result, sensor_str_list, "pressure_m")
    xs_phys = extract_sensor_matrix(scenario_result, sensor_str_list, "pressure_m")

    common_cols = [c for c in xb_obs.columns if c in xs_obs.columns and c in xs_phys.columns]
    if not common_cols:
        raise ValueError("No common sensor columns found between baseline and scenario results.")

    xb_obs = xb_obs[common_cols]
    xs_obs = xs_obs[common_cols]
    xb_phys = xb_phys[common_cols]
    xs_phys = xs_phys[common_cols]

    # Align baseline hours to scenario hours
    xb_obs_aligned = xb_obs.reindex(xs_obs.index).interpolate(limit_direction="both").ffill().bfill()
    xb_phys_aligned = xb_phys.reindex(xs_phys.index).interpolate(limit_direction="both").ffill().bfill()

    # 3. Model: Isolation Forest
    iso_model = IsolationForest(
        contamination=max(0.01, min(contamination, 0.5)),
        random_state=random_state
    )
    iso_model.fit(xb_obs.values)
    iso_pred = (iso_model.predict(xs_obs.values) == -1).astype(int)
    anomaly_scores = -iso_model.decision_function(xs_obs.values)

    # 4. Residual 1: Telemetry-Physics Residual (Cyber Twin vs Physical Twin)
    # Measures deviation between what sensors report and what the hydraulic physics dictate.
    scenario_physics_resid = (xs_obs - xs_phys).abs().max(axis=1).to_numpy()
    baseline_physics_resid = (xb_obs - xb_phys).abs().max(axis=1).to_numpy()

    if physics_threshold_override is not None:
        physics_thresh = float(physics_threshold_override)
    else:
        # Dynamic threshold based on baseline residual plus safety margin
        q99 = float(np.quantile(baseline_physics_resid, 0.99)) if len(baseline_physics_resid) > 0 else 0.0
        std = float(np.std(baseline_physics_resid)) if len(baseline_physics_resid) > 0 else 0.0
        physics_thresh = max(1.0, q99 + 3.0 * std)

    physics_inconsistency_pred = (scenario_physics_resid > physics_thresh).astype(int)

    # 5. Residual 2: Physical Dynamic Residual (Physical Twin vs Historical Baseline)
    # Measures physical deviation between the hydraulic state and normal historical operation.
    physical_dyn_resid = (xs_phys - xb_phys_aligned).abs().max(axis=1).to_numpy()
    counterfactual_resid = (xs_obs - xb_obs_aligned).abs().max(axis=1).to_numpy()

    if counterfactual_threshold_override is not None:
        cf_thresh = float(counterfactual_threshold_override)
    else:
        # Dynamic adaptive threshold: calibrated to detect physical anomalies
        # (leaks in looped/meshed transmission networks induce ~0.10 - 0.25 m head loss)
        base_std = float(np.std(baseline_physics_resid)) if len(baseline_physics_resid) > 0 else 0.02
        cf_thresh = max(0.08, min(0.35, 2.5 * base_std))

    cf_deviation_pred = (physical_dyn_resid > cf_thresh).astype(int)

    # 6. Hybrid TRITON Classification
    # - If physics inconsistency detected AND physical fault detected: HYBRID ATTACK
    # - If physics inconsistency detected: CYBER ATTACK (tampering / spoofing)
    # - If physical deviation detected or Isolation Forest flags anomalous pattern: PHYSICAL FAULT (leak / outage / closure)
    # - Else: NORMAL OPERATION
    classification_labels = []
    pred_anomaly = np.zeros(len(xs_obs), dtype=int)
    pred_physical = np.zeros(len(xs_obs), dtype=int)
    pred_cyber = np.zeros(len(xs_obs), dtype=int)

    for i in range(len(xs_obs)):
        is_p_incons = (physics_inconsistency_pred[i] == 1)
        is_phys_fault = (cf_deviation_pred[i] == 1) or (iso_pred[i] == 1 and physical_dyn_resid[i] > 0.04)

        if is_p_incons and is_phys_fault:
            classification_labels.append("Hybrid Attack (Physical + Cyber)")
            pred_anomaly[i] = 1
            pred_cyber[i] = 1
            pred_physical[i] = 1
        elif is_p_incons:
            classification_labels.append("Cyber Attack (FDI/Spoofing)")
            pred_anomaly[i] = 1
            pred_cyber[i] = 1
        elif is_phys_fault:
            classification_labels.append("Physical Fault (Leak/Outage/Closure)")
            pred_anomaly[i] = 1
            pred_physical[i] = 1
        else:
            classification_labels.append("Normal Operation")

    # 7. Ground Truth & Performance Metrics
    events_df = scenario_result.get("events")
    if events_df is not None and "is_event_active" in events_df:
        truth_map = events_df.set_index("hour")
        truth_active = np.array([int(truth_map["is_event_active"].get(int(h), 0)) for h in xs_obs.index])
        truth_physical = np.array([int(truth_map["is_physical_fault"].get(int(h), 0)) for h in xs_obs.index])
        truth_cyber = np.array([int(truth_map["is_cyber_attack"].get(int(h), 0)) for h in xs_obs.index])
    else:
        truth_active = np.zeros(len(xs_obs), dtype=int)
        truth_physical = np.zeros(len(xs_obs), dtype=int)
        truth_cyber = np.zeros(len(xs_obs), dtype=int)

    # Calculate standard ML metrics for anomaly detection
    if truth_active.sum() == 0:
        # Baseline / Nominal operation: perfect classification if 0 false alarms
        if pred_anomaly.sum() == 0:
            precision, recall, f1 = 1.0, 1.0, 1.0
        else:
            precision, recall, f1 = 0.0, 1.0, 0.0
    else:
        precision, recall, f1, _ = precision_recall_fscore_support(
            truth_active, pred_anomaly, average="binary", zero_division=0
        )

    # Calculate confusion matrix components
    tn, fp, fn, tp = confusion_matrix(truth_active, pred_anomaly, labels=[0, 1]).ravel()
    fpr = float(fp / max(fp + tn, 1))

    # Calculate Cyber Attack identification precision & recall
    if truth_cyber.sum() == 0:
        if pred_cyber.sum() == 0:
            cyber_prec, cyber_rec, cyber_f1 = 1.0, 1.0, 1.0
        else:
            cyber_prec, cyber_rec, cyber_f1 = 0.0, 1.0, 0.0
    else:
        cyber_prec, cyber_rec, cyber_f1, _ = precision_recall_fscore_support(
            truth_cyber, pred_cyber, average="binary", zero_division=0
        )

    # 8. Detailed Hourly Timeline DataFrame
    timeline_df = pd.DataFrame({
        "hour": xs_obs.index.astype(int),
        "truth_active": truth_active,
        "truth_physical": truth_physical,
        "truth_cyber": truth_cyber,
        "predicted_anomaly": pred_anomaly,
        "classification": classification_labels,
        "isolation_forest_flag": iso_pred,
        "anomaly_score": anomaly_scores,
        "physics_inconsistency_flag": physics_inconsistency_pred,
        "physics_residual_m": scenario_physics_resid,
        "counterfactual_flag": cf_deviation_pred,
        "counterfactual_residual_m": physical_dyn_resid,
        "observed_residual_m": counterfactual_resid,
    })

    return {
        "model": iso_model,
        "timeline": timeline_df,
        "sensor_nodes": sensor_str_list,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_positive_rate": fpr,
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
        "cyber_precision": float(cyber_prec),
        "cyber_recall": float(cyber_rec),
        "cyber_f1": float(cyber_f1),
        "physics_threshold_m": physics_thresh,
        "counterfactual_threshold_m": cf_thresh,
    }
