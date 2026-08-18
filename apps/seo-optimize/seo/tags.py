"""Tag stage — pool → 3 bộ tag khả dụng. Theo tag-definition.md.

LLM: relevance gate + phân vai + chọn primary (hiểu ngữ nghĩa nội dung video).
Python: assemble slot, cap broad, budget ký tự, tính điểm 'khớp pattern'. Multi-variant = 3 bộ
khác tỉ lệ broad/long-tail (tái dùng qua giai đoạn, né trùng metadata).
"""
from __future__ import annotations

import json
import statistics

from . import digest, harvest, llm

_SYS = (
    "Bạn là trợ lý SEO YouTube. Cho NỘI DUNG video của user và danh sách tag ứng viên "
    "(tag THẬT từ video đối thủ cùng chủ đề), hãy phân loại theo tag-definition: "
    "relevance với chính video này là trên hết, KHÔNG theo tần suất. "
    "keep=true cho MỌI tag liên quan chủ đề video (cả broad lẫn cụ thể) — giữ nhiều để đủ tạo 3 bộ "
    "khác nhau; chỉ keep=false nếu tag LẠC chủ đề. "
    "Trả JSON: {\"primary\": <1 tag ứng viên khớp nhất chủ đề chính>, "
    "\"tags\":[{\"tag\":<ứng viên>,\"keep\":<true nếu liên quan chủ đề>,"
    "\"role\":\"primary|variation|broad|longtail|entity\"}]}. "
    "broad = generic khó rank (astrophysics); longtail = cụ thể 2-3 từ; entity = tên riêng. "
    "Phân vai đủ cả broad, longtail, entity để 3 bộ đa dạng."
)
_DESC_RULE = (
    " Một số ứng viên nằm trong `candidates_from_description`: chúng rút từ hashtag và cụm từ "
    "lặp trong DESCRIPTION của đối thủ, KHÔNG phải tag do chủ kênh khai — bằng chứng yếu hơn. "
    "Chỉ keep=true khi thật sự đúng chủ đề video; KHÔNG được chọn làm primary."
)


def desc_candidates(dm: dict | None, have: set[str], limit: int = 14) -> list[str]:
    """Ứng viên tag rút từ DESCRIPTION đối thủ (hashtag + cụm khoá lặp), bỏ cái đã có trong pool.

    Bằng chứng yếu hơn tag thật (tag là chủ kênh tự khai, description thì tự do) nên chỉ làm
    ứng viên BỔ SUNG: vẫn phải qua cửa relevance của LLM, và `assemble_sets` xếp chúng sau vì
    không có view-weight trong pool.
    """
    if not dm:
        return []
    out: list[str] = []
    for t in [h.replace("_", " ") for h in (dm.get("hashtags") or [])] + (dm.get("phrases") or []):
        c = harvest.canonical(t)
        if c and c not in have and c not in out:
            out.append(c)
        if len(out) >= limit:
            break
    return out


def annotate(pool: list[dict], title: str, brief: dict | str, desc_meta: dict | None = None) -> dict:
    """LLM gate/phân vai/primary trên tối đa 40 ứng viên mạnh nhất pool (+ ứng viên từ description).

    `brief` = brief kịch bản (digest.build) dùng chung cả 3 stage; truyền str = kịch bản thô (fallback).
    """
    cands = [r["canonical"] for r in pool][:40]
    extra = desc_candidates(desc_meta, set(cands))
    content = digest.payload(brief, "") if isinstance(brief, dict) else digest.payload({}, brief)
    payload = {"title": title, **content, "candidates": cands + extra}
    if extra:
        # nói rõ nguồn để LLM biết đây là bằng chứng yếu hơn, đừng nâng lên primary chỉ vì lạ tai
        payload["candidates_from_description"] = extra
    user = json.dumps(payload, ensure_ascii=False)
    sysmsg = _SYS + (_DESC_RULE if extra else "")
    return llm.call_json(sysmsg, user, max_tokens=2400, temperature=0.2)  # reasoning model cần headroom


def _budget(order: list[str], target: int, cap: int, min_tags: int) -> tuple[list[str], int]:
    out: list[str] = []
    s = 0
    for t in order:
        if t in out:
            continue
        add = len(t) + (2 if out else 0)                 # ", "
        if s + add > cap:
            break
        if out and s + add > target and len(out) >= min_tags:
            break
        out.append(t)
        s += add
    return out, s


def assemble_sets(pool: list[dict], ann: dict, n_total: int,
                  cap: int = 500, base_tags: list[str] | None = None) -> list[dict]:
    """Python ráp 3 bộ khác thành phần broad/long-tail. Primary luôn đứng đầu.

    `base_tags` = tag nền của niche (Format Profile). Chèn CUỐI mỗi order → chỉ lọt vào bộ khi
    còn ngân sách ký tự, không đẩy tag relevance của chính video ra ngoài.
    """
    W = {r["canonical"]: r for r in pool}
    w = lambda c: W.get(c, {}).get("sum_view_w", 0.0)          # noqa: E731
    wl = lambda c: W.get(c, {}).get("word_len", len(c.split()))  # noqa: E731
    nv = lambda c: W.get(c, {}).get("n_videos", 1)            # noqa: E731

    # BỎ TAG BỊA: tag hợp lệ phải là tag THẬT của video đối thủ (có trong pool). LLM chỉ được
    # GIỮ/BỎ/phân vai ứng viên, không được đẻ tag mới — tag bịa đi thẳng lên video thật, mà
    # YouTube phạt tag sai lệch. Trả về `invented` để board nói rõ đã bỏ gì, không im lặng.
    raw_kept = [t for t in ann.get("tags", []) if t.get("keep")]
    kept = [t for t in raw_kept if harvest.canonical(t.get("tag", "")) in W]
    invented = [t.get("tag", "") for t in raw_kept if harvest.canonical(t.get("tag", "")) not in W]
    primary = ann.get("primary") or (kept[0]["tag"] if kept else "")
    if harvest.canonical(primary) not in W:               # primary bịa → lấy tag thật mạnh nhất
        if primary:
            invented.append(primary)
        primary = kept[0]["tag"] if kept else ""
    roles = {t["tag"]: t.get("role", "longtail") for t in kept}

    def is_broad(c):
        return roles.get(c) == "broad" or wl(c) <= 1

    names = [t["tag"] for t in kept if t["tag"] != primary]
    broad = sorted([c for c in names if is_broad(c)], key=lambda c: -w(c))
    entity = sorted([c for c in names if roles.get(c) == "entity" and not is_broad(c)], key=lambda c: -w(c))
    longtail = sorted([c for c in names if not is_broad(c) and roles.get(c) != "entity"], key=lambda c: -w(c))

    # 3 thành phần ưu tiên khác nhau (primary luôn đầu)
    orders = {
        "Long-tail nặng": [primary] + entity[:2] + longtail + broad[:1],
        "Cân bằng":       [primary] + entity[:1] + _interleave(longtail, broad[:2]),
        "Broad + reach":  [primary] + broad + entity + longtail,
    }
    base = [harvest.canonical(t) for t in (base_tags or []) if harvest.canonical(t)]
    if base:
        orders = {k: v + [b for b in base if b not in v] for k, v in orders.items()}
    targets = {"Long-tail nặng": 200, "Cân bằng": 260, "Broad + reach": 320}
    maxw = max((r["sum_view_w"] for r in pool), default=1.0) or 1.0

    sets = []
    for name, order in orders.items():
        order = [c for c in order if c]                        # bỏ rỗng
        tags, chars = _budget(order, targets[name], cap, min_tags=5)
        nb = sum(1 for c in tags if is_broad(c))
        nl = len(tags) - nb - (1 if primary in tags else 0)
        avg = statistics.mean([w(c) for c in tags]) / maxw if tags else 0
        nudge = {"Long-tail nặng": 4, "Cân bằng": 0, "Broad + reach": -5}[name]
        score = max(60, min(96, round(70 + 20 * avg + nudge)))
        cover = max((nv(c) for c in tags), default=0)
        sets.append({"name": name, "score": score, "chars": chars,
                     "ratio": {"broad": nb, "longtail": max(0, nl)},
                     "coverage": f"{cover}/{n_total}", "tags": tags,
                     "invented": sorted(set(x for x in invented if x))})
    sets.sort(key=lambda s: -s["score"])
    return sets


def _interleave(a: list, b: list) -> list:
    out = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            out.append(a[i])
        if i < len(b):
            out.append(b[i])
    return out


def select(pool: list[dict], title: str, brief: dict | str, n_total: int,
           base_tags: list[str] | None = None, desc_meta: dict | None = None) -> list[dict]:
    return assemble_sets(pool, annotate(pool, title, brief, desc_meta), n_total, base_tags=base_tags)


if __name__ == "__main__":                                    # self-test offline (seed giả)
    pool = [
        {"canonical": "sagittarius a*", "sum_view_w": 1000, "word_len": 2, "n_videos": 6},
        {"canonical": "supermassive black hole", "sum_view_w": 900, "word_len": 3, "n_videos": 5},
        {"canonical": "event horizon", "sum_view_w": 700, "word_len": 2, "n_videos": 4},
        {"canonical": "astrophysics", "sum_view_w": 800, "word_len": 1, "n_videos": 7},
        {"canonical": "spaghettification", "sum_view_w": 600, "word_len": 1, "n_videos": 3},
        {"canonical": "what is inside a black hole", "sum_view_w": 500, "word_len": 6, "n_videos": 2},
    ]
    ann = {"primary": "sagittarius a*", "tags": [
        {"tag": "sagittarius a*", "keep": True, "role": "primary"},
        {"tag": "supermassive black hole", "keep": True, "role": "longtail"},
        {"tag": "event horizon", "keep": True, "role": "longtail"},
        {"tag": "astrophysics", "keep": True, "role": "broad"},
        {"tag": "spaghettification", "keep": True, "role": "entity"},
        {"tag": "what is inside a black hole", "keep": True, "role": "longtail"},
    ]}
    sets = assemble_sets(pool, ann, n_total=8)
    assert len(sets) == 3, sets
    for s in sets:
        assert s["tags"][0] == "sagittarius a*", s          # primary đầu
        assert s["chars"] <= 500 and len(s["tags"]) >= 5, s
    # bộ 'Broad + reach' phải có nhiều broad hơn 'Long-tail nặng'
    by = {s["name"]: s for s in sets}
    assert by["Broad + reach"]["ratio"]["broad"] >= by["Long-tail nặng"]["ratio"]["broad"], by
    # base tag của niche: lọt vào bộ khi còn ngân sách, KHÔNG đẩy primary/relevance ra
    bs = assemble_sets(pool, ann, n_total=8, base_tags=["Deep Space", "deep space"])
    assert all(s["tags"][0] == "sagittarius a*" for s in bs), bs
    assert any("deep space" in s["tags"] for s in bs), bs
    assert all(s["chars"] <= 500 for s in bs), bs
    # annotate qua hook
    llm.set_hook(lambda s, u: '{"primary":"sagittarius a*","tags":[{"tag":"sagittarius a*","keep":true,"role":"primary"}]}')
    assert annotate(pool, "t", "s")["primary"] == "sagittarius a*"
    llm.set_hook(None)
    print("tags.py self-test OK ·", [(s["name"], s["score"], len(s["tags"])) for s in sets])

    # ── ứng viên từ DESCRIPTION đối thủ: bổ sung, không lấn tag thật ──
    DM = {"hashtags": ["space", "black_hole"], "phrases": ["event horizon", "the center of"]}
    have = {r["canonical"] for r in pool}
    dc = desc_candidates(DM, have)
    assert "space" in dc and "black hole" in dc, dc          # '_' trong hashtag → khoảng trắng
    assert "event horizon" not in dc, dc                     # đã có trong pool → không nhân đôi
    assert desc_candidates(None, have) == [] and desc_candidates({}, have) == []

    seen = []
    llm.set_hook(lambda sy, u: (seen.append((sy, u)),
                                '{"primary":"sagittarius a*","tags":[]}')[1])
    annotate(pool, "T", "kịch bản", DM)
    sy, u = seen[-1]
    assert "candidates_from_description" in u, u[:200]
    assert "bằng chứng yếu hơn" in sy, sy[-200:]             # prompt nói rõ nguồn yếu
    assert "KHÔNG được chọn làm primary" in sy, sy[-200:]
    seen.clear()
    annotate(pool, "T", "kịch bản")                          # không có desc_meta → prompt giữ nguyên
    assert "candidates_from_description" not in seen[-1][1]
    assert "bằng chứng yếu hơn" not in seen[-1][0]
    llm.set_hook(None)
    # ── BỎ TAG BỊA: LLM chỉ được giữ/bỏ ứng viên, KHÔNG được đẻ tag mới ──
    ann_bia = {"primary": "sagittarius a*", "tags": [
        {"tag": "sagittarius a*", "keep": True, "role": "primary"},
        {"tag": "supermassive black hole", "keep": True, "role": "longtail"},
        {"tag": "TAG NAY TOI BIA RA", "keep": True, "role": "longtail"},
        {"tag": "nasa secret footage", "keep": True, "role": "entity"}]}
    sb = assemble_sets(pool, ann_bia, n_total=3)
    real = {r["canonical"] for r in pool}
    allt = {t for x in sb for t in x["tags"]}
    assert not (allt - real), f"tag bịa lọt ra: {allt - real}"
    assert set(sb[0]["invented"]) == {"TAG NAY TOI BIA RA", "nasa secret footage"}, sb[0]["invented"]

    # primary bịa → phải rơi về tag THẬT mạnh nhất, không được dùng tag bịa làm primary
    ann_p = {"primary": "PRIMARY BIA", "tags": [
        {"tag": "event horizon", "keep": True, "role": "longtail"},
        {"tag": "astrophysics", "keep": True, "role": "broad"}]}
    sp2 = assemble_sets(pool, ann_p, n_total=3)
    assert all(t in real for x in sp2 for t in x["tags"]), sp2
    assert "PRIMARY BIA" in sp2[0]["invented"], sp2[0]["invented"]

    # base_tags của Format là do PYTHON đo, không phải LLM bịa → vẫn được giữ
    sbase = assemble_sets(pool, ann_p, n_total=3, base_tags=["space documentary"])
    assert any("space documentary" in x["tags"] for x in sbase), sbase

    print("tags.py self-test OK - tag LLM bia bi bo hoan toan, base_tags cua Format van giu")
