# -*- coding: utf-8 -*-
"""§20 — deadline có cả GIỜ, không chỉ ngày (Owner chốt 31/08).

Việc cũ chỉ có ngày phải chạy y nguyên — sổ tuần trên máy công ty đầy hạn dạng
YYYY-MM-DD, không migration.
"""
from datetime import datetime

import pytest

from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}
BAY_GIO = datetime(2026, 8, 31, 14, 0)


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _viec(han):
    return {"han": han, "trang_thai": tuan.DANG_LAM}


# ---------- nhận và chuẩn hóa ----------

def test_nhan_ca_ngay_lan_ngay_gio(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "Có giờ", "x", han="2026-09-02T17:30")
    assert v["han"] == "2026-09-02T17:30"
    v2 = tuan.them_viec_giao(ma, MGR, NV, "Chỉ ngày", "x", han="2026-09-02")
    assert v2["han"] == "2026-09-02"          # dạng cũ giữ NGUYÊN, không tự thêm giờ


def test_nhan_dang_co_dau_cach(ma):
    """Trình duyệt/дán tay có thể gửi 'YYYY-MM-DD HH:MM'."""
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x", han="2026-09-02 08:05")
    assert v["han"] == "2026-09-02T08:05"


def test_han_sai_dinh_dang_bi_chan(ma):
    with pytest.raises(ValueError):
        tuan.them_viec_giao(ma, MGR, NV, "A", "x", han="chiều mai")
    with pytest.raises(ValueError):
        tuan.them_viec_giao(ma, MGR, NV, "B", "x", han="2026-09-02T25:00")


# ---------- đếm giờ ----------

def test_han_chi_NGAY_thi_het_ngay_moi_qua_han():
    """Đặt hạn 31/08 mà 9 giờ sáng đã báo quá hạn thì vô lý."""
    hn = tuan.tinh_han(_viec("2026-08-31"), BAY_GIO)
    assert hn["chu"] == "Hạn hôm nay" and hn["muc"] == "cap"


def test_han_co_gio_dem_theo_gio_trong_hom_nay():
    assert tuan.tinh_han(_viec("2026-08-31T17:00"), BAY_GIO)["chu"] == "Còn 3 giờ"
    assert tuan.tinh_han(_viec("2026-08-31T14:20"), BAY_GIO)["chu"] == "Còn 20 phút"
    assert tuan.tinh_han(_viec("2026-08-31T11:00"), BAY_GIO)["chu"] == "Quá hạn 3 giờ"


def test_han_xa_van_dem_theo_ngay_va_hien_gio():
    assert tuan.tinh_han(_viec("2026-09-01T09:00"), BAY_GIO)["chu"] == "Hạn ngày mai 09:00"
    assert tuan.tinh_han(_viec("2026-09-05T18:30"), BAY_GIO)["chu"] == "Hạn 05/09 18:30"


def test_viec_da_nghiem_thu_khong_bi_doa_qua_han():
    v = {"han": "2026-08-20T09:00", "trang_thai": tuan.XAC_NHAN}
    assert tuan.tinh_han(v, BAY_GIO) == {"chu": "", "muc": "", "con": None}


def test_co_gio_phan_biet_dung():
    assert tuan.co_gio("2026-09-02T17:30") is True
    assert tuan.co_gio("2026-09-02") is False
    assert tuan.co_gio("") is False


# ---------- không vỡ thứ đang chạy ----------

def test_loc_qua_han_hieu_ca_hai_dang(ma):
    tuan.them_viec_giao(ma, MGR, NV, "Trễ theo giờ", "x", han="2026-01-02T08:00")
    tuan.them_viec_giao(ma, MGR, NV, "Trễ theo ngày", "x", han="2026-01-02")
    tuan.them_viec_giao(ma, MGR, NV, "Còn xa", "x", han="2099-01-01")
    ds = tuan.loc_viec(tuan.doc_tuan(ma)["viec"], "qua_han")
    assert sorted(v["tieu_de"] for v in ds) == ["Trễ theo giờ", "Trễ theo ngày"]


def test_chip_qua_deadline_van_chay_voi_han_co_gio(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x", han="2026-01-02T08:00")
    assert "Quá deadline" in [c["chu"] for c in tuan.the_trang_thai(v)]


# ---------- giao diện ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main, muc_tieu as mt              # noqa: E402

_c = TestClient(main.app)
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4",
         "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}], ""))


def test_o_nhap_han_viec_co_gio(ma, _so):
    g = mt.tao(MGR, "G", "kq")
    r = _c.get("/task?goal=" + g["id"], headers=H_MGR)
    khoi = r.text.split("data-che-han")[1].split(">")[0]
    assert 'type="datetime-local"' in r.text.split("data-che-han")[0][-60:] or \
           'datetime-local' in khoi or 'datetime-local' in r.text


def test_han_GOAL_van_theo_ngay(ma, _so):
    """Mục tiêu là mốc dài hạn — giờ giấc thuộc về việc con."""
    g = mt.tao(MGR, "G", "kq", han="2026-09-30")
    hop = _c.get("/muc-tieu", headers=H_MGR).text \
        .split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    o = hop.split('name="han"')[0][-120:]
    assert 'type="date"' in o and "datetime-local" not in o


def test_the_viec_hien_han_kem_gio(ma, _so):
    g = mt.tao(MGR, "G", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "Có giờ", "x", muc_tieu_id=g["id"],
                        han="2026-09-05T18:30")
    r = _c.get("/task?goal=" + g["id"], headers=H_MGR)
    assert "05/09 18:30" in r.text


def test_the_viec_han_chi_ngay_thi_khong_bia_gio(ma, _so):
    g = mt.tao(MGR, "G", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "Chỉ ngày", "x", muc_tieu_id=g["id"],
                        han="2026-09-05")
    r = _c.get("/task?goal=" + g["id"], headers=H_MGR)
    assert "05/09" in r.text and "05/09 00:00" not in r.text
