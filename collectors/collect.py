"""
Daily collection orchestrator.

Usage:
  python -m collectors.collect                       # all 53 cities, last 40 days
  python -m collectors.collect --cities xian,xianyang
  python -m collectors.collect --backfill            # full history since 2022-08-01

Outputs:
  data/raw/<YYYY-MM-DD>/<city_en>.json   immutable-ish daily raw snapshot
  data/daily/pollen.csv                  normalised pollen levels (upsert)
  data/daily/weather.csv                 latest weather forecast per day (upsert)
  data/latest_summary.json               collection summary for reports / web
"""
import argparse
import csv
import json
import os
import time
from datetime import date, datetime, timedelta

from . import pollen_cma as pc
from . import weather_om as wo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "cities.json")
HISTORY_START = "2022-08-01"  # Chinese pollen monitoring network begins Aug 2022


def load_cities():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)["cities"]


def upsert_csv(path, fieldnames, rows, key_fields):
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                existing[tuple(row[k] for k in key_fields)] = row
    for row in rows:
        existing[tuple(row[k] for k in key_fields)] = row
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ordered = sorted(existing.values(), key=lambda r: tuple(r[k] for k in key_fields))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(ordered)
    return len(ordered)


def collect_city(city, start, end, fetch_weather=True):
    payload = pc.fetch_pollen(city["en"], start, end)
    records = pc.normalize(payload)
    wrows = wo.forecast(city["lat"], city["lon"], days=7) if fetch_weather else []
    return records, wrows


def run(city_names, days, do_backfill=False, sleep_s=1.0):
    cities = load_cities()
    if city_names:
        wanted = set(city_names)
        cities = [c for c in cities if c["en"] in wanted]
        missing = wanted - {c["en"] for c in cities}
        if missing:
            print("[warn] unknown cities:", ",".join(sorted(missing)))
    today = date.today()
    stamp = today.isoformat()
    raw_dir = os.path.join(ROOT, "data", "raw", stamp)
    os.makedirs(raw_dir, exist_ok=True)

    pollen_rows, weather_rows = [], []
    summary_cities = []

    for i, city in enumerate(cities):
        try:
            if do_backfill:
                # request year by year to keep payloads bounded
                recs = []
                y = 2022
                while y <= today.year:
                    s = max(HISTORY_START, "%04d-01-01" % y)
                    e = min(stamp, "%04d-12-31" % y)
                    if s <= e:
                        p = pc.fetch_pollen(city["en"], s, e)
                        recs.extend(pc.normalize(p))
                        time.sleep(sleep_s)
                    y += 1
                wrows = []
            else:
                start = (today - timedelta(days=days)).isoformat()
                recs, wrows = collect_city(city, start, stamp)
                with open(os.path.join(raw_dir, city["en"] + ".json"), "w", encoding="utf-8") as f:
                    json.dump({"city": city, "fetched_at": datetime.now().isoformat(timespec="seconds"),
                               "pollen": recs, "weather_forecast": wrows}, f, ensure_ascii=False, indent=1)
        except Exception as exc:
            print("[error] %s: %s" % (city["en"], exc))
            summary_cities.append({"en": city["en"], "name": city["name"], "ok": False, "error": str(exc)})
            continue

        for r in recs:
            pollen_rows.append({
                "date": r["date"], "city": city["en"], "city_name": city["name"],
                "level_code": r["level_code"], "level": r["level"],
                "kind": r["kind"], "created_at": r["created_at"] or "",
            })
        for w in wrows:
            weather_rows.append({
                "date": w["date"], "city": city["en"],
                "code": w["code"] if w["code"] is not None else "",
                "weather": w["weather"], "is_rain": int(w["is_rain"]),
                "tmax": "" if w["tmax"] is None else w["tmax"],
                "tmin": "" if w["tmin"] is None else w["tmin"],
                "prcp_mm": "" if w["prcp_mm"] is None else w["prcp_mm"],
                "wind_kmh": "" if w["wind_kmh"] is None else w["wind_kmh"],
                "rhum_pct": "" if w["rhum_pct"] is None else w["rhum_pct"],
                "fetched_date": stamp,
            })

        real = [r for r in recs if r["level_code"] >= 0]
        latest = pc.latest_observed(recs)
        summary_cities.append({
            "en": city["en"], "name": city["name"], "prov": city["prov"],
            "ok": True,
            "latest_date": latest["date"] if latest else None,
            "latest_level": latest["level"] if latest else None,
            "latest_code": latest["level_code"] if latest else None,
            "real_days": len(real),
        })
        print("[ok] %s latest=%s/%s real_days=%d" % (
            city["en"],
            latest["date"] if latest else "-",
            latest["level"] if latest else "-", len(real)))
        if i < len(cities) - 1:
            time.sleep(sleep_s)

    n_pol = upsert_csv(
        os.path.join(ROOT, "data", "daily", "pollen.csv"),
        ["date", "city", "city_name", "level_code", "level", "kind", "created_at"],
        pollen_rows, ["date", "city", "kind"])
    n_wx = upsert_csv(
        os.path.join(ROOT, "data", "daily", "weather.csv"),
        ["date", "city", "code", "weather", "is_rain", "tmax", "tmin",
         "prcp_mm", "wind_kmh", "rhum_pct", "fetched_date"],
        weather_rows, ["date", "city"])

    summary = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "today": stamp, "mode": "backfill" if do_backfill else "daily",
        "cities_ok": sum(1 for c in summary_cities if c["ok"]),
        "cities_failed": [c["en"] for c in summary_cities if not c["ok"]],
        "pollen_rows": n_pol, "weather_rows": n_wx,
        "cities": summary_cities,
    }
    with open(os.path.join(ROOT, "data", "latest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("done. pollen_rows=%d weather_rows=%d ok=%d failed=%d" % (
        n_pol, n_wx, summary["cities_ok"], len(summary["cities_failed"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", default="", help="comma-separated city en names; default = all")
    ap.add_argument("--days", type=int, default=40)
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()
    names = [x.strip() for x in args.cities.split(",") if x.strip()]
    run(names, args.days, args.backfill, args.sleep)


if __name__ == "__main__":
    main()
