# -*- coding: utf-8 -*-
"""Proxy chuyển tiếp app phía sau gateway — CHUYỂN THỂ từ agent-app/src/app_proxy.py
(hệ cũ), giữ NGUYÊN các bẫy đã vá bằng sự cố thật 30/07–06/08/2026:

1. Header danh tính (X-Remote-User/Role) người dùng gửi lên bị VỨT — chỉ gateway đặt,
   app phụ bind 127.0.0.1 nên không có đường giả mạo.
2. App bị viết lại đường dẫn: CẤM conditional request (If-None-Match/If-Modified-Since)
   + CẮT ETag/Last-Modified ở phản hồi — ETag tính trên file gốc, trình duyệt nhận bản
   đã viết lại; để nguyên là dính cache bản hỏng tới khi Ctrl+F5.
3. X-Forwarded-Host/Proto luôn gửi — app tự dựng URL tuyệt đối (Gradio) thiếu nó là
   trỏ về 127.0.0.1; app có guard Origin-vs-Host (SEO) thiếu nó là 403 mọi POST.
4. Location chỉ thêm tiền tố khi CHƯA có (app tự khai root_path đã tự tiền tố — thêm
   nữa là đúp đường).
5. Tên user chuẩn hóa ASCII trước khi vào header — tên có dấu làm nổ UnicodeEncodeError.
6. Client httpx DÙNG CHUNG (keep-alive) — mỗi request một client là chục lần bắt tay
   TCP cho một trang nhiều asset.
7. SSE (text/event-stream) chảy thẳng, không gom bộ nhớ.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse

_client: httpx.AsyncClient | None = None
_client_loop = None


def _lay_client() -> httpx.AsyncClient:
    """Client dùng chung NHƯNG khóa theo event loop: AsyncClient gắn chặt vào loop
    tạo ra nó — production (uvicorn 1 loop) luôn tái dùng đúng client keep-alive;
    test (mỗi TestClient một loop) tự nhận client mới thay vì RuntimeError loop-khác.
    Bug bắt được bằng test tích hợp P1, 16/08/2026."""
    global _client, _client_loop
    import asyncio
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=40, max_connections=200))
        _client_loop = loop
    return _client


_HEADER_CAM = {"host", "connection", "keep-alive", "transfer-encoding", "upgrade",
               "proxy-authorization", "proxy-authenticate", "te", "trailer",
               "content-length", "accept-encoding",
               "x-remote-user", "x-remote-role", "x-remote-level", "x-remote-dept",
               "x-remote-apps", "x-remote-name", "x-role-code", "x-forwarded-for"}

_LOAI_CHU = ("text/html", "text/css", "application/javascript", "text/javascript",
             "application/json", "text/plain")
_LOAI_CHAY = "text/event-stream"


def ten_cho_header(ten: str) -> str:
    """Header HTTP chỉ nhận ASCII — 'Nguyễn Văn A' → 'nguyenvana'; rỗng → 'user'."""
    s = ten.strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(c for c in s if c.isalnum() or c in "._-")
    return s or "user"


def viet_lai_duong_dan(noi_dung: str, tien_to_app: list[str], goc: str) -> str:
    """Đổi đường dẫn tuyệt đối app tự khai (vd /api/x) thành đường qua gateway
    (/app/<slug>/api/x). Chỉ thay ở vị trí URL thật (sau nháy/ngoặc/dấu bằng)."""
    for t in tien_to_app:
        noi_dung = re.sub(
            rf'''(["'`(=])({re.escape(t)})(?=["'`/?#])''',
            rf'\1{goc}\2', noi_dung)
    return noi_dung


def _viet_lai_header(ten: str, gia_tri: str, goc: str, tien_to_app: list[str]) -> str:
    if ten == "location" and gia_tri.startswith("/"):
        if gia_tri == goc or gia_tri.startswith(goc + "/"):
            return gia_tri  # app tự tiền tố rồi — thêm nữa là đúp
        return goc + gia_tri
    if ten == "set-cookie":
        return re.sub(r"(?i)(;\s*Path=)(/[^;]*)", rf"\g<1>{goc}\g<2>", gia_tri)
    return gia_tri


async def chuyen_tiep(request: Request, cong: int, goc: str, duong_dan: str,
                      ten_user: str, tien_to_app: list[str], vai: str = "",
                      level: int | None = None, bo_phan: str = "",
                      apps_duoc_vao: list[str] | None = None,
                      ten_hien_thi: str = "") -> Response:
    """Chuyển tiếp request sang app 127.0.0.1:<cong>, tiêm claims do GATEWAY quyết."""
    dich = f"http://127.0.0.1:{cong}/{duong_dan}"
    cam = set(_HEADER_CAM)
    if tien_to_app:
        cam |= {"if-none-match", "if-modified-since"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in cam}
    if request.headers.get("host"):
        headers["X-Forwarded-Host"] = request.headers["host"]
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Remote-User"] = ten_cho_header(ten_user)
    if vai:
        headers["X-Remote-Role"] = vai
    if level is not None:
        headers["X-Remote-Level"] = str(level)
    if bo_phan:
        # Bộ phận có dấu tiếng Việt, header chỉ nhận ASCII → URL-encode ở đây,
        # app nhận unquote lại (RBAC bộ phận × level cần CHUỖI GỐC khớp payload).
        headers["X-Remote-Dept"] = quote(bo_phan)
    if ten_hien_thi:
        # Display name (tiếng Việt có dấu) → URL-encode như Dept, app unquote lại.
        headers["X-Remote-Name"] = quote(ten_hien_thi)
    if apps_duoc_vao is not None:
        # UI_FLOW.md mục 2: sidebar app nào hiện là GATEWAY quyết (một nguồn sự
        # thật quyền) — app chỉ đọc danh sách slug ASCII này, không tự đoán.
        headers["X-Remote-Apps"] = ",".join(apps_duoc_vao)
    than = await request.body()

    client = _lay_client()
    try:
        req = client.build_request(request.method, dich, headers=headers, content=than,
                                   params=dict(request.query_params))
        phan_hoi = await client.send(req, stream=True, follow_redirects=False)
    except httpx.ConnectError:
        return Response(
            f"<p style='font-family:system-ui;padding:24px'>⚠️ Chưa mở được app "
            f"(cổng {cong} không trả lời). Xem trang Sức khỏe hệ.</p>",
            status_code=502, media_type="text/html; charset=utf-8")

    loai = phan_hoi.headers.get("content-type", "")
    bo_ra = {"content-length", "transfer-encoding", "content-encoding"}
    if tien_to_app:
        bo_ra |= {"etag", "last-modified"}
    ra = {k: _viet_lai_header(k.lower(), v, goc, tien_to_app)
          for k, v in phan_hoi.headers.multi_items() if k.lower() not in bo_ra}

    if _LOAI_CHAY in loai:
        async def chay():
            try:
                async for mau in phan_hoi.aiter_raw():
                    yield mau
            finally:
                await phan_hoi.aclose()
        return StreamingResponse(chay(), status_code=phan_hoi.status_code, headers=ra,
                                 media_type=loai or None)

    noi_dung = await phan_hoi.aread()
    await phan_hoi.aclose()

    if tien_to_app and any(l in loai for l in _LOAI_CHU):
        try:
            noi_dung = viet_lai_duong_dan(
                noi_dung.decode("utf-8"), tien_to_app, goc).encode("utf-8")
        except UnicodeDecodeError:
            pass
    return Response(noi_dung, status_code=phan_hoi.status_code, headers=ra,
                    media_type=loai or None)
