"""
Open-Meteo weather driver (free, no API key, CC-BY 4.0).

- forecast(): daily weather for the next N days (driver for L1 rule prediction)
- archive(): ERA5 reanalysis daily weather (free historical features for later ML)

Pollen species from the Air-Quality API are Europe-only and return null over
China, so they are intentionally not used here.
"""
from urllib.parse import urlencode

from .http_utils import http_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_FIELDS = ",".join([
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "wind_speed_10m_max",
    "relative_humidity_2m_mean",
])

# WMO weather interpretation codes -> concise Chinese label + rain flag
WMO = {
    0: ("晴", False), 1: ("基本晴朗", False), 2: ("多云", False), 3: ("阴", False),
    45: ("雾", False), 48: ("雾凇", False),
    51: ("小毛毛雨", True), 53: ("毛毛雨", True), 55: ("浓毛毛雨", True),
    56: ("冻毛毛雨", True), 57: ("冻毛毛雨", True),
    61: ("小雨", True), 63: ("中雨", True), 65: ("大雨", True),
    66: ("冻雨", True), 67: ("冻雨", True),
    71: ("小雪", True), 73: ("中雪", True), 75: ("大雪", True), 77: ("雪粒", True),
    80: ("阵雨", True), 81: ("强阵雨", True), 82: ("暴雨", True),
    85: ("阵雪", True), 86: ("强阵雪", True),
    95: ("雷阵雨", True), 96: ("雷阵雨伴冰雹", True), 99: ("强雷暴冰雹", True),
}


def _daily_rows(payload):
    d = payload.get("daily", {})
    dates = d.get("time", [])
    codes = d.get("weather_code", [])
    tmax = d.get("temperature_2m_max", [])
    tmin = d.get("temperature_2m_min", [])
    prcp = d.get("precipitation_sum", [])
    wind = d.get("wind_speed_10m_max", [])
    rhum = d.get("relative_humidity_2m_mean", [])
    rows = []
    for i, day in enumerate(dates):
        code = codes[i] if i < len(codes) else None
        label, is_rain = WMO.get(code, ("未知", False))
        rows.append({
            "date": day,
            "code": code,
            "weather": label,
            "is_rain": is_rain,
            "tmax": tmax[i] if i < len(tmax) else None,
            "tmin": tmin[i] if i < len(tmin) else None,
            "prcp_mm": prcp[i] if i < len(prcp) else None,
            "wind_kmh": wind[i] if i < len(wind) else None,
            "rhum_pct": rhum[i] if i < len(rhum) else None,
        })
    return rows


def forecast(lat, lon, days=7):
    qs = urlencode({
        "latitude": lat, "longitude": lon,
        "daily": DAILY_FIELDS,
        "timezone": "Asia/Shanghai",
        "forecast_days": days,
    })
    return _daily_rows(http_json("%s?%s" % (FORECAST_URL, qs)))


def archive(lat, lon, start, end):
    qs = urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": DAILY_FIELDS,
        "timezone": "Asia/Shanghai",
    })
    return _daily_rows(http_json("%s?%s" % (ARCHIVE_URL, qs)))
