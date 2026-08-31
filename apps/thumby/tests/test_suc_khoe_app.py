# -*- coding: utf-8 -*-
"""B3 giám sát lan sang thumby (31/08/2026) — /api/suc-khoe.

Module radary-db: GĐ2 đọc RadarY CHỈ-ĐỌC (video đang nổ cùng chủ đề). DB
không đọc được → tính năng phụ tắt nhưng mô phỏng thumbnail VẪN chạy →
canh_bao chứ KHÔNG loi (đúng độ nặng thật của bệnh).
"""
from fastapi.testclient import TestClient

from src import main

tc = TestClient(main.app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "thumby"
    return {m["ten"]: m for m in b["mo_dun"]}


def test_radary_doc_duoc_la_ok(monkeypatch):
    monkeypatch.setattr(main.radary_reader, "danh_sach_pool",
                        lambda: [{"id": 1}, {"id": 2}])
    md = _mo_dun()
    assert md["radary-db"]["trang_thai"] == "ok"
    assert "2 pool" in md["radary-db"]["chi_tiet"]


def test_radary_chet_chi_canh_bao_khong_loi(monkeypatch):
    def _no():
        raise OSError("db khoa")
    monkeypatch.setattr(main.radary_reader, "danh_sach_pool", _no)
    md = _mo_dun()
    assert md["radary-db"]["trang_thai"] == "canh_bao"
    assert "mô phỏng" in md["radary-db"]["chi_tiet"]
