# -*- coding: utf-8 -*-
"""RadarY vào V3 (APPS.md app 1/6): hợp đồng app + luật Permissions v2 + vai dịch
từ hành động — ghim luật 04/08 hệ cũ: tick toan_quyen phát MANAGER, KHÔNG BAO GIỜ
lên admin (Manager không ngang Owner)."""
import bcrypt
import pytest

from nen.common.hop_dong import tim_app
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    c = iam.ket_noi()
    yield c
    c.close()


def _owner(conn):
    return iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner", "mk-owner", "Ban quản trị", 5, phai_doi_mk=False))


def test_hop_dong_radary():
    a = tim_app("radary")
    assert a and a["cong"] == 9111 and a["health"] == "/api/health"
    assert a["tien_to"] == ["/api", "/app.js", "/vendor"]   # đo từ registry V2
    store = {d["ten"]: d for d in a["du_lieu"]}
    assert store["radary-db"]["backup"] == "sqlite-snapshot"     # cấm copy trần db
    assert store["radary-thumbs"]["muc_quy"] == "tai-sinh"       # thumbs không backup
    assert store["radary-secret"]["muc_quy"] == "vang"           # mất khóa = mất key


def test_luat_va_vai_radary_theo_thuong_quy(conn):
    """Ma trận mặc định: mọi bộ phận L1 xem; them_video/tao_pool KD L3;
    toan_quyen L4 (Manager); quan_tri chỉ Owner. Vai dừng-tại-hit-đầu."""
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> (vào, them_video, toan_quyen, vai)
        (("Vận hành - Sản xuất", 1), (True, False, False, "viewer")),
        (("Vận hành - Sản xuất", 3), (True, False, False, "viewer")),  # VH L3: không them
        (("Kinh doanh", 3), (True, True, False, "leader")),
        (("Kinh doanh", 4), (True, True, True, "manager")),            # L4 → vai_xoa manager
        (("", 2), (True, False, False, "viewer")),                     # user "trắng" không nổ
    ]
    for i, ((bp, lv), (vao, them, toan, vai)) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "123456", bp, lv)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "radary", conn) == vao, (bp, lv)
        assert iam.co_quyen(u, "them_video", "radary", conn) == them, (bp, lv)
        assert iam.co_quyen(u, "toan_quyen", "radary", conn) == toan, (bp, lv)
        assert iam.vai_cho_app(u, "radary", conn) == vai, (bp, lv)
    assert iam.vai_cho_app(ow, "radary", conn) == "admin"       # Owner: quan_tri → admin
    assert iam.cac_hanh_dong(ow, "radary", conn) == \
        ["them_video", "tao_pool", "toan_quyen", "quan_tri"]


def test_sidebar_tu_an_app_da_di_tru():
    """APPS.md bước 2: thêm app vào apps.json là sidebar tự ăn — sb_apps dựng từ
    giao hợp đồng × X-Remote-Apps; 3 app lõi + app-mau không lặp ở nhóm Tools."""
    from nen.common.sidebar import sb_apps_tu_claims
    ds = sb_apps_tu_claims(["radary", "ai-agent", "to-chuc", "app-mau"])
    assert ds == [{"slug": "radary", "ten": "RadarY"}]
    assert sb_apps_tu_claims([]) == []                # không quyền → không mục
    assert sb_apps_tu_claims(["la-lam"]) == []        # slug lạ ngoài hợp đồng → ẩn


def test_tick_toan_quyen_phat_manager_khong_len_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.vai_cho_app(nv, "radary", conn) == "viewer"
    iam.gan_override(conn, ow, "nv", "radary", "toan_quyen", True, "trực thay Manager")
    assert iam.vai_cho_app(nv, "radary", conn) == "manager"     # vai_xoa — KHÔNG admin
    assert "toan_quyen" in iam.cac_hanh_dong(nv, "radary", conn)
    assert iam.vai_cho_app(nv, "ai-agent", conn) == "viewer"    # app khác không lây
    iam.gan_override(conn, ow, "nv", "radary", "quan_tri", True, "thử nấc quản trị")
    assert iam.vai_cho_app(nv, "radary", conn) == "admin"       # chỉ quan_tri mới admin
