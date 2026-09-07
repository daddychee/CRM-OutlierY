# -*- coding: utf-8 -*-
"""CỔNG VÀO cho bản thử Finance — tiêm danh tính Owner để khỏi phải đăng nhập.

App to-chuc chỉ tin header X-Remote-* khi gọi từ loopback và có TC_TRUST_PROXY
(siết 05/09). Cổng này đứng giữa: nhận request từ LAN, kiểm KHÓA, rồi gọi app
qua 127.0.0.1 kèm header — đúng vai gateway thật, nhưng chỉ phục vụ bản thử.

BA RÀO, vì cổng này bỏ qua đăng nhập:
  1. phải có khóa (?key=… lần đầu, sau đó nằm trong cookie phiên)
  2. chỉ nghe LAN nội bộ 192.168.*, không ra Internet
  3. sống cùng bản thử — tắt bản thử là tắt luôn

KHÔNG dùng cho bản thật, và không để chạy qua đêm. Tắt:
  .\finance-thu-nghiem.ps1 -Tat
"""
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

KHOA = os.environ["FTN_KHOA"]
DICH = "http://127.0.0.1:" + os.environ.get("FTN_CONG_APP", "9203")
CONG_VAO = int(os.environ.get("FTN_CONG_VAO", "9204"))
TEN_COOKIE = "ftn_key"

# Danh tính tiêm sẵn: Owner, đủ cờ để vào Finance + HR
DANH_TINH = {
    "X-Remote-User": "Bot",
    "X-Remote-Level": "5",
    "X-Remote-Role": "admin",
    "X-Remote-Dept": "Ban%20qu%E1%BA%A3n%20tr%E1%BB%8B",
    "X-Remote-Apps": "to-chuc,hr,finance,nas,quan-tri",
}

app = FastAPI(title="Bản thử Finance — cổng vào")
_client = httpx.AsyncClient(base_url=DICH, timeout=30.0, follow_redirects=False)

CHAN = """<!doctype html><meta charset="utf-8">
<title>Bản thử Finance</title>
<style>body{font-family:system-ui;background:#0d1117;color:#e6edf3;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}
div{max-width:30rem;padding:1.5rem 2rem;border:1px solid #30363d;border-radius:12px}
code{background:#161b22;padding:2px 6px;border-radius:4px}</style>
<div><h2>Bản thử Finance</h2>
<p>Cần khóa để vào. Mở lại bằng đường dẫn có <code>?key=…</code> mà bản thử in ra
lúc khởi động.</p>
<p style="color:#8b949e;font-size:.9rem">Đây là bản thử chạy trên dữ liệu sao chép —
không phải hệ thật của team.</p></div>"""


def _co_khoa(request: Request) -> bool:
    return (request.query_params.get("key") == KHOA
            or request.cookies.get(TEN_COOKIE) == KHOA)


@app.middleware("http")
async def chan_va_chuyen(request: Request, call_next):
    if not _co_khoa(request):
        return HTMLResponse(CHAN, status_code=401)

    # bỏ 'key' khỏi query trước khi chuyển tiếp cho app
    q = [(k, v) for k, v in request.query_params.multi_items() if k != "key"]
    duong = request.url.path + ("?" + "&".join(f"{k}={v}" for k, v in q) if q else "")

    than = await request.body()
    dau = {k: v for k, v in request.headers.items()
           if k.lower() not in ("host", "content-length", "connection")}
    dau.update(DANH_TINH)

    r = await _client.request(request.method, duong, content=than, headers=dau)
    ra_dau = {k: v for k, v in r.headers.items()
              if k.lower() not in ("content-length", "content-encoding",
                                   "transfer-encoding", "connection")}
    tra = Response(content=r.content, status_code=r.status_code, headers=ra_dau)
    if request.query_params.get("key") == KHOA:        # nhớ khóa cho lượt sau
        tra.set_cookie(TEN_COOKIE, KHOA, httponly=True, samesite="lax")
    return tra


@app.get("/")
async def goc():
    return RedirectResponse("/finance", status_code=303)


if __name__ == "__main__":
    import uvicorn
    # nghe LAN để mở từ máy khác; khóa ở trên là rào duy nhất, nên KHÔNG mở
    # cổng này ra Internet và không để chạy qua đêm.
    uvicorn.run(app, host="0.0.0.0", port=CONG_VAO, log_level="warning")
