# -*- coding: utf-8 -*-
"""B3 giám sát (31/08/2026) — sức khỏe SÂU của ai-agent (/api/suc-khoe).

Module đắt nhất: `kho-vector` — bắt đúng sự cố 31/07 (kho Qdrant RỖNG suốt 3
ngày trong khi catalog có tài liệu → hỏi–đáp chết LẶNG LẼ, không ai biết).
Lưới trang Kho tài liệu chỉ hiện khi Manager+ mở trang; giờ trồi lên hợp đồng
`suc_khoe` để tab Applications của nền tự thấy mà không cần ai bấm gì.
"""
from fastapi.testclient import TestClient

from src import main

tc = TestClient(main.app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "ai-agent" and b["trang_thai"] in ("ok", "canh_bao", "loi")
    return b, {m["ten"]: m for m in b["mo_dun"]}


def test_mock_mode_kho_la_canh_bao_khong_phai_ok():
    """MOCK không có kho thật — khai 'canh_bao' nói thẳng, không giả vờ ok
    (van chống bịa cho chính giám sát)."""
    b, md = _mo_dun()
    assert md["kho-vector"]["trang_thai"] == "canh_bao"
    assert "MOCK" in md["kho-vector"]["chi_tiet"]
    assert md["catalog"]["trang_thai"] == "ok"


def test_kho_rong_ma_catalog_co_tai_lieu_la_loi(monkeypatch):
    """Đúng ca sự cố 31/07: catalog có tài liệu + kho 0 point → 'loi' kèm lời
    chỉ đường nap_lai_kho.py."""
    monkeypatch.setattr(main.client, "mock", False)
    monkeypatch.setattr(main.client, "dem_point_kho", lambda: 0)
    monkeypatch.setattr(main, "doc_catalog", lambda: [{"Mã tài liệu": "KD-1"}])
    b, md = _mo_dun()
    assert md["kho-vector"]["trang_thai"] == "loi"
    assert "nap_lai_kho" in md["kho-vector"]["chi_tiet"]
    assert b["trang_thai"] == "loi"


def test_qdrant_chet_la_loi(monkeypatch):
    monkeypatch.setattr(main.client, "mock", False)
    monkeypatch.setattr(main.client, "dem_point_kho", lambda: None)
    b, md = _mo_dun()
    assert md["kho-vector"]["trang_thai"] == "loi"
    assert "Qdrant" in md["kho-vector"]["chi_tiet"]


def test_kho_khop_catalog_la_ok(monkeypatch):
    monkeypatch.setattr(main.client, "mock", False)
    monkeypatch.setattr(main.client, "dem_point_kho", lambda: 53)
    monkeypatch.setattr(main, "doc_catalog", lambda: [{"Mã tài liệu": "KD-1"}] * 10)
    b, md = _mo_dun()
    assert md["kho-vector"]["trang_thai"] == "ok"
    assert "53" in md["kho-vector"]["chi_tiet"]
