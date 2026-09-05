# -*- coding: utf-8 -*-
"""GĐ7 — CSRF middleware KHÔNG được nuốt body form (05/09/2026).

SỰ CỐ THẬT (user báo): bấm Thêm API key → 422 "Field required" cho loai_chon +
khoa, cả hai input=null. Nguyên nhân: middleware `_chan_csrf` gọi
`await request.form()` để lấy token → đọc form trong middleware TIÊU THỤ luồng
body → route (Form(...)) nhận form RỖNG.

ĐÃ TÁI HIỆN THẬT trên server uvicorn (bản sao 9500): POST /general/api-keys/add
với token đúng → 422 "Field required". TestClient KHÔNG tái hiện được (cache
request.form khác server thật) — nên kiểm chứng CHÍNH nằm ở server thật, ghi trong
sổ docs/bao-mat-internet.md. Test dưới ghim phần tách token thuần (tất định).

Vá: middleware đọc RAW body một lần, tách token bằng `_csrf_tu_body` (KHÔNG gọi
request.form()), rồi gắn body lại qua request._receive để route đọc nguyên vẹn.
"""
from urllib.parse import urlencode

import pytest


def test_tach_token_tu_body_urlencoded():
    from nen.gateway.main import _csrf_tu_body
    from nen.common import csrf
    body = urlencode({"loai_chon": "youtube", "khoa": "AIza", csrf.TEN_TRUONG: "tok-abc"}).encode()
    ct = "application/x-www-form-urlencoded"
    assert _csrf_tu_body(body, ct) == "tok-abc"


def test_body_khong_co_token_tra_none():
    from nen.gateway.main import _csrf_tu_body
    body = urlencode({"loai_chon": "youtube", "khoa": "AIza"}).encode()
    assert _csrf_tu_body(body, "application/x-www-form-urlencoded") is None


def test_multipart_tra_none_khong_no():
    """multipart (upload) không parse ở đây — token đi qua header cho các form đó."""
    from nen.gateway.main import _csrf_tu_body
    assert _csrf_tu_body(b"--boundary--", "multipart/form-data; boundary=x") is None


def test_body_hong_khong_no():
    from nen.gateway.main import _csrf_tu_body
    assert _csrf_tu_body(bytes([255, 254]) + b" rac", "application/x-www-form-urlencoded") is None
