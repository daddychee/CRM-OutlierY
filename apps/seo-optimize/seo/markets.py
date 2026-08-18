"""THỊ TRƯỜNG — khối cấp cao nhất của board (user chốt 2026-08-01).

User: *"SEO nhân bản ngôn ngữ sẽ là main tab: hiện các khối ghi ngôn ngữ vào — khối 1 US,
khối 2 SPAIN, khối 3 KOREA… nếu muốn nhập tiếp thì có 1 khối trống để tự input."*

**VÌ SAO PHẢI CÓ KHO RIÊNG, không suy ra từ dữ liệu.** Bản trước tôi dựng danh sách ngôn ngữ
bằng cách gom `lang` của kênh/format đang có. Cách đó KHÔNG tạo được **khối trống**: muốn mở
thị trường KOREA trước khi có bất kỳ kênh hay format Hàn nào thì chẳng có gì để gom. Mà mở
thị trường mới thì đúng là lúc chưa có gì cả — chính là lúc cần nó nhất.

**THỊ TRƯỜNG ≠ NGÔN NGỮ, dù hiện tại ánh xạ 1-1.** `name` là tên user gọi (`US`, `SPAIN`),
`lang` là ngôn ngữ SEO của thị trường đó — thứ dùng để lọc kênh/format. Tách hai field ngay
từ đầu vì chúng sẽ rời nhau ngay khi user mở US và UK (cùng English, khác thị trường); gộp
làm một rồi tách sau là phải sửa mọi chỗ đọc.

Không LLM, không quota.
"""
from __future__ import annotations

import re

from . import common, library

MAX = 60                  # trần mềm — mạng lưới thật không thể có 60 thị trường


def markets_file():
    return common.ROOT / "markets.json"


def _norm(s) -> str:
    return " ".join(str(s or "").split())


def all_markets() -> list[dict]:
    """Danh sách thị trường. File hỏng/thiếu → trả rỗng, KHÔNG ném: board vẫn phải mở được."""
    f = markets_file()
    if not f.exists():
        return []
    try:
        d = common.read_json(f)
    except Exception:                                      # noqa: BLE001
        return []
    out = []
    for m in (d.get("markets") if isinstance(d, dict) else d) or []:
        if isinstance(m, dict) and _norm(m.get("name")):
            out.append({"name": _norm(m.get("name")), "lang": _norm(m.get("lang")),
                        "note": _norm(m.get("note")), "created": m.get("created") or ""})
    return out


def _write(items: list[dict]) -> None:
    common.write_json(markets_file(), {"markets": items})


def save(name: str, lang: str = "", note: str = "", *, old: str = "") -> dict:
    """Thêm hoặc sửa một thị trường. `old` = tên cũ khi đổi tên.

    TRẢ LỖI BẰNG RaiseError chứ không im lặng bỏ qua: user gõ tên trùng mà tool lặng lẽ
    không tạo thì họ bấm lại vài lần rồi tưởng nút hỏng.
    """
    name, lang, note = _norm(name), _norm(lang), _norm(note)
    if not name:
        raise RuntimeError("Thiếu tên thị trường")
    items = all_markets()
    key = name.casefold()
    oldkey = _norm(old).casefold()
    for m in items:
        if m["name"].casefold() == key and m["name"].casefold() != oldkey:
            raise RuntimeError(f"Đã có thị trường tên {m['name']!r}")
    if oldkey:
        for m in items:
            if m["name"].casefold() == oldkey:
                m.update(name=name, lang=lang, note=note)
                _write(items)
                return m
        raise RuntimeError(f"Không thấy thị trường {old!r} để sửa")
    if len(items) >= MAX:
        raise RuntimeError(f"Quá {MAX} thị trường — nhiều bất thường, kiểm lại đi")
    m = {"name": name, "lang": lang, "note": note, "created": library.now_iso()}
    items.append(m)
    _write(items)
    return m


def remove(name: str) -> bool:
    """Xoá một thị trường KHỎI DANH SÁCH. Không đụng kênh/format — chúng giữ nguyên `lang`.

    Cố ý KHÔNG dọn theo: `lang` là dữ liệu thật đã đo/khai của từng kênh, còn thị trường chỉ
    là cách user gom nhóm. Xoá nhóm mà xoá luôn dữ liệu bên trong là mất thứ không lấy lại được.
    """
    items = all_markets()
    keep = [m for m in items if m["name"].casefold() != _norm(name).casefold()]
    if len(keep) == len(items):
        return False
    _write(keep)
    return True


def orphan_langs(langs) -> list[str]:
    """Ngôn ngữ đang có trên kênh/format nhưng CHƯA thị trường nào nhận.

    Phải nói ra: nếu không, những kênh đó biến mất khỏi mọi khối ở main tab mà không một chữ
    giải thích — đúng kiểu "im lặng giấu dữ liệu" mà dự án cấm.
    """
    have = {(m.get("lang") or "").casefold() for m in all_markets() if m.get("lang")}
    seen, out = set(), []
    for l in langs:
        l = _norm(l)
        if not l or l.casefold() in have or l.casefold() in seen:
            continue
        seen.add(l.casefold())
        out.append(l)
    return out


if __name__ == "__main__":                                 # self-test — thư mục tạm, không đụng dữ liệu thật
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        common.ROOT = Path(td)
        assert all_markets() == [], "chưa có file thì phải RỖNG, không ném"

        save("US", "English")
        save("SPAIN", "Spanish", "thị trường mới mở")
        # KHỐI TRỐNG: tạo được thị trường CHƯA có kênh/format nào — đây là lý do tồn tại của
        # file này (gom từ dữ liệu thì không bao giờ ra được khối trống).
        save("KOREA")
        got = [m["name"] for m in all_markets()]
        assert got == ["US", "SPAIN", "KOREA"], got
        assert all_markets()[2]["lang"] == "", "thị trường trống vẫn phải lưu được"

        # trùng tên (không phân biệt hoa/thường) → BÁO, không im lặng bỏ qua
        try:
            save("us", "English")
            raise AssertionError("phải chặn tên trùng")
        except RuntimeError as e:
            assert "Đã có" in str(e), e
        # sửa: đổi tên + gán ngôn ngữ cho khối trống
        save("KOREA (Hàn)", "Korean", old="KOREA")
        assert [m["name"] for m in all_markets()] == ["US", "SPAIN", "KOREA (Hàn)"]
        assert all_markets()[2]["lang"] == "Korean"
        # đổi tên chính nó thì KHÔNG được coi là trùng
        save("KOREA (Hàn)", "Korean", "ghi chú", old="KOREA (Hàn)")
        assert all_markets()[2]["note"] == "ghi chú"

        # ngôn ngữ mồ côi: có trên kênh nhưng chưa thị trường nào nhận
        assert orphan_langs(["English", "Spanish", "Korean"]) == []
        assert orphan_langs(["English", "Tiếng Việt", "tiếng việt"]) == ["Tiếng Việt"]

        assert remove("SPAIN") is True
        assert remove("SPAIN") is False, "xoá cái không có phải trả False, không ném"
        assert [m["name"] for m in all_markets()] == ["US", "KOREA (Hàn)"]

        try:
            save("")
            raise AssertionError("phải chặn tên rỗng")
        except RuntimeError:
            pass

    print("markets.py self-test OK - tao duoc KHOI TRONG, chan trung ten, doi ten giu duoc, "
          "xoa nhom khong dung du lieu, bao ngon ngu mo coi")
