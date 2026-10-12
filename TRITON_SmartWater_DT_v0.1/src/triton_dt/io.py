from pathlib import Path
import json


def save_run(output_dir, scenario, result, metrics, ai_eval=None):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result["pressure"].to_csv(out / f"{scenario}_pressure.csv", index=False)
    result["demand"].to_csv(out / f"{scenario}_demand.csv", index=False)
    result["leak"].to_csv(out / f"{scenario}_leak.csv", index=False)
    payload = {"scenario": scenario, "backend": result["backend"],
               "metadata": result.get("metadata", {}), "metrics": metrics}
    if ai_eval is not None:
        ai_eval["timeline"].to_csv(out / f"{scenario}_ai_timeline.csv", index=False)
    (out / f"{scenario}_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
