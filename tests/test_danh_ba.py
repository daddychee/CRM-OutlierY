# -*- coding: utf-8 -*-
"""Test danh bạ thực thể — mảnh ④ tầng nền (P0.6)."""
from nen.common import danh_ba  # conftest.py ở root đưa root vào sys.path


def _viet_csv(tmp_path, noi_dung):
    f = tmp_path / "danh_muc.csv"
    f.write_text(noi_dung, encoding="utf-8")
    return f


CSV_MAU = (
    "loai,ma,ten_chuan,bi_danh,seo_profile,plannery_project,"
    "radary_niche,niche_project,mau_ten_bao_cao,ghi_chu\n"
    "kenh,K-OUTLAND,Outland,outland;outland kr,outland-kr-ok-01,,,,outland*,\n"
    "ngach,N-LIFEIN,Life In,life in;đời sống mỹ,life-in,,16,Life_In,,\n"
)


# ---------- chuan_hoa_ten ----------

def test_chuan_hoa_bo_dau_va_d():
    assert danh_ba.chuan_hoa_ten("Đời Sống Mỹ") == "doi song my"


def test_chuan_hoa_gon_khoang_trang_va_hoa_thuong():
    assert danh_ba.chuan_hoa_ten("  Life   IN ") == "life in"


def test_chuan_hoa_rong():
    assert danh_ba.chuan_hoa_ten("") == ""


# ---------- tra_thuc_the ----------

def test_tra_theo_ten_chuan(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    assert danh_ba.tra_thuc_the("outland", duong=f)["ma"] == "K-OUTLAND"


def test_tra_theo_bi_danh_khong_phan_biet_hoa(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    assert danh_ba.tra_thuc_the("OUTLAND KR", duong=f)["ma"] == "K-OUTLAND"


def test_tra_bi_danh_co_dau_bang_cau_khong_dau(tmp_path):
    # bí danh lưu CÓ dấu, người gõ KHÔNG dấu vẫn khớp (chuẩn hóa 2 phía)
    f = _viet_csv(tmp_path, CSV_MAU)
    assert danh_ba.tra_thuc_the("doi song my", duong=f)["ma"] == "N-LIFEIN"


def test_tra_loc_theo_loai(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    assert danh_ba.tra_thuc_the("outland", loai="ngach", duong=f) is None
    assert danh_ba.tra_thuc_the("outland", loai="kenh", duong=f) is not None


def test_khong_khop_tra_none_khong_doan(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    assert danh_ba.tra_thuc_the("kenh chua ton tai", duong=f) is None


def test_dong_hong_thieu_ma_bi_bo_qua(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU + ",,,,,,,,,\n")
    assert len(danh_ba.doc_danh_muc(f)) == 2


# ---------- khoa_ung_dung ----------

def test_khoa_ung_dung_co_gia_tri(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    t = danh_ba.tra_thuc_the("outland", duong=f)
    assert danh_ba.khoa_ung_dung(t, "seo_profile") == "outland-kr-ok-01"


def test_khoa_ung_dung_trong_tra_none(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    t = danh_ba.tra_thuc_the("outland", duong=f)
    assert danh_ba.khoa_ung_dung(t, "plannery_project") is None


def test_khoa_ung_dung_cot_la_tra_none(tmp_path):
    f = _viet_csv(tmp_path, CSV_MAU)
    t = danh_ba.tra_thuc_the("outland", duong=f)
    assert danh_ba.khoa_ung_dung(t, "cot_khong_ton_tai") is None


# ---------- file seed thật ----------

def test_file_seed_that_doc_duoc_va_co_kenh():
    ds = danh_ba.doc_danh_muc()  # đường mặc định platform/rules/danh_muc.csv
    assert any(t["loai"] == "kenh" for t in ds)
    assert danh_ba.tra_thuc_the("outland") is not None
