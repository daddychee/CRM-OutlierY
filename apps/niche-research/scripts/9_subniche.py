"""STEP 9 [PY] — SUB-NICHE clustering: split the niche into enterable sub-territories.
Usage: python3 9_subniche.py [workdir]   Reads videos.json, analysis.json -> subniche.json

Deterministic clustering (LLM only NAMES clusters later, in S9b): each valid video is anchored to the
highest-LIFT keyword/phrase it contains (lift = over-indexes in outliers, from S3). Clusters = those
anchors. Per cluster we emit the numbers the beachhead scorer (S10) and the namer (S9b) need:
  size, n_channels, HHI (intra-cluster view concentration), sum_excess, median_ox,
  browse_vs_search (share of search-intent titles: how/what/why/best/guide/tutorial…).
`label` is left null for the LLM.
"""
import sys, json, os, re, statistics
from collections import defaultdict
from _common import compute_outliers, jsave, winners, compute_newcomers, get_scan_time, BASE_STOP

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)

MAX_CLUSTERS = 20
MIN_CLUSTER = 3            # drop anchors with fewer than this many videos

now = get_scan_time(WORK)                    # pinned scan time (V12)
videos = json.load(open(p("videos.json"), encoding="utf-8"))
analysis = json.load(open(p("analysis.json"), encoding="utf-8")) if os.path.exists(p("analysis.json")) else {}
chinfo = json.load(open(p("channels.json"), encoding="utf-8")) if os.path.exists(p("channels.json")) else {}
compute_outliers(videos, now)

# ONE winner definition for every stage (V7): valid primary >=3x + early-confirmed fresh
win_ids = {x["videoId"] for x in winners(videos)}
# global newcomer set (small AND young among outlier channels) -> per-cluster share feeds the
# beachhead "opportunity" factor in S10 (audit V2: the old global constant didn't rank anything)
_newc, _ = compute_newcomers({x["channelId"] for x in winners(videos)}, chinfo, now) if chinfo else (set(), 0)

# topic anchors must be CONTENT words: reject seeds containing base or corpus-dynamic stopwords
# ("the truth", "cách để"...) — audit V5
STOPSET = BASE_STOP | set(analysis.get("stop_dynamic", []))
def content_seed(term): return all(w not in STOPSET for w in term.split())

# seed anchors: lift phrases (bigrams first, higher priority) then lift unigrams, ranked by lift.
# FALLBACK: when lift seeds are sparse (small/quiet niche), anchor on CORE keywords that appear
# across >=2 channels so the niche still gets carved into real sub-territories.
seeds = []
for x in analysis.get("lift_bigrams", []):
    if content_seed(x["key"]): seeds.append((x["key"], 100 + x.get("lift", 0), 2))
for x in analysis.get("lift_unigrams", []):
    if content_seed(x["key"]): seeds.append((x["key"], 100 + x.get("lift", 0), 1))
if len({t for t, *_ in seeds}) < 5:
    # fallback score is capped BELOW 100 so it can never outrank a lift seed (lift seeds start at
    # 100+lift; a fallback keyword covering >100 channels would otherwise silently win best-match)
    for x in analysis.get("bigrams", []):
        if x.get("channels", 0) >= 2 and content_seed(x["key"]): seeds.append((x["key"], min(x.get("channels", 0), 99), 2))
    for x in analysis.get("unigrams", []):
        if x.get("channels", 0) >= 2 and content_seed(x["key"]): seeds.append((x["key"], min(x.get("channels", 0), 99), 1))
# de-dup, keep the strongest score per term; sort phrases-before-unigrams then by score desc
# Also track whether the seed was a lift seed (original) or fallback (core keyword) so each
# cluster in subniche.json carries a "source" field — the LLM namer + decision2 scorer can then
# trust lift-based clusters more than fallback clusters.
lift_seeds = set()
for x in analysis.get("lift_bigrams", []): lift_seeds.add(x["key"])
for x in analysis.get("lift_unigrams", []): lift_seeds.add(x["key"])
best = {}
for term, sc, ln in seeds:
    if term not in best or sc > best[term][0]: best[term] = (sc, ln)
seed_list = sorted(best.items(), key=lambda kv: (-kv[1][1], -kv[1][0]))   # phrases first, then score
SEARCH = re.compile(r"\b(how|what|why|when|which|who|best|top|guide|tutorial|explained|vs|review|"
                    r"cách|tại sao|là gì|hướng dẫn)\b", re.I)

def contains(title, term):
    return re.search(r"\b" + re.escape(term) + r"\b", (title or "").lower()) is not None

pool = [x for x in videos if x.get("scope") != "legacy"]      # recent universe
assigned = {}
clusters = defaultdict(list)
# BEST-MATCH assignment: instead of first-match (which biases toward phrases that happen to be
# earlier in seed_list), pick the seed with the highest lift score that matches the title.
# This ensures a video about "quantum computing" goes to the "quantum" cluster (lift=5.2) not
# "the truth" (lift=1.1, connector) just because "the truth" appears first alphabetically.
for x in pool:
    t = (x.get("title") or "").lower()
    best_term = None; best_score = -1
    for term, (sc, _) in seed_list:
        if contains(t, term) and sc > best_score:
            best_term = term; best_score = sc
    if best_term:
        clusters[best_term].append(x); assigned[x["videoId"]] = best_term

rows = []
for term, vids in clusters.items():
    if len(vids) < MIN_CLUSTER: continue
    chans = defaultdict(int)
    for x in vids: chans[x["channelId"]] += x.get("viewCount", 0)
    tot = sum(chans.values()) or 1
    hhi = round(sum((v / tot) ** 2 for v in chans.values()), 4)
    outliers = [x for x in vids if x["videoId"] in win_ids]   # shared winner rule (V7)
    ochans = {x["channelId"] for x in outliers}
    sum_excess = sum(max(x.get("excess", 0), 0) for x in outliers)
    med_ox = round(statistics.median([x.get("ox", 0) for x in vids]), 2)
    search = sum(1 for x in vids if SEARCH.search(x.get("title") or ""))
    browse_vs_search = round(1 - search / len(vids), 2)     # 1.0 = all browse, 0.0 = all search
    examples = sorted(outliers, key=lambda x: -x.get("excess", 0))[:4]
    rows.append({
        "anchor": term, "label": None,                     # <- LLM (S9b) fills label + intent read
        "source": "lift" if term in lift_seeds else "fallback",  # signal quality: lift-seeds = outlier-correlated
        "size": len(vids), "n_channels": len(chans),
        "hhi": hhi, "sum_excess": int(sum_excess),
        "n_outliers": len(outliers), "median_ox": med_ox,
        # channels whose OUTLIERS land in this cluster — the real replicability base for S10 (V9)
        "n_outlier_channels": len(ochans),
        # share of those channels that are newcomers (small AND young) — per-cluster opportunity (V2)
        "outlier_newcomer_share": (round(len(ochans & _newc) / len(ochans), 2) if (ochans and chinfo) else None),
        "browse_vs_search": browse_vs_search,
        "top_titles": [x["title"][:80] for x in examples],
        "example_channels": list({x["channelTitle"] for x in examples})[:4],
    })

rows.sort(key=lambda r: -r["sum_excess"])
rows = rows[:MAX_CLUSTERS]

out = {
    "generated": now.isoformat(),
    "method": "lift-anchor assignment; per-cluster HHI/Σexcess/intent; labels set by LLM (S9b)",
    "n_clusters": len(rows), "n_assigned": len(assigned), "n_pool": len(pool),
    "clusters": rows,
}
jsave(p("subniche.json"), out)
print(f"subniche.json — {len(rows)} clusters from {len(assigned)}/{len(pool)} videos anchored")
for r in rows[:12]:
    print(f"  {r['anchor'][:22]:22} size={r['size']:>3} ch={r['n_channels']:>2} "
          f"Σexc={r['sum_excess']:>11,} medOX={r['median_ox']:>4} b/s={r['browse_vs_search']}")
