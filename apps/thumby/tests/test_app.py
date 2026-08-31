# -*- coding: utf-8 -*-
"""ThumbY V1 — khuôn hợp đồng app + các van spec docs/thumby.md:
ảnh không rời trình duyệt (KHÔNG endpoint nhận file), JS không dùng API
secure-context-only (bài học LAN HTTP 01/08), theme nghe storage cả hệ."""
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.main import app

_APP = Path(__file__).resolve().parents[1]
client = TestClient(app)
CLAIMS = {"X-Remote-User": "nv-kd", "X-Remote-Level": "2",
          "X-Remote-Dept": "Kinh%20doanh"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["app"] == "thumby"


def test_chan_khong_danh_tinh():
    """Fail-closed: gọi thẳng không qua gateway (thiếu claims) → 401."""
    assert client.get("/thumby").status_code == 401


def test_trang_render_du_khoi():
    r = client.get("/thumby", headers=CLAIMS)
    assert r.status_code == 200
    b = r.text
    # thanh vị trí + đủ 7 tab (5 PC + 2 điện thoại)
    assert 'id="posbar"' in b
    for pos in ("sug", "home", "srch", "chan", "zoom", "mnext", "mhome"):
        assert f'data-pos="{pos}"' in b, pos
    # điều khiển: 2 ô thả ảnh + chỗ đứng GĐ2 (nút Pool RadarY khóa)
    assert 'id="dropA"' in b and 'id="dropB"' in b
    assert "Pool RadarY" in b and "giai đoạn 2" in b
    # font Roboto bundle local — không gọi font ngoài Internet
    assert "/thumby-static/roboto-local.css" in b
    assert "fonts.googleapis.com" not in b
    # sidebar OUTLIERY của base render quanh trang
    assert 'class="sidebar"' in b


def test_khong_endpoint_nhan_file():
    """VAN SPEC: ảnh chỉ nằm trong trình duyệt — app V1 TUYỆT ĐỐI không có
    route ghi (POST/PUT/PATCH/DELETE). Ai thêm route ghi phải qua test này
    = qua spec (docs/thumby.md mục 3) trước."""
    for r in app.routes:
        if isinstance(r, APIRoute):
            assert r.methods <= {"GET", "HEAD"}, (r.path, r.methods)


def test_js_khong_api_secure_context():
    """Bài học 01/08/2026: app phục vụ qua HTTP LAN — crypto.randomUUID /
    navigator.clipboard là undefined ở đó, gọi trần là chết cả khối script."""
    tpl = (_APP / "src" / "templates" / "thumby.html").read_text(encoding="utf-8")
    assert "crypto.randomUUID" not in tpl
    assert "navigator.clipboard" not in tpl
    # localStorage CÓ dùng (nhớ ô nhập) nhưng phải bọc try/catch cả đọc lẫn ghi
    assert tpl.count("localStorage.") == 2
    assert "try{localStorage.setItem" in tpl
    assert "try{var x=JSON.parse(localStorage.getItem" in tpl


def test_theme_nghe_storage_ca_he():
    """Đổi theme ở app khác cùng origin → trang này lật theo (lệ 22/08,
    test quét cả cây của RadarY cũng bắt — đây là ghim cục bộ)."""
    base = (_APP / "src" / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'addEventListener("storage"' in base
    assert "outliery_theme" in base
