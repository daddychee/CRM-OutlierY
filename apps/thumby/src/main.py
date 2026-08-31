# -*- coding: utf-8 -*-
"""THUMBY (v3, :9119) — mô phỏng vị trí hiển thị thumbnail YouTube.

Nghiệp vụ (docs/thumby.md, Owner chốt 31/08/2026): người làm packaging thả 1-2
ảnh thumbnail (A/B) + gõ title → xem đúng cách nó hiện ở từng vị trí YouTube
(Suggested 168px / Home / Search / Trang kênh / điện thoại), dark + light,
squint test. App MÔ PHỎNG — không chấm điểm tốt/xấu.

Đúng khuôn hợp đồng app (theo tasky / video-review):

1. AUTH: app KHÔNG giữ sổ user — claims X-Remote-* từ gateway (an toàn vì app
   bind 127.0.0.1, header giả từ trình duyệt đã bị gateway vứt). Cửa vào
   Kinh doanh L2 do gateway gate theo phan_quyen.json; app chỉ kiểm fail-closed
   "phải có danh tính". KHÔNG có hành động ghi nào (V1).
2. DỮ LIỆU: KHÔNG CÓ — ảnh đọc bằng FileReader, chỉ nằm trong trình duyệt.
   App cố ý KHÔNG có endpoint nhận file (test ghim); du_lieu=[] trong apps.json.
3. GĐ2 (chưa làm): đọc data/radary CHỈ-ĐỌC (mode=ro) lấy thumbnail đối thủ thật
   trong pool đứng cạnh A/B — cô lập vào module radary_reader.py khi làm.

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/thumby" --port 9119
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/thumby

PHIEN_BAN = "0.1.0"
app = FastAPI(title="ThumbY v3")
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar dùng chung

templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])
app.mount("/thumby-static", StaticFiles(directory=str(_APP_DIR / "src" / "static")),
          name="thumby-static")


# ---------- claims (app không tự giữ user) ----------

def lay_user(x_remote_user: str = Header("")) -> dict:
    """Cửa vào đã do gateway gate (Kinh doanh L2 — phan_quyen.json); app chỉ cần
    fail-closed: thiếu danh tính là chặn, không tự suy quyền."""
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    return {"ten": x_remote_user}


# ---------- health (hợp đồng app) ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "thumby", "phien_ban": PHIEN_BAN}


# ---------- trang duy nhất ----------

@app.get("/thumby", response_class=HTMLResponse)
def trang_chinh(request: Request, user: dict = Depends(lay_user)):
    """Toàn bộ nghiệp vụ chạy client-side trong template — server chỉ render."""
    return templates.TemplateResponse(request, "thumby.html", {})
