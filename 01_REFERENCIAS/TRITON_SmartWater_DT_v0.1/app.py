from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from triton_dt.core import run_simulation
from triton_dt.metrics import calculate_metrics, attach_ai
from triton_dt.ai import evaluate_anomaly_detector
from triton_dt.wntr_backend import wntr_available

st.set_page_config(page_title="TRITON Smart Water DT", layout="wide")
st.title("TRITON Smart Water Digital Twin — Prototype v0.1")
st.caption("Experimental research prototype: physical network + scenarios + cyber telemetry + sustainability + AI evidence")

cfg = yaml.safe_load((ROOT / "config/default.yaml").read_text(encoding="utf-8"))
simcfg = cfg["simulation"]

with st.sidebar:
    st.header("Simulation")
    backend = st.selectbox("Backend", ["wntr", "lite"] if wntr_available() else ["lite"], index=0)
    scenario = st.selectbox("Scenario", ["baseline", "leak", "sensor_spoof", "pipe_closure"], index=1)
    start = st.slider("Event start (h)", 1, 160, int(cfg["scenarios"]["event_start_hour"]))
    end = st.slider("Event end (h)", start + 1, 168, int(cfg["scenarios"]["event_end_hour"]))
    leak_mm = st.slider("Leak diameter (mm)", 2.0, 40.0, float(cfg["scenarios"]["leak_diameter_mm"]), 1.0)
    spoof_bias = st.slider("Sensor spoof bias (m)", -30.0, 30.0, float(cfg["scenarios"]["spoof_bias_m"]), 1.0)
    run = st.button("Run digital twin", type="primary")

if run or "result" not in st.session_state:
    kw = dict(duration_hours=168, event_start_hour=start, event_end_hour=end,
              leak_node=cfg["scenarios"]["leak_node"], leak_diameter_mm=leak_mm,
              spoof_node=cfg["scenarios"]["spoof_node"], spoof_bias_m=spoof_bias,
              close_pipe=cfg["scenarios"]["close_pipe"], required_pressure_m=simcfg["required_pressure_m"],
              pump_efficiency=simcfg["pump_efficiency"])
    baseline = run_simulation(backend=backend, scenario="baseline", **kw)
    result = run_simulation(backend=backend, scenario=scenario, **kw)
    ai_eval = evaluate_anomaly_detector(baseline, result, cfg["sensors"]["pressure_nodes"],
                                        contamination=cfg["ai"]["contamination"],
                                        random_state=cfg["ai"]["random_state"])
    metrics = attach_ai(calculate_metrics(result, simcfg["required_pressure_m"], 1.0), ai_eval)
    st.session_state.update(result=result, baseline=baseline, ai_eval=ai_eval, metrics=metrics, scenario=scenario)

result, ai_eval, metrics = st.session_state.result, st.session_state.ai_eval, st.session_state.metrics
st.info(f"Backend: **{result['backend']}** · Model: **{result['metadata']['source_model']}** · Fidelity: **{result['metadata']['hydraulic_fidelity']}**")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Service ≥20m", f"{metrics['service_availability_pct']:.1f}%")
c2.metric("Leak volume", f"{metrics['leak_volume_m3']:.1f} m³")
c3.metric("Energy proxy", f"{metrics['pump_energy_kwh']:.0f} kWh")
c4.metric("Physics residual", f"{metrics['telemetry_physics_residual_rmse_m']:.2f} m")
c5.metric("AI F1", f"{metrics['anomaly_f1']:.2f}")

st.subheader("Pressure telemetry")
p = result["pressure"]
sensors = [str(x) for x in cfg["sensors"]["pressure_nodes"]]
ps = p[p["node"].astype(str).isin(sensors)]
fig = px.line(ps, x="hour", y="observed_pressure_m", color="node", labels={"observed_pressure_m":"Observed pressure (m)"})
st.plotly_chart(fig, use_container_width=True)

st.subheader("Physical vs observed — target sensor")
target = cfg["scenarios"]["spoof_node"]
t = p[p["node"].astype(str) == str(target)]
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=t["hour"], y=t["pressure_m"], name="Physical twin"))
fig2.add_trace(go.Scatter(x=t["hour"], y=t["observed_pressure_m"], name="Telemetry"))
st.plotly_chart(fig2, use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("AI anomaly detection")
    st.dataframe(ai_eval["timeline"], use_container_width=True, height=300)
with right:
    st.subheader("TRITON evidence vector (v0.1)")
    show = pd.DataFrame({"metric": list(metrics.keys()), "value": list(metrics.values())})
    st.dataframe(show, use_container_width=True, height=300)

st.warning("The 0.1 indices are experimental evidence variables, not canonical TRITON scores. CI01–CI10, SO01–SO08 and AI01–AI08 remain adapters until the canonical TRITON semantics are loaded.")
