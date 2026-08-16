"""STEP 5 — SYNTHESIS: turn the pooled niche signals into a clean list of candidate BETS.
Usage: python3 5_synthesize_bets.py [workdir]   Reads videos.json, analysis.json, gaps.json -> bets.json

This is the DETERMINISTIC half of the Synthesis<->Critique loop (see
references/synthesis_critique_loop.md). It does NOT decide the final bets — it builds an
unbiased candidate pool that the two-model AUDITOR then merges / names / prunes / verdicts.

WHY lift-seeds, not Pattern Σexcess clusters: pooling many channels makes generic vocabulary
('most','true','scientists','world') dominate any frequency/Σexcess ranking. Anchoring each
candidate on a HIGH-LIFT phrase/word surfaces real breakout TOPICS instead of connector words.

Each bet carries 4 critique signals so the Auditor argues from numbers, not vibes:
  corroboration  — how many independent streams back it (outlier + lift + gap). 1 = weak.
  concentration  — Σexcess share of the single biggest channel (high = one-channel fluke).
  coherence      — mean pairwise title-token Jaccard of the cluster (low = generic connector).
  recency        — median age (days) of the cluster's outliers (old = signal may be fading).
Plus a provisional Builder verdict (STRONG/TEST/WEAK) and a falsifier ("this is wrong if ...").
"""
import sys, json, re, statistics, os
from datetime import datetime, timezone
from collections import defaultdict
from _common import compute_outliers, jload

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)

v = json.load(open(p("videos.json"), encoding="utf-8"))
b = json.load(open(p("analysis.json"), encoding="utf-8"))
gaps = jload(p("gaps.json"), None)
compute_outliers(v, datetime.now(timezone.utc))

# ---------------- tunables (declared, not magic) ----------------
SEED_UNI_MIN_LIFT = 2.5     # a single-word seed must over-index this much to qualify
MIN_CLUSTER_OUTLIERS = 2    # a seed must match >=2 valid-primary outliers to be a candidate
COH_TOPN = 12               # titles used for the coherence proxy
STRONG_MIN_CHANNELS = 3
STRONG_MAX_CONCENTRATION = 0.60
# function/structure words that pass lift gates but are never a topic on their own
GENERIC = set(("thing things really actually truly simply just now then here there about into onto "
               "made make makes making does did why what how when where which who your you our their "
               "this that these those been being have has had will would could should more most than "
               "very much many such other another every each some any all one two new old big small "
               "the of to and or but with from by as is are was were be it its their").split())

STOP = set(("the of in on at to for and or but with from by as is are was were be this that it its "
            "their you we they how why what when which who a an does do did will can could not no into "
            "vs com de la el un les des en und der die das").split())
def toks(t):
    return [w for w in re.sub(r"[^\w\s]", " ", (t or "").lower(), flags=re.UNICODE).split()
            if len(w) > 2 and w not in STOP]

# ---------------- valid primary outliers (the only evidence base) ----------------
outs = [x for x in v if x.get("valid") and x.get("scope") == "primary" and x.get("ox", 0) >= 3]
now = datetime.now(timezone.utc)
for o in outs:
    try:
        dt = datetime.fromisoformat((o.get("publishedAt") or "").replace("Z", "+00:00"))
        o["_age"] = max((now - dt).days, 0)
    except Exception:
        o["_age"] = None
    o["_tl"] = (o.get("title") or "").lower()

# ---------------- gap text (for the 3rd corroboration stream) ----------------
gap_text = ""
gap_examples = {}
if gaps:
    parts = []
    for t in gaps.get("themes", []):
        theme = str(t.get("theme", ""))
        ex = " ".join(e.get("q", "") for e in t.get("examples", []))
        parts.append(theme + " " + ex)
        for w in theme.lower().split():
            gap_examples.setdefault(w, theme)
    gap_text = " ".join(parts).lower()

# ---------------- seeds: significant lift bigrams + high-lift unigrams ----------------
seeds = []   # (term, lift, kind)
for r in b.get("lift_bigrams", []):
    if r.get("sig"):
        seeds.append((str(r["key"]).lower().strip(), r.get("lift"), "phrase"))
for r in b.get("lift_unigrams", []):
    if r.get("sig") and (r.get("lift") or 0) >= SEED_UNI_MIN_LIFT:
        seeds.append((str(r["key"]).lower().strip(), r.get("lift"), "word"))

def jaccard(a, c):
    A, B = set(a), set(c)
    return len(A & B) / len(A | B) if (A | B) else 0.0

bets = []
for term, lift, kind in seeds:
    cl = [o for o in outs if term in o["_tl"]]
    if len(cl) < MIN_CLUSTER_OUTLIERS:
        continue
    by_ch = defaultdict(float)
    for o in cl:
        by_ch[o.get("channelTitle") or o.get("channelId")] += max(o.get("excess", 0), 0)
    nch = len(by_ch)
    tot = sum(by_ch.values()) or 1.0
    concentration = max(by_ch.values()) / tot
    top = sorted(cl, key=lambda o: -o.get("excess", 0))[:COH_TOPN]
    tsets = [[w for w in toks(o.get("title")) if w != term and w not in term.split()] for o in top]
    pj = [jaccard(tsets[i], tsets[j]) for i in range(len(tsets)) for j in range(i + 1, len(tsets))]
    coherence = statistics.mean(pj) if pj else 0.0
    ages = [o["_age"] for o in cl if o["_age"] is not None]
    med_age = int(statistics.median(ages)) if ages else None
    in_gap = any(w in gap_text for w in term.split())
    corro = 2 + (1 if in_gap else 0)   # lift-seed itself = outlier-stream + lift-stream; +gap
    generic_risk = all(w in GENERIC for w in term.split())

    if generic_risk and coherence < 0.12:
        verdict = "WEAK"
    elif nch >= STRONG_MIN_CHANNELS and concentration < STRONG_MAX_CONCENTRATION and not generic_risk:
        verdict = "STRONG"
    else:
        verdict = "TEST"

    falsifier = (f"WRONG if the {nch} channels' titles aren't really one topic, "
                 f"or if {round(concentration*100)}% of the reach is one channel's fluke, "
                 f"or if the cluster is already saturated.")

    bets.append({
        "term": term, "kind": kind, "lift": lift,
        "builder_verdict": verdict,
        "topic_group": None,           # Auditor fills: merged human topic name
        "corroboration": corro, "streams": "+".join(
            ["outlier", "lift"] + (["gap"] if in_gap else [])),
        "n_channels": nch, "n_outliers": len(cl),
        "sum_excess": int(tot),
        "concentration": round(concentration, 2),
        "coherence": round(coherence, 2),
        "median_age_days": med_age,
        "gap_match": (gap_examples.get(term.split()[0]) if in_gap else None),
        "generic_risk": generic_risk,
        "falsifier": falsifier,
        "evidence": [{"channel": o.get("channelTitle"), "title": o.get("title"),
                      "ox": o.get("ox"), "excess": int(o.get("excess", 0)),
                      "age_days": o["_age"]} for o in top[:5]],
    })

# de-dup identical terms; order STRONG>TEST>WEAK then by reach
seen, uniq = set(), []
order = {"STRONG": 2, "TEST": 1, "WEAK": 0}
for x in sorted(bets, key=lambda d: (-order[d["builder_verdict"]], -d["sum_excess"])):
    if x["term"] in seen:
        continue
    seen.add(x["term"]); uniq.append(x)

out = {
    "generated": datetime.now(timezone.utc).isoformat(),
    "method": "lift-seed synthesis; 4 critique signals; Builder verdict (pre-audit)",
    "note": "CANDIDATES ONLY. Run the two-model Auditor to merge/name/prune and set final verdict.",
    "tunables": {"SEED_UNI_MIN_LIFT": SEED_UNI_MIN_LIFT,
                 "MIN_CLUSTER_OUTLIERS": MIN_CLUSTER_OUTLIERS,
                 "STRONG_MIN_CHANNELS": STRONG_MIN_CHANNELS,
                 "STRONG_MAX_CONCENTRATION": STRONG_MAX_CONCENTRATION},
    "n_candidates": len(uniq),
    "bets": uniq,
}
json.dump(out, open(p("bets.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(seeds)} lift-seeds -> {len(uniq)} candidate bets -> {p('bets.json')}")
for x in uniq[:25]:
    print(f"  {x['builder_verdict']:6} {x['term'][:20]:20} lift={x['lift']!s:>5} ch={x['n_channels']:>2} "
          f"conc={x['concentration']:>4} coh={x['coherence']:>4} Σexc={x['sum_excess']:>11,}")
