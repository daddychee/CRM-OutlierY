"""STEP 5 [PY] — CRACKABILITY: can a NEWCOMER break into this niche, or is it authority-locked?
Usage: python3 5_crackability.py [workdir]   Reads videos.json, channels.json -> crackability.json

Deterministic signals (LLM never touches these numbers):
  newcomer_rate        share of valid outliers coming from SMALL / YOUNG channels (below-median subs
                       or channel age < YOUNG_MONTHS). High = outsiders can win.
  authority_dependence Spearman(OX, subs) over valid videos. High positive = big channels win by size.
  pattern_replicability median # of distinct channels per repeated outlier-keyword cluster (>=2 outliers).
                       High = the WINNING formula travels across channels (not one-channel magic).
  verdict              OPEN / SEMI / CLOSED  (drives the Decision-1 hard gate in S8).

Honest limits: current subs != subs-at-post (residual R-A in the architecture doc). newcomer_rate is a
conservative proxy. OX rests on the recent-window assumption (R-1). Treat as an informed bet.
"""
import sys, json, os, statistics
from collections import defaultdict
from _common import compute_outliers, spearman, _pct, jsave, winners, compute_newcomers, get_scan_time

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)

YOUNG_MONTHS = 24          # a channel younger than this counts as a "newcomer"
MIN_OUTLIERS = 5           # need at least this many valid outliers to judge crackability

videos = json.load(open(p("videos.json"), encoding="utf-8"))
chinfo = json.load(open(p("channels.json"), encoding="utf-8")) if os.path.exists(p("channels.json")) else {}
now = get_scan_time(WORK)                    # pinned scan time (V12)
compute_outliers(videos, now)

def subs_of(cid):
    try: return int(chinfo.get(cid, {}).get("subs") or 0)
    except Exception: return 0

# valid primary videos are the trustworthy scoring universe
valid = [x for x in videos if x.get("valid") and x.get("scope") == "primary"]
outliers = winners(videos)                   # valid primary >=3x + early-confirmed fresh (V7)

# newcomer = small AND young, shared definition from _common (also used per-cluster by S9);
# median subs from OUTLIER channels only — using all channels inflates the median
outlier_channels = {x["channelId"] for x in outliers}
newcomer_channels, median_subs = compute_newcomers(outlier_channels, chinfo, now, YOUNG_MONTHS)
newcomer_rate = round(len(newcomer_channels) / len(outlier_channels), 3) if outlier_channels else 0.0

# --- authority_dependence: Spearman(OX, subs) over valid videos ---
sp = spearman([x.get("ox", 0) for x in valid], [subs_of(x["channelId"]) for x in valid])
authority_dependence = round(max(sp, 0.0), 3) if sp is not None else None  # only positive matters

# --- pattern_replicability: do outlier keyword clusters travel across channels? ---
from _common import tokenize as toks     # shared stop-list (V5: no more per-script drift)
kw_ch = defaultdict(set); kw_n = defaultdict(int)
for x in outliers:
    for w in set(toks(x["title"])):
        kw_ch[w].add(x["channelId"]); kw_n[w] += 1
repeated = [len(kw_ch[w]) for w in kw_ch if kw_n[w] >= 2]
pattern_replicability = round(statistics.median(repeated), 2) if repeated else 1.0

# --- verdict ---
enough = len(outliers) >= MIN_OUTLIERS
if not enough:
    verdict = "UNKNOWN"; reason = f"only {len(outliers)} valid outliers (<{MIN_OUTLIERS}) — not enough to judge."
else:
    auth = authority_dependence if authority_dependence is not None else 0.0
    open_signals = (newcomer_rate >= 0.5) + (auth <= 0.35) + (pattern_replicability >= 2)
    closed_signals = (newcomer_rate <= 0.25) + (auth >= 0.6) + (pattern_replicability < 2)
    if open_signals >= 2 and closed_signals == 0:
        verdict = "OPEN"
    elif closed_signals >= 2:
        verdict = "CLOSED"
    else:
        verdict = "SEMI"
    reason = (f"newcomer_rate={newcomer_rate}, authority_dependence={auth}, "
              f"pattern_replicability={pattern_replicability} over {len(outliers)} outliers.")

# 0..100 score (only used for ranking / the Decision-1 pillar)
if not enough:
    score = None
else:
    auth = authority_dependence if authority_dependence is not None else 0.0
    score = round(100 * (0.45 * newcomer_rate + 0.35 * (1 - min(auth, 1.0))
                         + 0.20 * min(pattern_replicability / 4.0, 1.0)))

out = {
    "generated": now.isoformat(),
    "method": "newcomer_rate + Spearman(OX,subs) + pattern_replicability; verdict gates Decision-1",
    "n_valid": len(valid), "n_outliers": len(outliers),
    "median_subs": median_subs, "young_months": YOUNG_MONTHS,
    "newcomer_rate": newcomer_rate,
    "authority_dependence": authority_dependence,
    "pattern_replicability": pattern_replicability,
    "score": score,
    "verdict": verdict,
    "reason": reason,
    "residuals": ["R-A current subs != subs-at-post -> newcomer_rate is conservative",
                  "R-1 OX rests on the recent-window assumption"],
}
jsave(p("crackability.json"), out)
print(f"crackability.json — verdict={verdict} score={score} newcomer_rate={newcomer_rate} "
      f"authority_dep={authority_dependence} pattern_repl={pattern_replicability} (n_outliers={len(outliers)})")
