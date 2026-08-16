# -*- coding: utf-8 -*-
"""GATEWAY — cổng vào duy nhất của OUTLIERY Platform v2 (:9000, sau Caddy :9443).

CHỈ làm việc của cổng: đăng nhập/session, menu app, proxy theo hợp đồng app, trang
sức khỏe, trang quản trị IAM. KHÔNG nghiệp vụ. Nguồn danh tính DUY NHẤT: iam.db
(P2) — không còn users.txt.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer

from nen.common.hop_dong import doc_hop_dong, tim_app
from nen.common.proxy import chuyen_tiep
from nen.iam import iam
from nen.ket_cau_hinh import ket

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Không có SESSION_SECRET trong .env → sinh tạm mỗi lần chạy (dev): restart là phải
# đăng nhập lại. Bản thay thế THẬT bắt buộc đặt trong .env (CAI-DAT lo).
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
COOKIE_TEN = "outliery_v2_phien"
PHIEN_TTL = 30 * 24 * 3600  # 30 ngày, như hệ cũ

app = FastAPI(title="OUTLIERY Gateway v2")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
# /static dùng chung cả hệ (font Inter/Space Grotesk, theme.js, markdown.js) —
# bản CHUẨN ở nen/gateway/static; app nào cần bản riêng thì khai /static trong
# tien_to như tri-thuc. Thiếu mount này là DA/to-chuc mất font (đo 16/08).
from fastapi.staticfiles import StaticFiles  # noqa: E402
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")),
          name="static")
_ky = URLSafeTimedSerializer(SESSION_SECRET, salt="phien-v2")


# ---------- session (nguồn user: iam.db, đọc SỐNG mỗi request) ----------

def user_hien_tai(request: Request) -> dict | None:
    ma = request.cookies.get(COOKIE_TEN)
    if not ma:
        return None
    try:
        ten = _ky.loads(ma, max_age=PHIEN_TTL)
    except BadSignature:
        return None
    conn = iam.ket_noi()
    try:
        tk = iam.lay_tai_khoan(conn, ten)
        if not tk or tk["khoa"]:
            return None  # user bị xóa/khóa → phiên chết theo (đọc sống)
        claims = iam.claims_cua(tk)
        claims["phai_doi_mk"] = bool(tk["phai_doi_mk"])
        return claims
    finally:
        conn.close()


def _ve_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def _kiem(request: Request) -> dict | RedirectResponse:
    """Đọc user; chưa đăng nhập → login; phải đổi mật khẩu → ép sang trang đổi."""
    user = user_hien_tai(request)
    if not user:
        return _ve_login()
    if user.get("phai_doi_mk") and request.url.path != "/doi-mat-khau":
        return RedirectResponse("/doi-mat-khau", status_code=303)
    return user


# ---------- routes chung ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "dich_vu": "gateway", "phien_ban": "2.0.0-p2"}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if user_hien_tai(request):
        return RedirectResponse("/", status_code=303)
    conn = iam.ket_noi()
    try:
        che_do_mo = iam.dem_tai_khoan(conn) == 0
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "login.html", {"loi": "", "che_do_mo": che_do_mo})


@app.post("/login", response_class=HTMLResponse)
def login_gui(request: Request, ten: str = Form(""), mat_khau: str = Form("")):
    """SYNC có chủ đích: bcrypt là CPU-bound — để async là block event loop, 50
    người login đồng thời làm cả cổng đứng (đo thật load test 16/08: trung vị
    44.6s/phiên → sửa xong đo lại phải <2s). FastAPI tự chạy route sync trong
    threadpool."""
    conn = iam.ket_noi()
    try:
        claims = iam.xac_thuc(conn, ten, mat_khau)
    finally:
        conn.close()
    if not claims:
        return templates.TemplateResponse(
            request, "login.html",
            {"loi": "Sai tên đăng nhập hoặc mật khẩu.", "che_do_mo": False},
            status_code=401)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE_TEN, _ky.dumps(claims["ten"]), max_age=PHIEN_TTL,
                    httponly=True, samesite="lax")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_TEN)
    return resp


@app.get("/doi-mat-khau", response_class=HTMLResponse)
def doi_mk_form(request: Request):
    user = user_hien_tai(request)
    if not user:
        return _ve_login()
    return templates.TemplateResponse(
        request, "doimatkhau.html", {"user": user, "loi": "", "xong": False})


@app.post("/doi-mat-khau", response_class=HTMLResponse)
def doi_mk_gui(request: Request, mk_moi: str = Form(""), mk_lai: str = Form("")):
    user = user_hien_tai(request)
    if not user:
        return _ve_login()
    if mk_moi != mk_lai:
        return templates.TemplateResponse(
            request, "doimatkhau.html",
            {"user": user, "loi": "Hai lần gõ không khớp.", "xong": False})
    conn = iam.ket_noi()
    try:
        iam.doi_mat_khau(conn, user, user["ten"], mk_moi, ep_doi_lan_sau=False)
    except iam.LoiIam as e:
        return templates.TemplateResponse(
            request, "doimatkhau.html", {"user": user, "loi": str(e), "xong": False})
    finally:
        conn.close()
    return RedirectResponse("/", status_code=303)


@app.get("/")
def trang_chu(request: Request):
    # UI_FLOW.md mục 1: đăng nhập xong vào THẲNG Hỏi–đáp như V1. Trang "bảng chọn
    # app" đã XÓA HẲN (Owner chốt 16/08) — mọi điều hướng qua sidebar.
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    return RedirectResponse("/app/tri-thuc/hoi-dap", status_code=303)


@app.get("/suc-khoe", response_class=HTMLResponse)
async def suc_khoe(request: Request):
    from starlette.concurrency import run_in_threadpool
    user = await run_in_threadpool(_kiem, request)   # sqlite không chạy trên loop
    if isinstance(user, RedirectResponse):
        return user
    import asyncio

    async def _kiem_mot_app(client, muc):   # tên KHÁC _kiem module-level (đã dính UnboundLocal)
        try:
            r = await client.get(f"http://127.0.0.1:{muc['cong']}{muc['health']}")
            return {"app": muc, "song": r.status_code == 200}
        except httpx.HTTPError:
            return {"app": muc, "song": False}

    async with httpx.AsyncClient(timeout=3.0) as client:
        ket_qua = list(await asyncio.gather(
            *(_kiem_mot_app(client, m) for m in doc_hop_dong())))
    return templates.TemplateResponse(
        request, "suckhoe.html", {"user": user, "ket_qua": ket_qua})


# ---------- trang quản trị IAM (giỏ ủy quyền: Owner + Admin ủy quyền) ----------

def _render_quan_tri(request: Request, user: dict, loi: str = "",
                     bao: str = "") -> HTMLResponse:
    conn = iam.ket_noi()
    try:
        return templates.TemplateResponse(
            request, "quantri.html",
            {"user": user, "loi": loi, "bao": bao,
             "tai_khoan": iam.liet_ke_tai_khoan(conn),
             "nguoi": iam.liet_ke_nguoi(conn),
             "nhat_ky": iam.doc_nhat_ky(conn, 30),
             "la_owner": user["level"] >= iam.OWNER_LEVEL})
    finally:
        conn.close()


def _yeu_cau_quan_tri(request: Request) -> dict | Response:
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    conn = iam.ket_noi()
    try:
        if not iam.co_quyen(user, "quan_tai_khoan", conn=conn):
            return Response("Bạn không có quyền vào trang quản trị.", status_code=403)
    finally:
        conn.close()
    return user


@app.get("/quan-tri", response_class=HTMLResponse)
def quan_tri(request: Request):
    user = _yeu_cau_quan_tri(request)
    if isinstance(user, Response):
        return user
    return _render_quan_tri(request, user)


@app.post("/quan-tri/tao-tai-khoan", response_class=HTMLResponse)
def qt_tao_tk(request: Request, ten: str = Form(""), mat_khau: str = Form(""),
                    bo_phan: str = Form(""), level: int = Form(1)):
    user = _yeu_cau_quan_tri(request)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        iam.tao_tai_khoan(conn, user, ten, mat_khau, bo_phan, level)
        return _render_quan_tri(request, user, bao=f"Đã tạo tài khoản {ten} "
                                "(bị ép đổi mật khẩu lần đăng nhập đầu).")
    except iam.LoiIam as e:
        return _render_quan_tri(request, user, loi=str(e))
    finally:
        conn.close()


@app.post("/quan-tri/sua", response_class=HTMLResponse)
def qt_sua(request: Request, ten: str = Form(...),
                 hanh_dong: str = Form(...), gia_tri: str = Form("")):
    user = _yeu_cau_quan_tri(request)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        if hanh_dong == "level":
            iam.sua_tai_khoan(conn, user, ten, level=int(gia_tri))
        elif hanh_dong == "bo_phan":
            iam.sua_tai_khoan(conn, user, ten, bo_phan=gia_tri)
        elif hanh_dong == "khoa":
            iam.sua_tai_khoan(conn, user, ten, khoa=(gia_tri == "1"))
        elif hanh_dong == "admin_uy_quyen":
            iam.sua_tai_khoan(conn, user, ten, admin_uy_quyen=(gia_tri == "1"))
        elif hanh_dong == "xoa":
            if gia_tri != ten:   # xác nhận 2 lớp: client gõ lại tên, SERVER kiểm
                return _render_quan_tri(request, user,
                                        loi="Muốn xóa phải gõ lại đúng tên tài khoản.")
            iam.xoa_tai_khoan(conn, user, ten)
        elif hanh_dong == "reset_mk":
            iam.doi_mat_khau(conn, user, ten, gia_tri, ep_doi_lan_sau=True)
        else:
            return _render_quan_tri(request, user, loi="Hành động lạ.")
        return _render_quan_tri(request, user, bao=f"Đã {hanh_dong}: {ten}")
    except iam.LoiIam as e:
        return _render_quan_tri(request, user, loi=str(e))
    finally:
        conn.close()


@app.post("/quan-tri/tao-nguoi", response_class=HTMLResponse)
def qt_tao_nguoi(request: Request, ho_ten: str = Form(""),
                       bo_phan: str = Form(""), vi_tri: str = Form("")):
    user = _yeu_cau_quan_tri(request)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        ns = iam.tao_nguoi(conn, user, ho_ten, bo_phan, vi_tri)
        return _render_quan_tri(request, user, bao=f"Đã tạo hồ sơ {ns['ma']}.")
    except iam.LoiIam as e:
        return _render_quan_tri(request, user, loi=str(e))
    finally:
        conn.close()


# ---------- két cấu hình (P3) ----------

@app.get("/api/cau-hinh/llm/{vai}")
def api_cau_hinh_llm(request: Request, vai: str):
    """App phụ (bind loopback) đọc cấu hình LLM theo vai — key KHÔNG bao giờ nằm
    trong file của app. CHỈ phục vụ loopback.

    ponytail: trần bảo vệ = mọi tiến trình local đọc được (cùng trust model
    X-Remote-User hiện tại); nâng cấp khi tách nhiều máy: token nội bộ."""
    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse({"loi": "chi loopback"}, status_code=403)
    conn = ket.ket_noi()
    try:
        return ket.cau_hinh_llm(conn, vai)
    finally:
        conn.close()


def _yeu_cau_owner_ket(request: Request) -> dict | Response:
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    if not iam.co_quyen(user, "ket_cau_hinh"):   # giỏ Owner tuyệt đối
        return Response("Két cấu hình chỉ dành cho Owner.", status_code=403)
    return user


@app.get("/cai-dat", response_class=HTMLResponse)
def cai_dat(request: Request, bao: str = "", loi: str = ""):
    user = _yeu_cau_owner_ket(request)
    if isinstance(user, Response):
        return user
    conn = ket.ket_noi()
    try:
        ds = ket.liet_ke(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "caidat.html", {"user": user, "ds": ds, "bao": bao, "loi": loi})


@app.post("/cai-dat/llm", response_class=HTMLResponse)
def cai_dat_llm(request: Request, vai: str = Form(...),
                      provider: str = Form(""), model: str = Form(""),
                      base_url: str = Form(""), api_key: str = Form("")):
    user = _yeu_cau_owner_ket(request)
    if isinstance(user, Response):
        return user
    vai = vai.strip().lower()
    if not vai.isidentifier():
        return RedirectResponse("/cai-dat?loi=T%C3%AAn+vai+kh%C3%B4ng+h%E1%BB%A3p+l%E1%BB%87",
                                status_code=303)
    conn = ket.ket_noi()
    try:
        for khoa, gt in (("provider", provider), ("model", model),
                         ("base_url", base_url)):
            if gt.strip():
                ket.dat_cau_hinh(conn, f"llm.{vai}.{khoa}", gt.strip())
        if api_key.strip():   # WRITE-ONLY: bỏ trống = giữ key cũ
            ket.dat_bi_mat(conn, f"llm.{vai}.api_key", api_key.strip())
    finally:
        conn.close()
    return RedirectResponse(f"/cai-dat?bao=%C4%90%C3%A3+l%C6%B0u+vai+{vai}",
                            status_code=303)


# ---------- cầu nối: hỏi số liệu (P6) ----------

@app.post("/api/cau-noi/hoi-so-lieu")
def api_hoi_so_lieu(request: Request, cau_hoi: str = Form(...)):
    """Router hỏi số liệu — danh bạ khớp kênh → connector đọc app sở hữu dữ liệu
    dưới danh nghĩa NGƯỜI HỎI. Nút 📊 của hỏi–đáp gọi vào đây.
    SYNC có chủ đích: connector dùng httpx sync — để async là block event loop
    (đo thật load test 16/08, cùng họ bug bcrypt-login)."""
    user = user_hien_tai(request)
    if not user:
        return JSONResponse({"loi": "chua dang nhap"}, status_code=401)
    from nen.common import cau_noi
    conn = iam.ket_noi()
    try:
        return cau_noi.hoi_so_lieu(cau_hoi, user, conn)
    finally:
        conn.close()


# ---------- proxy app ----------

@app.api_route("/app/{slug}/{duong_dan:path}",
               methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy_app(request: Request, slug: str, duong_dan: str):
    from starlette.concurrency import run_in_threadpool

    def _auth_va_quyen():
        """Gom mọi việc chạm sqlite/file vào MỘT lần xuống threadpool — proxy là
        route nóng nhất, tuyệt đối không block loop (đo thật load test 16/08)."""
        u = user_hien_tai(request)
        if not u:
            return None, None, False, []
        conn2 = iam.ket_noi()
        try:
            # Danh sách slug user được vào → claims X-Remote-Apps cho sidebar
            # (UI_FLOW.md mục 2). 'nas' là CỜ phụ: chỉ phát khi đã cấu hình
            # NAS_DUONG_DAN (luật V1: mục NAS ẩn tới khi cấu hình).
            duoc = [a["slug"] for a in doc_hop_dong()
                    if iam.co_quyen(u, "vao", a["slug"], conn2)]
            if "to-chuc" in duoc and os.getenv("NAS_DUONG_DAN", "").strip():
                duoc.append("nas")
            # Cờ 'quan-tri': ai mở được trang quản trị IAM (Owner / Admin ủy
            # quyền) thì sidebar mới hiện mục Nhân sự / User (UI_FLOW.md mục 2).
            if iam.co_quyen(u, "duyet_ho_so", conn=conn2) or \
               iam.co_quyen(u, "quan_tai_khoan", conn=conn2):
                duoc.append("quan-tri")
            return u, tim_app(slug), slug in duoc, duoc
        finally:
            conn2.close()

    user, muc, duoc_vao, apps_duoc_vao = await run_in_threadpool(_auth_va_quyen)
    if not user:
        if "text/html" in (request.headers.get("accept") or ""):
            return _ve_login()
        return JSONResponse({"loi": "chua dang nhap"}, status_code=401)
    if user.get("phai_doi_mk"):
        return RedirectResponse("/doi-mat-khau", status_code=303)
    if not muc:
        return Response("Không có app này.", status_code=404)
    if not duoc_vao:
        return Response("Bạn không có quyền vào công cụ này.", status_code=403)
    return await chuyen_tiep(
        request, cong=muc["cong"], goc=f"/app/{slug}", duong_dan=duong_dan,
        ten_user=user["ten"], tien_to_app=muc.get("tien_to", []),
        vai=iam.vai_cho_app(user, slug), level=user["level"],
        bo_phan=user.get("bo_phan", ""), apps_duoc_vao=apps_duoc_vao)
