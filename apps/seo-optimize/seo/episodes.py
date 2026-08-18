"""Module 5 — TẬP: hồ sơ 1 tập nội dung, gom theo niche.

Vì sao cần: đầu vào của 1 lần generate (video mẫu chính + phụ, kịch bản, SRT, danh sách kênh)
trước đây chỉ nằm trong ô nhập của overlay rồi mất. `runs/<run>/result.json` giữ `main_url`
và `_brief` nhưng KHÔNG giữ `sub_urls`/`script`/`srt` ⇒ mở lại run cũ không sinh lại được,
board phải bảo user "dán lại kịch bản/SRT". Tập giữ đúng những thứ đó.

Tập là ĐƠN VỊ CÔNG VIỆC: 1 tập → chọn Format đối thủ (qua kênh) → sinh package SEO cho N kênh.
Thuần đọc/ghi JSON — KHÔNG gọi LLM, KHÔNG tốn quota. Việc sinh vẫn do pipeline/episode lo.

Self-test:  python -m seo.episodes
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from . import common, library

# Ô nhập của user — re-generate KHÔNG được đụng vào (chỉ `runs` được tool ghi thêm).
INPUT_FIELDS = ("name", "code", "niche", "note", "main_url", "sub_urls", "script", "srt",
                "hook", "chapters", "channels", "title_bank", "use_bank")


def ascii_slug(text: str) -> str:
    """Slug KHÔNG DẤU cho tên file.

    `common.slug` dùng `\\w` nên chữ tiếng Việt có dấu lọt qua ⇒ tên file kiểu
    `quái-vật-giữa-ngân-hà.json`. Tên kênh/format phần lớn là ASCII nên chưa lộ, nhưng tên TẬP
    thì user gõ tiếng Việt là chính. Bỏ dấu ở đây thay vì sửa `common.slug` — sửa chỗ đó sẽ
    làm lệch slug của `profiles/`+`formats/` đã tồn tại trên đĩa.
    """
    t = (text or "").replace("Đ", "D").replace("đ", "d")
    t = "".join(c for c in unicodedata.normalize("NFD", t)
                if unicodedata.category(c) != "Mn")        # bỏ dấu thanh/dấu mũ
    return common.slug(t)


def _free_slug(base: str) -> str:
    """Slug còn TRỐNG cho tập MỚI.

    Chỉ gọi khi tạo mới (sửa tập thì board gửi kèm `slug`). Bản trước còn nhánh
    "trùng tên = coi như tập đang sửa" → tạo tập mới trùng tên là GHI ĐÈ IM LẶNG tập cũ, mất
    sạch kịch bản/SRT và còn thừa kế `runs`+`created` của nó. Mà nhánh đó chưa từng phục vụ
    luồng sửa nào (luồng sửa không đi qua đây) — nó chỉ gây hại. Trùng tên giờ ra `-2`, `-3`…
    """
    sl, i = base, 2
    while load(sl) is not None:
        sl, i = f"{base}-{i}", i + 1
    return sl


def episodes_dir(*, create: bool = False) -> Path:
    d = common.ROOT / "episodes"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def path_of(slug: str) -> Path:
    return episodes_dir() / f"{common.slug(slug)}.json"


def load(slug: str) -> dict | None:
    """File hỏng/không phải object → coi như KHÔNG CÓ, đừng ném lỗi.

    `load` bị gọi từ `attach_run` (chạy trong thread pipeline) và `_free_slug`; ném ở đây thì
    1 file rác trong episodes/ đủ làm hỏng nguyên lần generate đã tốn quota."""
    f = path_of(slug)
    if not f.exists():
        return None
    try:
        d = common.read_json(f)
    except Exception:                                      # noqa: BLE001 — JSON hỏng
        return None
    if not isinstance(d, dict):                            # `[]`, `"str"`, `null` vẫn là JSON hợp lệ
        return None
    d["slug"] = f.stem
    return d


def all_episodes(errors: list | None = None) -> list[dict]:
    """Mọi tập, mới nhất trước. Board tự gom nhóm theo field `niche`.

    File hỏng vẫn bỏ qua, nhưng PHẢI ghi vào `errors`. Tập chứa KỊCH BẢN + SRT user dán tay,
    `runs/` không lưu — nó biến mất im lặng là user tưởng mất trắng và gõ lại từ đầu."""
    out = []
    d = episodes_dir()
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            e = common.read_json(f)
        except Exception as e:                             # noqa: BLE001 — 1 file hỏng không được giết cả tab
            if errors is not None:
                errors.append({"kind": "tập", "file": f.name, "error": str(e)[:200]})
            continue
        if not isinstance(e, dict):                        # `[]`/`"x"`/`null` parse được nhưng không dùng được
            continue
        e["slug"] = f.stem
        e.setdefault("channels", [])
        e.setdefault("runs", [])
        for k in INPUT_FIELDS:
            e.setdefault(k, [] if k == "channels" else "")
        e.setdefault("code", "")               # tập tạo trước khi có mã → board hiện rỗng, không vỡ
        out.append(e)
    out.sort(key=lambda x: x.get("updated") or x.get("created") or "", reverse=True)
    return out


def _niche_of(channels: list[str]) -> str:
    """Suy niche từ kênh đầu tiên được tick — user không phải gõ lại thứ đã khai ở kênh."""
    for sl in channels:
        p = library.load(sl)
        if p and (p.get("niche") or "").strip():
            return p["niche"].strip()
    return ""


def gen_code(niche: str, existing: set) -> str:
    """Mã tập: chữ đầu của NICHE + số thứ tự trong chính niche đó (`LI-01`, `SP-03`).

    Cùng khuôn với mã kênh (`profile._gen_code`) để nhìn là biết ngay cùng một hệ. Đánh số THEO
    NICHE chứ không đánh số toàn cục: mạng lưới làm song song nhiều niche, đánh số chung thì mã
    nhảy cóc vô nghĩa (Life In 01, 05, 09…).

    Cấp MỘT LẦN lúc tạo rồi giữ nguyên trong file — KHÔNG tính lại theo vị trí, vì xoá một tập giữa
    chừng là mọi tập sau bị đánh số lại, mã đã dán lên video thật thành sai.
    """
    import re as _re
    words = _re.findall(r"[A-Za-z]+", niche or "")
    init = "".join(w[0] for w in words[:2]).upper()
    if len(init) < 2 and words:            # niche MỘT TỪ ("Space") → lấy 2 chữ đầu, đừng để mã 1 ký tự
        init = words[0][:2].upper()
    init = init or "TAP"
    i = 1
    while f"{init}-{i:02d}" in existing:
        i += 1
    return f"{init}-{i:02d}"


def save(body: dict) -> dict:
    """Tạo mới hoặc cập nhật 1 tập. `slug` rỗng = tạo mới (suy từ tên)."""
    name = (body.get("name") or "").strip()
    if not name:
        raise RuntimeError("Tập phải có tên (vd: 'Sagittarius A*')")
    chans = [common.slug(c) for c in (body.get("channels") or []) if c]
    # KHÔNG viết `ascii_slug(x) or ascii_slug(name)`: common.slug("") trả "x" (fallback của nó),
    # luôn truthy ⇒ mọi tập mới đều ghi đè nhau vào x.json. Phải xét chuỗi rỗng TRƯỚC khi slug.
    raw = (body.get("slug") or "").strip()
    sl = ascii_slug(raw) if raw else _free_slug(ascii_slug(name))
    old = load(sl) or {}
    ep = dict(old)
    ep.update({
        "name": name,
        # Thứ tự: user GÕ TAY thắng → suy từ kênh đã tick → giữ giá trị cũ.
        # Trước đây `old` đứng trên `_niche_of`: tập tạo lúc kênh chưa khai niche sẽ kẹt mãi ở
        # "Chưa phân loại", khai niche cho kênh rồi lưu lại tập cũng không kéo lên được.
        "niche": (body.get("niche") or "").strip() or _niche_of(chans) or old.get("niche", ""),
        "note": (body.get("note") or "").strip(),
        "main_url": (body.get("main_url") or "").strip(),
        "sub_urls": body.get("sub_urls") or "",
        "script": body.get("script") or "",
        "srt": body.get("srt") or "",
        # User tự viết hook mở đầu + tự đặt tên chapter → Python dùng nguyên văn, không hỏi LLM
        "hook": body.get("hook") or "",
        "chapters": body.get("chapters") or "",
        # Kho title thêm RIÊNG cho tập này + công tắc dùng kho mở rộng. `save` ghi bằng danh
        # sách field CỐ ĐỊNH (không lặp INPUT_FIELDS) nên thêm field mới mà quên chỗ này là
        # user gõ xong bấm Lưu rồi mất trắng, không báo lỗi gì.
        "title_bank": body.get("title_bank") or "",
        "use_bank": bool(body.get("use_bank", old.get("use_bank", True))),
        "channels": chans,
        "runs": old.get("runs") or [],
        "created": old.get("created") or library.now_iso(),
        "updated": library.now_iso(),
    })
    # MÃ TẬP LÀ CỦA USER (user chốt 2026-07-30: "tôi muốn đặt mã theo quy ước của tôi").
    # User gõ gì thì giữ NGUYÊN VĂN, kể cả trùng mã tập khác — quy ước của họ, tool không phán.
    # Chỉ khi user để TRỐNG và tập cũng chưa có mã thì mới gợi ý một mã cho đỡ vô danh.
    typed = (body.get("code") or "").strip()
    ep["code"] = typed or (old.get("code") or "").strip()
    if not ep["code"]:
        taken = {(e.get("code") or "").strip() for e in all_episodes() if e.get("slug") != sl}
        ep["code"] = gen_code(ep.get("niche", ""), taken)
    ep.pop("slug", None)                                   # slug suy từ tên file, không lưu trong file
    common.write_json(episodes_dir(create=True) / f"{sl}.json", ep)
    ep["slug"] = sl
    return ep


def attach_run(slug: str, run: str) -> None:
    """Gắn 1 run vào tập. Gọi sau khi pipeline chạy xong — im lặng nếu tập không còn."""
    # KHÔNG `common.slug(slug or "")` rồi mới kiểm: common.slug("") trả "x" (luôn truthy) ⇒ guard
    # thành code chết, và mọi run không đi từ Tập (vd nút ↻ Sinh lại) bị gắn vào tập slug "x".
    raw, run = (slug or "").strip(), (run or "").strip()
    if not raw or not run:
        return
    sl = common.slug(raw)
    ep = load(sl)
    if ep is None:
        return
    runs = [r for r in (ep.get("runs") or []) if r != run]
    ep["runs"] = [run, *runs]                              # mới nhất lên đầu
    ep["updated"] = library.now_iso()
    ep.pop("slug", None)
    common.write_json(path_of(sl), ep)


def delete(slug: str) -> str | None:
    """Xoá tập → vào thùng rác. Trả token để hoàn tác (None nếu không có gì để xoá)."""
    return common.trash(path_of(slug), "episodes")


def run_history(ep: dict, limit: int = 12) -> list[dict]:
    """LỊCH SỬ TỪNG LẦN SINH của MỘT tập — mới nhất trước.

    Vì sao cần (user 2026-08-01): trước đó thẻ tập chỉ có nút "Mở kết quả mới nhất" đọc
    `runs[0]`. Một nút, một đích — không có cách nào mở lại một lần sinh CŨ để đối chiếu,
    trong khi `runs[]` giữ tới 14 lần. User bắt được đúng lúc nút đó mở nhầm sang tập khác.

    **ĐỐI CHIẾU VIDEO ID, không tin `runs[]`**: id run từng có mặc định dùng chung (`"gen"`),
    nên `runs[]` của tập này có thể chứa run của tập khác. Kết quả nào không cùng video mẫu
    thì gắn cờ `lac=True` để board hiện đỏ chứ không im lặng bỏ — user cần biết nó tồn tại.
    Thuần đọc đĩa, không LLM, không quota.
    """
    mine = common.extract_video_id(ep.get("main_url", "") or "")
    out: list[dict] = []
    for run in (ep.get("runs") or [])[:limit]:
        f = common.run_dir(run) / "result.json"
        if not f.exists():
            out.append({"run": run, "mat": True})
            continue
        try:
            r = common.read_json(f)
        except Exception:                                  # noqa: BLE001
            out.append({"run": run, "hong": True})
            continue
        chans = r.get("channels") or []
        titles = ([(c.get("title") or {}).get("text", "") for c in chans] if chans
                  else [t.get("text", "") for t in (r.get("titles") or [])])
        rv = common.extract_video_id(r.get("main_url", "") or "")
        out.append({"run": run, "created": r.get("created", ""),
                    "exported_at": r.get("exported_at", ""),
                    "n_channels": len(chans), "titles": [x for x in titles if x][:4],
                    "lac": bool(mine and rv and rv != mine)})
    return out


def status(ep: dict) -> dict:
    """Tiến độ 1 tập: mỗi kênh đã tick đã có metadata chưa, đã xuất file chưa.

    Đọc từ `runs/<run>/result.json` — nguồn sự thật là kết quả thật, không phải cờ tự khai.
    """
    want = list(ep.get("channels") or [])
    done: dict[str, dict] = {}
    for run in ep.get("runs") or []:
        f = common.run_dir(run) / "result.json"
        if not f.exists():
            continue
        try:
            r = common.read_json(f)
        except Exception:                                  # noqa: BLE001
            continue
        exported = bool(r.get("exported_at"))
        if r.get("mode") == "episode":
            for c in r.get("channels") or []:
                sl = common.slug(c.get("slug") or "")
                if sl and sl not in done:
                    done[sl] = {"run": run, "title": (c.get("title") or {}).get("text", ""),
                                "exported": exported}
        else:
            praw = (r.get("profile") or "").strip()         # result.json thiếu profile → BỎ QUA,
            sl = common.slug(praw) if praw else ""          # đừng để common.slug("")=="x" gán bừa
            if sl and sl not in done:
                done[sl] = {"run": run, "title": r.get("picked_title") or "",
                            "exported": exported}
    return {"channels": [{"slug": s, **(done.get(s) or {})} for s in want],
            "n_done": sum(1 for s in want if s in done),
            "n_total": len(want),
            "n_exported": sum(1 for s in want if (done.get(s) or {}).get("exported"))}


if __name__ == "__main__":                                 # self-test offline (thư mục tạm)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        common.ROOT = Path(tmp)
        common.RUNS, common.PROFILES = Path(tmp) / "runs", Path(tmp) / "profiles"
        common.write_json(common.profiles_dir(create=True) / "cosmic-lens-cl-01.json",
                          {"channel": "Cosmic Lens", "code": "CL-01", "niche": "Space / Science"})
        common.write_json(common.profiles_dir() / "outland-o-01.json",
                          {"channel": "Outland", "code": "O-01", "niche": "Space / Science"})

        # tạo tập: niche tự suy từ kênh, không bắt user gõ lại
        ep = save({"name": "Sagittarius A*", "main_url": "https://youtu.be/AAAAAAAAAAA",
                   "sub_urls": "https://youtu.be/BBBBBBBBBBB", "script": "kịch bản dài…",
                   "srt": "1\n00:00:00,000 --> 00:00:04,000\nhello",
                   "channels": ["cosmic-lens-cl-01", "outland-o-01"]})
        assert ep["slug"] == "sagittarius-a" and ep["niche"] == "Space / Science", ep

        # ── NICHE: gõ tay thắng · suy từ kênh · kênh khai niche sau vẫn kéo được tập lên nhóm ──
        assert save({"slug": ep["slug"], "name": ep["name"], "niche": "Tự Gõ",
                     "channels": ["cosmic-lens-cl-01"]})["niche"] == "Tự Gõ"
        common.write_json(common.profiles_dir() / "chua-niche.json",
                          {"channel": "Chưa Niche", "code": "CN-01"})     # kênh CHƯA khai niche
        e2 = save({"name": "Tập kênh chưa niche", "channels": ["chua-niche"]})
        assert e2["niche"] == "", e2                        # không có gì để suy → để trống, không bịa
        library.update("chua-niche", {"niche": "Life In"})  # khai niche cho kênh SAU khi đã tạo tập
        e2b = save({"slug": e2["slug"], "name": e2["name"], "channels": ["chua-niche"]})
        assert e2b["niche"] == "Life In", e2b               # lưu lại tập là tự kéo lên đúng nhóm
        delete(e2["slug"])
        assert ep["script"] and ep["srt"], "kịch bản + SRT PHẢI được giữ — đây là lý do tồn tại của Tập"

        # sửa lại: giữ created, đổi updated, không mất runs
        attach_run("sagittarius-a", "gen-1")
        ep2 = save({"slug": "sagittarius-a", "name": "Sagittarius A*", "note": "bản re-up",
                    "channels": ["cosmic-lens-cl-01"], "script": "kịch bản mới"})
        assert ep2["created"] == ep["created"] and ep2["runs"] == ["gen-1"], ep2
        assert ep2["note"] == "bản re-up" and ep2["script"] == "kịch bản mới", ep2

        # tiến độ đọc từ result.json THẬT, không phải cờ tự khai
        st = status(load("sagittarius-a"))
        assert st == {"channels": [{"slug": "cosmic-lens-cl-01"}], "n_done": 0, "n_total": 1,
                      "n_exported": 0}, st
        common.write_json(common.run_dir("gen-1", create=True) / "result.json",
                          {"profile": "cosmic-lens-cl-01", "picked_title": "A Monster",
                           "exported_at": "2026-07-29T10:00:00+07:00"})
        st = status(load("sagittarius-a"))
        assert st["n_done"] == 1 and st["n_exported"] == 1, st
        assert st["channels"][0]["title"] == "A Monster", st

        # run kiểu episode (1 tập → N kênh) phải tính đủ từng kênh
        save({"slug": "sagittarius-a", "name": "Sagittarius A*",
              "channels": ["cosmic-lens-cl-01", "outland-o-01"]})
        attach_run("sagittarius-a", "ep-9")
        common.write_json(common.run_dir("ep-9", create=True) / "result.json",
                          {"mode": "episode", "channels": [
                              {"slug": "cosmic-lens-cl-01", "title": {"text": "T-A"}},
                              {"slug": "outland-o-01", "title": {"text": "T-B"}}]})
        st = status(load("sagittarius-a"))
        assert st["n_done"] == 2, st
        # RUN MỚI NHẤT THẮNG: ep-9 sinh lại cosmic-lens nên title là "T-A", không phải "A Monster"
        # của gen-1. Và vì bản mới CHƯA xuất file nên n_exported về 0 — đúng: metadata đang dùng
        # trên video vẫn là bản cũ, tập này thật sự còn việc phải làm.
        assert [c["title"] for c in st["channels"]] == ["T-A", "T-B"], st
        assert st["n_exported"] == 0, st

        # ── tên tiếng Việt → slug KHÔNG DẤU, và 2 tên khác nhau không bị gộp ──
        assert ascii_slug("Quái vật giữa Ngân Hà") == "quai-vat-giua-ngan-ha"
        assert ascii_slug("Đường tới Sao Hỏa") == "duong-toi-sao-hoa"
        v1 = save({"name": "Tập A", "channels": []})
        v2 = save({"name": "Tap A", "channels": []})       # bỏ dấu xong trùng slug của v1
        assert v1["slug"] == "tap-a" and v2["slug"] == "tap-a-2", (v1["slug"], v2["slug"])
        assert save({"slug": "tap-a", "name": "Tập A", "note": "sửa"})["slug"] == "tap-a"
        assert len(all_episodes()) == 3
        delete("tap-a"), delete("tap-a-2")

        assert len(all_episodes()) == 1
        assert delete("sagittarius-a") and not delete("sagittarius-a")
        try:
            save({"name": "  "})
            raise AssertionError("phải raise khi thiếu tên tập")
        except RuntimeError:
            pass

    # ── MÃ TẬP: cấp 1 lần, đánh số theo NICHE, không bao giờ cấp lại ──
    assert gen_code("Life In", set()) == "LI-01"
    assert gen_code("Life In", {"LI-01", "LI-02"}) == "LI-03"
    assert gen_code("", set()) == "TAP-01"                  # chưa phân loại vẫn có mã
    assert gen_code("Space", {"LI-01"}) == "SP-01"          # đánh số RIÊNG từng niche

    a = save({"name": "Tap A", "niche": "Life In"})
    b = save({"name": "Tap B", "niche": "Life In"})
    c = save({"name": "Tap C", "niche": "Space"})
    assert (a["code"], b["code"], c["code"]) == ("LI-01", "LI-02", "SP-01"), (a["code"], b["code"], c["code"])

    # đổi niche KHÔNG cấp lại mã — mã có thể đã nằm trên video thật
    b2 = save({"slug": b["slug"], "name": "Tap B", "niche": "Space"})
    assert b2["code"] == "LI-02", b2["code"]

    # ── MÃ DO USER GÕ LUÔN THẮNG (user chốt: "đặt mã theo quy ước của tôi") ──
    mine = save({"name": "Tap Rieng", "niche": "Life In", "code": "AMZ07"})
    assert mine["code"] == "AMZ07", mine["code"]           # giữ NGUYÊN VĂN, không ép về khuôn LI-xx
    assert load(mine["slug"])["code"] == "AMZ07"
    # sửa lại mã bất cứ lúc nào
    mine2 = save({"slug": mine["slug"], "name": "Tap Rieng", "code": "FIN-2025"})
    assert mine2["code"] == "FIN-2025", mine2["code"]
    # trùng mã tập khác vẫn cho — quy ước của user, tool không phán
    dup = save({"name": "Tap Trung Ma", "niche": "Life In", "code": "FIN-2025"})
    assert dup["code"] == "FIN-2025"
    # lưu lại mà KHÔNG gửi code (form cũ) → giữ mã đang có, không cấp mã mới
    keep = save({"slug": mine["slug"], "name": "Tap Rieng"})
    assert keep["code"] == "FIN-2025", keep["code"]

    # xoá tập giữa chừng KHÔNG đánh số lại tập còn lại
    delete(a["slug"])
    assert load(b["slug"])["code"] == "LI-02", "mã bị đánh số lại sau khi xoá"
    d = save({"name": "Tap D", "niche": "Life In"})
    assert d["code"] == "LI-01", d["code"]                  # tái dùng số TRỐNG, không đè mã đang có

    # MỌI field trong INPUT_FIELDS phải THẬT SỰ được `save` ghi xuống. `save` dựng dict bằng
    # danh sách CỐ ĐỊNH chứ không lặp INPUT_FIELDS ⇒ thêm field mới mà quên sửa `save` là user
    # gõ xong bấm Lưu rồi mất trắng, KHÔNG báo lỗi gì. Suýt cắn với `title_bank`/`use_bank`.
    probe = {"name": "Do Field", "channels": [],
             "code": "Z-99", "niche": "N", "note": "ghi chú", "main_url": "u", "sub_urls": "s",
             "script": "kb", "srt": "srt", "hook": "hk", "chapters": "ch",
             "title_bank": "T1\nT2", "use_bank": False}
    got = load(save(probe)["slug"])
    for k in INPUT_FIELDS:
        if k == "channels":
            continue
        assert got.get(k) == probe[k], f"`save` KHÔNG ghi field {k!r}: {got.get(k)!r} != {probe[k]!r}"
    assert save({**probe, "slug": got["slug"]})["use_bank"] is False, "use_bank=False bị hiểu nhầm thành mặc định True"

    print("episodes.py self-test OK - giu du kich ban/SRT, suy niche tu kenh, tien do doc tu run that")

    # ── REGRESSION (audit 2026-07-29): các cách MẤT DỮ LIỆU đã bịt ──
    with tempfile.TemporaryDirectory() as _t:
        common.ROOT = Path(_t)
        common.RUNS, common.PROFILES = Path(_t) / "runs", Path(_t) / "profiles"

        # 1. tập MỚI trùng tên KHÔNG được ghi đè tập cũ
        a = save({"name": "Tập 1", "script": "KICH-BAN-A", "channels": []})
        attach_run(a["slug"], "gen-A")
        b = save({"name": "Tập 1", "script": "KICH-BAN-B", "channels": []})
        assert b["slug"] != a["slug"], (a["slug"], b["slug"])
        assert load(a["slug"])["script"] == "KICH-BAN-A", "kịch bản tập cũ bị ghi đè!"
        assert b["runs"] == [] and load(a["slug"])["runs"] == ["gen-A"], (a, b)
        assert len(all_episodes()) == 2
        # sửa tập (có slug) vẫn cập nhật ĐÚNG chỗ, không đẻ file mới
        assert save({"slug": a["slug"], "name": "Tập 1", "script": "A2"})["slug"] == a["slug"]
        assert len(all_episodes()) == 2 and load(a["slug"])["script"] == "A2"

        # 2. attach_run với slug RỖNG không được bám vào tập nào (common.slug("")=="x")
        x = save({"name": "X", "channels": []})
        assert x["slug"] == "x", x["slug"]
        attach_run("", "gen-LAC")
        attach_run(None, "gen-LAC")
        assert load("x")["runs"] == [], load("x")["runs"]

        # 3. file rác trong episodes/ không được làm chết tab hay chết lần generate
        (episodes_dir() / "hong.json").write_text("{khong-phai-json", encoding="utf-8")
        (episodes_dir() / "mang.json").write_text("[1,2,3]", encoding="utf-8")
        assert len(all_episodes()) == 3, [e["slug"] for e in all_episodes()]
        assert load("hong") is None and load("mang") is None
        attach_run("hong", "gen-1")                        # không được ném
        assert save({"name": "sau khi co file rac", "channels": []})["slug"]

        # 4. result.json thiếu `profile` không được tính bừa vào tập slug "x"
        save({"slug": "x", "name": "X", "channels": ["x"]})
        attach_run("x", "gen-noprof")
        common.write_json(common.run_dir("gen-noprof", create=True) / "result.json",
                          {"titles": [], "picked_title": "T"})
        assert status(load("x"))["n_done"] == 0, status(load("x"))

    print("episodes.py self-test OK - khong ghi de tap trung ten, khong bam run lac, file rac khong lam chet")
