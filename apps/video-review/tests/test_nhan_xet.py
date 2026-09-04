# -*- coding: utf-8 -*-
"""Test nhận xét của MÁY: lưu, trộn chung danh sách note, chạy nền, RBAC."""
import pytest
from fastapi.testclient import TestClient

from src import kho_video, mach_dung, nhan_xet
from src.main import app
from tests.test_routes import _them, h


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_luu_ghi_de_khong_cong_don(client):
    _them(client)
    nhan_xet.luu_nhan_xet("VR-0001", [{"ts": 0.0, "benh": "Mở đầu chậm", "muc": "nang"}])
    nhan_xet.luu_nhan_xet("VR-0001", [{"ts": 5.0, "benh": "Nhịp đều", "muc": "nhe"}])
    ds = nhan_xet.ds_nhan_xet("VR-0001")
    assert len(ds) == 1 and ds[0]["benh"] == "Nhịp đều"


def test_danh_gia_chay_nen_va_sinh_cau_benh(client, monkeypatch):
    _them(client)
    monkeypatch.setattr(mach_dung, "do_video", lambda p, **k: {
        "hook_p50": 2.4, "hook_chop": 0.38, "shot_p50": 3.8, "shot_std": 1.9,
        "cat_phut": 9.1, "shot_dai_nhat": 9.2, "tin_cay": True, "duong_cong": [],
        "thoi_luong": 600, "so_shot": 100})
    r = client.post("/api-vr/danh-gia/VR-0001", headers=h())
    assert r.status_code == 200
    tid = r.json()["task_id"]
    tt = client.get(f"/api-vr/danh-gia/{tid}", headers=h()).json()
    assert tt["trang_thai"] == "xong" and tt["so"] >= 2
    ds = client.get("/api-vr/nhan-xet/VR-0001", headers=h()).json()
    ten = [n["benh"] for n in ds]
    assert "Mở đầu chậm — hook chưa nổ" in ten
    assert all(n["loi"] for n in ds)              # thẻ nào cũng phải có LỜI, không chỉ số


def test_tac_vu_rbac_chi_chu_xem_duoc(client, monkeypatch):
    _them(client)
    monkeypatch.setattr(mach_dung, "do_video", lambda p, **k: {})
    tid = client.post("/api-vr/danh-gia/VR-0001", headers=h()).json()["task_id"]
    assert client.get(f"/api-vr/danh-gia/{tid}", headers=h(ten="nguoi-la")).status_code == 404
    assert client.get(f"/api-vr/danh-gia/{tid}", headers=h()).status_code == 200


def test_do_hong_thi_bao_loi_khong_giet_app(client, monkeypatch):
    _them(client)
    monkeypatch.setattr(mach_dung, "do_video", lambda p, **k: {})
    tid = client.post("/api-vr/danh-gia/VR-0001", headers=h()).json()["task_id"]
    tt = client.get(f"/api-vr/danh-gia/{tid}", headers=h()).json()
    assert tt["trang_thai"] == "loi" and "Không đo được" in tt["loi"]
    assert nhan_xet.ds_nhan_xet("VR-0001") == []


def test_da_doc_va_sua_phan_quyet(client):
    _them(client)
    nhan_xet.luu_nhan_xet("VR-0001", [{"ts": 0.0, "benh": "Mở đầu chậm", "muc": "nang",
                                       "phan": "Làm lại"}])
    nx = nhan_xet.ds_nhan_xet("VR-0001")[0]
    assert nx["da_doc"] == 0
    assert client.post(f"/api-vr/nhan-xet/{nx['id']}/da-doc", headers=h()).status_code == 200
    assert nhan_xet.ds_nhan_xet("VR-0001")[0]["da_doc"] == 1
    assert client.post(f"/api-vr/nhan-xet/{nx['id']}/phan", data={"phan": "Bỏ hẳn"},
                       headers=h()).status_code == 200
    sau = nhan_xet.ds_nhan_xet("VR-0001")[0]
    assert sau["phan"] == "Làm lại" and sau["phan_nguoi"] == "Bỏ hẳn"


def test_trang_xem_nhung_nhan_xet_va_giu_mot_cot(client):
    _them(client)
    kho_video.them_binh_luan("VR-0001", "an", "note người", ts_giay=12)
    nhan_xet.luu_nhan_xet("VR-0001", [{"ts": 3.0, "benh": "Mở đầu chậm", "muc": "nang",
                                       "loi": "giải thích", "so_lieu": "x", "nen_lam": "y"}])
    trang = client.get("/xem/VR-0001", headers=h()).text
    # dữ liệu nhúng qua |tojson nên tiếng Việt thành \uXXXX — soi bản đã giải mã
    import json, re
    nx_js = json.loads(re.search(r"var NX = (\[.*?\]);", trang, re.S).group(1))
    bl_js = json.loads(re.search(r"var BL = (\[.*?\]);", trang, re.S).group(1))
    assert [n["benh"] for n in nx_js] == ["Mở đầu chậm"]
    assert [b["noi_dung"] for b in bl_js] == ["note người"]
    assert "veTheMay" in trang                    # thẻ máy dựng trong CÙNG panel note
    assert "Nhờ AI đánh giá" in trang
    assert trang.count('class="bl-panel"') == 1   # vẫn đúng MỘT cột bình luận


def test_niche_suy_tu_duong_nas(client):
    _them(client)
    v = kho_video.lay_video("VR-0001")
    assert nhan_xet._niche_cua({"duong": "Life In/US/LI088/Feedback/a.mp4"}) == "life-in"
    assert nhan_xet._niche_cua({"duong": "a.mp4"}) == "a.mp4"
