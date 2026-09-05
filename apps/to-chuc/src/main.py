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
import io
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import (Depends, FastAPI, File, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.responses import (FileResponse, HTMLResponse, RedirectResponse,
                               Response)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from nen.common import xac_thuc_app

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/to-chuc
ROOT = _APP_DIR.parents[1]                               # D:\AI AGENT OUTLIERY
# Luật 6: dữ liệu tách khỏi code. Đặt TRƯỚC khi import các module (chúng đọc env
# lúc gọi hàm nên setdefault ở đây là đủ; conftest test đè lại bằng monkeypatch).
os.environ.setdefault("CHAM_CONG_DIR", str(ROOT / "data" / "to-chuc" / "db" / "cham-cong"))
os.environ.setdefault("VAULT_DIR", str(ROOT / "data" / "vault"))
# Nguồn KPI (đổi 31/08, tab giám sát B3 bắt được "đã nối mà mất"): thời V2-song-
# song default trỏ hộp thư data/to-chuc/nguon/ KHÔNG tồn tại (KPI "—" chờ nối);
# cutover 22/08 xong thì PlannerY + Content V3 cùng máy LÀ nguồn thật → trỏ
# THẲNG, chỉ-đọc, app không bao giờ ghi vào các file này. SpeakY đã khai tử —
# giữ placeholder không tồn tại, KPI speaky hiện "—" là đúng sự thật.
os.environ.setdefault("PLANNERY_PLAN", str(ROOT / "data" / "plannery" / "plan.json"))
os.environ.setdefault("CONTENT_HISTORY", str(ROOT / "data" / "content-ultimate" / "admin" / "history.jsonl"))
os.environ.setdefault("SPEAKY_JOBS_LOG", str(ROOT / "data" / "to-chuc" / "nguon" / "speaky-jobs_log.csv"))
os.environ.setdefault("BAO_CAO_DIR", str(ROOT / "data" / "data-analytics" / "db" / "bao-cao-lich-su"))
# HR Hub + Finance Hub (DE.md mục 10) — 4 store mới, đều khai du_lieu trong apps.json
os.environ.setdefault("CHAM_CONG_CHOT_DIR", str(ROOT / "data" / "to-chuc" / "db" / "cham-cong-chot"))
os.environ.setdefault("KPI_DANH_GIA_DIR", str(ROOT / "data" / "to-chuc" / "db" / "kpi-danh-gia"))
os.environ.setdefault("SO_THU_CHI_DIR", str(ROOT / "data" / "to-chuc" / "db" / "so-thu-chi"))
os.environ.setdefault("MUC_TIEU_PATH", str(ROOT / "data" / "to-chuc" / "db" / "muc-tieu.json"))

from src import (chi_phi_ngach, don_vi_kinh_te, kpi_danh_gia, lich_tai_chinh,
                 luong, tai_chinh, tai_san, tu_dong, vault)           # noqa: E402
from src.cham_cong import doc_ngay as cc_doc_ngay        # noqa: E402
from src.cham_cong import (bang_cong_thang, chot_ky, doc_chot, ghi_nhan,  # noqa: E402
                           gio_chu, tong_gio)
from src.kpi import kpi_plannery, ky_hien_tai, tong_hop_kpi  # noqa: E402

PHIEN_BAN = "2.0.0"
app = FastAPI(title="Tổ chức v2")
from nen.common import danh_ba, nas_sync, nhat_ky  # noqa: E402 — danh bạ + NAS + log P4
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


def _fmt_vnd(v) -> str:
    """2592000 → '2.592.000 ₫' (kiểu VN); không phải số → '—'."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    s = f"{abs(v):,.0f}".replace(",", ".")
    return ("−" if v < 0 else "") + s + " ₫"


# Vendor chart (Frappe Charts) — LAN không ra Internet nên chép về, không CDN.
# Xem src/static/vendor/NGUON.md.
app.mount("/to-chuc-static", StaticFiles(directory=str(_APP_DIR / "src" / "static")),
          name="to-chuc-static")

def _fmt_theo_te(v, tien_te="VND") -> str:
    """Hiển thị số tiền ĐÚNG ký hiệu của tiền tệ đó: USD → $12,116 ·
    VND → 23.500.000 ₫. Trước đây mọi số dư đều mang dấu $ kể cả ví tiền đồng."""
    return _fmt_tien(v) if (tien_te or "VND").upper() != "VND" else _fmt_vnd(v)


templates.env.filters["tien"] = _fmt_tien
templates.env.filters["vnd"] = _fmt_vnd
templates.env.filters["theo_te"] = _fmt_theo_te
templates.env.filters["gio_chu"] = gio_chu


# ---------- claims (thay auth hệ cũ) ----------

def lay_user(request: Request,
             x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
             x_remote_role: str = Header(""), x_remote_dept: str = Header("")) -> dict:
    """User = claims gateway tiêm (an toàn vì app bind 127.0.0.1 — chỉ gateway tới
    được; header giả từ trình duyệt đã bị gateway vứt). Dept được proxy quote()
    (header phải ASCII) → unquote lại để RBAC so đúng CHUỖI GỐC tiếng Việt.
    ĐIỂM HỨNG CHẤM CÔNG (như auth.lay_user cổng 8000 cũ): mọi request có danh
    tính đều ghi hiện diện — bọc kín, chấm công hỏng không được chặn request."""
    if not xac_thuc_app.duoc_tin(request, "TC_TRUST_PROXY"):
        # SIẾT 05/09/2026 (sổ docs/bao-mat-internet.md muc A1): trước đây chỉ cần
        # header CÓ MẶT là tin → cổng 9103 lộ ra là curl thành Owner, đọc vault +
        # lương + hồ sơ nhân sự. Nay đòi CẢ TC_TRUST_PROXY=1 LẪN client loopback.
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
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


def yeu_cau_manager(user: dict = Depends(lay_user),
                    x_remote_actions: str = Header("")) -> dict:
    """Trang KPI: hành động 'kpi' trong X-Remote-Actions (Permissions v2 — mặc
    định Manager+ theo luật tầng nền, tick lẻ/acting chảy sang ngay lượt sau).
    App CHỈ TIN CỜ gateway phát; thiếu header → fail-closed."""
    if "kpi" not in _cac_khu(x_remote_actions):
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


@app.get("/api/suc-khoe")
async def api_suc_khoe():
    """Sức khỏe SÂU (B3 giám sát 31/08, khuôn nen/common/suc_khoe.py).

    kpi-nguon: KPI đọc nguồn CHỈ-ĐỌC ngoài app — nguồn chết thì KPI hiện '—'
    (van chống bịa) nhưng không ai biết vì sao; đây khai thẳng: chưa nối (env
    chưa đặt) là canh_bao, ĐÃ nối mà file mất là loi. Default env khớp kpi.py.
    """
    import os
    from pathlib import Path

    from nen.common import suc_khoe

    def _kpi_nguon():
        nguon = [("PLANNERY_PLAN", "plannery-plan.json"),
                 ("CONTENT_HISTORY", "content-history.jsonl"),
                 ("BAO_CAO_DIR", "bao-cao-lich-su")]
        chua_noi, mat = [], []
        for env, mac_dinh in nguon:
            gia_tri = os.getenv(env, "").strip()
            if not gia_tri:
                if not Path(mac_dinh).exists():
                    chua_noi.append(env)
            elif not Path(gia_tri).exists():
                mat.append(f"{env}={gia_tri}")
        if mat:
            return "loi", ("nguồn KPI ĐÃ nối mà mất: " + "; ".join(mat)
                           + " — KPI đang hiện '—'")
        if chua_noi:
            return "canh_bao", ("nguồn KPI chưa nối (env chưa đặt trong "
                                "start-all): " + ", ".join(chua_noi)
                                + " — KPI hiện '—' cho phần đó")
        return "ok", f"{len(nguon)}/{len(nguon)} nguồn KPI đọc được"

    return suc_khoe.bao_cao("to-chuc", PHIEN_BAN, [("kpi-nguon", _kpi_nguon)])


@app.get("/api/kiem/{ma}")
async def api_kiem(ma: str, request: Request):
    """CỬA KIỂM LOGIC (02/09 — "mỗi logic một sơ đồ"): trả SỐ ĐO THẬT của một
    logic nghiệp vụ, CHỈ-ĐỌC 0 quota. Phép nào cần ghi thì ghi vào THƯ MỤC TẠM
    riêng (tuyệt đối không đụng sổ tiền / chấm công thật). Chỉ loopback."""
    from src import kiem
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(404)
    ham = kiem.CAC_MA.get(ma)
    if ham is None:
        raise HTTPException(404, f"không có mã kiểm {ma!r}")
    return ham()


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
                if ho_so.get("trang_thai") == "nghi":
                    continue     # ĐÃ THÔI VIỆC: ra khỏi bảng KPI/chấm công/phép
                                 # (hồ sơ vẫn còn ở mục 'Đã thôi việc' tab Accounts;
                                 #  bản ghi chấm công cũ của họ KHÔNG bị xóa)
                ds.append({"ten": tk["ten"], "bo_phan": tk.get("bo_phan") or "",
                           "ho_ten": ho_so.get("ho_ten", ""),
                           # mã NS + vị trí: bảng lương/phiếu lương cần hiển thị,
                           # và 'ma' rỗng = tài khoản hệ thống (không trả lương)
                           "ma": ma_ns, "vi_tri": ho_so.get("vi_tri", ""),
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
             "thoi_viec": sum(1 for h in (ho_so or []) if h.get("trang_thai") == "nghi")
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
                  tu: str = "", den: str = "", loai: str = "", vi: str = "",
                  kenh: str = "", muc_tieu: str = "", danh_muc: str = "",
                  q: str = "", ky_luong: str = "", phan_bo: str = "doanh_thu",
                  user: dict = Depends(yeu_cau_finance)):
    """Finance Hub — 4 tab theo mockup finance-hub.html: Ledger (sổ chỉ-thêm +
    đảo) · Goals (mục tiêu) · Categories (rules CSV + tổng) · Channel P&L."""
    if tab not in ("ledger", "goals", "categories", "pnl", "wallets", "subs",
                   "payroll", "dashboard", "ngach", "auto", "assets"):
        tab = "ledger"
    thang = _thang_hop_le(thang)

    so = tai_chinh.doc_so()
    loc = {"thang": thang, "tu": tu, "den": den, "loai": loai, "vi": vi,
           "kenh": kenh, "muc_tieu": muc_tieu, "danh_muc": danh_muc, "q": q}
    so_thang = tai_chinh.loc_so(**loc)
    da_dao = {b.get("tham_chieu") for b in so if b.get("loai") == "dao"}

    ds_kenh = danh_ba.liet_ke("kenh")
    kenh_cua = {k["ma"]: k for k in ds_kenh}
    ten_ngach = {n["ma"]: n.get("ten_chuan", "") for n in danh_ba.liet_ke("ngach")}

    muc_tieu = tai_chinh.doc_muc_tieu()
    mt_tong = tai_chinh.tong_hop_muc_tieu()
    return templates.TemplateResponse(request, "finance.html", {
        "user": user, "tab": tab, "thang": thang, "loc": loc,
        "hom_nay": date.today().isoformat(),
        "tong": tai_chinh.tong_thang(thang), "so_thang": so_thang, "da_dao": da_dao,
        "danh_muc": tai_chinh.doc_danh_muc(),
        "dm_tong": tai_chinh.tong_hop_danh_muc(thang),
        "muc_tieu": muc_tieu, "mt_tong": mt_tong,
        "ds_kenh": ds_kenh, "kenh_cua": kenh_cua, "ten_ngach": ten_ngach,
        "pnl": tai_chinh.pnl_theo_kenh(thang),
        "phan_bo": phan_bo,
        "pnl_pb": tai_chinh.pnl_phan_bo(thang, phan_bo) if tab == "pnl" else None,
        "dvkt": don_vi_kinh_te.don_vi_kinh_te(thang) if tab == "pnl" else None,
        "ngan_sach": tai_chinh.ngan_sach_ky(thang) if tab == "goals" else None,
        "doi_chieu": (tai_chinh.doi_chieu_vi(thang, {}) if tab == "wallets" else None),
        "da_chot_ky": tai_chinh.doc_chot_ky(thang),
        "tien_api": tu_dong.tien_api_thang(thang) if tab == "auto" else None,
        **(_du_lieu_tai_san() if tab == "assets" else {}),
        "luat_goi_y": tu_dong.doc_luat_goi_y() if tab in ("auto", "ledger") else None,
        "don_gia_api": tu_dong.doc_don_gia() if tab == "auto" else None,
        "danh_muc_vi": tai_chinh.doc_danh_muc_vi(),
        "so_du_vi": tai_chinh.so_du_vi(), "kha_dung": tai_chinh.tien_kha_dung(),
        "kha_dung_vnd": tai_chinh.tien_kha_dung_vnd(),
        "quy_vnd": tai_chinh.quy_vnd,
        "ty_gia_usd": tai_chinh.ty_gia_ngay(date.today().isoformat(), "USD"),
        "dich_vu": tai_chinh.doc_dich_vu(), "den_han": tai_chinh.den_han(),
        "thue_bao_thang": tai_chinh.chi_phi_thue_bao_thang(),
        "tiet_kiem": tai_chinh.tiet_kiem_neu_bo(),
        "la_owner": user["level"] >= 5,
        "moc_ky": lich_tai_chinh.moc_ky(_ky_truoc(thang)),
        "ky_truoc": _ky_truoc(thang),
        "bd": _bieu_do_kem_ngach(thang) if tab == "dashboard" else None,
        **(_du_lieu_tong_quan(thang) if tab == "dashboard" else {}),
        **_du_lieu_luong(tab, ky_luong),
        **_du_lieu_ngach(tab, ky_luong)})


@app.post("/finance/but-toan")
def finance_but_toan(ngay: str = Form(...), danh_muc: str = Form(...),
                     so_tien: str = Form(...), muc_tieu: str = Form(...),
                     kenh_ma: str = Form(""), chung_tu: str = Form(""),
                     ghi_chu: str = Form(""), vi: str = Form(""),
                     ty_gia: str = Form(""), tep: list[UploadFile] = File(default=[]),
                     user: dict = Depends(yeu_cau_finance)):
    # A3 — đọc + VALIDATE tệp TRƯỚC khi ghi sổ: tệp sai thì sổ không nhận dòng rác
    nap = [(t.filename, t.file.read()) for t in tep if t and t.filename]
    try:
        sach = tai_chinh.kiem_tep(nap)          # sai tệp → 422, sổ chưa ghi gì
        b = tai_chinh.them_but_toan(user["ten"], ngay, danh_muc, so_tien,
                                    muc_tieu, kenh_ma, chung_tu, ghi_chu, vi,
                                    ty_gia or None,
                                    tep_dinh_kem=[t for t, _ in sach])
        if sach:
            tai_chinh.luu_chung_tu(b["id"], sach)   # id có rồi mới biết ghi vào đâu
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "but_toan",
                f"{b['id']} {b['loai']} {b['danh_muc']} {b['so_tien']}")
    return RedirectResponse(f"/finance?tab=ledger&thang={ngay[:7]}", status_code=303)


@app.post("/finance/dich-vu")
def finance_dich_vu(ten: str = Form(...), nhom: str = Form(...), phi: str = Form(...),
                    tien_te: str = Form("VND"), chu_ky: str = Form("thang"),
                    ngay_gia_han: str = Form(...), danh_muc: str = Form(...),
                    vi: str = Form(...), id: str = Form(""),
                    nha_cung_cap: str = Form(""), tu_dong_gia_han: str = Form(""),
                    trang_thai: str = Form("dang_dung"), kenh_ma: str = Form(""),
                    vault_id: str = Form(""), ghi_chu: str = Form(""),
                    user: dict = Depends(yeu_cau_finance)):
    try:
        dv = tai_chinh.luu_dich_vu(
            user["ten"], ten, nhom, phi, tien_te, chu_ky, ngay_gia_han, danh_muc,
            vi, id, nha_cung_cap, bool(tu_dong_gia_han), trang_thai, kenh_ma,
            vault_id, ghi_chu)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "dich_vu", f"{dv['id']} {dv['ten']} {dv['trang_thai']}")
    return RedirectResponse("/finance?tab=subs", status_code=303)


@app.post("/finance/dich-vu/trang-thai")
def finance_dich_vu_trang_thai(id: str = Form(...), trang_thai: str = Form(...),
                               user: dict = Depends(yeu_cau_finance)):
    """Đánh dấu 'sắp bỏ' (quyết định cắt chi) hoặc dùng lại. App KHÔNG tự hủy dịch
    vụ — hủy là việc tay trên trang nhà cung cấp, ở đây chỉ ghi nhận quyết định."""
    dv = next((d for d in tai_chinh.doc_dich_vu() if d.get("id") == id), None)
    if dv is None:
        raise HTTPException(404, "Không có dịch vụ này.")
    try:
        tai_chinh.luu_dich_vu(
            user["ten"], dv["ten"], dv["nhom"], dv["phi"], dv["tien_te"],
            dv["chu_ky"], dv["ngay_gia_han"], dv["danh_muc"], dv["vi"], id=id,
            nha_cung_cap=dv.get("nha_cung_cap", ""),
            tu_dong_gia_han=dv.get("tu_dong_gia_han", True), trang_thai=trang_thai,
            kenh_ma=dv.get("kenh_ma", ""), vault_id=dv.get("vault_id", ""),
            ghi_chu=dv.get("ghi_chu", ""))
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "dich_vu_trang_thai", f"{dv['ten']} {trang_thai}")
    return RedirectResponse("/finance?tab=subs", status_code=303)


@app.post("/finance/dich-vu/ghi")
def finance_dich_vu_ghi(id: str = Form(...), muc_tieu: str = Form(...),
                        so_tien: str = Form(""), ngay: str = Form(""),
                        user: dict = Depends(yeu_cau_finance)):
    """Ghi bút toán cho một kỳ thuê bao rồi đẩy hạn. Số tiền thật có thể khác
    phí khai — cho sửa, KHÔNG để máy tự quyết."""
    dv = next((d for d in tai_chinh.doc_dich_vu() if d.get("id") == id), None)
    if dv is None:
        raise HTTPException(404, "Không có dịch vụ này.")
    try:
        b = tai_chinh.them_but_toan(
            user["ten"], ngay or date.today().isoformat(), dv["danh_muc"],
            so_tien or dv["phi"], muc_tieu, dv.get("kenh_ma", ""),
            chung_tu="", ghi_chu=f"{dv['ten']} — kỳ {dv['ngay_gia_han']}",
            vi=dv["vi"], nguon="thue_bao")
        tai_chinh.day_gia_han(id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "thue_bao_ghi", f"{dv['ten']} {b['id']}")
    return RedirectResponse("/finance?tab=subs", status_code=303)


def _ky_truoc(thang: str) -> str:
    """Kỳ mà lịch tài chính đang nói tới: các mốc của kỳ N rơi vào tháng N+1."""
    nam, th = int(thang[:4]), int(thang[5:7])
    return f"{nam - 1:04d}-12" if th == 1 else f"{nam:04d}-{th - 1:02d}"


def _du_lieu_tai_san() -> dict:
    """Tab Tài sản. Danh sách người lấy từ IAM để biết ai đã nghỉ mà còn giữ đồ."""
    ds_nguoi, _ = _ds_nguoi_iam()
    return {"tai_san": tai_san.tong_hop(ds_nguoi or []),
            "nhom_ts": tai_san.NHOM, "nhom_vat_ly": tai_san.NHOM_VAT_LY,
            "ds_nguoi_ts": ds_nguoi or []}


def _bieu_do_kem_ngach(thang: str) -> dict:
    """Biểu đồ dashboard + cột chồng chi phí ngách (mockup BD5). Ngách đọc từ
    PlannerY nên có thể chết — hỏng thì bỏ đúng biểu đồ đó, không vỡ trang."""
    bd = tai_chinh.du_lieu_bieu_do(thang)
    bd["ngach_nhan"], bd["ngach_nhan_cong"], bd["ngach_tien_mat"] = [], [], []
    try:
        ds_nguoi, _ = _ds_nguoi_iam()
        cp = chi_phi_ngach.chi_phi_ngach(_ky_truoc(thang), ds_nguoi or [])
        if not cp["thieu_nguon"]:
            for d in cp["dong"]:
                bd["ngach_nhan"].append(d["ngach_ma"])
                bd["ngach_nhan_cong"].append(round(d["nhan_cong"]))
                bd["ngach_tien_mat"].append(round(d["tien_mat"]))
    except Exception:
        pass
    return bd


def _du_lieu_tong_quan(thang: str) -> dict:
    """Khối A1 · B3 · D2 · TQ của tab Tổng quan. Mỗi việc trong "cần làm" phải
    ĐẾM ĐƯỢC từ dữ liệu thật — không liệt kê việc của module chưa có."""
    can_lam = []
    thieu_ct = [b for b in tai_chinh.doc_so()
                if b.get("loai") != "dao" and not b.get("tep_dinh_kem")
                and not b.get("chung_tu")]
    if thieu_ct:
        can_lam.append({"muc": "gap", "chu": f"{len(thieu_ct)} bút toán thiếu chứng từ",
                        "di": "/finance?tab=ledger", "nhan": "Mở sổ"})
    qua_han = [d for d in tai_chinh.den_han() if d.get("qua_han")]
    if qua_han:
        can_lam.append({"muc": "gap",
                        "chu": f"{len(qua_han)} thuê bao quá hạn chưa ghi",
                        "di": "/finance?tab=subs", "nhan": "Xem"})
    ky_luong_truoc = _ky_truoc(thang)
    ds_nguoi, _ = _ds_nguoi_iam()
    bl = luong.bang_luong(ky_luong_truoc, ds_nguoi or [])
    thieu_xl = [d for d in bl["dong"] if d["thieu"]]
    if thieu_xl:
        can_lam.append({"muc": "canh",
                        "chu": f"{len(thieu_xl)} người chưa đủ dữ liệu lương kỳ {ky_luong_truoc}",
                        "di": f"/finance?tab=payroll&ky_luong={ky_luong_truoc}",
                        "nhan": "Xem lương"})
    if bl["da_duyet"]:
        can_lam.append({"muc": "xong", "chu": f"Đã duyệt lương kỳ {ky_luong_truoc}",
                        "di": "", "nhan": ""})
    if not tai_chinh.ty_gia_ngay(date.today().isoformat(), "USD"):
        can_lam.append({"muc": "canh", "chu": "Chưa có tỷ giá USD hôm nay",
                        "di": "/finance?tab=wallets", "nhan": "Lấy tỷ giá"})
    return {"muc_dot": tai_chinh.muc_dot(thang), "can_lam": can_lam}


def _du_lieu_ngach(tab: str, ky: str) -> dict:
    if tab != "ngach":
        return {"chi_ngach": None}
    ds_nguoi, _ = _ds_nguoi_iam()
    return {"chi_ngach": chi_phi_ngach.chi_phi_ngach(_thang_hop_le(ky), ds_nguoi or [])}


def _du_lieu_luong(tab: str, ky: str) -> dict:
    """Chỉ tính khi ĐANG XEM tab Payroll — đọc IAM + chấm công + KPI không rẻ."""
    if tab != "payroll":
        return {"bang_luong": None, "ky_luong": ky}
    ky = _thang_hop_le(ky)
    ds_nguoi, iam_loi = _ds_nguoi_iam()
    bl = luong.bang_luong(ky, ds_nguoi or [])
    return {"ky_luong": ky, "iam_loi": iam_loi, "bang_luong": bl,
            "gio_lam_viec": luong.doc_gio_lam_viec(),
            "cong_ngach": _cong_theo_ngach(ky, ds_nguoi or [], bl)}


def _cong_theo_ngach(ky: str, ds_nguoi: list, bl: dict) -> list | None:
    """Khối D1b — ngày công mỗi người rải cho ngách nào (kiểm chứng số của D3).
    PlannerY chết → None để UI nói thẳng, không dựng bảng rỗng giả."""
    pc = chi_phi_ngach.phan_cong_ngach()
    if pc is None:
        return None
    don_gia = luong.don_gia_ngay(ky)
    ra = []
    for d in bl["dong"]:
        if not d["cong_chot"]:
            continue
        n = next((x for x in ds_nguoi if x.get("ten") == d["ten"]), {})
        ng = pc.get(n.get("planner_id") or "", [])
        ra.append({"ten": d["ten"], "ma": d["ma"], "ho_ten": d["ho_ten"],
                   "cong": d["cong_chot"], "ngach": ng,
                   "moi_ngach": d["cong_chot"] / len(ng) if ng else 0,
                   "don_gia": don_gia.get(d["ten"])})
    return ra


@app.post("/finance/luong/co-ban")
def finance_luong_co_ban(ten: str = Form(...), so_tien: str = Form(...),
                         ky: str = Form(""), user: dict = Depends(yeu_cau_finance)):
    try:
        luong.dat_luong_co_ban(user["ten"], ten, so_tien)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "luong_co_ban", f"{ten} {so_tien}")
    return RedirectResponse(f"/finance?tab=payroll&ky_luong={ky}", status_code=303)


@app.post("/finance/luong/dieu-chinh")
def finance_luong_dieu_chinh(ten: str = Form(...), ky: str = Form(...),
                             so_tien: str = Form(...), ly_do: str = Form(...),
                             user: dict = Depends(yeu_cau_finance)):
    """Đường DUY NHẤT để công vắng / đi muộn ảnh hưởng lương — lý do bắt buộc."""
    try:
        luong.them_dieu_chinh(user["ten"], ky, ten, so_tien, ly_do)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "luong_dieu_chinh", f"{ky} {ten} {so_tien}")
    return RedirectResponse(f"/finance?tab=payroll&ky_luong={ky}", status_code=303)


@app.post("/finance/luong/duyet")
def finance_luong_duyet(ky: str = Form(...), muc_tieu: str = Form(...),
                        vi: str = Form(...), user: dict = Depends(yeu_cau_finance)):
    """Duyệt CHI tiền → chỉ Owner (HR lập và gửi phiếu, Owner quyết chi)."""
    if user["level"] < 5:
        raise HTTPException(403, "Chỉ Owner được duyệt chi lương.")
    ds_nguoi, _ = _ds_nguoi_iam()
    try:
        ban = luong.duyet_bang_luong(user["ten"], ky, ds_nguoi or [], muc_tieu, vi)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "luong_duyet", f"{ky} tong {ban['tong']}")
    return RedirectResponse(f"/finance?tab=payroll&ky_luong={ky}", status_code=303)


def _phieu_context(ky: str, ten: str) -> dict | None:
    """Gom dữ liệu phiếu: lương đã duyệt + ngách đã tham gia (D3)."""
    ds_nguoi, _ = _ds_nguoi_iam()
    ng = []
    try:
        cp = chi_phi_ngach.chi_phi_ngach(ky, ds_nguoi or [])
        ng = [{"ten": d["ten"], "ngach_ma": d["ngach_ma"],
               "ngay_cong": round(d["ngay_cong"], 1)}
              for d in cp["dong"] if ten in d["nguoi"]]
    except Exception:          # nguồn ngoài chết thì phiếu vẫn ra, chỉ thiếu khối
        ng = []
    return luong.du_lieu_phieu(ky, ten, ngach=ng)


@app.get("/finance/luong/phieu/{ky}/{ten}", response_class=HTMLResponse)
def finance_phieu_luong(request: Request, ky: str, ten: str,
                        user: dict = Depends(yeu_cau_finance)):
    """Phiếu lương — trang HTML IN ĐƯỢC (Ctrl+P ra PDF). KHÔNG dùng WeasyPrint:
    máy Windows này thiếu GTK, 3 test test_remake_dep fail đúng vì lý do đó."""
    ctx = _phieu_context(ky, ten)
    if ctx is None:
        raise HTTPException(404, "Chưa có phiếu cho kỳ này.")
    return templates.TemplateResponse(request, "phieu_luong.html",
                                      {"user": user, **ctx})


@app.get("/finance/luong/phieu.zip")
def finance_phieu_zip(request: Request, ky: str,
                      user: dict = Depends(yeu_cau_finance)):
    """Gói cả kỳ cho HR tải một lần rồi tự gửi (Workspace). Gửi thẳng bằng SMTP
    là việc sau — chưa có tài khoản gửi thì đừng vẽ nút."""
    ban = luong.doc_bang_luong(ky)
    if not ban:
        raise HTTPException(404, "Kỳ này chưa duyệt lương.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in ban.get("dong", []):
            ctx = _phieu_context(ky, d["ten"])
            if ctx is None:
                continue
            html = templates.get_template("phieu_luong.html").render(
                request=request, user=user, **ctx)
            z.writestr(f"phieu-luong-{ky}-{d.get('ma') or d['ten']}.html", html)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="phieu-luong-{ky}.zip"'})


@app.get("/finance/xuat.csv")
def finance_xuat_csv(thang: str = "", tu: str = "", den: str = "", loai: str = "",
                     vi: str = "", kenh: str = "", muc_tieu: str = "",
                     danh_muc: str = "", q: str = "",
                     user: dict = Depends(yeu_cau_finance)):
    noi_dung = tai_chinh.xuat_csv(tai_chinh.loc_so(
        thang=thang, tu=tu, den=den, loai=loai, vi=vi, kenh=kenh,
        muc_tieu=muc_tieu, danh_muc=danh_muc, q=q))
    return Response("\ufeff" + noi_dung, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="so-thu-chi-{thang or "tat-ca"}.csv"'})


@app.get("/finance/xuat.beancount")
def finance_xuat_beancount(thang: str = "", tu: str = "", den: str = "",
                           loai: str = "", vi: str = "", kenh: str = "",
                           muc_tieu: str = "", danh_muc: str = "", q: str = "",
                           user: dict = Depends(yeu_cau_finance)):
    """Xuất để mở bằng Fava — mượn nguyên phòng báo cáo của beancount."""
    noi_dung = tai_chinh.xuat_beancount(tai_chinh.loc_so(
        thang=thang, tu=tu, den=den, loai=loai, vi=vi, kenh=kenh,
        muc_tieu=muc_tieu, danh_muc=danh_muc, q=q))
    return Response(noi_dung, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="so-{thang or "tat-ca"}.beancount"'})


@app.get("/finance/chung-tu/{id_bt}/{ten}")
def finance_tai_chung_tu(id_bt: str, ten: str,
                         user: dict = Depends(yeu_cau_finance)):
    """Tải chứng từ của một bút toán. Không có → 404 LẶNG LẼ (không nói vì sao)."""
    p = tai_chinh.duong_chung_tu(id_bt, ten)
    if p is None:
        raise HTTPException(404, "Không có tệp này.")
    return FileResponse(p)


@app.post("/finance/chot-ky")
async def finance_chot_ky(request: Request, user: dict = Depends(yeu_cau_finance)):
    """C5 — chốt kỳ sau khi đối chiếu số dư ví. Chỉ Owner; lõi tự khóa khi còn
    ví lệch (không cho chốt đè lên chênh lệch)."""
    if user["level"] < 5:
        raise HTTPException(403, "Chỉ Owner được chốt kỳ.")
    form = await request.form()
    ky = _thang_hop_le(str(form.get("ky") or ""))
    khai = {}
    for khoa, gt in form.items():
        if khoa.startswith("khai_") and str(gt).strip():
            try:
                khai[khoa[5:]] = float(str(gt).replace(",", "").replace(" ", ""))
            except ValueError:
                raise HTTPException(422, f"Số dư khai của ví {khoa[5:]} không phải số.")
    try:
        ban = tai_chinh.chot_ky_tien(user["ten"], ky, khai)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "chot_ky", f"{ky} {len(ban['doi_chieu'])} ví")
    return RedirectResponse(f"/finance?tab=wallets&thang={ky}", status_code=303)


@app.post("/finance/tai-san")
def finance_tai_san(loai: str = Form(...), ten: str = Form(...), nhom: str = Form(...),
                    ma: str = Form(""), ma_dinh_danh: str = Form(""),
                    ngay_mua: str = Form(""), nguyen_gia: str = Form("0"),
                    tien_te: str = Form("VND"), noi_de: str = Form(""),
                    vault_id: str = Form(""), tinh_trang: str = Form("dang_dung"),
                    kenh_ma: str = Form(""), ghi_chu: str = Form(""),
                    user: dict = Depends(yeu_cau_finance)):
    """Khai/sửa tài sản. KHÔNG có tham số mật khẩu — tài sản số chỉ mang vault_id."""
    try:
        d = tai_san.luu_tai_san(
            user["ten"], loai, ten, nhom, ma=ma, ma_dinh_danh=ma_dinh_danh,
            ngay_mua=ngay_mua, nguyen_gia=nguyen_gia or 0, tien_te=tien_te,
            noi_de=noi_de, vault_id=vault_id, tinh_trang=tinh_trang,
            kenh_ma=kenh_ma, ghi_chu=ghi_chu)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "tai_san", f"{d['ma']} {d['ten']}")
    return RedirectResponse("/finance?tab=assets", status_code=303)


@app.post("/finance/tai-san/ban-giao")
def finance_ban_giao(ma: str = Form(...), nguoi_giu: str = Form(""),
                     ngay: str = Form(""), ghi_chu: str = Form(""),
                     user: dict = Depends(yeu_cau_finance)):
    """Bàn giao / thu hồi. Sổ chỉ-thêm: mỗi lượt một dòng, lịch sử giữ nguyên."""
    try:
        tai_san.ban_giao(user["ten"], ma, nguoi_giu, ngay, ghi_chu)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "ban_giao",
                f"{ma} → {nguoi_giu or 'kho'}")
    return RedirectResponse("/finance?tab=assets", status_code=303)


@app.get("/finance/tai-san/{ma}/lich-su", response_class=HTMLResponse)
def finance_ls_ban_giao(request: Request, ma: str,
                        user: dict = Depends(yeu_cau_finance)):
    d = tai_san.tim_tai_san(ma)
    if d is None:
        raise HTTPException(404, "Không có tài sản này.")
    ds_nguoi, _ = _ds_nguoi_iam()
    ten_cua = {n["ten"]: n.get("ho_ten") or n["ten"] for n in (ds_nguoi or [])}
    return templates.TemplateResponse(request, "ls_ban_giao.html", {
        "user": user, "ts": d, "ls": tai_san.lich_su_ban_giao(ma),
        "ten_cua": ten_cua})


@app.post("/finance/doi-soat")
async def finance_doi_soat(request: Request, user: dict = Depends(yeu_cau_finance)):
    """B5 — nạp CSV chi trả AdSense, trả BẢNG NHÁP để người soát. Không ghi sổ."""
    form = await request.form()
    tep = form.get("tep")
    thang = _thang_hop_le(str(form.get("thang") or ""))
    if tep is None or not getattr(tep, "filename", ""):
        raise HTTPException(422, "Chưa chọn tệp CSV chi trả.")
    try:
        noi_dung = (await tep.read()).decode("utf-8-sig", "replace")
        kq = tu_dong.doi_soat_adsense(noi_dung, thang)
    except ValueError as e:
        raise HTTPException(422, str(e))
    ds_kenh = danh_ba.liet_ke("kenh")
    return templates.TemplateResponse(request, "doi_soat.html", {
        "user": user, "kq": kq, "thang": thang, "ds_kenh": ds_kenh,
        "muc_tieu": tai_chinh.doc_muc_tieu(),
        "danh_muc_vi": tai_chinh.doc_danh_muc_vi()})


@app.post("/finance/doi-soat/duyet")
async def finance_doi_soat_duyet(request: Request,
                                 user: dict = Depends(yeu_cau_finance)):
    """Người chốt xong mới vào sổ — mỗi dòng một bút toán THU-ADS 'đã về ví'."""
    form = await request.form()
    thang = _thang_hop_le(str(form.get("thang") or ""))
    muc_tieu, vi = str(form.get("muc_tieu") or ""), str(form.get("vi") or "")
    dong = []
    for khoa, gt in form.multi_items():
        if not khoa.startswith("tien_"):
            continue
        i = khoa[5:]
        try:
            tien = float(str(gt).replace(",", "").strip())
        except ValueError:
            continue
        dong.append({"kenh_ma": str(form.get(f"kenh_{i}") or ""), "tien_that": tien})
    try:
        b = tu_dong.duyet_doi_soat(user["ten"], dong, thang, muc_tieu, vi)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "doi_soat", f"{thang} {len(b)} bút toán")
    return RedirectResponse(f"/finance?tab=ledger&thang={thang}", status_code=303)


@app.post("/finance/tien-api")
def finance_tien_api(thang: str = Form(...), muc_tieu: str = Form(...),
                     vi: str = Form(...), user: dict = Depends(yeu_cau_finance)):
    """C3 — một bút toán tổng hợp tiền API cho cả kỳ."""
    try:
        b = tu_dong.ghi_tien_api(user["ten"], _thang_hop_le(thang), muc_tieu, vi)
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "tien_api", f"{thang} {b['so_tien']}")
    return RedirectResponse(f"/finance?tab=auto&thang={thang}", status_code=303)


@app.post("/finance/don-gia-api")
def finance_don_gia_api(api: str = Form(...), gia: str = Form(...),
                        thang: str = Form(""), user: dict = Depends(yeu_cau_finance)):
    try:
        tu_dong.dat_don_gia(api, gia)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return RedirectResponse(f"/finance?tab=auto&thang={thang}", status_code=303)


@app.post("/finance/han-muc")
def finance_han_muc(muc_tieu: str = Form(...), so_tien: str = Form(...),
                    chuyen_tiep: str = Form(""), thang: str = Form(""),
                    user: dict = Depends(yeu_cau_finance)):
    """B4 — đặt hạn mức mỗi kỳ cho một mục tiêu."""
    try:
        tai_chinh.dat_han_muc(user["ten"], muc_tieu, so_tien, bool(chuyen_tiep))
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "han_muc", f"{muc_tieu} {so_tien}")
    return RedirectResponse(f"/finance?tab=goals&thang={thang}", status_code=303)


@app.post("/finance/ty-gia/lay")
def finance_lay_ty_gia(tien_te: str = Form("USD"), gia: str = Form(""),
                       user: dict = Depends(yeu_cau_finance)):
    """Lấy tỷ giá VCB (dự phòng ExchangeRate-API) và ghi SỔ chỉ-thêm. Mọi nguồn
    chết → 422 để người nhập tay; không bao giờ ghi một con số bịa."""
    hom_nay = date.today().isoformat()
    try:
        if gia.strip():
            kq = {"gia": float(gia.replace(",", "").strip()), "nguon": "tay"}
        else:
            kq = tai_chinh.lay_ty_gia_online(tien_te)
            if kq is None:
                raise HTTPException(
                    422, "Không lấy được tỷ giá từ VCB lẫn ExchangeRate-API — nhập tay.")
        tai_chinh.ghi_ty_gia(hom_nay, tien_te, kq["gia"], kq["nguon"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    nhat_ky.ghi("to-chuc", user["ten"], "ty_gia", f"{tien_te} {kq['gia']} {kq['nguon']}")
    return RedirectResponse("/finance?tab=wallets", status_code=303)


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
# nas_sync (đồng bộ tài khoản Windows theo mật khẩu OUTLIERY) sống ở nen/common —
# GATEWAY gọi lúc đăng nhập/tự đổi mật khẩu (nơi duy nhất biết mật khẩu thật);
# app này CHỈ ĐỌC trạng thái (nas_sync.trang_thai) để vẽ khung "Tài khoản của bạn",
# không tự đồng bộ gì. NAS_DONG_BO đọc qua nas_sync.bat() — MỘT công tắc chung
# cho cả "app đang chạy trên server share" (tra dung lượng ổ + nhật ký xóa) LẪN
# "gateway có đồng bộ tài khoản không" (khung tài khoản/nút Cài đặt).


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


_nas_nk_cache: tuple[float, list] | None = None  # (lúc quét, dữ liệu) — TTL 60s
_nas_nk_khoa_quet = threading.Lock()             # chỉ MỘT thread quét một lúc


def _nas_nhat_ky_xoa() -> list[dict]:
    """Nhật ký xóa/đổi tên cho Manager+ — TRẢ NGAY cache hiện có (kể cả cũ/rỗng),
    cache quá hạn thì kích quét NỀN cập nhật. ĐO THẬT 22/08: Get-WinEvent quét
    2000 event Security mất 16,8s — bản cũ chạy đồng bộ trong route làm Owner
    treo trang ~17s mỗi khi cache 60s hết hạn (đúng họ bài học Ý4 19/07: việc
    chờ-lâu không được chạy đồng bộ trong request). Nhật ký 14 ngày không cần
    realtime — trễ tối đa ~1 phút, đổi lấy trang mở tức thì."""
    if _nas_nk_cache is None or time.time() - _nas_nk_cache[0] >= 60:
        threading.Thread(target=_nas_quet_nhat_ky_nen, daemon=True).start()
    return _nas_nk_cache[1] if _nas_nk_cache else []


def _nas_quet_nhat_ky_nen() -> None:
    """Chạy trong thread nền: quét thật rồi cập nhật cache. Lock non-blocking —
    nhiều request cùng kích chỉ MỘT lượt PowerShell chạy, các lượt sau bỏ qua."""
    global _nas_nk_cache
    if not _nas_nk_khoa_quet.acquire(blocking=False):
        return
    try:
        _nas_nk_cache = (time.time(), _nas_quet_nhat_ky())
    finally:
        _nas_nk_khoa_quet.release()


def _nas_quet_nhat_ky() -> list[dict]:
    """Phần quét THẬT (04/08/2026): đọc Event 4663 (audit DELETE) từ log Security
    — app chạy SYSTEM nên đọc được; đổi tên = DELETE ở đường dẫn cũ nên cùng
    nguồn. Chỉ có sự kiện khi script dựng nền đã bật SACL. Best-effort: lỗi → []
    (panel tự ghi chú)."""
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
    return ket_qua   # cache do _nas_quet_nhat_ky_nen ghi — hàm này thuần quét


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
              "dl": _nas_thong_tin_o(d) if nas_sync.bat() else None}
             for i, d in enumerate(cac_duong) if i in thay_duoc]
    # Nhật ký xóa/đổi tên: CHỈ Manager+ thấy, và chỉ khi chạy trên server thật
    nhat_ky = (_nas_nhat_ky_xoa()
               if user["level"] >= 4 and nas_sync.bat() else None)
    return templates.TemplateResponse(request, "nas.html", {
        "user": user, "o_dia": o_dia, "nas_ip": nas_ip,
        "dong_bo_bat": nas_sync.bat(), "chua_ok": chua_ok, "nhat_ky": nhat_ky,
        "tt_nas": nas_sync.trang_thai(user["ten"]),
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
    if not vault.dang_mo(user["ten"]):   # SIẾT 05/09: két của CHÍNH người này
        return templates.TemplateResponse(request, "vault.html",
                                          _ctx_vault(request, user, trang_thai="khoa"))
    return templates.TemplateResponse(request, "vault.html", _ctx_vault(
        request, user, trang_thai="mo", muc=vault.doc_muc(user["ten"]) or [], audit=_doc_audit_moi(),
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
    try:
        ok = vault.mo_bang_master(master, user["ten"])
    except PermissionError as e:
        # SIẾT 05/09: đang bị khóa tạm do sai quá nhiều lần — hiện thông báo có
        # thời gian chờ, KHÔNG để lỗi 500 lọt ra ngoài.
        return templates.TemplateResponse(request, "vault.html", _ctx_vault(
            request, user, trang_thai="khoa", loi=str(e)))
    if not ok:
        con = vault.SO_LAN_SAI_TOI_DA - vault.so_lan_sai(user["ten"])
        them = f" Còn {con} lần trước khi khóa tạm." if 0 < con <= 3 else ""
        return templates.TemplateResponse(request, "vault.html", _ctx_vault(
            request, user, trang_thai="khoa", loi="Mật khẩu chủ không đúng." + them))
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
