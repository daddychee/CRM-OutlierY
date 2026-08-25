# -*- coding: utf-8 -*-
"""THÔNG BÁO TRONG HỆ (Owner chốt 24/08) — huy hiệu + khối "Cần chú ý".

KHÔNG có kênh ngoài ở vòng này: web push cần secure context mà hệ chạy http://IP:9000
(bài học `crypto.randomUUID` 01/08), Telegram/email để sau nếu dùng thật thấy thiếu.

Bốn việc đáng báo Owner chọn, kèm MỨC ĐỘ bằng màu:
  cap    (đỏ)   — việc kẹt · việc giao quá 1 ngày chưa ai nhận
  luu_y  (vàng) — chờ leader xác nhận · việc bị từ chối cần giao lại · nhắc cuối tuần
  tin    (xanh) — việc vừa được giao cho bạn

Thông báo SINH TỪ TRẠNG THÁI THẬT của sổ tuần mỗi lần mở trang — không có bảng
"đã đọc / chưa đọc", nên không bao giờ lệch với dữ liệu. Hết việc là hết báo.
"""
from __future__ import annotations

import os
from datetime import date, datetime

from src import tuan as t

CAP, LUU_Y, TIN = "cap", "luu_y", "tin"
_THU_TU = {CAP: 3, LUU_Y: 2, TIN: 1}


def _gio_cho_nhan() -> float:
    """Giao bao lâu mà chưa ai nhận thì thành việc gấp (đổi bằng env, không sửa code)."""
    try:
        return float(os.getenv("TASKY_GIO_CHO_NHAN", "24"))
    except ValueError:
        return 24.0


def _qua_han(luc_tao: str, gio: float) -> bool:
    try:
        return (datetime.now() - datetime.fromisoformat(luc_tao)).total_seconds() > gio * 3600
    except (TypeError, ValueError):
        return False


def _cuoi_tuan(ma: str, hom_nay: date | None = None) -> bool:
    """Thứ Sáu trở đi CỦA CHÍNH tuần đang xem — xem tuần cũ/tuần sau thì không nhắc."""
    hom_nay = hom_nay or date.today()
    return t.ma_tuan(hom_nay) == ma and hom_nay.weekday() >= 4


def _muc(muc_do: str, chu: str, so: int, duong: str) -> dict:
    return {"muc_do": muc_do, "chu": chu, "so": so, "duong": duong}


def cua_toi(ma: str, user: dict) -> list[dict]:
    """Thông báo về việc CỦA CHÍNH user (mọi người đều có)."""
    ds = t.viec_cua(ma, user["ten"])
    ra: list[dict] = []

    ket = [v for v in ds if v["so_lan_doi"] >= t.DOI_LA_KET
           and v["trang_thai"] in (t.CHO_NHAN, t.DANG_LAM, t.BAO_XONG)]
    if ket:
        ra.append(_muc(CAP, f"{len(ket)} việc kẹt — đã dời từ 2 tuần trước", len(ket), "/tasky"))

    song = [v for v in ds if v["trang_thai"] in (t.CHO_NHAN, t.CHO_PHOI_HOP,
                                                 t.DANG_LAM, t.BAO_XONG)]
    qua = [v for v in song if t.tinh_han(v)["chu"].startswith("Quá hạn")]
    if qua:
        ra.append(_muc(CAP, f"{len(qua)} việc đã quá hạn", len(qua), "/tasky"))
    hom_nay = [v for v in song if t.tinh_han(v)["chu"] == "Hạn hôm nay"]
    if hom_nay:
        ra.append(_muc(CAP, f"{len(hom_nay)} việc đến hạn hôm nay", len(hom_nay), "/tasky"))
    gap = [v for v in song if v.get("gap") and v not in qua and v not in hom_nay]
    if gap:
        ra.append(_muc(CAP, f"{len(gap)} việc được đánh dấu GẤP", len(gap), "/tasky"))

    ph = [v for v in ds if v["trang_thai"] == t.CHO_PHOI_HOP]
    if ph:
        ra.append(_muc(CAP if any(_qua_han(v["luc_tao"], _gio_cho_nhan()) for v in ph) else LUU_Y,
                       f"{len(ph)} yêu cầu phối hợp từ bộ phận khác đang chờ bạn trả lời",
                       len(ph), "/tasky"))

    cho = [v for v in ds if v["trang_thai"] == t.CHO_NHAN]
    tre = [v for v in cho if _qua_han(v["luc_tao"], _gio_cho_nhan())]
    if tre:
        ra.append(_muc(CAP, f"{len(tre)} việc giao đã quá 1 ngày mà bạn chưa nhận",
                       len(tre), "/tasky"))
    if len(cho) - len(tre) > 0:
        ra.append(_muc(TIN, f"{len(cho) - len(tre)} việc mới được giao cho bạn",
                       len(cho) - len(tre), "/tasky"))

    if _cuoi_tuan(ma):
        con = [v for v in ds if v["trang_thai"] in (t.CHO_NHAN, t.DANG_LAM)]
        if con:
            ra.append(_muc(LUU_Y, f"Sắp hết tuần — còn {len(con)} việc chưa xong",
                           len(con), "/tasky"))
    return ra


def cua_leader(ma: str, user: dict, ds_nguoi: list[dict]) -> list[dict]:
    """Thông báo về QUÂN của leader. `ds_nguoi` do route lọc sẵn (lõi không tự đoán
    ai quản ai) — chỉ đếm người trong phạm vi đó."""
    trong_pv = {n["ten"] for n in ds_nguoi}
    viec = [v for v in t.doc_tuan(ma)["viec"] if v["nguoi"] in trong_pv]
    ra: list[dict] = []

    cho_xn = [v for v in viec if v["trang_thai"] == t.BAO_XONG and t.duoc_xac_nhan(v, user)]
    if cho_xn:
        ra.append(_muc(LUU_Y, f"{len(cho_xn)} việc chờ bạn xác nhận", len(cho_xn), "/bao-cao-tuan"))

    tu_choi = [v for v in viec if v["trang_thai"] == t.TU_CHOI and v.get("nguoi_giao") == user["ten"]]
    if tu_choi:
        ra.append(_muc(LUU_Y, f"{len(tu_choi)} việc bị từ chối — cần giao lại",
                       len(tu_choi), "/bao-cao-tuan"))

    gui = t.yeu_cau_da_gui(ma, user)
    xong_ph = [v for v in gui if v["trang_thai"] == t.BAO_XONG]
    if xong_ph:
        ra.append(_muc(LUU_Y, f"{len(xong_ph)} việc phối hợp chờ bạn nghiệm thu",
                       len(xong_ph), "/bao-cao-tuan"))
    tu_choi_ph = [v for v in gui if v["trang_thai"] == t.TU_CHOI]
    if tu_choi_ph:
        ra.append(_muc(LUU_Y, f"{len(tu_choi_ph)} yêu cầu phối hợp bị bộ phận kia từ chối",
                       len(tu_choi_ph), "/bao-cao-tuan"))

    song_bp = [v for v in viec if v["trang_thai"] in (t.CHO_NHAN, t.CHO_PHOI_HOP,
                                                     t.DANG_LAM, t.BAO_XONG)]
    qua_bp = [v for v in song_bp if t.tinh_han(v)["chu"].startswith("Quá hạn")]
    if qua_bp:
        ra.append(_muc(CAP, f"{len(qua_bp)} việc của bộ phận đã quá hạn",
                       len(qua_bp), "/bao-cao-tuan"))

    ket = [v for v in viec if v["so_lan_doi"] >= t.DOI_LA_KET
           and v["trang_thai"] in (t.CHO_NHAN, t.DANG_LAM, t.BAO_XONG)]
    if ket:
        ra.append(_muc(CAP, f"{len(ket)} việc của bộ phận đang kẹt", len(ket), "/bao-cao-tuan"))

    if _cuoi_tuan(ma):
        so = t.doc_tuan(ma)["dong"]
        chua = [n for n in ds_nguoi if n["ten"] not in so]
        if chua:
            ra.append(_muc(LUU_Y, f"{len(chua)} người chưa đóng tuần", len(chua), "/bao-cao-tuan"))
    return ra


def tom_tat(ds: list[dict]) -> dict:
    """Huy hiệu sidebar: tổng số + MỨC CAO NHẤT để tô màu. Rỗng → so = 0, muc_do rỗng
    (template ẩn huy hiệu — không vẽ chấm '0' vô nghĩa)."""
    if not ds:
        return {"so": 0, "muc_do": ""}
    return {"so": sum(m["so"] for m in ds),
            "muc_do": max((m["muc_do"] for m in ds), key=lambda k: _THU_TU.get(k, 0))}
