"""
TRITON Digital Twin - WNTR Simulation Engine
Module: src.engine.wntr_runner

Provides hydraulic network management, EPANET (.inp) file loading,
programmatic network creation, and simulation execution using WNTR.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional, Union
import wntr


def load_network(source: Union[str, Path]) -> wntr.network.WaterNetworkModel:
    """
    Load a water network model from a file path or a WNTR library name.

    Args:
        source: File path to an EPANET .inp file, or model name (e.g., 'Net3').

    Returns:
        wntr.network.WaterNetworkModel instance.
    """
    source_path = Path(source)
    if source_path.is_file():
        return wntr.network.WaterNetworkModel(str(source_path))

    # Check relative to default data directory
    default_dir = Path(__file__).resolve().parents[2] / "data" / "networks"
    candidate = default_dir / source_path.name
    if candidate.is_file():
        return wntr.network.WaterNetworkModel(str(candidate))
    
    if not candidate.suffix and (default_dir / f"{source_path.name}.inp").is_file():
        return wntr.network.WaterNetworkModel(str(default_dir / f"{source_path.name}.inp"))

    # Fallback to WNTR library
    try:
        return wntr.network.WaterNetworkModel(str(source))
    except Exception:
        try:
            from wntr.library import ModelLibrary
            return wntr.network.WaterNetworkModel(ModelLibrary().get_filepath(str(source)))
        except Exception as e:
            raise FileNotFoundError(
                f"Could not load network from '{source}' or WNTR library: {e}"
            )


def create_simple_network(
    output_path: Optional[Union[str, Path]] = None,
    duration_hours: int = 168
) -> wntr.network.WaterNetworkModel:
    """
    Programmatically creates a simple, hydraulically valid water network:
    1 Reservoir (R1), 1 Pump (PUMP1), 3 Junctions (J1, J2, J3), and 2 Pipes (PIPE1, PIPE2).

    Args:
        output_path: Optional path to save the generated model as .inp.
        duration_hours: Simulation duration in hours (default 168h = 7 days).

    Returns:
        wntr.network.WaterNetworkModel instance.
    """
    wn = wntr.network.WaterNetworkModel()

    # 1. Demand pattern (24-hour diurnal cycle)
    pattern_multipliers = [
        0.6, 0.5, 0.4, 0.5, 0.7, 1.1, 1.4, 1.5,
        1.3, 1.1, 1.0, 1.0, 1.1, 1.0, 0.9, 1.0,
        1.2, 1.4, 1.5, 1.3, 1.1, 0.9, 0.8, 0.7
    ]
    wn.add_pattern("diurnal", pattern_multipliers)

    # 2. Nodes: 1 Reservoir and 3 Junctions
    wn.add_reservoir("R1", base_head=50.0, coordinates=(0.0, 100.0))
    wn.add_junction(
        "J1",
        elevation=12.0,
        base_demand=0.006,  # ~21.6 m3/h
        demand_pattern="diurnal",
        coordinates=(150.0, 100.0)
    )
    wn.add_junction(
        "J2",
        elevation=15.0,
        base_demand=0.010,  # ~36 m3/h
        demand_pattern="diurnal",
        coordinates=(300.0, 100.0)
    )
    wn.add_junction(
        "J3",
        elevation=18.0,
        base_demand=0.008,  # ~28.8 m3/h
        demand_pattern="diurnal",
        coordinates=(450.0, 100.0)
    )

    # 3. Pump curve & Pump (connects Reservoir R1 to Junction J1)
    # Head-capacity curve: Head decreases with flow
    wn.add_curve("pump_curve_1", "HEAD", [(0.0, 65.0), (0.03, 55.0), (0.06, 35.0)])
    wn.add_pump(
        "PUMP1",
        start_node_name="R1",
        end_node_name="J1",
        pump_type="HEAD",
        pump_parameter="pump_curve_1"
    )

    # 4. Pipes
    # PIPE1: J1 -> J2 (Length: 500m, Diam: 250mm, Hazen-Williams C=110)
    wn.add_pipe(
        "PIPE1",
        start_node_name="J1",
        end_node_name="J2",
        length=500.0,
        diameter=0.25,
        roughness=110.0
    )
    # PIPE2: J2 -> J3 (Length: 450m, Diam: 200mm, Hazen-Williams C=110)
    wn.add_pipe(
        "PIPE2",
        start_node_name="J2",
        end_node_name="J3",
        length=450.0,
        diameter=0.20,
        roughness=110.0
    )

    # 5. Simulation options
    wn.options.time.duration = duration_hours * 3600
    wn.options.time.hydraulic_timestep = 3600
    wn.options.time.report_timestep = 3600
    wn.options.hydraulic.demand_model = "PDD"
    wn.options.hydraulic.required_pressure = 20.0
    wn.options.hydraulic.minimum_pressure = 0.0

    if output_path is not None:
        save_network(wn, output_path)

    return wn


def save_network(wn: wntr.network.WaterNetworkModel, output_path: Union[str, Path]) -> Path:
    """
    Save water network model to an EPANET .inp file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wntr.network.write_inpfile(wn, str(path))
    return path


def get_network_summary(wn: wntr.network.WaterNetworkModel) -> Dict[str, Any]:
    """
    Extract useful summary metadata and lists of components for UI dropdowns.
    """
    junctions = [name for name, _ in wn.junctions()]
    reservoirs = [name for name, _ in wn.reservoirs()]
    tanks = [name for name, _ in wn.tanks()]
    pipes = [name for name, _ in wn.pipes()]
    pumps = [name for name, _ in wn.pumps()]
    valves = [name for name, _ in wn.valves()]

    node_coords = {}
    for name, node in wn.nodes():
        node_coords[name] = (node.coordinates[0], node.coordinates[1])

    return {
        "num_nodes": wn.num_nodes,
        "num_junctions": len(junctions),
        "num_reservoirs": len(reservoirs),
        "num_tanks": len(tanks),
        "num_links": wn.num_links,
        "num_pipes": len(pipes),
        "num_pumps": len(pumps),
        "num_valves": len(valves),
        "junction_names": junctions,
        "reservoir_names": reservoirs,
        "tank_names": tanks,
        "pipe_names": pipes,
        "pump_names": pumps,
        "valve_names": valves,
        "node_coordinates": node_coords,
        "duration_hours": int(wn.options.time.duration / 3600),
        "timestep_hours": int(wn.options.time.hydraulic_timestep / 3600) or 1,
    }


def run_hydraulic_simulation(
    wn: wntr.network.WaterNetworkModel,
    demand_model: str = "PDD",
    required_pressure_m: float = 20.0,
    minimum_pressure_m: float = 0.0,
    pump_efficiency: float = 0.75,
    force_wntr_simulator: bool = False
) -> Dict[str, Any]:
    """
    Execute hydraulic simulation using WNTR or EPANET engine.

    Args:
        wn: WaterNetworkModel instance.
        demand_model: 'PDD' (Pressure Dependent Demand) or 'DD' (Demand Driven).
        required_pressure_m: Minimum pressure required to deliver full nominal demand.
        minimum_pressure_m: Pressure below which delivered demand is zero.
        pump_efficiency: Pump efficiency ratio (0.05 to 1.0).
        force_wntr_simulator: True to force WNTRSimulator (required for leaks/PDD).

    Returns:
        Dictionary containing pressures, demands, leaks, link flows, and energy consumption.
    """
    wn.options.hydraulic.demand_model = demand_model
    wn.options.hydraulic.required_pressure = required_pressure_m
    wn.options.hydraulic.minimum_pressure = minimum_pressure_m

    # Check whether model contains leaks or requires PDD
    has_leaks = any(bool(node.leak) for _, node in wn.junctions())
    use_wntr_sim = force_wntr_simulator or has_leaks or (demand_model.upper() == "PDD")

    if use_wntr_sim:
        sim = wntr.sim.WNTRSimulator(wn)
        try:
            results = sim.run_sim()
        except Exception:
            # Fallback with relaxed tolerance if strict fails
            results = sim.run_sim(solver_options={"TOL": 1e-4, "MAXITER": 2000})
    else:
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim()

    # Extract node pressure
    p = results.node["pressure"].copy()
    hours = (p.index.to_numpy() / 3600.0).astype(int)

    expected_duration_h = int(wn.options.time.duration / 3600)
    actual_max_hour = int(hours.max()) if len(hours) > 0 else 0
    is_truncated = bool(actual_max_hour < max(0, expected_duration_h - 1))

    # Reshape pressure dataframe
    pressure_df = p.reset_index(names="seconds").melt(
        id_vars="seconds", var_name="node", value_name="pressure_m"
    )
    pressure_df["hour"] = (pressure_df["seconds"] / 3600).astype(int)
    # Default observed pressure matches physical pressure initially
    pressure_df["observed_pressure_m"] = pressure_df["pressure_m"]

    # Extract node demand
    d = results.node["demand"].copy()
    demand_df = d.reset_index(names="seconds").melt(
        id_vars="seconds", var_name="node", value_name="delivered_m3s"
    )
    demand_df["hour"] = (demand_df["seconds"] / 3600).astype(int)
    demand_df["requested_m3s"] = demand_df["delivered_m3s"]

    # Extract leak demand if present
    if "leak_demand" in results.node:
        ld = results.node["leak_demand"].copy()
        leak_df = ld.reset_index(names="seconds").melt(
            id_vars="seconds", var_name="node", value_name="leak_m3s"
        )
        leak_df["hour"] = (leak_df["seconds"] / 3600).astype(int)
    else:
        leak_df = demand_df[["seconds", "hour", "node"]].copy()
        leak_df["leak_m3s"] = 0.0

    # Extract link flowrate
    flow_df = None
    if "flowrate" in results.link:
        flow = results.link["flowrate"].copy()
        flow_df = flow.reset_index(names="seconds").melt(
            id_vars="seconds", var_name="link", value_name="flowrate_m3s"
        )
        flow_df["hour"] = (flow_df["seconds"] / 3600).astype(int)

    # Pump energy calculation: E (Joules) = sum(rho * g * Q * deltaH / efficiency * dt)
    rho, grav = 1000.0, 9.80665
    eff = max(float(pump_efficiency), 0.05)
    energy_joules = 0.0

    if "flowrate" in results.link and "head" in results.node:
        flow = results.link["flowrate"]
        head = results.node["head"]
        timestep_seconds = float(wn.options.time.hydraulic_timestep)
        for pump_name, pump in wn.pumps():
            if pump_name in flow.columns and pump.end_node_name in head.columns and pump.start_node_name in head.columns:
                q = flow[pump_name].abs()
                dh = (head[pump.end_node_name] - head[pump.start_node_name]).clip(lower=0)
                power_watts = (rho * grav * q * dh) / eff
                energy_joules += float((power_watts * timestep_seconds).sum())

    energy_kwh = energy_joules / 3.6e6

    return {
        "network": wn,
        "pressure": pressure_df,
        "demand": demand_df,
        "leak": leak_df,
        "flowrate": flow_df,
        "pump_energy_kwh": energy_kwh,
        "hours": hours,
        "simulator_used": "WNTRSimulator" if use_wntr_sim else "EpanetSimulator",
        "summary": get_network_summary(wn),
        "expected_duration_h": expected_duration_h,
        "actual_max_hour": actual_max_hour,
        "is_truncated": is_truncated,
    }
