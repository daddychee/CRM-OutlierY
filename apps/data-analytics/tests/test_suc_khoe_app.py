# -*- coding: utf-8 -*-
"""B3 giám sát lan sang data-analytics (31/08/2026) — /api/suc-khoe.

- llm-dien-giai: DA nạp cấu hình LLM từ KÉT qua gateway mỗi lần Analyze; két
  trống vai writer → diễn giải trả MẪU lặng lẽ (cùng họ bệnh ai-agent 31/08).
  Health hỏi két 1 lần (timeout 3s): trống → canh_bao chỉ đường điền két.
- bao-cao: BAO_CAO_DIR đọc được + đếm báo cáo.
"""
from fastapi.testclient import TestClient

from src import main

tc = TestClient(main.app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "data-analytics"
    return {m["ten"]: m for m in b["mo_dun"]}


def test_gateway_chet_la_canh_bao_khong_500():
    # conftest trỏ GATEWAY_URL cổng chết — chính là ca này
    md = _mo_dun()
    assert md["llm-dien-giai"]["trang_thai"] == "canh_bao"


def test_ket_trong_vai_writer_canh_bao_chi_duong(monkeypatch):
    monkeypatch.setattr(main, "_hoi_ket_writer", lambda: {"provider": ""})
    md = _mo_dun()
    assert md["llm-dien-giai"]["trang_thai"] == "canh_bao"
    assert "két" in md["llm-dien-giai"]["chi_tiet"]


def test_ket_co_writer_la_ok_kem_model(monkeypatch):
    monkeypatch.setattr(main, "_hoi_ket_writer",
                        lambda: {"provider": "openai_compatible",
                                 "model": "glm-4.5-air"})
    md = _mo_dun()
    assert md["llm-dien-giai"]["trang_thai"] == "ok"
    assert "glm-4.5-air" in md["llm-dien-giai"]["chi_tiet"]


def test_bao_cao_dir_doc_duoc(tmp_path, monkeypatch):
    (tmp_path / "b1.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BAO_CAO_DIR", str(tmp_path))
    md = _mo_dun()
    assert md["bao-cao"]["trang_thai"] == "ok"
    assert "1" in md["bao-cao"]["chi_tiet"]
