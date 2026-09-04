"""
Build the personal pollen rhinitis HTML report from daily raw snapshots.

Usage:
  python -m reporter.build_report --cities xian,xianyang
  python -m reporter.build_report --cities xian,xianyang --out web/report.html
"""
import argparse
import json
import os
from datetime import date, datetime, timedelta

from collectors import pollen_cma as pc
from predictor.rules import predict_series, season_phase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEASON_WINDOW = {
    "spring": ("03-01", "05-31", "春季花粉季(3-5月: 柏杨榆/悬铃木/牧草)"),
    "autumn": ("08-01", "10-31", "秋季花粉季(8-10月: 蒿属/葎草/豚草/藜苋)"),
}

CHEERS = [
    "花粉季只是一年中的一段,你比自己想象的更能扛。",
    "规范用药不是脆弱,是聪明地照顾自己。",
    "每一次认真防护,都是在给鼻子减负。",
    "雨后空气最干净,记得把那杯喜欢的茶留给自己。",
    "症状会有起伏,但季节一定会过去。",
    "今天也要好好洗鼻,把附着的花粉冲掉。",
    "你不需要硬扛,防护到位就可以安心出门。",
    "把口罩戴好,就是给自己最实在的安全感。",
    "难受的日子记下来,复诊时这些都是最有用的线索。",
    "身体在努力适应,你也在努力,这就够了。",
    "高浓度的日子缩短户外时间,不是退缩是策略。",
    "开窗通风选在清晨或雨后,小细节有大帮助。",
    "规律作息让免疫系统更稳,今晚早点休息。",
    "别和症状较劲,用药、冲洗、休息,一步一步来。",
    "你已经比上个花粉季更懂得照顾自己了。",
    "哪怕今天症状重一些,也不代表明天会一样。",
    "冷空气来时加件外套,鼻子会感谢你。",
    "运动可以换到室内,坚持本身就没有中断。",
    "记录不是负担,是你和身体对话的方式。",
    "回家先洗脸洗鼻,把花粉留在门外。",
    "被单衣物室内晾干,减少的不只是花粉还有焦虑。",
    "药按时用、觉按时睡,你已经做得很好。",
    "秋天的蒿草终会枯萎,清爽呼吸的日子正在路上。",
    "今天的谨慎,是为了症状更轻的明天。",
    "允许自己在难受的日子慢一点,没关系的。",
    "又平安度过一天高浓度日,你真的很会照顾自己。",
]

WEEK_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def current_season(today):
    md = (today.month, today.day)
    if (3, 1) <= md <= (5, 31):
        return "spring"
    if (8, 1) <= md <= (10, 31):
        return "autumn"
    return "autumn" if today.month in (6, 7) else "spring"


def build_city(city, raw, today):
    hist = raw["pollen"]
    wrows = raw["weather_forecast"]
    preds = predict_series(hist, wrows, today)

    start35 = today - timedelta(days=35)
    series = []
    by_date = {r["date"]: r for r in hist}
    for i in range(42):  # 35 history + 7 future window
        d = start35 + timedelta(days=i)
        ds = d.isoformat()
        r = by_date.get(ds)
        series.append({
            "date": ds,
            "code": r["level_code"] if r else None,
            "kind": r["kind"] if r else None,
            "level": r["level"] if r else "",
        })

    latest = pc.latest_observed(hist)
    fc = pc.future_forecasts(hist, today)

    sk = current_season(today)
    s_md, e_md, s_name = SEASON_WINDOW[sk]
    sy = today.year if (today.strftime("%m-%d") >= s_md) else today.year - 1
    s_start = "%04d-%s" % (sy, s_md)
    counts = {i: 0 for i in range(6)}
    for r in hist:
        if s_start <= r["date"] <= today.isoformat() and r["kind"] == "observed" and r["level_code"] >= 0:
            counts[r["level_code"]] += 1

    def wbrief(w):
        if not w:
            return None
        return {k: w[k] for k in ("date", "weather", "is_rain", "tmax", "tmin",
                                  "prcp_mm", "wind_kmh", "rhum_pct", "code")}

    return {
        "en": city["en"], "name": city["name"], "prov": city["prov"],
        "lat": city["lat"], "lon": city["lon"],
        "latest": latest,
        "first_forecast": fc[0] if fc else None,
        "series": series,
        "season": {"key": sk, "name": s_name, "start": s_start, "counts": counts},
        "predictions": [{
            "date": p["date"], "level": p["level"], "direction": p["direction"],
            "source": p["source"], "confidence": p["confidence"],
            "reasons": p["reasons"], "weather": wbrief(p["weather"]),
        } for p in preds],
        "weather_today": wbrief(wrows[0]) if wrows else None,
        "weather7": [wbrief(w) for w in wrows[:7]],
    }


def build(city_en_list, out_path, raw_date=None):
    today = date.fromisoformat(raw_date) if raw_date else date.today()
    with open(os.path.join(ROOT, "config", "cities.json"), encoding="utf-8") as f:
        all_cities = {c["en"]: c for c in json.load(f)["cities"]}
    raw_dir = os.path.join(ROOT, "data", "raw", today.isoformat())

    cities_data = []
    max_level = 0
    for en in city_en_list:
        with open(os.path.join(raw_dir, en + ".json"), encoding="utf-8") as f:
            raw = json.load(f)
        cd = build_city(all_cities[en], raw, today)
        cities_data.append(cd)
        if cd["latest"]:
            max_level = max(max_level, cd["latest"]["level_code"])
        if cd["first_forecast"]:
            max_level = max(max_level, cd["first_forecast"]["level_code"])

    idx = (today.month * 31 + today.day) % len(CHEERS)
    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "today": today.isoformat(),
        "weekday": WEEK_CN[today.weekday()],
        "cities": cities_data,
        "max_level": max_level,
        "cheer": CHEERS[idx],
        "cheers": CHEERS,
        "level_meta": {str(k): v for k, v in pc.LEVEL_META.items()},
    }

    tpl_path = os.path.join(ROOT, "reporter", "template.html")
    with open(tpl_path, encoding="utf-8") as f:
        html = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("'__DATA__'", payload)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("report written:", out_path, "%.0f KB" % (len(html.encode("utf-8")) / 1024))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", default="xian,xianyang")
    ap.add_argument("--out", default="")
    ap.add_argument("--date", default="", help="override today (YYYY-MM-DD), for testing")
    args = ap.parse_args()
    names = [x.strip() for x in args.cities.split(",") if x.strip()]
    stamp = args.date or date.today().isoformat()
    out = args.out or os.path.join("reports", "pollen-report-%s.html" % stamp)
    build(names, out, args.date or None)


if __name__ == "__main__":
    main()
