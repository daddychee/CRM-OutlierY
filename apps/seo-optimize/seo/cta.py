"""Sinh khối Link/CTA cho KÊNH CỦA MÌNH, bám rule Format của đối thủ.

Vì sao có module này: trước đây `links` là ô user gõ tay toàn bộ. User chỉ muốn khai
**đúng 1 thứ — link sub_confirmation** — phần chữ nghĩa để tool học từ đối thủ mà viết.

RANH GIỚI CỨNG (CLAUDE.md — "LLM KHÔNG bao giờ tự sinh link/CTA"):
    LLM viết CHỮ · Python giữ URL.
LLM chỉ được đặt đúng một chỗ giữ chỗ `{{SUB}}`. Mọi URL khác do LLM viết ra đều bị
Python loại — LLM bịa URL trông y như thật (sai 1 ký tự trong handle = link chết trên
video thật), và tool không có cách nào phân biệt URL thật/giả. Nên không tin, chỉ chặn.

Chạy 1 lần/kênh, kết quả lưu vào `profile.links` → mọi lần generate sau dùng lại, 0 token.

Self-test:  python -m seo.cta
"""
from __future__ import annotations

import json
import re

from . import library, llm, niche_format

_URL_RE = re.compile(r"https?://\S+")
_SLOT_RE = re.compile(r"\{\{[^}]*\}\}")
_SUB_SLOT_RE = re.compile(r"\{\{\s*(SUB|SUBSCRIBE|SUB_URL)\s*\}\}", re.I)
_HASH_RE = re.compile(r"#\w+")                     # \w của py3 ăn cả chữ có dấu (#Astronomía)

MAX_EVIDENCE = 8           # đủ để thấy pattern, không phình prompt
TAIL_CHARS = 700


_SYS_CTA = (
    "Bạn viết khối LINK/CTA đặt ở CUỐI phần description video YouTube cho một kênh. "
    "Đầu vào: (a) đuôi description THẬT của các video outlier trong cùng niche — đây là cách "
    "đối thủ đang viết CTA; (b) luật format của niche; (c) thông tin kênh cần viết. "
    "Nhiệm vụ: học CÁCH VIẾT của đối thủ (giọng, thứ tự dòng, emoji, số lượng và vị trí hashtag, "
    "độ dài) rồi viết một khối CTA cho kênh này. "
    "\n\nLUẬT TUYỆT ĐỐI VỀ LINK — vi phạm là hỏng cả kết quả:\n"
    "1. Chỗ nào cần link đăng ký kênh, viết ĐÚNG chuỗi {{SUB}} — không viết URL nào khác.\n"
    "2. CẤM viết bất kỳ http:// hay https:// nào. Cấm bịa tên miền, handle, mã video.\n"
    "3. Nếu đối thủ có dòng link mà kênh này không có dữ liệu tương ứng (affiliate, "
    "Patreon, mạng xã hội, video tiếp theo), hãy BỎ HẲN dòng đó — đừng bịa, đừng để chỗ trống.\n"
    "4. Hashtag thì được viết bình thường (không phải link).\n\n"
    "Nếu có `competitor_voice` (rút từ bài post cộng đồng của họ — chỗ họ nói chuyện tự nhiên "
    "nhất, chuẩn hơn cả đuôi description vốn đã đóng khuôn), hãy BÁM GIỌNG đó: cách xưng hô, "
    "mức trang trọng, độ dài câu. Đừng đổi giọng giữa chừng.\n"
    "Trả JSON: {\"cta\":<khối CTA nhiều dòng, dùng \\n xuống dòng>,"
    "\"note\":<1 câu tiếng Việt: học được gì từ đối thủ, đã bỏ dòng nào vì thiếu dữ liệu>}."
)


def cta_evidence(fmt: dict, limit: int = MAX_EVIDENCE) -> list[str]:
    """Đuôi description của video outlier — nơi khối CTA thật sự nằm.

    Ưu tiên `desc_tail`; format cũ (harvest trước 2026-07-28) chưa có field này thì
    đành dùng `desc` (600 ký tự đầu) — kém hơn nhiều, nên gắn cờ ở `generate`.
    """
    out: list[str] = []
    for c in fmt.get("competitors") or []:
        for v in (c.get("outliers") or [])[:4]:
            t = (v.get("desc_tail") or "").strip()
            if not t:
                t = (v.get("desc") or "").strip()
            if len(t) < 60:
                continue
            out.append(t[-TAIL_CHARS:])
            if len(out) >= limit:
                return out
    return out


def sanitize(text: str, sub_url: str) -> tuple[str, list[str]]:
    """Điền {{SUB}} bằng URL THẬT; bỏ mọi dòng còn chỗ giữ chỗ hoặc chứa URL lạ.

    Trả (khối sạch, các dòng đã bỏ). Bỏ theo DÒNG chứ không cắt giữa câu, để phần còn
    lại vẫn đọc được. Danh sách bỏ được trả về cho user thấy — không im lặng.
    """
    sub = (sub_url or "").strip()
    keep: list[str] = []
    dropped: list[str] = []
    for line in (text or "").splitlines():
        s = _SUB_SLOT_RE.sub(sub, line)
        if _SLOT_RE.search(s):                       # chỗ giữ chỗ tool không có dữ liệu
            dropped.append(line.strip())
            continue
        foreign = [u for u in _URL_RE.findall(s) if u.strip(".,);:") != sub]
        if foreign:                                  # URL do LLM bịa
            dropped.append(line.strip())
            continue
        keep.append(s.rstrip())
    clean = re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()
    return clean, [d for d in dropped if d]


def mine_hashtags(prof: dict, ev: list[str], limit: int = 5) -> list[str]:
    """Dòng hashtag từ DỮ LIỆU THẬT — không bịa (user báo 2026-08-05: có kênh sinh CTA
    thiếu hashtag → description xuất đi trần trụi, kênh khác thì có, đội tưởng lỗi thị trường).

    Nguồn theo độ tin giảm dần:
      1. `prof.hashtag.common` — hashtag CHÍNH KÊNH MÌNH đã dùng trên video thật.
      2. Hashtag trong đuôi description đối thủ (evidence) — ưu tiên cái xuất hiện ở ≥2 mẫu
         (hashtag chung của niche); hashtag brand riêng của một kênh thường chỉ hiện 1 mẫu.
    Cả hai đều rỗng → trả rỗng, caller phải NÓI RA chứ không lặng lẽ để trống.
    """
    own = [str(h) for h in ((prof.get("hashtag") or {}).get("common") or [])
           if str(h).startswith("#")]
    if own:
        return own[:limit]
    seen_in: dict[str, int] = {}
    for t in ev or []:
        for h in set(_HASH_RE.findall(t or "")):
            seen_in[h] = seen_in.get(h, 0) + 1
    ranked = sorted(seen_in, key=lambda h: -seen_in[h])
    multi = [h for h in ranked if seen_in[h] >= 2]
    return (multi or ranked)[:limit]


def generate(prof: dict, fmt: dict) -> dict:
    """1 call LLM → khối CTA đã qua kiểm duyệt URL. Không tốn quota YouTube."""
    sub = (prof.get("sub_url") or "").strip()
    if not sub:
        raise RuntimeError("Kênh chưa khai link sub_confirmation — nhập 1 lần ở thẻ kênh rồi bấm lại.")
    if not _URL_RE.match(sub):
        raise RuntimeError(f"Link sub_confirmation không hợp lệ (phải bắt đầu bằng http): {sub[:60]}")
    ev = cta_evidence(fmt)
    if not ev:
        raise RuntimeError("Format này chưa có description đối thủ để học — thêm đối thủ vào format trước.")
    stale = not any((v.get("desc_tail") or "")
                    for c in (fmt.get("competitors") or []) for v in (c.get("outliers") or []))

    payload = {
        "competitor_cta_samples": ev,
        "niche_rules": {"must": (fmt.get("rules") or {}).get("must", []),
                        "avoid": (fmt.get("rules") or {}).get("avoid", [])},
        "description_blocks": (fmt.get("description") or {}).get("blocks", []),
        "my_channel": {"name": prof.get("channel", ""), "language": prof.get("lang", ""),
                       "niche": prof.get("niche", "")},
    }
    # GIỌNG VĂN từ bài post cộng đồng: đuôi description là CTA đã đóng khuôn, còn post cộng đồng
    # mới là chỗ đối thủ nói chuyện tự nhiên nhất — nguồn giọng chuẩn hơn cả. Trước đây
    # `fmt["community"]` sinh ra rồi chỉ nằm hiển thị trên board, không chảy vào chỗ nào viết.
    comm = fmt.get("community") or {}
    voice = {k: comm[k] for k in ("tone", "cta", "post_pattern") if comm.get(k)}
    if voice:
        payload["competitor_voice"] = voice
    before = dict(llm.USAGE)
    # temp cao → KHÔNG dính cache đĩa: bấm sinh lại phải ra bản khác để user chọn
    out = llm.call_json(_SYS_CTA + "\n" + llm.OUTPUT_LANG_RULE,
                        json.dumps(payload, ensure_ascii=False), max_tokens=900, temperature=0.6)
    raw = (out or {}).get("cta", "") if isinstance(out, dict) else ""
    if isinstance(raw, list):                        # LLM hay trả mảng dòng thay vì chuỗi
        raw = "\n".join(str(x) for x in raw)
    clean, dropped = sanitize(str(raw), sub)
    if not clean:
        raise RuntimeError("LLM không trả được khối CTA dùng được — thử bấm lại.")
    # LƯỚI HASHTAG (user báo 2026-08-05): khối CTA là nơi DUY NHẤT mang hashtag vào
    # description — LLM quên (hoặc đối thủ mẫu không có) là mọi video của kênh đó xuất đi
    # không hashtag, và không ai thấy cho tới khi so hai thị trường. Thiếu thì TỰ NỐI dòng
    # hashtag từ dữ liệu thật (mine_hashtags); không đào được thì ghi chú to, không im lặng.
    note = str((out or {}).get("note", "") or "")
    if "#" not in clean:
        hs = mine_hashtags(prof, ev)
        if hs:
            clean += "\n\n" + " ".join(hs)
            note = (note + " · " if note else "") + \
                f"LLM quên hashtag — đã tự nối {len(hs)} hashtag thật ({'kênh mình' if (prof.get('hashtag') or {}).get('common') else 'đối thủ trong niche'})."
        else:
            note = (note + " · " if note else "") + \
                "⚠ CHƯA CÓ HASHTAG: kênh chưa có video và đối thủ mẫu cũng không dùng hashtag — thêm tay 1 dòng hashtag trước khi Lưu."
    delta = {k: llm.USAGE[k] - before.get(k, 0) for k in llm.USAGE}
    delta["total"] = delta["in"] + delta["out"]
    return {"links": clean, "dropped": dropped, "note": note,
            "evidence": len(ev), "stale_evidence": stale, "usage": delta}


def build(slug: str) -> dict:
    """Vào bằng slug kênh: tự tìm Format đã gắn của kênh đó."""
    prof = library.load(slug)
    if prof is None:
        raise RuntimeError(f"Không thấy kênh: {slug}")
    fslug = (prof.get("format") or "").strip()
    if not fslug:
        raise RuntimeError("Kênh chưa gắn Format đối thủ — chọn format ở thanh trên cùng rồi bấm lại.")
    fmt = niche_format.load(fslug)
    if fmt is None:
        raise RuntimeError(f"Không thấy format đã gắn: {fslug}")
    return generate(prof, fmt)


if __name__ == "__main__":
    SUB = "https://youtube.com/@MyChan?sub_confirmation=1"

    # ── Python: chặn URL bịa, không cần LLM ──
    c, d = sanitize("Thanks for watching!\n👉 {{SUB}}\n☕ Support: https://patreon.com/bia\n#Space", SUB)
    assert SUB in c and "patreon" not in c, c
    assert d == ["☕ Support: https://patreon.com/bia"], d
    assert "#Space" in c, c

    c, d = sanitize("👉 {{SUB}}\n🎬 Next: {{NEXT_VIDEO}}", SUB)
    assert "{{" not in c and len(d) == 1, (c, d)          # slot không có dữ liệu → bỏ dòng

    c, d = sanitize("Sub here: " + SUB, SUB)
    assert c.endswith(SUB) and not d, (c, d)              # LLM viết đúng URL thật thì giữ

    c, d = sanitize("a\n\n\n\nb", SUB)
    assert c == "a\n\nb", repr(c)                         # gộp dòng trống thừa

    # ── lấy bằng chứng: ưu tiên đuôi description ──
    TAIL = ("If you made it this far, you already know what to do.\n"
            "🔔 SUBSCRIBE for a new film every Friday: https://youtube.com/@rival\n"
            "🎬 Watch the full series: https://youtube.com/playlist?list=PLrival\n"
            "#Space #Documentary #Astronomy")
    fmt = {"competitors": [{"outliers": [
        {"desc": "x" * 600, "desc_tail": TAIL},
        {"desc": "y" * 200, "desc_tail": ""},
        {"desc": "ngắn", "desc_tail": ""}]}],                # < 60 ký tự → bỏ, không thành bằng chứng
        "rules": {"must": [], "avoid": []}, "description": {"blocks": []}}
    ev = cta_evidence(fmt)
    assert len(ev) == 2 and "SUBSCRIBE" in ev[0] and ev[1].startswith("y"), ev

    # ── 1 call LLM, và URL bịa của LLM bị chặn ──
    seen = []
    llm.set_hook(lambda sy, u: (seen.append(u), json.dumps({
        "cta": "🔔 New film every Friday.\n👉 {{SUB}}\n"
               "☕ Support us: https://www.patreon.com/khong-co-that\n\n#Space #Documentary",
        "note": "Đối thủ để CTA 3 dòng, hashtag cuối."}))[1])
    r = generate({"channel": "My Chan", "lang": "English", "sub_url": SUB}, fmt)
    llm.set_hook(None)
    assert len(seen) == 1, f"phải đúng 1 call, đang {len(seen)}"
    assert "competitor_cta_samples" in seen[0], seen[0][:200]
    assert SUB in r["links"], r["links"]
    assert "patreon" not in r["links"], r["links"]         # ← luật cứng: URL bịa không lọt
    assert r["dropped"] == ["☕ Support us: https://www.patreon.com/khong-co-that"], r["dropped"]
    # usage đo bằng DELTA (không usage_reset) để không xoá sổ token của job đang chạy song song.
    # Hook test thoát sớm trong llm.call_json nên không cộng token → ở đây chỉ kiểm hình dạng;
    # số call thật đếm bằng `seen`.
    assert set(r["usage"]) >= {"calls", "in", "out", "total"} and r["usage"]["total"] == 0, r["usage"]
    base = dict(llm.USAGE)
    llm.USAGE["calls"] += 3; llm.USAGE["in"] += 10          # giả lập job khác đang chạy
    assert llm.USAGE["calls"] == base["calls"] + 3          # delta không đụng biến toàn cục
    llm.USAGE.update(base)

    # ── thiếu link sub → chặn ngay, không gọi LLM ──
    seen.clear()
    llm.set_hook(lambda sy, u: (seen.append(u), "{}")[1])
    for bad, why in (({"sub_url": ""}, "thiếu sub"), ({"sub_url": "youtube.com/@x"}, "thiếu http")):
        try:
            generate(bad, fmt)
            raise AssertionError(f"phải raise khi {why}")
        except RuntimeError:
            pass
    llm.set_hook(None)
    assert not seen, "không được gọi LLM khi input đã sai"

    print("cta.py self-test OK - 1 call, LLM viet chu, Python chan URL bia")

    # ── GIỌNG VĂN từ bài post cộng đồng phải CHẢY VÀO prompt, không chỉ nằm hiển thị ──
    seen.clear()
    llm.set_hook(lambda sy, u: (seen.append((sy, u)),
                                json.dumps({"cta": "Subscribe nhé anh em\n👉 {{SUB}}"}))[1])
    fmt_voice = {**fmt, "community": {"tone": "thân mật, xưng 'anh em'", "cta": "hỏi ngược khán giả",
                                      "post_pattern": "1 câu hỏi + 1 ảnh", "note": "bỏ qua"}}
    generate({"channel": "My Chan", "lang": "Vietnamese", "sub_url": SUB}, fmt_voice)
    sy, u = seen[-1]
    assert "competitor_voice" in u, u[:300]
    assert "anh em" in u, u[:300]
    assert "BÁM GIỌNG" in sy, sy[:400]
    assert '"note"' not in u.split("competitor_voice")[1][:200], "chỉ lấy tone/cta/post_pattern"

    seen.clear()
    llm.set_hook(lambda sy, u: (seen.append((sy, u)), json.dumps({"cta": "x\n{{SUB}}"}))[1])
    generate({"channel": "My Chan", "sub_url": SUB}, fmt)      # format chưa dán post cộng đồng
    assert "competitor_voice" not in seen[-1][1], "không có dữ liệu thì đừng bịa field"
    llm.set_hook(None)
    print("cta.py self-test OK - giong van tu post cong dong chay vao prompt sinh CTA")

    # ── LƯỚI HASHTAG (user báo 2026-08-05: kênh sinh CTA không hashtag → description trần) ──
    assert mine_hashtags({"hashtag": {"common": ["#MyBrand", "#Docu"]}}, ["#X #Y"]) == \
        ["#MyBrand", "#Docu"], "hashtag kênh mình phải THẮNG"
    evs = ["... #Space #Documentary", "... #Space #Documentary #BrandRieng", "... #Space"]
    m = mine_hashtags({}, evs)
    assert m[0] == "#Space" and "#Documentary" in m and "#BrandRieng" not in m, \
        f"hashtag ≥2 mẫu mới là của niche, đang {m}"
    assert mine_hashtags({}, []) == [], "không dữ liệu → rỗng, không bịa"
    # LLM quên hashtag → generate tự nối từ đuôi đối thủ (TAIL có #Space #Documentary #Astronomy)
    llm.set_hook(lambda sy, u: json.dumps({"cta": "Thanks for watching!\n👉 {{SUB}}"}))
    r_no = generate({"channel": "My Chan", "sub_url": SUB}, fmt)
    llm.set_hook(None)
    assert "#" in r_no["links"], r_no["links"]
    assert r_no["links"].index("{{") < 0 if "{{" in r_no["links"] else True
    assert "hashtag" in r_no["note"], r_no["note"]           # phải NÓI đã tự nối, không im lặng
    # ...còn LLM đã viết hashtag thì KHÔNG đụng gì
    llm.set_hook(lambda sy, u: json.dumps({"cta": "👉 {{SUB}}\n#Space"}))
    r_has = generate({"channel": "My Chan", "sub_url": SUB}, fmt)
    llm.set_hook(None)
    assert r_has["links"].count("#Space") == 1 and "tự nối" not in r_has["note"], r_has
    print("cta.py self-test OK - luoi hashtag: kenh minh > doi thu >=2 mau, thieu thi tu noi + noi ra")
