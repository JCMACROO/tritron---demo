from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support


def _matrix(result, sensor_nodes, value_col):
    df = result["pressure"]
    x = (df[df["node"].astype(str).isin([str(x) for x in sensor_nodes])]
         .pivot_table(index="hour", columns="node", values=value_col, aggfunc="mean")
         .sort_index())
    return x.interpolate(limit_direction="both").ffill().bfill()


def evaluate_anomaly_detector(baseline_result, scenario_result, sensor_nodes,
                              contamination=0.05, random_state=42):
    # Data-driven detector: learns normal multivariate pressure patterns.
    xb = _matrix(baseline_result, sensor_nodes, "observed_pressure_m")
    xs = _matrix(scenario_result, sensor_nodes, "observed_pressure_m")
    pb = _matrix(baseline_result, sensor_nodes, "pressure_m")
    ps = _matrix(scenario_result, sensor_nodes, "pressure_m")
    common = [c for c in xb.columns if c in xs.columns and c in pb.columns and c in ps.columns]
    xb, xs, pb, ps = xb[common], xs[common], pb[common], ps[common]

    model = IsolationForest(contamination=contamination, random_state=random_state)
    model.fit(xb.values)
    iso_pred = (model.predict(xs.values) == -1).astype(int)
    iso_score = -model.decision_function(xs.values)

    # Telemetry-integrity residual: observed sensor value vs the simulated physical state.
    # This is especially sensitive to FDI/spoofing.
    baseline_resid = (xb - pb).abs().max(axis=1).to_numpy()
    scenario_resid = (xs - ps).abs().max(axis=1).to_numpy()
    physics_threshold_m = max(1.0, float(np.quantile(baseline_resid, 0.995) + 3*np.std(baseline_resid)))
    physics_pred = (scenario_resid > physics_threshold_m).astype(int)

    # Counterfactual-twin residual: observed state vs expected no-event baseline for
    # the same hour. It can detect physical leaks/closures as well as cyber changes.
    xb_aligned = xb.reindex(xs.index).interpolate(limit_direction="both").ffill().bfill()
    counterfactual_resid = (xs - xb_aligned).abs().max(axis=1).to_numpy()
    counterfactual_threshold_m = 0.25  # low-noise synthetic v0.1; calibrate on ESPOCH
    counterfactual_pred = (counterfactual_resid > counterfactual_threshold_m).astype(int)

    # Hybrid detector: learned anomaly, telemetry/physics inconsistency, or
    # counterfactual deviation from expected normal operation.
    pred = np.maximum.reduce([iso_pred, physics_pred, counterfactual_pred])
    truth_map = scenario_result["events"].set_index("hour")["event"]
    truth = np.array([int(truth_map.get(int(h), 0)) for h in xs.index])
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth, pred, average="binary", zero_division=0
    )
    fp = int(((pred == 1) & (truth == 0)).sum())
    negatives = max(int((truth == 0).sum()), 1)

    out = pd.DataFrame({
        "hour": xs.index.astype(int), "truth": truth,
        "predicted_anomaly": pred, "isolation_forest": iso_pred,
        "physics_inconsistency": physics_pred,
        "counterfactual_deviation": counterfactual_pred,
        "physics_residual_m": scenario_resid,
        "counterfactual_residual_m": counterfactual_resid,
        "anomaly_score": iso_score,
    })
    return {
        "model": model, "timeline": out,
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "false_positive_rate": fp / negatives,
        "physics_threshold_m": physics_threshold_m,
        "counterfactual_threshold_m": counterfactual_threshold_m,
    }
