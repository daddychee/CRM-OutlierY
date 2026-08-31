# -*- coding: utf-8 -*-
"""ThumbY V1 (app V3 mới 31/08 — spec docs/thumby.md): hợp đồng app + luật
Permissions v2. Owner chốt: vào CHỈ Kinh doanh L2+; V1 không hành động ghi
(app mô phỏng client-side, du_lieu rỗng — ảnh không rời trình duyệt)."""
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


def test_hop_dong_thumby():
    a = tim_app("thumby")
    assert a and a["cong"] == 9119 and a["health"] == "/health"
    assert a["tien_to"] == ["/thumby", "/thumby-static"]
    assert a["chay"]["app_dir"] == "apps/thumby"
    # VAN SPEC: V1 không lưu gì server-side — ai khai kho dữ liệu là đổi spec
    assert a["du_lieu"] == []
    # app native (tự vẽ sidebar OUTLIERY) — không đi đường khung /open
    assert "giao_dien" not in a


def test_luat_vao_chi_kinh_doanh_l2(conn):
    """Ma trận cửa vào: KD L2+ vào; bộ phận khác không; user 'trắng' không nổ;
    Manager+ vào theo lệ chung (min_level thỏa, L4 bỏ rào bộ phận ở co_quyen)."""
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> vào
        (("Kinh doanh", 1), False),                # KD L1 chưa đủ
        (("Kinh doanh", 2), True),
        (("Kinh doanh", 3), True),
        (("Vận hành - Sản xuất", 2), False),       # BP khác không vào
        (("Vận hành - Sản xuất", 4), True),        # Manager bộ phận khác: lệ chung L4+
        (("", 2), False),                          # user "trắng" không nổ
    ]
    for i, ((bp, lv), vao) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "123456", bp, lv)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "thumby", conn) == vao, (bp, lv)
    assert iam.co_quyen(ow, "vao", "thumby", conn) is True


def test_v1_khong_hanh_dong_ghi(conn):
    """V1 chỉ có cửa vào — kể cả Owner cũng không có cờ hành động nào (app không
    ghi gì). Thêm hành động mới (GĐ2 lưu bộ thumbnail...) phải qua spec trước."""
    ow = _owner(conn)
    assert iam.cac_hanh_dong(ow, "thumby", conn) == []
