"""Module 3 — Niche Format Profile: dán URL đối thủ trong niche → format chung của niche.

Khác Module 1 (Profile kênh = phong cách Description của MỘT kênh mình sở hữu), module này học
**format của cả niche** từ nhiều kênh/video đối thủ, và phủ cả 3 trụ cột + luật riêng:
  title (pattern) · description (skeleton) · tags (quy ước) · rules (must/avoid)

Nguyên tắc:
- Học từ **OUTLIER**, không phải mọi video: mỗi kênh lấy video có `views ≥ 2× median` (kênh ≥ 10
  video mới đủ mẫu để tính median; ít hơn thì lấy hết + gắn cờ). Video dán lẻ = user đã chọn tay
  → luôn giữ. Bám Outlier Engine trong CLAUDE.md.
- **Python đo** (đếm ký tự/từ, anchor lặp, tag phủ, tỉ lệ broad/long-tail, hashtag) —
  **LLM hiểu** (pattern title, skeleton description, đề xuất luật). LLM KHÔNG bịa số: mọi con số
  trong profile do Python tính.
- Một lần extract = **một** Format Profile (user đặt tên); 1 niche chứa nhiều format.
- `resolve()` ghép Format niche với Profile kênh theo luật **KÊNH ĐÈ NICHE**.
"""
from __future__ import annotations

import json
import re
import shlex
import statistics
from collections import Counter

from . import common, harvest, library, llm, profile

OUTLIER_RATIO = 2.0                 # views ≥ 2× median (CLAUDE.md)
MIN_VIDEOS_FOR_MEDIAN = 10          # kênh ít hơn → không đủ mẫu, lấy hết
BASE_TAG_COVERAGE = 0.4             # tag xuất hiện ở ≥40% outlier = tag nền của niche

_SYS_TITLE = (
    "Bạn phân tích PATTERN TIÊU ĐỀ của một niche YouTube. Đầu vào là title của các video OUTLIER "
    "(view vượt trội) trong niche + số liệu đã đo sẵn. Tìm công thức lặp lại, KHÔNG kể lể từng video. "
    "Trả JSON: {\"patterns\":[{\"pattern\":<công thức dạng slot, vd 'The [superlative] [entity] in [place]'>,"
    "\"example\":<title CÓ THẬT trong danh sách>,\"desire\":<mass-desire Schwartz đang khai thác>,"
    "\"technique\":<FAB|PAS|Personification|Identification|Redefinition|Intensification>,"
    "\"support\":<số title trong danh sách khớp pattern này>}],"
    "\"note\":<đặc điểm chung đáng lưu ý của title niche này>,"
    "\"rules\":{\"must\":[<điều title niche này LUÔN làm>],\"avoid\":[<điều nên tránh: cấm kị của niche, "
    "rủi ro policy, kiểu giật tít không hợp>]}}. "
    "Chỉ đưa pattern có ÍT NHẤT 2 title hậu thuẫn — không đủ bằng chứng thì bỏ. "
    "example PHẢI copy nguyên văn từ danh sách, cấm bịa. "
    "Phần note/rules viết TIẾNG VIỆT; pattern/example giữ nguyên ngôn ngữ gốc của title."
)
_SYS_DESC = (
    "Bạn phân tích FORMAT DESCRIPTION chung của một niche YouTube (nhiều kênh khác nhau). "
    "Trả JSON: {\"skeleton\":[block theo thứ tự phổ biến, chọn từ HOOK|SUMMARY|CHAPTERS|CTA|LINKS|HASHTAG],"
    "\"blocks\":[{\"block\":<tên>,\"chars\":<ước lượng số ký tự>,\"desc\":<block này thường viết gì>}],"
    "\"note\":<format niche này khác standard ở đâu>}. "
    "Mô tả viết TIẾNG VIỆT; ví dụ nội dung giữ nguyên ngôn ngữ gốc."
)

_SYS_PACKAGE = (
    "Bạn phân tích cách các kênh đối thủ trong một niche YouTube ĐÓNG GÓI KÊNH của họ "
    "(phần cấp KÊNH, không phải từng video): mô tả kênh (About), từ khoá kênh, cách bày trang chủ "
    "(các mục/playlist), nhịp đăng. Đầu vào là dữ liệu THẬT đã đo sẵn. "
    "Trả JSON: {"
    "\"about_pattern\":<công thức mô tả kênh: mở đầu bằng gì, nói gì, dài bao nhiêu, có CTA/link/lịch đăng không>,"
    "\"keywords_guide\":<cách họ chọn từ khoá kênh: bao nhiêu, rộng hay hẹp, có tên thương hiệu không>,"
    "\"homepage_guide\":<cách bày trang chủ: bao nhiêu mục, playlist đặt tên kiểu gì, có trailer không>,"
    "\"cadence_note\":<nhận xét nhịp đăng>,"
    "\"checklist\":[<3-7 việc cụ thể cần làm khi dựng kênh mới trong niche này>]}. "
    "Viết TIẾNG VIỆT; ví dụ trích dẫn giữ nguyên ngôn ngữ gốc. "
    "CẤM bịa số — chỉ dùng số có trong input.\n"
    # Không chốt độ dài thì model viết cả bài có bullet/markdown vào trong string JSON,
    # chạm max_tokens và JSON bị cắt mất dấu đóng ⇒ hỏng cả lần extract. Đây là lỗi THẬT
    # đã gặp 2026-07-28, không phải phòng xa.
    "ĐỘ DÀI BẮT BUỘC: mỗi trường mô tả TỐI ĐA 2 câu (~200 ký tự). Mỗi mục checklist 1 dòng ngắn. "
    "Viết văn xuôi liền mạch — CẤM markdown, CẤM xuống dòng, CẤM gạch đầu dòng hay đánh số trong giá trị."
)
_SYS_COMMUNITY = (
    "Bạn phân tích FORMAT BÀI POST CỘNG ĐỒNG (YouTube Community) của đối thủ trong 1 niche. "
    "Đầu vào là vài bài post user tự copy về. Trả JSON: {"
    "\"post_pattern\":<cấu trúc bài post điển hình>,\"length\":<độ dài thường thấy>,"
    "\"tone\":<giọng điệu>,\"cta\":<cách kêu gọi tương tác>,"
    "\"types\":[<các dạng post nhận ra: hỏi ý kiến, poll, hé lộ video mới, hậu trường...>],"
    "\"note\":<lưu ý khi bắt chước>}. Viết TIẾNG VIỆT, trích dẫn giữ nguyên gốc."
)

_WORD_RE = re.compile(r"[A-Za-zÀ-ỹ']{4,}")
_STOP = {"this", "that", "with", "from", "your", "you", "the", "and", "for", "what", "why", "how",
         "will", "when", "into", "than", "then", "they", "them", "their", "there", "here", "have",
         "has", "was", "were", "been", "just", "like", "about", "most", "more", "very", "over"}


# ── nguồn: phân loại URL kênh vs video ──
def parse_sources(text: str) -> dict:
    """Khối text nhiều dòng → {channels:[str], videos:[id]}. Dòng nào không nhận ra → bỏ."""
    channels, videos, unknown = [], [], []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        vid = common.extract_video_id(s)
        if vid and "/channel/" not in s:
            if vid not in videos:
                videos.append(vid)
        elif re.search(r"/channel/|@[\w.-]+|/user/|/c/|^UC[\w-]{20,}", s):
            if s not in channels:
                channels.append(s)
        else:
            unknown.append(s)
    return {"channels": channels, "videos": videos, "unknown": unknown}


def outliers_of(vids: list[dict]) -> tuple[list[dict], bool]:
    """Video của 1 kênh → (outlier, đủ_mẫu). Outlier = views ≥ 2× median."""
    if len(vids) < MIN_VIDEOS_FOR_MEDIAN:
        return vids, False                                  # ít video → không đủ mẫu tính median
    med = statistics.median([v["views"] for v in vids]) or 0
    out = [v for v in vids if v["views"] >= OUTLIER_RATIO * med]
    return (out or vids), True


def fetch_competitor(url: str, keys: list[str], per_channel: int = 30,
                     status: dict | None = None) -> dict:
    """1 URL (kênh / @handle / hoặc 1 video của kênh) → hồ sơ 1 ĐỐI THỦ.

    Gồm: package cấp kênh (tag kênh, About, cách bày trang chủ, stats) + video OUTLIER của kênh đó.
    Quota ~4-5 unit: channels(1) + channelSections(1) + playlistItems(1-2) + videos(1).
    Dán tên kênh trần sẽ tốn thêm 100 unit vì phải gọi `search` — luôn ưu tiên /channel/ hoặc @handle.
    """
    st = status if status is not None else {}
    st["step"] = "tìm kênh…"
    ch = common.resolve_channel_id(url, keys)
    if not ch:
        raise RuntimeError(f"Không nhận ra kênh từ: {url[:60]}")
    st["step"] = "đọc package kênh…"
    pkg = channel_package(ch, keys)
    st["step"] = f"lấy video của {pkg.get('title') or ch}…"
    ids = common.channel_video_ids(ch, keys, limit=per_channel)
    vids = []
    if ids:
        for it in common.fetch_videos(ids, keys, parts="snippet,statistics"):
            sn = it.get("snippet", {})
            _d = sn.get("description", "") or ""
            vids.append({"id": it.get("id"), "title": sn.get("title", ""),
                         "desc": _d[:600],
                         # ĐUÔI description: khối link/CTA/hashtag gần như luôn nằm ở cuối,
                         # cắt 600 ký tự đầu là mất sạch → cta.py học nhầm chỗ.
                         "desc_tail": _d[-700:] if len(_d) > 600 else "",
                         "tags": sn.get("tags", []) or [],
                         "views": int(it.get("statistics", {}).get("viewCount", 0) or 0),
                         "published_at": sn.get("publishedAt", "")})
    outs, enough = outliers_of(vids) if vids else ([], False)
    return {"channel_id": ch, "url": url.strip(), "title": pkg.get("title", ""),
            "handle": pkg.get("handle", ""), "added_at": library.now_iso(),
            "package": pkg, "cadence": upload_cadence([v["published_at"] for v in vids]),
            "n_videos": len(vids), "n_outliers": len(outs), "enough_sample": enough,
            "outliers": sorted(outs, key=lambda v: -v["views"])[:25]}


# ── PACKAGE CẤP KÊNH (cái mà video-level không thấy được) ──
def split_keywords(raw: str) -> list[str]:
    """`brandingSettings.channel.keywords` là chuỗi ngăn cách bằng KHOẢNG TRẮNG, cụm nhiều từ bọc
    trong dấu nháy kép (vd: Science space "black hole"). shlex tách đúng kiểu đó."""
    try:
        return [k.strip() for k in shlex.split(raw or "") if k.strip()]
    except ValueError:                                     # nháy lệch → tách thô
        return [k for k in (raw or "").replace('"', " ").split() if k]


def channel_package(ch_id: str, keys: list[str]) -> dict:
    """Package cấp KÊNH: tag kênh · description kênh · cách bày trang chủ · stats. ~2 unit.

    Bài post cộng đồng KHÔNG có trong YouTube Data API v3 (đã verify: /posts và /communityPosts
    trả 404, activities.list chỉ có upload+playlistItem) → phần đó user dán tay.
    """
    d = common.yt_get("channels",
                      {"part": "snippet,brandingSettings,statistics,topicDetails", "id": ch_id}, keys)
    items = d.get("items") or []
    if not items:
        raise RuntimeError(f"Không đọc được kênh {ch_id}")
    it = items[0]
    sn, br, st = it.get("snippet", {}), it.get("brandingSettings", {}), it.get("statistics", {})
    sections = []
    try:                                                   # kênh ẩn mục trang chủ → bỏ qua, không chặn
        sd = common.yt_get("channelSections", {"part": "snippet,contentDetails", "channelId": ch_id}, keys)
        for x in sd.get("items", []):
            xs = x.get("snippet", {})
            sections.append({"type": xs.get("type", ""), "title": xs.get("title", ""),
                             "playlists": (x.get("contentDetails") or {}).get("playlists", [])})
    except Exception:                                      # noqa: BLE001
        pass
    desc = sn.get("description", "") or ""
    return {
        "title": sn.get("title", ""), "handle": sn.get("customUrl", ""),
        "country": sn.get("country", ""), "published_at": sn.get("publishedAt", ""),
        "description": desc, "description_chars": len(desc),
        "keywords": split_keywords((br.get("channel") or {}).get("keywords", "")),
        "trailer": (br.get("channel") or {}).get("unsubscribedTrailer", ""),
        "subs": int(st.get("subscriberCount", 0) or 0),
        "views": int(st.get("viewCount", 0) or 0),
        "video_count": int(st.get("videoCount", 0) or 0),
        "topics": [t.rsplit("/", 1)[-1].replace("_", " ")
                   for t in (it.get("topicDetails", {}) or {}).get("topicCategories", [])],
        "sections": sections, "n_sections": len(sections),
    }


def upload_cadence(dates: list[str]) -> dict:
    """Nhịp đăng: số ngày trung vị giữa 2 video liên tiếp. Thuần Python, từ publishedAt có sẵn."""
    from datetime import datetime
    ds = sorted(d for d in dates if d)
    if len(ds) < 3:
        return {"median_days": None, "n": len(ds)}
    ts = [datetime.fromisoformat(d.replace("Z", "+00:00")) for d in ds]
    gaps = [(b - a).total_seconds() / 86400 for a, b in zip(ts, ts[1:])]
    return {"median_days": round(statistics.median(gaps), 1), "n": len(ds)}


def aggregate_package(comps: list[dict]) -> dict:
    """Gộp package của N đối thủ → số liệu chung của niche. Thuần Python (đếm được)."""
    pkgs = [c.get("package") or {} for c in comps]
    pkgs = [p for p in pkgs if p]
    if not pkgs:
        return {}
    kw = Counter(k.lower() for p in pkgs for k in (p.get("keywords") or []))
    n = len(pkgs)
    # 1 Format = 1 đối thủ (mặc định từ 2026-07-29) → "dùng chung" vô nghĩa, lấy thẳng từ khoá
    # của chính kênh đó. Ngưỡng max(2,…) bên dưới sẽ trả rỗng và board hiện "chưa có tag kênh".
    common_kw = ([k for k, _ in kw.most_common(40)] if n == 1
                 else [k for k, c in kw.most_common(20) if c >= max(2, n * 0.4)])
    dlens = [p.get("description_chars", 0) for p in pkgs]
    sect = Counter(s.get("type", "") for p in pkgs for s in (p.get("sections") or []))
    cad = [c.get("cadence", {}).get("median_days") for c in comps]
    cad = [x for x in cad if x]
    return {
        "n_channels": n,
        "keywords_common": common_kw,
        "keywords_all": [k for k, _ in kw.most_common(40)],
        "keywords_per_channel": round(statistics.mean([len(p.get("keywords") or []) for p in pkgs]), 1),
        "about_chars": {"avg": round(statistics.mean(dlens)) if dlens else 0,
                        "range": [min(dlens), max(dlens)] if dlens else [0, 0]},
        "sections": {"avg": round(statistics.mean([p.get("n_sections", 0) for p in pkgs]), 1),
                     "types": sect.most_common(6)},
        "with_trailer": sum(1 for p in pkgs if p.get("trailer")),
        "subs": {"min": min(p.get("subs", 0) for p in pkgs), "max": max(p.get("subs", 0) for p in pkgs)},
        "cadence_days": round(statistics.median(cad), 1) if cad else None,
    }


def infer_package(agg: dict, samples: list[str]) -> dict:
    """LLM đọc số liệu đã đo + vài mô tả kênh thật → guide đóng gói kênh (tiếng Việt)."""
    if not agg:
        return {}
    user = json.dumps({"measured": agg, "about_samples": [s[:700] for s in samples[:5]]},
                      ensure_ascii=False)
    out = llm.call_json(_SYS_PACKAGE, user, max_tokens=3000, temperature=0.3)
    return out if isinstance(out, dict) else {}


def infer_community(posts: str) -> dict:
    """Bài post cộng đồng user dán tay (API không có endpoint này)."""
    t = (posts or "").strip()
    if len(t) < 40:
        return {}
    out = llm.call_json(_SYS_COMMUNITY, json.dumps({"posts": t[:4000]}, ensure_ascii=False),
                        max_tokens=1200, temperature=0.3)
    return out if isinstance(out, dict) else {}


# ── Python đo ──
def title_stats(vids: list[dict]) -> dict:
    lens = [len(v["title"]) for v in vids if v["title"]]
    words = [len(v["title"].split()) for v in vids if v["title"]]
    cnt: Counter = Counter()
    for v in vids:
        for w in _WORD_RE.findall(v["title"].lower()):
            if w not in _STOP:
                cnt[w] += 1
    return {"chars": {"avg": round(statistics.mean(lens)) if lens else 0,
                      "range": [min(lens), max(lens)] if lens else [0, 0]},
            "words": {"avg": round(statistics.mean(words), 1) if words else 0},
            "anchors": [w for w, n in cnt.most_common(12) if n >= 2]}


def tag_stats(outliers: list[dict], pool: list[dict]) -> dict:
    """Quy ước tag của niche — thuần Python (đếm được → không dùng LLM)."""
    withtag = [v for v in outliers if v["tags"]]
    n = len(withtag)
    base = [r["canonical"] for r in pool if n and r["n_videos"] / n >= BASE_TAG_COVERAGE][:15]
    counts = [len(v["tags"]) for v in withtag]
    broad = sum(1 for r in pool if r["word_len"] <= 1)
    return {"base": base,
            "ratio": {"broad": broad, "longtail": max(0, len(pool) - broad)},
            "avg_count": round(statistics.mean(counts), 1) if counts else 0,
            "range": [min(counts), max(counts)] if counts else [0, 0],
            "videos_with_tag": n, "pool_size": len(pool)}


def desc_stats(descs: list[str]) -> dict:
    lens = [len(d) for d in descs]
    return {"chars": {"avg": round(statistics.mean(lens)) if lens else 0,
                      "range": [min(lens), max(lens)] if lens else [0, 0]},
            "hashtag": profile.hashtag_stats(descs),
            "special_chars": profile.special_chars(descs)}


# ── LLM hiểu ──
def infer_title(outliers: list[dict], stats: dict) -> dict:
    user = json.dumps({"outlier_titles": [{"title": v["title"], "views": v["views"]} for v in outliers[:40]],
                       "measured": stats}, ensure_ascii=False)
    out = llm.call_json(_SYS_TITLE, user, max_tokens=2400, temperature=0.3)
    return out if isinstance(out, dict) else {}


def infer_desc(descs: list[str]) -> dict:
    user = json.dumps({"samples": [d[:600] for d in descs[:6]], "n": len(descs)}, ensure_ascii=False)
    out = llm.call_json(_SYS_DESC, user, max_tokens=1500, temperature=0.2)
    return out if isinstance(out, dict) else {}


def _validate_patterns(pats, titles: list[str]) -> list[dict]:
    """Bỏ pattern bịa example (LLM phải copy nguyên văn title có thật)."""
    have = {t.strip().lower() for t in titles}
    ok = []
    for p in llm.as_list(pats) if not isinstance(pats, list) else pats:
        if not isinstance(p, dict) or not p.get("pattern"):
            continue
        ex = str(p.get("example", "")).strip()
        p["example_verified"] = ex.lower() in have
        if not p["example_verified"]:
            p["example"] = ""                               # không chứng minh được → bỏ example, giữ pattern
        ok.append(p)
    return ok


# ── store ──
def formats_dir(*, create: bool = False):
    d = common.ROOT / "formats"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def all_formats(errors: list | None = None) -> list[dict]:
    """File hỏng vẫn bỏ qua, nhưng PHẢI ghi vào `errors` — biến mất im lặng khỏi board là
    nói dối: user tưởng Format đã bị xoá rồi đi extract lại, tốn quota YouTube."""
    d = formats_dir()
    out = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            fm = common.read_json(f)
        except Exception as e:                              # noqa: BLE001
            if errors is not None:
                errors.append({"kind": "format", "file": f.name, "error": str(e)[:200]})
            continue
        fm["slug"] = f.stem
        out.append(fm)
    return out


def load(slug: str) -> dict | None:
    f = formats_dir() / f"{common.slug(slug)}.json"
    if not f.exists():
        return None
    fm = common.read_json(f)
    fm["slug"] = f.stem
    return fm


def update(slug: str, patch: dict) -> dict:
    """Sửa phần user chỉnh tay: name/niche/lang/rules/note. Không đụng số liệu đã đo.

    `lang` = ngôn ngữ của KÊNH ĐỐI THỦ mà format này học theo (user chốt 2026-08-01, để clone
    kênh sang thứ tiếng khác). Đây KHÔNG phải nhãn trang trí: title/tag được ghép từ CHÍNH CHỮ
    của đối thủ (`titles.trace_blocks`), nên ngôn ngữ của pool là ngôn ngữ bắt buộc của đầu ra.
    Đo thật (0 token): title tiếng Việt soi trên pool tiếng Anh → `cover 0.0`, bịa 14 chữ, LOẠI
    THẲNG. Tức kênh gắn nhầm format khác ngôn ngữ sẽ nhận **0 title**, không phải "kém hơn".
    Vì vậy `lang` ở đây tồn tại để ĐỐI CHIẾU với `lang` của kênh, không phải để hiển thị.
    """
    fm = load(slug)
    if fm is None:
        raise RuntimeError(f"Không thấy format: {slug}")
    for k in ("name", "niche", "note", "community_raw", "lang"):
        if k in patch:
            fm[k] = str(patch[k] or "").strip()
    if "rules" in patch:
        r = patch["rules"] or {}
        fm["rules"] = {"must": [str(x).strip() for x in (r.get("must") or []) if str(x).strip()],
                       "avoid": [str(x).strip() for x in (r.get("avoid") or []) if str(x).strip()]}
    fm["updated"] = library.now_iso()
    fm.pop("slug", None)
    common.write_json(formats_dir(create=True) / f"{common.slug(slug)}.json", fm)
    fm["slug"] = common.slug(slug)
    return fm


# Người ta gõ cùng một thứ tiếng theo nhiều kiểu; gộp vài kiểu PHỔ BIẾN NHẤT để không báo lệch
# oan. CỐ Ý không làm bảng lớn: đoán bừa hai chuỗi lạ là cùng ngôn ngữ thì tệ hơn là chịu thua
# và im lặng (thiếu dữ liệu ≠ đã đối chiếu và khớp).
_LANG_ALIAS = {
    "en": "english", "eng": "english", "tiếng anh": "english", "tieng anh": "english",
    "vi": "vietnamese", "vn": "vietnamese", "tiếng việt": "vietnamese",
    "tieng viet": "vietnamese", "việt": "vietnamese", "viet": "vietnamese",
}


# ── Hệ chữ KHÔNG-LATIN: dứt khoát, chữ Thái không thể là tiếng Anh ───────────────────────
_SCRIPTS = [
    ("Japanese", re.compile(r"[぀-ヿ]")),
    ("Korean", re.compile(r"[가-힯]")),
    ("Chinese", re.compile(r"[一-鿿]")),
    ("Thai", re.compile(r"[฀-๿]")),
    ("Arabic", re.compile(r"[؀-ۿ]")),
    ("Hindi", re.compile(r"[ऀ-ॿ]")),
    ("Russian", re.compile(r"[Ѐ-ӿ]")),
]
# ── Dấu RIÊNG của từng thứ tiếng Latin ──────────────────────────────────────────────────
# BẪY ĐÃ CẮN NGAY LẦN CHẠY ĐẦU trên dữ liệu thật (2026-08-01): mẫu tiếng Việt ban đầu của tôi
# gồm cả `à á è é ì í ò ó ù ú` — mà tiếng Tây Ban Nha dùng `á í ó` đầy. Kết quả: cả 3 format
# tiếng TBN user vừa thêm đều bị gán "Tiếng Việt". Chữ CHUNG thì không phân biệt được gì cả;
# chỉ dấu RIÊNG mới nói lên điều gì.
# `Ạ-ỹ` (Latin Extended Additional) gần như chỉ tiếng Việt dùng; cộng ơ ư đ.
_UNIQ = [
    ("Tiếng Việt", re.compile(r"[Ạ-ỹƠơƯưĐđ]")),
    ("Spanish", re.compile(r"[ñÑ¿¡]")),
    ("Portuguese", re.compile(r"[ãõÃÕ]")),
]
# Từ chức năng — tách các thứ tiếng Latin khi dấu riêng không đủ. Chỉ lấy từ CỰC PHỔ BIẾN
# trong tiêu đề, không phải từ điển.
_STOP = {
    "English": {"the", "of", "in", "and", "is", "a", "to", "on", "with", "for", "why", "what",
                "how", "this", "that", "it", "are", "was", "you", "your", "from", "at", "by",
                "most", "best", "will", "can", "has", "have", "does", "do", "not", "no"},
    "Spanish": {"de", "la", "el", "los", "las", "en", "que", "y", "del", "con", "por", "para",
                "un", "una", "es", "más", "su", "al", "lo", "como", "no", "se", "vida", "mundo"},
    "Portuguese": {"de", "da", "do", "que", "em", "para", "com", "não", "os", "as", "um", "uma",
                   "no", "na", "por", "mais", "se", "é", "dos", "das", "vida", "mundo"},
    "French": {"le", "la", "les", "de", "du", "des", "et", "est", "pour", "dans", "un", "une",
               "au", "aux", "que", "qui", "ce", "sur", "plus", "avec", "vie", "monde"},
    "Indonesian": {"di", "yang", "dan", "ini", "itu", "dengan", "untuk", "dari", "ke", "adalah",
                   "pada", "tidak", "paling", "kehidupan", "dunia", "negara"},
}


def format_text(fmt: dict) -> list[str]:
    """Chữ THẬT của đối thủ trong format — nguồn duy nhất để đoán ngôn ngữ."""
    out = [e.get("title", "") for e in (fmt.get("evidence") or [])]
    out += [p.get("example", "") for p in ((fmt.get("title") or {}).get("patterns") or [])]
    out += (fmt.get("tags") or {}).get("base") or []
    d = (fmt.get("description") or {}).get("example") or ""
    if d:
        out.append(d[:400])
    return [s for s in out if isinstance(s, str) and s.strip()]


def guess_lang(fmt: dict) -> dict:
    """ĐOÁN ngôn ngữ của format từ chữ thật của đối thủ → {lang, why, n}.

    ĐỀ XUẤT, KHÔNG TỰ ĐIỀN. Python đo được tới đâu thì nói tới đó, phần còn lại user chốt —
    đúng ranh giới của dự án. Tự ghi vào `fmt["lang"]` là đóng dấu "đã đối chiếu" cho một
    phỏng đoán, mà chính `lang_mismatch` lại dựa vào field đó để phán 0-title.

    Ba tầng, độ chắc GIẢM DẦN, và phải nói rõ mình đang ở tầng nào:
      1. Hệ chữ không-Latin (kana, hangul, Thái, Cyrillic…) — dứt khoát.
      2. Dấu RIÊNG của một thứ tiếng Latin (Ạ-ỹ của tiếng Việt · ñ¿¡ của TBN · ãõ của BĐN).
      3. Không có dấu riêng → chấm điểm từ chức năng nhiều thứ tiếng, chỉ nhận khi quán quân
         BỎ XA á quân; sát nhau thì TRẢ RỖNG kèm tên hai ứng viên, không bốc thăm hộ user.
    Không LLM, không quota.
    """
    txt = format_text(fmt)
    if not txt:
        return {"lang": "", "why": "format chưa có title/tag nào để đo", "n": 0}
    blob = " ".join(txt)
    for name, rx in _SCRIPTS:
        hits = sum(1 for s in txt if rx.search(s))
        if hits >= max(2, len(txt) // 5):                  # ≥20% mẫu, tối thiểu 2 dòng
            return {"lang": name, "why": f"{hits}/{len(txt)} dòng chữ của đối thủ dùng hệ chữ {name}",
                    "n": hits}
    for name, rx in _UNIQ:
        hits = sum(1 for s in txt if rx.search(s))
        if hits >= max(2, len(txt) // 5):
            return {"lang": name, "why": f"{hits}/{len(txt)} dòng có ký tự chỉ {name} mới dùng",
                    "n": hits}
    words = re.findall(r"[a-zà-öø-ÿ']+", blob.lower())
    if len(words) < 12:
        return {"lang": "", "why": f"chỉ có {len(words)} từ Latin — quá ít để đoán", "n": 0}
    sc = sorted(((sum(1 for w in words if w in st) / len(words), nm)
                 for nm, st in _STOP.items()), reverse=True)
    (r1, n1), (r2, n2) = sc[0], sc[1]
    if r1 < 0.10:
        return {"lang": "", "why": f"không thứ tiếng nào đủ dấu hiệu trong {len(words)} từ "
                                   f"— phải tự khai", "n": 0}
    if r1 < r2 * 1.5:                                      # quán quân không bỏ xa á quân
        return {"lang": "", "why": f"lẫn giữa {n1} và {n2} ({r1*100:.0f}% vs {r2*100:.0f}% "
                                   f"từ chức năng) — phải tự khai", "n": 0}
    return {"lang": n1, "why": f"{round(r1*len(words))}/{len(words)} từ là từ chức năng {n1}",
            "n": round(r1 * len(words))}


def norm_lang(v) -> str:
    s = " ".join(str(v or "").split()).casefold()
    return _LANG_ALIAS.get(s, s)


def lang_mismatch(profile: dict, fmt: dict | None) -> str:
    """'' nếu khớp HOẶC chưa đủ dữ liệu; câu giải thích nếu LỆCH.

    Đây là chốt đắt giá nhất của field `lang`, vì hậu quả không phải "chất lượng kém hơn" mà là
    **0 title**: `titles.score` truy nguyên từng cụm của title mới về pool title đối thủ, nên
    ứng viên viết bằng thứ tiếng khác pool sẽ bị đếm là bịa toàn bộ rồi loại thẳng. Đo thật
    (0 token, pool tiếng Anh): ứng viên tiếng Việt → `cover 0.0`, bịa 14 chữ, `score None`.

    Thiếu một trong hai bên thì TRẢ RỖNG, không đoán — "chưa khai" khác "đã đối chiếu và khớp".
    """
    a, b = norm_lang(profile.get("lang")), norm_lang((fmt or {}).get("lang"))
    if not a or not b or a == b:
        return ""
    return (f"kênh khai {profile.get('lang')!r} nhưng Format học đối thủ {(fmt or {}).get('lang')!r} — "
            f"title/tag ghép từ CHỮ của đối thủ nên chỉ ra được {(fmt or {}).get('lang')}; "
            f"mọi ứng viên đúng {profile.get('lang')} sẽ bị chốt chống bịa loại sạch (0 title)")


def _slug_of(niche: str, name: str) -> str:
    return common.slug(f"{niche}-{name}" if niche else name)


_NAME_URL_RE = re.compile(r"https?://|www\.|youtube\.com|youtu\.be", re.I)


def clean_name(name: str) -> str:
    """Bỏ URL ra khỏi TÊN format — link không bao giờ là tên.

    Ô "Tên format" nằm ngay trên ô "URL đối thủ" nên dán nhầm là chuyện thường. Nhầm một lần thì
    hỏng HAI chỗ, và cả hai đều không sửa được từ giao diện: tên hiện trên thẻ format thành cái
    link dài (không đọc ra kênh nào), và link đi thẳng vào SLUG = tên file
    (`space-httpswwwyoutubecomchannelucmzyhcpukkn96nz1zirs16q-science-channel.json`).
    Cắt theo TỪNG TỪ để "https://… · Science Channel" còn lại đúng "Science Channel";
    chỉ toàn link thì trả rỗng → gọi tự lấy tên kênh đối thủ như khi bỏ trống.
    """
    parts = [p for p in re.split(r"[\s·]+", name or "") if p and not _NAME_URL_RE.search(p)]
    return " ".join(parts).strip(" ·-")


def rebuild(fmt: dict, status: dict | None = None) -> dict:
    """Tính lại toàn bộ phần tổng hợp từ `fmt["competitors"]`. KHÔNG gọi YouTube API.

    Gọi lại mỗi khi thêm/bớt đối thủ. LLM ở nhiệt độ thấp nên llm.py cache — thêm 1 đối thủ
    mà dữ liệu cũ không đổi thì phần lớn call là cache hit.
    """
    st = status if status is not None else {}
    comps = fmt.get("competitors") or []
    outs = [v for c in comps for v in (c.get("outliers") or [])]
    fmt["n_channels"] = len(comps)
    fmt["n_videos"] = sum(c.get("n_videos", 0) for c in comps)
    fmt["n_outliers"] = len(outs)
    fmt["outlier_rule"] = (f"views ≥ {OUTLIER_RATIO:g}× median mỗi kênh (kênh ≥ {MIN_VIDEOS_FOR_MEDIAN} video); "
                           f"{sum(1 for c in comps if c.get('enough_sample'))}/{len(comps)} kênh đủ mẫu")

    st["step"] = "đo số liệu video…"
    vids = [{**v, "description": v.get("desc", "")} for v in outs]
    pool = harvest.build_pool([{**v, "is_main": False} for v in vids]) if vids else []
    tstats = title_stats(vids) if vids else {}
    descs = [v["description"] for v in vids if v["description"].strip()]
    dstats = desc_stats(descs) if descs else {}
    gstats = tag_stats(vids, pool) if vids else {}

    agg = aggregate_package(comps)
    comm_raw = fmt.get("community_raw", "")
    # 4 call này KHÔNG dùng kết quả của nhau (title đọc outlier · description đọc mô tả ·
    # package đọc số liệu cấp kênh · community đọc post user dán) ⇒ chạy SONG SONG.
    # Đo thật: mỗi call GLM-5.2 ~5–14 giây, xếp hàng thì một lần extract 1 kênh mất ~25–30 giây
    # chỉ để ngồi đợi. YouTube API cả kênh chỉ 1 giây — nghẽn nằm hết ở đây, không phải ở quota.
    jobs = {}
    if vids:
        jobs["title"] = lambda: infer_title(vids, tstats)
        if descs:
            jobs["desc"] = lambda: infer_desc(descs)
    jobs["package"] = lambda: infer_package(
        agg, [(c.get("package") or {}).get("description", "") for c in comps])
    if comm_raw:
        jobs["community"] = lambda: infer_community(comm_raw)
    st["step"] = f"phân tích {len(jobs)} phần cùng lúc (title/description/package)…"
    res = llm.gather(jobs)

    # title/description hỏng = hỏng THẬT (đó là nội dung chính của Format) → ném lên.
    for k in ("title", "desc"):
        if k in res and res[k][1] is not None:
            raise res[k][1]
    ai_t = (res.get("title") or ({}, None))[0] or {}
    ai_d = (res.get("desc") or ({}, None))[0] or {}
    # Package/community là phần BỔ SUNG. Đến được đây nghĩa là quota YouTube đã tiêu và 2 call
    # LLM chính (title/description) đã xong — để một call phụ ném lỗi làm hỏng cả lần extract
    # là bắt user trả tiền lại từ đầu. Hỏng thì ghi cờ, giữ nguyên phần đã làm được.
    soft_err: list[str] = []
    ai_p, e_p = res.get("package") or ({}, None)
    if e_p is not None:
        ai_p = {}
        soft_err.append(f"package: {e_p}")
    ai_c, e_c = res.get("community") or ({}, None)
    if e_c is not None:
        ai_c = {}
        soft_err.append(f"community: {e_c}")
    ai_p, ai_c = ai_p or {}, ai_c or {}
    fmt["soft_errors"] = soft_err

    fmt["title"] = {**tstats, "patterns": _validate_patterns(ai_t.get("patterns", []),
                                                             [v["title"] for v in vids]),
                    "note": ai_t.get("note", "")}
    fmt["description"] = {**dstats, "skeleton": ai_d.get("skeleton") or [],
                          "blocks": ai_d.get("blocks", []), "note": ai_d.get("note", "")}
    fmt["tags"] = gstats
    fmt["package"] = {**agg, "guide": ai_p}                 # package CẤP KÊNH của cả niche
    fmt["community"] = ai_c
    got = {"must": [str(x) for x in ((ai_t.get("rules") or {}).get("must") or [])],
           "avoid": [str(x) for x in ((ai_t.get("rules") or {}).get("avoid") or [])]}
    old = fmt.get("rules") or {}
    if not (old.get("must") or old.get("avoid")):           # user đã sửa luật thì GIỮ, không đè
        fmt["rules"] = got
    fmt["evidence"] = [{"id": v["id"], "title": v["title"], "views": v["views"],
                        "channel": next((c.get("title", "") for c in comps
                                         if v in (c.get("outliers") or [])), "")}
                       for v in sorted(outs, key=lambda x: -x.get("views", 0))[:12]]
    fmt["updated"] = library.now_iso()
    return fmt


def _one_num(v):
    """{min,max} → một số khi hai đầu bằng nhau; lệch thì giữ nguyên dict cho board hiện khoảng."""
    if isinstance(v, dict):
        lo, hi = v.get("min"), v.get("max")
        return lo if lo == hi else (v if lo is not None or hi is not None else None)
    return v


def _find_by_channel(cid: str) -> tuple[str, str, str] | None:
    """Format nào đang giữ kênh đối thủ `cid`? → (tên format, niche, slug). Không có → None."""
    if not cid:
        return None
    for f in all_formats():
        for c in (f.get("competitors") or []):
            if c.get("channel_id") == cid:
                return (f.get("name") or f.get("slug") or "?", f.get("niche") or "", f.get("slug") or "")
    return None


def channel_table() -> list[dict]:
    """BẢNG THỐNG KÊ kênh đối thủ đã nạp — mỗi Format một dòng (1 Format = 1 kênh đối thủ).

    Đọc thẳng từ `formats/*.json`, KHÔNG gọi YouTube và KHÔNG gọi LLM: mọi con số ở đây đã
    được `extract` harvest sẵn. Bảng này chỉ bày lại thứ có trên đĩa — mở bảng phải rẻ, không
    thì user ngại mở, mà ngại mở thì lại đi nạp trùng đúng cái nó sinh ra để ngăn.
    """
    out = []
    for f in all_formats():
        c = (f.get("competitors") or [{}])[0]
        pk = f.get("package") or {}
        out.append({
            "slug": f.get("slug") or "", "name": f.get("name") or "",
            "niche": f.get("niche") or "", "lang": f.get("lang") or "",
            "channel": c.get("title") or "", "channel_id": c.get("channel_id") or "",
            "handle": c.get("handle") or "", "url": c.get("url") or "",
            "n_videos": c.get("n_videos") or 0, "n_outliers": c.get("n_outliers") or 0,
            "enough": bool(c.get("enough_sample")),
            "cadence": c.get("cadence") or pk.get("cadence_days") or None,
            # `package.subs` là {min,max} vì hàm gộp vốn viết cho NHIỀU kênh. Từ khi chốt
            # 1 Format = 1 kênh đối thủ thì min == max, nên trả một số cho board khỏi phải
            # biết chuyện đó. Lệch nhau (dữ liệu Format cũ gộp nhiều kênh) thì giữ khoảng.
            "subs": _one_num(pk.get("subs")),
            "added": c.get("added_at") or f.get("created") or "",
            "updated": f.get("updated") or "",
        })
    # Mới nạp lên trước — người ta mở bảng này chủ yếu để xem "vừa có thêm gì".
    out.sort(key=lambda r: str(r.get("added") or ""), reverse=True)
    return out


def extract(body: dict, status: dict) -> dict:
    """MỖI URL → MỘT Format RIÊNG. 1 Format = 1 kênh đối thủ.

    Trước 2026-07-29 nhiều URL bị gộp vào 1 format rồi lấy trung bình — kênh của user
    học phải một "đối thủ trung bình" không có thật, pattern tiêu đề của 3 kênh trộn lẫn.
    User chốt: 1 kênh của tôi bám rule của ĐÚNG 1 kênh đối thủ. Nên dán 3 URL = 3 format,
    chọn gắn cái nào là việc của từng kênh.

    Tên format lấy theo TÊN KÊNH đối thủ; ô "tên" của user chỉ làm tiền tố khi có nhiều URL,
    và phải qua `clean_name()` — URL dán nhầm vào ô tên thì bỏ, không cho leo vào tên lẫn slug.
    """
    keys = common.load_keys()
    llm.usage_reset()
    raw_name = (body.get("name") or "").strip()
    name = clean_name(raw_name)
    # Bỏ chữ của user thì phải NÓI — im lặng sửa input là nói dối. Board hiện trong toast.
    name_ignored = raw_name if name != raw_name else ""
    niche = (body.get("niche") or "").strip()
    src = parse_sources(body.get("urls", ""))
    urls = src["channels"] + src["videos"]                  # video lẻ → suy ra kênh của nó
    if not urls:
        raise RuntimeError("Chưa có URL hợp lệ — dán URL kênh (/channel/…, @handle) hoặc URL video, mỗi dòng 1 cái")

    per = int(body.get("limit", 30))
    made: list[dict] = []
    dups: list[dict] = []
    seen: set[str] = set()
    for i, u in enumerate(urls, 1):
        status["step"] = f"đối thủ {i}/{len(urls)}…"
        try:
            c = fetch_competitor(u, keys, per_channel=per, status=status)
        except Exception as e:                              # noqa: BLE001 — 1 URL hỏng không chặn cả mẻ
            status["step"] = f"bỏ qua {u[:40]}: {e}"
            continue
        if c["channel_id"] in seen:
            continue
        seen.add(c["channel_id"])
        # ── CHỐNG TRÙNG KÊNH ĐỐI THỦ (user chốt 2026-08-02) ──────────────────────────────
        # Từ khi Seo cũng nạp được Format, hai người ở cùng một niche rất dễ nạp trùng một
        # kênh: A nạp "Cosmic Lens" hôm nay, B mai nạp lại vì không biết đã có. Kết quả là
        # hai Format y hệt nhau, mỗi cái tiêu ~5 unit quota + 2 call LLM, và lúc gắn Format
        # cho kênh thì không ai biết chọn cái nào.
        # KHOÁ SO SÁNH LÀ `channel_id`, KHÔNG phải URL: cùng một kênh dán được ít nhất ba
        # kiểu (`/channel/UC…`, `@handle`, URL một video của kênh) nên so mặt chữ URL là
        # gần như không bao giờ bắt được trùng. `channel_id` do YouTube trả về nên duy nhất.
        # So TOÀN BỘ thư viện chứ không chỉ trong niche đang nạp: một kênh đối thủ chỉ thuộc
        # về một niche, nên trùng ở niche khác vẫn là trùng — và thông báo nói rõ nó đang
        # nằm ở niche nào để user tự thấy mình gõ nhầm niche.
        dup = _find_by_channel(c["channel_id"])
        if dup and not body.get("refresh"):
            dn, dniche, dslug = dup
            # BỎ QUA DÒNG NÀY rồi đi tiếp, KHÔNG raise cả mẻ: dán 5 URL mà 1 cái trùng thì
            # raise là vứt luôn 4 cái hợp lệ đã tốn quota fetch. Hết mẻ mà chẳng nạp được gì
            # thì mới báo lỗi (ngay dưới) — lúc đó mới thật sự là "không có gì để làm".
            dups.append({"url": u, "channel": c.get("title") or c["channel_id"],
                         "in_format": dn, "niche": dniche, "slug": dslug})
            continue

        fname = c.get("title") or c.get("handle") or c["channel_id"]
        if name and len(urls) == 1:
            fname = name                                    # 1 URL → tôn trọng tên user đặt
        elif name:
            fname = f"{name} · {fname}"
        sl = _slug_of(niche, fname)
        # 2 kênh khác nhau mà tên slug-hoá ra giống nhau (vd "Space Doc" vs "space-doc") thì
        # format sau sẽ GHI ĐÈ format trước, mất trắng lần harvest đã tốn quota. Chỉ dùng lại
        # slug khi ĐÚNG kênh đó (channel_id khớp), còn không thì tìm slug trống.
        base, k = sl, 2
        while True:
            ex = load(sl)
            if ex is None or (ex.get("competitors") or [{}])[0].get("channel_id") == c["channel_id"]:
                break
            sl, k = f"{base}-{k}", k + 1
        old = load(sl) or {}
        fmt = {"name": fname, "niche": niche, "competitors": [c],
               "community_raw": (body.get("community") or "").strip() or old.get("community_raw", ""),
               "rules": old.get("rules") or {"must": [], "avoid": []},
               # GIỮ `lang` user đã khai qua mọi lần extract lại — cùng lý do với `rules`: đây là
               # thứ user gõ tay, extract lại là để làm mới SỐ LIỆU chứ không phải xoá khai báo.
               # FORMAT MỚI thừa kế ngôn ngữ THỊ TRƯỜNG ĐANG MỞ (body["lang"], board gửi — user
               # chốt 2026-08-04): trước đó format mới ra đời với lang rỗng nên bị tab FORMAT
               # (lọc theo thị trường) GIẤU ĐI — user thấy kênh vào bảng "📋 đã nạp" mà không
               # thấy thẻ format, tưởng tool nạp thiếu; phải tự đi khai ngôn ngữ nó mới hiện.
               # Đây KHÔNG phải máy đoán (việc đó vẫn là `guess_lang`, chỉ đề xuất): user đang
               # đứng trong thị trường đó mà bấm nạp, tức là chính họ khai bối cảnh rồi.
               "lang": old.get("lang", "") or str(body.get("lang") or "").strip(),
               "created": old.get("created") or library.now_iso()}
        status["step"] = f"phân tích {fname}…"
        rebuild(fmt, status)
        fmt["unknown_lines"] = src["unknown"]
        common.write_json(formats_dir(create=True) / f"{sl}.json", fmt)
        fmt["slug"] = sl
        made.append(fmt)

    if not made:
        # Nói ĐÚNG nguyên nhân. "Không đọc được kênh nào" cho một mẻ toàn kênh đã có sẵn là
        # sai hẳn — user sẽ đi kiểm tra URL, kiểm tra quota, trong khi việc cần làm là mở
        # bảng ra xem nó đã nằm ở Format nào.
        if dups:
            ds = "; ".join(f"{d['channel']} → đã có trong Format '{d['in_format']}'"
                           + (f" (niche {d['niche']})" if d["niche"] else "") for d in dups[:4])
            raise RuntimeError(
                f"Không nạp thêm được: {len(dups)} kênh đối thủ ĐÃ CÓ trong thư viện. {ds}"
                + ("…" if len(dups) > 4 else "")
                + " — mở bảng '📋 Kênh đối thủ đã nạp' để xem, hoặc bấm '↻ Làm mới' trên"
                  " chính dòng đó nếu muốn cập nhật lại số liệu.")
        raise RuntimeError("Không đọc được kênh đối thủ nào từ danh sách URL")
    usage = llm.usage_snapshot()
    for f in made:                                          # usage của cả mẻ, ghi vào từng format
        f["usage"] = usage
        common.write_json(formats_dir() / f"{f['slug']}.json", {k: v for k, v in f.items() if k != "slug"})
    status["usage"] = usage
    out = dict(made[0])
    out["created_formats"] = [{"slug": f["slug"], "name": f["name"]} for f in made]
    # BỎ DÒNG NÀO THÌ PHẢI NÓI — im lặng bỏ là user dán 5 URL, thấy 3 Format, rồi tự hỏi 2
    # cái kia đi đâu (cùng luật với `add_many` của kho niche và `name_ignored` bên dưới).
    out["dup_skipped"] = dups
    out["name_ignored"] = name_ignored
    return out


# ĐÃ GỠ `add_competitor()` (2026-07-31) — đừng viết lại. Từ khi chốt **1 Format = 1 kênh đối thủ**
# (2026-07-29) nó chỉ còn một đường ra duy nhất là `raise`: `extract()` sinh format nào cũng kèm
# sẵn 1 đối thủ, nên điều kiện "đã có đối thủ → chặn" luôn đúng. Ô nhập của nó trên board cũng đã
# bị gỡ từ lâu, còn lại hàm gọi vào ô không tồn tại.
# Muốn cập nhật số liệu một Format: `extract()` lại URL kênh đó với cùng niche + tên — trùng
# `channel_id` thì dùng lại đúng slug cũ (vòng while trong `extract`) và `rules` user sửa được giữ.


def remove_competitor(slug: str, channel_id: str, status: dict | None = None) -> dict:
    """Bỏ 1 đối thủ khỏi Format rồi tính lại. KHÔNG tốn quota YouTube (dữ liệu đã lưu sẵn)."""
    sl = common.slug(slug)
    fmt = load(sl)
    if fmt is None:
        raise RuntimeError(f"Không thấy format: {sl}")
    before = len(fmt.get("competitors") or [])
    fmt["competitors"] = [c for c in (fmt.get("competitors") or []) if c.get("channel_id") != channel_id]
    if len(fmt["competitors"]) == before:
        raise RuntimeError("Không thấy đối thủ này trong format")
    llm.usage_reset()
    rebuild(fmt, status or {})
    fmt["usage"] = llm.usage_snapshot()
    fmt.pop("slug", None)
    common.write_json(formats_dir(create=True) / f"{sl}.json", fmt)
    fmt["slug"] = sl
    return fmt


# ── áp dụng: KÊNH ĐÈ NICHE ──
def resolve(prof: dict | None, fmt: dict | None) -> dict:
    """Ghép Format niche (nền) + Profile kênh (đè) → cấu hình dùng cho 1 lần generate.

    Kênh có gì thì kênh thắng; kênh thiếu thì lấy của niche; không có cả hai → describe.py
    tự dùng standard.
    """
    prof, fmt = prof or {}, fmt or {}
    fd = fmt.get("description") or {}
    eff = {
        "skeleton": prof.get("skeleton") or fd.get("skeleton") or [],
        "blocks": prof.get("blocks") or fd.get("blocks") or [],
        "code": prof.get("code") or fmt.get("name") or "standard",
        "source": "kênh" if prof.get("skeleton") else ("niche" if fd.get("skeleton") else "standard"),
        "title_patterns": (fmt.get("title") or {}).get("patterns") or [],
        "title_note": (fmt.get("title") or {}).get("note", ""),
        "base_tags": (fmt.get("tags") or {}).get("base") or [],
        "rules": fmt.get("rules") or {"must": [], "avoid": []},
        "format_name": fmt.get("name", ""), "niche": fmt.get("niche") or prof.get("niche", ""),
        # Kênh thắng, thiếu thì lấy của niche — cùng nguyên tắc mọi field khác ở trên.
        # describe.py đọc field này để BẮT BUỘC ngôn ngữ output (xem describe._lang_rule).
        "lang": prof.get("lang") or fmt.get("lang") or "",
    }
    return eff


def check_rules(text: str, rules: dict) -> list[str]:
    """Soi 'avoid' của niche trong text sinh ra → cảnh báo (không hard-gate; user quyết)."""
    low = (text or "").lower()
    hits = []
    for r in (rules or {}).get("avoid", []):
        kws = [w for w in _WORD_RE.findall(str(r).lower()) if w not in _STOP][:3]
        if kws and all(k in low for k in kws):
            hits.append(str(r))
    return hits


if __name__ == "__main__":                                  # self-test offline (seed giả + monkeypatch LLM)
    src = parse_sources("https://www.youtube.com/@CosmicLens\nhttps://youtu.be/NTGYICp6c4s\nrác\n"
                        "https://www.youtube.com/channel/UC1234567890123456789012")
    assert src["channels"] == ["https://www.youtube.com/@CosmicLens",
                               "https://www.youtube.com/channel/UC1234567890123456789012"], src
    assert src["videos"] == ["NTGYICp6c4s"] and src["unknown"] == ["rác"], src

    vids = [{"id": f"v{i}", "title": f"The Biggest Black Hole Number {i}", "description": "",
             "tags": ["black hole"], "views": 1000, "channel": "C", "channel_id": "UC1"} for i in range(12)]
    vids[0]["views"] = 50_000                               # 1 outlier rõ rệt
    out, ok = outliers_of(vids)
    assert ok and [v["id"] for v in out] == ["v0"], out
    assert outliers_of(vids[:3])[1] is False                # <10 video → không đủ mẫu

    ts = title_stats(vids)
    assert ts["chars"]["avg"] > 0 and "black" in ts["anchors"], ts
    pool = harvest.build_pool([{**v, "is_main": False} for v in vids])
    gs = tag_stats(vids, pool)
    assert gs["base"] == ["black hole"] and gs["avg_count"] == 1.0, gs

    pats = _validate_patterns([{"pattern": "The [superlative] [entity]", "example": "The Biggest Black Hole Number 0"},
                               {"pattern": "X", "example": "TITLE BỊA KHÔNG CÓ THẬT"}],
                              [v["title"] for v in vids])
    assert pats[0]["example_verified"] and not pats[1]["example_verified"] and pats[1]["example"] == "", pats

    eff = resolve({"skeleton": ["HOOK", "SUMMARY"], "code": "CL-01"},
                  {"name": "Doc", "description": {"skeleton": ["HOOK", "CHAPTERS", "CTA"]},
                   "tags": {"base": ["space"]}, "rules": {"must": [], "avoid": ["giật tít sai sự thật"]}})
    assert eff["skeleton"] == ["HOOK", "SUMMARY"] and eff["source"] == "kênh", eff   # KÊNH ĐÈ NICHE
    assert eff["base_tags"] == ["space"], eff
    eff2 = resolve(None, {"description": {"skeleton": ["HOOK", "CHAPTERS"]}})
    assert eff2["skeleton"] == ["HOOK", "CHAPTERS"] and eff2["source"] == "niche", eff2

    # `lang` (06/08): kênh thắng, thiếu thì lấy của niche — describe.py bắt buộc ngôn ngữ output
    assert resolve({"lang": "Spanish"}, {"lang": "English"})["lang"] == "Spanish", "kênh phải thắng"
    assert resolve({}, {"lang": "English"})["lang"] == "English", "thiếu kênh thì lấy của niche"
    assert resolve({}, {})["lang"] == "", "cả hai đều chưa khai thì để rỗng, không bịa"

    assert check_rules("This is a giật tít sai sự thật video", {"avoid": ["giật tít sai sự thật"]})
    assert not check_rules("A calm documentary", {"avoid": ["giật tít sai sự thật"]})

    llm.set_hook(lambda s, u: '{"patterns":[{"pattern":"The [sup] [entity]","example":"The Biggest Black Hole Number 0","support":12}],"note":"n","rules":{"must":["ngắn"],"avoid":["clickbait"]}}')
    ai = infer_title(vids, ts)
    llm.set_hook(None)
    assert ai["patterns"][0]["support"] == 12 and ai["rules"]["avoid"] == ["clickbait"], ai

    # ── package cấp KÊNH (thứ video-level không thấy) ──
    assert split_keywords('Science space "black hole" life') == ["Science", "space", "black hole", "life"]
    assert split_keywords('nhay "lech') and split_keywords("") == []      # nháy lệch → không được crash
    assert upload_cadence(["2026-01-01T00:00:00Z", "2026-01-08T00:00:00Z",
                           "2026-01-15T00:00:00Z"])["median_days"] == 7.0
    assert upload_cadence(["2026-01-01T00:00:00Z"])["median_days"] is None   # <3 mốc → không đủ mẫu

    comps = [{"title": "A", "cadence": {"median_days": 7},
              "package": {"keywords": ["space", "science", "riêng A"], "description_chars": 400,
                          "sections": [{"type": "recentuploads"}], "n_sections": 1,
                          "trailer": "x", "subs": 1000}},
             {"title": "B", "cadence": {"median_days": 5},
              "package": {"keywords": ["Space", "science", "riêng B"], "description_chars": 600,
                          "sections": [{"type": "singleplaylist"}, {"type": "recentuploads"}],
                          "n_sections": 2, "trailer": "", "subs": 5000}}]
    agg = aggregate_package(comps)
    assert agg["n_channels"] == 2 and agg["keywords_common"] == ["space", "science"], agg  # chung ≥2 kênh
    assert "riêng a" not in agg["keywords_common"], agg                  # tag của 1 kênh → không phải chung
    assert agg["about_chars"]["avg"] == 500 and agg["with_trailer"] == 1, agg
    assert agg["cadence_days"] == 6.0 and agg["subs"] == {"min": 1000, "max": 5000}, agg
    assert aggregate_package([]) == {}

    # rebuild: tính lại từ competitors, KHÔNG gọi YouTube API
    fmt = {"name": "F", "niche": "Space", "rules": {"must": ["giữ nguyên"], "avoid": []},
           "competitors": [{"title": "A", "channel_id": "UC1", "n_videos": 12, "enough_sample": True,
                            "cadence": {"median_days": 7},
                            "package": {"keywords": ["space"], "description_chars": 400, "sections": [],
                                        "n_sections": 0, "trailer": "", "subs": 1000, "description": "About A"},
                            "outliers": [{"id": "v0", "title": "The Biggest Black Hole Number 0",
                                          "desc": "d", "tags": ["black hole"], "views": 50_000}]}]}
    llm.set_hook(lambda s, u: '{"patterns":[],"note":"","rules":{"must":["moi"],"avoid":[]},'
                              '"skeleton":["HOOK"],"blocks":[],"about_pattern":"p","checklist":["c1"]}')
    rebuild(fmt, {})
    llm.set_hook(None)
    assert fmt["n_channels"] == 1 and fmt["n_outliers"] == 1 and fmt["n_videos"] == 12, fmt
    assert fmt["rules"]["must"] == ["giữ nguyên"], fmt["rules"]        # luật user sửa KHÔNG bị đè
    # 1 đối thủ thì "từ khoá CHUNG" vô nghĩa (cần ≥2 kênh cùng dùng) → rỗng, nhưng vẫn liệt kê đủ
    # 1 Format = 1 đối thủ ⇒ "tag kênh dùng chung" chính là tag của kênh đó (không còn ngưỡng ≥2)
    assert fmt["package"]["keywords_common"] == ["space"], fmt["package"]
    assert fmt["package"]["n_channels"] == 1, fmt["package"]
    assert fmt["package"]["guide"]["checklist"] == ["c1"], fmt["package"]
    assert fmt["evidence"][0]["channel"] == "A", fmt["evidence"]
    print("niche_format.py self-test OK - parse URL, outlier 2x median, do so lieu, chan example bia, kenh de niche")

    # ── 1 Format = 1 KÊNH ĐỐI THỦ: dán 3 URL phải ra 3 format riêng, không trộn ──
    import tempfile as _tf
    from pathlib import Path as _Path

    with _tf.TemporaryDirectory() as _tmp:
        common.ROOT = _Path(_tmp)
        common.load_keys = lambda: ["k"]

        def _fake_comp(url, keys, per_channel=30, status=None):
            i = "123".index(url[-1])
            titles = ["Rival Alpha", "Rival Beta", "Rival Gamma"]
            return {"channel_id": f"UC{i}", "url": url, "title": titles[i], "handle": f"@r{i}",
                    "added_at": "t", "n_videos": 12, "n_outliers": 1, "enough_sample": True,
                    "cadence": {"median_days": 5 + i, "n": 12},
                    "package": {"title": titles[i], "keywords": [f"kw{i}", "chung"],
                                "description": "about", "description_chars": 100 + i,
                                "n_sections": 3, "subs": 1000 * (i + 1), "trailer": "", "sections": []},
                    "outliers": [{"id": f"v{i}", "title": f"The Alpha Thing {i}", "views": 9000,
                                  "desc": "d", "desc_tail": "", "tags": [f"tag{i}"],
                                  "published_at": "2026-01-01T00:00:00Z"}]}

        _real = fetch_competitor
        fetch_competitor = _fake_comp                        # noqa: F811
        llm.set_hook(lambda s, u: '{"patterns":[],"note":"","rules":{"must":[],"avoid":[]},'
                                  '"skeleton":["HOOK"],"blocks":[],"about_pattern":"p","checklist":["c"]}')
        res = extract({"name": "", "niche": "Space", "limit": 10, "lang": "English",
                       "urls": "https://youtube.com/channel/UC00000000000000000001\n"
                               "https://youtube.com/channel/UC00000000000000000002\n"
                               "https://youtube.com/channel/UC00000000000000000003"}, {})
        llm.set_hook(None)
        fetch_competitor = _real                             # noqa: F811

        made = res["created_formats"]
        assert len(made) == 3, made                          # 3 URL → 3 FORMAT, không phải 1
        assert [m["name"] for m in made] == ["Rival Alpha", "Rival Beta", "Rival Gamma"], made
        alls = all_formats()
        assert len(alls) == 3 and all(len(f["competitors"]) == 1 for f in alls), alls
        # FORMAT MỚI thừa kế ngôn ngữ thị trường (04/08) — lang rỗng là bị tab FORMAT giấu
        assert all(f.get("lang") == "English" for f in alls), [f.get("lang") for f in alls]
        for f in alls:                                       # số liệu KHÔNG bị trộn giữa các đối thủ
            assert f["package"]["n_channels"] == 1, f["name"]
            assert f["package"]["cadence_days"] in (5, 6, 7), f["package"]
        cad = sorted(f["package"]["cadence_days"] for f in alls)
        assert cad == [5, 6, 7], cad                         # mỗi format giữ nhịp đăng RIÊNG

        # NẠP TRÙNG bị CHẶN (user chốt 2026-08-02). Từ khi Seo cũng nạp được Format, hai
        # người cùng niche rất dễ nạp trùng một kênh và cùng tiêu quota cho một thứ.
        fetch_competitor = _fake_comp                        # noqa: F811
        try:
            extract({"name": "", "niche": "Space", "limit": 10,
                     "urls": "https://youtube.com/channel/UC00000000000000000001"}, {})
            raise AssertionError("phải CHẶN khi nạp trùng kênh đối thủ")
        except RuntimeError as e:
            assert "ĐÃ CÓ" in str(e), e
            assert "Rival Alpha" in str(e), e                 # phải chỉ đúng Format nào đang giữ
        assert len(all_formats()) == 3, "chặn rồi thì KHÔNG được đẻ thêm format"
        fetch_competitor = _real                             # noqa: F811

        # ...nhưng LÀM MỚI SỐ LIỆU thì vẫn phải chạy được: `refresh=True`. Đây là đường DUY
        # NHẤT để cập nhật một Format (từ khi gỡ `add_competitor`), chặn luôn nó là khoá cứng
        # dữ liệu ở lần harvest đầu tiên.
        target = alls[0]
        update(target["slug"], {"rules": {"must": ["luật user gõ tay"], "avoid": []},
                                "lang": "Tiếng Việt"})
        fetch_competitor = _fake_comp                        # noqa: F811
        llm.set_hook(lambda s, u: '{"patterns":[],"note":"","rules":{"must":[],"avoid":[]},'
                                  '"skeleton":["HOOK"],"blocks":[],"about_pattern":"p","checklist":["c"]}')
        extract({"name": "", "niche": "Space", "limit": 10, "refresh": True, "lang": "English",
                 "urls": "https://youtube.com/channel/UC00000000000000000001"}, {})
        llm.set_hook(None)
        fetch_competitor = _real                             # noqa: F811
        again = all_formats()
        assert len(again) == 3, [f["slug"] for f in again]    # KHÔNG đẻ format thứ 4
        same = next(f for f in again if f["slug"] == target["slug"])
        assert len(same["competitors"]) == 1, same["competitors"]
        assert same["rules"]["must"] == ["luật user gõ tay"], same["rules"]   # luật user KHÔNG bị đè
        # lang user KHAI TAY thắng lang thị trường gửi kèm lần refresh — cùng luật với `rules`
        assert same["lang"] == "Tiếng Việt", same["lang"]

    print("niche_format.py self-test OK - 1 format = 1 doi thu, nap trung bi CHAN, "
          "refresh=True van cap nhat tai cho")

    # ── URL dán nhầm vào ô "Tên format" ──────────────────────────────────────────────
    assert clean_name("https://www.youtube.com/channel/UCxx · Science Channel") == "Science Channel"
    assert clean_name("https://youtu.be/abc") == ""              # toàn link → rỗng, gọi tự lấy tên kênh
    assert clean_name("www.youtube.com/@x The Space Race") == "The Space Race"
    assert clean_name("Country Documentary") == "Country Documentary"   # tên thường KHÔNG bị đụng
    assert clean_name("Youtube Shorts Doc") == "Youtube Shorts Doc"     # "youtube" trần không phải URL

    with _tf.TemporaryDirectory() as _tmp:
        common.ROOT = _Path(_tmp)
        common.load_keys = lambda: ["k"]
        _real = fetch_competitor
        fetch_competitor = _fake_comp                            # noqa: F811
        llm.set_hook(lambda s, u: '{"patterns":[],"note":"","rules":{"must":[],"avoid":[]},'
                                  '"skeleton":["HOOK"],"blocks":[],"about_pattern":"p","checklist":["c"]}')
        bad = "https://www.youtube.com/channel/UCmZyhcpukKn96nz1ziRs16Q"
        res = extract({"name": bad, "niche": "Space", "limit": 10,
                       "urls": "https://youtube.com/channel/UC00000000000000000001\n"
                               "https://youtube.com/channel/UC00000000000000000002"}, {})
        llm.set_hook(None)
        fetch_competitor = _real                                 # noqa: F811
        # link không được leo vào TÊN (thẻ format) lẫn SLUG (tên file) — và phải BÁO là đã bỏ
        assert [m["name"] for m in res["created_formats"]] == ["Rival Alpha", "Rival Beta"], res
        assert all("youtube" not in m["slug"] for m in res["created_formats"]), res
        assert res["name_ignored"] == bad, res

    print("niche_format.py self-test OK - URL dan nham o ten format: bo khoi ten + slug, co bao")

    # ── NGÔN NGỮ: chỉ báo khi ĐỦ DỮ LIỆU và THẬT SỰ lệch ──────────────────────────────────
    assert lang_mismatch({"lang": "Vietnamese"}, {"lang": "English"}), "phai bat duoc lech that"
    assert not lang_mismatch({"lang": "English"}, {"lang": "English"}), "khop ma van bao"
    # viết kiểu khác nhau của CÙNG một thứ tiếng: không được báo oan
    for a, b in [("EN", "English"), ("Tiếng Việt", "vietnamese"), ("  english ", "ENGLISH"),
                 ("vi", "Tiếng Việt")]:
        assert not lang_mismatch({"lang": a}, {"lang": b}), (a, b)
    # THIẾU dữ liệu ≠ đã đối chiếu và khớp → im lặng, KHÔNG bịa cảnh báo
    assert not lang_mismatch({"lang": "English"}, {}), "format chua khai -> khong duoc bao"
    assert not lang_mismatch({}, {"lang": "English"}), "kenh chua khai -> khong duoc bao"
    assert not lang_mismatch({}, None), "khong co gi de doi chieu"
    # `lang` phải là field user sửa được, và extract lại KHÔNG được xoá nó
    import tempfile as _tf
    from pathlib import Path as _Path
    with _tf.TemporaryDirectory() as td:
        # Phải gán CẢ HAI: common.py tính FORMATS lúc import nên đổi mỗi ROOT là vẫn ghi vào
        # thư mục THẬT của user (bẫy đã cắn hồi bấm giờ extract).
        common.ROOT = _Path(td)
        common.FORMATS = _Path(td) / "formats"
        f = {"name": "F", "niche": "N", "competitors": [], "rules": {"must": [], "avoid": []}}
        common.write_json(formats_dir(create=True) / "n-f.json", f)
        got = update("n-f", {"lang": "Tiếng Việt"})
        assert got["lang"] == "Tiếng Việt", got
        assert (load("n-f") or {}).get("lang") == "Tiếng Việt", "khong ghi xuong dia"
    print("niche_format.py self-test OK - lang: bat lech that, khong bao oan bi danh khac kieu, "
          "thieu du lieu thi im")

    # ── guess_lang: ĐOÁN được thì nói, KHÔNG đoán được thì THÚ NHẬN ─────────────────────
    def _ev(*titles):
        return {"evidence": [{"title": t} for t in titles]}
    g = guess_lang(_ev("Cuộc sống ở PHẦN LAN - Quốc gia hạnh phúc nhất",
                       "Cuộc sống ở NA UY - Thiên nhiên tuyệt đẹp",
                       "Khám phá ĐAN MẠCH: nơi đáng sống nhất"))
    assert g["lang"] == "Tiếng Việt", g
    g = guess_lang(_ev("Life in FINLAND! - The HAPPIEST Country on Earth with Beautiful Nature",
                       "Why Life in NORWAY is the Best in the World for Families",
                       "What Life is Really Like in SWEDEN and How People Live There"))
    assert g["lang"] == "English", g
    # ── CA ĐÃ CẮN THẬT 2026-08-01: title TIẾNG TÂY BAN NHA bị gán "Tiếng Việt" ──────────
    # Mẫu tiếng Việt ban đầu gồm cả `à á è é ì í ò ó ù ú`, mà TBN dùng `á í ó` đầy → cả 3
    # format TBN của user đều đoán sai. Chữ CHUNG không phân biệt được gì; chỉ dấu RIÊNG mới
    # nói lên điều gì. Dùng đúng title thật của user làm ca kiểm.
    es = guess_lang(_ev("¡La vida en Noruega en 2026! Mujeres hermosas y naturaleza majestuosa",
                        "¡Así es la vida en Vietnam! El país más barato del mundo",
                        "MUNDO BELLO | Los lugares más hermosos del planeta",
                        "Así Es La Vida En BURUNDI, El País Más POBRE Del MUNDO"))
    assert es["lang"] == "Spanish", es
    assert "Việt" not in es["lang"], es
    # và tiếng Việt vẫn phải nhận ra được (không phải chữa bằng cách tắt hẳn)
    assert guess_lang(_ev("Cuộc sống ở PHẦN LAN - Quốc gia hạnh phúc nhất thế giới",
                          "Cuộc sống ở NA UY - Thiên nhiên tuyệt đẹp vô cùng",
                          "Khám phá ĐAN MẠCH: nơi đáng sống nhất hành tinh"))["lang"] == "Tiếng Việt"
    # Latin mà hai ứng viên sát nhau → thà trả rỗng còn hơn bốc thăm hộ user
    g = guess_lang(_ev("Kehidupan di FINLANDIA negara paling bahagia sedunia",
                       "Kehidupan di NORWEGIA alam yang sangat indah sekali",
                       "Menjelajahi DENMARK tempat terbaik untuk keluarga muda"))
    assert g["lang"] in ("", "Indonesian"), g
    assert guess_lang({})["lang"] == "" and guess_lang({})["n"] == 0
    # mọi nhánh phải kèm LÝ DO — đề xuất không giải thích thì user không có cơ sở duyệt
    for case in [_ev("Cuộc sống ở HÀ LAN rất tuyệt vời và đáng sống"), _ev(), {},
                 _ev("Life in FINLAND is the best in the world for all of us and you")]:
        assert guess_lang(case)["why"], case
    # KHÔNG được tự ghi vào format — đề xuất là đề xuất
    _f = {"evidence": [{"title": "Cuộc sống ở PHẦN LAN rất đáng sống và hạnh phúc nhất"}]}
    guess_lang(_f)
    assert "lang" not in _f, "guess_lang KHONG duoc tu dien vao format"
    print("niche_format.py self-test OK - guess_lang: doan he chu + tieng Anh, THA RONG khi "
          "khong chac, luon kem ly do, khong tu ghi")
