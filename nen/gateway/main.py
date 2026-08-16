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
_NHAN_GIO = {"quan_tai_khoan": "Quản tài khoản", "duyet_ho_so": "Duyệt hồ sơ nhân sự",
             "nap_tai_lieu": "Nạp tài liệu", "duyet_qa": "Duyệt Q&A bổ sung",
             "giam_sat": "Giám sát hoạt động"}


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
        ds = ket.liet_ke(kconn)
    finally:
        kconn.close()
    vai_llm: dict[str, dict] = {}
    for c in ds["cau_hinh"]:
        manh = c["khoa"].split(".")
        if len(manh) == 3 and manh[0] == "llm":
            vai_llm.setdefault(manh[1], {})[manh[2]] = c["gia_tri"]
    for b in ds["bi_mat"]:
        manh = b["khoa"].split(".")
        if len(manh) == 3 and manh[0] == "llm" and manh[2] == "api_key":
            vai_llm.setdefault(manh[1], {})["key_duoi"] = b["duoi"]
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
            "vai_llm": vai_llm, "so_thuc_the": so_thuc_the,
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


@app.get("/general/accounts", response_class=HTMLResponse)
def nen_tai_khoan(request: Request):
    user = _gate_nen(request, quyen="quan_tai_khoan")
    if isinstance(user, Response):
        return user
    return _render_tai_khoan(request, user)


@app.post("/general/accounts/create", response_class=HTMLResponse)
def nen_tk_tao(request: Request, ten: str = Form(""), mat_khau: str = Form(""),
               bo_phan: str = Form(""), level: int = Form(1)):
    user = _gate_nen(request, quyen="quan_tai_khoan")
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        iam.tao_tai_khoan(conn, user, ten, mat_khau, bo_phan, level)
        return _render_tai_khoan(request, user, bao=f"Created account {ten} "
                                 "(must change password at first sign-in).")
    except iam.LoiIam as e:
        return _render_tai_khoan(request, user, loi=str(e))
    finally:
        conn.close()


@app.post("/general/accounts/update", response_class=HTMLResponse)
def nen_tk_sua(request: Request, ten: str = Form(...),
               hanh_dong: str = Form(...), gia_tri: str = Form("")):
    user = _gate_nen(request, quyen="quan_tai_khoan")
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
        elif hanh_dong == "xoa":
            if gia_tri != ten:   # xác nhận 2 lớp: client gõ lại tên, SERVER kiểm
                return _render_tai_khoan(request, user,
                                         loi="To delete, retype the exact account name.")
            iam.xoa_tai_khoan(conn, user, ten)
        elif hanh_dong == "reset_mk":
            iam.doi_mat_khau(conn, user, ten, gia_tri, ep_doi_lan_sau=True)
        else:
            return _render_tai_khoan(request, user, loi="Unknown action.")
        return _render_tai_khoan(request, user, bao=f"Done {hanh_dong}: {ten}")
    except iam.LoiIam as e:
        return _render_tai_khoan(request, user, loi=str(e))
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


@app.get("/general/people", response_class=HTMLResponse)
def nen_nhan_su(request: Request):
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    return _render_nhan_su(request, user)


@app.post("/general/people/create", response_class=HTMLResponse)
def nen_ns_tao(request: Request, ho_ten: str = Form(""),
               bo_phan: str = Form(""), vi_tri: str = Form("")):
    user = _gate_nen(request, nhan_su=True)
    if isinstance(user, Response):
        return user
    conn = iam.ket_noi()
    try:
        ns = iam.tao_nguoi(conn, user, ho_ten, bo_phan, vi_tri)
        return _render_nhan_su(request, user, bao=f"Created profile {ns['ma']}.")
    except iam.LoiIam as e:
        return _render_nhan_su(request, user, loi=str(e))
    finally:
        conn.close()


# --- Phân quyền tick (chỉ Owner — giỏ tuyệt đối bang_phan_quyen) ---

def _luat_pq() -> dict:
    import json
    return json.loads((ROOT / "nen" / "rules" / "phan_quyen.json")
                      .read_text(encoding="utf-8-sig"))


def _render_phan_quyen(request: Request, user: dict, ten: str = "",
                       loi: str = "", bao: str = "") -> HTMLResponse:
    conn = iam.ket_noi()
    try:
        tai_khoan = iam.liet_ke_tai_khoan(conn)
        overrides = {}
        chon = next((t for t in tai_khoan if t["ten"] == ten), None)
        if chon:
            for r in conn.execute(
                    "SELECT * FROM quyen_override WHERE ten_tai_khoan=?", (ten,)):
                overrides[(r["app_slug"], r["hanh_dong"])] = bool(r["cho_phep"])
    finally:
        conn.close()
    luat = _luat_pq()
    hang = []
    for a in doc_hop_dong():
        if a["slug"] == "app-mau":
            continue
        dk = (luat.get("apps", {}).get(a["slug"], {}) or {}).get("vao", {})
        mota = f"L{dk.get('min_level', 1)}+"
        if dk.get("bo_phan"):
            mota += " bộ phận " + "/".join(dk["bo_phan"]) + " (L4+ mọi bộ phận)"
        hang.append({"app_slug": a["slug"], "hanh_dong": "vao",
                     "nhan": f"Vào {a['ten']}", "mac_dinh": mota})
    for hd in luat.get("gio_uy_quyen", []):
        hang.append({"app_slug": "*", "hanh_dong": hd,
                     "nhan": _NHAN_GIO.get(hd, hd),
                     "mac_dinh": "Owner / Admin ủy quyền"})
    return templates.TemplateResponse(
        request, "nen_phan_quyen.html",
        {"user": user, "trang": "phan-quyen", "loi": loi, "bao": bao,
         "tai_khoan": tai_khoan, "ten_chon": ten if chon else "",
         "hang": hang, "overrides": overrides,
         "gio_tuyet_doi": luat.get("gio_owner_tuyet_doi", [])})


@app.get("/general/permissions", response_class=HTMLResponse)
def nen_phan_quyen(request: Request, ten: str = "", bao: str = "", loi: str = ""):
    user = _gate_nen(request, quyen="bang_phan_quyen")   # giỏ tuyệt đối = chỉ Owner
    if isinstance(user, Response):
        return user
    return _render_phan_quyen(request, user, ten=ten, bao=bao, loi=loi)


@app.post("/general/permissions/grant", response_class=HTMLResponse)
def nen_pq_gan(request: Request, ten: str = Form(...), app_slug: str = Form(...),
               hanh_dong: str = Form(...), gia_tri: str = Form(...)):
    user = _gate_nen(request, quyen="bang_phan_quyen")
    if isinstance(user, Response):
        return user
    cho_phep = {"ke_thua": None, "cho": True, "chan": False}.get(gia_tri, None)
    conn = iam.ket_noi()
    try:
        iam.gan_override(conn, user, ten, app_slug, hanh_dong, cho_phep)
        return _render_phan_quyen(request, user, ten=ten,
                                  bao=f"Set {app_slug}/{hanh_dong} = {gia_tri}")
    except iam.LoiIam as e:
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


# --- Cấu hình LLM (két — chỉ Owner, giỏ tuyệt đối ket_cau_hinh) ---

@app.get("/general/ai-models", response_class=HTMLResponse)
def nen_cau_hinh(request: Request, bao: str = "", loi: str = ""):
    user = _gate_nen(request, quyen="ket_cau_hinh")   # giỏ tuyệt đối = chỉ Owner
    if isinstance(user, Response):
        return user
    conn = ket.ket_noi()
    try:
        ds = ket.liet_ke(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "nen_cau_hinh.html",
        {"user": user, "trang": "cau-hinh", "ds": ds, "bao": bao, "loi": loi})


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


# --- Trang cũ nghỉ hưu → redirect (giữ 1 nhịp chuyển tiếp, UI_FLOW.md mục 5) ---

@app.get("/suc-khoe")
def suc_khoe_cu():
    return RedirectResponse("/general", status_code=303)


@app.get("/quan-tri")
def quan_tri_cu():
    return RedirectResponse("/general/accounts", status_code=303)


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


@app.get("/cai-dat")
def cai_dat_cu():
    return RedirectResponse("/general/ai-models", status_code=303)


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
    "/cau-hinh": "/general/ai-models",
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
            # Cờ 'quan-tri': ai mở được mục Nhân sự/User trên sidebar — luật V1:
            # Owner + HR L3+ (iam.quyen_nhan_su) hoặc Admin ủy quyền tài khoản.
            if iam.quyen_nhan_su(u) or iam.co_quyen(u, "quan_tai_khoan", conn=conn2):
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
        return Response("No such app.", status_code=404)
    if not duoc_vao:
        return Response("You do not have access to this tool.", status_code=403)
    return await chuyen_tiep(
        request, cong=muc["cong"], goc=f"/app/{slug}", duong_dan=duong_dan,
        ten_user=user["ten"], tien_to_app=muc.get("tien_to", []),
        vai=iam.vai_cho_app(user, slug), level=user["level"],
        bo_phan=user.get("bo_phan", ""), apps_duoc_vao=apps_duoc_vao,
        ten_hien_thi=user.get("ten_hien_thi", ""), bo_qua=_ALIAS_BO_QUA)


def _lam_alias(slug: str, dd: str):
    async def _alias(request: Request):
        return await proxy_app(request, slug, dd)
    return _alias


for _duong, (_slug, _dd) in _ALIAS.items():
    app.add_api_route(_duong, _lam_alias(_slug, _dd), methods=["GET", "HEAD"],
                      name=f"alias_{_duong.strip('/')}")
