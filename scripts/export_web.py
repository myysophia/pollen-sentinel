"""
Export web/data.json for the static national dashboard (GitHub Pages).

Reads every city snapshot under data/raw/<today>/, attaches the L1 outlook,
and writes one compact JSON consumed by web/index.html.
"""
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from collectors import pollen_cma as pc
from collectors.collect import _find_snapshot_files, _load_json_lenient
from predictor.rules import predict_series


def main():
    today = date.today().isoformat()
    with open(os.path.join(ROOT, "config", "cities.json"), encoding="utf-8") as f:
        cities = json.load(f)["cities"]
    raw_dir = os.path.join(ROOT, "data", "raw", today)
    # Same discovery/lenient-read as the assembler: per-shard snapshots may sit
    # one level deeper and a stale root-level file must not be preferred.
    snaps = _find_snapshot_files(raw_dir)
    if not snaps:
        snaps = _find_snapshot_files(os.path.join(ROOT, "data", "raw"))
    out_cities = []
    for c in cities:
        p = snaps.get(c["en"])
        if not p:
            continue
        raw = _load_json_lenient(p)
        hist = raw["pollen"]
        latest = pc.latest_observed(hist)
        try:
            preds = predict_series(hist, raw.get("weather_forecast", []), date.today())
        except Exception:
            preds = []
        out_cities.append({
            "en": c["en"], "name": c["name"], "prov": c["prov"],
            "lat": c["lat"], "lon": c["lon"],
            "latest_date": latest["date"] if latest else None,
            "latest_code": latest["level_code"] if latest else -1,
            "latest_level": latest["level"] if latest else "待发布",
            "outlook": [{
                "date": x["date"], "level": x["level"], "direction": x["direction"],
                "source": x["source"], "weather": x["weather"]["weather"],
                "tmin": x["weather"]["tmin"], "tmax": x["weather"]["tmax"],
                "prcp": x["weather"]["prcp_mm"],
            } for x in preds],
        })
    out_cities.sort(key=lambda x: (x["latest_code"] if x["latest_code"] >= 0 else -1),
                    reverse=True)
    payload = {"today": today, "cities": out_cities}
    os.makedirs(os.path.join(ROOT, "web", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "web", "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print("web/data.json written, cities=%d" % len(out_cities))


if __name__ == "__main__":
    main()
