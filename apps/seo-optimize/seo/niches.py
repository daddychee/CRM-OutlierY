"""KHO TITLE CẤP NICHE — khai 1 lần cho cả niche, mọi tập trong niche đó dùng chung.

Vì sao có file này: `title_bank` ban đầu nằm trong TỪNG TẬP, nên cùng một niche user phải dán
lại danh sách title cho mỗi tập (user phản hồi 2026-07-31: *"tôi muốn input cho cả niche ấy
chứ không phải mỗi 1 tập lại đi nhập tay"*). Kho này là **hằng số của niche**, đúng tinh thần
"hằng số vs biến số" trong CLAUDE.md — giống `profiles/` và `formats/`, khai một lần rồi thôi.

Trước đây niche KHÔNG có store riêng (chỉ là một field text trên profile/format, board gom
nhóm lúc render). Giờ có, nhưng CỐ Ý giữ tối thiểu: đúng BA cột (`patterns` ·
`title_bank` · `thumb_bank`). Đừng biến nó thành nơi chứa mọi thứ về niche — niche vẫn được định nghĩa bởi
field trên profile/format, file này chỉ đính kèm 3 kho trên.

Không LLM, không quota.
"""
from __future__ import annotations

import difflib
import re

from . import common, episodes, library

MAX_TITLES = 400          # trần mềm: quá số này thì payload gửi LLM phình vô ích
MAX_PATTERNS = 120
MAX_THUMBS = 400
NEAR_DUP = 0.85           # ≥ mức này coi là "gần giống" → HỎI LẠI, không tự quyết thay user

# ── BA CỘT, BA BẢN CHẤT — đừng trộn, và ĐỪNG GỌI NHẦM TÊN (user chốt 2026-07-31) ────
# `patterns`  = CÔNG THỨC, có chỗ giữ chỗ (`{NAME} in {CAPS}! - {NAME} of {CAPS}`).
#               Đây KHÔNG phải chữ có thật ⇒ **TUYỆT ĐỐI không đưa vào `trace_blocks`**.
#               `{NAME}` mà nằm trong kho truy nguyên thì LLM điền gì cũng "truy được", chốt
#               chống bịa mất sạch răng. Công thức chỉ đi vào PROMPT làm khung.
# `title_bank` = TIÊU ĐỀ TẬP NỔ có thật ⇒ vào kho truy nguyên như bình thường.
# `thumb_bank` = **TEXT ON THUMB** — chữ NẰM TRÊN ảnh thumbnail. Gọi tắt là "kho thumb" thì
#               đọc ra là kho ẢNH, sai hẳn nghĩa (user nhắc 2026-07-31). Mọi chữ hiện ra cho
#               user phải viết đủ **Text on Thumb**. Nuôi `thumbtext.analyze` (mẫu to hơn thì
#               luật đặt chữ chắc hơn vài dòng của riêng một tập) + làm nguyên liệu ĐỀ XUẤT.
#               KHÔNG dính gì tới title.
_PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]+\}")


def is_pattern(line: str) -> bool:
    """Dòng có chỗ giữ chỗ `{...}` = công thức, không phải title thật."""
    return bool(_PLACEHOLDER.search(line or ""))


def niches_dir(*, create: bool = False):
    d = common.ROOT / "niches"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _path(niche: str):
    # Dùng ascii_slug của `episodes`: tên niche tiếng Việt có dấu → `common.slug` giữ nguyên dấu
    # nên đẻ ra tên file có dấu (đã cắn ở TẬP). Dùng chung một hàm để hai chỗ không lệch nhau.
    return niches_dir() / f"{episodes.ascii_slug(niche)}.json"


def parse_bank(raw: str, cap: int = MAX_TITLES) -> list[str]:
    """Chuỗi nhiều dòng → danh sách, bỏ trùng, GIỮ THỨ TỰ user gõ."""
    out, seen = [], set()
    for ln in (raw or "").splitlines():
        t = ln.strip().lstrip("-•*").strip()
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out[:cap]


# BA CỘT khai ở MỘT chỗ: {kind: (field lưu đĩa, field danh sách, field đếm)}. Thêm cột thứ tư
# về sau chỉ phải sửa bảng này + UI, không phải đi dò từng hàm. `kind` dùng xuyên suốt
# server/board nên đổi khoá ở đây là đổi cả API.
COLS = {"titles": ("title_bank", "titles", "n"),
        "patterns": ("patterns", "pattern_list", "n_patterns"),
        "thumbs": ("thumb_bank", "thumb_list", "n_thumbs")}


def _pack(n: str, titles_: list[str], pats: list[str], thumbs: list[str], updated: str) -> dict:
    return {"niche": n,
            "title_bank": "\n".join(titles_), "patterns": "\n".join(pats),
            "thumb_bank": "\n".join(thumbs),
            "titles": titles_, "pattern_list": pats, "thumb_list": thumbs,
            "n": len(titles_), "n_patterns": len(pats), "n_thumbs": len(thumbs),
            "updated": updated}


def load(niche: str) -> dict:
    """Kho của 1 niche. Chưa có thì trả bản rỗng — KHÔNG raise (niche mới là bình thường)."""
    n = (niche or "").strip()
    if not n:
        return _pack("", [], [], [], "")
    f = _path(n)
    d = common.read_json(f) if f.exists() else {}
    # Kho cũ (trước 2026-07-31) chỉ có `title_bank`, có thể lẫn công thức nếu user từng dán vào.
    # Tách ra lúc ĐỌC để bản cũ không phải sửa tay — công thức không được lọt vào kho truy nguyên.
    old = parse_bank(d.get("title_bank", ""))
    pats = parse_bank(d.get("patterns", ""), MAX_PATTERNS) + [x for x in old if is_pattern(x)]
    titles_ = [x for x in old if not is_pattern(x)]
    thumbs = parse_bank(d.get("thumb_bank", ""), MAX_THUMBS)
    return _pack(n, titles_, pats[:MAX_PATTERNS], thumbs, d.get("updated", ""))


def save(niche: str, raw: str, patterns: str | None = None, thumbs: str | None = None) -> dict:
    """Ghi các cột. Truyền `None` cho cột nào = KHÔNG đụng cột đó (giữ nguyên bản đang có)."""
    n = (niche or "").strip()
    if not n:
        raise RuntimeError("Thiếu tên niche")
    cur = load(n)
    lines = parse_bank(raw)
    # Công thức lỡ gõ nhầm sang ô title thì tự chuyển sang đúng cột, đừng để nó vào kho truy nguyên.
    stray = [x for x in lines if is_pattern(x)]
    titles_ = [x for x in lines if not is_pattern(x)]
    pats = parse_bank(patterns, MAX_PATTERNS) if patterns is not None else cur["pattern_list"]
    thmb = parse_bank(thumbs, MAX_THUMBS) if thumbs is not None else cur["thumb_list"]
    for x in stray:
        if x.lower() not in {p.lower() for p in pats}:
            pats.append(x)
    # Ghi lại BẢN ĐÃ DỌN chứ không ghi nguyên văn: user dán từ chỗ khác hay dính dòng trống,
    # bullet, trùng lặp. Dọn ngay lúc lưu thì mọi nơi đọc ra đều thấy cùng một danh sách.
    out = _pack(n, titles_, pats[:MAX_PATTERNS], thmb, library.now_iso())
    common.write_json(_path(n),
                      {k: out[k] for k in ("niche", "title_bank", "patterns", "thumb_bank", "updated")})
    out["moved_to_patterns"] = stray
    return out


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower().split(), b.lower().split()).ratio()


def add_title(niche: str, title: str, *, force: bool = False) -> dict:
    """Thêm ĐÚNG MỘT title, có CHECK TRÙNG (user chốt 2026-07-31: nhập tay từng cái).

    Ba kết quả, đừng gộp:
      · `dup`  — trùng khít (không phân biệt hoa/thường) → TỪ CHỐI, chỉ ra dòng nào
      · `near` — giống ≥ NEAR_DUP → HỎI LẠI, user quyết (`force=True` để vẫn thêm).
                 Tự quyết thay user ở đây là sai cả hai chiều: chặn thì mất title thật khác
                 nhau vài chữ, cho qua thì kho đầy bản na ná nhau mà không ai biết.
      · thêm được
    """
    n = (niche or "").strip()
    t = (title or "").strip().lstrip("-•*").strip()
    if not n:
        raise RuntimeError("Thiếu tên niche")
    if not t:
        raise RuntimeError("Chưa nhập title")
    cur = load(n)
    if is_pattern(t):                                       # gõ công thức vào ô title
        return {"ok": False, "kind": "pattern", "title": t,
                "msg": "Dòng này có chỗ giữ chỗ {…} — đó là CÔNG THỨC, dán vào ô công thức bên trên."}
    low = t.lower()
    for i, x in enumerate(cur["titles"]):
        if x.lower() == low:
            return {"ok": False, "kind": "dup", "title": t, "at": i + 1, "dup_of": x,
                    "msg": f"Đã có trong kho (dòng {i + 1})"}
    if not force:
        for i, x in enumerate(cur["titles"]):
            s = _sim(t, x)
            if s >= NEAR_DUP:
                return {"ok": False, "kind": "near", "title": t, "at": i + 1, "dup_of": x,
                        "sim": round(s, 3),
                        "msg": f"Giống {round(s * 100)}% dòng {i + 1} — vẫn thêm?"}
    r = save(n, "\n".join(cur["titles"] + [t]))
    return {"ok": True, "kind": "added", "title": t, **r}


def add_many(niche: str, raw: str, *, kind: str = "titles") -> dict:
    """Thêm NHIỀU dòng một lúc (dán/nạp .txt) — TRÙNG THÌ KHÔNG THÊM, và phải LIỆT KÊ ra.

    Trước đây đường hàng loạt dọn trùng IM LẶNG trong `parse_bank`: user nạp file 50 dòng,
    kho lên 30, không biết 20 dòng kia đi đâu — tưởng tool nuốt mất. Giờ mỗi dòng bị bỏ đều
    có tên + lý do (`dup` trùng khít · `near` gần giống · `same_batch` trùng ngay trong file).
    Muốn thêm bản gần giống thì dùng ô thêm-từng-cái rồi bấm "Vẫn thêm".
    """
    n = (niche or "").strip()
    if not n:
        raise RuntimeError("Thiếu tên niche")
    if kind not in COLS:
        raise RuntimeError(f"Cột không hợp lệ: {kind}")
    cur = load(n)
    is_pat = kind == "patterns"
    have = list(cur[COLS[kind][1]])
    lower = {x.lower(): i for i, x in enumerate(have)}
    cap = MAX_PATTERNS if is_pat else (MAX_THUMBS if kind == "thumbs" else MAX_TITLES)
    added, skipped = [], []
    # KHÔNG dùng `parse_bank` ở đây: nó bỏ trùng IM LẶNG ngay trong lô, nên hai dòng chỉ khác
    # hoa/thường thì dòng thứ hai biến mất trước khi tới được chỗ kiểm — user nạp 50 dòng, kho
    # lên 48, không ai giải thích 2 dòng kia. Ở đây phải NHÌN THẤY từng dòng để gọi tên nó ra.
    for ln in (raw or "").splitlines():
        line = ln.strip().lstrip("-•*").strip()
        if not line:
            continue
        if len(have) >= cap:
            skipped.append({"text": line, "why": "full", "cap": cap})
            continue
        # Dòng đi nhầm cột thì bỏ + nói rõ, đừng tự ý ném sang cột kia trong một thao tác
        # user nghĩ là "nạp công thức" (hoặc ngược lại).
        if is_pattern(line) != is_pat:
            skipped.append({"text": line, "why": "pattern" if is_pattern(line) else "not_pattern"})
            continue
        low = line.lower()
        if low in lower:
            j = lower[low]
            # trùng với dòng CÓ SẴN trong kho, hay trùng với dòng khác trong CHÍNH lô này
            in_batch = have[j] in added
            skipped.append({"text": line, "why": "same_batch" if in_batch else "dup",
                            "at": j + 1, "dup_of": have[j]})
            continue
        near = None
        # Chỉ soi GẦN GIỐNG cho cột TITLE. Công thức vốn na ná nhau (khác 1 ô đã giống ~89%),
        # còn Text on Thumb thì rất ngắn ("1000 ĐỘ C" vs "2000 ĐỘ C" giống 67%) — soi gần giống ở
        # hai cột đó là chặn oan gần hết kho.
        if kind == "titles":
            for i, x in enumerate(have):
                s = _sim(line, x)
                if s >= NEAR_DUP:
                    near = {"text": line, "why": "near", "at": i + 1, "dup_of": x, "sim": round(s, 3)}
                    break
        if near:
            skipped.append(near)
            continue
        have.append(line)
        lower[low] = len(have) - 1
        added.append(line)
    return {"ok": True, "added": added, "skipped": skipped, **_write_col(n, cur, kind, have)}


def _write_col(n: str, cur: dict, kind: str, items: list[str]) -> dict:
    """Ghi ĐÚNG một cột, hai cột kia giữ nguyên. Viết một chỗ để không sót cột nào khi thêm cột mới."""
    raw = "\n".join(items)
    return save(n,
                raw if kind == "titles" else cur["title_bank"],
                raw if kind == "patterns" else None,
                raw if kind == "thumbs" else None)


def remove(niche: str, items: list, *, kind: str = "titles") -> dict:
    """Xoá các dòng ĐƯỢC CHỌN (khớp mặt chữ, bỏ qua hoa/thường). Trả số đã xoá + số không thấy."""
    n = (niche or "").strip()
    if not n:
        raise RuntimeError("Thiếu tên niche")
    if kind not in COLS:
        raise RuntimeError(f"Cột không hợp lệ: {kind}")
    cur = load(n)
    have = list(cur[COLS[kind][1]])
    want = {str(x).strip().lower() for x in (items or []) if str(x).strip()}
    if not want:
        raise RuntimeError("Chưa chọn dòng nào để xoá")
    keep = [x for x in have if x.lower() not in want]
    gone = [x for x in have if x.lower() in want]
    return {"ok": True, "removed": gone, "n_removed": len(gone),
            "not_found": len(want) - len(gone), **_write_col(n, cur, kind, keep)}


def all_banks(errors: list | None = None) -> dict:
    """`{niche: {n, n_patterns}}` — file hỏng thì GHI vào `errors`, không biến mất im lặng.

    Đếm qua `load()` chứ không đếm thẳng `title_bank`: kho cũ có thể còn công thức nằm lẫn
    trong đó, đếm thô là board khoe số title cao hơn số thật sự vào được kho truy nguyên.
    """
    out: dict[str, dict] = {}
    d = niches_dir()
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            j = common.read_json(f)
        except Exception as e:                              # noqa: BLE001
            if errors is not None:
                errors.append({"kind": "niche", "file": f.name, "error": str(e)[:200]})
            continue
        n = (j.get("niche") or "").strip()
        if n:
            b = load(n)
            out[n] = {"n": b["n"], "n_patterns": b["n_patterns"], "n_thumbs": b["n_thumbs"]}
    return out


def titles_for(niche: str) -> list[str]:
    """Title THẬT của niche — dùng thẳng làm `ref_titles` (vào kho truy nguyên)."""
    return load(niche)["titles"]


def patterns_for(niche: str) -> list[str]:
    """CÔNG THỨC của niche — chỉ đi vào PROMPT, KHÔNG vào kho truy nguyên (xem chú thích đầu file)."""
    return load(niche)["pattern_list"]


def thumbs_for(niche: str) -> list[str]:
    """TEXT ON THUMB của niche — cộng vào mẫu cho `thumbtext.analyze` + làm nguyên liệu đề xuất."""
    return load(niche)["thumb_list"]


if __name__ == "__main__":                                  # self-test offline
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        common.ROOT = Path(tmp)
        niches_dir(create=True)

        assert load("")["n"] == 0 and load("Chưa Có")["n"] == 0   # niche mới: rỗng, không raise

        raw = ("Life in NORWAY - The RICHEST Country\n"
               "  • 10 Facts About RUSSIA They NEVER Show You  \n"
               "\n"
               "life in norway - the richest country\n"          # trùng (khác hoa/thường) → bỏ
               "Inside JAPAN's Most SECRETIVE Village")
        r = save("Life In", raw)
        assert r["n"] == 3, r["titles"]
        assert r["titles"][1] == "10 Facts About RUSSIA They NEVER Show You", r["titles"]
        assert titles_for("Life In") == r["titles"]
        # ghi lại BẢN ĐÃ DỌN → đọc lên không còn bullet/dòng trống
        assert "•" not in load("Life In")["title_bank"]

        save("Space", "A Title\nB Title")
        assert {k: v["n"] for k, v in all_banks().items()} == {"Life In": 3, "Space": 2}, all_banks()

        # tên niche có DẤU → tên file phải không dấu (cùng bài học với TẬP)
        save("Vũ Trụ Học", "X Title")
        assert (niches_dir() / "vu-tru-hoc.json").exists(), list(niches_dir().iterdir())
        assert titles_for("Vũ Trụ Học") == ["X Title"]

        # file hỏng: bỏ qua nhưng PHẢI ghi lại, không biến mất im lặng
        (niches_dir() / "hong.json").write_text("{khong-phai-json", encoding="utf-8")
        errs: list = []
        all_banks(errs)
        assert errs and errs[0]["file"] == "hong.json", errs

        try:
            save("", "x")
            raise AssertionError("phải chặn niche rỗng")
        except RuntimeError:
            pass

        # ── HAI CỘT: công thức TÁCH KHỎI title thật ──────────────────────────────
        FORM = "{NAME} in {CAPS}! - {NAME} of {CAPS} {NAME} and {CAPS}"
        FORM2 = "Real Life in {CAPS}: How {CAPS} Survive in {NAME}"
        # dán kèm 1 bản chỉ khác hoa/thường → `parse_bank` bỏ trùng KHÔNG phân biệt hoa/thường
        r = save("Life In", "\n".join(titles_for("Life In")), f"{FORM}\n{FORM.lower()}\n{FORM2}")
        assert r["n_patterns"] == 2, r["pattern_list"]
        assert patterns_for("Life In") == [FORM, FORM2], patterns_for("Life In")
        assert FORM not in titles_for("Life In"), "CÔNG THỨC KHÔNG được lọt vào kho truy nguyên"
        assert is_pattern(FORM) and not is_pattern("Life in NORWAY - The RICHEST Country")

        # gõ nhầm công thức vào ô title → tự chuyển sang đúng cột, không vào kho truy nguyên
        r2 = save("Life In", "Title That Nhat\n{NAME} lac sang o title", None)
        assert r2["moved_to_patterns"] == ["{NAME} lac sang o title"], r2["moved_to_patterns"]
        assert all(not is_pattern(t) for t in r2["titles"]), r2["titles"]
        assert len(r2["pattern_list"]) == 3, r2["pattern_list"]   # 2 công thức cũ + 1 vừa chuyển sang

        # ── THÊM TỪNG TITLE, CHECK TRÙNG ─────────────────────────────────────────
        save("Chk", "Life in NORWAY - The RICHEST Country on Earth")
        a = add_title("Chk", "  • Inside JAPAN Most SECRETIVE Village  ")
        assert a["ok"] and a["n"] == 2 and a["title"].startswith("Inside JAPAN"), a

        d = add_title("Chk", "life in norway - the richest country on EARTH")
        assert not d["ok"] and d["kind"] == "dup" and d["at"] == 1, d      # trùng khít, chỉ ra dòng

        nr = add_title("Chk", "Life in NORWAY - The RICHEST Country on Mars")
        assert not nr["ok"] and nr["kind"] == "near" and nr["sim"] >= 0.85, nr
        assert add_title("Chk", "Life in NORWAY - The RICHEST Country on Mars", force=True)["ok"]
        assert load("Chk")["n"] == 3, load("Chk")["titles"]

        p = add_title("Chk", "{NAME} in {CAPS}")
        assert not p["ok"] and p["kind"] == "pattern", p                   # chỉ đường sang ô công thức

        for bad, err in ((("", "x"), "niche"), (("Chk", "  "), "title")):
            try:
                add_title(*bad)
                raise AssertionError("phải raise: " + err)
            except RuntimeError:
                pass

        # ── THÊM HÀNG LOẠT: trùng thì KHÔNG thêm, và phải LIỆT KÊ ra ────────────
        save("Bulk", "Life in NORWAY - The RICHEST Country on Earth")
        r = add_many("Bulk",
                     "Life in NORWAY - The RICHEST Country on Earth\n"      # trùng khít
                     "LIFE IN NORWAY - THE RICHEST COUNTRY ON EARTH\n"      # trùng, khác hoa/thường
                     "Life in NORWAY - The RICHEST Country on Mars\n"       # gần giống
                     "Inside JAPAN Most SECRETIVE Village\n"                # thêm được
                     "{NAME} in {CAPS}\n")                                  # đi nhầm cột
        assert r["added"] == ["Inside JAPAN Most SECRETIVE Village"], r["added"]
        why = [s["why"] for s in r["skipped"]]
        # 2 dòng trùng: 1 với kho có sẵn, 1 nữa cũng vậy (khác hoa/thường) — KHÔNG dòng nào
        # được biến mất im lặng như bản cũ (`parse_bank` nuốt trước khi kịp kiểm).
        assert why.count("dup") == 2, r["skipped"]
        assert "near" in why and "pattern" in why, r["skipped"]
        assert all(s.get("text") for s in r["skipped"]), "mỗi dòng bị bỏ phải GỌI TÊN ra"
        assert load("Bulk")["n"] == 2, load("Bulk")["titles"]

        # trùng NGAY TRONG LÔ (kho chưa có) → vẫn phải báo, nhãn riêng `same_batch`
        save("Batch", "")
        rb = add_many("Batch", "Alpha One Title\nalpha one title\nBeta Two Title")
        assert rb["added"] == ["Alpha One Title", "Beta Two Title"], rb["added"]
        assert [s["why"] for s in rb["skipped"]] == ["same_batch"], rb["skipped"]

        # công thức: chỉ soi TRÙNG KHÍT (công thức vốn na ná nhau, soi gần giống là chặn oan)
        F1 = "{NAME} in {CAPS} - {NAME}"
        F2 = "{NAME} in {CAPS} - {CAPS}"
        rp = add_many("Bulk", f"{F1}\n{F2}\n{F1.upper()}", kind="patterns")
        assert rp["added"] == [F1, F2], rp["added"]
        # F1.upper() trùng với F1 vừa thêm TRONG CHÍNH LÔ NÀY → nhãn `same_batch`, không phải `dup`
        assert [s["why"] for s in rp["skipped"]] == ["same_batch"], rp["skipped"]
        # F1 và F2 chỉ khác 1 ô cuối (giống ~89%) mà VẪN vào được: công thức chỉ soi trùng khít,
        # soi gần giống ở đây là chặn oan gần hết kho công thức.
        assert load("Bulk")["n_patterns"] == 2, load("Bulk")["pattern_list"]

        # ── XOÁ CÓ CHỌN: xoá đúng dòng đã tick, giữ nguyên phần còn lại ─────────
        add_many("Bulk", "T Mot\nT Hai\nT Ba")
        before = load("Bulk")["titles"]
        rr = remove("Bulk", ["t mot", "T Ba", "Khong Ton Tai"])
        assert rr["n_removed"] == 2 and rr["not_found"] == 1, rr
        assert load("Bulk")["titles"] == [x for x in before if x not in ("T Mot", "T Ba")], load("Bulk")["titles"]
        # xoá cột công thức KHÔNG được đụng cột title (và ngược lại)
        t_before = load("Bulk")["titles"]
        remove("Bulk", [F1], kind="patterns")
        assert load("Bulk")["titles"] == t_before, "xoá công thức làm mất title"
        assert load("Bulk")["pattern_list"] == [F2], load("Bulk")["pattern_list"]
        try:
            remove("Bulk", [])
            raise AssertionError("phải chặn xoá khi chưa chọn gì")
        except RuntimeError:
            pass

        # ── CỘT THỨ BA: TEXT ON THUMB ──────────────────────────────────────────
        t0 = load("Bulk")["titles"]
        rt = add_many("Bulk", "1000 ĐỘ C\nMOST RADIOACTIVE\n1000 do c\n2000 ĐỘ C", kind="thumbs")
        # "1000 do c" khác dấu nên KHÔNG trùng khít; "2000 ĐỘ C" giống 67% nhưng cột thumb
        # KHÔNG soi gần giống (Text on Thumb rất ngắn, soi gần giống là chặn oan).
        assert len(rt["added"]) == 4 and rt["skipped"] == [], rt
        assert thumbs_for("Bulk") == rt["thumb_list"], rt
        assert load("Bulk")["titles"] == t0, "ghi cột thumb làm mất cột title"
        assert load("Bulk")["n_thumbs"] == 4, load("Bulk")["thumb_list"]
        # trùng khít vẫn bị chặn
        rt2 = add_many("Bulk", "most radioactive", kind="thumbs")
        assert rt2["added"] == [] and rt2["skipped"][0]["why"] == "dup", rt2
        # xoá cột thumb không đụng hai cột kia
        p0, tt0 = load("Bulk")["pattern_list"], load("Bulk")["titles"]
        remove("Bulk", ["1000 ĐỘ C"], kind="thumbs")
        assert load("Bulk")["n_thumbs"] == 3, load("Bulk")["thumb_list"]
        assert load("Bulk")["pattern_list"] == p0 and load("Bulk")["titles"] == tt0
        try:
            add_many("Bulk", "x", kind="khong-co-cot-nay")
            raise AssertionError("phải chặn kind lạ")
        except RuntimeError:
            pass

    print("niches.py self-test OK - kho title cap niche, don rac, ten file khong dau, bao file hong")
    print("niches.py self-test OK - tach cong thuc khoi title that, them tung cai co check trung")
    print("niches.py self-test OK - them hang loat bao trung tung dong, xoa theo lua chon")
