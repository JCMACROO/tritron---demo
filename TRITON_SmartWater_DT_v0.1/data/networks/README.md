# Networks

The prototype defaults to `Net3` from the WNTR model library when WNTR is installed.
Run `python fetch_net3.py` to place the official public `Net3.inp` here for reproducible file-based loading.

For ESPOCH, place an EPANET-compatible `.inp` in this directory and run:

`python run_demo.py --backend wntr --inp data/networks/ESPOCH.inp --scenario leak`

The Lite backend uses a small Net3-derived connected demonstrator embedded in `lite_network.py`; it is explicitly not the full Net3 hydraulic model.
