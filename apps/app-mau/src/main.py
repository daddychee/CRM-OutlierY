# -*- coding: utf-8 -*-
"""APP MẪU — chứng minh hợp đồng app của platform v2.

Một app nghiệp vụ tối thiểu đúng chuẩn: bind 127.0.0.1, tin claims từ gateway
(X-Remote-User/Role/Level — an toàn VÌ chỉ gateway tới được cổng này), trả /health
cho trang sức khỏe. App thật (ai-agent, data-analytics...) theo đúng khuôn này.

Chạy: python -m uvicorn main:app --app-dir "apps/app-mau/src" --port 9190
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from nen.common import suc_khoe

PHIEN_BAN = "0.1.0"
app = FastAPI(title="App mẫu")


@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "app-mau", "phien_ban": PHIEN_BAN}


@app.get("/api/suc-khoe")
async def api_suc_khoe():
    """Sức khỏe SÂU theo khuôn nen/common/suc_khoe.py — app thật thay các kiểm
    mẫu bằng kiểm nghiệp vụ của mình (DB nối được? kho vector khớp catalog?
    job nền chạy đúng hạn?). Check nổ → module 'loi', endpoint vẫn 200."""
    return suc_khoe.bao_cao("app-mau", PHIEN_BAN, [
        ("tien-trinh", lambda: ("ok", "app đang phục vụ")),
    ])


@app.get("/", response_class=HTMLResponse)
async def trang_chu(request: Request):
    user = request.headers.get("x-remote-user", "(không có — gọi thẳng không qua gateway?)")
    vai = request.headers.get("x-remote-role", "(không có)")
    level = request.headers.get("x-remote-level", "(không có)")
    apps_vao = request.headers.get("x-remote-apps", "(không có)")
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>App mẫu</title></head>
<body style="font-family:system-ui;max-width:560px;margin:48px auto;line-height:1.7">
<h2>✅ App mẫu — hợp đồng app hoạt động</h2>
<p>Claims nhận từ gateway (app không tự giữ sổ user nào):</p>
<ul>
<li>Người dùng: <b>{user}</b></li>
<li>Vai: <b>{vai}</b> · Level: <b>{level}</b></li>
<li>Được vào app: <b>{apps_vao}</b> (X-Remote-Apps — sidebar dựng từ đây)</li>
</ul>
<p style="color:#777;font-size:13px">Nếu bạn thấy tên thật của mình ở trên nghĩa là:
đăng nhập một lần ở gateway → mọi app phía sau tự biết bạn là ai. Header giả gửi từ
trình duyệt đã bị gateway vứt trước khi tới đây.</p>
<p><a href="/app/app-mau/health">/health</a> · <a href="/">Trang chủ gateway</a></p>
</body></html>"""
