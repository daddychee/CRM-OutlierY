# -*- coding: utf-8 -*-
"""§17 — Tasky tách ba mục Goal / Task / Report (Owner chốt 26/08).

Trang Goal chỉ theo dõi MỤC TIÊU: overview + danh sách. Việc con chuyển sang
mục Task.
"""
from datetime import date, timedelta

import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _han(n):
    return (date.today() + timedelta(days=n)).isoformat()


def _goal_xong(ma, ten="G"):
    """Goal có đúng một việc đã nghiệm thu."""
    g = mt.tao(MGR, ten, "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, ten + "-việc", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], MGR)
    return g


# ---------- overview ----------

def test_tong_quan_dem_dung_tung_trang_thai(ma):
    mt.tao(MGR, "Chưa có việc nào", "kq")               # đang chạy, 0 việc
    g2 = mt.tao(MGR, "Đang làm dở", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "V", "x", muc_tieu_id=g2["id"])
    _goal_xong(ma, "Xong hết chờ chốt")                 # xong hết → chờ chốt
    g4 = _goal_xong(ma, "Đã chốt đạt")
    mt.chot_ket_qua(g4["id"], MGR, mt.DAT)

    tq = mt.tong_quan(mt.doc_tat_ca())
    assert tq["tong"] == 4
    assert tq["dang_chay"] == 2 and tq["cho_chot"] == 1 and tq["dat"] == 1
    assert tq["chua_co_viec"] == 1                      # Goal bị bỏ quên
    assert tq["viec_tong"] == 3 and tq["viec_xong"] == 2


def test_chua_co_viec_nao_thi_khong_bia_ti_le():
    mt.tao(MGR, "Goal rỗng", "kq")
    assert mt.tong_quan(mt.doc_tat_ca())["ti_le"] is None


def test_dem_goal_tre_han(ma):
    mt.tao(MGR, "Trễ", "kq", han=_han(-2))
    mt.tao(MGR, "Còn hạn", "kq", han=_han(9))
    assert mt.tong_quan(mt.doc_tat_ca())["tre_han"] == 1


# ---------- sắp xếp + cần để ý ----------

def _cay(han_map):
    ra = []
    for ten, con in han_map.items():
        ra.append({"id": ten, "tieu_de": ten, "trang_thai": mt.DANG_CHAY,
                   "con_han": con, "canh_bao": [], "luc_tao": "2026-08-0" + str(len(ra) + 1),
                   "tien_do": {"tong": 2, "xong": 0}})
    return ra


def test_goal_da_chot_luon_xuong_duoi():
    cay = _cay({"A": 5, "B": 1})
    cay[0]["trang_thai"] = mt.DAT
    assert [g["tieu_de"] for g in mt.sap_xep_goal(cay)] == ["B", "A"]


def test_sap_theo_gan_han_goal_khong_han_xuong_cuoi():
    cay = _cay({"A": 9, "B": None, "C": 2})
    assert [g["tieu_de"] for g in mt.sap_xep_goal(cay)] == ["C", "A", "B"]


def test_can_de_y_gom_goal_sap_chay_va_goal_bo_quen():
    cay = _cay({"Xa": 30, "Gấp": 2, "Bỏ quên": 30})
    cay[2]["tien_do"] = {"tong": 0, "xong": 0}
    gap, thuong = mt.can_de_y(cay)
    assert sorted(g["tieu_de"] for g in gap) == ["Bỏ quên", "Gấp"]
    assert [g["tieu_de"] for g in thuong] == ["Xa"]


def test_goal_da_chot_khong_vao_can_de_y():
    cay = _cay({"A": -5})
    cay[0]["trang_thai"] = mt.KHONG_DAT
    gap, thuong = mt.can_de_y(cay)
    assert gap == [] and len(thuong) == 1
