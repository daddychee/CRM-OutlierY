# -*- coding: utf-8 -*-
"""Adapter SSO V3 (radary/auth.py): dịch claims OUTLIERY → vai NỘI BỘ radary.
Ghim: X-Remote-Actions ƯU TIÊN (tick chảy từng request), fallback X-Remote-Role
danh pháp chuẩn (admin→owner nội bộ), DEFAULT viewer fail-closed, user trắng
không nổ, RADARY_SSO_MAP đã GỠ HẲN (bài học map-tên-chết 04/08)."""
import radary.auth as auth


def test_actions_uu_tien_tung_ca():
    assert auth.vai_tu_headers({"X-Remote-Actions": "quan_tri"}) == "owner"
    assert auth.vai_tu_headers(
        {"X-Remote-Actions": "them_video,tao_pool,toan_quyen,quan_tri"}) == "owner"
    assert auth.vai_tu_headers({"X-Remote-Actions": "toan_quyen"}) == "manager"
    assert auth.vai_tu_headers(
        {"X-Remote-Actions": "them_video,tao_pool,toan_quyen"}) == "manager"
    assert auth.vai_tu_headers({"X-Remote-Actions": "them_video"}) == "leader"
    assert auth.vai_tu_headers({"X-Remote-Actions": "tao_pool"}) == "leader"
    assert auth.vai_tu_headers({"X-Remote-Actions": ""}) == "viewer"   # rỗng = fail-closed
    # hành động app KHÁC lọt vào (không bao giờ xảy ra qua gateway) → không thăng quyền
    assert auth.vai_tu_headers({"X-Remote-Actions": "nap_tai_lieu,kpi"}) == "viewer"
    # có Actions thì Role bị bỏ qua — Actions là nguồn sự thật mới
    assert auth.vai_tu_headers(
        {"X-Remote-Actions": "", "X-Remote-Role": "admin"}) == "viewer"


def test_fallback_role_khi_thieu_header_actions():
    assert auth.vai_tu_headers({"X-Remote-Role": "admin"}) == "owner"    # danh pháp mới
    assert auth.vai_tu_headers({"X-Remote-Role": "manager"}) == "manager"
    assert auth.vai_tu_headers({"X-Remote-Role": "leader"}) == "leader"
    assert auth.vai_tu_headers({"X-Remote-Role": "viewer"}) == "viewer"
    assert auth.vai_tu_headers({"X-Remote-Role": "owner"}) == "viewer"   # vai cũ hết giá trị
    assert auth.vai_tu_headers({"X-Remote-Role": "OWNER "}) == "viewer"
    assert auth.vai_tu_headers({}) == "viewer"                           # user trắng không nổ


def test_sso_map_da_go_han():
    assert not hasattr(auth, "_doc_sso_map")   # cấm map theo tên đăng nhập (luật ghim #3)
