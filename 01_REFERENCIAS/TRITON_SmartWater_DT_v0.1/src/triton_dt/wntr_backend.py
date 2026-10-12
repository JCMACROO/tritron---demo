"""WNTR/EPANET backend for the full public Net3 model."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd


def wntr_available():
    try:
        import wntr  # noqa
        return True
    except Exception:
        return False


def load_net3_or_inp(inp_path=None):
    import wntr
    if inp_path:
        return wntr.network.WaterNetworkModel(str(inp_path))
    # Current WNTR supports the model-library name directly.
    try:
        return wntr.network.WaterNetworkModel("Net3")
    except Exception:
        from wntr.library import ModelLibrary
        return wntr.network.WaterNetworkModel(ModelLibrary().get_filepath("Net3"))


def simulate_wntr(scenario="baseline", inp_path=None, duration_hours=168,
                  event_start_hour=72, event_end_hour=120,
                  leak_node="113", leak_diameter_mm=14.0,
                  spoof_node="111", spoof_bias_m=15.0,
                  close_pipe="114", required_pressure_m=20.0,
                  pump_efficiency=0.75):
    import wntr
    wn = load_net3_or_inp(inp_path)
    wn.options.time.duration = duration_hours * 3600
    wn.options.time.hydraulic_timestep = 3600
    wn.options.time.report_timestep = 3600
    wn.options.hydraulic.demand_model = "PDD"
    wn.options.hydraulic.required_pressure = required_pressure_m
    wn.options.hydraulic.minimum_pressure = 0.0

    if scenario == "leak":
        node = wn.get_node(str(leak_node))
        area = math.pi * (leak_diameter_mm / 1000.0 / 2.0) ** 2
        node.add_leak(wn, area=area, discharge_coeff=0.75,
                      start_time=event_start_hour * 3600,
                      end_time=event_end_hour * 3600)

    if scenario == "pipe_closure":
        # Time-window link manipulation, representing a physical fault or malicious actuator command.
        from wntr.network import controls
        from wntr.network.base import LinkStatus
        link = wn.get_link(str(close_pipe))
        close_action = controls.ControlAction(link, "status", LinkStatus.Closed)
        open_action = controls.ControlAction(link, "status", LinkStatus.Open)
        c1 = controls.Control(controls.SimTimeCondition(wn, "=", f"{event_start_hour}:00:00"),
                              close_action, name="TRITON_close")
        c2 = controls.Control(controls.SimTimeCondition(wn, "=", f"{event_end_hour}:00:00"),
                              open_action, name="TRITON_reopen")
        wn.add_control("TRITON_close", c1)
        wn.add_control("TRITON_reopen", c2)

    # WNTRSimulator is needed to support leak demands directly.
    sim = wntr.sim.WNTRSimulator(wn) if scenario == "leak" else wntr.sim.EpanetSimulator(wn)
    res = sim.run_sim()
    p = res.node["pressure"].copy()
    d = res.node["demand"].copy()
    observed = p.copy()

    hours = (p.index.to_numpy() / 3600.0).astype(int)
    active_mask = (hours >= event_start_hour) & (hours < event_end_hour)
    if scenario == "sensor_spoof" and str(spoof_node) in observed.columns:
        observed.loc[active_mask, str(spoof_node)] += spoof_bias_m

    pressure_df = p.reset_index(names="seconds").melt(id_vars="seconds", var_name="node", value_name="pressure_m")
    pressure_df["hour"] = (pressure_df["seconds"] / 3600).astype(int)
    obs_df = observed.reset_index(names="seconds").melt(id_vars="seconds", var_name="node", value_name="observed_pressure_m")
    pressure_df = pressure_df.merge(obs_df[["seconds", "node", "observed_pressure_m"]], on=["seconds", "node"])

    demand_df = d.reset_index(names="seconds").melt(id_vars="seconds", var_name="node", value_name="delivered_m3s")
    demand_df["hour"] = (demand_df["seconds"] / 3600).astype(int)
    demand_df["requested_m3s"] = demand_df["delivered_m3s"]

    if "leak_demand" in res.node:
        ld = res.node["leak_demand"].copy()
        leak_df = ld.reset_index(names="seconds").melt(id_vars="seconds", var_name="node", value_name="leak_m3s")
        leak_df["hour"] = (leak_df["seconds"] / 3600).astype(int)
    else:
        leak_df = demand_df[["hour", "node"]].copy()
        leak_df["leak_m3s"] = 0.0

    events_df = pd.DataFrame({"hour": hours,
                              "event": ((hours >= event_start_hour) & (hours < event_end_hour) & (scenario != "baseline")).astype(int)})

    # Pump energy from hydraulic power = rho*g*Q*deltaH/efficiency.
    rho, grav = 1000.0, 9.80665
    flow = res.link["flowrate"]
    head = res.node["head"]
    energy_j = 0.0
    for pump_name, pump in wn.pumps():
        if pump_name not in flow.columns:
            continue
        q = flow[pump_name].abs()
        dh = (head[pump.end_node_name] - head[pump.start_node_name]).abs()
        power = rho * grav * q * dh / max(pump_efficiency, 0.05)
        energy_j += float((power * 3600.0).sum())

    return {
        "backend": "wntr",
        "network": wn,
        "pressure": pressure_df,
        "demand": demand_df,
        "leak": leak_df,
        "events": events_df,
        "pump_energy_kwh": energy_j / 3.6e6,
        "metadata": {"source_model": "EPANET Example Network 3 (Net3)",
                     "hydraulic_fidelity": "WNTR/EPANET"},
    }
