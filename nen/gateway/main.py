# -*- coding: utf-8 -*-
"""GATEWAY — cổng vào duy nhất của OUTLIERY Platform v2 (:9000, sau Caddy :9443).

CHỈ làm việc của cổng: đăng nhập/session, menu app, proxy theo hợp đồng app, trang
sức khỏe, trang quản trị IAM. KHÔNG nghiệp vụ. Nguồn danh tính DUY NHẤT: iam.db
(P2) — không còn users.txt.
"""
from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse, Response)
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
# tien_to như ai-agent. Thiếu mount này là DA/to-chuc mất font (đo 16/08).
from fastapi.staticfiles import StaticFiles  # noqa: E402


class StaticCache(StaticFiles):
    """StaticFiles + Cache-Control. Thiếu header này là trình duyệt REVALIDATE font
    mỗi lần chuyển trang → trang vẽ bằng Segoe UI rồi mới swap sang Inter
    (font-display:swap) → cả app 'zoom nhẹ' mỗi điều hướng (Owner báo 16/08, đo
    bằng curl: response chỉ có ETag, không Cache-Control). Font/CSS font đổi cực
    hiếm → cache 30 ngày; còn lại (theme.js…) 10 phút là đủ tươi cho LAN."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        resp = super().file_response(full_path, stat_result, scope, status_code)
        duong = str(full_path)
        if duong.endswith((".woff2", ".woff")) or duong.endswith("fonts.css"):
            resp.headers["Cache-Control"] = "public, max-age=2592000"
        else:
            resp.headers["Cache-Control"] = "public, max-age=600"
        return resp


app.mount("/static", StaticCache(directory=str(Path(__file__).parent / "static")),
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
        # CẤP TRUY CẬP (acting — Permissions v2) áp MỘT chỗ ngay lúc dựng claims:
        # mọi kiểm quyền phía sau (gate nền + proxy app) tự ăn level hiệu lực.
        claims = iam.hieu_luc(iam.claims_cua(tk), conn)
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
            {"loi": "Wrong username or password.", "che_do_mo": False},
            status_code=401)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE_TEN, _ky.dumps(claims["ten"]), max_age=PHIEN_TTL,
                    httponly=True, samesite="lax", domain=_mien_cookie(request))
    return resp


def _mien_cookie(request: Request) -> str | None:
    """Vào bằng miền outliery.test → cookie đặt cấp miền CHA: một lần đăng nhập
    chạy mọi miền con (UI_FLOW.md mục 7). Vào bằng IP/localhost → cookie host-only
    như cũ (đặt domain là trình duyệt từ chối)."""
    host = request.url.hostname or ""
    if host == "outliery.test" or host.endswith(".outliery.test"):
        return ".outliery.test"
    return None


@app.get("/logout")
def logout(request: Request):
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_TEN)
    mien = _mien_cookie(request)
    if mien:   # cookie đặt kèm domain phải xóa kèm đúng domain đó
        resp.delete_cookie(COOKIE_TEN, domain=mien)
    return resp


# ---------- Profile (tự phục vụ — UI_FLOW.md mục 8) ----------

def _render_profile(request: Request, user: dict, loi: str = "",
                    bao: str = "") -> HTMLResponse:
    conn = iam.ket_noi()
    try:
        tk = iam.lay_tai_khoan(conn, user["ten"]) or {}
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "profile.html",
        {"user": user, "tk": tk, "loi": loi, "bao": bao,
         "rank": _TEN_LEVEL.get(user["level"], f"L{user['level']}")})


@app.get("/profile", response_class=HTMLResponse)
def profile_form(request: Request):
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    return _render_profile(request, user)


@app.post("/profile", response_class=HTMLResponse)
def profile_luu(request: Request, ten_hien_thi: str = Form(""),
                email: str = Form(""), dien_thoai: str = Form("")):
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    conn = iam.ket_noi()
    try:
        iam.sua_ho_so_ca_nhan(conn, user, ten_hien_thi, email, dien_thoai)
    finally:
        conn.close()
    return _render_profile(request, user, bao="Profile saved.")


@app.post("/profile/mat-khau", response_class=HTMLResponse)
def profile_doi_mk(request: Request, mk_hien_tai: str = Form(""),
                   mk_moi: str = Form(""), mk_lai: str = Form("")):
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    if mk_moi != mk_lai:
        return _render_profile(request, user, loi="New passwords do not match.")
    conn = iam.ket_noi()
    try:
        # Luật V1 (v2 từng thiếu): đổi mật khẩu CỦA MÌNH phải gõ mật khẩu hiện tại.
        iam.doi_mat_khau_ca_nhan(conn, user, mk_hien_tai, mk_moi)
    except iam.LoiIam as e:
        return _render_profile(request, user, loi=str(e))
    finally:
        conn.close()
    return _render_profile(request, user, bao="Password changed.")


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
            {"user": user, "loi": "Passwords do not match.", "xong": False})
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
async def trang_chu(request: Request):
    # UI_FLOW.md mục 1: đăng nhập xong vào THẲNG Hỏi–đáp như V1. Trang "bảng chọn
    # app" đã XÓA HẲN (Owner chốt 16/08) — mọi điều hướng qua sidebar.
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    # Miền quản trị (UI_FLOW.md mục 7): quantri.* vào thẳng khu nền.
    if (request.url.hostname or "").startswith("quantri."):
        return RedirectResponse("/general", status_code=303)
    # URL ĐẸP (Owner chốt 16/08, UI_FLOW.md mục 9): Home = "/" PHỤC VỤ thẳng trang
    # chat (không redirect sang /app/... nữa — thanh địa chỉ phải khớp nút bấm).
    return await proxy_app(request, "ai-agent", "hoi-dap")


# ---------- KHU QUẢN TRỊ NỀN (UI_FLOW.md mục 5 — mỗi trang MỘT việc) ----------

_TEN_LEVEL = {1: "Intern", 2: "Staff", 3: "Leader", 4: "Manager", 5: "Owner"}
# Giỏ ủy quyền = KHU CHỨC NĂNG (Permissions v2: nap_tai_lieu/duyet_qa/giam_sat đã
# về app ai-agent thành hành động thật). Mô tả mặc định phải nói đúng luật thật
# (nhan_su/ke_toan tính ở _gio_chuc_nang).
_NHAN_GIO = {"quan_tai_khoan": "Accounts admin", "duyet_ho_so": "Approve HR profiles",
             "nhan_su": "HR Hub", "ke_toan": "Finance Hub"}
_MAC_DINH_GIO = {"quan_tai_khoan": "Owner / Delegated admin",
                 "duyet_ho_so": "Owner / Delegated admin",
                 "nhan_su": "Owner / HR L3+ / Delegated admin",
                 "ke_toan": "Owner / Kế toán L2+"}

KE_TOAN_BO_PHAN = "Kế toán"


def _gio_chuc_nang(u: dict, conn) -> list[str]:
    """Cờ khu chức năng HR/Finance phát vào X-Remote-Apps (DE.md mục 10) — GATEWAY
    là nơi DUY NHẤT tính quyền hub; app to-chuc chỉ tin cờ (khuôn sb_ns/nas).

    KHÔNG đi qua iam.co_quyen cho 2 giỏ này: co_quyen xếp gio_uy_quyen mặc định
    chỉ Owner/admin_uy_quyen, còn luật hub có thêm vế BỘ PHẬN (HR L3+ / Kế toán
    L2+). Helper đọc thẳng Ô TICK (quyen_override — tick THẮNG luật mặc định,
    đúng lệ bảng phân quyền) rồi mới xét luật bộ phận."""
    def _tick(gio: str) -> bool | None:
        r = conn.execute(
            "SELECT cho_phep FROM quyen_override WHERE ten_tai_khoan=? "
            "AND app_slug='*' AND hanh_dong=?", (u["ten"], gio)).fetchone()
        return None if r is None else bool(r["cho_phep"])

    co: list[str] = []
    t = _tick("nhan_su")
    if t if t is not None else iam.quyen_nhan_su(u):
        co.append("hr")
    t = _tick("ke_toan")
    if t if t is not None else (
            u["level"] >= iam.OWNER_LEVEL
            or (u.get("bo_phan") == KE_TOAN_BO_PHAN and u["level"] >= 2)):
        co.append("finance")
    return co


def _gate_nen(request: Request, quyen: str | None = None,
              nhan_su: bool = False) -> dict | Response:
    """Cổng vào trang nền. Mặc định CHỈ Owner; quyen=<hành động> mở thêm theo
    co_quyen (giỏ ủy quyền/ô tick — mặc định tắt → hành vi = V1); nhan_su=True
    dùng luật Nhân sự V1 (Owner + HR L3+)."""
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    if user["level"] >= iam.OWNER_LEVEL:
        return user
    if nhan_su and iam.quyen_nhan_su(user):
        return user
    if quyen:
        conn = iam.ket_noi()
        try:
            if iam.co_quyen(user, quyen, conn=conn):
                return user
        finally:
            conn.close()
    return Response("You do not have access to this page.", status_code=403)


async def _do_dich_vu() -> list[dict]:
    """Sức khỏe từng dịch vụ: mọi app trong hợp đồng + Qdrant kho vector."""
    import asyncio

    async def _mot(client, ten, url):
        try:
            r = await client.get(url)
            return {"ten": ten, "song": r.status_code == 200}
        except httpx.HTTPError:
            return {"ten": ten, "song": False}

    qdrant = os.getenv("QDRANT_URL", "http://127.0.0.1:6343").rstrip("/")
    async with httpx.AsyncClient(timeout=3.0) as client:
        viec = [_mot(client, m["ten"], f"http://127.0.0.1:{m['cong']}{m['health']}")
                for m in doc_hop_dong()]
        viec.append(_mot(client, "Qdrant (kho vector)", qdrant + "/readyz"))
        return list(await asyncio.gather(*viec))


def _thong_ke_de() -> dict:
    """Đế đã nạp gì — số liệu THẬT đọc tại chỗ, nguồn chết thì None (không bịa 0)."""
    import datetime
    conn = iam.ket_noi()
    try:
        tk = iam.liet_ke_tai_khoan(conn)
        nguoi = iam.liet_ke_nguoi(conn)
    finally:
        conn.close()
    theo_level: dict[int, int] = {}
    for t in tk:
        theo_level[t["level"]] = theo_level.get(t["level"], 0) + 1
    kconn = ket.ket_noi()
    try:
        # Khối API Keys theo LOẠI (trang /general/api-keys thay AI Models tự chế)
        so_api: dict[str, int] = {}
        for k in ket.liet_ke_api_keys(kconn):
            so_api[k["loai"]] = so_api.get(k["loai"], 0) + 1
    finally:
        kconn.close()
    try:
        from nen.common import danh_ba
        so_thuc_the = len(danh_ba.liet_ke())
    except Exception:
        so_thuc_the = None
    bk_dir = Path(os.getenv("BACKUP_DIR", "D:/OUTLIERY-v2-backup"))
    backup_moi = None
    if bk_dir.exists():
        cac = sorted((d for d in bk_dir.iterdir() if d.is_dir()),
                     key=lambda d: d.stat().st_mtime)
        if cac:
            backup_moi = datetime.datetime.fromtimestamp(
                cac[-1].stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    return {"so_tai_khoan": len(tk), "theo_level": theo_level,
            "ten_level": _TEN_LEVEL, "so_ho_so": len(nguoi),
            "so_uy_quyen": sum(1 for t in tk if t["admin_uy_quyen"]),
            "so_api": so_api, "ten_loai_api": ket.TEN_LOAI_API,
            "so_thuc_the": so_thuc_the,
            "backup_moi": backup_moi, "bk_dir": str(bk_dir)}


@app.get("/general", response_class=HTMLResponse)
async def nen_tong_quan(request: Request):
    from starlette.concurrency import run_in_threadpool
    user = await run_in_threadpool(_gate_nen, request)
    if isinstance(user, Response):
        return user
    dich_vu = await _do_dich_vu()
    de = await run_in_threadpool(_thong_ke_de)
    return templates.TemplateResponse(
        request, "nen_tong_quan.html",
        {"user": user, "trang": "tong-quan", "dich_vu": dich_vu, **de})


# --- Tài khoản (tách từ /quan-tri cũ) ---

# HR HUB một cửa (Owner chốt 16/08, DE.md mục 10+12): form trong /hr POST THẲNG
# về các route General sẵn có kèm field ẩn `ve` (whitelist) — có ve hợp lệ thì
# xử lý xong 303 về /hr kèm bao/loi ngắn trên query để hub hiện thông báo;
# không có ve → render General như cũ (backend giữ nguyên, test cũ không vỡ).
_VE_HOP_LE = {"hr"}


def _ve_hub(tab: str, bao: str = "", loi: str = "") -> RedirectResponse:
    duong = f"/hr?tab={tab}"
    if bao:
        duong += "&bao=" + quote(bao)
    if loi:
        duong += "&loi=" + quote(loi)
    return RedirectResponse(duong, status_code=303)


def _render_tai_khoan(request: Request, user: dict, loi: str = "",
                      bao: str = "") -> HTMLResponse:
    conn = iam.ket_noi()
    try:
        return templates.TemplateResponse(
            request, "nen_tai_khoan.html",
            {"user": user, "trang": "tai-khoan", "loi": loi, "bao": bao,
             "tai_khoan": iam.liet_ke_tai_khoan(conn),
             "la_owner": user["level"] >= iam.OWNER_LEVEL})
    finally:
        conn.close()


@app.get("/general/accounts")
def nen_tai_khoan(request: Request):
    # Nghỉ hưu kiểu /quan-tri (Owner chốt 16/08): HR Hub tab Accounts là cửa mới.
    # POST /general/accounts/* GIỮ NGUYÊN — chúng là backend của hub.
    return RedirectResponse("/hr?tab=accounts", status_code=303)


@app.post("/general/accounts/create", response_class=HTMLResponse)
def nen_tk_tao(request: Request, ten: str = Form(""), mat_khau: str = Form(""),
               bo_phan: str = Form(""), level: int = Form(1), ve: str = Form("")):
    user = _gate_nen(request, quyen="quan_tai_khoan")
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        iam.tao_tai_khoan(conn, user, ten, mat_khau, bo_phan, level)
        bao = (f"Created account {ten} "
               "(must change password at first sign-in).")
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", bao=bao)
        return _render_tai_khoan(request, user, bao=bao)
    except iam.LoiIam as e:
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=str(e))
        return _render_tai_khoan(request, user, loi=str(e))
    finally:
        conn.close()


@app.post("/general/accounts/update", response_class=HTMLResponse)
def nen_tk_sua(request: Request, ten: str = Form(...),
               hanh_dong: str = Form(...), gia_tri: str = Form(""),
               ve: str = Form("")):
    user = _gate_nen(request, quyen="quan_tai_khoan")
    if isinstance(user, Response):
        return user

    def _loi(thong_diep: str):
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=thong_diep)
        return _render_tai_khoan(request, user, loi=thong_diep)

    conn = iam.ket_noi()
    try:
        if hanh_dong == "level":
            iam.sua_tai_khoan(conn, user, ten, level=int(gia_tri))
        elif hanh_dong == "bo_phan":
            iam.sua_tai_khoan(conn, user, ten, bo_phan=gia_tri)
        elif hanh_dong == "khoa":
            iam.sua_tai_khoan(conn, user, ten, khoa=(gia_tri == "1"))
        elif hanh_dong == "xoa":
            if gia_tri != ten:   # xác nhận 2 lớp: client gõ lại tên, SERVER kiểm
                return _loi("To delete, retype the exact account name.")
            iam.xoa_tai_khoan(conn, user, ten)
        elif hanh_dong == "reset_mk":
            iam.doi_mat_khau(conn, user, ten, gia_tri, ep_doi_lan_sau=True)
        else:
            return _loi("Unknown action.")
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", bao=f"Done {hanh_dong}: {ten}")
        return _render_tai_khoan(request, user, bao=f"Done {hanh_dong}: {ten}")
    except iam.LoiIam as e:
        return _loi(str(e))
    finally:
        conn.close()


# --- Nhân sự (Owner + HR L3+ — đúng V1, UI_FLOW.md mục 6) ---

def _render_nhan_su(request: Request, user: dict, loi: str = "",
                    bao: str = "") -> HTMLResponse:
    conn = iam.ket_noi()
    try:
        return templates.TemplateResponse(
            request, "nen_nhan_su.html",
            {"user": user, "trang": "nhan-su", "loi": loi, "bao": bao,
             "nguoi": iam.liet_ke_nguoi(conn)})
    finally:
        conn.close()


@app.get("/general/people")
def nen_nhan_su(request: Request):
    # Nghỉ hưu kiểu /quan-tri (Owner chốt 16/08): HR Hub tab Accounts là cửa mới
    # (People + Accounts đã GỘP MỘT — Owner chốt tiếp cùng ngày).
    # POST /general/people/* GIỮ NGUYÊN — chúng là backend của hub.
    return RedirectResponse("/hr?tab=accounts", status_code=303)


@app.post("/general/people/create", response_class=HTMLResponse)
def nen_ns_tao(request: Request, ho_ten: str = Form(""),
               bo_phan: str = Form(""), vi_tri: str = Form(""),
               ngay_sinh: str = Form(""), cccd: str = Form(""),
               dia_chi: str = Form(""), ngay_vao: str = Form(""),
               cap_bac: str = Form(""), ve: str = Form("")):
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        ns = iam.tao_nguoi(conn, user, ho_ten, bo_phan, vi_tri,
                           ngay_sinh=ngay_sinh, cccd=cccd, dia_chi=dia_chi,
                           ngay_vao=ngay_vao, cap_bac=cap_bac)
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", bao=f"Created profile {ns['ma']}.")
        return _render_nhan_su(request, user, bao=f"Created profile {ns['ma']}.")
    except iam.LoiIam as e:
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=str(e))
        return _render_nhan_su(request, user, loi=str(e))
    finally:
        conn.close()


@app.post("/general/people/update", response_class=HTMLResponse)
def nen_ns_sua(request: Request, ma: str = Form(...), ho_ten: str = Form(""),
               bo_phan: str = Form(""), vi_tri: str = Form(""),
               trang_thai: str = Form(""), ngay_sinh: str = Form(""),
               cccd: str = Form(""), dia_chi: str = Form(""),
               ngay_vao: str = Form(""), cap_bac: str = Form(""),
               ve: str = Form("")):
    """Sửa hồ sơ + đổi trạng thái (iam.sua_nguoi — trả nợ 'hồ sơ chỉ tạo được').
    KHÔNG có xóa hồ sơ: nghỉ việc = trang_thai 'nghi' (gỡ mềm). Trường bỏ trống =
    giữ nguyên — riêng CCCD nhờ vậy form không bao giờ phải render giá trị đầy đủ.
    Gate nhan_su=True như /general/people (Owner + HR L3+)."""
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        iam.sua_nguoi(conn, user, ma, ho_ten=ho_ten or None,
                      bo_phan=bo_phan or None, vi_tri=vi_tri or None,
                      trang_thai=trang_thai or None, ngay_sinh=ngay_sinh or None,
                      cccd=cccd or None, dia_chi=dia_chi or None,
                      ngay_vao=ngay_vao or None, cap_bac=cap_bac or None)
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", bao=f"Saved profile {ma}.")
        return _render_nhan_su(request, user, bao=f"Saved profile {ma}.")
    except iam.LoiIam as e:
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=str(e))
        return _render_nhan_su(request, user, loi=str(e))
    finally:
        conn.close()


# --- MỘT DÒNG = MỘT CON NGƯỜI (Owner gộp People+Accounts 16/08) ---

@app.post("/general/accounts/create-full", response_class=HTMLResponse)
def nen_tk_tao_tron(request: Request, ho_ten: str = Form(""), bo_phan: str = Form(""),
                    vi_tri: str = Form(""), ngay_sinh: str = Form(""),
                    cccd: str = Form(""), dia_chi: str = Form(""),
                    ngay_vao: str = Form(""), cap_bac: str = Form(""),
                    username: str = Form(""), mat_khau: str = Form(""),
                    level: int = Form(1), ve: str = Form("")):
    """Tạo MỘT CON NGƯỜI trọn gói: hồ sơ + tài khoản TÙY CHỌN nối nguoi_ma
    (username bỏ trống = chỉ hồ sơ). Trình tự chống mồ côi (bài học V2 GĐ2):
    kiểm quyền + username TRƯỚC → tạo nguoi → tạo tai_khoan (bộ phận LẤY TỪ HỒ SƠ,
    không nhận riêng) → lỗi tài khoản thì XÓA hồ sơ vừa tạo (rollback có vết)."""
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    username = username.strip()

    def _loi(thong_diep: str):
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=thong_diep)
        return _render_nhan_su(request, user, loi=thong_diep)

    conn = iam.ket_noi()
    try:
        if username and not iam.co_quyen(user, "quan_tai_khoan", conn=conn):
            return Response("Granting accounts requires the account-admin basket.",
                            status_code=403)
        if username and iam.lay_tai_khoan(conn, username):
            return _loi("Tên đăng nhập đã tồn tại.")
        ns = iam.tao_nguoi(conn, user, ho_ten, bo_phan, vi_tri,
                           ngay_sinh=ngay_sinh, cccd=cccd, dia_chi=dia_chi,
                           ngay_vao=ngay_vao, cap_bac=cap_bac)
        bao = f"Created profile {ns['ma']}."
        if username:
            try:
                iam.tao_tai_khoan(conn, user, username, mat_khau,
                                  ns["bo_phan"], level, nguoi_ma=ns["ma"])
                bao = f"Created profile {ns['ma']} + account {username}."
            except iam.LoiIam:
                with conn:   # rollback: không để hồ sơ mồ côi vừa tạo nửa chừng
                    conn.execute("DELETE FROM nguoi WHERE ma=?", (ns["ma"],))
                iam.ghi_nhat_ky(conn, user["ten"], "rollback_tao_nguoi",
                                f"{ns['ma']} vi loi cap tai khoan {username}")
                raise
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", bao=bao)
        return _render_nhan_su(request, user, bao=bao)
    except iam.LoiIam as e:
        return _loi(str(e))
    finally:
        conn.close()


@app.post("/general/accounts/grant", response_class=HTMLResponse)
def nen_tk_cap(request: Request, ma: str = Form(...), username: str = Form(...),
               mat_khau: str = Form(""), level: int = Form(1), ve: str = Form("")):
    """Cấp tài khoản cho HỒ SƠ CÓ SẴN — nối nguoi_ma, bộ phận LẤY TỪ HỒ SƠ; mỗi
    hồ sơ tối đa MỘT tài khoản. Gate quan_tai_khoan như mọi route accounts."""
    user = _gate_nen(request, quyen="quan_tai_khoan")
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        ns = conn.execute("SELECT * FROM nguoi WHERE ma=?", (ma,)).fetchone()
        if not ns:
            raise iam.LoiIam("Không có hồ sơ này.")
        da_co = conn.execute(
            "SELECT ten FROM tai_khoan WHERE nguoi_ma=?", (ma,)).fetchone()
        if da_co:
            raise iam.LoiIam(f"Hồ sơ này đã có tài khoản: {da_co['ten']}.")
        iam.tao_tai_khoan(conn, user, username.strip(), mat_khau,
                          ns["bo_phan"], level, nguoi_ma=ma)
        bao = f"Granted account {username.strip()} for {ma}."
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", bao=bao)
        return _render_tai_khoan(request, user, bao=bao)
    except iam.LoiIam as e:
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=str(e))
        return _render_tai_khoan(request, user, loi=str(e))
    finally:
        conn.close()


# --- Hồ sơ nhân sự: CCCD + tài liệu gốc (DE.md mục 12.1 — NHẠY CẢM, có vết) ---

_LOAI_TAI_LIEU = ("cccd", "syll", "khac")
_DUOI_TAI_LIEU = (".pdf", ".jpg", ".jpeg", ".png")
_TRAN_TAI_LIEU = 10 * 1024 * 1024


def _kho_tai_lieu_ns() -> Path:
    return Path(os.getenv("HO_SO_TAI_LIEU_DIR",
                          str(ROOT / "data" / "nen" / "ho-so-tai-lieu")))


@app.get("/general/people/cccd/{ma}")
def nen_ns_cccd(request: Request, ma: str):
    """Xem CCCD ĐẦY ĐỦ — app to-chuc chỉ render bản CHE, xem đủ phải qua đây:
    gate nhan_su + MỖI lượt xem một dòng nhat_ky_quyen (khuôn audit vault)."""
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        r = conn.execute("SELECT cccd FROM nguoi WHERE ma=?", (ma,)).fetchone()
        if not r:
            return Response("Not found.", status_code=404)
        iam.ghi_nhat_ky(conn, user["ten"], "xem_cccd", ma)
    finally:
        conn.close()
    return Response(r["cccd"] or "—", media_type="text/plain; charset=utf-8")


@app.post("/general/people/tai-lieu")
def nen_ns_tai_lieu(request: Request, ma: str = Form(...), loai: str = Form(...),
                    file: UploadFile = File(...), ve: str = Form("")):
    """Nộp tài liệu gốc hồ sơ (scan CCCD/SYLL/khác) vào kho
    data/nen/ho-so-tai-lieu/<mã NS>/ (du_lieu_nen VÀNG vĩnh viễn): whitelist đuôi,
    trần 10MB, tên lưu slug an toàn chống path traversal, KHÔNG ghi đè (hậu tố
    -2/-3 — bản cũ giữ nguyên), ghi nguyên tử tmp+os.replace, có vết nộp."""
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user

    def _loi(thong_diep: str):
        if ve in _VE_HOP_LE:
            return _ve_hub("accounts", loi=thong_diep)
        return Response(thong_diep, status_code=422)

    conn = iam.ket_noi()
    try:
        if not (re.fullmatch(r"NS-\d{3,}", ma)
                and conn.execute("SELECT 1 FROM nguoi WHERE ma=?", (ma,)).fetchone()):
            return _loi("Không có hồ sơ này.")
        if loai not in _LOAI_TAI_LIEU:
            return _loi("Loại tài liệu phải là: " + " / ".join(_LOAI_TAI_LIEU))
        goc = Path(file.filename or "tep").name
        duoi = Path(goc).suffix.lower()
        if duoi not in _DUOI_TAI_LIEU:
            return _loi("Chỉ nhận tệp: " + " ".join(_DUOI_TAI_LIEU))
        noi_dung = file.file.read(_TRAN_TAI_LIEU + 1)
        if len(noi_dung) > _TRAN_TAI_LIEU:
            return _loi("Tệp vượt trần 10MB.")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(goc).stem).strip("-") or "tep"
        thu_muc = _kho_tai_lieu_ns() / ma
        thu_muc.mkdir(parents=True, exist_ok=True)
        ten_luu, dem = f"{loai}_{stem}{duoi}", 2
        while (thu_muc / ten_luu).exists():
            ten_luu, dem = f"{loai}_{stem}-{dem}{duoi}", dem + 1
        tam = thu_muc / (ten_luu + ".tmp")
        tam.write_bytes(noi_dung)
        os.replace(tam, thu_muc / ten_luu)
        iam.ghi_nhat_ky(conn, user["ten"], "nop_tai_lieu_ns",
                        f"{ma} {loai} {ten_luu}")
    finally:
        conn.close()
    if ve in _VE_HOP_LE:
        return _ve_hub("accounts", bao=f"Uploaded {ten_luu} for {ma}.")
    return RedirectResponse("/hr?tab=people", status_code=303)


@app.get("/general/people/tai-lieu/{ma}/{ten}")
def nen_ns_tai_lieu_xem(request: Request, ma: str, ten: str):
    """Xem/tải một tài liệu hồ sơ — gate nhan_su, MỖI lượt xem có vết
    (nhạy cảm như CCCD); tên tệp/mã sai khuôn → 404 lặng lẽ (chống traversal)."""
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    if (not re.fullmatch(r"NS-\d{3,}", ma) or Path(ten).name != ten
            or ten.startswith(".")):
        return Response("Not found.", status_code=404)
    duong = _kho_tai_lieu_ns() / ma / ten
    if not duong.is_file():
        return Response("Not found.", status_code=404)
    conn = iam.ket_noi()
    try:
        iam.ghi_nhat_ky(conn, user["ten"], "xem_tai_lieu_ns", f"{ma} {ten}")
    finally:
        conn.close()
    return FileResponse(duong)


# --- Phân quyền v2 (chỉ Owner — giỏ tuyệt đối bang_phan_quyen; mockup P1-P5) ---

def _mo_ta_dieu_kien(dk: dict | None) -> str:
    """Mô tả luật mặc định một hành động cho UI — fail-closed = chỉ Owner."""
    if not dk:
        return "Owner only (L5)"
    if dk.get("min_level", 1) >= 5:
        return "Owner only (L5)"
    mota = f"L{dk.get('min_level', 1)}+"
    if dk.get("bo_phan"):
        mota += " · " + "/".join(dk["bo_phan"]) + " (L4+ any dept)"
    return mota


def _render_phan_quyen(request: Request, user: dict, ten: str = "",
                       loi: str = "", bao: str = "") -> HTMLResponse:
    luat = iam._luat()
    conn = iam.ket_noi()
    try:
        tai_khoan = iam.liet_ke_tai_khoan(conn)
        nguoi = {n["ma"]: n for n in iam.liet_ke_nguoi(conn)}
        chon = next((t for t in tai_khoan if t["ten"] == ten), None)
        acting = None
        apps_p2: list[dict] = []
        khoi_p4: list[dict] = []
        overrides: dict = {}
        if chon:
            claims_that = iam.claims_cua(chon)
            acting = iam.doc_cap_truy_cap(conn, ten)
            claims_hl = iam.hieu_luc(claims_that, conn)
            for r in conn.execute(
                    "SELECT * FROM quyen_override WHERE ten_tai_khoan=?", (ten,)):
                overrides[(r["app_slug"], r["hanh_dong"])] = dict(r)
            # P2 — MẶC ĐỊNH CHỈ ĐỌC per app (trên claims HIỆU LỰC)
            for a in doc_hop_dong():
                if a["slug"] == "app-mau":
                    continue
                vao = iam.co_quyen(claims_hl, "vao", a["slug"], conn)
                apps_p2.append({
                    "ten": a["ten"], "vao": vao,
                    "vai": iam.vai_cho_app(claims_hl, a["slug"], conn) if vao else "—",
                    "vi_sao": _mo_ta_dieu_kien(
                        (luat.get("apps", {}).get(a["slug"], {}) or {}).get("vao"))})
            co_hub = _gio_chuc_nang(claims_hl, conn)
            apps_p2.append({"ten": "HR Hub", "vao": "hr" in co_hub, "vai": "—",
                            "vi_sao": _MAC_DINH_GIO["nhan_su"]})
            apps_p2.append({"ten": "Finance Hub", "vao": "finance" in co_hub,
                            "vai": "—", "vi_sao": _MAC_DINH_GIO["ke_toan"]})
            # P4 — mỗi app một khối hành động thật (+ khối giỏ khu chức năng '*')
            for a in doc_hop_dong():
                cac_hd = iam.hanh_dong_cua_app(a["slug"])
                if not cac_hd:
                    continue
                hang = []
                for ma, dk in cac_hd.items():
                    ov = overrides.get((a["slug"], ma))
                    mac_dinh_that = iam.co_quyen(claims_that, ma, a["slug"], None)
                    hl = iam.co_quyen(claims_hl, ma, a["slug"], conn)
                    nguon = "override" if ov else \
                        ("acting" if acting and hl != mac_dinh_that else "default")
                    hang.append({"ma": ma, "nhan": dk.get("nhan", ma),
                                 "mo_ta": dk.get("mo_ta", ""),
                                 "mac_dinh": _mo_ta_dieu_kien(dk),
                                 "hieu_luc": hl, "nguon": nguon,
                                 "dat": "cho" if ov and ov["cho_phep"]
                                        else "chan" if ov else "ke_thua",
                                 "ly_do": ov["ly_do"] if ov else ""})
                khoi_p4.append({"slug": a["slug"], "ten": a["ten"], "hang": hang,
                                "so_le": sum(1 for h in hang if h["nguon"] == "override")})
            hang_gio = []
            for hd in luat.get("gio_uy_quyen", []):
                ov = overrides.get(("*", hd))
                if hd == "nhan_su":
                    hl = "hr" in co_hub
                elif hd == "ke_toan":
                    hl = "finance" in co_hub
                else:
                    hl = iam.co_quyen(claims_hl, hd, conn=conn)
                hang_gio.append({"ma": hd, "nhan": _NHAN_GIO.get(hd, hd), "mo_ta": "",
                                 "mac_dinh": _MAC_DINH_GIO.get(hd, "Owner / Delegated admin"),
                                 "hieu_luc": hl,
                                 "nguon": "override" if ov else "default",
                                 "dat": "cho" if ov and ov["cho_phep"]
                                        else "chan" if ov else "ke_thua",
                                 "ly_do": ov["ly_do"] if ov else ""})
            khoi_p4.append({"slug": "*", "ten": "Function hubs & baskets",
                            "hang": hang_gio,
                            "so_le": sum(1 for h in hang_gio if h["nguon"] == "override")})
        # P5 — sổ ngoại lệ TOÀN HỆ
        p5 = [dict(r) for r in conn.execute(
            "SELECT * FROM quyen_override ORDER BY ten_tai_khoan, app_slug, hanh_dong")]
    finally:
        conn.close()
    ten_app = {a["slug"]: a["ten"] for a in doc_hop_dong()} | {"*": "Platform"}
    nhan_hd = {(a["slug"], ma): dk.get("nhan", ma) for a in doc_hop_dong()
               for ma, dk in iam.hanh_dong_cua_app(a["slug"]).items()}
    nhan_hd |= {("*", hd): _NHAN_GIO.get(hd, hd) for hd in luat.get("gio_uy_quyen", [])}
    ho_ten_cua = {t["ten"]: (nguoi.get(t.get("nguoi_ma") or "", {}) or {}).get("ho_ten", "")
                  for t in tai_khoan}
    # KHÔNG BAO GIỜ cache: trang sửa liên tục (Owner nghi cache trình duyệt khi
    # thấy UI cũ) — no-store cho MỌI đường render (GET lẫn POST-lỗi trực tiếp).
    return templates.TemplateResponse(
        request, "nen_phan_quyen.html",
        {"user": user, "trang": "phan-quyen", "loi": loi, "bao": bao,
         "tai_khoan": tai_khoan, "ho_ten_cua": ho_ten_cua,
         "ten_chon": ten if chon else "", "chon": chon, "acting": acting,
         "apps_p2": apps_p2, "khoi_p4": khoi_p4, "p5": p5,
         "ten_app": ten_app, "nhan_hd": nhan_hd, "ten_level": _TEN_LEVEL},
        headers={"Cache-Control": "no-store"})


@app.get("/general/permissions", response_class=HTMLResponse)
def nen_phan_quyen(request: Request, ten: str = "", bao: str = "", loi: str = ""):
    user = _gate_nen(request, quyen="bang_phan_quyen")   # giỏ tuyệt đối = chỉ Owner
    if isinstance(user, Response):
        return user
    return _render_phan_quyen(request, user, ten=ten, bao=bao, loi=loi)


@app.post("/general/permissions/grant", response_class=HTMLResponse)
def nen_pq_gan(request: Request, ten: str = Form(...), app_slug: str = Form(...),
               hanh_dong: str = Form(...), gia_tri: str = Form(...),
               ly_do: str = Form("")):
    user = _gate_nen(request, quyen="bang_phan_quyen")
    if isinstance(user, Response):
        return user
    cho_phep = {"ke_thua": None, "cho": True, "chan": False}.get(gia_tri, None)
    conn = iam.ket_noi()
    try:
        iam.gan_override(conn, user, ten, app_slug, hanh_dong, cho_phep, ly_do)
        return _render_phan_quyen(request, user, ten=ten,
                                  bao=f"Set {app_slug}/{hanh_dong} = {gia_tri}")
    except iam.LoiIam as e:
        return _render_phan_quyen(request, user, ten=ten, loi=str(e))
    finally:
        conn.close()


@app.post("/general/permissions/save")
async def nen_pq_luu(request: Request):
    """Lưu MỘT LƯỢT các ô P4 của một người: chỉ áp Ô KHÁC hiện trạng (tick về
    kế thừa = gỡ lệ); đặt cho/chặn bắt buộc lý do (iam.gan_override chặn)."""
    from starlette.concurrency import run_in_threadpool
    form = await request.form()

    def _lam():
        user = _gate_nen(request, quyen="bang_phan_quyen")
        if isinstance(user, Response):
            return user
        ten = form.get("ten", "")
        conn = iam.ket_noi()
        try:
            hien = {(r["app_slug"], r["hanh_dong"]): bool(r["cho_phep"])
                    for r in conn.execute(
                        "SELECT * FROM quyen_override WHERE ten_tai_khoan=?", (ten,))}
            so_doi = 0
            for khoa in form.keys():
                if not khoa.startswith("dat__"):
                    continue
                _, app_slug, ma = khoa.split("__", 2)
                muon = {"ke_thua": None, "cho": True,
                        "chan": False}.get(form.get(khoa), None)
                co = (app_slug, ma) in hien
                if (muon is None and not co) or (co and hien[(app_slug, ma)] == muon):
                    continue                     # ô không đổi — bỏ qua
                iam.gan_override(conn, user, ten, app_slug, ma, muon,
                                 form.get(f"lydo__{app_slug}__{ma}", ""))
                so_doi += 1
        except iam.LoiIam as e:
            return RedirectResponse(
                f"/general/permissions?ten={ten}&loi=" + quote(str(e)), status_code=303)
        finally:
            conn.close()
        return RedirectResponse(
            f"/general/permissions?ten={ten}&bao=" + quote(f"Saved {so_doi} change(s)."),
            status_code=303)

    return await run_in_threadpool(_lam)


@app.post("/general/permissions/acting")
def nen_pq_acting(request: Request, ten: str = Form(...), cap: str = Form(""),
                  ly_do: str = Form("")):
    """P3 — cấp truy cập 1-4 (rỗng = về chức danh thật). Owner thật không hạ được."""
    user = _gate_nen(request, quyen="bang_phan_quyen")
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        iam.dat_cap_truy_cap(conn, user, ten, int(cap) if cap.strip() else None, ly_do)
        return _render_phan_quyen(request, user, ten=ten,
                                  bao=f"Acting level for {ten} = {cap or 'real level'}")
    except (iam.LoiIam, ValueError) as e:
        return _render_phan_quyen(request, user, ten=ten, loi=str(e))
    finally:
        conn.close()


@app.post("/general/permissions/delegate", response_class=HTMLResponse)
def nen_pq_uy_quyen(request: Request, ten: str = Form(...), bat: str = Form("0")):
    user = _gate_nen(request, quyen="bang_phan_quyen")
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        iam.sua_tai_khoan(conn, user, ten, admin_uy_quyen=(bat == "1"))
        return _render_phan_quyen(request, user, ten=ten,
                                  bao=f"Delegated admin for {ten} = {bat}")
    except iam.LoiIam as e:
        return _render_phan_quyen(request, user, ten=ten, loi=str(e))
    finally:
        conn.close()


# --- API Keys (két — chỉ Owner, giỏ tuyệt đối ket_cau_hinh) ---
# Trang theo mockup ĐÃ DUYỆT docs/mockup-de/api-keys.html (DE.md mục 12.3 + K5
# vòng 4): hiển thị THEO API (YouTube/LLM/VEO/Seedream), cấu hình theo app sinh
# từ viec_api trong HỢP ĐỒNG, quota log JSON-lines P4. Thay trang "AI Models"
# tự chế (chưa từng được Owner duyệt) — GET cũ redirect, POST llm cũ giữ làm
# backend fallback.
from nen.common import quota_log  # noqa: E402


def _viec_api_cua() -> dict[str, dict]:
    """{slug: {'ten': ..., 'viec': [...]}} từ hợp đồng — app không khai viec_api
    thì không hiện (K5 vòng 4: việc sinh từ TÍNH NĂNG THẬT, không bịa)."""
    return {a["slug"]: {"ten": a["ten"], "viec": a["viec_api"]}
            for a in doc_hop_dong() if a.get("viec_api")}


def _render_api_keys(request: Request, user: dict, bao: str = "",
                     loi: str = "") -> HTMLResponse:
    q = request.query_params
    conn = ket.ket_noi()
    try:
        di_tru = ket.di_tru_llm_cu(conn)   # idempotent — mục cũ giữ làm fallback
        ket.backfill_dau_khoa(conn)        # idempotent — khóa cũ chưa có 'dau'
        keys = ket.liet_ke_api_keys(conn)
        cap_phat = ket.doc_cap_phat(conn)
    finally:
        conn.close()
    if di_tru:                             # trả nợ audit két (DE.md 3b)
        iconn = iam.ket_noi()
        try:
            for m in di_tru:
                iam.ghi_nhat_ky(iconn, user["ten"], "api_key_di_tru",
                                f"{m['id']} tu llm.{m['vai']}.* ••••{m['duoi']}")
        finally:
            iconn.close()
    tab = q.get("tab", "api")
    if tab not in ("api", "app", "log"):
        tab = "api"
    theo_loai = {lo: [k for k in keys if k["loai"] == lo] for lo in ket.LOAI_API}
    dang_dung = {kid for cac_viec in cap_phat.values()
                 for muc in cac_viec.values() for kid in muc.get("khoa", [])}
    viec_api = _viec_api_cua()
    app_chon = q.get("app", "")
    if app_chon not in viec_api:
        app_chon = next(iter(viec_api), "")
    ngay = q.get("ngay", "")
    loc = {"api": q.get("loc_api", ""), "khoa": q.get("loc_khoa", ""),
           "app": q.get("loc_app", "")}
    log_rows = quota_log.doc(ngay, loc["api"], loc["khoa"], loc["app"]) \
        if tab == "log" else []
    from datetime import date as _date
    # Quota log chỉ ghi ĐUÔI (khuôn P4 cũ, không đổi schema log) — tra 'dau' để
    # hiển thị đồng bộ; khóa đã thu hồi thì không tra được, hiện đuôi trơn (đúng
    # — bí mật đã xóa hẳn khỏi két, không còn nguồn nào tính lại đầu).
    dau_theo_duoi = {k["duoi"]: k["dau"] for k in keys}
    # Loại API có NHIỀU NHÀ cung cấp (Owner chốt 17/08 — chọn nhà, không tự ấn
    # định): llm (claude/glm/gemini/chatgpt/deepseek) + generate (veo/seedream).
    # Template lặp {% for loai, ten in ten_loai.items() %} tra dict này để biết
    # loại nào cần nhóm theo nhà — thêm loại có nhà mới chỉ cần thêm một mục ở đây.
    nha_por_loai = {"llm": (ket.NHA_LLM, ket.NHA_LLM_INFO),
                    "generate": (ket.NHA_GEN, ket.NHA_GEN_INFO)}
    # Show-more SERVER-SIDE (18/08): JS ẩn/hiện cũ Owner báo không tác dụng trên
    # trình duyệt thật mà không tái hiện được — đổi sang server tự cắt danh sách
    # (>5 dòng render 5 + LINK GET thật), kiểm được 100% bằng TestClient.
    # LUẬT TRANG API (Owner chốt 18/08, ghi docs/UI.md): MỌI danh sách trên trang
    # mặc định 5 dòng + Show more/less — tab 1 mỗi KHỐI LOẠI một mã 'loai:<x>',
    # tab 2 mỗi việc một mã, tab 3 mã 'log' (URL giữ nguyên bộ lọc ngày/api/app).
    # ?mo_rong=<ma1,ma2> = các khối đang yêu cầu hiện ĐỦ; URL mở/gọn tính sẵn ở
    # Python từng mã (Jinja set-math rắc rối, không đáng).
    mo_rong = {x for x in q.get("mo_rong", "").split(",") if x}
    url_mo_rong = {}

    def _lam_url_mo(goc: str, ma: str) -> None:
        bot = ",".join(sorted(mo_rong - {ma}))
        url_mo_rong[ma] = {
            "mo": goc + "&mo_rong=" + ",".join(sorted(mo_rong | {ma})),
            "gon": goc + (f"&mo_rong={bot}" if bot else "")}

    if tab == "app" and app_chon in viec_api:
        for v in viec_api[app_chon]["viec"]:
            _lam_url_mo(f"/general/api-keys?tab=app&app={app_chon}", v["ma"])
    elif tab == "api":
        for lo in ket.LOAI_API:
            _lam_url_mo("/general/api-keys?tab=api", f"loai:{lo}")
    elif tab == "log":
        goc = "/general/api-keys?tab=log" + "".join(
            f"&{t}={quote(g)}" for t, g in
            (("ngay", ngay), ("loc_api", loc["api"]),
             ("loc_khoa", loc["khoa"]), ("loc_app", loc["app"])) if g)
        _lam_url_mo(goc, "log")
    # KHÔNG BAO GIỜ cache: trang sửa liên tục (Owner nghi cache trình duyệt khi
    # thấy UI cũ) — no-store cho MỌI đường render.
    return templates.TemplateResponse(request, "nen_api_keys.html", {
        "user": user, "trang": "api-keys", "tab": tab, "bao": bao, "loi": loi,
        "keys": keys, "theo_loai": theo_loai, "dang_dung": dang_dung,
        "dau_theo_duoi": dau_theo_duoi,
        "luot": quota_log.luot_hom_nay(), "cap_phat": cap_phat,
        "viec_api": viec_api, "app_chon": app_chon,
        "nha_llm": ket.NHA_LLM, "nha_info": ket.NHA_LLM_INFO,
        "nha_por_loai": nha_por_loai,
        "mo_rong": mo_rong, "url_mo_rong": url_mo_rong,
        "ten_loai": ket.TEN_LOAI_API, "model_goi_y": ket.MODEL_GOI_Y,
        "log_rows": log_rows, "ngay": ngay or _date.today().isoformat(),
        "loc": loc}, headers={"Cache-Control": "no-store"})


@app.get("/general/api-keys", response_class=HTMLResponse)
def nen_api_keys(request: Request, bao: str = "", loi: str = ""):
    user = _gate_nen(request, quyen="ket_cau_hinh")   # giỏ tuyệt đối = chỉ Owner
    if isinstance(user, Response):
        return user
    return _render_api_keys(request, user, bao=bao, loi=loi)


def _audit_api(user: dict, hanh_dong: str, chi_tiet: str) -> None:
    conn = iam.ket_noi()
    try:
        iam.ghi_nhat_ky(conn, user["ten"], hanh_dong, chi_tiet)
    finally:
        conn.close()


def _ve_api_keys(ve_tab: str = "", ve_app: str = "", ve_mo_rong: str = "",
                 bao: str = "", loi: str = "") -> RedirectResponse:
    """Redirect về ĐÚNG chỗ đang đứng trên trang API Keys. Owner phê lần 4
    (18/08): redirect trần mất tab/app/mo_rong — mọi thao tác đều bị ném về tab
    1 đầu trang. Mọi form mang hidden ve_tab/ve_app/ve_mo_rong (macro ve_fields
    trong template); param rỗng bị bỏ cho URL gọn."""
    phan = [p for p in (
        f"tab={quote(ve_tab)}" if ve_tab else "",
        f"app={quote(ve_app)}" if ve_app else "",
        f"mo_rong={quote(ve_mo_rong)}" if ve_mo_rong else "",
        "bao=" + quote(bao) if bao else "",
        "loi=" + quote(loi) if loi else "") if p]
    return RedirectResponse(
        "/general/api-keys" + ("?" + "&".join(phan) if phan else ""),
        status_code=303)


@app.post("/general/api-keys/add")
def nen_api_keys_them(request: Request, loai_chon: str = Form(...),
                      khoa: str = Form(...), model: str = Form(""),
                      ve_tab: str = Form(""), ve_app: str = Form(""),
                      ve_mo_rong: str = Form("")):
    """Thêm khóa: loai_chon = youtube | llm:<nhà> | generate:<nhà> | transcript.
    Ô khóa WRITE-ONLY — lưu xong không bao giờ render lại; audit chỉ ghi đuôi."""
    user = _gate_nen(request, quyen="ket_cau_hinh")
    if isinstance(user, Response):
        return user
    loai, _, nha = loai_chon.partition(":")
    conn = ket.ket_noi()
    try:
        kid = ket.them_api_key(conn, loai, khoa, nha=nha, model=model)
    except ValueError as e:
        return _ve_api_keys(ve_tab, ve_app, ve_mo_rong, loi=str(e))
    finally:
        conn.close()
    _audit_api(user, "api_key_them",
               f"{kid} {loai}{('/' + nha) if nha else ''} ••••{khoa.strip()[-4:]}")
    return _ve_api_keys(ve_tab, ve_app, ve_mo_rong,
                        bao=f"Added key {kid} (••••{khoa.strip()[-4:]}).")


@app.post("/general/api-keys/revoke")
def nen_api_keys_thu_hoi(request: Request, id: str = Form(...),
                         go_lai: str = Form(""), ve_tab: str = Form(""),
                         ve_app: str = Form(""), ve_mo_rong: str = Form("")):
    """Thu hồi có xác nhận (gõ lại ĐUÔI 4 trong MODAL): xóa bí mật + gỡ khỏi mọi
    cấp phát + vết audit; KHÔNG xóa lịch sử quota log."""
    user = _gate_nen(request, quyen="ket_cau_hinh")
    if isinstance(user, Response):
        return user
    conn = ket.ket_noi()
    try:
        muc = next((k for k in ket.liet_ke_api_keys(conn) if k["id"] == id), None)
        if not muc:
            return _ve_api_keys(ve_tab, ve_app, ve_mo_rong, loi="No such key.")
        if go_lai.strip() != muc["duoi"]:
            return _ve_api_keys(ve_tab, ve_app, ve_mo_rong,
                                loi="To revoke, retype the 4-char key tail.")
        ket.thu_hoi_api_key(conn, id)
    finally:
        conn.close()
    _audit_api(user, "api_key_thu_hoi", f"{id} ••••{muc['duoi']}")
    return _ve_api_keys(ve_tab, ve_app, ve_mo_rong,
                        bao=f"Revoked {id} (••••{muc['duoi']}).")


@app.post("/general/api-keys/model")
def nen_api_keys_model(request: Request, id: str = Form(...),
                       model: str = Form(""), ve_tab: str = Form(""),
                       ve_app: str = Form(""), ve_mo_rong: str = Form("")):
    user = _gate_nen(request, quyen="ket_cau_hinh")
    if isinstance(user, Response):
        return user
    conn = ket.ket_noi()
    try:
        if not ket.lay_cau_hinh(conn, f"api.{id}.loai"):
            return _ve_api_keys(ve_tab, ve_app, ve_mo_rong, loi="No such key.")
        ket.dat_cau_hinh(conn, f"api.{id}.model", model.strip())
    finally:
        conn.close()
    _audit_api(user, "api_key_model", f"{id} = {model.strip()}")
    return _ve_api_keys(ve_tab, ve_app, ve_mo_rong, bao=f"Model saved for {id}.")


@app.post("/general/api-keys/cap-phat")
def nen_api_keys_cap_phat(request: Request, app_slug: str = Form(...),
                          viec: str = Form(...), them: str = Form(""),
                          go: str = Form(""), che_do: str = Form(""),
                          model: str = Form(""), ve_tab: str = Form(""),
                          ve_app: str = Form(""), ve_mo_rong: str = Form("")):
    """MỘT route cho 3 thao tác của một VIỆC: + khóa (them) / gỡ × (go) / Lưu
    chế độ + model. Khóa thêm phải ĐÚNG LOẠI API của việc (theo hợp đồng)."""
    user = _gate_nen(request, quyen="ket_cau_hinh")
    if isinstance(user, Response):
        return user
    # form cũ (mở trước khi thêm ve_*) không mang field → giữ hành vi cũ tab app
    ve_tab, ve_app = ve_tab or "app", ve_app or app_slug
    viec_api = _viec_api_cua()
    muc_viec = next((v for v in viec_api.get(app_slug, {}).get("viec", [])
                     if v["ma"] == viec), None)
    if not muc_viec:
        return _ve_api_keys(ve_tab, ve_app, ve_mo_rong, loi="Unknown app task.")
    conn = ket.ket_noi()
    try:
        hien = ket.doc_cap_phat(conn).get(app_slug, {}).get(viec, {})
        ids = list(hien.get("khoa", []))
        if them:
            if ket.lay_cau_hinh(conn, f"api.{them}.loai") != muc_viec["loai"]:
                return _ve_api_keys(ve_tab, ve_app, ve_mo_rong,
                                    loi="Key type does not match this task.")
            if them not in ids:
                ids.append(them)
        if go:
            ids = [k for k in ids if k != go]
        muc = ket.luu_cap_phat_viec(conn, app_slug, viec, ids,
                                    che_do or hien.get("che_do", ""),
                                    model or hien.get("model", ""))
    finally:
        conn.close()
    _audit_api(user, "api_cap_phat",
               f"{app_slug}/{viec} = {muc['khoa']} {muc['che_do']}"
               + (f" model={muc['model']}" if muc.get("model") else ""))
    return _ve_api_keys(ve_tab, ve_app, ve_mo_rong, bao=f"Saved {viec}.")


@app.get("/general/api-keys/export")
def nen_api_keys_export(request: Request):
    user = _gate_nen(request, quyen="ket_cau_hinh")
    if isinstance(user, Response):
        return user
    q = request.query_params
    rows = quota_log.doc(q.get("ngay", ""), q.get("loc_api", ""),
                         q.get("loc_khoa", ""), q.get("loc_app", ""))
    import csv as _csv
    import io as _io
    dem = _io.StringIO()
    w = _csv.writer(dem)
    w.writerow(["luc", "api", "khoa_duoi", "app", "viec", "luot", "quota_tieu"])
    for d in rows:
        w.writerow([d.get("luc", ""), d.get("api", ""), d.get("khoa_duoi", ""),
                    d.get("app", ""), d.get("viec", ""), d.get("luot", 0),
                    d.get("quota_tieu", 0)])
    return Response("﻿" + dem.getvalue(),      # BOM cho Excel (lệ _catalog hệ cũ)
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             "attachment; filename=quota-log.csv"})


@app.get("/general/ai-models")
def nen_cau_hinh_cu():
    # Nghỉ hưu trang "AI Models" tự chế (vi phạm quy trình duyệt UI — Owner lệnh
    # 16/08 code lại theo mockup api-keys.html). POST /general/ai-models/llm GIỮ
    # làm backend fallback llm.<vai>.* cũ.
    return RedirectResponse("/general/api-keys", status_code=303)


@app.post("/general/ai-models/llm", response_class=HTMLResponse)
def nen_cau_hinh_llm(request: Request, vai: str = Form(...),
                     provider: str = Form(""), model: str = Form(""),
                     base_url: str = Form(""), api_key: str = Form("")):
    user = _gate_nen(request, quyen="ket_cau_hinh")
    if isinstance(user, Response):
        return user
    vai = vai.strip().lower()
    if not vai.isidentifier():
        return RedirectResponse(
            "/general/ai-models?loi=Invalid+role+name",
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
    return RedirectResponse(
        f"/general/ai-models?bao=Saved+role+{vai}", status_code=303)


# --- Dữ liệu & backup / Nhật ký / Ứng dụng ---

@app.get("/general/data-backup", response_class=HTMLResponse)
def nen_du_lieu(request: Request):
    import json
    user = _gate_nen(request)
    if isinstance(user, Response):
        return user
    raw = json.loads((ROOT / "nen" / "rules" / "apps.json")
                     .read_text(encoding="utf-8-sig"))
    khoi = []
    for chu, stores in [("Tầng nền", raw.get("du_lieu_nen", []))] + \
            [(a["ten"], a.get("du_lieu", [])) for a in raw.get("apps", [])]:
        for s in stores:
            duong = Path(s["duong"])
            if not duong.is_absolute():
                duong = ROOT / duong
            khoi.append({"chu": chu, **s, "co": duong.exists()})
    de = _thong_ke_de()
    return templates.TemplateResponse(
        request, "nen_du_lieu.html",
        {"user": user, "trang": "du-lieu", "khoi": khoi,
         "backup_moi": de["backup_moi"], "bk_dir": de["bk_dir"]})


@app.get("/general/audit-log", response_class=HTMLResponse)
def nen_nhat_ky(request: Request):
    user = _gate_nen(request)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        nk = iam.doc_nhat_ky(conn, 200)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "nen_nhat_ky.html",
        {"user": user, "trang": "nhat-ky", "nhat_ky": nk})


@app.get("/general/applications", response_class=HTMLResponse)
async def nen_ung_dung(request: Request):
    from starlette.concurrency import run_in_threadpool
    user = await run_in_threadpool(_gate_nen, request)
    if isinstance(user, Response):
        return user
    dich_vu = {d["ten"]: d["song"] for d in await _do_dich_vu()}
    return templates.TemplateResponse(
        request, "nen_ung_dung.html",
        {"user": user, "trang": "ung-dung", "apps": doc_hop_dong(),
         "dich_vu": dich_vu})


# ---------- DANH BẠ THỰC THỂ — Niches + Channels (Đ1 khối đế, DE.md) ----------
# Gate theo chốt Owner 16/08: Manager+ (L4) tạo/sửa vận hành; liên kết app +
# khai tử (gõ lại mã) chỉ Owner. Mọi thao tác ghi nhat_ky_quyen.
from nen.common import danh_ba  # noqa: E402

_LOAI_KENH = ("compilation", "narrator", "documentary", "tre_em", "tutorial", "giai_tri")
_APP_LIEN_KET = ("seo-optimize", "plannery", "radary", "niche-research", "speaky",
                 "content", "vox", "flowkit", "bao-cao")


def _gate_danh_ba(request: Request, chi_owner: bool = False):
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    if user["level"] < (5 if chi_owner else 4):
        return Response("Owner/Manager only.", status_code=403)
    return user


def _audit_danh_ba(user: dict, chi_tiet: str) -> None:
    conn = iam.ket_noi()
    try:
        iam.ghi_nhat_ky(conn, user["ten"], "danh_ba", chi_tiet)
    finally:
        conn.close()


def _ve_danh_ba(trang: str, ve_ma: str = "", ve_ngach: str = "",
                ve_trang_thai: str = "", bao: str = "",
                loi: str = "") -> RedirectResponse:
    """POST-REDIRECT-GET cho trang Channels/Niches (khuôn _ve_api_keys — Owner
    18/08 'đổi trạng thái kênh bị chuyển URL'): bản cũ POST render trực tiếp →
    URL trình duyệt kẹt ở đường POST, F5 là re-submit. Giờ 303 về GET sạch, giữ
    NGUYÊN vị trí (?ma= chi tiết kênh đang mở + bộ lọc ngach/trang_thai) + bao/
    loi; nhánh lỗi cũng redirect."""
    phan = [p for p in (
        f"ma={quote(ve_ma)}" if ve_ma else "",
        f"ngach={quote(ve_ngach)}" if ve_ngach else "",
        f"trang_thai={quote(ve_trang_thai)}" if ve_trang_thai else "",
        "bao=" + quote(bao) if bao else "",
        "loi=" + quote(loi) if loi else "") if p]
    return RedirectResponse(
        f"/general/{trang}" + ("?" + "&".join(phan) if phan else ""),
        status_code=303)


def _render_niches(request, user, bao="", loi=""):
    ds = danh_ba.doc_danh_muc()
    kenh = [t for t in ds if t["loai"] == "kenh"]
    # dict nằm trong cache module — copy trước khi gắn trường phụ kenh_con
    ngach = [dict(n, kenh_con=[k["ma"] for k in kenh if k["ngach_ma"] == n["ma"]])
             for n in ds if n["loai"] == "ngach"]
    # Cột "Channels" của bảng Markets (mockup M1) — đếm tại chỗ, không đổi dữ liệu.
    so_kenh_tt: dict[str, int] = {}
    for k in kenh:
        if k.get("thi_truong_ma"):
            so_kenh_tt[k["thi_truong_ma"]] = so_kenh_tt.get(k["thi_truong_ma"], 0) + 1
    return templates.TemplateResponse(request, "nen_niches.html", {
        "user": user, "trang": "niches", "la_owner": user["level"] >= 5,
        "ds_ngach": ngach, "ds_tt": [t for t in ds if t["loai"] == "thi_truong"],
        "so_kenh_tt": so_kenh_tt,
        "tt_ngach": danh_ba.TRANG_THAI_NGACH, "bao": bao, "loi": loi})


@app.get("/general/niches", response_class=HTMLResponse)
def nen_niches(request: Request, bao: str = "", loi: str = ""):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    return _render_niches(request, user, bao=bao, loi=loi)


@app.post("/general/niches/create")
def nen_niches_tao(request: Request, ten_chuan: str = Form(...),
                   trang_thai: str = Form("thu"), ghi_chu: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        ma = danh_ba.them_ngach(conn, ten_chuan, trang_thai, ghi_chu)
    except ValueError as e:
        return _ve_danh_ba("niches", loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"tao ngach {ma} ({ten_chuan})")
    return _ve_danh_ba("niches", bao=f"Created niche {ma}.")


@app.post("/general/niches/update")
def nen_niches_sua(request: Request, ma: str = Form(...), ten_chuan: str = Form(...),
                   trang_thai: str = Form("thu"), ghi_chu: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        danh_ba.sua_thuc_the(conn, "ngach", ma, ten_chuan=ten_chuan,
                             trang_thai=trang_thai, ghi_chu=ghi_chu)
    except ValueError as e:
        return _ve_danh_ba("niches", loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"sua ngach {ma}")
    return _ve_danh_ba("niches", bao=f"Saved {ma}.")


def _alias_chung(request, ma, bi_danh, viec, ve):
    """ve = callable(bao=…/loi=…) → RedirectResponse (PRG — khuôn _ve_danh_ba)."""
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        if viec == "them":
            danh_ba.them_bi_danh(conn, ma, bi_danh)
        else:
            danh_ba.xoa_bi_danh(conn, bi_danh)
    except ValueError as e:
        return ve(loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"alias {viec} '{bi_danh}' cho {ma}")
    return ve(bao=f"Alias updated for {ma}.")


@app.post("/general/niches/alias")
def nen_niches_alias(request: Request, ma: str = Form(...),
                     bi_danh: str = Form(...), viec: str = Form("them")):
    return _alias_chung(request, ma, bi_danh, viec,
                        lambda **kw: _ve_danh_ba("niches", **kw))


@app.post("/general/niches/link")
def nen_niches_link(request: Request, ma: str = Form(...), khoa: str = Form("")):
    user = _gate_danh_ba(request, chi_owner=True)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        danh_ba.dat_lien_ket(conn, ma, "niche-research", khoa)
    finally:
        conn.close()
    _audit_danh_ba(user, f"lien ket niche-research {ma} = '{khoa}'")
    return _ve_danh_ba("niches", bao=f"Linked {ma}.")


@app.post("/general/markets/create")
def nen_markets_tao(request: Request, ten: str = Form(...), ngon_ngu: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        ma = danh_ba.them_thi_truong(conn, ten, ngon_ngu)
    finally:
        conn.close()
    _audit_danh_ba(user, f"tao thi truong {ma}")
    return _ve_danh_ba("niches", bao=f"Created market {ma}.")


@app.post("/general/markets/update")
def nen_markets_sua(request: Request, ma: str = Form(...), ten: str = Form(...),
                    ngon_ngu: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        danh_ba.sua_thuc_the(conn, "thi_truong", ma, ten=ten, ngon_ngu=ngon_ngu)
    except ValueError as e:
        return _ve_danh_ba("niches", loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"sua thi truong {ma}")
    return _ve_danh_ba("niches", bao=f"Saved {ma}.")


def _render_channels(request, user, bao="", loi=""):
    ds = danh_ba.doc_danh_muc()
    ngach = [t for t in ds if t["loai"] == "ngach"]
    tt = [t for t in ds if t["loai"] == "thi_truong"]
    kenh = [t for t in ds if t["loai"] == "kenh"]
    loc_ngach = request.query_params.get("ngach", "")
    loc_tt = request.query_params.get("trang_thai", "")
    ds_kenh = [k for k in kenh
               if (not loc_ngach or k["ngach_ma"] == loc_ngach)
               and (not loc_tt or k["trang_thai"] == loc_tt)]
    ma_mo = request.query_params.get("ma", "")
    chi_tiet = next((k for k in kenh if k["ma"] == ma_mo), None)
    conn = iam.ket_noi()
    try:
        ds_nguoi = iam.liet_ke_nguoi(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "nen_channels.html", {
        "user": user, "trang": "channels", "la_owner": user["level"] >= 5,
        "ds_ngach": ngach, "ds_tt": tt, "ds_kenh": ds_kenh, "ds_kenh_moi": kenh,
        "chi_tiet": chi_tiet, "ds_loai": _LOAI_KENH, "ds_app": _APP_LIEN_KET,
        "ds_nguoi": ds_nguoi, "tt_kenh": danh_ba.TRANG_THAI_KENH,
        "ten_ngach": {n["ma"]: n["ten_chuan"] for n in ngach},
        "ten_tt": {m["ma"]: m["ten_chuan"] for m in tt},
        "loc_ngach": loc_ngach, "loc_tt": loc_tt, "bao": bao, "loi": loi})


@app.get("/general/channels", response_class=HTMLResponse)
def nen_channels(request: Request, bao: str = "", loi: str = ""):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    return _render_channels(request, user, bao=bao, loi=loi)


@app.get("/general/channels/export")
def nen_channels_export(request: Request):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    return Response(danh_ba.xuat_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             "attachment; filename=danh-ba.csv"})


@app.post("/general/channels/create")
def nen_channels_tao(request: Request, ten_chuan: str = Form(...),
                     ngach_ma: str = Form(...), thi_truong_ma: str = Form(""),
                     channel_id: str = Form(""), loai_kenh: str = Form(""),
                     kenh_goc_ma: str = Form(""), phu_trach: str = Form(""),
                     trang_thai: str = Form("uom_mam"), ve_ma: str = Form(""),
                     ve_ngach: str = Form(""), ve_trang_thai: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        ma = danh_ba.them_kenh(conn, ten_chuan, ngach_ma, thi_truong_ma,
                               channel_id, loai_kenh, trang_thai, kenh_goc_ma,
                               phu_trach, bo_phan_chu_quan=user.get("bo_phan", ""),
                               nguoi_tao=user["ten"])
    except Exception as e:
        return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai, loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"tao kenh {ma} ({ten_chuan})")
    # mở luôn chi tiết kênh vừa tạo (thay vì giữ ve_ma cũ — kênh mới là thứ
    # người tạo muốn thấy)
    return _ve_danh_ba("channels", ma, ve_ngach, ve_trang_thai,
                       bao=f"Created channel {ma}.")


@app.post("/general/channels/update")
def nen_channels_sua(request: Request, ma: str = Form(...), ten_chuan: str = Form(...),
                     channel_id: str = Form(""), ngach_ma: str = Form(...),
                     thi_truong_ma: str = Form(""), loai_kenh: str = Form(""),
                     kenh_goc_ma: str = Form(""), phu_trach: str = Form(""),
                     ghi_chu: str = Form(""), ve_ma: str = Form(""),
                     ve_ngach: str = Form(""), ve_trang_thai: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        danh_ba.sua_thuc_the(conn, "kenh", ma, ten_chuan=ten_chuan,
                             channel_id=channel_id, ngach_ma=ngach_ma,
                             thi_truong_ma=thi_truong_ma or None,
                             loai_kenh=loai_kenh, kenh_goc_ma=kenh_goc_ma or None,
                             phu_trach=phu_trach, ghi_chu=ghi_chu)
    except Exception as e:
        return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai, loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"sua kenh {ma}")
    return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai,
                       bao=f"Saved {ma}.")


@app.post("/general/channels/trang-thai")
def nen_channels_trang_thai(request: Request, ma: str = Form(...),
                            trang_thai: str = Form(...), ve_ma: str = Form(""),
                            ve_ngach: str = Form(""),
                            ve_trang_thai: str = Form("")):
    user = _gate_danh_ba(request)
    if not isinstance(user, dict):
        return user
    conn = danh_ba.ket_noi()
    try:
        danh_ba.doi_trang_thai_kenh(conn, ma, trang_thai)
    except ValueError as e:
        return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai, loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"kenh {ma} -> {trang_thai}")
    return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai,
                       bao=f"{ma} → {trang_thai}.")


@app.post("/general/channels/alias")
def nen_channels_alias(request: Request, ma: str = Form(...),
                       bi_danh: str = Form(...), viec: str = Form("them"),
                       ve_ma: str = Form(""), ve_ngach: str = Form(""),
                       ve_trang_thai: str = Form("")):
    return _alias_chung(request, ma, bi_danh, viec,
                        lambda **kw: _ve_danh_ba("channels", ve_ma, ve_ngach,
                                                 ve_trang_thai, **kw))


@app.post("/general/channels/link")
def nen_channels_link(request: Request, ma: str = Form(...),
                      app_slug: str = Form(...), khoa: str = Form(""),
                      ve_ma: str = Form(""), ve_ngach: str = Form(""),
                      ve_trang_thai: str = Form("")):
    user = _gate_danh_ba(request, chi_owner=True)
    if not isinstance(user, dict):
        return user
    if app_slug not in _APP_LIEN_KET:
        return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai,
                           loi="Unknown app.")
    conn = danh_ba.ket_noi()
    try:
        danh_ba.dat_lien_ket(conn, ma, app_slug, khoa)
    finally:
        conn.close()
    _audit_danh_ba(user, f"lien ket {app_slug} {ma} = '{khoa}'")
    return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai,
                       bao=f"Linked {ma}.")


@app.post("/general/channels/khai-tu")
def nen_channels_khai_tu(request: Request, ma: str = Form(...),
                         go_lai: str = Form(""), ve_ma: str = Form(""),
                         ve_ngach: str = Form(""),
                         ve_trang_thai: str = Form("")):
    user = _gate_danh_ba(request, chi_owner=True)
    if not isinstance(user, dict):
        return user
    if go_lai.strip() != ma:
        return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai,
                           loi="Retype the exact channel code to retire.")
    conn = danh_ba.ket_noi()
    try:
        danh_ba.khai_tu_kenh(conn, ma)
    except ValueError as e:
        return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai, loi=str(e))
    finally:
        conn.close()
    _audit_danh_ba(user, f"KHAI TU kenh {ma}")
    # kênh đã khai tử vẫn xem được chi tiết (read-only) — giữ vị trí
    return _ve_danh_ba("channels", ve_ma, ve_ngach, ve_trang_thai,
                       bao=f"Retired {ma}.")


# --- Trang cũ nghỉ hưu → redirect (giữ 1 nhịp chuyển tiếp, UI_FLOW.md mục 5) ---

@app.get("/suc-khoe")
def suc_khoe_cu():
    return RedirectResponse("/general", status_code=303)


@app.get("/quan-tri")
def quan_tri_cu():
    return RedirectResponse("/general/accounts", status_code=303)


# ---------- két cấu hình (P3) ----------

@app.get("/api/cau-hinh/llm/{vai}")
def api_cau_hinh_llm(request: Request, vai: str, app: str = "ai-agent"):
    """App phụ (bind loopback) đọc cấu hình LLM theo APP + VIỆC — key KHÔNG bao
    giờ nằm trong file của app. CHỈ phục vụ loopback. Query ?app= (mặc định
    ai-agent — tương thích ngược caller cũ quên truyền; 2 caller thật đều truyền
    tường minh sau bug data-analytics mượn nhầm khóa Writer ai-agent 18/08).

    ponytail: trần bảo vệ = mọi tiến trình local đọc được (cùng trust model
    X-Remote-User hiện tại); nâng cấp khi tách nhiều máy: token nội bộ."""
    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse({"loi": "chi loopback"}, status_code=403)
    conn = ket.ket_noi()
    try:
        return ket.cau_hinh_llm(conn, app, vai)
    finally:
        conn.close()


@app.get("/api/cau-hinh/api-khoa/{app_slug}")
def api_cau_hinh_api_khoa(request: Request, app_slug: str):
    """App phụ (bind loopback) lấy KHÓA ĐƯỢC CẤP PHÁT theo VIỆC từ két (trang API
    Keys — làm gọn RadarY 16/08: nguồn khóa duy nhất, bảng nội bộ app nghỉ).
    Trả {viec: {khoa: [{id, key, loai, nha}], che_do, model}} — key plaintext cho
    app DÙNG, TUYỆT ĐỐI không log giá trị. CHỈ phục vụ loopback (khuôn llm/{vai})."""
    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse({"loi": "chi loopback"}, status_code=403)
    conn = ket.ket_noi()
    try:
        ra = {}
        for viec, muc in ket.doc_cap_phat(conn).get(app_slug, {}).items():
            khoa = []
            for kid in muc.get("khoa", []):
                gia_tri = ket.lay_bi_mat(conn, f"api.{kid}.key")
                if gia_tri:
                    khoa.append({"id": kid, "key": gia_tri,
                                 "loai": ket.lay_cau_hinh(conn, f"api.{kid}.loai"),
                                 "nha": ket.lay_cau_hinh(conn, f"api.{kid}.nha")})
            ra[viec] = {"khoa": khoa, "che_do": muc.get("che_do", "mot_khoa"),
                        "model": muc.get("model", "")}
        return ra
    finally:
        conn.close()


@app.get("/cai-dat")
def cai_dat_cu():
    return RedirectResponse("/general/api-keys", status_code=303)


# Khu nền đổi URL /nen/* → /general/* EN (Owner 16/08, UI_FLOW.md mục 9 — URL khớp
# nhãn tab). Đường cũ redirect trọn bộ: GET 303, POST 307 (giữ method+body cho form
# mở sẵn từ trước khi đổi).
_NEN_CU = {
    "": "/general",
    "/tai-khoan": "/general/accounts",
    "/tai-khoan/tao": "/general/accounts/create",
    "/tai-khoan/sua": "/general/accounts/update",
    "/nhan-su": "/general/people",
    "/nhan-su/tao": "/general/people/create",
    "/phan-quyen": "/general/permissions",
    "/phan-quyen/gan": "/general/permissions/grant",
    "/phan-quyen/uy-quyen": "/general/permissions/delegate",
    "/cau-hinh": "/general/api-keys",
    "/cau-hinh/llm": "/general/ai-models/llm",
    "/du-lieu": "/general/data-backup",
    "/nhat-ky": "/general/audit-log",
    "/ung-dung": "/general/applications",
}


@app.api_route("/nen{duong:path}", methods=["GET", "POST"])
def nen_cu(request: Request, duong: str):
    moi = _NEN_CU.get(duong, "/general")
    if request.url.query:
        moi += "?" + request.url.query
    return RedirectResponse(moi, status_code=307 if request.method == "POST" else 303)


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

# --- URL ĐẸP cấp 1 (Owner chốt 16/08/2026, UI_FLOW.md mục 9) ---
# Thanh địa chỉ khớp nút bấm: alias cấp-1 PHỤC VỤ thẳng trang (URL giữ nguyên),
# URL /app/... cũ của đúng các TRANG này 303 về alias. Route con (form/API/stream)
# vẫn đi /app/<slug>/... như cũ — không đổi hợp đồng app.
_ALIAS: dict[str, tuple[str, str]] = {
    "/input": ("ai-agent", ""),
    "/library": ("ai-agent", "kho-tai-lieu"),
    "/gap": ("ai-agent", "kho-thieu"),
    "/history": ("ai-agent", "lich-su"),
    "/tracking": ("ai-agent", "giam-sat"),
    "/data-analytics": ("data-analytics", "chan-doan"),
    "/nas": ("to-chuc", "nas"),
    "/kpi": ("to-chuc", "kpi"),
    "/vault": ("to-chuc", "vault"),
    "/hr": ("to-chuc", "hr"),
    "/finance": ("to-chuc", "finance"),
}
# (slug, duong_dan) → URL đẹp; Home "/" phục vụ hoi-dap ở trang_chu.
_ALIAS_NGUOC = {v: k for k, v in _ALIAS.items()} | {("ai-agent", "hoi-dap"): "/"}
# Đường alias trùng mặt chữ tien_to (vd /nas của to-chuc) không bị proxy viết lại
# thành /app/... — xem viet_lai_duong_dan(bo_qua=).
_ALIAS_BO_QUA = tuple(_ALIAS)


@app.api_route("/app/{slug}/{duong_dan:path}",
               methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy_app(request: Request, slug: str, duong_dan: str):
    from starlette.concurrency import run_in_threadpool

    # Slug cũ nghỉ hưu (Owner chốt 16/08: app này tên là AI AGENT từ đầu,
    # "tri-thuc" là tên kỹ thuật tự chế khi di trú) — đỡ URL/fetch cũ không vỡ.
    if slug == "tri-thuc":
        slug = "ai-agent"

    # Trang có URL đẹp mà bị mở bằng đường /app/... cũ → 303 về URL đẹp (chỉ
    # điều hướng HTML thật; fetch/stream/form giữ nguyên đường cũ).
    if (request.method in ("GET", "HEAD")
            and request.url.path.startswith("/app/")
            and "text/html" in (request.headers.get("accept") or "")
            and (slug, duong_dan) in _ALIAS_NGUOC):
        dich = _ALIAS_NGUOC[(slug, duong_dan)]
        if request.url.query:
            dich += "?" + request.url.query
        return RedirectResponse(dich, status_code=303)

    def _auth_va_quyen():
        """Gom mọi việc chạm sqlite/file vào MỘT lần xuống threadpool — proxy là
        route nóng nhất, tuyệt đối không block loop (đo thật load test 16/08)."""
        u = user_hien_tai(request)
        if not u:
            return None, None, False, [], "", []
        conn2 = iam.ket_noi()
        try:
            # Danh sách slug user được vào → claims X-Remote-Apps cho sidebar
            # (UI_FLOW.md mục 2). 'nas' là CỜ phụ: chỉ phát khi đã cấu hình
            # NAS_DUONG_DAN (luật V1: mục NAS ẩn tới khi cấu hình).
            duoc = [a["slug"] for a in doc_hop_dong()
                    if iam.co_quyen(u, "vao", a["slug"], conn2)]
            if "to-chuc" in duoc and os.getenv("NAS_DUONG_DAN", "").strip():
                duoc.append("nas")
            # Cờ 'quan-tri': ai mở được mục Nhân sự/User trên sidebar — luật V1:
            # Owner + HR L3+ (iam.quyen_nhan_su) hoặc Admin ủy quyền tài khoản.
            quan_tk = iam.co_quyen(u, "quan_tai_khoan", conn=conn2)
            if iam.quyen_nhan_su(u) or quan_tk:
                duoc.append("quan-tri")
            # Cờ khu chức năng 'hr'/'finance' (DE.md mục 10) — chỉ khi vào được
            # to-chuc (hub sống trong app đó); app CHỈ TIN cờ này, không tự tính.
            # Cờ 'accounts': tab Accounts trong HR Hub (một cửa nhân sự 16/08) —
            # giỏ ủy quyền quan_tai_khoan sẵn có (mặc định Owner/Admin ủy quyền);
            # người không cờ KHÔNG thấy tab, backend /general/accounts/* vẫn tự gate.
            if "to-chuc" in duoc:
                duoc += _gio_chuc_nang(u, conn2)
                if quan_tk:
                    duoc.append("accounts")
            # Permissions v2: vai dịch từ hành động + danh sách hành động được
            # phép của app đang vào (X-Remote-Actions) — tính TRONG threadpool
            # vì cần conn (ô tick lẻ thắng mặc định).
            vai = iam.vai_cho_app(u, slug, conn2)
            hanh_dong = iam.cac_hanh_dong(u, slug, conn2)
            return u, tim_app(slug), slug in duoc, duoc, vai, hanh_dong
        finally:
            conn2.close()

    user, muc, duoc_vao, apps_duoc_vao, vai, hanh_dong = \
        await run_in_threadpool(_auth_va_quyen)
    if not user:
        if "text/html" in (request.headers.get("accept") or ""):
            return _ve_login()
        return JSONResponse({"loi": "chua dang nhap"}, status_code=401)
    if user.get("phai_doi_mk"):
        return RedirectResponse("/doi-mat-khau", status_code=303)
    if not muc:
        return Response("No such app.", status_code=404)
    if not duoc_vao:
        return Response("You do not have access to this tool.", status_code=403)
    return await chuyen_tiep(
        request, cong=muc["cong"], goc=f"/app/{slug}", duong_dan=duong_dan,
        ten_user=user["ten"], tien_to_app=muc.get("tien_to", []),
        vai=vai, level=user["level"],
        bo_phan=user.get("bo_phan", ""), apps_duoc_vao=apps_duoc_vao,
        ten_hien_thi=user.get("ten_hien_thi", ""), bo_qua=_ALIAS_BO_QUA,
        hanh_dong=hanh_dong, khung=muc.get("giao_dien") == "khung")


# ---------- KHUNG MỞ APP GIỮ SIDEBAR (Owner 16/08: "mở app vẫn còn sidebar") ----------

@app.get("/open/{slug}", response_class=HTMLResponse)
def mo_app_khung(request: Request, slug: str):
    """App NGOÀI (hợp đồng khai giao_dien 'khung' — SPA tự render trọn trang) mở
    trong khung OUTLIERY: sidebar + topbar chuẩn, nội dung là MỘT iframe
    /app/<slug>/ (cùng origin — cookie/back trình duyệt tự ăn). Gate Y HỆT cửa
    vào app; app native / slug lạ → 404. /app/<slug> trực tiếp vẫn sống nguyên
    (bookmark cũ, không redirect — tránh vòng lặp iframe)."""
    user = _kiem(request)
    if isinstance(user, RedirectResponse):
        return user
    muc = tim_app(slug)
    if not muc or muc.get("giao_dien") != "khung":
        return Response("Not found.", status_code=404)
    conn = iam.ket_noi()
    try:
        if not iam.co_quyen(user, "vao", slug, conn):
            return Response("You do not have access to this tool.", status_code=403)
        duoc = [a["slug"] for a in doc_hop_dong()
                if iam.co_quyen(user, "vao", a["slug"], conn)]
        co_nas = "to-chuc" in duoc and bool(os.getenv("NAS_DUONG_DAN", "").strip())
        co_hub = _gio_chuc_nang(user, conn) if "to-chuc" in duoc else []
        quan_tri = iam.quyen_nhan_su(user) or iam.co_quyen(user, "quan_tai_khoan", conn=conn)
    finally:
        conn.close()
    from nen.common.sidebar import KHONG_LAP_TOOLS
    ds_tools = [{"slug": a["slug"], "ten": a["ten"],
                 "href": (f"/open/{a['slug']}" if a.get("giao_dien") == "khung"
                          else f"/app/{a['slug']}")}
                for a in doc_hop_dong()
                if a["slug"] in duoc and a["slug"] not in KHONG_LAP_TOOLS]
    from datetime import datetime as _dt
    return templates.TemplateResponse(request, "nen_khung_app.html", {
        "user": user, "app": muc, "ds_tools": ds_tools,
        "sb_da": "data-analytics" in duoc, "sb_nas": co_nas,
        "sb_hr": "hr" in co_hub, "sb_fin": "finance" in co_hub,
        "sb_ns": quan_tri, "la_owner": user["level"] >= iam.OWNER_LEVEL,
        "sb_ngay": _dt.now().strftime("%d/%m/%Y"),
        "level_chu": _TEN_LEVEL.get(user["level"], "")})


def _lam_alias(slug: str, dd: str):
    async def _alias(request: Request):
        return await proxy_app(request, slug, dd)
    return _alias


for _duong, (_slug, _dd) in _ALIAS.items():
    app.add_api_route(_duong, _lam_alias(_slug, _dd), methods=["GET", "HEAD"],
                      name=f"alias_{_duong.strip('/')}")
