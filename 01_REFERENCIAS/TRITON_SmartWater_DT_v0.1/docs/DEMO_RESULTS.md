# Demo results — Lite backend

These values are executable prototype outputs, not ESPOCH estimates and not canonical TRITON scores.

| Scenario | Water loss (m³) | Service ≥20m (%) | Low-pressure node-hours | Pump energy (kWh) | AI recall | AI F1 | Telemetry/physics RMSE (m) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.0 | 100.0 | 0.0 | 3545 | 0.00 | 0.00 | 0.00 |
| leak | 775.0 | 100.0 | 0.0 | 3624 | 1.00 | 0.95 | 0.00 |
| sensor_spoof | 0.0 | 100.0 | 0.0 | 3545 | 1.00 | 0.95 | 2.53 |
| pipe_closure | 0.0 | 100.0 | 0.0 | 3545 | 0.04 | 0.07 | 0.00 |

## Interpretation

- `leak`: demonstrates water-loss and energy-impact evidence plus anomaly detection.
- `sensor_spoof`: physical state remains normal while observed telemetry is biased, creating a physics-integrity residual.
- `pipe_closure`: demonstrates a malicious/accidental actuator consequence that degrades service at part of the network.
- The hybrid detector combines Isolation Forest, telemetry/physics consistency and a counterfactual no-event twin residual.

The Lite solver is deliberately a proxy. WNTR/EPANET is the intended hydraulic backend for scientific experiments.