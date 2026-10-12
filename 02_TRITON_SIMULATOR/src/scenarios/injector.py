"""
TRITON Digital Twin - Scenario Injection Engine
Module: src.scenarios.injector

Implements physical fault injections (pipe leaks, pipe closures)
and cyber-physical sensor telemetry manipulations (FDI/spoofing).
"""

from __future__ import annotations
import copy
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pandas as pd
import wntr
from wntr.network import controls
from wntr.network.base import LinkStatus

from src.engine.wntr_runner import run_hydraulic_simulation


class ScenarioType:
    BASELINE = "baseline"
    LEAK = "leak"
    SENSOR_SPOOF = "sensor_spoof"
    PIPE_CLOSURE = "pipe_closure"
    PUMP_OUTAGE = "pump_outage"
    DEMAND_BURST = "demand_burst"
    STEALTH_ATTACK = "stealth_attack"

    @classmethod
    def all_types(cls) -> List[str]:
        return [
            cls.BASELINE,
            cls.LEAK,
            cls.SENSOR_SPOOF,
            cls.PIPE_CLOSURE,
            cls.PUMP_OUTAGE,
            cls.DEMAND_BURST,
            cls.STEALTH_ATTACK,
        ]


@dataclass
class ScenarioConfig:
    scenario_type: str = ScenarioType.BASELINE
    event_start_hour: int = 72
    event_end_hour: int = 120
    # Leak parameters
    leak_node: Optional[str] = None
    leak_diameter_mm: float = 14.0
    leak_discharge_coeff: float = 0.75
    # Cyber spoofing parameters
    spoof_node: Optional[str] = None
    spoof_bias_m: float = 15.0
    # Pipe closure parameters
    close_pipe: Optional[str] = None
    # Pump outage parameters
    outage_pump: Optional[str] = None
    # Demand burst parameters
    burst_node: Optional[str] = None
    burst_flow_m3s: float = 0.020  # ~72 m3/h
    # Simulation parameters
    duration_hours: int = 168
    hydraulic_timestep: int = 3600
    demand_model: str = "PDD"
    required_pressure_m: float = 20.0
    minimum_pressure_m: float = 0.0
    pump_efficiency: float = 0.75


def apply_physical_scenario(
    wn: wntr.network.WaterNetworkModel,
    config: ScenarioConfig
) -> wntr.network.WaterNetworkModel:
    """
    Applies physical modifications to a deep copy of the water network model:
    - Normal operation for BASELINE and SENSOR_SPOOF (physics unaltered).
    - Orifice leak addition for LEAK scenario.
    - Actuator closed/open controls for PIPE_CLOSURE scenario.

    Returns:
        Modified copy of wntr.network.WaterNetworkModel.
    """
    wn_mod = copy.deepcopy(wn)
    wn_mod.options.time.duration = config.duration_hours * 3600
    wn_mod.options.time.hydraulic_timestep = config.hydraulic_timestep
    wn_mod.options.time.report_timestep = config.hydraulic_timestep

    # Physical Fault: Pipe Leak or Stealth Cyber-Physical Attack
    if config.scenario_type in [ScenarioType.LEAK, ScenarioType.STEALTH_ATTACK]:
        if not config.leak_node:
            raise ValueError("leak_node must be specified for LEAK or STEALTH_ATTACK scenario")
        
        leak_node_str = str(config.leak_node)
        if leak_node_str not in wn_mod.node_name_list:
            raise KeyError(f"Node '{leak_node_str}' not found in network")
        
        node = wn_mod.get_node(leak_node_str)
        # Orifice area in m^2: A = pi * (D/2)^2
        area_m2 = math.pi * ((config.leak_diameter_mm / 1000.0) / 2.0) ** 2
        start_sec = config.event_start_hour * 3600
        end_sec = config.event_end_hour * 3600
        
        node.add_leak(
            wn_mod,
            area=area_m2,
            discharge_coeff=config.leak_discharge_coeff,
            start_time=start_sec,
            end_time=end_sec
        )

    # Physical Fault: Pipe Closure (Valve/Pipe shutdown)
    elif config.scenario_type == ScenarioType.PIPE_CLOSURE:
        if not config.close_pipe:
            raise ValueError("close_pipe must be specified for PIPE_CLOSURE scenario")
        
        pipe_str = str(config.close_pipe)
        if pipe_str not in wn_mod.link_name_list:
            raise KeyError(f"Link '{pipe_str}' not found in network")
        
        # Ensure existing controls are rules so higher priority outage rule takes precedence
        wn_mod.convert_controls_to_rules(priority=3)
        link = wn_mod.get_link(pipe_str)
        close_act = controls.ControlAction(link, "status", LinkStatus.Closed)
        open_act = controls.ControlAction(link, "status", LinkStatus.Open)

        # Timed rules for closure and reopening
        start_time_str = f"{config.event_start_hour}:00:00"
        end_time_str = f"{config.event_end_hour}:00:00"
        
        c1 = controls.SimTimeCondition(wn_mod, ">=", start_time_str)
        c2 = controls.SimTimeCondition(wn_mod, "<", end_time_str)
        and_c = controls.AndCondition(c1, c2)
        rule_close = controls.Rule(and_c, [close_act], priority=6)
        wn_mod.add_control("TRITON_pipe_close_rule", rule_close)

        c_open = controls.Control(
            controls.SimTimeCondition(wn_mod, "=", end_time_str),
            open_act,
            name="TRITON_pipe_reopen"
        )
        wn_mod.add_control("TRITON_pipe_reopen", c_open)

    # Physical Fault: Pump Outage (Emergency shutdown / Blackout)
    elif config.scenario_type == ScenarioType.PUMP_OUTAGE:
        if not config.outage_pump:
            raise ValueError("outage_pump must be specified for PUMP_OUTAGE scenario")
        
        pump_str = str(config.outage_pump)
        if pump_str not in wn_mod.link_name_list:
            raise KeyError(f"Pump '{pump_str}' not found in network")
            
        # Ensure existing controls are rules so higher priority outage rule takes precedence
        wn_mod.convert_controls_to_rules(priority=3)
        link = wn_mod.get_link(pump_str)
        close_act = controls.ControlAction(link, "status", LinkStatus.Closed)
        open_act = controls.ControlAction(link, "status", LinkStatus.Open)

        start_time_str = f"{config.event_start_hour}:00:00"
        end_time_str = f"{config.event_end_hour}:00:00"
        
        c1 = controls.SimTimeCondition(wn_mod, ">=", start_time_str)
        c2 = controls.SimTimeCondition(wn_mod, "<", end_time_str)
        and_c = controls.AndCondition(c1, c2)
        rule_close = controls.Rule(and_c, [close_act], priority=6)
        wn_mod.add_control("TRITON_pump_stop_rule", rule_close)

        c_open = controls.Control(
            controls.SimTimeCondition(wn_mod, "=", end_time_str),
            open_act,
            name="TRITON_pump_restart"
        )
        wn_mod.add_control("TRITON_pump_restart", c_open)

    # Physical Fault: Demand Burst / Illicit Consumption
    elif config.scenario_type == ScenarioType.DEMAND_BURST:
        if not config.burst_node:
            raise ValueError("burst_node must be specified for DEMAND_BURST scenario")
            
        burst_node_str = str(config.burst_node)
        if burst_node_str not in wn_mod.node_name_list:
            raise KeyError(f"Node '{burst_node_str}' not found in network")
            
        burst_mult = [0.0] * config.duration_hours
        for h in range(config.event_start_hour, min(config.event_end_hour, config.duration_hours)):
            burst_mult[h] = 1.0
            
        pat_name = "TRITON_burst_pattern"
        if pat_name in wn_mod.pattern_name_list:
            wn_mod.get_pattern(pat_name).multipliers = burst_mult
        else:
            wn_mod.add_pattern(pat_name, burst_mult)
            
        j_node = wn_mod.get_node(burst_node_str)
        j_node.add_demand(base=config.burst_flow_m3s, pattern_name=pat_name)

    return wn_mod


def apply_cyber_scenario(
    sim_results: Dict[str, Any],
    config: ScenarioConfig
) -> Dict[str, Any]:
    """
    Applies cyber modifications to sensor telemetry observations without
    altering physical ground truth. Generates timeline of events.

    Args:
        sim_results: Dictionary output from run_hydraulic_simulation.
        config: ScenarioConfig instance.

    Returns:
        Updated dictionary with separate physical and observed telemetry, plus event flags.
    """
    pressure_df = sim_results["pressure"].copy()
    hours = sim_results["hours"]

    # Cyber Attack: Sensor Spoofing / False Data Injection (FDI)
    if config.scenario_type == ScenarioType.SENSOR_SPOOF and config.spoof_node:
        spoof_node_str = str(config.spoof_node)
        mask = (
            (pressure_df["node"].astype(str) == spoof_node_str) &
            (pressure_df["hour"] >= config.event_start_hour) &
            (pressure_df["hour"] < config.event_end_hour)
        )
        pressure_df.loc[mask, "observed_pressure_m"] += config.spoof_bias_m

    # Stealth Attack: Fuga física real pero la telemetría en el nudo es enmascarada
    # (se suma presión a la lectura observada para engañar al SCADA de que no hay caída)
    elif config.scenario_type == ScenarioType.STEALTH_ATTACK:
        target_cyber = str(config.spoof_node or config.leak_node)
        mask = (
            (pressure_df["node"].astype(str) == target_cyber) &
            (pressure_df["hour"] >= config.event_start_hour) &
            (pressure_df["hour"] < config.event_end_hour)
        )
        bias = config.spoof_bias_m if config.spoof_bias_m != 0.0 else 12.0
        pressure_df.loc[mask, "observed_pressure_m"] += bias

    sim_results["pressure"] = pressure_df

    # Ground truth event vector across hours
    is_event = (
        (hours >= config.event_start_hour) &
        (hours < config.event_end_hour) &
        (config.scenario_type != ScenarioType.BASELINE)
    ).astype(int)

    is_physical = (
        is_event &
        (config.scenario_type in [
            ScenarioType.LEAK,
            ScenarioType.PIPE_CLOSURE,
            ScenarioType.PUMP_OUTAGE,
            ScenarioType.DEMAND_BURST,
            ScenarioType.STEALTH_ATTACK,
        ])
    ).astype(int)

    is_cyber = (
        is_event &
        (config.scenario_type in [ScenarioType.SENSOR_SPOOF, ScenarioType.STEALTH_ATTACK])
    ).astype(int)

    events_df = pd.DataFrame({
        "hour": hours,
        "is_event_active": is_event,
        "is_physical_fault": is_physical,
        "is_cyber_attack": is_cyber,
        "scenario_type": config.scenario_type,
    })

    sim_results["events"] = events_df
    sim_results["config"] = config
    return sim_results


def execute_scenario(
    wn: wntr.network.WaterNetworkModel,
    config: ScenarioConfig
) -> Dict[str, Any]:
    """
    Full pipeline to execute a scenario:
    1. Injects physical modifications into network copy.
    2. Runs hydraulic simulation.
    3. Injects cyber modifications to sensor telemetry.
    """
    # 1. Physical Layer
    wn_scenario = apply_physical_scenario(wn, config)

    # 2. Hydraulic Simulation Engine
    requires_pdd = config.scenario_type in [
        ScenarioType.LEAK,
        ScenarioType.PIPE_CLOSURE,
        ScenarioType.PUMP_OUTAGE,
        ScenarioType.DEMAND_BURST,
        ScenarioType.STEALTH_ATTACK,
    ]

    sim_results = run_hydraulic_simulation(
        wn=wn_scenario,
        demand_model=config.demand_model,
        required_pressure_m=config.required_pressure_m,
        minimum_pressure_m=config.minimum_pressure_m,
        pump_efficiency=config.pump_efficiency,
        force_wntr_simulator=requires_pdd
    )

    # 3. Cyber Layer (Sensor Telemetry)
    final_results = apply_cyber_scenario(sim_results, config)
    final_results["config"] = config

    return final_results
