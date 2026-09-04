"""
China Weather (weather.com.cn / weatherdt) pollen index collector.

Internal JSON endpoint used by the official pollen page. No API key required,
but the Referer header is mandatory. Please poll politely (default sleep 1s
between cities) and do not hammer the service.

Level scheme (summer/autumn, grains per 1000 mm^2):
    -1 pending/not published yet ("暂无")
     0 none detected
     1 very low (1-20)  2 low (21-60)  3 medium (61-170)
     4 high (171-390)   5 very high (>=391)
NOTE: pre-2024 records used an older 5-tier naming; normalise via level_code only.
"""
from datetime import date
from urllib.parse import urlencode

from .http_utils import http_json

ENDPOINT = "https://graph.weatherdt.com/ty/pollen/v2/hfindex.html"
REFERER = "https://www.weather.com.cn/"

# Canonical 6-tier metadata keyed by level_code (current scheme since 2024).
LEVEL_META = {
    -1: {"name": "待发布", "color": "#E5E7EB"},
    0: {"name": "未检测", "color": "#999999", "min": 0, "max": 0},
    1: {"name": "很低", "color": "#81CB31", "min": 1, "max": 20, "pct": "10%"},
    2: {"name": "低", "color": "#A1FF3D", "min": 21, "max": 60, "pct": "25%"},
    3: {"name": "中", "color": "#F5EE32", "min": 61, "max": 170, "pct": "50%"},
    4: {"name": "高", "color": "#FFAF13", "min": 171, "max": 390, "pct": "75%"},
    5: {"name": "很高", "color": "#FF2319", "min": 391, "max": None, "pct": "75%+"},
}
LEVEL_ORDER = [0, 1, 2, 3, 4, 5]


def fetch_pollen(city_en, start, end):
    """Fetch raw pollen payload for one city between ISO dates (inclusive)."""
    qs = urlencode({
        "eletype": 1,
        "city": city_en,
        "start": start,
        "end": end,
        "predictFlag": "true",
    })
    url = "%s?%s" % (ENDPOINT, qs)
    return http_json(url, extra_headers={"Referer": REFERER})


def normalize(payload, today=None):
    """Turn a raw payload into a date-sorted list of canonical records.

    kind is "forecast" when either:
      - the record date is in the future relative to `today`, or
      - it was published (createDate) before its own date.
    Historical rows lack createDate and are observed as long as they are not future.
    """
    today = today or date.today()
    today_s = today.isoformat()
    out = []
    for item in payload.get("dataList", []):
        d = item.get("addTime")
        if not d:
            continue
        code = item.get("levelCode", -1)
        created = item.get("createDate")  # e.g. 2026-09-03T16:14:22
        kind = "observed"
        if d > today_s:
            kind = "forecast"
        elif created and len(created) >= 10 and d > created[:10]:
            kind = "forecast"
        out.append({
            "date": d,
            "level_code": code if code in LEVEL_META else -1,
            "level": item.get("level", ""),
            "color": item.get("color", ""),
            "msg": item.get("levelMsg", ""),
            "created_at": created or None,
            "kind": kind,
        })
    out.sort(key=lambda r: r["date"])
    return out


def latest_observed(records):
    """Most recent record with a real level (code >= 0), observed preferred."""
    obs = [r for r in records if r["level_code"] >= 0 and r["kind"] == "observed"]
    if obs:
        return obs[-1]
    real = [r for r in records if r["level_code"] >= 0]
    return real[-1] if real else None


def future_forecasts(records, today):
    """All forecast records dated after today, sorted ascending."""
    today_s = today.isoformat() if hasattr(today, "isoformat") else str(today)
    return [r for r in records if r["kind"] == "forecast" and r["date"] > today_s]
