# -*- coding: utf-8 -*-
"""Test nạp video từ NAS — duyệt an toàn + chép nền + RBAC tác vụ."""
import pytest
from fastapi.testclient import TestClient

from src import kho_video, nap_nas
from src.main import app
from tests.test_routes import h


@pytest.fixture()
def client():
    nap_nas._TAC_VU.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def nas(tmp_path, monkeypatch):
    """Cây NAS giả: goc/xuat/tap1.mp4 (+ file txt phải bị lọc)."""
    goc = tmp_path / "nas"
    (goc / "xuat").mkdir(parents=True)
    (goc / "xuat" / "tap1.mp4").write_bytes(b"v" * 4096)
    (goc / "xuat" / "ghi-chu.txt").write_text("x")
    (goc / "khac").mkdir()
    monkeypatch.setenv("VR_NAS_DIR", str(goc))
    return goc


def test_chua_cau_hinh_thi_an(client):
    r = client.get("/api-vr/nas", headers=h())
    assert r.status_code == 200 and r.json()["cau_hinh"] is False


def test_liet_ke_loc_duoi_va_can_claims(client, nas):
    assert client.get("/api-vr/nas").status_code == 401
    goc = client.get("/api-vr/nas", headers=h()).json()
    assert [m["ten"] for m in goc["muc"]] == ["khac", "xuat"]
    con = client.get("/api-vr/nas", params={"duong": "xuat"}, headers=h()).json()
    assert [m["ten"] for m in con["muc"]] == ["tap1.mp4"]   # .txt bị lọc
    assert con["muc"][0]["loai"] == "file"


def test_chan_path_traversal(client, nas):
    for xau in ["..", "../..", "xuat/../../..", "C:/Windows"]:
        r = client.get("/api-vr/nas", params={"duong": xau}, headers=h())
        assert r.status_code == 404, xau     # ngoài root = 404 lặng lẽ, không lộ cây


def test_nap_tron_vong_va_giu_nguyen_file_goc(client, nas):
    r = client.post("/api-vr/nas-nap", data={"duong": "xuat/tap1.mp4", "ten": "Tập 1"},
                    headers=h())
    assert r.status_code == 200
    tid = r.json()["task_id"]
    # TestClient chạy BackgroundTasks ngay trong request → tác vụ đã xong
    tt = client.get(f"/api-vr/nas-tien-do/{tid}", headers=h()).json()
    assert tt["trang_thai"] == "xong" and tt["phan_tram"] == 100 and tt["ma"] == "VR-0001"
    v = kho_video.lay_video("VR-0001")
    assert v["kich_thuoc"] == 4096
    assert (kho_video.kho_dir() / v["duong"]).read_bytes() == b"v" * 4096
    assert (nas / "xuat" / "tap1.mp4").is_file()            # file gốc NAS không bị đụng
    assert not list(kho_video.kho_dir().glob("*.tam"))       # không sót file tạm


def test_nap_chan_duoi_tran_va_file_ma(client, nas, monkeypatch):
    assert client.post("/api-vr/nas-nap", data={"duong": "xuat/ghi-chu.txt"},
                       headers=h()).status_code == 422
    assert client.post("/api-vr/nas-nap", data={"duong": "xuat/khong-co.mp4"},
                       headers=h()).status_code == 404
    monkeypatch.setenv("VR_NAS_MAX_MB", "0")
    assert client.post("/api-vr/nas-nap", data={"duong": "xuat/tap1.mp4"},
                       headers=h()).status_code == 413


def test_tien_do_rbac_chi_chu_tac_vu(client, nas):
    tid = client.post("/api-vr/nas-nap", data={"duong": "xuat/tap1.mp4"},
                      headers=h()).json()["task_id"]
    assert client.get(f"/api-vr/nas-tien-do/{tid}", headers=h(ten="binh")).status_code == 404
    assert client.get(f"/api-vr/nas-tien-do/{tid}", headers=h()).status_code == 200


def test_chep_hong_khong_de_lai_ban_ghi(client, nas, monkeypatch):
    def no(*a, **k):
        raise RuntimeError("đĩa đầy giả lập")
    monkeypatch.setattr(kho_video, "them_video", no)
    tid = client.post("/api-vr/nas-nap", data={"duong": "xuat/tap1.mp4"},
                      headers=h()).json()["task_id"]
    tt = client.get(f"/api-vr/nas-tien-do/{tid}", headers=h()).json()
    assert tt["trang_thai"] == "loi" and "đĩa đầy" in tt["loi"]
    assert kho_video.danh_sach_video() == []                 # không có video ma
    assert not list(kho_video.kho_dir().glob("*.tam"))       # file tạm được dọn


def test_trang_danh_sach_hien_khoi_nas_khi_cau_hinh(client, nas):
    r = client.get("/danh-sach", headers=h())
    assert "Load from NAS" in r.text
