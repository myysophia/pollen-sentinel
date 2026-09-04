"""
L1 rule-based pollen outlook (explainable, conservative).

Why rules first:
- Official labels are 6 coarse tiers; precise grain counts do not exist.
- Pollen concentration is strongly weather-driven: rain washes particles out,
  strong cold surges suppress release, persistent dry/windy days in the
  climber/peak phenology phase favour accumulation.
- Every predicted day carries human-readable reasons and a confidence tag.
  Official published forecasts are always preferred and tagged "official".

ML models (L2) replace the rule rollout once enough daily snapshots exist;
until then this module is deterministic and needs no training data.
"""
from datetime import date


def season_phase(day):
    """Pollen season phase for northern-China cities: ramp / peak / decline / off."""
    m, d = day.month, day.day
    if m == 3:
        return "ramp"          # 春季爬升: 柏/杨/榆
    if m == 4:
        return "peak"          # 春季高峰: 杨柳/悬铃木/白蜡
    if m == 5:
        return "decline" if d >= 11 else "peak"
    if m == 8:
        return "ramp"          # 秋季爬升: 葎草/蒿开始
    if m == 9:
        return "peak"          # 秋季高峰: 蒿属/豚草/藜苋
    if m == 10:
        return "decline"       # 秋季消退
    return "off"


def clamp_level(v):
    return max(0, min(5, int(v)))


def predict_series(history, weather_rows, today):
    """
    history: list of normalized pollen records (ascending date, may contain nulls)
    weather_rows: list of Open-Meteo daily rows (today + future)
    today: datetime.date

    Returns list of dicts for FUTURE days only:
    {date, level, direction, source(official/rule), confidence(high/medium/low), reasons[]}
    """
    # Latest real observed level as the rollout anchor.
    anchor = None
    for r in reversed(history):
        if r["level_code"] >= 0 and r["kind"] == "observed":
            anchor = r
            break
    if anchor is None:
        for r in reversed(history):
            if r["level_code"] >= 0:
                anchor = r
                break
    cur = anchor["level_code"] if anchor else 0

    official_by_date = {}
    for r in history:
        if r["kind"] == "forecast" and r["level_code"] >= 0 and r["date"] > today.isoformat():
            official_by_date[r["date"]] = r["level_code"]

    w_by_date = {w["date"]: w for w in weather_rows}
    future = [w for w in weather_rows if w["date"] > today.isoformat()]

    out = []
    prev = cur
    prev_w = w_by_date.get(today.isoformat())
    dry_streak = 0
    if prev_w and not prev_w["is_rain"] and (prev_w["prcp_mm"] or 0) < 1:
        dry_streak = 1

    for idx, w in enumerate(future):
        y, m, d = map(int, w["date"].split("-"))
        phase = season_phase(date(y, m, d))
        reasons = []

        if w["date"] in official_by_date:
            lvl = official_by_date[w["date"]]
            source, conf = "official", "high"
            reasons.append("官方已发布预报")
        else:
            lvl = prev
            source = "rule"
            # 1) washout by rain today
            prcp = w["prcp_mm"] or 0
            if w["is_rain"] or prcp >= 1:
                drop = 2 if prcp >= 10 else 1
                lvl -= drop
                reasons.append(("降水%.0fmm冲刷,等级下调%d级" % (prcp, drop)) if prcp >= 1
                               else "有降水,利于花粉沉降")
                dry_streak = 0
            else:
                dry_streak += 1
            # 2) lagged washout from yesterday's heavy rain
            if prev_w and (prev_w["prcp_mm"] or 0) >= 10 and not (w["is_rain"] or prcp >= 1):
                lvl -= 1
                reasons.append("昨日大雨后空气残留湿度,浓度继续回落")
            # 3) strong cold surge
            if prev_w and prev_w["tmax"] is not None and w["tmax"] is not None:
                delta = w["tmax"] - prev_w["tmax"]
                if delta <= -6:
                    lvl -= 1
                    reasons.append("强降温%.0f℃抑制花粉释放" % delta)
            # 4) persistent dry + windy during ramp/peak -> accumulate
            wind = w["wind_kmh"] or 0
            rhum = w["rhum_pct"] or 100
            if dry_streak >= 2 and phase in ("ramp", "peak") and rhum < 55 and wind >= 18:
                if phase == "ramp" or lvl <= 3:
                    lvl += 1
                    reasons.append("连续干燥有风,花粉易累积扩散")
            # 5) phenology guard rails
            if phase == "off":
                lvl = min(lvl, 1)
                reasons.append("非主要花粉季,本底水平")
            elif phase == "decline" and not (w["is_rain"] or prcp >= 1):
                # decline phase: do not let rules raise levels
                lvl = min(lvl, prev)
            if not reasons:
                reasons.append("气象平稳,维持当前等级")
            conf = "medium" if idx <= 1 else "low"

        lvl = clamp_level(lvl)
        direction = "平" if lvl == prev else ("升" if lvl > prev else "降")
        out.append({
            "date": w["date"],
            "level": lvl,
            "direction": direction,
            "source": source,
            "confidence": conf,
            "reasons": reasons,
            "weather": w,
        })
        prev = lvl
        prev_w = w
    return out
