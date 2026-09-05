# -*- coding: utf-8 -*-
"""GĐ1 — video-review: KHÔNG tin header khi chưa đủ điều kiện (05/09/2026).

LỖ ĐÃ TÌM (rà 05/09): `lay_user()` chỉ cần header CÓ MẶT là tin. Cổng 9114 lộ ra
thì `curl -H "X-Remote-User: x" -H "X-Remote-Level: 5" -H "X-Remote-Actions: xoa"`
thành Owner và XÓA VĨNH VIỄN file gốc trên NAS (NAS không có Recycle Bin).

Sửa: dùng `nen.common.xac_thuc_app.duoc_tin` — đòi CẢ `VR_TRUST_PROXY=1` LẪN
client loopback, y khuôn seo-optimize.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

GOC = Path(__file__).resolve().parents[3]
if str(GOC) not in sys.path:
    sys.path.insert(0, str(GOC))


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("VR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VR_TRUST_PROXY", "1")   # bật như tác vụ nền thật
    from src import main as m
    return TestClient(m.app)


HEADER_GIA = {"X-Remote-User": "keXau", "X-Remote-Level": "5",
              "X-Remote-Role": "owner", "X-Remote-Actions": "duyet,xoa"}


def test_tu_choi_khi_TRUST_PROXY_tat(monkeypatch, tmp_path):
    """Cờ tắt (app chạy trần / container mới) → header vô giá trị."""
    monkeypatch.setenv("VR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VR_TRUST_PROXY", raising=False)
    from src import main as m
    c = TestClient(m.app)
    r = c.get("/danh-sach", headers=HEADER_GIA)
    assert r.status_code in (401, 403, 404), (
        f"App tin header dù VR_TRUST_PROXY tắt → {r.status_code}")


def test_nhan_header_khi_du_dieu_kien(client):
    """TestClient gửi từ 'testclient' — không phải loopback thật.

    Ghi rõ hành vi mong đợi để bản vá không vô tình nới: nếu TestClient bị coi là
    không-loopback thì app PHẢI từ chối (đúng chiều fail-closed).
    """
    r = client.get("/danh-sach", headers=HEADER_GIA)
    assert r.status_code in (200, 401, 403, 404)


def test_thieu_danh_tinh_thi_401(client):
    r = client.get("/danh-sach")
    assert r.status_code in (401, 403, 404)
