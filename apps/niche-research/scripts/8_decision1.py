"""STEP 8 [PY] — DECISION 1 (Go / No-Go): should you enter this niche at all?
Usage: python3 8_decision1.py [workdir]   Reads demand/monetization/crackability.json + videos.json -> decision1.json

Five pillars (0..100), weighted -> attractiveness, THEN a hard gate:
  Demand        7_demand.score
  Monetization  6_monetization.score
  Crackability  5_crackability.score        <-- also a HARD GATE
  Competition   inverse of view-concentration (HHI) across channels (less concentrated = easier)
  Trend         from 7_demand.trend
HARD GATE: crackability verdict CLOSED  -> NO-GO no matter how attractive (an authority-locked niche
is un-enterable for a newcomer). UNKNOWN -> CONDITIONAL (need more data).
"""
import sys, json, os
from collections import defaultdict
from _common import jsave, compute_outliers, get_scan_time

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)
def load(f, d=None): return json.load(open(p(f), encoding="utf-8")) if os.path.exists(p(f)) else d

WEIGHTS = {"demand": 0.25, "monetization": 0.20, "crackability": 0.25, "competition": 0.15, "trend": 0.15}

videos = json.load(open(p("videos.json"), encoding="utf-8"))
compute_outliers(videos, get_scan_time(WORK))   # needed so x["age"] exists for the recent-window HHI (pinned time, V12)
demand = load("demand.json", {}); money = load("monetization.json", {}); crack = load("crackability.json", {})

# --- Competition pillar: HHI of RECENT views across channels (0=fragmented, 1=monopoly) ---
# Only count videos within the recent window so inactive legacy channels with huge
# accumulated view counts don't dominate the concentration metric.
from _common import RECENT_WINDOW_MONTHS
recent_cutoff_days = RECENT_WINDOW_MONTHS * 30.44
ch_views = defaultdict(int)
for x in videos:
    age = x.get("age")
    if age is not None and age <= recent_cutoff_days:
        ch_views[x["channelId"]] += x.get("viewCount", 0)
tot = sum(ch_views.values()) or 1
hhi = sum((v / tot) ** 2 for v in ch_views.values())          # 1/N (even) .. 1 (one channel)
n_ch = len(ch_views) or 1
# normalize against an even split (1/N): 0 shares evenly -> high score; near-monopoly -> low
competition_score = round(100 * max(0.0, min(1.0, (1 - hhi) / (1 - 1.0 / n_ch))) ) if n_ch > 1 else 0

trend_map = {"RISING": 80, "FLAT": 50, "DECLINING": 25}
# A missing optional input is N/A, NOT zero: weights are RE-NORMALIZED over the pillars we actually
# have. (The old code scored a missing monetization.json as 0/100 — up to -20 attractiveness — which
# silently biased borderline niches to NO-GO; audit V8.) Missing crackability is still handled by the
# hard gate below (UNKNOWN -> CONDITIONAL).
pillars = {
    "demand": demand.get("score") if demand else None,
    "monetization": money.get("score") if money else None,
    "crackability": crack.get("score"),                      # None khi UNKNOWN/thiếu
    "competition": competition_score,
    "trend": trend_map.get(demand.get("trend", "FLAT"), 50) if demand else None,
}
present = {k: v for k, v in pillars.items() if v is not None}
wsum = sum(WEIGHTS[k] for k in present) or 1.0
attractiveness = round(sum(present[k] * WEIGHTS[k] for k in present) / wsum)
missing = [k for k in WEIGHTS if k not in present]
if missing:
    print(f"note: pillar(s) {missing} unavailable — weights re-normalized over the rest (no zero-penalty)")

# --- hard gate ---
cv = crack.get("verdict", "UNKNOWN")
if cv == "CLOSED":
    decision, gate = "NO-GO", "crackability=CLOSED (authority-locked) — hard gate overrides score"
elif cv == "UNKNOWN":
    decision, gate = "CONDITIONAL", "crackability=UNKNOWN (too few outliers) — gather more channels/data"
elif attractiveness >= 62 and cv in ("OPEN", "SEMI"):
    decision, gate = "GO", f"attractiveness {attractiveness} with crackability={cv}"
elif attractiveness >= 48:
    decision, gate = "CONDITIONAL", f"attractiveness {attractiveness} — borderline; enter only with a sharp beachhead"
else:
    decision, gate = "NO-GO", f"attractiveness {attractiveness} too low"

out = {
    "method": "weighted 5-pillar attractiveness (weights re-normalized over available pillars) + crackability hard-gate",
    "weights": WEIGHTS,
    "pillars": pillars,
    "pillars_missing": missing,
    "competition_hhi": round(hhi, 4), "n_channels": n_ch,
    "attractiveness": attractiveness,
    "crackability_verdict": cv,
    "decision": decision,
    "gate_reason": gate,
    "inputs_present": {"demand": bool(demand), "monetization": bool(money), "crackability": bool(crack)},
}
jsave(p("decision1.json"), out)
print(f"decision1.json — {decision}  attractiveness={attractiveness}  pillars={pillars}  gate: {gate}")
