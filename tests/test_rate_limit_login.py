# -*- coding: utf-8 -*-
"""GĐ4 — RATE LIMIT đăng nhập (05/09/2026).

LỖ N2 (rà 05/09, sổ `docs/bao-mat-internet.md`): `/login` không đếm lần sai,
không khóa tạm, không delay, không CAPTCHA. Cộng với mật khẩu tối thiểu 6 ký tự
(N8) = tài khoản bị dò.

Kèm rủi ro DoS: `/login` chạy bcrypt SYNC trong threadpool (có chủ đích — bcrypt
là CPU-bound, để async là block event loop). Bắn vài trăm request/giây làm CẠN
THREADPOOL → cả cổng đứng, không chỉ đăng nhập.

Thiết kế: đếm theo (tên đăng nhập, IP), khóa tăng dần. Chặn TRƯỚC khi chạy bcrypt
để đóng luôn đường DoS.
"""
import pytest

from nen.common import chan_do


@pytest.fixture(autouse=True)
def _sach():
    chan_do.xoa_het()
    yield
    chan_do.xoa_het()


def test_duoi_nguong_thi_cho_qua():
    for _ in range(chan_do.SO_LAN_TOI_DA - 1):
        chan_do.ghi_that_bai("nv", "1.2.3.4")
    assert chan_do.bi_chan("nv", "1.2.3.4") is False


def test_vuot_nguong_thi_chan():
    for _ in range(chan_do.SO_LAN_TOI_DA):
        chan_do.ghi_that_bai("nv", "1.2.3.4")
    assert chan_do.bi_chan("nv", "1.2.3.4") is True


def test_dang_nhap_dung_xoa_bo_dem():
    for _ in range(chan_do.SO_LAN_TOI_DA):
        chan_do.ghi_that_bai("nv", "1.2.3.4")
    chan_do.ghi_thanh_cong("nv", "1.2.3.4")
    assert chan_do.bi_chan("nv", "1.2.3.4") is False


def test_chan_theo_TUNG_KHOA_khong_lay_nguoi_khac():
    """Kẻ tấn công dò tài khoản 'owneruser' không được khóa lây người thật."""
    for _ in range(chan_do.SO_LAN_TOI_DA):
        chan_do.ghi_that_bai("owneruser", "9.9.9.9")
    assert chan_do.bi_chan("owneruser", "9.9.9.9") is True
    assert chan_do.bi_chan("owneruser", "1.2.3.4") is False   # IP khác
    assert chan_do.bi_chan("nhanvien", "9.9.9.9") is False    # tên khác


def test_khoa_tang_dan():
    """Sai càng nhiều, chờ càng lâu — chống dò kiên trì."""
    for _ in range(chan_do.SO_LAN_TOI_DA):
        chan_do.ghi_that_bai("nv", "1.2.3.4")
    d1 = chan_do.con_lai("nv", "1.2.3.4")
    for _ in range(chan_do.SO_LAN_TOI_DA):
        chan_do.ghi_that_bai("nv", "1.2.3.4")
    assert chan_do.con_lai("nv", "1.2.3.4") > d1
