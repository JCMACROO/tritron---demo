# TRITON Smart Water Digital Twin — Prototype v0.1

First executable research prototype for a reusable Smart Water cyber-physical digital twin supporting **cybersecurity, sustainability and AI evidence**, with ESPOCH intended as the first real case study.

## What is already implemented

- Public benchmark network: **EPANET Example Network 3 (Net3)** through the WNTR model library.
- Two simulation backends:
  - `wntr`: full WNTR/EPANET-compatible simulation.
  - `lite`: executable low-dependency hydraulic proxy using a reduced Net3-derived branch.
- Scenarios: `baseline`, `leak`, `sensor_spoof`, `pipe_closure`.
- Separation between **physical state** and **observed telemetry**.
- Sustainability evidence: water loss, service pressure, delivered water, low-pressure node-hours, pump-energy estimate.
- Cyber evidence: telemetry/physics residual and event impact.
- AI demonstration: Isolation Forest trained on baseline pressures, with precision/recall/F1 and false-positive rate.
- Streamlit dashboard.
- Placeholder evidence adapter for TRITON `CI01..CI10`, `SO01..SO08`, `AI01..AI08` without inventing canonical meanings.

## Quick start (Windows / PowerShell)

```powershell
cd TRITON_SmartWater_DT_v0.1
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python run_demo.py --backend wntr --scenario leak
streamlit run app.py
```

If you want to test immediately without WNTR/Streamlit:

```powershell
python run_demo.py --backend lite --scenario sensor_spoof
```

## Scenarios

```powershell
python run_demo.py --backend lite --scenario baseline
python run_demo.py --backend lite --scenario leak
python run_demo.py --backend lite --scenario sensor_spoof
python run_demo.py --backend lite --scenario pipe_closure
```

Results are written to `output/` as CSV and JSON.

## Load ESPOCH later

Once ESPOCH has an EPANET-compatible representation:

```powershell
python run_demo.py --backend wntr --inp data/networks/ESPOCH.inp --scenario leak
```

No change to the scenario, AI or evidence layers should be required.

## Provenance

The default full network is the EPA/WNTR **EPANET Example Network 3 (Net3)**. WNTR is released under the Revised BSD license and is designed to simulate and analyse water distribution networks under disruptive scenarios. The optional `fetch_net3.py` retrieves the official Net3 file from the USEPA/WNTR GitHub repository.

## Research status

This is a **v0.1 experimental prototype**, not an operational control system. Its scores/evidence must not be interpreted as certified cybersecurity or sustainability assessments. The purpose is to provide a reproducible experimental layer beneath TRITON.
