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


def test_writer_mock_la_canh_bao_chi_duong_ket(monkeypatch):
    """Ca thật 31/08: két có critic mà vai WRITER trống → hỏi–đáp trả lời MẪU
    trên hệ thật dù kho đã thật. Tab giám sát phải tự soi được, kèm lời chỉ
    đường điền két — không chờ ai nghi ngờ câu trả lời."""
    from types import SimpleNamespace
    monkeypatch.setattr(main.qa, "writer",
                        SimpleNamespace(mock=True, model="glm-4.5-air"))
    b, md = _mo_dun()
    assert md["llm-writer"]["trang_thai"] == "canh_bao"
    assert "két" in md["llm-writer"]["chi_tiet"]


def test_canary_search_0_ket_qua_la_loi_va_co_cache(monkeypatch):
    """B6 canary: kho có dữ liệu, health khác đều xanh mà search câu phổ quát ra
    0 kết quả = tầng truy xuất lệch (model/hybrid/alias) — chỉ canary bắt được.
    Search local rẻ nhưng không miễn phí → cache 10 phút (vòng giám sát gọi 60s/lần)."""
    dem = []
    monkeypatch.setattr(main.client, "mock", False)
    monkeypatch.setattr(main.client, "dem_point_kho", lambda: 5)
    monkeypatch.setattr(main, "doc_catalog", lambda: [{"Mã tài liệu": "KD-1"}])
    monkeypatch.setattr(main.client, "search", lambda q: dem.append(q) or [])
    monkeypatch.setattr(main, "_CANARY", {"ts": 0.0, "kq": None})
    b, md = _mo_dun()
    assert md["search-canary"]["trang_thai"] == "loi"
    _mo_dun()
    assert len(dem) == 1  # lần 2 ăn cache, không search lại


def test_canary_search_co_ket_qua_la_ok(monkeypatch):
    monkeypatch.setattr(main.client, "mock", False)
    monkeypatch.setattr(main.client, "dem_point_kho", lambda: 5)
    monkeypatch.setattr(main, "doc_catalog", lambda: [{"Mã tài liệu": "KD-1"}])
    monkeypatch.setattr(main.client, "search", lambda q: [{"document_id": "KD-1"}])
    monkeypatch.setattr(main, "_CANARY", {"ts": 0.0, "kq": None})
    b, md = _mo_dun()
    assert md["search-canary"]["trang_thai"] == "ok"


def test_canary_mock_la_canh_bao(monkeypatch):
    b, md = _mo_dun()  # conftest ép MOCK
    assert md["search-canary"]["trang_thai"] == "canh_bao"


def test_writer_that_la_ok_kem_ten_model(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(main.qa, "writer",
                        SimpleNamespace(mock=False, model="glm-4.5-air"))
    monkeypatch.setattr(main.qa, "critics", [SimpleNamespace(mock=False)])
    b, md = _mo_dun()
    assert md["llm-writer"]["trang_thai"] == "ok"
    assert "glm-4.5-air" in md["llm-writer"]["chi_tiet"]
