from __future__ import annotations
from .lite_network import simulate_lite
from .wntr_backend import wntr_available, simulate_wntr


def run_simulation(backend="auto", **kwargs):
    if backend == "auto":
        backend = "wntr" if wntr_available() else "lite"
    if backend == "wntr":
        if not wntr_available():
            raise RuntimeError("WNTR no está instalado. Use --backend lite o pip install -r requirements.txt")
        return simulate_wntr(**kwargs)
    if backend == "lite":
        return simulate_lite(**kwargs)
    raise ValueError(f"Backend desconocido: {backend}")
