# Architecture — TRITON Smart Water DT v0.1

## Goal
A low-level cyber-physical digital-twin environment for water networks that can ingest an EPANET model, simulate normal/fault/attack scenarios, generate telemetry, quantify operational/sustainability effects, and expose evidence to TRITON.

## Layers
1. **Physical twin** — WNTR/EPANET when available; executable Lite proxy otherwise.
2. **Scenario engine** — baseline, leak, sensor spoofing/FDI, malicious or accidental pipe closure.
3. **Telemetry twin** — distinguishes physical state from observed sensor state.
4. **AI layer** — baseline-trained Isolation Forest demonstrates anomaly detection.
5. **Evidence layer** — raw cyber/sustainability/AI metrics; no invented TRITON semantics.
6. **UI** — Streamlit dashboard.

## Digital-twin state separation
Every future ESPOCH field should be tagged as one of:
- OBSERVED — measured/known from ESPOCH.
- CALIBRATED — inferred from measurements or engineering calibration.
- SIMULATED — hypothetical instrumentation, attack, fault, control or AI capability.

## v0.1 limitations
- Lite hydraulic solver is only a physically motivated proxy; use WNTR for hydraulic studies.
- Sensor spoofing is currently a telemetry-layer FDI scenario.
- Pipe closure models an actuator/network consequence, not packet-level OT traffic.
- Energy is hydraulic-power based; tariff/carbon factors are not yet modelled.
- TRITON control/indicator names are intentionally placeholders until the canonical mapping is supplied.

## Next milestones
- Import ESPOCH EPANET/GIS/CSV topology.
- Add tank/pump/valve state and richer actuator attacks.
- Add demand forecasting and leak-localisation models.
- Add network/PLC emulation (e.g. MiniCPS) as an optional cyber-range layer.
- Calibrate against BattLeDIM, BATADAL, SWaT and WADI.
- Add uncertainty/Monte Carlo and counterfactual optimisation.
