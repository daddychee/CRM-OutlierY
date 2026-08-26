# -*- coding: utf-8 -*-
"""LỊCH TÀI CHÍNH (D4) — Owner chốt: báo cáo tổng ngày 10–12 hằng tháng (ngày
YouTube tổng tiền), lương trả ngày 15.

Kỳ kế toán VẪN là tháng dương lịch — đổi kỳ là đổi mọi phép cộng. Cái theo mốc
này chỉ là LỊCH VIỆC của kỳ đó, và mọi việc đều làm ở tháng SAU kỳ.

Trạng thái mốc: xong · den_han · tre_han · cho_den_han · chua_co_module.
Trễ hạn thì NHẮC, không tự chạy — không mốc nào tự sinh bút toán.
"""
from __future__ import annotations

from datetime import date

from src import cham_cong, luong

NGAY_DOI_SOAT_TU, NGAY_DOI_SOAT_DEN = 10, 12
NGAY_TRA_LUONG = 15


def _thang_sau(ky: str) -> tuple[int, int]:
    nam, thang = int(ky[:4]), int(ky[5:7])
    return (nam + 1, 1) if thang == 12 else (nam, thang + 1)


def _trang_thai(han: str, hom_nay: str, xong: bool, den_han_tu: str = "") -> str:
    if xong:
        return "xong"
    if hom_nay > han:
        return "tre_han"
    if hom_nay >= (den_han_tu or han):
        return "den_han"
    return "cho_den_han"


def moc_ky(ky: str, hom_nay: str = "") -> list[dict]:
    """Ba mốc của một kỳ. `khoa_vi` = lý do mốc chưa mở được (phụ thuộc mốc trước)."""
    hom_nay = hom_nay or date.today().isoformat()
    nam, thang = _thang_sau(ky)
    tu = date(nam, thang, NGAY_DOI_SOAT_TU).isoformat()
    den = date(nam, thang, NGAY_DOI_SOAT_DEN).isoformat()
    han_luong = date(nam, thang, NGAY_TRA_LUONG).isoformat()

    da_chot_cong = cham_cong.doc_chot(ky) is not None
    da_duyet_luong = luong.doc_bang_luong(ky) is not None

    return [
        {"ma": "doi_soat", "ten": "Google chốt tiền — nạp CSV, đối soát doanh thu",
         "han": f"{tu}…{den}", "trang_thai": "chua_co_module",
         "khoa_vi": "Đối soát AdSense (B5) chưa làm — hiện ghi doanh thu tay."},
        {"ma": "chot_cong", "ten": "Chốt công kỳ",
         "han": den, "trang_thai": _trang_thai(den, hom_nay, da_chot_cong, tu),
         "khoa_vi": ""},
        {"ma": "tra_luong", "ten": "Duyệt bảng lương → bút toán CHI-LUONG",
         "han": han_luong,
         "trang_thai": _trang_thai(han_luong, hom_nay, da_duyet_luong),
         "khoa_vi": "" if da_chot_cong else "Chưa chốt công kỳ này."},
    ]
