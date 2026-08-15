# -*- coding: utf-8 -*-
"""GATEWAY — cổng vào duy nhất của OUTLIERY Platform v2 (:9000, sau Caddy :9443).

CHỈ làm việc của cổng: đăng nhập/session, menu app, proxy theo hợp đồng app, trang
sức khỏe hệ. KHÔNG nghiệp vụ. Mỏng đến mức cả năm không phải đụng — nâng cấp app
không bao giờ chết cổng (bài học agent-app cũ ôm cả cổng lẫn app).

P1 dùng users.txt tạm (khuôn hệ cũ: ten:bcrypt:bo_phan:level, đọc SỐNG mỗi request).
P2 (IAM) thay bằng iam.db + co_quyen() + vai theo bảng hanh_dong — các chỗ đánh dấu
`TODO-P2` là mối nối chờ.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import bcrypt
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer

from nen.common.hop_dong import doc_hop_dong, tim_app
from nen.common.proxy import chuyen_tiep

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Không có SESSION_SECRET trong .env → sinh tạm mỗi lần chạy (dev): restart là phải
# đăng nhập lại. Bản thay thế THẬT bắt buộc đặt trong .env (CAI-DAT lo).
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
COOKIE_TEN = "outliery_v2_phien"
PHIEN_TTL = 30 * 24 * 3600  # 30 ngày, như hệ cũ

app = FastAPI(title="OUTLIERY Gateway v2")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_ky = URLSafeTimedSerializer(SESSION_SECRET, salt="phien-v2")


# ---------- users tạm (TODO-P2: thay bằng iam.db) ----------

def _duong_users() -> Path:
    return Path(os.environ.get("NEN_USERS", ROOT / "data" / "nen" / "users.txt"))


def doc_users() -> dict[str, dict]:
    """Đọc SỐNG mỗi lần gọi (file nhỏ) — đổi user/khóa user ăn ngay không restart,
    đúng hành vi hệ cũ đã kiểm chứng (YC6)."""
    duong = _duong_users()
    if not duong.exists():
        return {}
    ket_qua: dict[str, dict] = {}
    for dong in duong.read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if not dong or dong.startswith("#"):
            continue
        phan = dong.split(":")
        if len(phan) < 4:
            continue
        ten, mk_hash, bo_phan, level = phan[0], phan[1], phan[2], phan[3]
        try:
            ket_qua[ten] = {"hash": mk_hash, "bo_phan": bo_phan, "level": int(level)}
        except ValueError:
            continue
    return ket_qua


def _vai_tam(level: int) -> str:
    """TODO-P2: vai thật tính từ bảng hanh_dong per app (apps_registry hệ cũ).
    P1 chỉ cần nhãn thô cho app-mau hiển thị."""
    return {5: "owner", 4: "manager", 3: "leader"}.get(level, "viewer")


# ---------- session ----------

def user_hien_tai(request: Request) -> dict | None:
    ma = request.cookies.get(COOKIE_TEN)
    if not ma:
        return None
    try:
        ten = _ky.loads(ma, max_age=PHIEN_TTL)
    except BadSignature:
        return None
    thong_tin = doc_users().get(ten)
    if not thong_tin:
        return None  # user bị xóa → phiên chết theo (đọc sống)
    return {"ten": ten, **thong_tin}


def _ve_login(request: Request) -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


# ---------- routes ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "dich_vu": "gateway", "phien_ban": "2.0.0-p1"}


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    if user_hien_tai(request):
        return RedirectResponse("/", status_code=303)
    che_do_mo = not doc_users()  # chưa có users.txt → hướng dẫn tạo, không khóa cửa chết
    return templates.TemplateResponse(
        request, "login.html", {"loi": "", "che_do_mo": che_do_mo})


@app.post("/login", response_class=HTMLResponse)
async def login_gui(request: Request, ten: str = Form(""), mat_khau: str = Form("")):
    thong_tin = doc_users().get(ten.strip())
    if not thong_tin or not bcrypt.checkpw(
            mat_khau.encode("utf-8"), thong_tin["hash"].encode("utf-8")):
        return templates.TemplateResponse(
            request, "login.html",
            {"loi": "Sai tên đăng nhập hoặc mật khẩu.", "che_do_mo": False},
            status_code=401)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE_TEN, _ky.dumps(ten.strip()), max_age=PHIEN_TTL,
                    httponly=True, samesite="lax")
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_TEN)
    return resp


@app.get("/", response_class=HTMLResponse)
async def trang_chu(request: Request):
    user = user_hien_tai(request)
    if not user:
        return _ve_login(request)
    # TODO-P2: lọc app theo quyền (co_quyen). P1: đăng nhập là thấy hết.
    return templates.TemplateResponse(
        request, "trangchu.html",
        {"user": user, "vai": _vai_tam(user["level"]), "apps": doc_hop_dong()})


@app.get("/suc-khoe", response_class=HTMLResponse)
async def suc_khoe(request: Request):
    user = user_hien_tai(request)
    if not user:
        return _ve_login(request)
    ket_qua = []
    async with httpx.AsyncClient(timeout=3.0) as client:
        for muc in doc_hop_dong():
            url = f"http://127.0.0.1:{muc['cong']}{muc['health']}"
            try:
                r = await client.get(url)
                song = r.status_code == 200
            except httpx.HTTPError:
                song = False
            ket_qua.append({"app": muc, "song": song})
    return templates.TemplateResponse(
        request, "suckhoe.html", {"user": user, "ket_qua": ket_qua})


@app.api_route("/app/{slug}/{duong_dan:path}",
               methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy_app(request: Request, slug: str, duong_dan: str):
    user = user_hien_tai(request)
    if not user:
        # API trả 401 gọn; trình duyệt về trang login
        if "text/html" in (request.headers.get("accept") or ""):
            return _ve_login(request)
        return JSONResponse({"loi": "chua dang nhap"}, status_code=401)
    muc = tim_app(slug)
    if not muc:
        return Response("Không có app này.", status_code=404)
    # TODO-P2: kiểm quyền vào app (co_quyen) trước khi chuyển tiếp.
    return await chuyen_tiep(
        request, cong=muc["cong"], goc=f"/app/{slug}", duong_dan=duong_dan,
        ten_user=user["ten"], tien_to_app=muc.get("tien_to", []),
        vai=_vai_tam(user["level"]), level=user["level"])
