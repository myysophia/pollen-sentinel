#!/usr/bin/env bash
# Daily pipeline: collect -> personal report -> national dashboard data.
# Designed to run both locally and inside GitHub Actions (no third-party deps).
set -euo pipefail
cd "$(dirname "$0")/.."

# CITIES: comma-separated city en names; empty = all monitored cities.
# REPORT_CITIES: cities included in the personal HTML report.
CITIES="${CITIES:-}"
REPORT_CITIES="${REPORT_CITIES:-xian,xianyang}"
SLEEP="${SLEEP:-0.8}"

echo "==> [1/3] collecting pollen + weather (CITIES='${CITIES:-all}')"
if [ -z "$CITIES" ]; then
  python3 -m collectors.collect --sleep "$SLEEP"
else
  python3 -m collectors.collect --cities "$CITIES" --sleep "$SLEEP"
fi

echo "==> [2/3] building personal report for ${REPORT_CITIES}"
python3 -m reporter.build_report --cities "$REPORT_CITIES" --out web/reports/latest.html
TODAY="$(date +%F)"
cp web/reports/latest.html "web/reports/${TODAY}.html"

echo "==> [3/3] exporting national dashboard data"
python3 scripts/export_web.py

# Publish the committed personal diary archive so the Pages report can read it.
mkdir -p web/data
if [ -f data/personal/diary.json ]; then
  cp data/personal/diary.json web/data/diary.json
fi

echo "daily pipeline finished."
