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
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/tasky
ROOT = _APP_DIR.parents[1]                              # D:\AI AGENT OUTLIERY
# Luật 6: dữ liệu tách khỏi code. Đặt TRƯỚC khi import module đọc env.
os.environ.setdefault("TASKY_DIR", str(ROOT / "data" / "tasky" / "db"))

PHIEN_BAN = "0.2.0"
app = FastAPI(title="Tasky v3")
from src import muc_tieu as mt_lo, nhan_su, thong_bao as tb  # noqa: E402 — danh sách người, đọc chỉ-đọc sổ IAM chung
from src import tuan as tuan_lo  # noqa: E402 — lõi sổ tuần (đọc TASKY_DIR lúc gọi hàm)
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2

templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])
# Vendor chart (Frappe Charts) — LAN không ra Internet nên chép về, không CDN.
# Xem src/static/vendor/NGUON.md.
app.mount("/tasky-static", StaticFiles(directory=str(_APP_DIR / "src" / "static")),
          name="tasky-static")
templates.env.filters["han"] = tuan_lo.tinh_han   # {{ v|han }} → {chu, muc, con}


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
yeu_cau_muc_tieu = _yeu_cau("giao_viec", "Mục tiêu dành cho Leader trở lên.")


def _co_sidebar(x_remote_actions: str, ma: str = "", user: dict | None = None) -> dict:
    """Cờ hiện mục con sidebar + huy hiệu thông báo — CHỈ theo cờ gateway phát,
    không tự suy từ level. Thông báo sinh từ TRẠNG THÁI THẬT mỗi lần mở trang."""
    hd = cac_hanh_dong(x_remote_actions)
    co_giao = "giao_viec" in hd
    ds = []
    if ma and user:
        ds = tb.cua_toi(ma, user)
        if co_giao:
            cap_duoi, _ = nhan_su.cap_duoi_cua(user)
            ds += tb.cua_leader(ma, user, cap_duoi or [])
    return {"tk_giao": co_giao,
            "tk_bao_cao": bool({"bao_cao_bo_phan", "bao_cao_cong_ty",
                                "bao_cao_nhan_su"} & hd),
            "tk_bao": ds, "tk_huy_hieu": tb.tom_tat(ds)}


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
def trang_viec(request: Request, user: dict = Depends(lay_user), tuan_xem: str = "",
               x_remote_actions: str = Header("")):
    """Việc của tôi — chỉ việc CỦA MÌNH (luật 1: lọc ở server, không ẩn nút)."""
    ma = _ma_tuan_hop_le(tuan_xem)
    ds = tuan_lo.sap_xep(tuan_lo.viec_cua(ma, user["ten"]))
    tu, den = tuan_lo.khoang_tuan(ma)
    return templates.TemplateResponse(request, "viec.html", {
        "user": user, "ma_tuan": ma, "tu": tu, "den": den,
        "viec_giao": [v for v in ds if v["nguon"] == "giao"],
        "viec_tu": [v for v in ds if v["nguon"] == "tu_them"],
        "viec_ph": [v for v in ds if v["nguon"] == "phoi_hop"],
        "cap_duoi_toi": (nhan_su.cap_duoi_cua(user)[0] or [])
                        if "giao_viec" in cac_hanh_dong(x_remote_actions) else [],
        "viec_con": {v["id"]: tuan_lo.viec_con(ma, v["id"])
                     for v in ds if v["nguon"] == "phoi_hop"},
        "tk": tuan_lo.thong_ke_nguoi(ma, user["ten"]),
        "loai_viec": tuan_lo.cac_loai_viec(),
        "tuan_truoc": tuan_lo.tuan_lien_ke(ma, -1),
        "tuan_sau": tuan_lo.tuan_lien_ke(ma, 1),
        "tuan_nay": tuan_lo.ma_tuan(), **_co_sidebar(x_remote_actions, ma, user)})


@app.get("/giao-viec", response_class=HTMLResponse)
def trang_giao(request: Request, user: dict = Depends(yeu_cau_giao_viec),
               tuan_xem: str = "", x_remote_actions: str = Header("")):
    """Giao việc — chỉ người trong bộ phận mình và cấp dưới mình (lọc bằng chính
    luật của lõi). Kèm khối chờ xác nhận + việc còn treo để đóng tuần."""
    ma = _ma_tuan_hop_le(tuan_xem)
    cap_duoi, loi = nhan_su.cap_duoi_cua(user)
    ds_nguoi = cap_duoi or []
    bang = tuan_lo.bang_bao_cao(ma, ds_nguoi)
    tu, den = tuan_lo.khoang_tuan(ma)
    return templates.TemplateResponse(request, "giao_viec.html", {
        "user": user, "ma_tuan": ma, "tu": tu, "den": den,
        "cap_duoi": ds_nguoi, "loi_iam": loi,
        "bang": bang,
        "ngang_cap": nhan_su.ngang_cap_bo_phan_khac(user)[0] or [],
        "da_gui": tuan_lo.sap_xep(tuan_lo.yeu_cau_da_gui(ma, user)),
        "cho_xac_nhan": tuan_lo.cho_xac_nhan(ma, user),
        "con_treo": tuan_lo.sap_xep(tuan_lo.con_treo(ma, user)),
        "loai_viec": tuan_lo.cac_loai_viec(),
        "tuan_truoc": tuan_lo.tuan_lien_ke(ma, -1),
        "tuan_sau": tuan_lo.tuan_lien_ke(ma, 1),
        "tuan_nay": tuan_lo.ma_tuan(), **_co_sidebar(x_remote_actions, ma, user)})


@app.get("/muc-tieu", response_class=HTMLResponse)
def trang_muc_tieu(request: Request, user: dict = Depends(yeu_cau_muc_tieu),
                   x_remote_actions: str = Header(""), chon: str = ""):
    """Cây mục tiêu — MỘT mục tiêu một tab (Owner chốt 25/08). Dữ liệu gom sẵn ở
    server, template chỉ hiển thị."""
    hd = cac_hanh_dong(x_remote_actions)
    ds = mt_lo.trong_pham_vi(user, bool({"bao_cao_cong_ty", "bao_cao_nhan_su"} & hd))
    gom = mt_lo.viec_theo_muc_tieu()          # MỘT lượt quét cho cả trang
    cay = []
    for m in ds:
        viec = gom.get(m["id"], [])
        cay.append({**m, "tien_do": mt_lo.tien_do(m["id"], viec),
                    "nhom": mt_lo.nhom_viec(tuan_lo.sap_xep(viec)),
                    "canh_bao": mt_lo.canh_bao(m, viec),
                    "con_han": mt_lo.con_han(m)})
    cay.sort(key=lambda c: (c["trang_thai"] != mt_lo.DANG_CHAY,
                            -len(c["canh_bao"]), c["tieu_de"]))
    cap_duoi, _ = nhan_su.cap_duoi_cua(user)
    return templates.TemplateResponse(request, "muc_tieu.html", {
        "user": user, "cay": cay, "chon": chon or (cay[0]["id"] if cay else ""),
        "cap_duoi": cap_duoi or [], "loai_viec": tuan_lo.cac_loai_viec(),
        "duoc_dat": mt_lo.duoc_dat_muc_tieu(user),
        "ma_tuan": tuan_lo.ma_tuan(),
        **_co_sidebar(x_remote_actions, tuan_lo.ma_tuan(), user)})


@app.get("/bao-cao-tuan", response_class=HTMLResponse)
def trang_bao_cao(request: Request, user: dict = Depends(yeu_cau_bao_cao),
                  x_remote_actions: str = Header(""), tuan_xem: str = ""):
    """Báo cáo — phạm vi theo FLOW-v3 §9.1: Leader bộ phận mình · Manager L4+ mọi bộ
    phận · HR Leader+ toàn công ty (cờ `bao_cao_nhan_su` khai kèm bộ phận trong
    phan_quyen.json) · Owner tất. App CHỈ TIN CỜ gateway phát."""
    hd = cac_hanh_dong(x_remote_actions)
    toan_cong_ty = bool({"bao_cao_cong_ty", "bao_cao_nhan_su"} & hd)
    ma = _ma_tuan_hop_le(tuan_xem)
    ds, loi = nhan_su.trong_pham_vi_bao_cao(user, toan_cong_ty)
    bang = tuan_lo.bang_bao_cao(ma, ds or [])
    tu, den = tuan_lo.khoang_tuan(ma)
    return templates.TemplateResponse(request, "bao_cao.html", {
        "user": user, "ma_tuan": ma, "tu": tu, "den": den,
        "bang": bang, "loi_iam": loi, "toan_cong_ty": toan_cong_ty,
        "tong": tuan_lo.tong_hop(bang),
        "kho_quy_trinh": tuan_lo.kho_quy_trinh(),
        "tuan_truoc": tuan_lo.tuan_lien_ke(ma, -1),
        "tuan_sau": tuan_lo.tuan_lien_ke(ma, 1),
        "tuan_nay": tuan_lo.ma_tuan(), **_co_sidebar(x_remote_actions, ma, user)})


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
                han: str = Form(""), gap: str = Form(""),
                tuan_xem: str = Form(""), user: dict = Depends(lay_user)):
    return _goi(tuan_lo.them_viec_tu, _ma_tuan_hop_le(tuan_xem), user, tieu_de,
                loai_viec, han, _co(gap))


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


# --- API của leader (gate bằng cờ hành động; luật level/bộ phận vẫn kiểm ở lõi) ---

def _co(v: str) -> bool:
    """Ô tick từ form: '1'/'true'/'on' là bật, còn lại tắt."""
    return str(v).strip().lower() in ("1", "true", "on", "co", "yes")


def _tim_nguoi(ten: str) -> dict:
    """Level + bộ phận THẬT của người nhận, đọc từ IAM — không lấy từ form gửi lên,
    kẻo client tự khai level thấp để lách luật giao việc."""
    ds, loi = nhan_su.ds_nguoi()
    if ds is None:
        raise HTTPException(503, loi)
    for n in ds:
        if n["ten"] == ten:
            return n
    raise HTTPException(400, "Không tìm thấy người này trong sổ nhân sự.")


@app.post("/api-tasky/giao")
def api_giao(nguoi: str = Form(...), tieu_de: str = Form(...), loai_viec: str = Form(""),
             tu_yeu_cau: str = Form(""), han: str = Form(""), gap: str = Form(""),
             tuan_xem: str = Form(""), user: dict = Depends(yeu_cau_giao_viec)):
    """Giao việc trong bộ phận. `tu_yeu_cau` = id yêu cầu phối hợp đang chẻ nhỏ."""
    return _goi(tuan_lo.them_viec_giao, _ma_tuan_hop_le(tuan_xem), user,
                _tim_nguoi(nguoi), tieu_de, loai_viec, tu_yeu_cau, han, _co(gap))


@app.post("/api-tasky/phoi-hop")
def api_phoi_hop(nguoi: str = Form(...), tieu_de: str = Form(...), loai_viec: str = Form(""),
                 han: str = Form(""), gap: str = Form(""),
                 tuan_xem: str = Form(""), user: dict = Depends(yeu_cau_giao_viec)):
    """Gửi yêu cầu phối hợp sang bộ phận khác (luật ngang cấp kiểm ở lõi)."""
    return _goi(tuan_lo.yeu_cau_phoi_hop, _ma_tuan_hop_le(tuan_xem), user,
                _tim_nguoi(nguoi), tieu_de, loai_viec, han, _co(gap))


@app.post("/api-tasky/danh-dau")
def api_danh_dau(id: str = Form(...), gap: str = Form(""), han: str = Form(""),
                 tuan_xem: str = Form(""), user: dict = Depends(lay_user)):
    """Đổi dấu GẤP / hạn chót sau khi việc đã tồn tại (quyền kiểm ở lõi).
    Chuỗi rỗng ở `gap` = không đụng tới; 'xoa' ở `han` = gỡ hạn."""
    return _goi(tuan_lo.danh_dau, _ma_tuan_hop_le(tuan_xem), id, user,
                None if gap == "" else _co(gap),
                None if han == "" else ("" if han == "xoa" else han))


@app.post("/api-tasky/xac-nhan")
def api_xac_nhan(id: str = Form(...), tuan_xem: str = Form(""),
                 user: dict = Depends(yeu_cau_xac_nhan)):
    return _goi(tuan_lo.xac_nhan_viec, _ma_tuan_hop_le(tuan_xem), id, user)


@app.post("/api-tasky/tra-lai")
def api_tra_lai(id: str = Form(...), ly_do: str = Form(""), tuan_xem: str = Form(""),
                user: dict = Depends(yeu_cau_xac_nhan)):
    return _goi(tuan_lo.tra_lai_viec, _ma_tuan_hop_le(tuan_xem), id, user, ly_do)


@app.post("/api-tasky/huy")
def api_huy(id: str = Form(...), ly_do: str = Form(""), tuan_xem: str = Form(""),
            user: dict = Depends(yeu_cau_xac_nhan)):
    return _goi(tuan_lo.huy_viec, _ma_tuan_hop_le(tuan_xem), id, user, ly_do)


@app.post("/api-tasky/doi")
def api_doi(id: str = Form(...), ly_do: str = Form(""), nguoi_moi: str = Form(""),
            tuan_xem: str = Form(""), user: dict = Depends(yeu_cau_xac_nhan)):
    nm = _tim_nguoi(nguoi_moi) if nguoi_moi.strip() else None
    return _goi(tuan_lo.doi_sang_tuan_sau, _ma_tuan_hop_le(tuan_xem), id, user, ly_do, nm)


@app.post("/api-tasky/mo-lai-tuan")
def api_mo_lai_tuan(nguoi: str = Form(...), tuan_xem: str = Form(""),
                    user: dict = Depends(yeu_cau_xac_nhan)):
    """Thu lại việc đóng tuần — đóng nhầm thì mở lại, có vết trong nhật ký."""
    return _goi(tuan_lo.mo_lai_tuan, _ma_tuan_hop_le(tuan_xem), nguoi, user)


# --- API mục tiêu (§12) ---

@app.post("/api-tasky/muc-tieu")
def api_tao_muc_tieu(tieu_de: str = Form(...), ket_qua: str = Form(...),
                     han: str = Form(""), tu_nhiem_vu: str = Form(""),
                     user: dict = Depends(yeu_cau_muc_tieu)):
    return _goi(mt_lo.tao, user, tieu_de, ket_qua, han, tu_nhiem_vu)


@app.post("/api-tasky/muc-tieu/chot")
def api_chot_muc_tieu(id: str = Form(...), ket_qua: str = Form(...),
                      nhan_xet: str = Form(""), user: dict = Depends(yeu_cau_muc_tieu)):
    return _goi(mt_lo.chot_ket_qua, id, user, ket_qua, nhan_xet)


@app.post("/api-tasky/muc-tieu/mo-lai")
def api_mo_lai_muc_tieu(id: str = Form(...), user: dict = Depends(yeu_cau_muc_tieu)):
    return _goi(mt_lo.mo_lai, id, user)


@app.post("/api-tasky/muc-tieu/che-viec")
def api_che_viec(muc_tieu_id: str = Form(...), tieu_de: str = Form(...),
                 loai_viec: str = Form(""), nguoi: str = Form(""), han: str = Form(""),
                 gap: str = Form(""), tuan_xem: str = Form(""),
                 user: dict = Depends(yeu_cau_muc_tieu)):
    """Chẻ một việc từ mục tiêu. Để trống `nguoi` = chưa phân công, giao sau."""
    ma = _ma_tuan_hop_le(tuan_xem)
    if nguoi.strip():
        return _goi(tuan_lo.them_viec_giao, ma, user, _tim_nguoi(nguoi), tieu_de,
                    loai_viec, "", han, _co(gap), muc_tieu_id)
    return _goi(tuan_lo.them_viec_muc_tieu, ma, user, tieu_de, loai_viec,
                muc_tieu_id, han, _co(gap))


@app.post("/api-tasky/muc-tieu/gan-nguoi")
def api_gan_nguoi(id: str = Form(...), nguoi: str = Form(...), tuan_xem: str = Form(""),
                  user: dict = Depends(yeu_cau_muc_tieu)):
    return _goi(tuan_lo.gan_nguoi, _ma_tuan_hop_le(tuan_xem), id, user, _tim_nguoi(nguoi))


@app.post("/api-tasky/dong-tuan")
def api_dong_tuan(nguoi: str = Form(...), tuan_xem: str = Form(""),
                  user: dict = Depends(yeu_cau_xac_nhan)):
    return _goi(tuan_lo.dong_tuan, _ma_tuan_hop_le(tuan_xem), nguoi, user)
