# -*- coding: utf-8 -*-
"""B10.1 — vendor biểu đồ phục vụ được (ghim để nâng bản không làm hỏng lặng lẽ)."""
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_vendor_chart_phuc_vu_duoc():
    r = client.get("/tasky-static/vendor/frappe-charts.min.umd.js")
    assert r.status_code == 200
    assert "frappe" in r.text[:200].lower() or len(r.content) > 50_000


def test_vendor_khong_phai_file_rong():
    """Chép nhầm file 0 byte thì dashboard trắng mà không ai biết."""
    r = client.get("/tasky-static/vendor/frappe-charts.min.umd.js")
    assert len(r.content) > 50_000
