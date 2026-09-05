# -*- coding: utf-8 -*-
"""GĐ6 — Cookie phiên phải có cờ `secure` khi chạy HTTPS (05/09/2026).

LỖ N3 (một phần): cookie đặt `httponly` + `samesite=lax` nhưng THIẾU `secure=True`
→ trình duyệt gửi cookie qua cả kết nối HTTP. Ra Internet, chỉ cần một liên kết
`http://` là cookie rò ra ngoài dù đã có HTTPS.

KHÔNG bật cứng được ngay: hệ hiện chạy HTTP trên LAN (cổng 9000), bật `secure`
là trình duyệt TỪ CHỐI LƯU cookie → **không ai đăng nhập được**.
→ Cờ theo biến môi trường `COOKIE_SECURE`, bật cùng lúc với HTTPS thật (GĐ6).
"""
import os

import pytest


def test_mac_dinh_tat_de_khong_pha_lan_http(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    import importlib

    from nen.gateway import main
    importlib.reload(main)
    assert main.COOKIE_SECURE is False


def test_bat_duoc_qua_bien_moi_truong(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "1")
    import importlib

    from nen.gateway import main
    importlib.reload(main)
    assert main.COOKIE_SECURE is True
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    importlib.reload(main)


def test_set_cookie_dung_co(monkeypatch):
    """Cờ phải thực sự đi vào lời gọi set_cookie, không chỉ là biến treo."""
    import inspect

    from nen.gateway import main
    ma = inspect.getsource(main)
    assert "secure=COOKIE_SECURE" in ma, "set_cookie phải dùng biến COOKIE_SECURE"
