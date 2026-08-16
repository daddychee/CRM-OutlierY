# -*- coding: utf-8 -*-
"""Content Ultimate vào V3 (APPS.md app 2/6): hợp đồng app + luật Permissions v2.
Ghim chốt V2 31/07 + 04/08: VH L2 vào · sua VH L3 (vai leader = TRẦN vận hành,
Manager không ngang Owner) · quan_tri chỉ Owner · KHÔNG khai xoa (không trỏ
chức năng thật)."""
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


def test_hop_dong_content_ultimate():
    a = tim_app("content-ultimate")
    assert a and a["cong"] == 9112 and a["health"] == "/api/health"
    assert a["tien_to"] == ["/api", "/oe", "/author", "/outline", "/write",
                            "/manage", "/settings", "/logout"]   # đo từ registry V2 (vụ 6d9f069)
    store = {d["ten"]: d for d in a["du_lieu"]}
    assert store["cu-cookies"]["muc_quy"] == "vang"              # SECRET có danh phận
    assert store["cu-admin"]["duong"].endswith("admin")          # KPI đọc history.jsonl


def test_luat_khong_khai_xoa_va_ma_tran_vao(conn):
    assert set(iam.hanh_dong_cua_app("content-ultimate")) == {"sua", "quan_tri"}
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> (vào, sua, vai)
        (("Kinh doanh", 2), (False, False, "creator-khong-vao")),  # KD không thuộc VH
        (("Vận hành - Sản xuất", 1), (False, False, "-")),          # VH L1 chưa đủ
        (("Vận hành - Sản xuất", 2), (True, False, "viewer")),
        (("Vận hành - Sản xuất", 3), (True, True, "leader")),
        (("Vận hành - Sản xuất", 4), (True, True, "leader")),       # Manager VH = trần leader
        (("Kinh doanh", 4), (True, True, "leader")),                # L4 bỏ rào bộ phận (luật engine)
    ]
    for i, ((bp, lv), (vao, sua, _)) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "123456", bp, lv)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "content-ultimate", conn) == vao, (bp, lv)
        assert iam.co_quyen(u, "sua", "content-ultimate", conn) == sua, (bp, lv)
    # vai dịch hit-đầu: sua→leader; KHÔNG có đường nào ra manager/admin ngoài quan_tri
    u3 = iam.claims_cua(iam.lay_tai_khoan(conn, "u3"))
    u4 = iam.claims_cua(iam.lay_tai_khoan(conn, "u4"))
    assert iam.vai_cho_app(u3, "content-ultimate", conn) == "leader"
    assert iam.vai_cho_app(u4, "content-ultimate", conn) == "leader"   # Manager KHÔNG admin
    assert iam.vai_cho_app(ow, "content-ultimate", conn) == "admin"    # Owner qua quan_tri


def test_tick_sua_phat_leader_khong_len_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Vận hành - Sản xuất", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.vai_cho_app(nv, "content-ultimate", conn) == "viewer"
    iam.gan_override(conn, ow, "nv", "content-ultimate", "sua", True, "trực nhật ký thay leader")
    assert iam.vai_cho_app(nv, "content-ultimate", conn) == "leader"   # KHÔNG admin
    assert iam.cac_hanh_dong(nv, "content-ultimate", conn) == ["sua"]
    iam.gan_override(conn, ow, "nv", "content-ultimate", "quan_tri", True, "thử nấc quản trị")
    assert iam.vai_cho_app(nv, "content-ultimate", conn) == "admin"    # chỉ quan_tri mới admin
