# -*- coding: utf-8 -*-
"""B3 — màn Việc của tôi: render + API dưới /api-tasky (luật quyền vẫn ở lõi)."""
import pytest
from fastapi.testclient import TestClient

from src import tuan
from src.main import app

client = TestClient(app)

HA = {"X-Remote-User": "hant", "X-Remote-Level": "2",
      "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh", "X-Remote-Name": "Thu%20H%C3%A0"}
DUC = {"X-Remote-User": "ducm", "X-Remote-Level": "2", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh"}
LEADER = {"ten": "huytq", "level": 3, "bo_phan": "Vận hành"}
NHANVIEN = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _giao(ma, tieu_de="Dựng 6 video kênh Hidden Laos"):
    return tuan.them_viec_giao(ma, LEADER, NHANVIEN, tieu_de, "Dựng video")


# ---------- trang ----------

def test_trang_hien_viec_cua_minh(ma):
    _giao(ma)
    r = client.get("/tasky", headers=HA)
    assert r.status_code == 200
    assert "Dựng 6 video kênh Hidden Laos" in r.text
    assert "Chờ bạn nhận" in r.text


def test_trang_khong_lo_viec_cua_nguoi_khac(ma):
    """Luật 1 — lọc Ở SERVER: việc người khác không được gửi ra client."""
    _giao(ma)
    r = client.get("/tasky", headers=DUC)
    assert r.status_code == 200 and "Hidden Laos" not in r.text


def test_tuan_rong_hien_dau_gach_khong_hien_0_phan_tram(ma):
    """Van chống bịa: chưa có việc thì hiện '—' + nói rõ vì sao, KHÔNG hiện tỉ lệ.
    (Không assert vắng chuỗi '0%' — base.html có '0%' trong CSS keyframes.)"""
    r = client.get("/tasky", headers=HA)
    assert "Chưa có việc nào trong tuần" in r.text
    assert "đã được xác nhận" not in r.text


def test_ma_tuan_bay_ba_trong_url_khong_lam_vo_trang():
    r = client.get("/tasky?tuan_xem=../../etc", headers=HA)
    assert r.status_code == 200                      # về tuần này, không 500


def test_xem_duoc_tuan_cu(ma):
    truoc = tuan.tuan_lien_ke(ma, -1)
    tuan.them_viec_giao(truoc, LEADER, NHANVIEN, "Việc tuần trước", "Dựng video")
    r = client.get(f"/tasky?tuan_xem={truoc}", headers=HA)
    assert "Việc tuần trước" in r.text and "đang xem tuần cũ" in r.text


# ---------- API ----------

def test_nhan_roi_moi_them_duoc_buoc(ma):
    v = _giao(ma)
    r = client.post("/api-tasky/buoc", headers=HA,
                    data={"id": v["id"], "noi_dung": "Rà transcript", "tuan_xem": ma})
    assert r.status_code == 400 and "Nhận việc trước" in r.json()["detail"]

    assert client.post("/api-tasky/nhan", headers=HA,
                       data={"id": v["id"], "tuan_xem": ma}).status_code == 200
    r2 = client.post("/api-tasky/buoc", headers=HA,
                     data={"id": v["id"], "noi_dung": "Rà transcript", "tuan_xem": ma})
    assert r2.status_code == 200 and r2.json()["du_lieu"]["noi_dung"] == "Rà transcript"


def test_khong_thao_tac_duoc_tren_viec_nguoi_khac(ma):
    v = _giao(ma)
    r = client.post("/api-tasky/nhan", headers=DUC, data={"id": v["id"], "tuan_xem": ma})
    assert r.status_code == 403


def test_tu_choi_thieu_ly_do_bi_chan_o_server(ma):
    """Client có ô lý do, nhưng chốt chặn thật nằm ở server."""
    v = _giao(ma)
    r = client.post("/api-tasky/tu-choi", headers=HA, data={"id": v["id"], "tuan_xem": ma})
    assert r.status_code == 400 and "lý do" in r.json()["detail"]


def test_tick_va_bo_tick_mot_buoc(ma):
    v = _giao(ma)
    client.post("/api-tasky/nhan", headers=HA, data={"id": v["id"], "tuan_xem": ma})
    b = client.post("/api-tasky/buoc", headers=HA,
                    data={"id": v["id"], "noi_dung": "Dựng thô", "tuan_xem": ma}).json()["du_lieu"]
    client.post("/api-tasky/tick", headers=HA,
                data={"id": v["id"], "buoc": b["id"], "xong": "1", "tuan_xem": ma})
    assert tuan.thong_ke_nguoi(ma, "hant")["buoc_xong"] == 1
    client.post("/api-tasky/tick", headers=HA,
                data={"id": v["id"], "buoc": b["id"], "xong": "0", "tuan_xem": ma})
    assert tuan.thong_ke_nguoi(ma, "hant")["buoc_xong"] == 0


def test_bao_xong_chua_lam_ti_le_len_100(ma):
    v = _giao(ma)
    client.post("/api-tasky/nhan", headers=HA, data={"id": v["id"], "tuan_xem": ma})
    client.post("/api-tasky/bao-xong", headers=HA, data={"id": v["id"], "tuan_xem": ma})
    t = tuan.thong_ke_nguoi(ma, "hant")
    assert t["cho_xac_nhan"] == 1 and t["ti_le"] == 0


def test_tu_them_viec_qua_api(ma):
    r = client.post("/api-tasky/viec-tu", headers=HA,
                    data={"tieu_de": "Dựng lại intro", "loai_viec": "Dựng video", "tuan_xem": ma})
    assert r.status_code == 200
    assert tuan.viec_cua(ma, "hant")[0]["nguon"] == "tu_them"


def test_api_khong_claims_thi_401(ma):
    assert client.post("/api-tasky/viec-tu", data={"tieu_de": "x"}).status_code == 401


# ---------- gợi ý loại việc ----------

def test_goi_y_loai_viec_lay_tu_viec_da_co(ma):
    _giao(ma)
    tuan.them_viec_tu(ma, NHANVIEN, "Việc khác", "Quy trình nội bộ")
    assert set(tuan.cac_loai_viec()) == {"Dựng video", "Quy trình nội bộ"}


def test_kho_rong_thi_khong_bia_danh_muc_mau():
    assert tuan.cac_loai_viec() == []
