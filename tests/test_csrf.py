# -*- coding: utf-8 -*-
"""GĐ4 — CSRF: mọi route GHI phải đòi token (05/09/2026).

LỖ N1 (rà 05/09, sổ `docs/bao-mat-internet.md` — nghiêm trọng nhất tầng nền):
toàn bộ `nen/` không có một dòng CSRF nào; phòng thủ duy nhất là
`samesite="lax"`. 38 route POST, gồm tạo/sửa/xóa tài khoản, đặt cấp truy cập,
bật admin ủy quyền, thêm/thu hồi API key, đổi mật khẩu.

`SameSite=Lax` KHÔNG đủ khi ra Internet:
  - Lax cho cookie đi theo **top-level navigation**, và `/nen{duong:path}`
    (`main.py:2437`) trả **307 giữ nguyên method + body** → bàn đạp chuyển tiếp.
  - Cookie đặt ở `.outliery.test` (`main.py:171`) nên **subdomain khác cùng site
    không bị Lax chặn** — một subdomain bị chiếm là POST thay mặt Owner.

Thiết kế: token ký số, gắn với phiên, nhúng vào form (31 form) + gửi qua header
cho 2 chỗ fetch. Route GHI thiếu/sai token → 403.
"""
import pytest

from nen.common import csrf


def test_sinh_va_kiem_khop():
    t = csrf.sinh_token("owneruser")
    assert csrf.kiem_token(t, "owneruser") is True


def test_token_cua_nguoi_khac_bi_tu_choi():
    """Token của A không dùng được cho phiên của B."""
    t = csrf.sinh_token("owneruser")
    assert csrf.kiem_token(t, "nhanvien") is False


def test_token_rong_hoac_bay_bi_tu_choi():
    for xau in ["", None, "abc", "a.b.c"]:
        assert csrf.kiem_token(xau, "owneruser") is False


def test_token_sua_doi_bi_tu_choi():
    t = csrf.sinh_token("owneruser")
    assert csrf.kiem_token(t[:-2] + "xy", "owneruser") is False


def test_token_qua_han_bi_tu_choi(monkeypatch):
    """Sinh token với hạn ÂM (đã hết hạn ngay) — phải bị từ chối."""
    monkeypatch.setattr(csrf, "HAN_GIAY", -10)
    t = csrf.sinh_token("owneruser")
    assert csrf.kiem_token(t, "owneruser") is False


def test_so_sanh_hang_thoi_gian():
    import inspect
    assert "compare_digest" in inspect.getsource(csrf.kiem_token)
