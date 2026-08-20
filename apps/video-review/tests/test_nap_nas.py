# -*- coding: utf-8 -*-
"""Test duyệt NAS + LIÊN KẾT video (từ 20/08 app không chép file về nữa)."""
import pytest
from fastapi.testclient import TestClient

from src import kho_video, nap_nas
from src.main import app
from tests.test_routes import h


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def nas():
    """Cây NAS giả: goc/xuat/tap1.mp4 (+ file txt phải bị lọc) — gốc do conftest khai."""
    goc = kho_video.nas_dir()
    (goc / "xuat").mkdir(parents=True)
    (goc / "xuat" / "tap1.mp4").write_bytes(b"v" * 4096)
    (goc / "xuat" / "ghi-chu.txt").write_text("x", encoding="utf-8")
    (goc / "khac").mkdir()
    return goc


def test_chua_cau_hinh_thi_an(client, monkeypatch):
    monkeypatch.setenv("VR_NAS_DIR", "")
    r = client.get("/api-vr/nas", headers=h())
    assert r.status_code == 200 and r.json()["cau_hinh"] is False


def test_liet_ke_loc_duoi_va_can_claims(client, nas):
    assert client.get("/api-vr/nas").status_code == 401
    goc = client.get("/api-vr/nas", headers=h()).json()
    assert [m["ten"] for m in goc["muc"]] == ["khac", "xuat"]
    con = client.get("/api-vr/nas", params={"duong": "xuat"}, headers=h()).json()
    assert [m["ten"] for m in con["muc"]] == ["tap1.mp4"]   # .txt bị lọc
    assert con["muc"][0]["loai"] == "file" and con["muc"][0]["da_them"] is False


def test_chan_path_traversal(client, nas):
    for xau in ["..", "../..", "xuat/../../..", "C:/Windows"]:
        r = client.get("/api-vr/nas", params={"duong": xau}, headers=h())
        assert r.status_code == 404, xau     # ngoài gốc = 404 lặng lẽ, không lộ cây


def test_lien_ket_giu_nguyen_file_goc_va_ghi_van_tay(client, nas):
    f = nas / "xuat" / "tap1.mp4"
    r = client.post("/api-vr/nas-lien-ket", data={"duong": "xuat/tap1.mp4", "ten": "Tập 1"},
                    headers=h())
    assert r.status_code == 200 and r.json()["ma"] == "VR-0001"
    v = kho_video.lay_video("VR-0001")
    assert v["nguon"] == "nas" and v["duong"] == "xuat/tap1.mp4"
    assert v["ten_file"] == "tap1.mp4" and v["kich_thuoc"] == 4096
    assert abs(v["nas_mtime"] - f.stat().st_mtime) < 1     # vân tay chụp lúc liên kết
    assert f.read_bytes() == b"v" * 4096                   # file gốc NAS không bị đụng
    assert not list(kho_video.kho_dir().rglob("*.mp4"))    # không chép bản sao nào


def test_file_da_them_bi_danh_dau_trong_danh_sach_nas(client, nas):
    client.post("/api-vr/nas-lien-ket", data={"duong": "xuat/tap1.mp4"}, headers=h())
    con = client.get("/api-vr/nas", params={"duong": "xuat"}, headers=h()).json()
    assert con["muc"][0]["da_them"] is True
    # gỡ mềm rồi thì file NAS được phép thêm lại
    kho_video.doi_trang_thai("VR-0001", "da_xoa")
    con2 = client.get("/api-vr/nas", params={"duong": "xuat"}, headers=h()).json()
    assert con2["muc"][0]["da_them"] is False


def test_lien_ket_ngoai_goc_bi_chan_o_server(client, nas, tmp_path):
    ngoai = tmp_path / "ngoai-vung.mp4"
    ngoai.write_bytes(b"v")
    for xau in ["../ngoai-vung.mp4", str(ngoai)]:
        r = client.post("/api-vr/nas-lien-ket", data={"duong": xau}, headers=h())
        assert r.status_code == 404, xau
    assert kho_video.danh_sach_video() == []


def test_ham_lien_ket_bao_loi_ro_khi_nas_chua_khai(monkeypatch, nas):
    monkeypatch.setenv("VR_NAS_DIR", "")
    with pytest.raises(FileNotFoundError):
        nap_nas.lien_ket("xuat/tap1.mp4", "x", "an", "Vận hành")


def test_trang_danh_sach_hien_khoi_nas_khi_cau_hinh(client, nas):
    assert "Add a cut from NAS" in client.get("/danh-sach", headers=h()).text
