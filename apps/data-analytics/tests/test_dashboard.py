# -*- coding: utf-8 -*-
"""Test trang /niche (dashboard gộp) — danh bạ mock qua monkeypatch, dữ liệu tmp."""
import json

import pytest
from fastapi.testclient import TestClient

from src import dashboard
from src.main import app
from tests.test_niche_bridge import _seed

CLAIMS = {"X-Remote-User": "tester", "X-Remote-Level": "2"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    project = _seed(tmp_path)                      # snapshot giả 2026-08-18, điểm 58
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))
    map_path = tmp_path / "niche_projects.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": project}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "TEST NICHE"}])
    monkeypatch.setattr(dashboard, "_ds_kenh",
                        lambda ma: [{"ma": "K-A", "ten_chuan": "KENH A",
                                     "ngach_ma": ma, "thi_truong_ma": "TT-US"}])
    monkeypatch.setattr(dashboard, "_ten_thi_truong", lambda: {"TT-US": "US"})
    return TestClient(app)


def test_khong_claims_401(client):
    assert client.get("/niche").status_code == 401


def test_overall_hien_tile_va_kenh(client):
    r = client.get("/niche", headers=CLAIMS)
    assert r.status_code == 200
    body = r.text
    assert "TEST NICHE" in body and "KENH A" in body        # rail: niche + kênh
    assert "58" in body and "3.071" in body                  # tile số thật từ snapshot
    assert "VÀO CÓ ĐIỀU KIỆN" in body                        # verdict tiếng Việt
    assert "Read report" in body and "New report" in body    # button tiếng Anh
    assert "hidden" in body and "iraq" in body               # Best & Worst cụm


def test_xem_lai_ngay_cu(client):
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-TEST", "ngay": "2026-08-18"})
    assert r.status_code == 200 and "snapshot 2026-08-18" in r.text


def test_doc_va_tai_bao_cao(client):
    ok = client.get("/niche/tai/TestNiche_US/2026-08-18/BAO-CAO-8-PHASE.html",
                    headers=CLAIMS, params={"inline": 1})
    assert ok.status_code == 200 and "text/html" in ok.headers["content-type"]
    assert "content-disposition" not in ok.headers or "attachment" not in ok.headers.get("content-disposition", "")
    tai = client.get("/niche/tai/TestNiche_US/2026-08-18/BAO-CAO-8-PHASE.html", headers=CLAIMS)
    assert "attachment" in tai.headers.get("content-disposition", "")
    # file ngoài sổ snapshot → 404 lặng lẽ
    assert client.get("/niche/tai/TestNiche_US/2026-08-18/decision1.json",
                      headers=CLAIMS).status_code == 404


def test_niche_chua_gan_project(client, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-KHAC", "ten_chuan": "NICHE TRỐNG"}])
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-KHAC"})
    assert r.status_code == 200 and "chưa gán dự án" in r.text
