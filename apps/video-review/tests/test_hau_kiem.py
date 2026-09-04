# -*- coding: utf-8 -*-
"""Test luồng 2 — hậu kiểm: thư mục tập, nhập số liệu, chẩn đoán bằng lời."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from src import hau_kiem, kho_video, nhan_xet
from src.main import app
from tests.test_routes import _them, h, tao_file_nas


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def tap_co_full(client):
    """LI088: một bản duyệt 10 phút + một bản full đã đăng."""
    _them(client, ten="LI088.1")
    _them(client, ten="LI088_full")
    kho_video.gan_tap("VR-0001", "LI088", "duyet")
    kho_video.gan_tap("VR-0002", "LI088", "full")
    kho_video.gan_youtube("VR-0002", "xK3n9", "2026-08-26")
    conn = kho_video.ket_noi()
    try:
        conn.execute("UPDATE video SET so_do_nhip=? WHERE ma='VR-0002'",
                     ('{"thoi_luong": 1800}',))
        conn.commit()
    finally:
        conn.close()
    return "LI088"


def _anh(tmp_path, w=800, h=280):
    im = Image.new("RGB", (w, h), (15, 15, 15))
    d = ImageDraw.Draw(im)
    xs = np.arange(w)
    y = 0.86 * np.exp(-xs / (w * 0.16)) + 0.10
    d.line([(int(x), int(h - y[x] * h * 0.9)) for x in xs], fill=(62, 166, 255), width=3)
    p = tmp_path / "gc.png"
    im.save(p)
    return p


def test_trang_tap_gom_ban_duyet_va_ban_full(client, tap_co_full):
    trang = client.get("/tap/LI088", headers=h()).text
    assert "LI088.1" in trang and "LI088_full" in trang
    assert "Bản duyệt" in trang and "Bản full" in trang
    assert "không gióng sang bản full" in trang      # ghi rõ luật hai video khác nhau
    assert client.get("/tap/KHONG-CO", headers=h()).status_code == 404


def _hook_that(p, thoi_luong=1800):
    """Giá trị ở giây 30 mà ảnh THẬT SỰ mang — test phải khai đúng, không bịa."""
    from src import do_thi
    cong = do_thi.doc_duong_cong(p)
    return round(do_thi._diem_tai(cong, 30.0 / thoi_luong * 100), 1)


def test_nhap_so_lieu_va_doc_do_thi(client, tap_co_full, tmp_path):
    p = _anh(tmp_path)
    hook = _hook_that(p)
    with open(p, "rb") as f:
        r = client.post("/api-vr/giu-chan/LI088",
                        data={"hook_30": hook, "avd_giay": 259, "giu_tb": 13.9},
                        files={"anh": ("gc.png", f, "image/png")}, headers=h())
    assert r.status_code == 200 and r.json()["so_diem"] == 100
    gc = hau_kiem.lay_giu_chan("LI088")
    assert gc["hook_30"] == hook and len(gc["cong"]) == 100


def test_anh_khong_khop_so_that_thi_TU_CHOI(client, tap_co_full, tmp_path):
    p = _anh(tmp_path)
    with open(p, "rb") as f:
        r = client.post("/api-vr/giu-chan/LI088",
                        data={"hook_30": 15, "avd_giay": 259, "giu_tb": 13.9},
                        files={"anh": ("gc.png", f, "image/png")}, headers=h())
    assert r.status_code == 422 and "lệch" in r.json()["detail"]
    assert hau_kiem.lay_giu_chan("LI088") is None   # không ghi số sai vào sổ


def test_chan_doan_ra_cau_benh_co_loi_va_phan_quyet(client, tap_co_full, tmp_path):
    p = _anh(tmp_path)
    with open(p, "rb") as f:
        client.post("/api-vr/giu-chan/LI088",
                    data={"hook_30": _hook_that(p), "avd_giay": 259, "giu_tb": 13.9},
                    files={"anh": ("gc.png", f, "image/png")}, headers=h())
    r = client.post("/api-vr/hau-kiem/LI088", headers=h())
    assert r.status_code == 200 and r.json()["so"] >= 1
    ds = nhan_xet.ds_nhan_xet("VR-0002")
    assert all(n["loi"] and n["benh"] for n in ds)   # thẻ nào cũng có LỜI
    assert any(n["phan"] for n in ds)                # máy phán trước
    kl = r.json()["ket_luan"]
    # xem TB 4:19 trên video 30 phút = thừa thời lượng, và phải ra việc cho tập sau
    assert kl["viec"] and kl["tom"] == "thừa thời lượng"


def test_mau_mong_thi_khong_ket_luan():
    t = {"mat_diem": 7, "con_lai": 3.4, "tu_giay": 1070, "den_giay": 1145}
    c = hau_kiem._loi_cho_tut(t, 2, 40, 1800, 259)
    assert c["phan"] == "Chưa đủ cơ sở" and "quá ít để kết luận" in c["loi"]


def test_cho_tut_sau_AVD_duoc_ha_muc(client):
    t = {"mat_diem": 9, "con_lai": 8.0, "tu_giay": 900, "den_giay": 960}
    c = hau_kiem._loi_cho_tut(t, 1, 40, 1800, 259)
    assert c["muc"] == "nhe" and "ít đổi được kết quả" in c["loi"]


def test_chua_co_ban_full_thi_khong_mo_hau_kiem(client):
    _them(client, ten="LI099.1")
    kho_video.gan_tap("VR-0001", "LI099", "duyet")
    assert client.get("/hau-kiem/LI099", headers=h()).status_code == 404
    assert client.post("/api-vr/hau-kiem/LI099", headers=h()).status_code == 404
