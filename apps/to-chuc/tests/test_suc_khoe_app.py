# -*- coding: utf-8 -*-
"""B3 giám sát lan sang to-chuc (31/08/2026) — /api/suc-khoe.

Module kpi-nguon: KPI đọc 4 nguồn CHỈ-ĐỌC ngoài app; nguồn chết thì KPI hiện
'—' (van chống bịa) nhưng không ai biết VÌ SAO. Health khai thẳng: nguồn nào
chưa nối (env chưa đặt) / mất (env đặt mà file biến mất) — tab Applications
tự thấy, hết cảnh "KPI toàn gạch ngang" mà phải đi điều tra.
"""
from fastapi.testclient import TestClient

from src.main import app

tc = TestClient(app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "to-chuc" and b["trang_thai"] in ("ok", "canh_bao", "loi")
    return {m["ten"]: m for m in b["mo_dun"]}


def test_nguon_chua_noi_la_canh_bao_neu_ro_ten(monkeypatch):
    monkeypatch.delenv("PLANNERY_PLAN", raising=False)
    monkeypatch.delenv("CONTENT_HISTORY", raising=False)
    monkeypatch.delenv("BAO_CAO_DIR", raising=False)
    md = _mo_dun()
    assert md["kpi-nguon"]["trang_thai"] == "canh_bao"
    assert "PLANNERY_PLAN" in md["kpi-nguon"]["chi_tiet"]


def test_du_nguon_la_ok(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    hist = tmp_path / "h.jsonl"
    hist.write_text("", encoding="utf-8")
    bc = tmp_path / "bao-cao"
    bc.mkdir()
    monkeypatch.setenv("PLANNERY_PLAN", str(plan))
    monkeypatch.setenv("CONTENT_HISTORY", str(hist))
    monkeypatch.setenv("BAO_CAO_DIR", str(bc))
    md = _mo_dun()
    assert md["kpi-nguon"]["trang_thai"] == "ok"


def test_nguon_da_noi_ma_mat_la_loi(tmp_path, monkeypatch):
    """env đặt rồi mà file biến mất = nguồn TỪNG sống giờ chết — nặng hơn chưa nối."""
    monkeypatch.setenv("PLANNERY_PLAN", str(tmp_path / "khong-co.json"))
    md = _mo_dun()
    assert md["kpi-nguon"]["trang_thai"] == "loi"
    assert "khong-co.json" in md["kpi-nguon"]["chi_tiet"]
