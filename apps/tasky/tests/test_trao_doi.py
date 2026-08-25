# -*- coding: utf-8 -*-
"""§15 — trao đổi trong việc + đổi tên Goal (Owner yêu cầu 25/08)."""
import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}
NGOAI = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Minh Đức"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _viec(ma):
    return tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "x")


# ---------- trao đổi ----------

def test_hai_ben_nhan_tin_qua_lai(ma):
    v = _viec(ma)
    tuan.them_trao_doi(ma, v["id"], MGR, "Nhớ làm intro trước nhé")
    tuan.them_trao_doi(ma, v["id"], NV, "Vâng, em làm intro chiều nay")
    td = tuan.doc_trao_doi(ma, v["id"], NV)
    assert [t["ai"] for t in td] == ["huytq", "hant"]
    assert td[0]["ten"] == "Quốc Huy" and "intro" in td[1]["chu"]


def test_nguoi_ngoai_cuoc_khong_doc_khong_viet(ma):
    """Giữ luật 1: đồng nghiệp ngang cấp không xem việc của nhau."""
    v = _viec(ma)
    with pytest.raises(PermissionError):
        tuan.doc_trao_doi(ma, v["id"], NGOAI)
    with pytest.raises(PermissionError):
        tuan.them_trao_doi(ma, v["id"], NGOAI, "xen vào")


def test_owner_doc_duoc(ma):
    v = _viec(ma)
    tuan.them_trao_doi(ma, v["id"], NV, "câu hỏi")
    assert len(tuan.doc_trao_doi(ma, v["id"], OWNER)) == 1


def test_khong_nhan_tin_rong(ma):
    v = _viec(ma)
    with pytest.raises(ValueError):
        tuan.them_trao_doi(ma, v["id"], NV, "   ")


def test_trao_doi_la_chi_them_giu_thu_tu(ma):
    v = _viec(ma)
    for i in range(3):
        tuan.them_trao_doi(ma, v["id"], NV, f"câu {i}")
    assert [t["chu"] for t in tuan.doc_trao_doi(ma, v["id"], NV)] == ["câu 0", "câu 1", "câu 2"]


def test_viec_tu_them_thi_chinh_chu_van_nhan_tin_duoc(ma):
    v = tuan.them_viec_tu(ma, NV, "Việc của tôi", "x")
    tuan.them_trao_doi(ma, v["id"], NV, "ghi chú cho mình")
    assert len(tuan.doc_trao_doi(ma, v["id"], NV)) == 1


# ---------- đổi tên Goal ----------

def test_doi_ten_goal():
    m = mt.tao(MGR, "Tên cũ", "kết quả cũ")
    d = mt.sua(m["id"], MGR, tieu_de="Tên mới")
    assert d["tieu_de"] == "Tên mới" and d["ket_qua_can_dat"] == "kết quả cũ"


def test_sua_ket_qua_va_han():
    from datetime import date, timedelta
    han = (date.today() + timedelta(days=5)).isoformat()
    m = mt.tao(MGR, "Goal", "kq cũ")
    d = mt.sua(m["id"], MGR, ket_qua_can_dat="AVD ≥ 50%", han=han)
    assert d["ket_qua_can_dat"] == "AVD ≥ 50%" and d["han"] == han


def test_de_trong_thi_giu_nguyen():
    m = mt.tao(MGR, "Giữ tên", "giữ kết quả")
    d = mt.sua(m["id"], MGR, tieu_de="  ")
    assert d["tieu_de"] == "Giữ tên"


def test_nguoi_khac_bo_phan_khong_sua_duoc():
    m = mt.tao(MGR, "Goal", "kq")
    with pytest.raises(PermissionError):
        mt.sua(m["id"], {"ten": "ngocpb", "level": 4, "bo_phan": "Kinh doanh"}, tieu_de="X")


def test_han_sai_dinh_dang_bi_chan():
    m = mt.tao(MGR, "Goal", "kq")
    with pytest.raises(ValueError):
        mt.sua(m["id"], MGR, han="cuối tháng")


# ---------- giao diện: form thuần, không phụ thuộc JS ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main                               # noqa: E402

_c = TestClient(main.app)
H_NV = {"X-Remote-User": "hant", "X-Remote-Level": "2", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
        "X-Remote-Actions": "vao", "X-Remote-Apps": "tasky"}
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan", "X-Remote-Apps": "tasky"}


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}], ""))


def test_gui_tin_bang_form_va_quay_lai_dung_trang(ma, _so):
    v = _viec(ma)
    r = _c.post("/tasky/trao-doi", headers=H_NV, follow_redirects=False,
                data={"id": v["id"], "chu": "Em làm intro chiều nay",
                      "tuan_xem": ma, "ve": "/tasky?tuan_xem=" + ma})
    assert r.status_code == 303 and r.headers["location"].startswith("/tasky")
    assert tuan.doc_trao_doi(ma, v["id"], NV)[0]["chu"] == "Em làm intro chiều nay"


def test_tin_hien_tren_man_viec_cua_toi(ma, _so):
    v = _viec(ma)
    tuan.them_trao_doi(ma, v["id"], MGR, "Nhớ làm intro trước")
    r = _c.get("/tasky", headers=H_NV)
    assert "Nhớ làm intro trước" in r.text and "Trao đổi" in r.text


def test_o_trao_doi_la_form_that_khong_phai_JS(ma, _so):
    _viec(ma)
    r = _c.get("/tasky", headers=H_NV)
    assert 'action="/tasky/trao-doi"' in r.text and 'name="chu"' in r.text


def test_doi_ten_goal_bang_form(_so):
    m = mt.tao(MGR, "Tên cũ", "kq")
    r = _c.post("/muc-tieu/sua", headers=H_MGR, follow_redirects=False,
                data={"id": m["id"], "tieu_de": "Tên mới", "ket_qua": "", "han": ""})
    assert r.status_code == 303 and mt.doc_tat_ca()[0]["tieu_de"] == "Tên mới"


def test_sua_goal_TAI_CHO_khong_co_box_rieng(_so):
    """Owner 25/08: box 'Sửa Goal này' thừa — sửa thẳng trên tiêu đề đang hiển thị."""
    mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/muc-tieu", headers=H_MGR)
    assert 'action="/muc-tieu/sua"' in r.text
    assert 'class="o-tai-cho ten-goal" name="tieu_de"' in r.text
    assert "Sửa Goal này" not in r.text


def test_goal_da_chot_thi_khong_sua_tai_cho(_so):
    m = mt.tao(MGR, "Goal A", "kq")
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    r = _c.get("/muc-tieu", headers=H_MGR)
    assert 'name="tieu_de"' not in r.text      # đã chốt → chỉ đọc
