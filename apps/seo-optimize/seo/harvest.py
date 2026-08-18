"""H1/H2 — harvest video đối thủ (YouTube API) → pool tag đã weighting.

Python thuần: chuẩn hóa tag, dedup mặt chữ, view-weighted + position-weighted.
Semantic dedup (synonym) để cho tag stage (LLM). Không đếm thô — theo tag-definition.md.
"""
from __future__ import annotations

import math
import re

from . import common


def canonical(tag: str) -> str:
    """Chuẩn hóa mặt chữ: lower, gộp khoảng trắng. (Synonym dedup = LLM, ở tag stage.)"""
    return re.sub(r"\s+", " ", (tag or "").strip().lower())


def videos_from_items(items: list[dict], main_id: str | None) -> list[dict]:
    """Item API → shape gọn {id,title,description,tags,views,is_main}."""
    out = []
    for it in items:
        sn = it.get("snippet", {})
        st = it.get("statistics", {})
        out.append({
            "id": it.get("id"),
            "title": sn.get("title", ""),
            "description": sn.get("description", ""),
            "tags": sn.get("tags", []) or [],
            "views": int(st.get("viewCount", 0) or 0),
            "is_main": it.get("id") == main_id,
        })
    return out


def build_pool(videos: list[dict]) -> list[dict]:
    """Gộp tag toàn bộ video → pool record đã weighting, sort theo sum_view_w giảm dần.

    - sum_view_w: Σ sqrt(views) các video dùng tag (giảm chấn: 1 video khủng không áp đảo).
    - best_pos: vị trí sớm nhất trong list tag gốc của owner (nhỏ = intent cao).
    - n_videos: số video dùng tag (phủ pool).
    """
    agg: dict[str, dict] = {}
    for v in videos:
        vw = math.sqrt(max(v["views"], 1))
        for pos, tag in enumerate(v["tags"]):
            c = canonical(tag)
            if not c:
                continue
            rec = agg.get(c)
            if rec is None:
                rec = agg[c] = {"tag": tag, "canonical": c, "n_videos": 0,
                                "sum_view_w": 0.0, "best_pos": 999,
                                "word_len": len(c.split())}
            rec["n_videos"] += 1
            rec["sum_view_w"] = round(rec["sum_view_w"] + vw, 2)
            rec["best_pos"] = min(rec["best_pos"], pos)
    return sorted(agg.values(), key=lambda r: (-r["sum_view_w"], r["best_pos"]))


_HASH_RE = re.compile(r"#(\w[\w-]{1,39})")


def desc_meta(videos: list[dict]) -> dict:
    """META trong DESCRIPTION của chính các video đối thủ trong tập này.

    `videos_from_items` vẫn tải description về từ trước nhưng không ai dùng — trong khi đó là
    nguồn SEO thật: hashtag họ gắn, cụm khoá lặp lại giữa nhiều video, keyword có nằm trong
    125 ký tự đầu không (phần YouTube hiển thị/đánh trọng số cao nhất).

    Thuần Python đếm — không LLM, không thêm quota (dữ liệu đã có trong tay).
    """
    descs = [(v.get("description") or "") for v in videos]
    live = [d for d in descs if d.strip()]
    if not live:
        return {}
    hs: dict[str, int] = {}
    for d in live:
        for h in {m.lower() for m in _HASH_RE.findall(d)}:  # mỗi video đếm 1 lần/hashtag
            hs[h] = hs.get(h, 0) + 1
    n = len(live)
    heads = [d[:125].lower() for d in live]
    # cụm 2-3 từ lặp ở ≥2 video → ứng viên tag long-tail có bằng chứng
    phr: dict[str, int] = {}
    for d in live:
        words = re.findall(r"[a-zA-ZÀ-ỹ0-9']+", d[:600].lower())
        seen_here = set()
        for size in (2, 3):
            for i in range(len(words) - size + 1):
                p = " ".join(words[i:i + size])
                if len(p) < 8 or p in seen_here:
                    continue
                seen_here.add(p)
                phr[p] = phr.get(p, 0) + 1
    return {
        "n_desc": n,
        "chars": {"avg": round(sum(len(d) for d in live) / n),
                  "range": [min(len(d) for d in live), max(len(d) for d in live)]},
        "hashtags": [h for h, c in sorted(hs.items(), key=lambda x: (-x[1], x[0])) if c >= 2][:12]
                    or [h for h, _ in sorted(hs.items(), key=lambda x: (-x[1], x[0]))][:8],
        "phrases": [p for p, c in sorted(phr.items(), key=lambda x: (-x[1], x[0])) if c >= 2][:15],
        "heads": heads[:3],                                # 125 ký tự đầu để đối chiếu keyword
    }


def harvest(main_url: str, sub_urls: str, keys: list[str]) -> dict:
    """Gọi API lấy video chính + phụ → {videos, pool, n_videos}. (Cần key thật.)"""
    main_id = common.extract_video_id(main_url or "")
    ids = ([main_id] if main_id else []) + common.parse_urls(sub_urls)
    ids = list(dict.fromkeys([i for i in ids if i]))          # dedup, giữ thứ tự
    if not ids:
        raise RuntimeError("Không có video id hợp lệ (video chính + phụ)")
    items = common.fetch_videos(ids, keys, parts="snippet,statistics")
    videos = videos_from_items(items, main_id)
    return {"videos": videos, "pool": build_pool(videos), "n_videos": len(videos),
            "desc_meta": desc_meta(videos)}


if __name__ == "__main__":                                    # self-test offline (seed giả)
    vids = [
        {"id": "A", "tags": ["sagittarius a*", "black hole", "astrophysics"], "views": 1_000_000, "is_main": True},
        {"id": "B", "tags": ["black hole", "event horizon"], "views": 10_000, "is_main": False},
        {"id": "C", "tags": ["Black Hole", "astrophysics", "spaghettification"], "views": 250_000, "is_main": False},
    ]
    pool = build_pool([{**v, "title": "", "description": ""} for v in vids])
    by = {r["canonical"]: r for r in pool}
    assert by["black hole"]["n_videos"] == 3, by["black hole"]          # gộp 'Black Hole' == 'black hole'
    assert by["black hole"]["best_pos"] == 0
    # tag ở video view cao (A:1M, pos0) weight hơn tag chỉ ở video nhỏ
    assert by["sagittarius a*"]["sum_view_w"] > by["event horizon"]["sum_view_w"], pool
    assert pool[0]["sum_view_w"] >= pool[-1]["sum_view_w"]              # sort giảm dần
    print("harvest.py self-test OK ·", len(pool), "tag ·", by["black hole"])

    # ── META trong description đối thủ: trước đây tải về rồi vứt ──
    dv = [{"description": "Sagittarius A* is the black hole at the center.\n\n"
                          "In this documentary we explore the event horizon.\n#Space #BlackHole",
           "tags": [], "views": 10, "is_main": True},
          {"description": "The black hole at the center of our galaxy is real.\n#Space #Astronomy",
           "tags": [], "views": 10, "is_main": False},
          {"description": "   ", "tags": [], "views": 1, "is_main": False}]
    dm = desc_meta(dv)
    assert dm["n_desc"] == 2, dm                              # bỏ description rỗng
    assert dm["hashtags"] == ["space"], dm["hashtags"]        # #Space có ở 2/2 video; #BlackHole 1
    assert "black hole" in dm["phrases"], dm["phrases"]       # cụm lặp ở cả 2 → ứng viên tag
    assert "the center" in dm["phrases"], dm["phrases"]
    assert dm["chars"]["avg"] > 0 and len(dm["heads"]) == 2, dm
    assert desc_meta([{"description": "", "tags": [], "views": 1}]) == {}   # không có gì thì im
    print("harvest.py self-test OK - desc_meta lay hashtag + cum khoa lap tu description doi thu")
