# -*- coding: utf-8 -*-
"""Test D4 — lịch tài chính: đối soát 10–12, chốt công, trả lương 15 (tháng SAU kỳ)."""
from src import cham_cong, lich_tai_chinh, luong

KY = "2026-08"


def test_moc_roi_vao_thang_sau_ky():
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-01")}
    assert m["doi_soat"]["han"] == "2026-09-10…2026-09-12"
    assert m["tra_luong"]["han"] == "2026-09-15"
    m12 = {x["ma"]: x for x in lich_tai_chinh.moc_ky("2026-12", "2027-01-05")}
    assert m12["tra_luong"]["han"] == "2027-01-15"      # sang năm mới


def test_trang_thai_theo_ngay_va_viec_da_lam():
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-02")}
    assert m["chot_cong"]["trang_thai"] == "cho_den_han"
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-11")}
    assert m["chot_cong"]["trang_thai"] == "den_han"
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-20")}
    assert m["chot_cong"]["trang_thai"] == "tre_han"    # trễ thì NHẮC, không tự chạy
    cham_cong.chot_ky(KY, "hr")
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-20")}
    assert m["chot_cong"]["trang_thai"] == "xong"


def test_tra_luong_khoa_khi_chua_chot_cong():
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-01")}
    assert "chưa chốt công" in m["tra_luong"]["khoa_vi"].lower()
    cham_cong.chot_ky(KY, "hr")
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-01")}
    assert m["tra_luong"]["khoa_vi"] == ""


def test_moc_doi_soat_noi_thang_la_chua_co_module():
    """Không vẽ trạng thái giả cho việc chưa làm (B5)."""
    m = {x["ma"]: x for x in lich_tai_chinh.moc_ky(KY, "2026-09-11")}
    assert m["doi_soat"]["trang_thai"] == "chua_co_module"
    assert "B5" in m["doi_soat"]["khoa_vi"]
