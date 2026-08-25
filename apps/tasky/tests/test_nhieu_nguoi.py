# -*- coding: utf-8 -*-
"""§14 — cùng một việc nhiều người, tự giao cho mình, lý do từ chối (Owner 25/08)."""
import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành"}
A = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
B = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành"}
KD = {"ten": "ngocpb", "level": 2, "bo_phan": "Kinh doanh"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


# ---------- tự giao cho mình ----------

def test_manager_tu_giao_viec_cho_chinh_minh(ma):
    """Manager cũng là người làm việc — trước đó luật 'level cao hơn' chặn cả họ."""
    assert tuan.duoc_giao_cho(MGR, MGR) is True
    v = tuan.them_viec_giao(ma, MGR, MGR, "Tôi tự làm", "x")
    assert v["nguoi"] == "huytq" and v["trang_thai"] == tuan.CHO_NHAN


def test_van_khong_giao_nguoc_len_cap_tren(ma):
    assert tuan.duoc_giao_cho(A, MGR) is False


# ---------- một việc, nhiều người ----------

def test_giao_ba_nguoi_thi_sinh_ba_ban_cung_nhom(ma):
    ds = tuan.giao_nhieu_nguoi(ma, MGR, [A, B, MGR], "Rà 10 video đối thủ", "Nghiên cứu")
    assert len(ds) == 3
    assert len({v["cung_viec"] for v in ds}) == 1 and ds[0]["cung_viec"]
    assert {v["nguoi"] for v in ds} == {"hant", "ducm", "huytq"}


def test_moi_nguoi_co_checklist_va_tien_do_rieng(ma):
    ds = tuan.giao_nhieu_nguoi(ma, MGR, [A, B], "Việc chung", "x")
    tuan.nhan_viec(ma, ds[0]["id"], A)
    tuan.them_buoc(ma, ds[0]["id"], A, "Bước của Hà")
    assert tuan.viec_cua(ma, "ducm")[0]["checklist"] == []      # không dùng chung
    assert tuan.thong_ke_nguoi(ma, "hant")["so_viec"] == 1
    assert tuan.thong_ke_nguoi(ma, "ducm")["so_viec"] == 1


def test_mot_nguoi_thi_khong_gan_nhom(ma):
    ds = tuan.giao_nhieu_nguoi(ma, MGR, [A], "Việc một mình", "x")
    assert ds[0]["cung_viec"] == ""


def test_giao_nhieu_van_qua_luat_bo_phan(ma):
    with pytest.raises(PermissionError):
        tuan.giao_nhieu_nguoi(ma, MGR, [A, KD], "Việc lạc", "x")


def test_khong_chon_ai_thi_bao_loi(ma):
    with pytest.raises(ValueError):
        tuan.giao_nhieu_nguoi(ma, MGR, [], "x", "y")


# ---------- lý do từ chối phải đọc được ----------

def test_viec_bi_tu_choi_noi_len_nhom_can_xu_ly(ma):
    v = tuan.them_viec_giao(ma, MGR, A, "Việc bị từ chối", "x")
    tuan.tu_choi_viec(ma, v["id"], A, "Tuần này đang chạy 8 video Life In")
    n = tuan.nhom_viec(tuan.viec_cua(ma, "hant"))
    assert [x["tieu_de"] for x in n["can_xu_ly"]] == ["Việc bị từ chối"]
    assert n["can_xu_ly"][0]["ly_do"] == "Tuần này đang chạy 8 video Life In"


def test_ly_do_tu_choi_len_toi_man_goal(ma):
    g = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, A, "Việc bị từ chối", "x", muc_tieu_id=g["id"])
    tuan.tu_choi_viec(ma, v["id"], A, "Không đúng chuyên môn")
    nhom = mt.nhom_viec(mt.viec_cua_muc_tieu(g["id"]))
    assert nhom["can_xu_ly"][0]["ly_do"] == "Không đúng chuyên môn"


# ---------- giao nhiều người qua API (ô chọn nhiều trong Goal) ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main                               # noqa: E402

_c = TestClient(main.app)
H = {"X-Remote-User": "huytq", "X-Remote-Level": "4", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
     "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan", "X-Remote-Apps": "tasky"}


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"},
        {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Minh Đức"}], ""))


def test_che_viec_cho_nhieu_nguoi_qua_api(_so, ma):
    g = mt.tao(MGR, "Goal A", "kq")
    r = _c.post("/api-tasky/muc-tieu/che-viec", headers=H,
                data={"muc_tieu_id": g["id"], "tieu_de": "Việc chung",
                      "loai_viec": "x", "nguoi": "hant,ducm", "tuan_xem": ma})
    assert r.status_code == 200
    assert mt.tien_do(g["id"])["tong"] == 2
    assert len(tuan.viec_cua(ma, "hant")) == 1 and len(tuan.viec_cua(ma, "ducm")) == 1


def test_che_viec_cho_chinh_minh_qua_api(_so, ma):
    g = mt.tao(MGR, "Goal A", "kq")
    r = _c.post("/api-tasky/muc-tieu/che-viec", headers=H,
                data={"muc_tieu_id": g["id"], "tieu_de": "Tôi làm",
                      "loai_viec": "x", "nguoi": "huytq", "tuan_xem": ma})
    assert r.status_code == 200 and tuan.viec_cua(ma, "huytq")[0]["tieu_de"] == "Tôi làm"


def test_de_trong_nguoi_thi_van_la_chua_phan_cong(_so, ma):
    g = mt.tao(MGR, "Goal A", "kq")
    _c.post("/api-tasky/muc-tieu/che-viec", headers=H,
            data={"muc_tieu_id": g["id"], "tieu_de": "Chưa giao", "loai_viec": "x",
                  "nguoi": "", "tuan_xem": ma})
    assert len(tuan.chua_giao(ma, g["id"])) == 1
