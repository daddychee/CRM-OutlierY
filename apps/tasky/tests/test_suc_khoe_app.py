# -*- coding: utf-8 -*-
"""B3 giám sát lan sang tasky (31/08/2026) — /api/suc-khoe.

Module nas-goc: Owner chốt 31/08 "tài liệu gộp hết vào 1 folder trên NAS" —
NAS_TASKY_GOC rời là đính kèm file chết lặng lẽ. Chưa khai → canh_bao;
khai mà mất → loi.
"""
from fastapi.testclient import TestClient

from src.main import app

tc = TestClient(app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "tasky"
    return {m["ten"]: m for m in b["mo_dun"]}


def test_chua_khai_canh_bao(monkeypatch):
    monkeypatch.delenv("NAS_TASKY_GOC", raising=False)
    md = _mo_dun()
    assert md["nas-goc"]["trang_thai"] == "canh_bao"


def test_khai_ma_mat_la_loi(tmp_path, monkeypatch):
    monkeypatch.setenv("NAS_TASKY_GOC", str(tmp_path / "bay-hoi"))
    md = _mo_dun()
    assert md["nas-goc"]["trang_thai"] == "loi"
    assert "bay-hoi" in md["nas-goc"]["chi_tiet"]


def test_goc_song_la_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("NAS_TASKY_GOC", str(tmp_path))
    md = _mo_dun()
    assert md["nas-goc"]["trang_thai"] == "ok"
