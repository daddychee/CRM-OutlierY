"""STEP 7 [PY] — DEMAND & TREND: how big and which way is the niche moving?
Usage: python3 7_demand.py [workdir]   Reads videos.json -> demand.json

Deterministic signals:
  demand_median_views   median views of RECENT MATURED videos (the niche's typical reach right now).
  reach_p90             90th-pct views (how big the ceiling is).
  supply_per_month      recent upload cadence across all channels (competition supply).
  trend                 RISING / FLAT / DECLINING from the slope of monthly median OX (last 12 mo) —
                        OX is already age-adjusted by the maturity curve, so the natural early-spike
                        decay of raw views/day can't fake a trend (audit V3).
  trend_strength        normalized slope magnitude.

Honest limit: a single API snapshot mixes age/cohort/period (R-1); trend is directional, not causal.
NOTE (audit V1): trend is NOT baked into this score anymore — it is its own pillar in Decision 1.
"""
import sys, json, os, statistics
from collections import defaultdict
from _common import compute_outliers, _pct, jsave, get_scan_time

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)

now = get_scan_time(WORK)                    # pinned scan time (V12)
videos = json.load(open(p("videos.json"), encoding="utf-8"))
compute_outliers(videos, now)

matured = [x for x in videos if x.get("age") is not None and 45 <= x["age"] <= 18 * 30.44]
views = [x["viewCount"] for x in matured] or [0]
demand_median = int(statistics.median(views))
reach_p90 = int(_pct(views, 90))

# supply: uploads per month over the last 12 months
recent = [x for x in videos if x.get("age") is not None and x["age"] <= 365]
supply_per_month = round(len(recent) / 12.0, 1)

# trend: monthly median OX over the last 12 months (by publish-month bucket), least-squares slope.
# OX = views / (channel_scale x shape(age)) — the maturity curve already removes the age effect, so
# a flat market reads ~1.0 in every month. views/day (the old metric) still decayed with age
# (early-spike long tail) and biased recent months toward a fake RISING (audit V3).
by_month = defaultdict(list)
for x in matured:
    if x["age"] <= 365 and not x.get("scale_borrowed"):
        m = int(x["age"] // 30.44)            # 0 = this month ... 11 = ~a year ago
        by_month[m].append(x.get("ox", 0))
pts = sorted((11 - m, statistics.median(vs)) for m, vs in by_month.items() if len(vs) >= 3)  # x asc in time
trend, trend_strength = "FLAT", 0.0
if len(pts) >= 4:
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom else 0
    norm = slope / my if my else 0          # fractional change per month
    trend_strength = round(norm, 3)
    if norm >= 0.05: trend = "RISING"
    elif norm <= -0.05: trend = "DECLINING"

# 0..100 demand pillar (log-scaled reach, so a mega niche doesn't dwarf everything).
# Trend is deliberately NOT added here: Decision 1 already weighs trend as its own pillar, and
# adding it twice double-penalized DECLINING / double-rewarded RISING niches (audit V1).
import math
score = max(0, min(100, round(12 * math.log10(max(demand_median, 10)))))   # ~48 at 10k, ~72 at 1M

out = {
    "method": "recent-matured median/p90 views + monthly-median OX slope (last 12 mo, age-adjusted); trend NOT in score (own pillar in D1)",
    "n_matured": len(matured),
    "demand_median_views": demand_median,
    "reach_p90_views": reach_p90,
    "supply_per_month": supply_per_month,
    "trend": trend, "trend_strength": trend_strength,
    "score": score,
    "residuals": ["R-1 one snapshot mixes age/cohort/period -> trend is directional, not causal",
                  "R-5 OX-based trend removes the age curve, but the curve itself is estimated from this same snapshot"],
}
jsave(p("demand.json"), out)
print(f"demand.json — median_views={demand_median:,} p90={reach_p90:,} supply/mo={supply_per_month} "
      f"trend={trend}({trend_strength}) score={score}")
