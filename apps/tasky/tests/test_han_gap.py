# -*- coding: utf-8 -*-
"""B9 — hạn chót + dấu GẤP (Owner yêu cầu 24/08)."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from src import main, thong_bao as tb, tuan
from src.main import app

client = TestClient(app)

SO = [{"ten": "huytq", "level": 3, "bo_phan": "Vận hành", "ho_ten": "Trần Quốc Huy"},
      {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Nguyễn Thu Hà"}]
LEADER = {"ten": "huytq", "level": 3, "bo_phan": "Vận hành"}
NHANVIEN = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
HA_H = {"X-Remote-User": "hant", "X-Remote-Level": "2", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
        "X-Remote-Actions": "vao", "X-Remote-Apps": "tasky"}
LEADER_H = {"X-Remote-User": "huytq", "X-Remote-Level": "3", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
            "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
            "X-Remote-Apps": "tasky"}


@pytest.fixture(autouse=True)
def _so_gia(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: (list(SO), ""))


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _ngay(lech):
    return (date.today() + timedelta(days=lech)).isoformat()


# ---------- đặt hạn ----------

def test_giao_kem_han_va_dau_gap(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng 6 video", "Dựng video",
                            han=_ngay(2), gap=True)
    assert v["han"] == _ngay(2) and v["gap"] is True


def test_han_sai_dinh_dang_bao_loi_khong_am_tham_bo_qua(ma):
    """Người giao tưởng đã đặt hạn mà thật ra không — tệ hơn là báo lỗi."""
    with pytest.raises(ValueError):
        tuan.them_viec_giao(ma, LEADER, NHANVIEN, "x", "y", han="thứ sáu")


def test_khong_dat_han_thi_khong_sao(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "x", "y")
    assert v["han"] == "" and tuan.tinh_han(v)["chu"] == ""


# ---------- nhãn hạn ----------

def test_nhan_han_theo_so_ngay_con_lai(ma):
    def nhan(lech):
        v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, f"v{lech}", "y", han=_ngay(lech))
        return tuan.tinh_han(v)
    assert nhan(-2)["chu"] == "Quá hạn 2 ngày" and nhan(-2)["muc"] == "cap"
    assert nhan(0)["chu"] == "Hạn hôm nay" and nhan(0)["muc"] == "cap"
    assert nhan(1)["chu"] == "Hạn ngày mai" and nhan(1)["muc"] == "luu_y"
    assert nhan(3)["muc"] == "luu_y"
    assert nhan(10)["muc"] == ""              # còn xa thì không tô màu


def test_viec_da_xong_thi_thoi_bao_qua_han(ma):
    """Không dọa người ta bằng việc đã xong."""
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Đã xong", "y", han=_ngay(-5))
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    tuan.bao_xong(ma, v["id"], NHANVIEN)
    tuan.xac_nhan_viec(ma, v["id"], LEADER)
    assert tuan.tinh_han(tuan.viec_cua(ma, "hant")[0])["chu"] == ""


# ---------- đổi dấu sau khi giao ----------

def test_nguoi_giao_doi_duoc_han_va_dau_gap(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "x", "y")
    tuan.danh_dau(ma, v["id"], LEADER, gap=True, han=_ngay(1))
    d = tuan.viec_cua(ma, "hant")[0]
    assert d["gap"] is True and d["han"] == _ngay(1)


def test_nguoi_lam_khong_tu_go_dau_gap_cua_viec_duoc_giao(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "x", "y", gap=True)
    with pytest.raises(PermissionError):
        tuan.danh_dau(ma, v["id"], NHANVIEN, gap=False)


def test_viec_tu_them_thi_chinh_chu_tu_dat_han(ma):
    v = tuan.them_viec_tu(ma, NHANVIEN, "Việc của tôi", "y")
    tuan.danh_dau(ma, v["id"], NHANVIEN, han=_ngay(2), gap=True)
    assert tuan.viec_cua(ma, "hant")[0]["han"] == _ngay(2)


def test_api_danh_dau_go_han(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "x", "y", han=_ngay(3))
    r = client.post("/api-tasky/danh-dau", headers=LEADER_H,
                    data={"id": v["id"], "han": "xoa", "tuan_xem": ma})
    assert r.status_code == 200 and tuan.viec_cua(ma, "hant")[0]["han"] == ""


def test_api_giao_nhan_han_va_gap(ma):
    r = client.post("/api-tasky/giao", headers=LEADER_H,
                    data={"nguoi": "hant", "tieu_de": "Gấp lắm", "loai_viec": "Dựng video",
                          "han": _ngay(1), "gap": "1", "tuan_xem": ma})
    assert r.status_code == 200
    v = tuan.viec_cua(ma, "hant")[0]
    assert v["gap"] is True and v["han"] == _ngay(1)


# ---------- sắp xếp ----------

def test_gap_va_qua_han_noi_len_dau(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Thường", "y")
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Quá hạn", "y", han=_ngay(-1))
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Gấp", "y", gap=True)
    ten = [v["tieu_de"] for v in tuan.sap_xep(tuan.viec_cua(ma, "hant"))]
    assert ten[0] == "Gấp" and ten[1] == "Quá hạn" and ten[2] == "Thường"


# ---------- thông báo ----------

def test_bao_qua_han_va_den_han_hom_nay(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "A", "y", han=_ngay(-2))
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "B", "y", han=_ngay(0))
    ds = tb.cua_toi(ma, NHANVIEN)
    assert any("quá hạn" in m["chu"] and m["muc_do"] == tb.CAP for m in ds)
    assert any("đến hạn hôm nay" in m["chu"] for m in ds)


def test_bao_viec_gap_khong_dem_trung_voi_qua_han(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Gấp và quá hạn", "y",
                        han=_ngay(-1), gap=True)
    ds = tb.cua_toi(ma, NHANVIEN)
    assert any("quá hạn" in m["chu"] for m in ds)
    assert not any("GẤP" in m["chu"] for m in ds)     # đã nằm trong nhóm quá hạn


def test_leader_duoc_bao_viec_qua_han_cua_bo_phan(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "A", "y", han=_ngay(-3))
    assert any("của bộ phận đã quá hạn" in m["chu"] for m in tb.cua_leader(ma, LEADER, SO))


# ---------- hiển thị ----------

def test_trang_hien_chip_gap_va_han(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng gấp", "Dựng video",
                        han=_ngay(-1), gap=True)
    r = client.get("/tasky", headers=HA_H)
    assert ">GẤP<" in r.text and "Quá hạn 1 ngày" in r.text


def test_thong_ke_dem_gap_va_qua_han(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "A", "y", han=_ngay(-1))
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "B", "y", gap=True)
    t = tuan.thong_ke_nguoi(ma, "hant")
    assert t["qua_han"] == 1 and t["gap"] == 1
