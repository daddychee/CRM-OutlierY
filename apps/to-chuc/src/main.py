# -*- coding: utf-8 -*-
"""APP TỔ CHỨC (v2, :9103) — KPI + chấm công + NAS + VAULT, DI TRÚ từ agent-app.

Nghiệp vụ GIỮ NGUYÊN hệ cũ (kpi.py / cham_cong.py / vault.py + trang NAS).
Chỉ đổi các mối nối theo kiến trúc nền (theo mẫu apps/data-analytics):
1. AUTH: không tự giữ user — nhận claims X-Remote-User/Level/Role/Dept từ gateway
   (Dept được gateway quote → app unquote lại). Gate trong app:
   /kpi = Manager+ (level >= 4) · /vault* = CHỈ Owner (level == 5) · /nas = mọi
   người có claims.
2. DỮ LIỆU: data/to-chuc/db/cham-cong + data/vault theo Luật 6 (env đặt sẵn dưới).
3. Nguồn KPI giữ cơ chế env (PLANNERY_PLAN/CONTENT_HISTORY/SPEAKY_JOBS_LOG/
   BAO_CAO_DIR) — mặc định trỏ chỗ KHÔNG tồn tại → "nguồn chết → —" (van chống
   bịa); TUYỆT ĐỐI không default sang C:\\OutlierY hệ thật như bản cũ.
   Riêng BAO_CAO_DIR mặc định = data của app data-analytics v2 (CHỈ-ĐỌC file;
   việc treo: chuyển sang connector API khi app đó mở API).
4. Chấm công: điểm hứng = lay_user của CHÍNH app này (mọi request có claims) +
   /api/nhip (nhịp tim 5') + /api/nhip-thoat (beacon đóng app) — base.html đã có
   sẵn khối JS gọi 2 route đó. Điểm hứng TOÀN HỆ (mọi app như cổng 8000 cũ) thuộc
   gateway — việc treo, ghi trong README.
5. Danh sách người cho bảng KPI: đọc CHỈ-ĐỌC sổ IAM (nen/iam) — hồ sơ nhân sự đã
   về IAM ở v2. IAM không đọc được → bảng trống + ghi chú (không hiện 0 người giả).

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/to-chuc" --port 9103
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/to-chuc
ROOT = _APP_DIR.parents[1]                               # D:\AI AGENT OUTLIERY
# Luật 6: dữ liệu tách khỏi code. Đặt TRƯỚC khi import các module (chúng đọc env
# lúc gọi hàm nên setdefault ở đây là đủ; conftest test đè lại bằng monkeypatch).
os.environ.setdefault("CHAM_CONG_DIR", str(ROOT / "data" / "to-chuc" / "db" / "cham-cong"))
os.environ.setdefault("VAULT_DIR", str(ROOT / "data" / "vault"))
# Nguồn KPI: mặc định KHÔNG TỒN TẠI → kpi.py trả None → UI "—" (van chống bịa).
# Muốn nối nguồn thật (PlannerY/Content/SpeakY còn chạy hệ cũ) → Owner đặt env
# trỏ đường CHỈ-ĐỌC, app không bao giờ ghi vào các file này.
os.environ.setdefault("PLANNERY_PLAN", str(ROOT / "data" / "to-chuc" / "nguon" / "plannery-plan.json"))
os.environ.setdefault("CONTENT_HISTORY", str(ROOT / "data" / "to-chuc" / "nguon" / "content-history.jsonl"))
os.environ.setdefault("SPEAKY_JOBS_LOG", str(ROOT / "data" / "to-chuc" / "nguon" / "speaky-jobs_log.csv"))
os.environ.setdefault("BAO_CAO_DIR", str(ROOT / "data" / "data-analytics" / "db" / "bao-cao-lich-su"))
# HR Hub + Finance Hub (DE.md mục 10) — 4 store mới, đều khai du_lieu trong apps.json
os.environ.setdefault("CHAM_CONG_CHOT_DIR", str(ROOT / "data" / "to-chuc" / "db" / "cham-cong-chot"))
os.environ.setdefault("KPI_DANH_GIA_DIR", str(ROOT / "data" / "to-chuc" / "db" / "kpi-danh-gia"))
os.environ.setdefault("SO_THU_CHI_DIR", str(ROOT / "data" / "to-chuc" / "db" / "so-thu-chi"))
os.environ.setdefault("MUC_TIEU_PATH", str(ROOT / "data" / "to-chuc" / "db" / "muc-tieu.json"))

from src import kpi_danh_gia, tai_chinh, vault           # noqa: E402
from src.cham_cong import doc_ngay as cc_doc_ngay        # noqa: E402
from src.cham_cong import (bang_cong_thang, chot_ky, doc_chot, ghi_nhan,  # noqa: E402
                           gio_chu, tong_gio)
from src.kpi import kpi_plannery, ky_hien_tai, tong_hop_kpi  # noqa: E402

PHIEN_BAN = "2.0.0"
app = FastAPI(title="Tổ chức v2")
from nen.common import danh_ba, nhat_ky     # noqa: E402 — danh bạ đế (chỉ-đọc) + log P4
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2
templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])


def _fmt_tien(v) -> str:
    """Hiển thị tiền cho template ($ theo mockup F1): 2140→$2,140 · -43→−$43;
    không phải số → '—' (không bịa)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    s = f"{abs(v):,.2f}"
    if s.endswith(".00"):
        s = s[:-3]
    return ("−$" if v < 0 else "$") + s


templates.env.filters["tien"] = _fmt_tien
templates.env.filters["gio_chu"] = gio_chu


# ---------- claims (thay auth hệ cũ) ----------

def lay_user(x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
             x_remote_role: str = Header(""), x_remote_dept: str = Header("")) -> dict:
    """User = claims gateway tiêm (an toàn vì app bind 127.0.0.1 — chỉ gateway tới
    được; header giả từ trình duyệt đã bị gateway vứt). Dept được proxy quote()
    (header phải ASCII) → unquote lại để RBAC so đúng CHUỖI GỐC tiếng Việt.
    ĐIỂM HỨNG CHẤM CÔNG (như auth.lay_user cổng 8000 cũ): mọi request có danh
    tính đều ghi hiện diện — bọc kín, chấm công hỏng không được chặn request."""
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    try:
        level = int(x_remote_level or 0)
    except ValueError:
        level = 0
    try:
        ghi_nhan(x_remote_user)
    except Exception:
        pass
    return {"ten": x_remote_user, "level": level, "vai": x_remote_role,
            "bo_phan": unquote(x_remote_dept or "")}


def yeu_cau_manager(user: dict = Depends(lay_user)) -> dict:
    """Trang KPI: Manager+ (level >= 4) — giữ ý gate trang Nhân sự hệ cũ."""
    if user["level"] < 4:
        raise HTTPException(403, "Trang KPI dành cho Quản lý trở lên (level 4+).")
    return user


def yeu_cau_owner(user: dict = Depends(lay_user)) -> dict:
    """Vault: CHỈ Owner (level == 5) — giữ nguyên luật hệ cũ, khác → 403."""
    if user["level"] != 5:
        raise HTTPException(403, "Chỉ Owner được vào vault.")
    return user


# ---------- health (hợp đồng app) ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "to-chuc", "phien_ban": PHIEN_BAN}


@app.get("/", response_class=HTMLResponse)
async def goc():
    # /nas là trang mọi người vào được (KPI cần Manager+, vault cần Owner)
    return RedirectResponse("/nas", status_code=303)


# ═══════════════ KPI + CHẤM CÔNG (Manager+) ═══════════════
# Hệ cũ: khối KPI + chấm công nằm trong trang /nhan-su (hồ sơ đã về IAM ở v2)
# → v2 tách thành trang /kpi riêng, chỉ HIỂN THỊ số từ hàm sẵn có, không bịa cột.

def _ds_nguoi_iam() -> tuple[list[dict] | None, str]:
    """Danh sách người cho bảng KPI, đọc CHỈ-ĐỌC sổ IAM chung (tài khoản + họ tên
    hồ sơ nối qua nguoi_ma). App vẫn tự đứng: thiếu nen/iam hay DB lỗi → (None, lý
    do) — UI nói thẳng, không dựng bảng rỗng giả vờ 'không có ai'.
    Đ2 khối đế: planner_id DẪN XUẤT từ mã hồ sơ (NS-005 → ns_ns005 — đúng khuôn
    plannery_sync hệ cũ) → nối PlannerY theo ID, hết so họ tên không phân hoa thường."""
    try:
        from nen.iam import iam
        conn = iam.ket_noi()
        try:
            nguoi = {n["ma"]: n for n in iam.liet_ke_nguoi(conn)}
            ds = []
            for tk in iam.liet_ke_tai_khoan(conn):
                ma_ns = tk.get("nguoi_ma") or ""
                ho_so = nguoi.get(ma_ns) or {}
                ds.append({"ten": tk["ten"], "bo_phan": tk.get("bo_phan") or "",
                           "ho_ten": ho_so.get("ho_ten", ""),
                           "planner_id": ("ns_" + ma_ns.replace("-", "").lower())
                                         if ma_ns else ""})
            return ds, ""
        finally:
            conn.close()
    except Exception as e:
        return None, (f"Không đọc được sổ IAM ({e.__class__.__name__}) — "
                      "chưa dựng được danh sách người cho bảng KPI.")


@app.get("/kpi", response_class=HTMLResponse)
def kpi_trang(request: Request, ky: str = "tuan", ngay_cc: str = "",
              user: dict = Depends(yeu_cau_manager)):
    """Bảng KPI kỳ tuần/tháng (tong_hop_kpi — 4 nguồn chỉ-đọc, nguồn chết → '—')
    + bảng chấm công một ngày (mặc định hôm nay)."""
    if ky not in ("tuan", "thang"):
        ky = "tuan"
    ds_nguoi, iam_loi = _ds_nguoi_iam()
    kpi = tong_hop_kpi(ds_nguoi or [], ky)

    ngay = (ngay_cc or "").strip() or date.today().isoformat()
    cc_ban_ghi = cc_doc_ngay(ngay)
    # Danh sách dòng chấm công: theo tài khoản IAM (thấy cả người VẮNG — trung
    # thực); IAM chết → chỉ liệt kê được người CÓ tín hiệu trong ngày đó.
    ho_ten_cua = {n["ten"]: n.get("ho_ten", "") for n in (ds_nguoi or [])}
    ten_cham = sorted(set(ho_ten_cua) | set(cc_ban_ghi)) if ds_nguoi is not None \
        else sorted(cc_ban_ghi)
    cham_cong = []
    for ten in ten_cham:
        d = cc_ban_ghi.get(ten) or {}
        cham_cong.append({"ten": ten, "ho_ten": ho_ten_cua.get(ten, ""),
                          "vao": d.get("vao"), "ra": d.get("ra"),
                          "nguon_ra": d.get("nguon_ra", ""),
                          "tong": tong_gio(d.get("vao", ""), d.get("ra", ""))})
    return templates.TemplateResponse(request, "kpi.html", {
        "user": user, "kpi": kpi, "iam_loi": iam_loi,
        "ngay_cc": ngay, "cham_cong": cham_cong})


# ═══════════════ HR HUB + FINANCE HUB (DE.md mục 10 — khu chức năng) ═══════════════
# Quyền: GATEWAY tính (giỏ nhan_su/ke_toan + luật bộ phận + ô tick) và phát cờ
# 'hr'/'finance' vào X-Remote-Apps — app CHỈ TIN CỜ, không tự tính lại (khuôn
# sb_ns/sb_nas). Thiếu cờ → 403.

def _cac_khu(x_remote_apps: str) -> set[str]:
    return {s.strip() for s in (x_remote_apps or "").split(",") if s.strip()}


def yeu_cau_hr(user: dict = Depends(lay_user), x_remote_apps: str = Header("")) -> dict:
    if "hr" not in _cac_khu(x_remote_apps):
        raise HTTPException(403, "HR Hub cần giỏ chức năng nhân sự (gateway chưa phát cờ 'hr').")
    return user


def yeu_cau_finance(user: dict = Depends(lay_user),
                    x_remote_apps: str = Header("")) -> dict:
    if "finance" not in _cac_khu(x_remote_apps):
        raise HTTPException(403, "Finance Hub cần giỏ chức năng kế toán (gateway chưa phát cờ 'finance').")
    return user


def _ds_ho_so_iam() -> tuple[list[dict] | None, str]:
    """Hồ sơ nhân sự CHỈ-ĐỌC từ sổ IAM chung (khuôn _ds_nguoi_iam — hub không giữ
    bản sao, IAM vẫn là nguồn sự thật; mọi GHI đi route gateway /general/people/*).
    planner_id dẫn xuất ns_<mã NS> đúng khuôn Đ2 khối đế.
    CCCD NHẠY CẢM (DE.md mục 12.1): app này KHÔNG BAO GIỜ giữ/render bản đầy đủ —
    pop khỏi dict ngay tại cửa đọc, chỉ còn cccd_che (8 số đầu + ****); xem đủ đi
    route gateway /general/people/cccd/<mã> có vết."""
    try:
        from nen.iam import iam
        conn = iam.ket_noi()
        try:
            ds = []
            for n in iam.liet_ke_nguoi(conn):
                d = dict(n, planner_id="ns_" + (n.get("ma") or "").replace("-", "").lower())
                so = d.pop("cccd", "") or ""
                d["cccd_che"] = (so[:8] + "****") if so else ""
                ds.append(d)
            return ds, ""
        finally:
            conn.close()
    except Exception as e:
        return None, (f"Không đọc được sổ IAM ({e.__class__.__name__}) — "
                      "chưa dựng được danh sách hồ sơ.")


def _tai_lieu_ns(ma: str) -> list[dict]:
    """Liệt kê CHỈ-ĐỌC tài liệu gốc của một hồ sơ từ kho tầng nền
    data/nen/ho-so-tai-lieu/<mã>/ (tiền lệ đọc IAM) — upload/xem đi route gateway."""
    goc = Path(os.getenv("HO_SO_TAI_LIEU_DIR",
                         str(ROOT / "data" / "nen" / "ho-so-tai-lieu")))
    d = goc / ma
    if not d.is_dir():
        return []
    ra = []
    for f in sorted(d.iterdir()):
        if f.is_file() and not f.name.endswith(".tmp"):
            ra.append({"ten": f.name, "loai": f.name.split("_", 1)[0],
                       "luc": datetime.fromtimestamp(
                           f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})
    return ra


def _ds_tai_khoan_iam() -> tuple[list[dict] | None, str]:
    """Tài khoản CHỈ-ĐỌC từ sổ IAM chung (tiền lệ _ds_nguoi_iam) cho tab Accounts
    của HR Hub. App KHÔNG ghi IAM (Luật 4) — mọi form ghi POST thẳng về route
    gateway /general/accounts/* sẵn có; đây chỉ là bảng đọc."""
    try:
        from nen.iam import iam
        conn = iam.ket_noi()
        try:
            return iam.liet_ke_tai_khoan(conn), ""
        finally:
            conn.close()
    except Exception as e:
        return None, (f"Không đọc được sổ IAM ({e.__class__.__name__}) — "
                      "chưa dựng được danh sách tài khoản.")


def _thang_hop_le(thang: str) -> str:
    thang = (thang or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", thang):
        return date.today().strftime("%Y-%m")
    return thang


@app.get("/hr", response_class=HTMLResponse)
def hr_trang(request: Request, tab: str = "accounts", thang: str = "",
             bao: str = "", loi: str = "", user: dict = Depends(yeu_cau_hr),
             x_remote_apps: str = Header("")):
    """HR Hub — MỘT CỬA công tác nhân sự (Owner chốt 16/08, gộp People+Accounts
    cùng ngày): Accounts (MỖI DÒNG = MỘT CON NGƯỜI — hồ sơ LEFT JOIN tài khoản
    qua nguoi_ma; form POST thẳng route gateway kèm ve=hr; khối tài khoản trong
    chi tiết CHỈ render khi gateway phát cờ 'accounts' — giỏ quan_tai_khoan) ·
    Attendance · KPI Review · Leaves.
    bao/loi trên query = thông báo ngắn gateway gửi về sau khi xử lý form."""
    co_accounts = "accounts" in _cac_khu(x_remote_apps)
    if tab not in ("accounts", "attendance", "kpi", "leaves"):
        tab = "accounts"        # gồm cả 'people' cũ — hai tab đã gộp một
    thang = _thang_hop_le(thang)
    ky_kpi = date.today().strftime("%Y-%m")   # KPI Review chấm kỳ THÁNG HIỆN TẠI

    ho_so, iam_loi = _ds_ho_so_iam()
    ds_nguoi, _ = _ds_nguoi_iam()
    ho_ten_cua = {n["ten"]: n.get("ho_ten", "") for n in (ds_nguoi or [])}

    bang_cong = bang_cong_thang(thang)
    chot = doc_chot(thang)

    kpi = tong_hop_kpi(ds_nguoi or [], "thang")
    danh_gia = kpi_danh_gia.moi_nhat_theo_nguoi(ky_kpi)

    # Leaves: đọc từ kpi_plannery kỳ tháng hiện tại — nguồn chết → None → UI '—'
    tu, den = ky_hien_tai("thang")
    planner = kpi_plannery(tu, den)
    nghi = []
    for n in (ds_nguoi or []):
        muc = None
        if planner is not None:
            muc = (planner.get(n.get("planner_id") or "")
                   or planner.get((n.get("ho_ten") or n.get("ten") or "").strip().lower()))
        nghi.append({"ten": n["ten"], "ho_ten": n.get("ho_ten", ""),
                     "ngay_nghi": muc["ngay_nghi"] if muc else None})

    chua_xep = [r["ten"] for r in (kpi["vh"] + kpi["kd"]) if r["ten"] not in danh_gia]
    stats = {"ho_so": sum(1 for h in (ho_so or []) if h.get("trang_thai") == "hoat_dong")
                      if ho_so is not None else None,
             "co_mat": len(cc_doc_ngay(date.today().isoformat())),
             "chua_xep": len(chua_xep)}
    # Tab Accounts (gộp): danh mục hồ sơ (luật ngoài code) + tài liệu gốc + LEFT
    # JOIN tài khoản qua nguoi_ma — một hồ sơ có thể chưa có tài khoản (Username
    # '—'); tài khoản không nối được hồ sơ vẫn hiện DÒNG RIÊNG (không giấu).
    ds_chuc_danh, ds_bo_phan, ds_cap_bac, tai_lieu_cua = [], [], [], {}
    tk_cua, tk_mo_coi, tk_loi = {}, [], ""
    if tab == "accounts":
        try:
            from nen.iam import iam as _iam
            ds_chuc_danh = _iam.doc_chuc_danh()
            ds_bo_phan = list(_iam.DEPARTMENTS)
            ds_cap_bac = list(_iam.CAP_BAC)
        except Exception:
            pass
        tai_lieu_cua = {h["ma"]: _tai_lieu_ns(h["ma"]) for h in (ho_so or [])}
        tai_khoan, tk_loi = _ds_tai_khoan_iam()
        ma_co = {h["ma"] for h in (ho_so or [])}
        for tk in (tai_khoan or []):
            ma_ns = tk.get("nguoi_ma") or ""
            if ma_ns in ma_co and ma_ns not in tk_cua:
                tk_cua[ma_ns] = tk
            else:
                tk_mo_coi.append(tk)
    return templates.TemplateResponse(request, "hr.html", {
        "user": user, "tab": tab, "thang": thang, "ky_kpi": ky_kpi,
        "ho_so": ho_so, "iam_loi": iam_loi, "stats": stats,
        "bang_cong": bang_cong, "chot": chot, "ho_ten_cua": ho_ten_cua,
        "kpi": kpi, "danh_gia": danh_gia,
        "nghi": nghi, "planner_song": planner is not None, "tu": tu, "den": den,
        "co_accounts": co_accounts, "tk_cua": tk_cua, "tk_mo_coi": tk_mo_coi,
        "tk_loi": tk_loi, "ds_chuc_danh": ds_chuc_danh, "ds_bo_phan": ds_bo_phan,
        "ds_cap_bac": ds_cap_bac, "tai_lieu_cua": tai_lieu_cua,
        "bao": bao, "loi": loi})


@app.post("/hr/chot-cong")
def hr_chot_cong(thang: str = Form(...), user: dict = Depends(yeu_cau_hr)):
    """Chốt công kỳ — file chốt CHỈ-THÊM (đã chốt → 409, không ghi đè)."""
    try:
        chot_ky(thang, user["ten"])
    except ValueError as e:
        raise HTTPException(409, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "chot_cong", thang)
    return RedirectResponse(f"/hr?tab=attendance&thang={thang}", status_code=303)


@app.post("/hr/kpi-danh-gia")
def hr_kpi_danh_gia(nguoi: str = Form(...), ky: str = Form(...),
                    xep_loai: str = Form(...), nhan_xet: str = Form(""),
                    user: dict = Depends(yeu_cau_hr)):
    """Xếp loại KPI — APPEND bản ghi (giữ trọn lịch sử chấm), hiển thị bản mới nhất."""
    try:
        kpi_danh_gia.them_danh_gia(nguoi, ky, xep_loai, nhan_xet, user["ten"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "kpi_danh_gia", f"{nguoi} {ky} = {xep_loai}")
    return RedirectResponse("/hr?tab=kpi", status_code=303)


@app.get("/finance", response_class=HTMLResponse)
def finance_trang(request: Request, tab: str = "ledger", thang: str = "",
                  user: dict = Depends(yeu_cau_finance)):
    """Finance Hub — 4 tab theo mockup finance-hub.html: Ledger (sổ chỉ-thêm +
    đảo) · Goals (mục tiêu) · Categories (rules CSV + tổng) · Channel P&L."""
    if tab not in ("ledger", "goals", "categories", "pnl"):
        tab = "ledger"
    thang = _thang_hop_le(thang)

    so = tai_chinh.doc_so()
    so_thang = sorted((b for b in so if (b.get("ngay") or "")[:7] == thang),
                      key=lambda b: (b.get("ngay", ""), b.get("tao_luc", "")),
                      reverse=True)
    da_dao = {b.get("tham_chieu") for b in so if b.get("loai") == "dao"}

    ds_kenh = danh_ba.liet_ke("kenh")
    kenh_cua = {k["ma"]: k for k in ds_kenh}
    ten_ngach = {n["ma"]: n.get("ten_chuan", "") for n in danh_ba.liet_ke("ngach")}

    muc_tieu = tai_chinh.doc_muc_tieu()
    mt_tong = tai_chinh.tong_hop_muc_tieu()
    return templates.TemplateResponse(request, "finance.html", {
        "user": user, "tab": tab, "thang": thang, "hom_nay": date.today().isoformat(),
        "tong": tai_chinh.tong_thang(thang), "so_thang": so_thang, "da_dao": da_dao,
        "danh_muc": tai_chinh.doc_danh_muc(),
        "dm_tong": tai_chinh.tong_hop_danh_muc(thang),
        "muc_tieu": muc_tieu, "mt_tong": mt_tong,
        "ds_kenh": ds_kenh, "kenh_cua": kenh_cua, "ten_ngach": ten_ngach,
        "pnl": tai_chinh.pnl_theo_kenh(thang)})


@app.post("/finance/but-toan")
def finance_but_toan(ngay: str = Form(...), danh_muc: str = Form(...),
                     so_tien: str = Form(...), muc_tieu: str = Form(...),
                     kenh_ma: str = Form(""), chung_tu: str = Form(""),
                     ghi_chu: str = Form(""), user: dict = Depends(yeu_cau_finance)):
    try:
        b = tai_chinh.them_but_toan(user["ten"], ngay, danh_muc, so_tien,
                                    muc_tieu, kenh_ma, chung_tu, ghi_chu)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "but_toan",
                f"{b['id']} {b['loai']} {b['danh_muc']} {b['so_tien']}")
    return RedirectResponse(f"/finance?tab=ledger&thang={ngay[:7]}", status_code=303)


@app.post("/finance/dao")
def finance_dao(id: str = Form(...), thang: str = Form(""),
                user: dict = Depends(yeu_cau_finance)):
    try:
        b = tai_chinh.dao_but_toan(user["ten"], id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "but_toan_dao", f"{b['id']} dao {id}")
    return RedirectResponse(
        f"/finance?tab=ledger&thang={_thang_hop_le(thang)}", status_code=303)


@app.post("/finance/muc-tieu")
def finance_muc_tieu(ten: str = Form(...), ngan_sach: str = Form(...),
                     trang_thai: str = Form("dang_chay"),
                     user: dict = Depends(yeu_cau_finance)):
    try:
        tai_chinh.them_muc_tieu(ten, ngan_sach, trang_thai)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "muc_tieu_moi", ten)
    return RedirectResponse("/finance?tab=goals", status_code=303)


# ═══════════════ NAS (01-05/08/2026 hệ cũ — mọi người có claims đều xem) ═══════════════
# nas_sync (đồng bộ tài khoản Windows theo mật khẩu OUTLIERY) KHÔNG mang sang —
# nó cần mật khẩu thật lúc đăng nhập nên thuộc gateway/IAM (việc treo, xem README).
# tt_nas vì thế luôn 'tat' → trang chỉ hiện đường copy + hướng dẫn map ổ + smb://
# (đúng hành vi hệ cũ khi NAS_DONG_BO tắt). NAS_DONG_BO ở đây chỉ còn vai trò
# "app đang chạy NGAY TRÊN server share" → mới tra dung lượng ổ + nhật ký xóa.

def _nas_dong_bo_bat() -> bool:
    return os.getenv("NAS_DONG_BO", "false").strip().lower() == "true"


def _nas_cac_duong() -> list[str]:
    """NAS_DUONG_DAN nhận NHIỀU đường dẫn ngăn bởi ';' (04/08/2026 — server có 2
    share NAS1 + Video). Một đường như cũ vẫn chạy — tương thích ngược."""
    tho = os.getenv("NAS_DUONG_DAN", "").strip()
    return [d.strip() for d in tho.split(";") if d.strip()]


def _nas_o_thay_duoc(level: int) -> list[int]:
    """Chỉ số các ổ (trong _nas_cac_duong()) một cấp bậc ĐƯỢC THẤY — lọc theo
    NAS_RIENG_MANAGER (05/08/2026: ổ liệt kê ở đây chỉ Manager+ level>=4 mới thấy,
    ẩn HẲN giao diện — quyền NTFS/share Windows thật chưa tách theo ổ này). Dùng
    chung cho trang /nas VÀ bộ .bat Cài đặt — bộ cài phải gắn lại ĐÚNG tập ổ user
    này thấy, không hơn không kém."""
    rieng_manager = {t.strip().lower() for t in os.getenv("NAS_RIENG_MANAGER", "").split(";") if t.strip()}
    return [i for i, d in enumerate(_nas_cac_duong())
            if not (d.rstrip("\\").split("\\")[-1].lower() in rieng_manager and level < 4)]


_nas_goc_share: dict[str, str] | None = None  # cache share→local path, đời tiến trình


def _nas_thong_tin_o(duong: str) -> dict | None:
    """Dung lượng thật cho thẻ ổ kiểu This PC (04/08/2026). App chạy NGAY TRÊN
    server nên tra local path của share (Get-SmbShare — cache 1 lần/đời tiến
    trình) rồi shutil.disk_usage local, không đi vòng SMB. Best-effort: bất kỳ
    lỗi nào → None, thẻ chỉ thiếu thanh dung lượng chứ không vỡ trang."""
    global _nas_goc_share
    if os.name != "nt":
        return None
    if _nas_goc_share is None:
        try:
            kq = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-SmbShare | ForEach-Object { $_.Name + '|' + $_.Path }"],
                capture_output=True, text=True, timeout=10)
            _nas_goc_share = {}
            for dong in (kq.stdout or "").splitlines():
                if "|" in dong:
                    n, p = dong.split("|", 1)
                    if p.strip():
                        _nas_goc_share[n.strip().lower()] = p.strip()
        except Exception:  # trang trí thuần túy — mọi lỗi đều không được vỡ trang
            _nas_goc_share = None  # không cache lỗi — lần sau thử lại
            return None
    goc = _nas_goc_share.get((duong.rstrip("\\").split("\\")[-1] or "").lower())
    if not goc:
        return None
    try:
        du = shutil.disk_usage(goc)
    except Exception:
        return None
    return {"phan_tram": min(100, round((du.total - du.free) * 100 / max(du.total, 1))),
            "trong_gb": f"{du.free / 2**30:,.0f}", "tong_gb": f"{du.total / 2**30:,.0f}"}


_nas_nk_cache: tuple[float, list] | None = None  # (lúc đọc, dữ liệu) — cache 60s


def _nas_nhat_ky_xoa() -> list[dict]:
    """Nhật ký XÓA/ĐỔI TÊN trên NAS cho Manager+ (04/08/2026): đọc Event 4663
    (audit DELETE) từ log Security — app chạy SYSTEM nên đọc được; đổi tên =
    DELETE ở đường dẫn cũ nên cùng nguồn. Chỉ có sự kiện khi script dựng nền đã
    bật SACL. Cache 60 giây; best-effort: lỗi → [] (panel tự ghi chú)."""
    global _nas_nk_cache
    if _nas_nk_cache and time.time() - _nas_nk_cache[0] < 60:
        return _nas_nk_cache[1]
    goc = []
    for d in _nas_cac_duong():
        _nas_thong_tin_o(d)  # bảo đảm bảng share→đường local đã nạp
        p = (_nas_goc_share or {}).get((d.rstrip("\\").split("\\")[-1] or "").lower())
        if p:
            goc.append(p.rstrip("\\"))
    ket_qua: list[dict] = []
    if goc:
        danh_sach = ",".join("'" + g.replace("'", "''") + "'" for g in goc)
        # LƯU Ý (đo thật 04/08): ObjectName trong event 4663 là ĐƯỜNG DẪN KERNEL
        # (\Device\HarddiskVolume7\OutlierY Nas 1\...) chứ KHÔNG phải G:\... —
        # phải so theo TÊN THƯ MỤC GỐC rồi dựng lại đường đẹp để hiển thị.
        ps = (
            "$bd=(Get-Date).AddDays(-14); $goc=@(" + danh_sach + ")\n"
            "Get-WinEvent -FilterHashtable @{LogName='Security';Id=4663;StartTime=$bd} "
            "-MaxEvents 2000 -ErrorAction SilentlyContinue | ForEach-Object {\n"
            "  $x=[xml]$_.ToXml(); $d=@{}\n"
            "  foreach ($n in $x.Event.EventData.Data) { $d[$n.Name]=$n.'#text' }\n"
            "  $m=0; try { $m=[Convert]::ToInt32($d['AccessMask'],16) } catch {}\n"
            "  if (($m -band 0x10000) -ne 0) {\n"
            "    $o=[string]$d['ObjectName']\n"
            "    foreach ($g in $goc) {\n"
            "      $la='\\'+(Split-Path $g -Leaf)+'\\'\n"
            "      $i=$o.ToLower().IndexOf($la.ToLower())\n"
            "      if ($i -ge 0) {\n"
            "        $dep=(Split-Path $g -Qualifier)+$o.Substring($i)\n"
            "        '{0}|{1}|{2}' -f $_.TimeCreated.ToString('yyyy-MM-dd HH:mm'), "
            "$d['SubjectUserName'], $dep; break } }\n"
            "  }\n"
            "}")
        try:
            kq = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True, timeout=25)
            for dong in (kq.stdout or "").splitlines():
                phan = dong.split("|", 2)
                if len(phan) == 3 and not phan[1].endswith("$"):  # bỏ tài khoản máy
                    ket_qua.append({"luc": phan[0], "tai_khoan": phan[1],
                                    "duong": phan[2]})
                if len(ket_qua) >= 40:
                    break
        except Exception:
            ket_qua = []
    _nas_nk_cache = (time.time(), ket_qua)
    return ket_qua


@app.get("/nas", response_class=HTMLResponse)
def nas_trang(request: Request, user: dict = Depends(lay_user), chua_ok: int = 0):
    """Ổ NAS công ty (01/08/2026, user chốt: mọi người đã đăng nhập đều thấy).
    Trình duyệt KHÔNG mở được đường dẫn SMB trực tiếp (chặn file://) → trang này
    đưa đường dẫn + nút copy/mở nhanh + hướng dẫn map ổ."""
    cac_duong = _nas_cac_duong()
    if not cac_duong:
        raise HTTPException(404, "Chưa cấu hình NAS_DUONG_DAN trong .env.")
    # IP server lấy từ chính đường dẫn share đầu tiên (\\IP\Ten)
    khop = re.match(r"^\\\\([^\\]+)", cac_duong[0])
    nas_ip = khop.group(1) if khop else ""
    # "idx" giữ ĐÚNG vị trí trong cac_duong (không phải vị trí sau khi lọc) —
    # /nas/cai-dat/{so} đọc lại cac_duong đầy đủ nên link phải trỏ đúng chỉ số gốc.
    thay_duoc = set(_nas_o_thay_duoc(user["level"]))
    o_dia = [{"duong": d, "idx": i,
              "ten": (ten_o := d.rstrip("\\").split("\\")[-1] or "NAS"),
              "chu": _NAS_CHU_O[i] if i < len(_NAS_CHU_O) else "",
              "smb": f"smb://{nas_ip}/{quote(ten_o)}" if nas_ip else "",
              "dl": _nas_thong_tin_o(d) if _nas_dong_bo_bat() else None}
             for i, d in enumerate(cac_duong) if i in thay_duoc]
    # Nhật ký xóa/đổi tên: CHỈ Manager+ thấy, và chỉ khi chạy trên server thật
    nhat_ky = (_nas_nhat_ky_xoa()
               if user["level"] >= 4 and _nas_dong_bo_bat() else None)
    return templates.TemplateResponse(request, "nas.html", {
        "user": user, "o_dia": o_dia, "nas_ip": nas_ip,
        # tt_nas luôn 'tat': mạch đồng bộ tài khoản Windows chưa mang sang v2
        # (thuộc gateway/IAM) → khung "Tài khoản của bạn" + nút Cài đặt tự ẩn,
        # trang chỉ đường như hệ cũ khi chưa bật đồng bộ.
        "dong_bo_bat": False, "chua_ok": chua_ok, "nhat_ky": nhat_ky,
        "tt_nas": "tat",
        "nas_web": os.getenv("NAS_WEB", "").strip()})  # có web UI thì thêm nút mở


_NAS_CHU_O = "YZXWVU"  # share thứ i gắn chữ ổ thứ i — NAS1=Y:, Video=Z: (khớp máy Owner)


@app.get("/nas/cai-dat/{so}")
def nas_cai_dat(so: int, user: dict = Depends(lay_user)):
    """File .bat CÀI MỘT Ổ vào This PC (04/08/2026: NÚT NÀO CÀI Ổ ĐÓ). File chạy
    2 nhịp: máy ĐÃ có tài khoản đúng trong Credential Manager → gắn ổ luôn; máy
    lần đầu → gỡ sạch phiên + credential cũ (tránh lỗi 1219) → cmdkey /pass TỰ HỎI
    mật khẩu (file không bao giờ chứa mật khẩu) → gắn ổ /persistent:yes.
    ASCII không dấu (bat chạy codepage OEM, tiếng Việt có dấu sẽ vỡ).
    V2: bỏ van chặn 'tài khoản NAS chưa sẵn sàng' của hệ cũ — van đó đọc sổ
    nas_sync (chưa mang sang); .bat vẫn an toàn vì tự hỏi mật khẩu lúc chạy."""
    cac_duong = _nas_cac_duong()
    if not (0 <= so < len(cac_duong) and so < len(_NAS_CHU_O)):
        raise HTTPException(404, "Không có ổ NAS này.")
    duong, chu = cac_duong[so], _NAS_CHU_O[so]
    ten_o = duong.rstrip("\\").split("\\")[-1] or "NAS"
    ten_file = re.sub(r"[^A-Za-z0-9_-]+", "-", ten_o)
    khop = re.match(r"^\\\\([^\\]+)", duong)
    ip = khop.group(1) if khop else ""
    # 05/08/2026 (bug "ấn 1 ổ thì ổ còn lại bị mất"): khối quét-sạch xóa MỌI kết
    # nối NAS trên máy trước khi gắn lại → phải gắn lại LUÔN mọi ổ user này thấy.
    anh_em = [i for i in _nas_o_thay_duoc(user["level"]) if i != so]
    bat_noi_dung = (
        "@echo off\r\n"
        f"echo === CAI O {ten_o} ({chu}:) VAO THIS PC - chay mot lan la xong ===\r\n"
        f"rem May da co tai khoan dung -> khoi hoi mat khau, gan o luon\r\n"
        f"cmdkey /list:{ip} | findstr /c:\"{ip}\\{user['ten']}\" >nul 2>&1\r\n"
        "if %errorlevel%==0 goto gan_o\r\n"
        ":nhap_mk\r\n"
        "echo Se go tai khoan cu tren may (neu co) va hoi MAT KHAU OUTLIERY cua ban.\r\n"
        "echo LUU Y: dong het file dang mo tren o NAS truoc khi tiep tuc!\r\n"
        "pause\r\n"
        "net use * /delete /y >nul 2>&1\r\n"
        f"cmdkey /delete:Domain:target={ip} >nul 2>&1\r\n"
        f"cmdkey /delete:{ip} >nul 2>&1\r\n"
        f"echo Nhap MAT KHAU OUTLIERY cua ban ({user['ten']}) roi Enter:\r\n"
        f"cmdkey /add:{ip} /user:{ip}\\{user['ten']} /pass\r\n"
        ":gan_o\r\n"
        "rem QUET SACH ket noi toi server truoc khi gan (04/08: phien nhanvien cu con\r\n"
        "rem song la o moi DI NHO danh tinh cu -> Manager co quyen van khong xoa duoc)\r\n"
        + "".join(f"net use {c}: /delete /y >nul 2>&1\r\n" for c in _NAS_CHU_O[:len(cac_duong)])
        + "".join(f"net use \"{d}\" /delete /y >nul 2>&1\r\n" for d in cac_duong)
        + f"net use {chu}: \"{duong}\" /persistent:yes\r\n"
        "if %errorlevel%==0 goto xong\r\n"
        "rem Ket noi truot: tai khoan luu tren may cu/sai -> lam lai tu dau DUNG MOT LAN\r\n"
        "if \"%dalap%\"==\"1\" goto bo_tay\r\n"
        "set dalap=1\r\n"
        "echo Ket noi chua duoc - tai khoan luu tren may co the cu/sai, lam lai...\r\n"
        "goto nhap_mk\r\n"
        ":bo_tay\r\n"
        "echo.\r\n"
        "echo VAN CHUA DUOC: kiem tra tai khoan NAS voi quan tri (mat khau du manh,\r\n"
        "echo tai khoan Windows da duoc cap) roi TAI LAI file nay va chay lai.\r\n"
        "goto het\r\n"
        ":xong\r\n"
        "rem Gan lai CAC O KHAC ban dang dung (vua bi quet sach o buoc tren) - am\r\n"
        "rem tham, khong bao loi rieng vi day la phu, o chinh da chac chan gan duoc\r\n"
        + "".join(f"net use {_NAS_CHU_O[j]}: \"{cac_duong[j]}\" /persistent:yes >nul 2>&1\r\n"
                  for j in anh_em)
        + f"start \"\" {chu}:\\\r\n"
        "echo.\r\n"
        f"echo XONG! O {ten_o} da nam trong This PC (o {chu}:) - tu nay chi can click dup.\r\n"
        + ("echo Cac o khac ban dang dung cung da duoc gan lai luon, khong can bam\r\n"
           "echo Cai dat rieng cho tung o nua.\r\n" if anh_em else "")
        + "echo Neu bao \"already in use\": chu o dang bi chiem - mo file nay bang\r\n"
        f"echo Notepad, doi chu {chu}: thanh chu khac roi chay lai.\r\n"
        ":het\r\n"
        "pause\r\n")
    return Response(bat_noi_dung, media_type="application/x-bat", headers={
        "Content-Disposition": f'attachment; filename="Cai-o-{ten_file}.bat"'})


# ═══════════════ CHẤM CÔNG — 2 tín hiệu từ trình duyệt (khối JS trong base.html) ═══════════════

@app.post("/api/nhip")
def api_nhip(user: dict = Depends(lay_user)):
    ghi_nhan(user["ten"], "nhip")
    return Response(status_code=204)


@app.post("/api/nhip-thoat")
def api_nhip_thoat(user: dict = Depends(lay_user)):
    ghi_nhan(user["ten"], "dong_app")
    return Response(status_code=204)


# ═══════════════ VAULT — kho tài khoản số, CHỈ OWNER (31/07/2026) ═══════════════
# Hai cửa: claims Owner (yeu_cau_owner) + mật khẩu chủ riêng (vault.mo_bang_master).
# Bản rõ chỉ tồn tại trong RAM khi vault mở; đĩa luôn là bản mã AES-GCM.
# Đường /khoi-phuc (đặt lại mật khẩu đăng nhập Owner bằng safekey) KHÔNG mang sang
# — nó đổi mật khẩu trong sổ user nên thuộc IAM/gateway (việc treo, xem README).

TEN_NHOM_VAULT = {"google": "Google/Kênh", "adsense": "AdSense", "proxy": "Proxy/IP",
                  "email": "Email", "the": "Thẻ/Ngân hàng", "khac": "Khác"}


# nhãn tiếng Việt cho mã hành động trong sổ kiểm toán (mã máy giữ nguyên trong CSV)
NHAN_AUDIT = {
    "tao_vault": "Tạo vault", "mo_vault": "Mở vault", "khoa_vault": "Khóa vault",
    "mo_vault_SAI_mat_khau": "Mở vault SAI mật khẩu",
    "them_muc": "Thêm mục", "sua_muc": "Sửa mục", "xoa_muc": "Xóa mục",
    "xem_mat_khau": "Xem mật khẩu",
    "khoi_phuc_master": "Đổi mật khẩu chủ bằng safekey",
    "khoi_phuc_master_SAI_safekey": "Cứu vault SAI safekey",
    "dat_lai_login_owner": "Đặt lại đăng nhập Owner bằng safekey",
    "dat_lai_login_SAI_safekey": "Đặt lại đăng nhập SAI safekey",
    "dat_lai_login_TU_CHOI_khong_phai_owner": "Đặt lại đăng nhập bị TỪ CHỐI (không phải Owner)",
}


def _doc_audit_moi(n: int = 40) -> list[dict]:
    p = Path(os.getenv("VAULT_DIR", "vault")) / "audit.csv"
    if not p.is_file():
        return []
    ra = []
    for d in list(csv.reader(p.open(encoding="utf-8-sig")))[1:][-n:][::-1]:
        if len(d) >= 4:
            ra.append({"luc": d[0], "ai": d[1], "hanh_dong": NHAN_AUDIT.get(d[2], d[2]),
                       "muc": d[3], "canh": "SAI" in d[2] or "TU_CHOI" in d[2]})
    return ra


def _ctx_vault(request: Request, user: dict, **them) -> dict:
    return {"user": user, "ten_nhom": TEN_NHOM_VAULT,
            "tu_khoa_phut": vault.TU_KHOA_GIAY // 60,
            "so_safekey": vault.so_safekey_con_lai(),
            # nhắc HTTP: mật khẩu chủ đi trần trong LAN cho tới khi bật HTTPS
            "canh_bao_http": request.url.scheme != "https"
                             and request.client and request.client.host not in ("127.0.0.1", "::1"),
            **them}


@app.get("/vault", response_class=HTMLResponse)
def vault_trang(request: Request, user: dict = Depends(yeu_cau_owner)):
    """Trang Vault. 3 trạng thái: chưa tạo → khóa → mở (bản rõ chỉ khi đang mở)."""
    if not vault.da_tao():
        return templates.TemplateResponse(request, "vault.html",
                                          _ctx_vault(request, user, trang_thai="chua_tao"))
    if not vault.dang_mo():
        return templates.TemplateResponse(request, "vault.html",
                                          _ctx_vault(request, user, trang_thai="khoa"))
    return templates.TemplateResponse(request, "vault.html", _ctx_vault(
        request, user, trang_thai="mo", muc=vault.doc_muc() or [], audit=_doc_audit_moi(),
        safekey_bang=vault.trang_thai_safekey()))


@app.post("/vault/tao", response_class=HTMLResponse)
def vault_tao(request: Request, master: str = Form(...), master2: str = Form(...),
              user: dict = Depends(yeu_cau_owner)):
    """Tạo vault + cấp 10 safekey. Safekey trả về template hiện ĐÚNG MỘT LẦN — KHÔNG
    lưu bản rõ, KHÔNG log, không có đường xem lại."""
    try:
        if master != master2:
            raise ValueError("Hai lần nhập mật khẩu chủ không khớp.")
        safekeys = vault.tao_vault(master, user["ten"])
    except ValueError as e:
        return templates.TemplateResponse(request, "vault.html", _ctx_vault(
            request, user, trang_thai="chua_tao", loi=str(e)))
    return templates.TemplateResponse(request, "vault.html", _ctx_vault(
        request, user, trang_thai="vua_tao", safekeys=safekeys))


@app.post("/vault/mo", response_class=HTMLResponse)
def vault_mo(request: Request, master: str = Form(...), user: dict = Depends(yeu_cau_owner)):
    if not vault.mo_bang_master(master, user["ten"]):
        return templates.TemplateResponse(request, "vault.html", _ctx_vault(
            request, user, trang_thai="khoa", loi="Mật khẩu chủ không đúng."))
    return RedirectResponse("/vault", status_code=303)


@app.post("/vault/khoa")
def vault_khoa(user: dict = Depends(yeu_cau_owner)):
    vault.khoa(user["ten"])
    return RedirectResponse("/vault", status_code=303)


@app.post("/vault/khoi-phuc-master", response_class=HTMLResponse)
def vault_khoi_phuc_master(request: Request, safekey: str = Form(...),
                           master_moi: str = Form(...), master_moi2: str = Form(...),
                           user: dict = Depends(yeu_cau_owner)):
    """Quên mật khẩu chủ: 1 safekey mở được DEK → đặt mật khẩu chủ mới. Safekey vô hiệu."""
    try:
        if master_moi != master_moi2:
            raise ValueError("Hai lần nhập mật khẩu chủ mới không khớp.")
        if not vault.khoi_phuc_master(safekey, master_moi, user["ten"]):
            raise ValueError("Safekey không đúng hoặc đã dùng rồi.")
    except ValueError as e:
        return templates.TemplateResponse(request, "vault.html", _ctx_vault(
            request, user, trang_thai="khoa", loi=str(e)))
    return RedirectResponse("/vault", status_code=303)


@app.post("/vault/muc")
def vault_muc(id: str = Form(""), nhom: str = Form(...), ten: str = Form(...),
              tai_khoan: str = Form(""), mat_khau: str = Form(""), ghi_chu: str = Form(""),
              user: dict = Depends(yeu_cau_owner)):
    try:
        vault.them_hoac_sua_muc(user["ten"], id, nhom, ten,
                                tai_khoan=tai_khoan, mat_khau=mat_khau, ghi_chu=ghi_chu)
    except PermissionError:
        return RedirectResponse("/vault", status_code=303)   # vault vừa tự khóa → về form mở
    except ValueError as e:
        raise HTTPException(422, str(e))
    return RedirectResponse("/vault", status_code=303)


@app.post("/vault/xoa-muc")
def vault_xoa_muc(id: str = Form(...), user: dict = Depends(yeu_cau_owner)):
    try:
        vault.xoa_muc(user["ten"], id)
    except PermissionError:
        raise HTTPException(423, "Vault đang khóa.")
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@app.post("/vault/xem")
def vault_xem(id: str = Form(...), user: dict = Depends(yeu_cau_owner)):
    """Lộ mật khẩu MỘT mục — mỗi lần gọi ghi 1 dòng audit (ai xem gì, lúc nào)."""
    try:
        return {"mat_khau": vault.xem_mat_khau(user["ten"], id)}
    except PermissionError:
        raise HTTPException(423, "Vault đang khóa.")
    except ValueError as e:
        raise HTTPException(404, str(e))
