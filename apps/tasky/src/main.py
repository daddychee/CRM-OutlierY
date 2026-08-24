# -*- coding: utf-8 -*-
"""TASKY (v3, :9117) — kế hoạch tuần của nhân sự.

Nghiệp vụ (FLOW-v3.md, Owner chốt 24/08/2026): Leader giao VIỆC tuần cho nhân sự →
nhân sự NHẬN việc rồi tự viết CHECKLIST cách mình sẽ triển khai → làm xong tick →
quản lý xem khối lượng + tỉ lệ hoàn thành. Không mục tiêu tầng trên, không trọng số.

Đúng khuôn hợp đồng app (theo video-review / to-chuc):

1. AUTH: app KHÔNG giữ sổ user — claims X-Remote-User/Level/Role/Dept từ gateway
   (an toàn vì app bind 127.0.0.1, header giả từ trình duyệt đã bị gateway vứt).
   Gate tính năng bằng cờ X-Remote-Actions (Permissions v2, FAIL-CLOSED):
   'giao_viec' (L3+) · 'xac_nhan_ket_qua' (L3+) · 'bao_cao_bo_phan' (L3+) ·
   'bao_cao_cong_ty' (L4+) · 'bao_cao_nhan_su' (L3+ bộ phận HCNS).
   Luật "level cao giao level thấp" KHÔNG nằm trong claims — app tự kiểm ở server
   bằng level+bộ phận hai người (FLOW-v3 §9.2), không tin dropdown của client.
2. DỮ LIỆU (Luật 6): data/tasky/db/tuan/YYYY-Www.json + nhat-ky.jsonl chỉ-thêm.
3. KHÔNG nối app khác (Luật 4 + FLOW-v3 §9.5): không đọc/ghi PlannerY. Chiều nối
   tương lai là Tasky → PlannerY, chưa làm; task chừa sẵn trường 'nguon_ngoai'.

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/tasky" --port 9117
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/tasky
ROOT = _APP_DIR.parents[1]                              # D:\AI AGENT OUTLIERY
# Luật 6: dữ liệu tách khỏi code. Đặt TRƯỚC khi import module đọc env.
os.environ.setdefault("TASKY_DIR", str(ROOT / "data" / "tasky" / "db"))

PHIEN_BAN = "0.2.0"
app = FastAPI(title="Tasky v3")
from src import tuan as tuan_lo  # noqa: E402 — lõi sổ tuần (đọc TASKY_DIR lúc gọi hàm)
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2

templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])


# ---------- claims (app không tự giữ user) ----------

def lay_user(x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
             x_remote_role: str = Header(""), x_remote_dept: str = Header(""),
             x_remote_name: str = Header("")) -> dict:
    """User = claims gateway tiêm. Dept/Name được proxy quote() (header phải ASCII)
    → unquote lại để so đúng CHUỖI GỐC tiếng Việt."""
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    try:
        level = int(x_remote_level or 0)
    except ValueError:
        level = 0
    return {"ten": x_remote_user, "level": level, "vai": x_remote_role,
            "bo_phan": unquote(x_remote_dept or ""),
            "ho_ten": unquote(x_remote_name or "")}


def cac_hanh_dong(x_remote_actions: str) -> set[str]:
    """Cờ hành động gateway phát (nen/common/proxy.py nối bằng dấu phẩy)."""
    return {s.strip() for s in (x_remote_actions or "").split(",") if s.strip()}


def _yeu_cau(ma: str, thong_bao: str):
    """Dựng dependency gate cho MỘT hành động — app CHỈ TIN CỜ gateway phát;
    thiếu header → fail-closed (403), không tự suy quyền từ level."""
    def _gate(user: dict = Depends(lay_user), x_remote_actions: str = Header("")) -> dict:
        if ma not in cac_hanh_dong(x_remote_actions):
            raise HTTPException(403, thong_bao)
        return user
    return _gate


yeu_cau_giao_viec = _yeu_cau("giao_viec", "Chỉ Leader trở lên mới giao được việc.")
yeu_cau_xac_nhan = _yeu_cau("xac_nhan_ket_qua", "Chỉ Leader trở lên mới xác nhận được việc.")
yeu_cau_bao_cao = _yeu_cau("bao_cao_bo_phan", "Báo cáo dành cho Leader trở lên.")


def _ma_tuan_hop_le(ma: str) -> str:
    """Tuần lấy từ query/form của client — mã sai hoặc rỗng thì về TUẦN NÀY chứ
    không nổ 500 (người dùng sửa URL không được làm hỏng trang)."""
    ma = (ma or "").strip()
    if not ma:
        return tuan_lo.ma_tuan()
    try:
        tuan_lo.khoang_tuan(ma)
    except ValueError:
        return tuan_lo.ma_tuan()
    return ma


# ---------- health (hợp đồng app) ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "tasky", "phien_ban": PHIEN_BAN}


# ---------- trang ----------

@app.get("/tasky", response_class=HTMLResponse)
def trang_viec(request: Request, user: dict = Depends(lay_user), tuan_xem: str = ""):
    """Việc của tôi — chỉ việc CỦA MÌNH (luật 1: lọc ở server, không ẩn nút)."""
    ma = _ma_tuan_hop_le(tuan_xem)
    ds = tuan_lo.viec_cua(ma, user["ten"])
    tu, den = tuan_lo.khoang_tuan(ma)
    return templates.TemplateResponse(request, "viec.html", {
        "user": user, "ma_tuan": ma, "tu": tu, "den": den,
        "viec_giao": [v for v in ds if v["nguon"] == "giao"],
        "viec_tu": [v for v in ds if v["nguon"] == "tu_them"],
        "tk": tuan_lo.thong_ke_nguoi(ma, user["ten"]),
        "loai_viec": tuan_lo.cac_loai_viec(),
        "tuan_truoc": tuan_lo.tuan_lien_ke(ma, -1),
        "tuan_sau": tuan_lo.tuan_lien_ke(ma, 1),
        "tuan_nay": tuan_lo.ma_tuan()})


# ---------- API (dưới /api-tasky: đường sâu dưới /tasky bị proxy viết lại) ----------

def _goi(ham, *a, **k):
    """Dịch lỗi nghiệp vụ sang HTTP: luật quyền → 403, dữ liệu sai → 400.
    Thông điệp của lõi là tiếng Việt cho người dùng đọc, đưa thẳng ra."""
    try:
        return {"ok": True, "du_lieu": ham(*a, **k)}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api-tasky/viec-tu")
def api_viec_tu(tieu_de: str = Form(...), loai_viec: str = Form(""),
                tuan_xem: str = Form(""), user: dict = Depends(lay_user)):
    return _goi(tuan_lo.them_viec_tu, _ma_tuan_hop_le(tuan_xem), user, tieu_de, loai_viec)


@app.post("/api-tasky/nhan")
def api_nhan(id: str = Form(...), tuan_xem: str = Form(""),
             user: dict = Depends(lay_user)):
    return _goi(tuan_lo.nhan_viec, _ma_tuan_hop_le(tuan_xem), id, user)


@app.post("/api-tasky/tu-choi")
def api_tu_choi(id: str = Form(...), ly_do: str = Form(""), tuan_xem: str = Form(""),
                user: dict = Depends(lay_user)):
    return _goi(tuan_lo.tu_choi_viec, _ma_tuan_hop_le(tuan_xem), id, user, ly_do)


@app.post("/api-tasky/buoc")
def api_them_buoc(id: str = Form(...), noi_dung: str = Form(...), tuan_xem: str = Form(""),
                  user: dict = Depends(lay_user)):
    return _goi(tuan_lo.them_buoc, _ma_tuan_hop_le(tuan_xem), id, user, noi_dung)


@app.post("/api-tasky/tick")
def api_tick(id: str = Form(...), buoc: str = Form(...), xong: str = Form("1"),
             tuan_xem: str = Form(""), user: dict = Depends(lay_user)):
    return _goi(tuan_lo.tick_buoc, _ma_tuan_hop_le(tuan_xem), id, buoc, user,
                xong not in ("0", "false", ""))


@app.post("/api-tasky/bao-xong")
def api_bao_xong(id: str = Form(...), tuan_xem: str = Form(""),
                 user: dict = Depends(lay_user)):
    return _goi(tuan_lo.bao_xong, _ma_tuan_hop_le(tuan_xem), id, user)
