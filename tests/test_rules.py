"""Unit tests for the L1 rule predictor (offline, deterministic)."""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from predictor.rules import predict_series, season_phase, clamp_level  # noqa: E402


def w(d, code=0, tmax=30, tmin=20, prcp=0, wind=10, rhum=50, weather="晴", is_rain=False):
    return {"date": d, "code": code, "weather": weather, "is_rain": is_rain,
            "tmax": tmax, "tmin": tmin, "prcp_mm": prcp, "wind_kmh": wind, "rhum_pct": rhum}


def obs(d, code):
    return {"date": d, "level_code": code, "level": "", "kind": "observed",
            "color": "", "msg": "", "created_at": None}


def fc(d, code):
    return {"date": d, "level_code": code, "level": "", "kind": "forecast",
            "color": "", "msg": "", "created_at": None}


class RuleTests(unittest.TestCase):

    def test_clamp(self):
        self.assertEqual(clamp_level(-2), 0)
        self.assertEqual(clamp_level(9), 5)

    def test_phase(self):
        self.assertEqual(season_phase(date(2026, 9, 4)), "peak")
        self.assertEqual(season_phase(date(2026, 3, 10)), "ramp")
        self.assertEqual(season_phase(date(2026, 12, 1)), "off")

    def test_official_forecast_wins(self):
        hist = [obs("2026-09-04", 5), fc("2026-09-05", 4)]
        weather = [w("2026-09-04"), w("2026-09-05")]
        out = predict_series(hist, weather, date(2026, 9, 4))
        self.assertEqual(out[0]["level"], 4)
        self.assertEqual(out[0]["source"], "official")
        self.assertEqual(out[0]["confidence"], "high")

    def test_heavy_rain_washes_down(self):
        hist = [obs("2026-09-04", 5)]
        weather = [w("2026-09-04"),
                   w("2026-09-05", code=65, prcp=20, weather="大雨", is_rain=True)]
        out = predict_series(hist, weather, date(2026, 9, 4))
        # -2 from 20mm washout => level 3
        self.assertEqual(out[0]["level"], 3)
        self.assertTrue(any("冲刷" in r for r in out[0]["reasons"]))

    def test_off_season_caps_level(self):
        hist = [obs("2026-12-10", 3)]
        weather = [w("2026-12-10"), w("2026-12-11")]
        out = predict_series(hist, weather, date(2026, 12, 10))
        self.assertLessEqual(out[0]["level"], 1)


if __name__ == "__main__":
    unittest.main()
