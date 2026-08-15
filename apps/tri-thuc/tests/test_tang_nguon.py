"""Test Bước 1 Supervisor — TẦNG NGUỒN ở nhập liệu: mặc định noi_bo/Official (hành vi cũ
KHÔNG đổi), tầng "ngoai" (07/08: gộp chuyên gia + nguồn ngoài làm MỘT) kèm Tên nguồn bắt
buộc; validation 2 lớp (backend 422). Mock (MOCK_MODE)."""

import os

os.environ["MOCK_MODE"] = "true"

from fastapi.testclient import TestClient

from src.main import app, doc_catalog
from claims_v2 import client_claims

# V2: /upload cần claims Manager+ (hệ cũ chạy chế độ mở khi chưa có users.txt)
tc = client_claims(app, "sep", "Kinh doanh", 5)


def _form(**thay):
    d = {"title": "Tài liệu thử", "keywords": "kw", "owner": "An", "version": "v1",
         "department": "Kinh doanh", "doc_type": "Quy trình", "effective_status": "Còn hiệu lực",
         "access_level": "Công khai nội bộ", "min_level": "2"}
    d.update(thay)
    return d


def _dong(code):
    return next((d for d in doc_catalog() if d["Mã tài liệu"] == code), None)


def test_mac_dinh_noi_bo_official():
    """KHÔNG gửi tang_nguon → mặc định noi_bo + Tên nguồn = Official (hành vi cũ, không đổi)."""
    r = tc.post("/upload", data=_form(), files={"file": ("a.txt", b"noi dung")})
    assert r.status_code == 200
    row = _dong(r.json()["doc_code"])
    assert row["Tầng nguồn"] == "noi_bo" and row["Tên nguồn"] == "Official"


def test_ngoai_kem_ten_nguon():
    r = tc.post("/upload", data=_form(tang_nguon="ngoai", nguon_ten="Anh A"),
                files={"file": ("b.txt", b"noi dung")})
    assert r.status_code == 200
    row = _dong(r.json()["doc_code"])
    assert row["Tầng nguồn"] == "ngoai" and row["Tên nguồn"] == "Anh A"


def test_gia_tri_cu_chuyen_gia_khong_con_duoc_chap_nhan():
    """07/08: gộp chuyên gia + ngoài làm MỘT — dropdown chỉ còn noi_bo/ngoai, "chuyen_gia"
    (giá trị CŨ) không còn hợp lệ cho tài liệu MỚI (dữ liệu cũ đã có được gộp bằng script)."""
    r = tc.post("/upload", data=_form(tang_nguon="chuyen_gia", nguon_ten="Anh A"),
                files={"file": ("b2.txt", b"noi dung")})
    assert r.status_code == 422


def test_noi_bo_luon_official_bo_qua_ten_gui_len():
    """noi_bo thì Tên nguồn LUÔN Official — kể cả client cố gửi tên khác lên."""
    r = tc.post("/upload", data=_form(tang_nguon="noi_bo", nguon_ten="Cố nhét tên"),
                files={"file": ("c.txt", b"x")})
    assert _dong(r.json()["doc_code"])["Tên nguồn"] == "Official"


def test_tang_ngoai_dropdown_bi_chan_422():
    r = tc.post("/upload", data=_form(tang_nguon="tao_lao", nguon_ten="x"),
                files={"file": ("d.txt", b"x")})
    assert r.status_code == 422


def test_ngoai_thieu_ten_nguon_422():
    r = tc.post("/upload", data=_form(tang_nguon="ngoai", nguon_ten="   "),
                files={"file": ("e.txt", b"x")})
    assert r.status_code == 422       # tầng ≠ noi_bo bắt buộc có Tên nguồn (khoảng trắng = rỗng)


def test_trang_nhap_co_dropdown_tang_nguon():
    r = tc.get("/")
    assert r.status_code == 200
    assert 'name="tang_nguon"' in r.text and "Tài liệu công ty (Official)" in r.text
    assert 'name="nguon_ten"' in r.text
