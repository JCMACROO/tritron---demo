"""Optional reproducibility helper: download official WNTR Net3.inp into data/networks."""
from pathlib import Path
import requests
URL = "https://raw.githubusercontent.com/USEPA/WNTR/main/examples/networks/Net3.inp"
out = Path(__file__).resolve().parent / "data/networks/Net3.inp"
r = requests.get(URL, timeout=30)
r.raise_for_status()
out.write_bytes(r.content)
print(out)
