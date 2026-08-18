# -*- coding: utf-8 -*-
"""Test API cầu nối AI Agent (phương án 2) — registry + lát JSON + van mục lạ."""
import json

import pytest
from fastapi.testclient import TestClient

from src import dashboard
from src.main import app
from tests.test_niche_bridge import _seed

CLAIMS = {"X-Remote-User": "agent", "X-Remote-Level": "2"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    project = _seed(tmp_path)
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": project}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "TEST NICHE"}])
    monkeypatch.setattr(dashboard, "_ds_kenh",
                        lambda ma: [{"ma": "K-A", "ten_chuan": "KENH A", "bi_danh": "",
                                     "ngach_ma": ma, "thi_truong_ma": "TT-US"}])
    monkeypatch.setattr(dashboard, "_ten_thi_truong", lambda: {"TT-US": "US"})
    return TestClient(app)


def test_registry_muc_luc_song(client):
    from src.bao_cao_lich_su import luu_bao_cao
    luu_bao_cao("t", {"id": "r1", "ten_file_goc": "x.csv", "ten_bao_cao": "Tuần 33",
                      "ten_kenh": "Kenh A", "duong_dan_goc": "/x", "kenh": {}},
                "2026-08-17T00:00:00")
    r = client.get("/api/agent/registry", headers=CLAIMS)
    assert r.status_code == 200
    d = r.json()
    ni = d["niches"][0]
    assert ni["markets"][0]["project"] == "TestNiche_US"
    assert ni["markets"][0]["snapshots"] == ["2026-08-18"]
    assert ni["channels"][0]["reports"][0]["id"] == "r1"
    assert "decision2" in d["muc_ngach"]


def test_lat_bao_cao_ngach(client):
    r = client.get("/api/agent/bao-cao/TestNiche_US", headers=CLAIMS,
                   params={"muc": "decision2"})
    assert r.status_code == 200
    d = r.json()
    assert d["snapshot"] == "2026-08-18"
    assert d["du_lieu"]["ranked"][0]["anchor"] == "hidden"     # bảng nguyên cấu trúc
    tom = client.get("/api/agent/bao-cao/TestNiche_US", headers=CLAIMS).json()
    assert tom["muc"] == "tom_tat" and tom["du_lieu"]["diem_hap_dan"] == 58


def test_van_chong_bia_muc_va_project(client):
    r = client.get("/api/agent/bao-cao/TestNiche_US", headers=CLAIMS,
                   params={"muc": "bi_mat"})
    assert r.status_code == 400 and "Hợp lệ" in r.json()["detail"]
    assert client.get("/api/agent/bao-cao/KhongCo", headers=CLAIMS).status_code == 404
    # snapshot có nhưng thiếu artifact của mục đó → 404 nói rõ
    # (dùng 'subniche' — mục DUY NHẤT _seed không ghi; analysis/bets đã có thật)
    r2 = client.get("/api/agent/bao-cao/TestNiche_US", headers=CLAIMS,
                    params={"muc": "subniche"})
    assert r2.status_code == 404 and "không có mục subniche" in r2.json()["detail"]


def test_kenh_report_theo_id(client):
    from src.bao_cao_lich_su import luu_bao_cao
    luu_bao_cao("t", {"id": "r9", "ten_file_goc": "x.csv", "ten_kenh": "Kenh A",
                      "duong_dan_goc": "/mat", "kenh": {"so_video": 5}},
                "2026-08-17T00:00:00")
    r = client.get("/api/agent/kenh-report/r9", headers=CLAIMS)
    assert r.status_code == 200 and r.json()["kenh"]["so_video"] == 5
    assert "duong_dan_goc" not in r.json()                     # không lộ đường nội bộ
    assert client.get("/api/agent/kenh-report/khong-co", headers=CLAIMS).status_code == 404
