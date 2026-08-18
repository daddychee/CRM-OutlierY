"""Module 1 — Profile Description Library (kiểu Author Extract).

Nhập URL kênh → Python tự fetch video (30–50 mới nhất) → phân tích PHONG CÁCH Description:
- skeleton (thứ tự block) + số ký tự mỗi block
- icon / ký tự đặc biệt dùng
- CÁCH ĐẶT HASHTAG (số lượng, vị trí, kiểu, hashtag phổ biến, #brand)
- 1 description điển hình

Python: thống kê/regex (hashtag, ký tự đặc biệt, độ dài). LLM: skeleton + guide + mô tả block.
Guide/mô tả viết TIẾNG VIỆT (UI-facing); ví dụ hashtag/nội dung giữ nguyên English.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

from . import common, library, llm, roles

_SYS = (
    "Bạn phân tích PHONG CÁCH Description của 1 kênh YouTube (để làm guide cho người viết). "
    "Cho 1 description điển hình + vài mẫu + hint thống kê, trả JSON: {"
    "\"skeleton\":[block theo thứ tự phổ biến, chọn từ HOOK|SUMMARY|CHAPTERS|CTA|LINKS|HASHTAG],"
    "\"note\":<lệch gì so với standard>,"
    "\"blocks\":[{\"block\":<tên>,\"chars\":<ước lượng số ký tự>,\"desc\":<mô tả ngắn nội dung/phong cách block>}],"
    "\"hashtag_guide\":<CÁCH họ đặt hashtag: bao nhiêu cái, đặt ở đâu, kiểu chữ, thứ tự (chủ đề rộng trước hay sau?), "
    "có #brand kênh không, có đặt hashtag trong body không>}. "
    "Phần note/desc/hashtag_guide viết TIẾNG VIỆT; giữ nguyên ví dụ hashtag/nội dung tiếng Anh."
)
_HASH_RE = re.compile(r"#\w+")
_URL_RE = re.compile(r"https?://")
_TS_RE = re.compile(r"\b\d{1,2}:\d{2}\b")


# ── Python: thống kê phong cách ──
def special_chars(descs: list[str]) -> list[str]:
    """Icon/emoji/ký tự đặc biệt kênh dùng (bỏ chữ/số/dấu — kể cả tiếng Việt)."""
    seen: Counter = Counter()
    for d in descs:
        for ch in d:
            if ord(ch) < 0x80:
                continue
            if unicodedata.category(ch)[0] in ("L", "M", "N"):
                continue
            seen[ch] += 1
    return [c for c, _ in seen.most_common(24)]


def hashtag_stats(descs: list[str]) -> dict:
    counts, cnt, place = [], Counter(), Counter()
    for d in descs:
        tags = _HASH_RE.findall(d)
        if not tags:
            continue
        counts.append(len(tags))
        cnt.update(tags)
        lines = [ln for ln in d.strip().splitlines() if ln.strip()]
        if lines and _HASH_RE.search(lines[-1]):
            place["cuối description"] += 1
        if lines and _HASH_RE.search(lines[0]):
            place["đầu description"] += 1
    return {
        "avg_count": round(sum(counts) / len(counts), 1) if counts else 0,
        "range": [min(counts), max(counts)] if counts else [0, 0],
        "placement": place.most_common(1)[0][0] if place else "không rõ",
        "common": [t for t, _ in cnt.most_common(8)],
        "videos_with_hashtag": len(counts),
    }


def pick_example(descs: list[str]) -> str:
    s = sorted(descs, key=len)
    return s[len(s) // 2] if s else ""


def _hints(descs: list[str]) -> dict:
    return {"n": len(descs),
            "with_timestamps": sum(bool(_TS_RE.search(d)) for d in descs),
            "with_urls": sum(bool(_URL_RE.search(d)) for d in descs),
            "with_hashtags": sum(bool(_HASH_RE.search(d)) for d in descs)}


# ── LLM: skeleton + guide ──
def infer(example: str, descs: list[str]) -> dict:
    user = json.dumps({"typical_example": example[:1500],
                       "samples": [d[:500] for d in descs[:5]],
                       "hints": _hints(descs)}, ensure_ascii=False)
    out = llm.call_json(_SYS, user, max_tokens=1500, temperature=0.2)
    return out if isinstance(out, dict) else {}


def _gen_code(channel: str, existing: set) -> str:
    init = "".join(w[0] for w in re.findall(r"[A-Za-z]+", channel)[:2]).upper() or "CH"
    i = 1
    while f"{init}-{i:02d}" in existing:
        i += 1
    return f"{init}-{i:02d}"


def extract(body: dict, status: dict) -> dict:
    keys = common.load_keys()
    llm.usage_reset()
    src = body.get("channel_url") or body.get("urls", "")
    status["step"] = "tìm kênh…"
    ch = common.resolve_channel_id(src, keys)
    if not ch:
        raise RuntimeError("Không nhận diện được kênh — dùng URL /channel/…, @handle, hoặc 1 video của kênh")
    status["step"] = "lấy video của kênh…"
    ids = common.channel_video_ids(ch, keys, limit=int(body.get("limit", 30)))
    items = common.fetch_videos(ids, keys, parts="snippet") if ids else []
    if ids:
        status["step"] = f"đọc description ({len(ids)} video)…"
    descs = [it["snippet"].get("description", "") for it in items
             if it.get("snippet", {}).get("description", "").strip()]
    # KÊNH MỚI TINH (chưa đăng video, hoặc video chưa viết description) VẪN phải tạo được hồ sơ:
    # mạng lưới kênh luôn có kênh vừa lập, cần khai niche/lang/sub_url/Format và sinh metadata
    # cho video ĐẦU TIÊN — mà lúc đó đúng là chưa có gì để học. Chặn ở đây là khoá luôn cửa vào.
    # Skeleton để RỖNG → niche_format.resolve() rơi xuống skeleton của Format đã gắn.
    no_videos = not descs
    channel = body.get("channel") or (items[0]["snippet"].get("channelTitle") if items else None) \
        or common.channel_title(ch, keys)
    existing_codes, match_code, match_slug, keep = set(), None, "", {}
    match_prof = None
    if common.profiles_dir().exists():
        for f in common.profiles_dir().glob("*.json"):
            try:
                p = common.read_json(f)
            except Exception:                             # noqa: BLE001
                continue
            existing_codes.add(p.get("code"))
            if p.get("channel_id") == ch or (not p.get("channel_id") and p.get("channel") == channel):
                match_code = p.get("code")                # cùng kênh (id, hoặc tên nếu profile cũ chưa có id) → CẬP NHẬT
                match_slug = f.stem                       # GIỮ nguyên tên file đang có (xem chú thích ở `sl`)
                keep = library.user_meta(p)               # giữ niche/lang/link/anh em user đã khai
                match_prof = p
    # ── EXTRACT LẠI MỘT KÊNH ĐÃ CÓ = GHI ĐÈ HỒ SƠ ĐÓ, nên phải hỏi AI LÀ CHỦ ────────────
    # Lỗ này chỉ mở ra từ 2026-08-02, lúc Seo được cấp `extract_chan`: trước đó Seo không
    # extract được gì nên không ai tới được đây. Quyền sở hữu KHÔNG bị cướp (`merge_user` giữ
    # `created_by`), nhưng skeleton/blocks/n_videos của người khác thì bị viết lại, và tiêu
    # quota + 1 call LLM của cả nhóm. Đó vẫn là GHI lên kênh không phải của mình.
    # Chặn Ở ĐÂY chứ không ở `_scope_deny`: server không biết kênh đích là cái nào cho tới
    # khi `resolve_channel_id` chạy xong. Đổi lại, chốt này nằm TRƯỚC call LLM (phần đắt
    # nhất) nên chỉ tốn ~2 unit quota rồi dừng.
    _me = body.get("_me") or {}
    if match_prof is not None and _me and not roles.can_write_profile(_me, match_prof):
        ow = (match_prof.get("created_by") or "").strip()
        raise RuntimeError(
            f"Kênh '{match_prof.get('channel') or match_slug}' đã có trong thư viện và "
            + (f"do {ow} tạo" if ow else "chưa có tài khoản nào đứng tên chủ")
            + ". Bạn chỉ extract lại được kênh do CHÍNH MÌNH tạo — nhờ Leader / Manager / "
              "Owner bấm '👤 Đổi chủ kênh' để nhận kênh này, rồi chạy lại.")
    # MÃ KÊNH NHẬP TAY lúc tạo (user chốt 2026-08-04) — nhưng kênh ĐÃ CÓ thì mã cũ THẮNG:
    # đổi mã chỉ đi qua đường "Sửa thông tin kênh" (có luật vai: Seo 1 lần duy nhất), để
    # re-extract không thành cửa sau đổi mã vô hạn. Mã gõ tay trùng mã kênh khác → chặn
    # ngay TRƯỚC call LLM, nói rõ trùng với ai (mã là khoá tra cứu của user, trùng là loạn sổ).
    manual = str(body.get("code") or "").strip()[:24]
    if manual and not match_code and manual in existing_codes:
        raise RuntimeError(f"Mã kênh '{manual}' đã có kênh khác dùng — chọn mã khác "
                           "(mỗi kênh một mã riêng để tra cứu lịch sử không lẫn)")
    code = match_code or manual or _gen_code(channel, existing_codes)

    example = pick_example(descs)
    if no_videos:
        status["step"] = "kênh chưa có video — tạo hồ sơ trống…"
        ai = {}                                           # không có gì để phân tích → KHÔNG gọi LLM, 0 token
    else:
        status["step"] = "phân tích phong cách…"
        ai = infer(example, descs)
    prof = {
        "channel": channel, "channel_id": ch, "code": code, "n_videos": len(descs),
        "no_videos": no_videos,
        # kênh có video mà LLM im lặng → vẫn dùng standard; kênh CHƯA có video → để rỗng,
        # đừng bịa skeleton cho kênh chưa tồn tại nội dung (Format của đối thủ mới là nguồn đúng)
        "skeleton": ai.get("skeleton") or ([] if no_videos else ["HOOK", "SUMMARY", "CHAPTERS", "CTA", "HASHTAG"]),
        "deviation_vs_standard": ai.get("note", ""),
        "blocks": ai.get("blocks", []),
        "special_chars": special_chars(descs),
        "hashtag": {**hashtag_stats(descs), "guide": ai.get("hashtag_guide", "")},
        "example": example[:1500],
        "example_chars": len(example),
    }
    # Đã nhận ra là CÙNG kênh thì giữ NGUYÊN tên file cũ. Tính lại slug từ tên kênh sẽ đẻ file
    # thứ hai khi tên đổi — mà ô "Tên kênh" trong form extract cho user gõ tay, và YouTube cũng
    # cho đổi tên kênh. Hậu quả: 1 kênh hiện thành 2 thẻ, trùng `code`, lịch sử run vỡ đôi.
    # Slug chỉ là ID nội bộ (library suy từ tên file) nên giữ tên cũ là đúng, không phải lười.
    sl = match_slug or common.slug(channel + "-" + code)
    library.merge_user(prof, keep)                         # profile cũ trước…
    library.merge_user(prof, body)                         # …form extract (nếu có nhập) ghi đè
    # Đây là kênh CỦA USER và ta vừa lấy được channel_id thật → dựng luôn link đăng ký, khỏi bắt
    # họ đi copy. Chỉ điền khi còn trống: user gõ tay thì tôn trọng bản của họ.
    # CHỈ nhận kết quả là URL thật: `sub_url_from` trả nguyên input khi không nhận ra, nên
    # channel_id lạ (id giả, kênh lỗi) sẽ nhét thẳng chuỗi rác vào ô link nếu không chặn.
    if not (prof.get("sub_url") or "").strip():
        auto = common.sub_url_from(ch)
        if auto.startswith("http"):
            prof["sub_url"] = auto
    prof["updated"] = library.now_iso()
    prof["usage"] = status["usage"] = llm.usage_snapshot()
    common.write_json(common.profiles_dir(create=True) / f"{sl}.json", prof)
    # slug gắn SAU khi ghi file: slug suy ra từ tên file, ghi vào JSON là lệch schema
    # (library.update cố tình pop nó ra). Board cần biết profile NÀO vừa được ghi vì
    # dedup theo channel_id xảy ra ở đây — extract lại kênh cũ là CẬP NHẬT, không sinh slug mới.
    prof["slug"] = sl
    return prof


if __name__ == "__main__":                                # self-test offline (seed giả)
    descs = [
        "A cinematic hook line about space.\n\nA summary paragraph explaining the video.\n\n👉 Subscribe https://x\n#Space #BlackHole #Cosmos",
        "Another hook — dramatic.\n\nMore summary text here.\n\n🔗 https://y\n#BlackHole #Astrophysics #Space #Cosmos",
        "Third hook.\n\nSummary.\n\n#Space #BlackHole",
    ]
    assert "👉" in special_chars(descs) and "—" in special_chars(descs), special_chars(descs)
    hs = hashtag_stats(descs)
    assert hs["placement"] == "cuối description" and hs["videos_with_hashtag"] == 3, hs
    assert hs["common"][0] in ("#Space", "#BlackHole"), hs
    assert _gen_code("Cosmic Lens", set()) == "CL-01" and _gen_code("Cosmic Lens", {"CL-01"}) == "CL-02"
    llm.set_hook(lambda s, u: '{"skeleton":["HOOK","SUMMARY","CTA","HASHTAG"],"note":"bỏ chapters","blocks":[{"block":"HOOK","chars":40,"desc":"câu điện ảnh"}],"hashtag_guide":"~3 hashtag ở cuối, có #brand"}')
    ai = infer(pick_example(descs), descs)
    llm.set_hook(None)
    assert ai["skeleton"][0] == "HOOK" and ai["hashtag_guide"], ai
    print("profile.py self-test OK · special", special_chars(descs), "· hashtag", hs["placement"], hs["avg_count"])

    # ── extract(): cùng channel_id thì CẬP NHẬT ĐÚNG file cũ, dù tên kênh đổi ──
    # Trước đây slug tính lại từ tên kênh ⇒ gõ tên khác trong form = đẻ profile thứ 2,
    # trùng `code`, lịch sử run vỡ đôi. Đây là bug im lặng nên phải có test chốt.
    import tempfile
    from pathlib import Path as _P

    with tempfile.TemporaryDirectory() as _tmp:
        common.PROFILES = _P(_tmp) / "profiles"
        common.load_keys = lambda: ["k"]
        common.resolve_channel_id = lambda s, k: "UC_SAME"
        common.channel_video_ids = lambda c, k, limit=30: ["v1", "v2", "v3"]
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Cosmic Lens"}} for d in descs]
        llm.set_hook(lambda s, u: '{"skeleton":["HOOK"],"note":"","blocks":[],"hashtag_guide":"x"}')

        p1 = extract({"channel_url": "https://youtube.com/channel/UC_SAME"}, {})
        assert p1["slug"] == "cosmic-lens-cl-01", p1["slug"]
        p1b = common.read_json(common.profiles_dir() / "cosmic-lens-cl-01.json")
        assert p1b["channel_id"] == "UC_SAME"

        # user gõ TÊN KHÁC vào ô "Tên kênh" của form extract
        p2 = extract({"channel_url": "https://youtube.com/channel/UC_SAME",
                      "channel": "Tên Mới Toanh"}, {})
        files = sorted(f.name for f in common.profiles_dir().glob("*.json"))
        assert files == ["cosmic-lens-cl-01.json"], f"phải CẬP NHẬT 1 file, đang có {files}"
        assert p2["slug"] == "cosmic-lens-cl-01" and p2["code"] == "CL-01", p2
        assert p2["channel"] == "Tên Mới Toanh", p2       # tên đổi theo, chỉ tên FILE giữ nguyên

        # kênh KHÁC thì vẫn phải ra profile mới
        common.resolve_channel_id = lambda s, k: "UC_OTHER"
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Outland"}} for d in descs]
        p3 = extract({"channel_url": "https://youtube.com/channel/UC_OTHER"}, {})
        assert p3["slug"] == "outland-o-01", p3["slug"]
        assert len(list(common.profiles_dir().glob("*.json"))) == 2

        # ── MÃ KÊNH NHẬP TAY lúc tạo (04/08): tôn trọng mã gõ; trùng → chặn; re-extract giữ mã cũ ──
        common.resolve_channel_id = lambda s, k: "UC_MANUAL"
        p4 = extract({"channel_url": "https://youtube.com/channel/UC_MANUAL",
                      "channel": "Kênh Gõ Mã", "code": "IU-07"}, {})
        assert p4["code"] == "IU-07", p4["code"]
        try:
            common.resolve_channel_id = lambda s, k: "UC_DUP"
            extract({"channel_url": "https://youtube.com/channel/UC_DUP",
                     "channel": "Kênh Trùng Mã", "code": "IU-07"}, {})
            raise AssertionError("mã gõ tay trùng kênh khác phải bị CHẶN")
        except RuntimeError as e:
            assert "IU-07" in str(e), e
        common.resolve_channel_id = lambda s, k: "UC_MANUAL"   # re-extract gửi mã KHÁC → mã cũ THẮNG
        p5 = extract({"channel_url": "https://youtube.com/channel/UC_MANUAL", "code": "XX-99"}, {})
        assert p5["code"] == "IU-07", "re-extract không được thành cửa sau đổi mã"
        llm.set_hook(None)

    print("profile.py self-test OK - re-extract giu nguyen file du doi ten kenh, ma kenh nhap tay + chan trung")

    # ── KÊNH MỚI TINH: chưa đăng video vẫn phải tạo được hồ sơ (0 token LLM) ──
    with tempfile.TemporaryDirectory() as _tmp:
        common.PROFILES = _P(_tmp) / "profiles"
        common.load_keys = lambda: ["k"]
        common.resolve_channel_id = lambda s, k: "UC_NEW"
        common.channel_video_ids = lambda c, k, limit=30: []      # kênh 0 video
        common.fetch_videos = lambda ids, k, parts="snippet": []
        common.channel_title = lambda c, k: "Kênh Mới"
        _hit = []
        llm.set_hook(lambda s, u: (_hit.append(u), "{}")[1])

        pn = extract({"channel_url": "https://youtube.com/channel/UC_NEW", "niche": "Space",
                      "lang": "English", "sub_url": "https://youtube.com/@New?sub_confirmation=1"}, {})
        assert not _hit, "kênh trống thì KHÔNG được gọi LLM (không có gì để phân tích)"
        assert pn["no_videos"] is True and pn["n_videos"] == 0, pn
        assert pn["skeleton"] == [], pn["skeleton"]       # rỗng → resolve() rơi xuống Format
        assert pn["channel"] == "Kênh Mới" and pn["channel_id"] == "UC_NEW", pn
        assert pn["niche"] == "Space" and pn["sub_url"].startswith("https://"), pn

        # skeleton rỗng phải rơi xuống Format của đối thủ, không phải standard
        from . import niche_format
        eff = niche_format.resolve(common.read_json(common.profiles_dir() / f"{pn['slug']}.json"),
                                   {"description": {"skeleton": ["HOOK", "LINKS", "HASHTAG"]},
                                    "name": "Doc dài"})
        assert eff["skeleton"] == ["HOOK", "LINKS", "HASHTAG"] and eff["source"] == "niche", eff

        # sau khi kênh đăng video → extract lại phải NÂNG CẤP đúng hồ sơ đó, không đẻ file mới
        common.channel_video_ids = lambda c, k, limit=30: ["v1", "v2", "v3"]
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Kênh Mới"}} for d in descs]
        llm.set_hook(lambda s, u: '{"skeleton":["HOOK","SUMMARY"],"note":"","blocks":[],"hashtag_guide":"x"}')
        pu = extract({"channel_url": "https://youtube.com/channel/UC_NEW"}, {})
        assert pu["slug"] == pn["slug"], (pu["slug"], pn["slug"])
        assert pu["no_videos"] is False and pu["skeleton"] == ["HOOK", "SUMMARY"], pu
        assert pu["niche"] == "Space", pu                 # field user khai KHÔNG bị mất khi nâng cấp
        assert len(list(common.profiles_dir().glob("*.json"))) == 1
        llm.set_hook(None)

    print("profile.py self-test OK - kenh chua up video van tao duoc ho so, len video thi tu nang cap")

    # ── gắn Format + sub_url NGAY LÚC TẠO KÊNH (trước đây overlay không có ô, phải sửa lại sau) ──
    with tempfile.TemporaryDirectory() as _tmp3:
        common.PROFILES = _P(_tmp3) / "profiles"
        common.load_keys = lambda: ["k"]
        common.resolve_channel_id = lambda s, k: "UC_NEW2"
        common.channel_video_ids = lambda c, k, limit=30: ["v1"]
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Kênh Có Format"}} for d in descs]
        llm.set_hook(lambda s, u: '{"skeleton":["HOOK"],"note":"","blocks":[],"hashtag_guide":"x"}')
        pf = extract({"channel_url": "https://youtube.com/channel/UC_NEW2",
                      "niche": "Space", "lang": "English",
                      "format": "space-cosmic-lens",
                      "sub_url": "https://youtube.com/@X?sub_confirmation=1",
                      "links": "👉 Sub"}, {})
        assert pf["format"] == "space-cosmic-lens", pf
        assert pf["sub_url"].startswith("https://"), pf
        assert pf["links"] == "👉 Sub" and pf["niche"] == "Space", pf
        on_disk = common.read_json(common.profiles_dir() / f"{pf['slug']}.json")
        assert on_disk["format"] == "space-cosmic-lens" and on_disk["sub_url"], on_disk

        # bỏ trống 2 ô đó vẫn tạo được kênh bình thường (user gắn sau)
        common.resolve_channel_id = lambda s, k: "UC_NEW3"
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Kênh Trống"}} for d in descs]
        p0 = extract({"channel_url": "https://youtube.com/channel/UC_NEW3"}, {})
        # channel_id giả (không đúng dạng UC…) → KHÔNG được nhét chuỗi rác vào ô link
        assert p0.get("format", "") == "" and p0.get("sub_url", "") == "", p0
        llm.set_hook(None)

    # ── sub_url TỰ DỰNG từ channel_id, khỏi bắt user đi copy link ──
    with tempfile.TemporaryDirectory() as _tmp4:
        common.PROFILES = _P(_tmp4) / "profiles"
        common.load_keys = lambda: ["k"]
        common.channel_video_ids = lambda c, k, limit=30: ["v1"]
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Auto Sub"}} for d in descs]
        llm.set_hook(lambda s, u: '{"skeleton":["HOOK"],"note":"","blocks":[],"hashtag_guide":"x"}')
        UCA = "UC" + "q" * 22
        common.resolve_channel_id = lambda s, k: UCA

        pa = extract({"channel_url": "https://youtube.com/@AutoSub"}, {})
        assert pa["sub_url"] == f"https://www.youtube.com/channel/{UCA}?sub_confirmation=1", pa["sub_url"]

        # user tự gõ thì TÔN TRỌNG bản của họ, không đè bằng bản tự dựng
        common.resolve_channel_id = lambda s, k: "UC" + "w" * 22
        common.fetch_videos = lambda ids, k, parts="snippet": [
            {"snippet": {"description": d, "channelTitle": "Tay Nhap"}} for d in descs]
        pb = extract({"channel_url": "https://youtube.com/@TayNhap",
                      "sub_url": "https://www.youtube.com/@Rieng"}, {})
        assert pb["sub_url"] == "https://www.youtube.com/@Rieng?sub_confirmation=1", pb["sub_url"]
        llm.set_hook(None)

    print("profile.py self-test OK - gan Format + sub_url ngay luc tao kenh, bo trong cung duoc · sub_url tu dung tu channel_id")
