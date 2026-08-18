# -*- coding: utf-8 -*-
"""Test upload TỪNG KHÚC — phiên, ghép khúc tuần tự, trần, RBAC, dọn dở dang."""
import pytest
from fastapi.testclient import TestClient

from src import kho_video, upload_khuc
from src.main import app
from tests.test_routes import h


@pytest.fixture()
def client():
    upload_khuc._PHIEN.clear()
    with TestClient(app) as c:
        yield c


def _bat_dau(client, ten_file="tap1.mp4", kich_thuoc=10, ten="Tập 1", **hd):
    return client.post("/api-vr/upload-bat-dau", headers=h(**hd),
                       data={"ten_file": ten_file, "kich_thuoc": kich_thuoc, "ten": ten})


def test_bat_dau_kiem_o_cua(client, monkeypatch):
    assert _bat_dau(client, ten_file="x.exe").status_code == 422
    assert _bat_dau(client, kich_thuoc=0).status_code == 422
    monkeypatch.setenv("VR_MAX_MB", "1")
    assert _bat_dau(client, kich_thuoc=2 * 1024 * 1024).status_code == 413
    assert client.post("/api-vr/upload-bat-dau",
                       data={"ten_file": "a.mp4", "kich_thuoc": 1}).status_code == 401


def test_ghep_khuc_tron_vong(client):
    pid = _bat_dau(client, kich_thuoc=10).json()["phien"]
    r1 = client.post(f"/api-vr/upload-khuc/{pid}?offset=0", content=b"abcdef", headers=h())
    assert r1.status_code == 200 and r1.json()["da_nhan"] == 6
    r2 = client.post(f"/api-vr/upload-khuc/{pid}?offset=6", content=b"ghij", headers=h())
    assert r2.json()["da_nhan"] == 10
    xong = client.post(f"/api-vr/upload-xong/{pid}", headers=h())
    assert xong.status_code == 200 and xong.json()["ma"] == "VR-0001"
    v = kho_video.lay_video("VR-0001")
    assert v["kich_thuoc"] == 10 and v["ten"] == "Tập 1"
    assert (kho_video.kho_dir() / v["duong"]).read_bytes() == b"abcdefghij"
    assert not list(kho_video.kho_dir().glob("up-*.tam"))   # .tam đã replace vào kho


def test_lech_khuc_vuot_khai_va_thieu_du_lieu(client):
    pid = _bat_dau(client, kich_thuoc=10).json()["phien"]
    # offset lệch (gửi lại khúc cũ / nhảy cóc) → 409, không ghi
    assert client.post(f"/api-vr/upload-khuc/{pid}?offset=3", content=b"x",
                       headers=h()).status_code == 409
    # vượt kích thước khai → 413
    assert client.post(f"/api-vr/upload-khuc/{pid}?offset=0", content=b"y" * 11,
                       headers=h()).status_code == 413
    # chưa đủ byte mà đòi xong → 409, KHÔNG ghi sổ
    client.post(f"/api-vr/upload-khuc/{pid}?offset=0", content=b"abc", headers=h())
    assert client.post(f"/api-vr/upload-xong/{pid}", headers=h()).status_code == 409
    assert kho_video.danh_sach_video() == []


def test_phien_rbac_chi_chinh_chu(client):
    pid = _bat_dau(client).json()["phien"]
    assert client.post(f"/api-vr/upload-khuc/{pid}?offset=0", content=b"x",
                       headers=h(ten="binh")).status_code == 404
    assert client.post(f"/api-vr/upload-xong/{pid}",
                       headers=h(ten="binh")).status_code == 404


def test_huy_don_file_tam(client):
    pid = _bat_dau(client).json()["phien"]
    client.post(f"/api-vr/upload-khuc/{pid}?offset=0", content=b"abc", headers=h())
    assert client.post(f"/api-vr/upload-huy/{pid}", headers=h()).status_code == 200
    assert not list(kho_video.kho_dir().glob("up-*.tam"))
    assert client.post(f"/api-vr/upload-khuc/{pid}?offset=3", content=b"x",
                       headers=h()).status_code == 404


def test_don_phien_bo_do_qua_han(client):
    pid = _bat_dau(client).json()["phien"]
    upload_khuc._PHIEN[pid]["luc"] -= upload_khuc._HAN_GIAY + 60   # giả phiên 24h trước
    _bat_dau(client, ten_file="b.mp4")                             # phiên mới kích quét dọn
    assert pid not in upload_khuc._PHIEN
