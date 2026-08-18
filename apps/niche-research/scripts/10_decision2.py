"""STEP 10 [PY] — DECISION 2 (beachhead): which sub-niche to attack FIRST?
Usage: python3 10_decision2.py [workdir]   Reads subniche.json (+ crackability/monetization) -> decision2.json

Beachhead score per cluster = geomean(reach, opportunity, replicability) / sqrt(competition), with floors
so no single zero nukes a cluster. The idea: pick a territory that is big ENOUGH, winnable (fragmented,
repeatable outliers), and not already dominated. Global crackability/monetization scale every cluster.
`decision` = the top cluster if it clears a minimum bar, else "WIDEN SEARCH".
"""
import sys, json, os, math
from _common import jsave

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)
def load(f, d=None): return json.load(open(p(f), encoding="utf-8")) if os.path.exists(p(f)) else d

sn = load("subniche.json", {"clusters": []})
crack = load("crackability.json", {}) or {}
money = load("monetization.json", {}) or {}
clusters = sn.get("clusters", [])

if not clusters:
    jsave(p("decision2.json"), {"method": "beachhead geomean/sqrt(competition)", "ranked": [],
                                "decision": "WIDEN SEARCH", "reason": "no sub-niche clusters found"})
    print("decision2.json — no clusters; WIDEN SEARCH"); raise SystemExit(0)

max_excess = max((c.get("sum_excess", 0) for c in clusters), default=1) or 1
crack_scale = (crack.get("score") or 50) / 100.0
money_scale = (money.get("score") or 50) / 100.0

def geomean(xs):
    xs = [max(x, 0.01) for x in xs]
    return math.exp(sum(math.log(x) for x in xs) / len(xs))

ranked = []
for c in clusters:
    reach = (c.get("sum_excess", 0) / max_excess)                      # 0..1 relative absolute reach
    # replicability = channels whose OUTLIERS land here (audit V9) — the old n_channels counted any
    # channel that merely POSTED on the topic, so 5 posters / 1 winner scored a perfect 1.0.
    n_win_ch = c.get("n_outlier_channels")
    if n_win_ch is None: n_win_ch = c.get("n_channels", 1)             # old subniche.json fallback
    repl = min(n_win_ch / 5.0, 1.0)
    # opportunity: per-cluster newcomer share (small+young channels among this cluster's winners)
    # when available — the old global crack x money constant scaled every cluster equally and
    # therefore never influenced the RANKING (audit V2). money stays global (category-level).
    share = c.get("outlier_newcomer_share")
    opp = money_scale * ((0.3 + 0.7 * share) if share is not None else crack_scale)
    competition = max(c.get("hhi", 1.0), 0.05)                         # concentration (lower = easier)
    raw = geomean([reach, max(opp, 0.05), max(repl, 0.05)]) / math.sqrt(competition)
    ranked.append({
        "anchor": c.get("anchor"), "label": c.get("label"),
        "size": c.get("size"), "n_channels": c.get("n_channels"),
        "n_outlier_channels": n_win_ch,
        "outlier_newcomer_share": share,
        "sum_excess": c.get("sum_excess"), "hhi": c.get("hhi"),
        "browse_vs_search": c.get("browse_vs_search"),
        "reach": round(reach, 3), "replicability": round(repl, 3),
        "opportunity": round(opp, 3), "competition": round(competition, 3),
        "beachhead_score": round(raw * 100, 1),
        "top_titles": c.get("top_titles", [])[:3],
    })

ranked.sort(key=lambda r: -r["beachhead_score"])
for i, r in enumerate(ranked, 1): r["rank"] = i

best = ranked[0]
if best["beachhead_score"] >= 12 and best["n_outlier_channels"] >= 2:
    decision = best["label"] or best["anchor"]
    reason = (f"top beachhead '{decision}' score={best['beachhead_score']} "
              f"(reach={best['reach']}, competition_hhi={best['competition']}, "
              f"{best['n_outlier_channels']} channels with outliers)")
else:
    decision = "WIDEN SEARCH"
    reason = f"best cluster score {best['beachhead_score']} below bar — no clearly winnable beachhead yet"

out = {
    "method": ("geomean(reach,opportunity,replicability)/sqrt(competition); repl = channels with OUTLIERS "
               "in cluster; opportunity = money(global) x per-cluster newcomer share (fallback: global crack)"),
    "crack_scale": round(crack_scale, 2), "money_scale": round(money_scale, 2),
    "ranked": ranked, "decision": decision, "reason": reason,
}
jsave(p("decision2.json"), out)
print(f"decision2.json — beachhead: {decision}")
for r in ranked[:8]:
    print(f"  #{r['rank']} {(r['label'] or r['anchor'])[:24]:24} score={r['beachhead_score']:>5} "
          f"reach={r['reach']} comp={r['competition']} ch={r['n_channels']}")
