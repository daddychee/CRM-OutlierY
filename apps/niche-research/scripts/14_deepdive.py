"""STEP 14 [PY] — DEEP-DIVE a chosen sub-niche: pick the videos worth studying for DNA.
Usage: python3 14_deepdive.py [workdir] [anchor_or_label]
       (no anchor -> uses the #1 beachhead from decision2.json; else the strongest outliers overall)

Reads videos.json (+ analysis.json, subniche.json, decision2.json). Writes:
  00-danh-sach-video-<slug>.md   URL list VALIDATED BY OX (title · OX · excess) — the S15 input
  deepdive_<slug>.json           per-sub-niche keywords (3 tiers) + tags + content_outliers

Only valid outliers are selected — S15 spends transcript credits, so we never fetch a dud video.
"""
import sys, os, re, json, statistics
from collections import Counter, defaultdict
from _common import compute_outliers, jsave, winners, get_scan_time

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
WANT = sys.argv[2] if len(sys.argv) > 2 else None
def p(f): return os.path.join(WORK, f)
def load(f, d=None): return json.load(open(p(f), encoding="utf-8")) if os.path.exists(p(f)) else d

MAX_VIDEOS = 30            # cap the DNA study set (credits + focus)
now = get_scan_time(WORK)                    # pinned scan time (V12)
videos = json.load(open(p("videos.json"), encoding="utf-8"))
compute_outliers(videos, now)
subniche = load("subniche.json", {"clusters": []})
d2 = load("decision2.json", {})

# choose the anchor: explicit arg > top beachhead > None (overall)
anchor = WANT
if not anchor and d2.get("ranked"):
    anchor = d2["ranked"][0].get("anchor")
label = anchor or "top-outliers"

def contains(title, term):
    return re.search(r"\b" + re.escape(term.lower()) + r"\b", (title or "").lower()) is not None

# S15 spends 1 transcript credit per video — only the shared winner set qualifies (valid primary
# >=3x + early-confirmed fresh; V7): never a fresh video whose OX is just young-shape noise.
valid = winners(videos)
if anchor:
    pool = [x for x in valid if contains(x["title"], anchor)]
    if not pool:
        # maybe the arg was a LABEL from the S9b namer — map it back to its anchor term (audit V24)
        low = anchor.lower()
        cand = next((c for c in subniche.get("clusters", [])
                     if (c.get("label") or "").lower() == low or (c.get("label") and low in c["label"].lower())), None)
        if cand and cand.get("anchor"):
            print(f"note: '{anchor}' matched a cluster LABEL -> using its anchor term '{cand['anchor']}'")
            anchor = cand["anchor"]; label = anchor
            pool = [x for x in valid if contains(x["title"], anchor)]
    if not pool:
        print(f"WARNING: anchor '{anchor}' matched NO valid outlier — falling back to the TOP OUTLIERS "
              f"of the WHOLE niche (not the requested sub-niche!)")
        pool = valid; label = "top-outliers"
else:
    pool = valid
pool.sort(key=lambda x: -x.get("excess", 0))
picked = pool[:MAX_VIDEOS]

slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "sub"

# --- keyword tiers from the picked set (titles + tags) ---
from _common import tokenize as toks     # shared stop-list (V5)
uni = Counter(); big = Counter(); tags = Counter()
for x in picked:
    ts = toks(x["title"])
    uni.update(set(ts))
    big.update({" ".join(ts[i:i+2]) for i in range(len(ts)-1)})
    for tg in (x.get("tags") or []): tags[tg.lower()] += 1

deepdive = {
    "sub_niche": label, "slug": slug, "n_videos": len(picked),
    "keywords_tier1_titlecore": [w for w, _ in uni.most_common(25)],
    "keywords_tier2_phrases": [w for w, c in big.most_common(20) if c >= 2],
    "keywords_tier3_tags": [t for t, _ in tags.most_common(30)],
    "content_outliers": [{"videoId": x["videoId"], "title": x["title"], "channel": x["channelTitle"],
                          "ox": x["ox"], "excess": x["excess"], "views": x["viewCount"],
                          "url": f"https://youtu.be/{x['videoId']}"} for x in picked],
}
jsave(p(f"deepdive_{slug}.json"), deepdive)

# --- 00-danh-sach-video markdown (the S15 input) ---
lines = [f"# Danh sách video deep-dive — {label}", "",
         f"{len(picked)} video (valid outliers, OX>=3, sorted by excess). Nguồn cho DNA (S15/S16).", ""]
for i, x in enumerate(picked, 1):
    lines.append(f"{i:>2}. https://youtu.be/{x['videoId']}  — OX {x['ox']} · excess {x['excess']:,} · {x['title'][:70]}")
open(p(f"00-danh-sach-video-{slug}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

print(f"deepdive_{slug}.json + 00-danh-sach-video-{slug}.md — {len(picked)} videos for sub-niche '{label}'")
