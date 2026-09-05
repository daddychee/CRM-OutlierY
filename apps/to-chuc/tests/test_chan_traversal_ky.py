# -*- coding: utf-8 -*-
"""GĐ2 — to-chuc: `ky` không được thoát khỏi thư mục lương (05/09/2026).

LỖ T2 (rà 05/09, sổ `docs/bao-mat-internet.md`): `luong._duong` ghép thẳng
`Path(LUONG_DIR) / f"bang-luong/{ky}.json"` — không resolve, không kiểm biên.
Route `/finance/luong/phieu/{ky}/{ten}` và `/finance/luong/phieu.zip?ky=` KHÔNG
gọi `_thang_hop_le` (hàm này CÓ tồn tại ở main.py nhưng không được áp).

TÁI HIỆN 05/09 (chạy thật): `%2f` bị Starlette chặn nhưng **`%5c` (dấu \) thì
KHÔNG** — `unquote("..%5c..%5c..%5csecret")` → `..\..\..\secret` → đường dẫn
`secret.json`. Đọc được file JSON bất kỳ trên đĩa, nội dung render ra trang phiếu.

BÀI HỌC: chặn `..` mà chỉ nghĩ tới `/` là chưa đủ trên Windows.

Vá ở HÀM LÕI (`doc_bang_luong`, `cham_cong._duong`) chứ không chỉ ở route — route
mới thêm sau sẽ tự được bảo vệ. Bịt luôn T3.
"""
import pytest

from src import cham_cong, luong

XAU = [
    "..%5c..%5csecret",                       # dạng chưa giải mã
    ".." + chr(92) + ".." + chr(92) + "x",    # backslash thật
    "../../x",
    "2026-09/../../../etc",
    "....//....//x",
    "C:" + chr(92) + "Windows" + chr(92) + "x",
]


@pytest.mark.parametrize("ky", XAU)
def test_doc_bang_luong_tu_choi_ky_xau(ky):
    """Không ném lỗi lạ, chỉ trả None — route đã xử lý None thành 404."""
    assert luong.doc_bang_luong(ky) is None, f"KHONG chan: {ky!r}"


@pytest.mark.parametrize("thang", XAU)
def test_cham_cong_tu_choi_thang_xau(thang):
    assert cham_cong.doc_chot(thang) is None, f"KHONG chan: {thang!r}"


@pytest.mark.parametrize("ky", ["2026-09", "2025-01", "2030-12"])
def test_ky_dung_khuon_van_chay(ky):
    """KHÔNG được phá tính năng: kỳ hợp lệ vẫn đọc bình thường (None vì chưa có
    file, nhưng KHÔNG được ném lỗi)."""
    assert luong.doc_bang_luong(ky) is None or isinstance(luong.doc_bang_luong(ky), dict)


# ── ĐO ĐÚNG THỨ CẦN ĐO ────────────────────────────────────────────────────────
# BÀI HỌC 05/09: bản test đầu chỉ kiểm `doc_bang_luong(...) is None` và XANH NGAY
# TỪ ĐẦU — nhưng xanh vì FILE KHÔNG TỒN TẠI, chứ không phải vì bị chặn. Đường dẫn
# thật lúc đó VẪN thoát ra ngoài (đã soi tận mắt: .../bang-luong/../../secret.json
# → normpath ra .../secret.json). Test xanh ngay từ đầu là dấu hiệu TEST SAI.
# Hai test dưới đo trực tiếp cái cần chặn: hàm phải TỪ CHỐI, và không dựng nổi
# đường dẫn ra ngoài.

def test_ky_hop_le_tu_choi_dung():
    assert luong.ky_hop_le("2026-09") is True
    for xau in XAU + ["", None, "2026-9", "2026-13-01", "abc"]:
        assert luong.ky_hop_le(xau) is False, f"KHONG chan: {xau!r}"


def test_cham_cong_duong_nem_loi_thay_vi_dung_duong_xau():
    """`_duong` phải NÉM LỖI — không được lặng lẽ trả đường dẫn ra ngoài."""
    import pytest as _pt
    for xau in XAU:
        with _pt.raises(ValueError):
            cham_cong._duong(xau)
