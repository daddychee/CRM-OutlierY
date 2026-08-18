# -*- coding: utf-8 -*-
"""Test cầu chạy pipeline ngách — HTTP + snapshot đều giả lập, không đụng service thật."""
import json

import pytest
from fastapi.testclient import TestClient

from src import dashboard, niche_run
from src.main import app

CLAIMS_L3 = {"X-Remote-User": "leader", "X-Remote-Level": "3"}
CLAIMS_L2 = {"X-Remote-User": "nv", "X-Remote-Level": "2"}


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


@pytest.fixture()
def client(tmp_path, monkeypatch):
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": "Proj_US"}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    # trạng thái sạch giữa các test (registry chống-snapshot-đúp là module-level)
    niche_run._da_snapshot.clear()
    return TestClient(app)


def test_chay_can_leader(client, monkeypatch):
    monkeypatch.setattr(niche_run.requests, "post",
                        lambda url, **kw: _Resp({"status": "resumed"}))
    assert client.post("/niche/chay/Proj_US", headers=CLAIMS_L2).status_code == 403
    r = client.post("/niche/chay/Proj_US", headers=CLAIMS_L3)
    assert r.status_code == 200 and r.json()["status"] == "resumed"


def test_project_ngoai_so_404(client):
    assert client.post("/niche/chay/LaProject", headers=CLAIMS_L3).status_code == 404
    assert client.get("/niche/chay/LaProject/trang-thai", headers=CLAIMS_L3).status_code == 404


def test_xong_thi_snapshot_dung_mot_lan(client, monkeypatch):
    goi = []
    monkeypatch.setattr(niche_run.requests, "get",
                        lambda url, **kw: _Resp({"running": False, "has_report": True}))
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: goi.append(p) or True)
    r1 = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
    r2 = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
    assert r1 == {"running": False, "has_report": True, "done_moi": True}
    assert r2["done_moi"] is False and goi == ["Proj_US"]    # snapshot đúng 1 lần


def test_chay_lai_mo_cua_snapshot_moi(client, monkeypatch):
    monkeypatch.setattr(niche_run.requests, "get",
                        lambda url, **kw: _Resp({"running": False, "has_report": True}))
    monkeypatch.setattr(niche_run.requests, "post",
                        lambda url, **kw: _Resp({"status": "resumed"}))
    goi = []
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: goi.append(p) or True)
    client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3)      # snapshot lần 1
    client.post("/niche/chay/Proj_US", headers=CLAIMS_L3)                # chạy mới → reset
    client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3)      # snapshot lần 2
    assert goi == ["Proj_US", "Proj_US"]


def test_service_chet_502(client, monkeypatch):
    def _no(url, **kw):
        raise niche_run.requests.ConnectionError("refused")
    monkeypatch.setattr(niche_run.requests, "post", _no)
    r = client.post("/niche/chay/Proj_US", headers=CLAIMS_L3)
    assert r.status_code == 502 and "không phản hồi" in r.json()["detail"]
