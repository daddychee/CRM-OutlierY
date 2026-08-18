"""STEP 6 [PY] — MONETIZATION heuristic: how much is a view worth in this niche?
Usage: python3 6_monetization.py [workdir]   Reads videos.json, analysis.json -> monetization.json

Deterministic heuristic (clearly labelled as a heuristic — NOT measured ad revenue):
  rpm_band     est. USD RPM range, from the niche CATEGORY inferred by keyword voting over titles+tags
               against a small category->RPM table (industry ballparks).
  sponsor_density  share of videos whose title/tags carry sponsor markers (code/promo/sponsor/link…).
  verdict      HIGH / MEDIUM / LOW  (feeds the Decision-1 Monetization pillar; can override a weak niche).

Honest limits: real RPM depends on audience geography, season, and format; this is a category ballpark.
Sponsor markers live mostly in descriptions (not fetched) so sponsor_density is a floor, not the truth.
"""
import sys, json, os, re
from collections import Counter
from _common import jsave, parse_duration, SHORT_MAX_SEC, shorts_gate_on

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return os.path.join(WORK, f)

# category -> (rpm_low, rpm_high, band) — rough industry ballparks (USD, long-form)
CATEGORY_RPM = {
    "finance":    (12, 40, "HIGH"),
    "business":   (10, 30, "HIGH"),
    "tech":       (6, 20, "HIGH"),
    "software":   (8, 22, "HIGH"),
    "education":  (5, 15, "MEDIUM"),
    "health":     (6, 18, "MEDIUM"),
    "science":    (4, 12, "MEDIUM"),
    "diy":        (4, 12, "MEDIUM"),
    "food":       (3, 9, "MEDIUM"),
    "travel":     (3, 10, "MEDIUM"),
    "lifestyle":  (2, 7, "LOW"),
    "gaming":     (2, 6, "LOW"),
    "entertainment": (1.5, 5, "LOW"),
    "music":      (1, 4, "LOW"),
    "kids":       (1, 4, "LOW"),
    "automotive": (4, 12, "MEDIUM"),
    "realestate": (8, 25, "HIGH"),
    "beauty":     (3, 10, "MEDIUM"),
    "fitness":    (5, 15, "MEDIUM"),
    "cooking":    (3, 9, "MEDIUM"),
}
# cue PHRASES per category, comma-separated. Matched as whole phrases with word boundaries —
# splitting on spaces broke Vietnamese multi-syllable terms ("đầu tư" -> "đầu","tư" matched noise)
# and multi-word English ("passive income", "real estate") — audit V14b.
CUES = {
    "finance":  "money, invest, investing, stock, stocks, crypto, bitcoin, trading, finance, dividend, passive income, wealth, tài chính, đầu tư, chứng khoán",
    "business": "business, startup, entrepreneur, marketing, sales, ecommerce, dropshipping, saas, revenue, kinh doanh, khởi nghiệp",
    "tech":     "tech, iphone, android, laptop, gadget, pc, gpu, cpu, smartphone, công nghệ, điện thoại",
    "software": "code, coding, python, javascript, programming, developer, software, app, ai, machine learning, lập trình",
    "education":"learn, course, tutorial, lesson, study, exam, education, guide, how to, khóa học, bài học",
    "health":   "health, diet, weight, nutrition, sức khỏe, giảm cân, dinh dưỡng",
    "science":  "science, physics, space, universe, quantum, biology, chemistry, experiment, khoa học, vũ trụ",
    "diy":      "diy, build, craft, woodworking, repair, fix, tự làm",
    "food":     "recipe, cooking, food, kitchen, bake, meal, chef, nấu ăn, công thức, món ăn",
    "travel":   "travel, trip, destination, tour, flight, hotel, du lịch",
    "lifestyle":"vlog, daily life, routine, minimalism, productivity, motivation, đời sống",
    "gaming":   "game, gaming, gameplay, minecraft, fortnite, roblox, chơi game",
    "entertainment":"funny, reaction, prank, challenge, drama, celebrity, giải trí, hài hước, thử thách",
    "music":    "music, song, cover, remix, beat, lyrics, guitar, piano, bài hát, ca sĩ, âm nhạc",
    "kids":     "kids, cartoon, nursery, toy, trẻ em, hoạt hình, đồ chơi",
    "automotive":"car review, motorcycle, ô tô, xe máy, lái xe, siêu xe",
    "realestate":"real estate, property, apartment, rent, nhà đất, bất động sản, căn hộ",
    "beauty":    "makeup, skincare, beauty, cosmetic, nails, trang điểm, dưỡng da, mỹ phẩm",
    "fitness":   "workout, gym, fitness, training, exercise, bodybuilding, tập luyện, thể hình",
    "cooking":   "recipe, cooking, kitchen, bake, chef, nấu ăn, món ăn, vào bếp",
}
# word-boundary phrase patterns (lookarounds instead of \b so Unicode letters bound correctly)
CUE_PATS = {c: [re.compile(r"(?<!\w)" + re.escape(ph.strip().lower()) + r"(?!\w)")
                for ph in s.split(",") if ph.strip()] for c, s in CUES.items()}
SPONSOR = re.compile(r"\b(sponsor|sponsored|promo|promo\s?code|coupon|discount|use\s?code|"
                     r"link\s?in\s?bio|affiliate|nordvpn|surfshark|honey|skillshare|brilliant|betterhelp|"
                     r"tài\s?trợ|mã\s?giảm|mã\s?khuyến\s?mãi|giảm\s?giá|đăng\s?ký\s?qua\s?link|"
                     r"nhận\s?giảm\s?giá)\b", re.I)

videos = json.load(open(p("videos.json"), encoding="utf-8"))
# shorts gate (this script doesn't call compute_outliers, so it filters on its own)
if shorts_gate_on(WORK):
    videos = [x for x in videos
              if (lambda s: s is None or s > SHORT_MAX_SEC)(parse_duration(x.get("duration")))]

# --- category voting over titles + tags (each phrase counted once per video) ---
votes = Counter()
for x in videos:
    blob = ((x.get("title") or "") + " " + " ".join(x.get("tags") or [])).lower()
    for c, pats in CUE_PATS.items():
        hit = sum(1 for pt in pats if pt.search(blob))
        if hit: votes[c] += hit
top = votes.most_common(3)
if top:
    category = top[0][0]
    total = sum(votes.values()) or 1
    confidence = round(top[0][1] / total, 2)
else:
    category, confidence = "entertainment", 0.0   # unknown -> assume low

rpm_low, rpm_high, band = CATEGORY_RPM.get(category, (1.5, 5, "LOW"))

# --- sponsor density (floor: only title/tags visible) ---
sp = 0
for x in videos:
    blob = (x.get("title") or "") + " " + " ".join(x.get("tags") or [])
    if SPONSOR.search(blob): sp += 1
sponsor_density = round(sp / len(videos), 3) if videos else 0.0

# a sponsor-heavy niche upgrades a low ad-RPM band (creators clearly earn off-platform)
verdict = band
if band == "LOW" and sponsor_density >= 0.15: verdict = "MEDIUM"
if band == "MEDIUM" and sponsor_density >= 0.30: verdict = "HIGH"

# 0..100 pillar score
band_base = {"HIGH": 85, "MEDIUM": 55, "LOW": 25}[band]
score = min(100, round(band_base + 30 * sponsor_density))

out = {
    "method": "category keyword-vote -> RPM table (heuristic) + sponsor-marker density",
    "category": category, "category_confidence": confidence,
    "category_runners_up": [c for c, _ in top[1:]],
    "rpm_band_usd": [rpm_low, rpm_high], "rpm_label": band,
    "sponsor_density": sponsor_density,
    "score": score, "verdict": verdict,
    "note": "HEURISTIC ballpark, not measured revenue. RPM varies by geo/season/format; sponsor_density is a floor (descriptions not fetched).",
}
jsave(p("monetization.json"), out)
print(f"monetization.json — category={category}({confidence}) rpm={rpm_low}-{rpm_high} band={band} "
      f"sponsor_density={sponsor_density} verdict={verdict} score={score}")
