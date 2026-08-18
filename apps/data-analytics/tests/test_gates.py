# -*- coding: utf-8 -*-
"""Test gate ký — quyền theo bảng mockup v3, chữ ký sống trong sổ tmp."""
import pytest
from fastapi.testclient import TestClient

from src import dashboard, gates
from src.main import app


@pytest.fixture(autouse=True)
def _gates_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("GATES_DIR", str(tmp_path / "gates"))


def test_quyen_ky_theo_loai():
    with pytest.raises(PermissionError):
        gates.ky("N", "TT", "p0", {"ten": "ld", "level": 3})          # business cần L4
    gates.ky("N", "TT", "p0", {"ten": "mgr", "level": 4})
    gates.ky("N", "TT", "p4", {"ten": "ld", "level": 3})              # production L3 ok
    with pytest.raises(ValueError):
        gates.ky("N", "TT", "p1", {"ten": "mgr", "level": 5})         # auto không ký tay
    with pytest.raises(KeyError):
        gates.ky("N", "TT", "p9", {"ten": "mgr", "level": 5})


def test_trang_thai_va_chu_ky_song():
    gates.ky("N", "TT", "p3", {"ten": "mgr", "level": 4}, phuong_an="A")
    ds = gates.trang_thai("N", "TT", co_bao_cao=True, level=4)
    theo_ma = {g["ma"]: g for g in ds}
    assert theo_ma["p3"]["trang_thai"] == "da_ky" and theo_ma["p3"]["phuong_an"] == "A"
    assert theo_ma["p1"]["trang_thai"] == "dat"                        # auto + có báo cáo
    assert theo_ma["p0"]["trang_thai"] == "cho" and theo_ma["p0"]["ky_duoc"]
    assert theo_ma["p3"]["ky_duoc"] is False                           # ký rồi thì thôi
    # chưa có báo cáo → auto về chờ; level thấp → không ký được gate business
    ds2 = gates.trang_thai("N", "TT2", co_bao_cao=False, level=3)
    theo2 = {g["ma"]: g for g in ds2}
    assert theo2["p1"]["trang_thai"] == "cho"
    assert theo2["p0"]["ky_duoc"] is False and theo2["p4"]["ky_duoc"] is True


def test_route_ky_gate():
    client = TestClient(app)
    l3 = {"X-Remote-User": "ld", "X-Remote-Level": "3"}
    l4 = {"X-Remote-User": "mgr", "X-Remote-Level": "4"}
    assert client.post("/niche/gate/N/TT/p0", headers=l3).status_code == 403
    assert client.post("/niche/gate/N/TT/p1", headers=l4).status_code == 400
    assert client.post("/niche/gate/N/TT/p9", headers=l4).status_code == 404
    r = client.post("/niche/gate/N/TT/p3", headers=l4, data={"phuong_an": "A"})
    assert r.status_code == 200 and r.json()["boi"] == "mgr" and r.json()["phuong_an"] == "A"
    assert gates.doc("N", "TT")["p3"]["boi"] == "mgr"                  # đã ghi sổ
