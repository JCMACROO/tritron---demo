"""Low-dependency hydraulic proxy used as an executable fallback.

The topology is a small connected branch derived from public EPANET Net3 data.
It is NOT a replacement for an EPANET hydraulic solver. Its purpose is to let
TRITON scenario/evidence/AI code run before WNTR is installed.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import networkx as nx
import numpy as np
import pandas as pd

GPM_TO_M3S = 6.30901964e-5
FT_TO_M = 0.3048
IN_TO_M = 0.0254
G = 9.80665
RHO = 1000.0

NODE_DATA = {
    "Lake": {"elev_ft": 0.0, "demand_gpm": 0.0, "x": 5.5, "y": 29.0, "source": True},
    "10": {"elev_ft": 147.0, "demand_gpm": 0.0, "x": 9.00, "y": 27.85},
    "101": {"elev_ft": 42.0, "demand_gpm": 189.95, "x": 13.81, "y": 22.94},
    "103": {"elev_ft": 43.0, "demand_gpm": 133.20, "x": 12.96, "y": 21.31},
    "105": {"elev_ft": 28.5, "demand_gpm": 135.37, "x": 16.97, "y": 21.28},
    "107": {"elev_ft": 22.0, "demand_gpm": 54.64, "x": 18.45, "y": 20.46},
    "109": {"elev_ft": 20.3, "demand_gpm": 231.40, "x": 17.64, "y": 18.92},
    "111": {"elev_ft": 10.0, "demand_gpm": 141.94, "x": 20.21, "y": 17.53},
    "113": {"elev_ft": 2.0, "demand_gpm": 20.01, "x": 22.04, "y": 16.61},
    "115": {"elev_ft": 14.0, "demand_gpm": 52.10, "x": 20.98, "y": 19.18},
    "197": {"elev_ft": 23.0, "demand_gpm": 17.04, "x": 23.30, "y": 18.20},
}

# id, n1, n2, length_ft, diameter_in, Hazen-Williams C
PIPE_DATA = [
    ("PUMP10", "Lake", "10", 1.0, 48.0, 200.0),
    ("101", "10", "101", 14200, 18, 110),
    ("103", "101", "103", 1350, 16, 130),
    ("105", "101", "105", 2540, 12, 130),
    ("107", "105", "107", 1470, 12, 130),
    ("109", "103", "109", 3940, 16, 130),
    ("111", "109", "111", 2000, 12, 130),
    ("112", "115", "111", 1160, 12, 130),
    ("113", "111", "113", 1680, 12, 130),
    ("114", "115", "113", 2000, 8, 130),
    ("115", "107", "115", 1950, 8, 130),
    ("225", "111", "197", 2790, 12, 130),
]

@dataclass
class LiteNetwork:
    graph: nx.Graph
    source: str = "Lake"
    source_head_m: float = (167.0 + 92.0) * FT_TO_M  # lake head + pump-head proxy

    @classmethod
    def build(cls) -> "LiteNetwork":
        g = nx.Graph()
        for n, d in NODE_DATA.items():
            g.add_node(
                n,
                elevation_m=d["elev_ft"] * FT_TO_M,
                base_demand_m3s=d["demand_gpm"] * GPM_TO_M3S,
                x=d["x"], y=d["y"],
            )
        for pid, n1, n2, length_ft, diameter_in, c in PIPE_DATA:
            length_m = length_ft * FT_TO_M
            d_m = diameter_in * IN_TO_M
            # Resistance factor excluding Q^1.852 in Hazen-Williams.
            resistance = 10.67 * length_m / ((c ** 1.852) * (d_m ** 4.8704))
            if pid == "PUMP10":
                resistance = 1e-6
            g.add_edge(n1, n2, pipe_id=pid, length_m=length_m,
                       diameter_m=d_m, roughness_c=c, resistance=resistance)
        return cls(g)

    def topology(self):
        nodes = pd.DataFrame([
            {"node": n, **d} for n, d in self.graph.nodes(data=True)
        ])
        edges = pd.DataFrame([
            {"node1": u, "node2": v, **d} for u, v, d in self.graph.edges(data=True)
        ])
        return nodes, edges


def demand_multiplier(hour: int) -> float:
    h = hour % 24
    morning = 0.38 * math.exp(-((h - 8.0) / 2.8) ** 2)
    evening = 0.32 * math.exp(-((h - 19.0) / 3.0) ** 2)
    night = -0.18 * math.exp(-((h - 3.0) / 3.0) ** 2)
    return max(0.55, 0.82 + morning + evening + night)


def _edge_key(a, b):
    return tuple(sorted((a, b)))


def _solve_hour(net: LiteNetwork, hour: int, extra_demands=None, closed_pipe=None,
                required_pressure_m=20.0):
    extra_demands = extra_demands or {}
    g = net.graph.copy()
    if closed_pipe:
        for u, v, d in list(g.edges(data=True)):
            if d.get("pipe_id") == closed_pipe:
                g.remove_edge(u, v)
                break

    dm = demand_multiplier(hour)
    demand = {
        n: d["base_demand_m3s"] * dm + extra_demands.get(n, 0.0)
        for n, d in g.nodes(data=True) if n != net.source
    }
    paths = {}
    for n in demand:
        try:
            paths[n] = nx.shortest_path(g, net.source, n, weight="resistance")
        except nx.NetworkXNoPath:
            paths[n] = None

    edge_flow = {_edge_key(u, v): 0.0 for u, v in g.edges()}
    for n, path in paths.items():
        if not path:
            continue
        q = max(demand[n], 0.0)
        for a, b in zip(path[:-1], path[1:]):
            edge_flow[_edge_key(a, b)] += q

    pressure = {net.source: net.source_head_m}
    head = {net.source: net.source_head_m}
    for n, path in paths.items():
        if not path:
            head[n] = g.nodes[n]["elevation_m"]
            pressure[n] = 0.0
            continue
        h = net.source_head_m
        for a, b in zip(path[:-1], path[1:]):
            ed = g.get_edge_data(a, b)
            q = max(edge_flow[_edge_key(a, b)], 1e-9)
            h -= ed["resistance"] * (q ** 1.852)
        head[n] = h
        pressure[n] = max(0.0, h - g.nodes[n]["elevation_m"])

    delivered = {}
    for n, q in demand.items():
        p = pressure.get(n, 0.0)
        factor = 1.0 if p >= required_pressure_m else math.sqrt(max(p, 0.0) / required_pressure_m)
        delivered[n] = q * factor

    return pressure, demand, delivered, edge_flow


def simulate_lite(scenario: str = "baseline", duration_hours: int = 168,
                  event_start_hour: int = 72, event_end_hour: int = 120,
                  leak_node: str = "113", leak_diameter_mm: float = 14.0,
                  spoof_node: str = "111", spoof_bias_m: float = 15.0,
                  close_pipe: str = "114", required_pressure_m: float = 20.0,
                  pump_efficiency: float = 0.75):
    net = LiteNetwork.build()
    rows = []
    demand_rows = []
    leak_rows = []
    flow_rows = []
    event_rows = []

    # Baseline pressure estimate used by the leak orifice approximation.
    base_p, _, _, _ = _solve_hour(net, event_start_hour, required_pressure_m=required_pressure_m)
    leak_area = math.pi * (leak_diameter_mm / 1000.0 / 2.0) ** 2
    leak_q = 0.75 * leak_area * math.sqrt(2 * G * max(base_p.get(leak_node, 10.0), 0.1))

    for h in range(duration_hours + 1):
        active = event_start_hour <= h < event_end_hour
        extra = {leak_node: leak_q} if scenario == "leak" and active else {}
        closed = close_pipe if scenario == "pipe_closure" and active else None
        p, qreq, qdel, eflow = _solve_hour(net, h, extra_demands=extra,
                                            closed_pipe=closed,
                                            required_pressure_m=required_pressure_m)
        for n in net.graph.nodes:
            if n == net.source:
                continue
            observed = p.get(n, 0.0)
            if scenario == "sensor_spoof" and active and n == spoof_node:
                observed += spoof_bias_m
            rows.append({"hour": h, "node": n, "pressure_m": p.get(n, 0.0),
                         "observed_pressure_m": observed})
            demand_rows.append({"hour": h, "node": n,
                                "requested_m3s": qreq.get(n, 0.0),
                                "delivered_m3s": qdel.get(n, 0.0)})
            leak_rows.append({"hour": h, "node": n,
                              "leak_m3s": leak_q if (scenario == "leak" and active and n == leak_node) else 0.0})
        for (a, b), q in eflow.items():
            flow_rows.append({"hour": h, "edge": f"{a}-{b}", "flow_m3s": q})
        event_rows.append({"hour": h, "event": int(active and scenario != "baseline")})

    pressure_df = pd.DataFrame(rows)
    demand_df = pd.DataFrame(demand_rows)
    leak_df = pd.DataFrame(leak_rows)
    flow_df = pd.DataFrame(flow_rows)
    events_df = pd.DataFrame(event_rows)

    # Simple pump energy proxy based on total delivered demand and fixed pump head.
    total_q = demand_df.groupby("hour")["delivered_m3s"].sum()
    pump_head_m = 92.0 * FT_TO_M
    dt = 3600.0
    energy_kwh = float((RHO * G * total_q * pump_head_m / pump_efficiency * dt).sum() / 3.6e6)

    return {
        "backend": "lite",
        "network": net,
        "pressure": pressure_df,
        "demand": demand_df,
        "leak": leak_df,
        "flow": flow_df,
        "events": events_df,
        "pump_energy_kwh": energy_kwh,
        "metadata": {"source_model": "EPANET Net3-derived reduced demonstrator",
                     "hydraulic_fidelity": "proxy / non-EPANET"},
    }
