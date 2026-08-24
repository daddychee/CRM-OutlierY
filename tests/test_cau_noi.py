# -*- coding: utf-8 -*-
"""Test cầu nối P6: router khớp danh bạ, quyền người hỏi, van chống bịa số liệu."""
import bcrypt
import httpx
import pytest

from nen.common import cau_noi
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def he(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    # Đ1 khối đế: danh bạ chuyển CSV → SQLite, seed test qua chính API ghi
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    from nen.common import danh_ba
    db = danh_ba.ket_noi()
    ng = danh_ba.them_ngach(db, "Life In")
    ma = danh_ba.them_kenh(db, "Outland", ng)          # sinh mã K-OUTLAND
    danh_ba.them_bi_danh(db, ma, "outland kr")
    danh_ba.them_kenh(db, "Space", ng)
    db.close()
    conn = iam.ket_noi()
    yield conn
    conn.close()


KD_L2 = {"ten": "nv", "level": 2, "vai": "viewer", "bo_phan": "Kinh doanh"}
VH_L2 = {"ten": "vh", "level": 2, "vai": "viewer", "bo_phan": "Vận hành - Sản xuất"}


def test_router_khong_khop_hoi_lai_khong_doan(he):
    kq = cau_noi.hoi_so_lieu("kênh nào đó tuần rồi thế nào", KD_L2, he)
    assert kq["loai"] == "khong_khop"
    assert "Outland" in kq["goi_y"]          # gợi ý từ danh bạ, không đoán


def test_router_khop_bi_danh_khong_dau(he, monkeypatch):
    goi = {}
    monkeypatch.setattr(cau_noi, "bao_cao_kenh",
                        lambda kenh, user, conn=None: goi.update(ma=kenh["ma"]) or {"loai": "x"})
    cau_noi.hoi_so_lieu("tuan roi kenh OUTLAND KR the nao?", KD_L2, he)
    assert goi["ma"] == "K-OUTLAND"


def test_router_nhieu_kenh_hoi_lai(he):
    kq = cau_noi.hoi_so_lieu("so sánh outland với space", KD_L2, he)
    assert kq["loai"] == "nhieu_kenh"
    assert set(kq["goi_y"]) == {"Outland", "Space"}


def test_quyen_nguoi_hoi_bi_chan_noi_thang(he):
    """LUẬT 19/08: MỌI nhân sự xem được Data Analytics → Vận hành L2 giờ hỏi
    được (trước bị rào bộ phận Kinh doanh). Cơ chế 'bị chặn thì NÓI THẲNG' vẫn
    phải sống, nên ca chặn giờ dựng bằng ô tick deny của Owner."""
    assert cau_noi.bao_cao_kenh(
        {"ten_chuan": "Outland", "ma": "K-OUTLAND"}, VH_L2, he
    )["loai"] != "khong_du_quyen"

    ow = iam.claims_cua(iam.tao_tai_khoan(
        he, None, "owner-test", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(he, ow, "vh", "mk-vh-6", "Vận hành - Sản xuất", 2,
                      phai_doi_mk=False)
    iam.gan_override(he, ow, "vh", "data-analytics", "vao", False, "tạm khóa bàn giao")

    kq = cau_noi.bao_cao_kenh({"ten_chuan": "Outland", "ma": "K-OUTLAND"}, VH_L2, he)
    assert kq["loai"] == "khong_du_quyen"
    assert "Data Analytics" in kq["noi_thang"]   # app nói THẲNG, khác tài liệu lặng lẽ


def test_nguon_chet_noi_thang_khong_bia(he, monkeypatch):
    def _chet(*a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(cau_noi, "_goi_api_app", _chet)
    kq = cau_noi.bao_cao_kenh({"ten_chuan": "Outland", "ma": "K-OUTLAND"}, KD_L2, he)
    assert kq["loai"] == "nguon_chet"
    assert "Sức khỏe" in kq["noi_thang"]


def test_chua_co_bao_cao_noi_thang(he, monkeypatch):
    class _R:
        def raise_for_status(self): ...
        def json(self): return {"bao_cao": [
            {"id": "x1", "ten": "space thang 7", "thoi_gian": "T", "nguoi_chay": "nv"}]}
    monkeypatch.setattr(cau_noi, "_goi_api_app", lambda *a, **k: _R())
    kq = cau_noi.bao_cao_kenh({"ten_chuan": "Outland", "ma": "K-OUTLAND"}, KD_L2, he)
    assert kq["loai"] == "chua_co_bao_cao"
    assert "upload" in kq["noi_thang"]           # chỉ đường hành động, không bịa số


def test_co_bao_cao_kem_nguon_va_tuoi(he, monkeypatch):
    class _R:
        def raise_for_status(self): ...
        def json(self): return {"bao_cao": [
            {"id": "ab12", "ten": "T32", "ten_kenh": "Outland",
             "thoi_gian": "2026-08-12T10:00:00",
             "nguoi_chay": "thanh", "tang_vo": "retention", "so_video": 80},
            {"id": "cd34", "ten": "outland thang 7", "ten_kenh": "",
             "thoi_gian": "2026-07-12T10:00:00", "nguoi_chay": "thanh"}]}
    monkeypatch.setattr(cau_noi, "_goi_api_app", lambda *a, **k: _R())
    kq = cau_noi.bao_cao_kenh({"ten_chuan": "Outland", "ma": "K-OUTLAND"}, KD_L2, he)
    assert kq["loai"] == "co_bao_cao"
    assert kq["bao_cao"]["id"] == "ab12"         # mới nhất trước
    assert kq["so_bao_cao"] == 2
    assert kq["tuoi_du_lieu"].startswith("2026-08-12")   # tuổi dữ liệu bắt buộc
    assert "thanh" in kq["nguon"]


def test_router_ranh_gioi_tu_va_uu_tien_ten_dai_nhat(he, monkeypatch):
    # Đ2: "Life" và "Life In" cùng tồn tại — tên DÀI NHẤT thắng, hết nhieu_kenh oan
    from nen.common import danh_ba
    db = danh_ba.ket_noi()
    ng = danh_ba.them_ngach(db, "Test")
    danh_ba.them_kenh(db, "Life", ng)
    danh_ba.them_kenh(db, "Life In", ng)
    db.close()
    goi = {}
    monkeypatch.setattr(cau_noi, "bao_cao_kenh",
                        lambda kenh, user, conn=None: goi.update(ma=kenh["ma"]) or {"loai": "x"})
    cau_noi.hoi_so_lieu("kênh life in dạo này thế nào", KD_L2, he)
    assert goi["ma"] == "K-LIFE-IN"
    # ranh giới từ: "lifetime" KHÔNG khớp kênh "Life" (hết substring trần)
    kq = cau_noi.hoi_so_lieu("lifetime value là gì", KD_L2, he)
    assert kq["loai"] == "khong_khop"
