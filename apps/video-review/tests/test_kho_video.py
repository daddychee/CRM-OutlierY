# -*- coding: utf-8 -*-
"""Test tầng dữ liệu kho_video — sổ SQLite + luật quyền bình luận."""
import sqlite3

import pytest

from src import kho_video


def test_khoi_tao_ghi_schema_version():
    conn = kho_video.ket_noi()
    try:
        v = conn.execute("SELECT v FROM schema_version").fetchone()["v"]
    finally:
        conn.close()
    assert v >= 1


def test_khoi_tao_chay_lai_khong_vo():
    kho_video.khoi_tao()   # idempotent — chạy lần 2 không nổ
    kho_video.khoi_tao()


def test_them_video_ma_bat_bien_va_duong_nam_thang():
    b = kho_video.them_video("Bản dựng Tập 1 — Đảo hoang", ".mp4", "an", "Vận hành", 123)
    assert b["ma"] == "VR-0001"
    # Luật 5: năm/tháng + khuôn tên YYYY-MM-DD_<ma>_<slug>; 'Đ' phải thành 'd'
    assert b["duong"].count("/") == 2
    assert "_VR-0001_" in b["ten_file"]
    assert "dao-hoang" in b["ten_file"]
    b2 = kho_video.them_video("hai", ".webm", "an", "Vận hành", 1)
    assert b2["ma"] == "VR-0002"


def test_them_video_duoi_la_bi_chan():
    with pytest.raises(ValueError):
        kho_video.them_video("x", ".exe", "an", "", 1)


def test_doi_trang_thai_va_go_mem():
    b = kho_video.them_video("x", ".mp4", "an", "", 1)
    kho_video.doi_trang_thai(b["ma"], "da_duyet")
    assert kho_video.lay_video(b["ma"])["trang_thai"] == "da_duyet"
    with pytest.raises(ValueError):
        kho_video.doi_trang_thai(b["ma"], "bay_bay")
    # gỡ mềm → biến khỏi danh sách nhưng bản ghi còn
    kho_video.doi_trang_thai(b["ma"], "da_xoa")
    assert all(v["ma"] != b["ma"] for v in kho_video.danh_sach_video())
    assert kho_video.lay_video(b["ma"]) is not None


def test_binh_luan_vong_doi_va_quyen():
    b = kho_video.them_video("x", ".mp4", "an", "", 1)
    bl = kho_video.them_binh_luan(b["ma"], "an", "cắt cảnh này", ts_giay=12.5,
                                  ve_json='{"net": []}')
    assert bl["ts_giay"] == 12.5
    # người khác KHÔNG duyệt → cấm giải/xóa
    with pytest.raises(PermissionError):
        kho_video.giai_binh_luan(bl["id"], "binh", False)
    # chính chủ giải được; leader (co_duyet) mở lại được
    kho_video.giai_binh_luan(bl["id"], "an", False)
    assert kho_video.ds_binh_luan(b["ma"])[0]["trang_thai"] == "da_giai"
    kho_video.mo_lai_binh_luan(bl["id"], "chi", True)
    kho_video.xoa_binh_luan(bl["id"], "chi", True)
    assert kho_video.ds_binh_luan(b["ma"]) == []


def test_binh_luan_chan_rong_va_ve_json_hong_va_video_ma():
    b = kho_video.them_video("x", ".mp4", "an", "", 1)
    with pytest.raises(ValueError):
        kho_video.them_binh_luan(b["ma"], "an", "   ")
    with pytest.raises(ValueError):
        kho_video.them_binh_luan(b["ma"], "an", "ok", ve_json="{hong")
    with pytest.raises(KeyError):
        kho_video.them_binh_luan("VR-9999", "an", "ok")


def test_ds_binh_luan_moc_truoc_chung_sau():
    b = kho_video.them_video("x", ".mp4", "an", "", 1)
    kho_video.them_binh_luan(b["ma"], "an", "chung")               # không mốc
    kho_video.them_binh_luan(b["ma"], "an", "muon", ts_giay=30)
    kho_video.them_binh_luan(b["ma"], "an", "som", ts_giay=5)
    ds = [x["noi_dung"] for x in kho_video.ds_binh_luan(b["ma"])]
    assert ds == ["som", "muon", "chung"]


def test_danh_sach_dem_binh_luan_mo():
    b = kho_video.them_video("x", ".mp4", "an", "", 1)
    bl = kho_video.them_binh_luan(b["ma"], "an", "một")
    kho_video.them_binh_luan(b["ma"], "an", "hai")
    kho_video.giai_binh_luan(bl["id"], "an", False)
    hang = kho_video.danh_sach_video()[0]
    assert hang["so_mo"] == 1
    assert hang["so_tong"] == 2      # so_tong đếm CẢ đã giải — tín hiệu "đã có người review"
