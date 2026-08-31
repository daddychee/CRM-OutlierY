# -*- coding: utf-8 -*-
"""§19 — tải file lên, app gom vào MỘT thư mục trên NAS (Owner chốt 31/08).

Trước đó chỉ dán được đường dẫn. Nguyên tắc giữ nguyên: một tài liệu một chỗ —
app KHÔNG giữ bản thứ hai, chỉ chép lên NAS rồi lưu đường dẫn như mọi tài liệu.
"""
import io
import os

import pytest
from fastapi.testclient import TestClient

from src import main, tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}
NGOAI = {"ten": "kd9", "level": 2, "bo_phan": "Kinh doanh"}
_c = TestClient(main.app)
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4",
         "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


@pytest.fixture(autouse=True)
def _kho_tep(tmp_path, monkeypatch):
    """KHÔNG ghi vào NAS thật khi chạy test."""
    monkeypatch.setenv("TASKY_TEP_DIR", str(tmp_path / "nas-tasky"))


def _viec(ma):
    return tuan.them_viec_giao(ma, MGR, NV, "Việc A", "x")


def _gui(id_viec, ma, ten, noi_dung, h=None):
    return _c.post("/tasky/viec/tai-lieu/tep", headers=h or H_MGR,
                   data={"id": id_viec, "tuan_xem": ma, "ve": "/task"},
                   files={"tep": (ten, io.BytesIO(noi_dung), "application/octet-stream")},
                   follow_redirects=False)


# ---------- lõi ----------

def test_file_duoc_chep_len_NAS_va_dinh_duong_dan(ma):
    v = _viec(ma)
    r = _gui(v["id"], ma, "bao cao.pdf", b"%PDF-1.4 noi dung")
    assert r.status_code == 303 and "loi=" not in r.headers["location"]
    tl = tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]
    assert len(tl) == 1 and tl[0]["ten"] == "bao cao.pdf"
    assert os.path.isfile(tl[0]["dia_chi"])                 # file nằm thật trên đĩa
    assert open(tl[0]["dia_chi"], "rb").read() == b"%PDF-1.4 noi dung"


def test_trung_ten_khong_ghi_de_ban_cu(ma):
    """File người khác đính trước không được biến mất chỉ vì trùng tên."""
    v = _viec(ma)
    _gui(v["id"], ma, "brief.docx", b"ban mot")
    _gui(v["id"], ma, "brief.docx", b"ban hai")
    tl = tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]
    assert len(tl) == 2 and tl[0]["dia_chi"] != tl[1]["dia_chi"]
    assert open(tl[0]["dia_chi"], "rb").read() == b"ban mot"


def test_chan_duoi_chay_duoc(ma):
    v = _viec(ma)
    r = _gui(v["id"], ma, "virus.exe", b"MZ...")
    assert "loi=" in r.headers["location"]
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"] == []


def test_chan_file_qua_25MB(ma):
    v = _viec(ma)
    r = _gui(v["id"], ma, "to.pdf", b"x" * (26 * 1024 * 1024))
    assert "loi=" in r.headers["location"]
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"] == []


def test_ten_file_co_duong_dan_bi_lam_sach(ma):
    """Tên file do trình duyệt gửi là dữ liệu người dùng — không được thoát thư mục."""
    v = _viec(ma)
    _gui(v["id"], ma, "../../../etc/passwd.txt", b"noi dung")
    tl = tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"][0]
    assert tl["ten"] == "passwd.txt" and ".." not in tl["dia_chi"]


# ---------- quyền ----------

def test_nguoi_ngoai_khong_tai_len_duoc(ma):
    v = _viec(ma)
    h = {**H_MGR, "X-Remote-User": "kd9", "X-Remote-Dept": "Kinh%20doanh",
         "X-Remote-Level": "2", "X-Remote-Actions": "vao"}
    r = _gui(v["id"], ma, "a.pdf", b"x", h)
    assert "loi=" in r.headers["location"]
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"] == []


def test_tai_ve_kiem_quyen_va_KHONG_nhan_duong_dan_tuy_y(ma, tmp_path):
    v = _viec(ma)
    _gui(v["id"], ma, "brief.pdf", b"noi dung mat")
    duong = tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"][0]["dia_chi"]
    r = _c.get("/tasky/tep", headers=H_MGR,
               params={"duong": duong, "tuan_xem": ma, "id": v["id"]})
    assert r.status_code == 200 and r.content == b"noi dung mat"

    # người ngoài việc → 404 lặng lẽ
    h = {**H_MGR, "X-Remote-User": "kd9", "X-Remote-Dept": "Kinh%20doanh",
         "X-Remote-Level": "2", "X-Remote-Actions": "vao"}
    assert _c.get("/tasky/tep", headers=h,
                  params={"duong": duong, "tuan_xem": ma, "id": v["id"]}).status_code == 404

    # đường dẫn tùy ý (file khác trên máy chủ) → 404, dù người xem có quyền việc
    khac = tmp_path / "bi-mat.txt"
    khac.write_text("khong duoc doc")
    assert _c.get("/tasky/tep", headers=H_MGR,
                  params={"duong": str(khac), "tuan_xem": ma,
                          "id": v["id"]}).status_code == 404
