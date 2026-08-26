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

import unicodedata
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/tasky
ROOT = _APP_DIR.parents[1]                              # D:\AI AGENT OUTLIERY
# Luật 6: dữ liệu tách khỏi code. Đặt TRƯỚC khi import module đọc env.
os.environ.setdefault("TASKY_DIR", str(ROOT / "data" / "tasky" / "db"))

PHIEN_BAN = "0.2.0"
app = FastAPI(title="Tasky v3")
from src import dashboard as db_lo, muc_tieu as mt_lo, nhan_su, thong_bao as tb  # noqa: E402 — danh sách người, đọc chỉ-đọc sổ IAM chung
from src import tuan as tuan_lo  # noqa: E402 — lõi sổ tuần (đọc TASKY_DIR lúc gọi hàm)
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2

templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])
# Vendor chart (Frappe Charts) — LAN không ra Internet nên chép về, không CDN.
# Xem src/static/vendor/NGUON.md.
app.mount("/tasky-static", StaticFiles(directory=str(_APP_DIR / "src" / "static")),
          name="tasky-static")
def _khong_dau(chu: str) -> str:
    """So chữ KHÔNG DẤU, không phân biệt hoa thường — gõ 'seo' phải ra 'SEO',
    gõ 'tai nguyen' phải ra 'Tài nguyên' (lệ ô tìm của hệ)."""
    x = unicodedata.normalize("NFD", (chu or "").casefold())
    return "".join(c for c in x if unicodedata.category(c) != "Mn").replace("đ", "d")


templates.env.filters["han"] = tuan_lo.tinh_han   # {{ v|han }} → {chu, muc, con}
templates.env.filters["chip"] = tuan_lo.the_trang_thai


def _viet_tat(ho_ten: str) -> str:
    """Hai chữ cái cho avatar tròn kiểu Trello: 'Đặng Hương Giang' → 'HG'."""
    phan = [p for p in (ho_ten or "").split() if p]
    if not phan:
        return "?"
    return (phan[-2][0] + phan[-1][0]).upper() if len(phan) > 1 else phan[0][:2].upper()


templates.env.filters["viet_tat"] = _viet_tat   # {{ v|chip }} → [{chu, muc}]


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
               x_remote_actions: str = Header(""), loi: str = "", loi_viec: str = ""):
    """Việc của tôi — chỉ việc CỦA MÌNH (luật 1: lọc ở server, không ẩn nút)."""
    ma = _ma_tuan_hop_le(tuan_xem)
    ds = tuan_lo.sap_xep(tuan_lo.viec_cua(ma, user["ten"]))
    tu, den = tuan_lo.khoang_tuan(ma)
    ds_mt = mt_lo.doc_tat_ca()
    gom_mt = mt_lo.viec_theo_muc_tieu()          # MỘT lượt quét, dùng cho cả trang
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
        "loi_form": loi, "loi_viec": loi_viec,
        "xoa_duoc": {v["id"]: tuan_lo.duoc_xoa(v, user)[0] for v in ds},
        "trao_doi": {v["id"]: (v.get("trao_doi") or []) for v in ds},
        # việc thuộc mục tiêu nào (chip xanh trên thẻ việc) + nhiệm vụ chờ dựng
        "mt_theo_id": mt_lo.theo_id(ds_mt),
        "mt_tien_do": {m["id"]: mt_lo.tien_do(m["id"], gom_mt.get(m["id"], []))
                       for m in ds_mt},
        # Việc cấp trên giao cho Manager mà chưa dựng thành mục tiêu → hiện nút
        # "Dựng thành mục tiêu" (§12.1). Nhân sự thường không thấy khối này.
        "cho_dung_mt": [v for v in ds
                        if mt_lo.duoc_dat_muc_tieu(user)
                        and v["trang_thai"] in (tuan_lo.CHO_NHAN, tuan_lo.DANG_LAM)
                        and not v.get("muc_tieu_id")
                        and mt_lo.nhiem_vu_da_dung(v["id"], ds_mt) is None],
        "loai_viec": tuan_lo.cac_loai_viec(),
        "tuan_truoc": tuan_lo.tuan_lien_ke(ma, -1),
        "tuan_sau": tuan_lo.tuan_lien_ke(ma, 1),
        "tuan_nay": tuan_lo.ma_tuan(), **_co_sidebar(x_remote_actions, ma, user)})


@app.get("/giao-viec")
def trang_giao_cu():
    """Màn Giao việc cũ đã gộp đi (25/08). Từ 26/08 Tasky có ba mục Goal / Task /
    Report, nên bookmark cũ trỏ về TASK — đó mới là nơi giao việc."""
    return RedirectResponse("/task", status_code=303)


@app.get("/muc-tieu", response_class=HTMLResponse)
def trang_muc_tieu(request: Request, user: dict = Depends(yeu_cau_muc_tieu),
                   x_remote_actions: str = Header(""), tuan_xem: str = "",
                   da_don: str = "", loi: str = "", tim: str = "", loc: str = "",
                   bo: str = "", sap: str = "gan_han", kieu: str = ""):
    """TRANG GOAL — chỉ theo dõi MỤC TIÊU (Owner chốt 26/08: Tasky có ba mục
    Goal / Task / Report; việc con chuyển hẳn sang mục Task).

    Trang này KHÔNG dựng việc con nữa: chỉ tổng quan + danh sách Goal. Bấm một
    Goal là sang board Task đã lọc sẵn Goal đó."""
    hd = cac_hanh_dong(x_remote_actions)
    ds = mt_lo.trong_pham_vi(user, bool({"bao_cao_cong_ty", "bao_cao_nhan_su"} & hd))
    gom = mt_lo.viec_theo_muc_tieu()          # MỘT lượt quét cho cả trang
    cay = [{**m, "tien_do": mt_lo.tien_do(m["id"], gom.get(m["id"], [])),
            "canh_bao": mt_lo.canh_bao(m, gom.get(m["id"], [])),
            "con_han": mt_lo.con_han(m)} for m in ds]
    tong_quan = mt_lo.tong_quan(ds, gom)

    # lọc: chữ tìm (không dấu) / trạng thái / bộ phận người đặt
    moi_nguoi, _ = nhan_su.ds_nguoi()
    moi_nguoi = moi_nguoi or []
    bo_cua = {n["ten"]: n.get("bo_phan") or "" for n in moi_nguoi}
    if tim.strip():
        k = _khong_dau(tim)
        cay = [g for g in cay if k in _khong_dau(g["tieu_de"])
               or k in _khong_dau(g.get("ket_qua_can_dat") or "")]
    if loc in ("dang_chay", "cho_chot", "da_chot"):
        def hop(g):
            if loc == "da_chot":
                return g["trang_thai"] != mt_lo.DANG_CHAY
            if g["trang_thai"] != mt_lo.DANG_CHAY:
                return False
            return g["tien_do"]["xong_het"] if loc == "cho_chot" else not g["tien_do"]["xong_het"]
        cay = [g for g in cay if hop(g)]
    if bo:
        cay = [g for g in cay if bo_cua.get(g["nguoi_tao"]) == bo]

    cay = mt_lo.sap_xep_goal(cay, sap)
    gap, thuong = mt_lo.can_de_y(cay)
    ten_hien = {n["ten"]: (n.get("ho_ten") or n["ten"]) for n in moi_nguoi}
    ma = _ma_tuan_hop_le(tuan_xem)
    return templates.TemplateResponse(request, "muc_tieu.html", {
        "user": user, "gap": gap, "thuong": thuong, "tong_quan": tong_quan,
        "tim": tim, "loc": loc, "bo": bo, "sap": sap,
        # kiểu hiển thị: nhiều Goal thì mặc định DÒNG cho đỡ miss (Owner 26/08)
        "kieu": kieu if kieu in ("the", "dong") else ("dong" if len(cay) > 12 else "the"),
        "bo_phan_co": sorted({v for v in bo_cua.values() if v}),
        "duoc_dat": mt_lo.duoc_dat_muc_tieu(user),
        "la_owner": user["level"] >= mt_lo.OWNER_LEVEL,
        "da_don": da_don, "loi_form": loi, "ten_hien": ten_hien,
        "con_viec_cu": sum(1 for ma_t in tuan_lo.cac_tuan_gan()
                           for v in tuan_lo.doc_tuan(ma_t)["viec"]
                           if not v.get("muc_tieu_id")),
        "ma_tuan": ma, "tuan_nay": tuan_lo.ma_tuan(),
        **_co_sidebar(x_remote_actions, ma, user)})


@app.get("/task", response_class=HTMLResponse)
def trang_task(request: Request, user: dict = Depends(lay_user),
               x_remote_actions: str = Header(""), goal: str = "", truc: str = "",
               ai: str = "", tuan_xem: str = "", loi: str = "", loi_viec: str = ""):
    """MỤC TASK — board kanban (Owner chốt 26/08).

    Cột đổi được theo TRỤC: trạng thái (khâu nào đang ùn) · goal (kiểu Trello) ·
    người (ai đang ôm bao nhiêu). Số cột do BỘ LỌC quyết chứ không do số Goal, nên
    không bao giờ cuộn ngang vô tận.

    Nhân viên (không có quyền giao việc) mặc định thấy việc CỦA MÌNH — màn 'việc
    của tôi' cũ chính là board này với bộ lọc đó.
    """
    hd = cac_hanh_dong(x_remote_actions)
    la_quan_ly = "giao_viec" in hd
    ds_mt = mt_lo.trong_pham_vi(user, bool({"bao_cao_cong_ty", "bao_cao_nhan_su"} & hd))
    ma = _ma_tuan_hop_le(tuan_xem)

    # Goal đang mở: rỗng = xem MỌI Goal (board toàn cảnh)
    m = next((x for x in ds_mt if x["id"] == goal), None)
    cap_duoi, _ = nhan_su.cap_duoi_cua(user)
    if m is not None:
        viec = mt_lo.viec_cua_muc_tieu(m["id"])
    elif la_quan_ly:
        # MỌI việc trong tầm, kể cả việc CHƯA GẮN GOAL nào — không giấu đi, chúng
        # hiện ở cột "Chưa thuộc Goal nào" để còn gom vào Goal
        viec = [v for ma_t in tuan_lo.cac_tuan_gan()
                for v in tuan_lo.doc_tuan(ma_t)["viec"]]
    else:
        viec = tuan_lo.viec_cua(ma, user["ten"])

    # LỌC QUYỀN Ở SERVER (luật 1): không có quyền giao việc → chỉ việc của mình;
    # có quyền → việc của quân mình (Owner/cấp công ty thì cap_duoi đã là tất cả)
    if not la_quan_ly:
        viec = [v for v in viec if v["nguoi"] == user["ten"]]
    elif m is None:
        trong = {n["ten"] for n in (cap_duoi or [])} | {user["ten"], ""}
        viec = [v for v in viec
                if v.get("nguoi", "") in trong or v.get("nguoi_giao") == user["ten"]]
    ai = ai if ai != "toi" else user["ten"]
    if ai:
        viec = [v for v in viec if v["nguoi"] == ai]
    viec = [v for v in viec if v["trang_thai"] != tuan_lo.DOI]   # bản mới ở tuần sau

    # Mặc định theo VAI: nhân viên nhìn theo khâu (việc của tôi đang ở đâu);
    # quản lý xem toàn cảnh thì nhìn theo Goal (kiểu Trello).
    truc = truc if truc in tuan_lo.TRUC else (
        "goal" if (la_quan_ly and not m) else "trang_thai")
    moi_nguoi, _ = nhan_su.ds_nguoi()
    ten_hien = {n["ten"]: (n.get("ho_ten") or n["ten"]) for n in (moi_nguoi or [])}
    cot = tuan_lo.dung_cot(tuan_lo.sap_xep(viec), truc, ds_mt, ten_hien)

    g = None
    if m:
        vm = mt_lo.viec_cua_muc_tieu(m["id"])
        g = {**m, "tien_do": mt_lo.tien_do(m["id"], vm),
             "canh_bao": mt_lo.canh_bao(m, vm), "con_han": mt_lo.con_han(m)}
    return templates.TemplateResponse(request, "task.html", {
        "user": user, "g": g, "ds_goal": ds_mt, "cot": cot, "truc": truc,
        "ai": "" if ai == user["ten"] and not la_quan_ly else ai,
        "la_quan_ly": la_quan_ly, "so_viec": len(viec),
        "nguoi_loc": sorted((cap_duoi or []) + [n for n in (moi_nguoi or [])
                                                if n["ten"] == user["ten"]],
                            key=lambda n: (n.get("ho_ten") or n["ten"]).lower()),
        "cap_duoi": cap_duoi or [], "loai_viec": tuan_lo.cac_loai_viec(),
        "ngang_cap": nhan_su.ngang_cap_bo_phan_khac(user)[0] or [],
        "ten_hien": ten_hien,
        "xoa_duoc": {v["id"]: tuan_lo.duoc_xoa(v, user)[0] for v in viec},
        "keo_duoc": {v["id"]: [c["ma"] for c in cot
                               if tuan_lo.keo_duoc(v, truc, c["ma"], user)[0]]
                     for v in viec},
        "loi_form": loi, "loi_viec": loi_viec,
        "la_owner": user["level"] >= mt_lo.OWNER_LEVEL,
        "ma_tuan": ma, "tuan_nay": tuan_lo.ma_tuan(),
        **_co_sidebar(x_remote_actions, ma, user)})


@app.post("/api-tasky/keo")
def api_keo(id: str = Form(...), truc: str = Form(...), cot: str = Form(...),
            tuan_xem: str = Form(""), user: dict = Depends(lay_user)):
    """Thả một thẻ sang cột khác. Mỗi nước đi gọi ĐÚNG hàm nghiệp vụ đã có — board
    không có đường ghi riêng, nên không thể lách luật bằng cách kéo."""
    ma = _ma_tuan_hop_le(tuan_xem)
    v = tuan_lo._tim(tuan_lo.doc_tuan(ma), id)
    duoc, vi_sao = tuan_lo.keo_duoc(v, truc, cot, user)
    if not duoc:
        raise HTTPException(403, vi_sao)
    if truc == "trang_thai":
        ham = {"dang_lam": lambda: tuan_lo.nhan_viec(ma, id, user),
               "bao_xong": lambda: tuan_lo.bao_xong(ma, id, user),
               "xac_nhan": lambda: tuan_lo.xac_nhan_viec(ma, id, user),
               "chua_nhan": lambda: tuan_lo.tra_lai_viec(ma, id, user)}[cot]
        return _goi(ham)
    if truc == "goal":
        return _goi(tuan_lo.chuyen_vao_goal, ma, id, user, cot)
    return _goi(tuan_lo.gan_lai_nguoi, ma, id, user, _tim_nguoi(cot) if cot else None)


@app.get("/bao-cao-tuan", response_class=HTMLResponse)
def trang_bao_cao(request: Request, user: dict = Depends(yeu_cau_bao_cao),
                  x_remote_actions: str = Header(""), tuan_xem: str = "",
                  pham_vi: str = "", bo: str = "", ai: str = ""):
    """Dashboard. HAI báo cáo trả lời hai câu hỏi khác nhau (§12.3):
    - `bo-phan` (mặc định): Manager điều hành — người + việc
    - `cong-ty`: Owner — bộ phận + Goal + nhiệm vụ mình đã giao (cần quyền)
    """
    hd = cac_hanh_dong(x_remote_actions)
    duoc_cong_ty = bool({"bao_cao_cong_ty", "bao_cao_nhan_su"} & hd)
    # Ai có quyền toàn công ty thì MẶC ĐỊNH thấy toàn công ty (giữ luật 24/08:
    # Manager L4 xem mọi bộ phận) — muốn xem riêng bộ phận mình thì ?pham_vi=bo-phan
    # BA TAB (Owner 25/08: một trang quá dài) — cong-ty / bo-phan / nhan-su.
    # Ai không có quyền toàn công ty thì chỉ có hai tab sau.
    tab = pham_vi if pham_vi in ("cong-ty", "bo-phan", "nhan-su") else (
        "cong-ty" if duoc_cong_ty else "bo-phan")
    if tab == "cong-ty" and not duoc_cong_ty:
        tab = "bo-phan"
    la_cong_ty = tab == "cong-ty"
    ma = _ma_tuan_hop_le(tuan_xem)
    ds, loi = nhan_su.trong_pham_vi_bao_cao(user, duoc_cong_ty)
    ds = ds or []
    bo_phan_co = sorted({n["bo_phan"] for n in ds if n["bo_phan"]})
    bo_chon = bo if bo in bo_phan_co else (user.get("bo_phan") or
                                           (bo_phan_co[0] if bo_phan_co else ""))
    if la_cong_ty:
        trong_bc = ds
    else:
        trong_bc = [n for n in ds if n["bo_phan"] == bo_chon or n["ten"] == user["ten"]]
    ai_co = sorted(trong_bc, key=lambda n: n.get("ho_ten") or n["ten"])
    ai_chon = ai if any(n["ten"] == ai for n in ai_co) else (
        ai_co[0]["ten"] if ai_co else "")
    if tab == "nhan-su" and ai_chon:
        trong_bc = [n for n in trong_bc if n["ten"] == ai_chon]
    bang = tuan_lo.bang_bao_cao(ma, trong_bc)
    ds_mt = mt_lo.trong_pham_vi(user, la_cong_ty)
    tu, den = tuan_lo.khoang_tuan(ma)
    return templates.TemplateResponse(request, "bao_cao.html", {
        # Khối "Chờ bạn xử lý" là hộp việc của CHÍNH người xem, không phụ thuộc
        # phạm vi tab → chỉ hiện MỘT lần, ở tab họ vào đầu tiên.
        "tab_mac_dinh": "cong-ty" if duoc_cong_ty else "bo-phan",
        "user": user, "ma_tuan": ma, "tu": tu, "den": den,
        "la_cong_ty": la_cong_ty, "duoc_cong_ty": duoc_cong_ty,
        "tab": tab, "bo_phan_co": bo_phan_co, "bo_chon": bo_chon,
        "ai_co": ai_co, "ai_chon": ai_chon,
        "bang": bang, "loi_iam": loi,
        "tong": tuan_lo.tong_hop(bang),
        "xu_huong": db_lo.xu_huong(trong_bc, ma),
        "bo_phan": db_lo.theo_bo_phan(ma, trong_bc) if la_cong_ty else [],
        "goal": db_lo.goal_kem_tien_do(ds_mt),
        "tong_goal": db_lo.tong_hop_goal(ds_mt),
        "nhiem_vu": db_lo.nhiem_vu_da_giao(user) if la_cong_ty else [],
        "ds_goal": [{"id": g["id"], "tieu_de": g["tieu_de"]} for g in ds_mt],
        "kho_quy_trinh": tuan_lo.kho_quy_trinh(),   # gom toàn bộ checklist, không theo bộ phận
        # Việc chờ xác nhận + bị từ chối — gồm cả việc NGOÀI Goal, vì màn Goal chỉ
        # hiện việc thuộc Goal (bỏ tab Việc lẻ 25/08) thì chúng mất chỗ đứng.
        "cho_xac_nhan": tuan_lo.cho_xac_nhan(ma, user),
        "bi_tu_choi": [v for v in tuan_lo.doc_tuan(ma)["viec"]
                       if v["trang_thai"] == tuan_lo.TU_CHOI
                       and v.get("nguoi_giao") == user["ten"]],
        # nút Đóng tuần / Mở lại chuyển từ màn Giao việc sang đây (25/08)
        "duoc_dong": "xac_nhan_ket_qua" in hd,
        "quan_ly": {n["ten"] for n in (nhan_su.cap_duoi_cua(user)[0] or [])},
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


@app.post("/api-tasky/xoa")
def api_xoa(id: str = Form(...), tuan_xem: str = Form(""),
            user: dict = Depends(lay_user)):
    """Xóa hẳn một việc (luật + quyền kiểm ở lõi; nhật ký giữ nguyên bản)."""
    return _goi(tuan_lo.xoa_viec, _ma_tuan_hop_le(tuan_xem), id, user)


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
                 han: str = Form(""), gap: str = Form(""), muc_tieu_id: str = Form(""),
                 tuan_xem: str = Form(""), user: dict = Depends(yeu_cau_giao_viec)):
    """Gửi yêu cầu phối hợp sang bộ phận khác (luật ngang cấp kiểm ở lõi).
    Gửi từ trong Goal thì gắn luôn vào Goal đó — nó là việc phục vụ Goal."""
    return _goi(tuan_lo.yeu_cau_phoi_hop, _ma_tuan_hop_le(tuan_xem), user,
                _tim_nguoi(nguoi), tieu_de, loai_viec, han, _co(gap), muc_tieu_id)


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


@app.post("/muc-tieu/mau")
def form_mau_muc_tieu(id: str = Form(...), mau: str = Form(""),
                      user: dict = Depends(yeu_cau_muc_tieu)):
    """Đổi màu bằng FORM THUẦN — trước đó làm bằng JS và Owner báo bấm không ăn hai
    lần liền; form POST + 303 thì hỏng JS cũng không chết tính năng."""
    try:
        mt_lo.dat_mau(id, user, mau)
    except (ValueError, PermissionError):
        pass
    return RedirectResponse(f"/muc-tieu?chon={id}", status_code=303)


@app.post("/muc-tieu/sua")
def form_sua_muc_tieu(id: str = Form(...), tieu_de: str = Form(""),
                      ket_qua: str = Form(""), han: str = Form(""),
                      user: dict = Depends(yeu_cau_muc_tieu)):
    """Sửa Goal bằng FORM THUẦN (cùng lệ với đổi màu — không phụ thuộc JS)."""
    try:
        mt_lo.sua(id, user, tieu_de, ket_qua, han if han else None)
    except (ValueError, PermissionError):
        pass
    return RedirectResponse(f"/muc-tieu?chon={id}", status_code=303)


@app.post("/tasky/trao-doi")
def form_trao_doi(id: str = Form(...), chu: str = Form(""), ve: str = Form("/tasky"),
                  tuan_xem: str = Form(""), user: dict = Depends(lay_user)):
    """Nhắn vào việc — FORM THUẦN, quay lại đúng trang vừa nhắn."""
    try:
        tuan_lo.them_trao_doi(_ma_tuan_hop_le(tuan_xem), id, user, chu)
    except (ValueError, PermissionError):
        pass
    return RedirectResponse(ve if ve.startswith("/") else "/tasky", status_code=303)


def _ve_kem_loi(ve: str, loi: str = "", id_viec: str = "") -> str:
    """Quay lại đúng trang vừa thao tác. Lỗi ĐI THEO URL chứ không nuốt lặng lẽ —
    dán sai đường dẫn tài liệu mà im re thì người dùng tưởng đã lưu."""
    duong = ve if ve.startswith("/") else "/tasky"
    if not loi:
        return duong
    q = urlencode({"loi": loi[:200], "loi_viec": id_viec})
    return duong + ("&" if "?" in duong else "?") + q


@app.post("/tasky/viec/sua")
def form_sua_viec(id: str = Form(...), tieu_de: str = Form(""), mo_ta: str = Form(""),
                  loai_viec: str = Form(""), tuan_xem: str = Form(""),
                  ve: str = Form("/tasky"), user: dict = Depends(lay_user)):
    """Sửa đề bài + mô tả của một việc — FORM THUẦN (§16)."""
    loi = ""
    try:
        tuan_lo.sua_viec(_ma_tuan_hop_le(tuan_xem), id, user,
                         tieu_de=tieu_de, mo_ta=mo_ta, loai_viec=loai_viec)
    except (ValueError, PermissionError) as e:
        loi = str(e)
    return RedirectResponse(_ve_kem_loi(ve, loi, id), status_code=303)


@app.post("/tasky/viec/tai-lieu")
def form_them_tai_lieu(id: str = Form(...), dia_chi: str = Form(""), ten: str = Form(""),
                       tuan_xem: str = Form(""), ve: str = Form("/tasky"),
                       user: dict = Depends(lay_user)):
    loi = ""
    try:
        tuan_lo.them_tai_lieu(_ma_tuan_hop_le(tuan_xem), id, user, dia_chi, ten)
    except (ValueError, PermissionError) as e:
        loi = str(e)
    return RedirectResponse(_ve_kem_loi(ve, loi, id), status_code=303)


@app.post("/tasky/viec/tai-lieu/xoa")
def form_xoa_tai_lieu(id: str = Form(...), id_tl: str = Form(...),
                      tuan_xem: str = Form(""), ve: str = Form("/tasky"),
                      user: dict = Depends(lay_user)):
    loi = ""
    try:
        tuan_lo.xoa_tai_lieu(_ma_tuan_hop_le(tuan_xem), id, user, id_tl)
    except (ValueError, PermissionError) as e:
        loi = str(e)
    return RedirectResponse(_ve_kem_loi(ve, loi, id), status_code=303)


@app.post("/tasky/viec/xoa")
def form_xoa_viec(id: str = Form(...), tuan_xem: str = Form(""),
                  ve: str = Form("/tasky"), user: dict = Depends(lay_user)):
    """Gỡ hẳn một việc khỏi Goal. Luật ai-gỡ-được nằm ở `tuan.duoc_xoa` — việc đang
    làm dở vẫn phải Hủy kèm lý do, không xóa trắng công của người ta."""
    loi = ""
    try:
        tuan_lo.xoa_viec(_ma_tuan_hop_le(tuan_xem), id, user)
    except (ValueError, PermissionError) as e:
        loi = str(e)
    return RedirectResponse(_ve_kem_loi(ve, loi, id), status_code=303)


@app.post("/muc-tieu/don-viec-cu")
def form_don_viec_cu(user: dict = Depends(yeu_cau_muc_tieu)):
    """Dọn MỌI việc không thuộc Goal nào — dùng một lần để xóa việc tạo từ trước khi
    có Goal (Owner yêu cầu 25/08). Chỉ Owner; nhật ký giữ nguyên bản từng việc."""
    if user["level"] < mt_lo.OWNER_LEVEL:
        raise HTTPException(403, "Chỉ Owner mới dọn được việc cũ.")
    dem = 0
    for ma in tuan_lo.cac_tuan_gan():
        for v in list(tuan_lo.doc_tuan(ma)["viec"]):
            if v.get("muc_tieu_id"):
                continue
            try:
                tuan_lo.xoa_viec(ma, v["id"], user)
                dem += 1
            except (ValueError, PermissionError):
                pass
    return RedirectResponse(f"/muc-tieu?da_don={dem}", status_code=303)


@app.post("/api-tasky/chuyen-goal")
def api_chuyen_goal(id: str = Form(...), muc_tieu_id: str = Form(""),
                    tuan_xem: str = Form(""), user: dict = Depends(yeu_cau_muc_tieu)):
    """Gom việc lẻ vào một Goal — dùng để dọn nhiệm vụ tồn từ bản cũ."""
    return _goi(tuan_lo.chuyen_vao_goal, _ma_tuan_hop_le(tuan_xem), id, user, muc_tieu_id)


@app.post("/api-tasky/muc-tieu/mau")
def api_mau_muc_tieu(id: str = Form(...), mau: str = Form(""),
                     user: dict = Depends(yeu_cau_muc_tieu)):
    return _goi(mt_lo.dat_mau, id, user, mau)


@app.post("/api-tasky/muc-tieu/xoa")
def api_xoa_muc_tieu(id: str = Form(...), user: dict = Depends(yeu_cau_muc_tieu)):
    """Xóa Goal — việc con được GỠ LIÊN KẾT thành việc lẻ, không xóa theo."""
    return _goi(mt_lo.xoa, id, user)


@app.post("/api-tasky/muc-tieu/che-viec")
def api_che_viec(muc_tieu_id: str = Form(...), tieu_de: str = Form(...),
                 loai_viec: str = Form(""), nguoi: str = Form(""), han: str = Form(""),
                 gap: str = Form(""), tuan_xem: str = Form(""), mo_ta: str = Form(""),
                 tai_lieu: str = Form(""),
                 user: dict = Depends(yeu_cau_muc_tieu)):
    """Chẻ một việc từ mục tiêu. Để trống `nguoi` = chưa phân công, giao sau.

    `mo_ta` + `tai_lieu` là phần SETUP ban đầu; sau đó vẫn bổ sung được trong phiếu
    chi tiết của việc — nên chúng đính SAU khi việc đã tạo, và đính hỏng (dán sai
    đường dẫn) KHÔNG làm hỏng việc vừa tạo."""
    ma = _ma_tuan_hop_le(tuan_xem)
    ds = [t.strip() for t in (nguoi or "").split(",") if t.strip()]
    if ds:
        ra = _goi(tuan_lo.giao_nhieu_nguoi, ma, user, [_tim_nguoi(t) for t in ds],
                  tieu_de, loai_viec, han=han, gap=_co(gap), muc_tieu_id=muc_tieu_id)
        moi = ra["du_lieu"]                      # nhiều người → nhiều bản việc
    else:
        ra = _goi(tuan_lo.them_viec_muc_tieu, ma, user, tieu_de, loai_viec,
                  muc_tieu_id, han, _co(gap))
        moi = [ra["du_lieu"]]
    for v in moi:
        try:
            if mo_ta.strip():
                tuan_lo.sua_viec(ma, v["id"], user, mo_ta=mo_ta)
            if tai_lieu.strip():
                tuan_lo.them_tai_lieu(ma, v["id"], user, tai_lieu)
        except (ValueError, PermissionError) as e:
            ra["canh_bao"] = str(e)
    return ra


@app.post("/api-tasky/muc-tieu/gan-nguoi")
def api_gan_nguoi(id: str = Form(...), nguoi: str = Form(...), tuan_xem: str = Form(""),
                  user: dict = Depends(yeu_cau_muc_tieu)):
    return _goi(tuan_lo.gan_nguoi, _ma_tuan_hop_le(tuan_xem), id, user, _tim_nguoi(nguoi))


@app.post("/api-tasky/dong-tuan")
def api_dong_tuan(nguoi: str = Form(...), tuan_xem: str = Form(""),
                  user: dict = Depends(yeu_cau_xac_nhan)):
    return _goi(tuan_lo.dong_tuan, _ma_tuan_hop_le(tuan_xem), nguoi, user)
