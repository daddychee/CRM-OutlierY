# -*- coding: utf-8 -*-
"""APP DATA ANALYTICS (v2, :9102) — chẩn đoán số liệu YouTube, DI TRÚ từ agent-app.

Nghiệp vụ GIỮ NGUYÊN hệ cũ (engine 4 trục + 7 phán quyết + báo cáo 9 mục + cache
diễn giải + lịch sử dùng chung + chạy nền). Chỉ đổi 4 mối nối theo kiến trúc nền:
1. AUTH: không tự giữ user — nhận claims X-Remote-User/Level/Role từ gateway
   (gateway đã kiểm quyền "vao" app theo nen/rules/phan_quyen.json).
2. DIỄN GIẢI LLM: src/dien_giai.py (trích từ qa_pipeline) — config từ KÉT qua
   gateway, không còn .env key trong app.
3. DỮ LIỆU: data/data-analytics/{db,kho}/ theo Luật 6 (env đặt sẵn dưới đây).
4. Thêm /health (hợp đồng app) + dropdown kênh đọc DANH BẠ thực thể chung.

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/data-analytics" --port 9102
"""
from __future__ import annotations

import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form, Header,
                     HTTPException, Request, UploadFile)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

_APP_DIR = Path(__file__).resolve().parents[1]          # apps/data-analytics
ROOT = _APP_DIR.parents[1]                               # D:\AI AGENT OUTLIERY
# Luật 6: db/ (bản ghi lịch sử) vs kho/ (file gốc tích lũy). Đặt TRƯỚC khi import
# bao_cao_lich_su (module đọc env lúc gọi hàm nên setdefault ở đây là đủ).
os.environ.setdefault("BAO_CAO_DIR", str(ROOT / "data" / "data-analytics" / "db" / "bao-cao-lich-su"))
os.environ.setdefault("BAO_CAO_GOC_DIR", str(ROOT / "data" / "data-analytics" / "kho" / "bao-cao-goc"))

from src import dien_giai                                # noqa: E402
from src.bao_cao_lich_su import (danh_sach_ten_kenh, doc_bao_cao_list,           # noqa: E402
                                 doc_bao_cao_moi_nguoi, doc_dien_giai_video,
                                 doc_mot_bao_cao, luu_bao_cao, luu_dien_giai_9muc,
                                 luu_dien_giai_video, luu_file_goc, tim_bao_cao)
from src.diagnosis_engine import (chan_doan, chan_doan_kenh, chan_doan_toan_bo,   # noqa: E402
                                  chan_doan_video, doc_bao_cao, doc_chart_data,
                                  doi_chieu_ngay_chay, pham_vi_ngay_chart,
                                  so_sanh_ky, tach_total_va_video)

PHIEN_BAN = "2.0.0"
app = FastAPI(title="Data Analytics v2")
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2
templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])
# Nhãn vòng đời kênh — đọc từ danh bạ nền (29/08), MỘT nguồn dùng chung với
# General. Hằng số tĩnh nên đặt globals thay context processor: phủ mọi template,
# không phải sửa từng route. Danh bạ lỗi → dict rỗng, badge tự lùi về mã thô.
try:
    from nen.common.danh_ba import NHAN_TRANG_THAI_KENH as _NHAN_TT_KENH
except Exception:                                        # nền lỗi không giết app
    _NHAN_TT_KENH = {}
templates.env.globals["nhan_tt_kenh"] = _NHAN_TT_KENH


@app.on_event("startup")
async def _startup():
    dien_giai.nap_cau_hinh_llm()   # config LLM từ KÉT — gateway chết thì env/mock


# ---------- claims (thay auth hệ cũ) ----------

def lay_user(x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
             x_remote_role: str = Header("")) -> dict:
    """User = claims gateway tiêm (an toàn vì app bind 127.0.0.1 — chỉ gateway tới
    được; header giả từ trình duyệt đã bị gateway vứt)."""
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    try:
        level = int(x_remote_level or 0)
    except ValueError:
        level = 0
    return {"ten": x_remote_user, "level": level, "vai": x_remote_role}


yeu_cau_data_analytics = lay_user   # gateway đã gate quyền "vao" app; giữ tên cũ cho route


# ---------- health (hợp đồng app) ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "data-analytics", "phien_ban": PHIEN_BAN}


def _hoi_ket_writer() -> dict:
    """Hỏi két cấu hình vai writer của app (tách hàm để test monkeypatch)."""
    import os

    import httpx
    goc = os.getenv("GATEWAY_URL", "http://127.0.0.1:9000")
    with httpx.Client(timeout=3) as c:
        return c.get(f"{goc}/api/cau-hinh/llm/writer",
                     params={"app": "data-analytics"}).json()


@app.get("/api/suc-khoe")
async def api_suc_khoe():
    """Sức khỏe SÂU (B3 giám sát 31/08, khuôn nen/common/suc_khoe.py).

    llm-dien-giai: két trống vai writer → Analyze trả diễn giải MẪU lặng lẽ
    (cùng họ bệnh ai-agent 31/08) — health nói thẳng + chỉ đường. Không gọi LLM.
    """
    import os
    from pathlib import Path

    from nen.common import suc_khoe

    def _llm():
        try:
            ch = _hoi_ket_writer()
        except Exception:  # noqa: BLE001 — gateway chết không được 500
            return "canh_bao", "không hỏi được két (gateway 9000?) — diễn giải sẽ dùng env/mock"
        if not ch.get("provider"):
            return "canh_bao", ("két chưa có vai writer cho data-analytics — "
                                "Analyze trả diễn giải MẪU; điền ở General → API keys")
        return "ok", f"writer từ két: {ch.get('model') or ch['provider']}"

    def _bao_cao():
        d = Path(os.getenv("BAO_CAO_DIR", "bao-cao-lich-su"))
        if not d.is_dir():
            return "canh_bao", f"BAO_CAO_DIR {d} chưa tồn tại — chưa có báo cáo nào"
        return "ok", f"{sum(1 for _ in d.glob('*.json'))} báo cáo trong kho"

    return suc_khoe.bao_cao("data-analytics", PHIEN_BAN, [
        ("llm-dien-giai", _llm), ("bao-cao", _bao_cao)])


@app.get("/", response_class=HTMLResponse)
async def goc():
    # Mặt tiền = trang chọn module 2 khối (user chốt 18/08).
    return RedirectResponse("/chan-doan", status_code=303)


# ---------- các hàm phụ (chuyển thể nguyên từ app.py cũ) ----------

@app.get("/chan-doan", response_class=HTMLResponse)
def chan_doan_trang(request: Request, user: dict = Depends(yeu_cau_data_analytics)):
    # Mặt tiền module (user chốt 18/08, khuôn Content Ultimate): trang CHỌN 2 KHỐI
    # Niche Research (/niche) · Channel Research (/niche/kenh). Alias cấp-1 của
    # gateway /data-analytics trỏ 'chan-doan' nên landing phải phục vụ TẠI ĐÂY
    # (redirect /niche là 404 với người vào qua cổng — bài học PA2b).
    # POST /chan-doan + trang-thai + mọi route con GIỮ NGUYÊN (backend modal).
    return templates.TemplateResponse(request, "chon_module.html", {"user": user})


async def _doc_report_upload(file: UploadFile):
    ten = Path(file.filename or "bao-cao.csv").name
    if not ten.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(422, "Chỉ nhận báo cáo .csv / .xlsx / .xls")
    noi_dung = await file.read()
    with tempfile.TemporaryDirectory() as tmp:
        duong_dan = Path(tmp) / ten
        duong_dan.write_bytes(noi_dung)
        try:
            return ten, noi_dung, doc_bao_cao(duong_dan), doc_chart_data(duong_dan)
        except Exception as e:
            raise HTTPException(422, f"Không đọc được báo cáo: {e}")


def _message_chan_doan(ket_qua: dict) -> str:
    if not ket_qua.get("du_du_lieu", True):
        return "Video có quá ít lượt xem để kết luận chắc chắn — chưa đủ dữ liệu (van chống bịa)."
    return (f"Tầng phễu vỡ đầu tiên: {ket_qua['tang_vo']}" if ket_qua["matched"]
            else "Không phát hiện bất thường theo bộ luật hiện có.")


def _gan_da_co_bao_cao(videos: list[dict], ten_user: str, bao_cao_id: str | None) -> list[dict]:
    da_co = set()
    if bao_cao_id:
        rec = doc_mot_bao_cao(ten_user, bao_cao_id)
        da_co = set((rec or {}).get("dien_giai_video") or {})
    for v in videos:
        v["da_co_bao_cao"] = str(v["chi_muc"]) in da_co
    return videos


def _boi_canh_loai_kenh(profile: dict | None) -> str:
    if not profile:
        return ""
    dong = "\n".join(f"  - {d['chi_so']}: {d['nguon']} (độ tin cậy: {d['do_tin_cay']})"
                     for d in profile["dieu_chinh"])
    return (f"LOẠI KÊNH: {profile['ten_hien_thi']}. Đọc các con số theo ĐẶC THÙ loại kênh này "
            f"(vẫn không bịa số, không đảo chiều kết luận/trạng thái engine):\n{dong}")


def _loi_llm_than_thien(loi: Exception) -> str:
    s = str(loi)
    if "1113" in s or "insufficient balance" in s.lower() or "recharge" in s.lower():
        return ("tài khoản model hết credit (nhà cung cấp báo 'Insufficient balance') — "
                "nạp thêm hoặc đổi writer ở Két cấu hình (Owner), "
                "rồi chẩn đoán lại để có phần diễn giải AI.")
    return f"gọi model diễn giải lỗi ({s[:160]})."


def _gan_dien_giai(ket_qua: dict, user: dict, loai_kenh_ctx: str = "") -> dict:
    """LLM chết KHÔNG được giết bài chẩn đoán (bài học 15/08 hệ cũ) — chỉ thành cảnh báo."""
    ket_qua["message"] = _message_chan_doan(ket_qua)
    ket_qua["dien_giai"] = None
    if ket_qua["matched"]:
        try:
            ket_qua["dien_giai"] = dien_giai.dien_giai_chan_doan(
                ket_qua, user=user, loai_kenh_ctx=loai_kenh_ctx)
        except Exception as loi:
            logging.warning("Diễn giải kênh lỗi (engine vẫn trả kết quả): %s", loi)
            ket_qua["dien_giai_loi"] = _loi_llm_than_thien(loi)
    return ket_qua


_NHAN_TT_MUC = {"chua_co_so_lieu": "chưa có số liệu",
                "chua_du_de_phan_tich": "số liệu chưa đủ để phân tích"}


def _tom_tat_muc(m: dict) -> str:
    chi_tiet = (m.get("noi_dung") if m["trang_thai"] == "co_ket_qua"
                else m.get("ghi_chu") or _NHAN_TT_MUC.get(m["trang_thai"], ""))
    return f"[{m['ma']}] {m['ten']}: {chi_tiet}"


def _dong_tong_quan_bo_sung(tong_quan: dict | None) -> list[str]:
    if not tong_quan:
        return []
    dong = []
    tq = tong_quan.get("tuong_quan") or []
    if tq:
        phan = "; ".join(f"{t['bien_1']}↔{t['bien_2']} = {t['he_so']:+.2f} (n={t['so_mau']})"
                         for t in tq)
        dong.append(f"Tương quan số liệu toàn kênh (Pearson, càng gần ±1 càng chặt): {phan}")
    xh = tong_quan.get("xu_huong_thang") or {}
    for bien, diem in xh.items():
        chuoi = " → ".join(f"{d['thang']}={d['trung_vi']:g} (n={d['so_video']})" for d in diem)
        dong.append(f"Xu hướng {bien} theo tháng đăng: {chuoi}")
    return dong


def _dien_giai_9_muc(bao_cao_kenh: list[dict], user: dict, loai_kenh_ctx: str = "",
                     tong_quan: dict | None = None) -> dict:
    tom_tat = {m["ma"]: _tom_tat_muc(m) for m in bao_cao_kenh}
    dong_tq = _dong_tong_quan_bo_sung(tong_quan)
    ket = {}
    for m in bao_cao_kenh:
        if m["trang_thai"] != "co_ket_qua":
            continue
        boi_canh = "\n".join(v for ma, v in tom_tat.items() if ma != m["ma"])
        if dong_tq:
            boi_canh = "\n".join(dong_tq) + "\n" + boi_canh
        dg = dien_giai.dien_giai_muc_kenh(m, boi_canh, user=user,
                                          loai_kenh_ctx=loai_kenh_ctx)
        if dg:
            m["dien_giai"] = dg
            ket[m["ma"]] = dg
    return ket


def _gan_dien_giai_9muc_cache(bao_cao_kenh: list[dict], dg_map: dict) -> None:
    for m in bao_cao_kenh:
        if m["ma"] in (dg_map or {}):
            m["dien_giai"] = dg_map[m["ma"]]


def _luu_lich_su_bao_cao(user: dict, ten_goc: str, noi_dung: bytes, kenh: dict,
                         dien_giai_9muc: dict | None = None, ten_bao_cao: str = "",
                         loai_kenh: str = "", ten_kenh: str = "",
                         ky_bat_dau: str = "", ky_ket_thuc: str = "", nguon_ky: str = "",
                         trang_thai_kenh: str = "") -> str:
    bao_cao_id = uuid.uuid4().hex[:8]
    m = kenh.get("metrics", {})
    duong_goc = luu_file_goc(bao_cao_id, ten_goc, noi_dung)
    ban_ghi = {
        "id": bao_cao_id,
        "ten_file_goc": ten_goc,
        "ten_bao_cao": ten_bao_cao,
        "ten_kenh": ten_kenh,
        "loai_kenh": loai_kenh,
        # Vòng đời LÚC CHẠY — đóng băng theo bản ghi: kênh lên nấc mới sau này
        # KHÔNG viết lại lịch sử (cùng lệ loai_kenh). Bản ghi cũ thiếu khóa này
        # → đọc ra None, trang lịch sử tự ẩn chip (không vỡ).
        "trang_thai_kenh": trang_thai_kenh,
        "ky_bat_dau": ky_bat_dau, "ky_ket_thuc": ky_ket_thuc, "nguon_ky": nguon_ky,
        "duong_dan_goc": duong_goc,
        "kenh": {
            "tang_vo": kenh.get("tang_vo"),
            "so_video": kenh.get("so_video"),
            "metrics_chinh": {k: m[k] for k in ("ctr", "retention", "views",
                                                "watchtime", "revenue") if k in m},
            "luat_khop": [r["ma_luat"] for r in kenh.get("matched", [])],
        },
        "dien_giai_kenh": kenh.get("dien_giai"),
        "dien_giai_9muc": dien_giai_9muc or {},
    }
    luu_bao_cao(user["ten"], ban_ghi, datetime.now().isoformat(timespec="seconds"))
    return bao_cao_id


# ---------- chẩn đoán chạy nền (khuôn _TAC_VU hệ cũ) ----------
# ponytail: registry trong bộ nhớ — đủ cho 1 worker; mất khi restart. Trả nợ scale
# P5 cuối: đưa ra SQLite nếu cần đa worker (đã ghi kế hoạch).
_TAC_VU: dict[str, dict] = {}


def _phan_giai_ky_bao_cao(df_chart, ky_bat_dau: str, ky_ket_thuc: str) -> tuple[str, str, str]:
    tu_chart = pham_vi_ngay_chart(df_chart)
    if tu_chart:
        return tu_chart[0], tu_chart[1], "chart_data"
    dau, cuoi = ky_bat_dau.strip(), ky_ket_thuc.strip()
    if dau and cuoi:
        return dau, cuoi, "nhap_tay"
    return "", "", ""


def _chan_doan_che_do_chi_so(user: dict, ten_goc: str, noi_dung: bytes, toan_bo: dict,
                             ngay, ten_bao_cao: str, loai_kenh: str, ten_kenh: str,
                             df_chart, ky_bat_dau: str, ky_ket_thuc: str,
                             trang_thai_kenh: str) -> dict:
    """Kênh CHƯA BẬT KIẾM TIỀN — trả BẢNG SỐ, không phán quyết, KHÔNG gọi LLM.

    Owner chốt 29/08: "chỉ quan tâm mức tăng trưởng view/AVD/CTR, không đưa ra so sánh
    gợi ý nào cả — kênh nhỏ các chỉ số chưa chính xác". Diễn giải LLM chính là gợi ý,
    nên tắt hẳn ở nhánh này (đỡ luôn tiền token). Vẫn lưu lịch sử như thường để xem lại
    và so kỳ sau."""
    canh_bao_ngay = None
    if ngay:
        _, canh_bao_ngay = doi_chieu_ngay_chay(ngay, None)
    ky_dau, ky_cuoi, nguon_ky = _phan_giai_ky_bao_cao(df_chart, ky_bat_dau, ky_ket_thuc)
    bao_cao_id = None
    try:
        # kenh={} — chế độ này không có chẩn đoán cấp kênh kiểu 4 trục để tóm tắt
        bao_cao_id = _luu_lich_su_bao_cao(user, ten_goc, noi_dung, {},
                                          ten_bao_cao=ten_bao_cao.strip(),
                                          loai_kenh=(loai_kenh or "").strip(),
                                          ten_kenh=ten_kenh.strip(),
                                          ky_bat_dau=ky_dau, ky_ket_thuc=ky_cuoi,
                                          nguon_ky=nguon_ky,
                                          trang_thai_kenh=(trang_thai_kenh or "").strip())
    except Exception as loi:
        logging.warning("Không lưu lịch sử báo cáo (chế độ chỉ-số): %s", loi)
    return {"loai": "youtube", "che_do": "chi_so",
            "so_video": toan_bo.get("so_video"),
            "chi_so_kenh": toan_bo.get("chi_so_kenh"),
            "videos": toan_bo.get("videos"),
            "xu_huong": toan_bo.get("xu_huong"),
            "canh_bao_sut_sau": toan_bo.get("canh_bao_sut_sau"),
            "canh_bao_baseline": toan_bo.get("canh_bao_baseline"),
            "canh_bao_anh_xa": toan_bo.get("canh_bao_anh_xa"),
            "canh_bao_mau_thuan": toan_bo.get("canh_bao_mau_thuan"),
            "trang_thai_kenh": toan_bo.get("trang_thai_kenh"),
            "ly_do_che_do": toan_bo.get("ly_do_che_do"),
            "canh_bao_ngay": canh_bao_ngay, "bao_cao_id": bao_cao_id}


def _chay_chan_doan_youtube(user: dict, ten_goc: str, noi_dung: bytes, df, df_chart,
                            ngay_chay: str, ten_bao_cao: str, loai_kenh: str = "",
                            ten_kenh: str = "", ky_bat_dau: str = "",
                            ky_ket_thuc: str = "", trang_thai_kenh: str = "") -> dict:
    ngay = ngay_chay.strip() or None
    toan_bo = chan_doan_toan_bo(df, ngay, df_chart=df_chart, loai_kenh=loai_kenh,
                                trang_thai_kenh=trang_thai_kenh)
    # CHẾ ĐỘ CHỈ-SỐ (kênh chưa bật kiếm tiền, Owner chốt 29/08): engine KHÔNG phán quyết
    # nên đường LLM diễn giải + khung 9 mục cũng nghỉ — không có kết luận nào để diễn giải,
    # và gọi model lúc này chính là "đưa gợi ý" mà Owner đã cắt. Trả thẳng bảng số.
    if toan_bo.get("che_do") == "chi_so":
        return _chan_doan_che_do_chi_so(user, ten_goc, noi_dung, toan_bo, ngay,
                                        ten_bao_cao, loai_kenh, ten_kenh,
                                        df_chart, ky_bat_dau, ky_ket_thuc, trang_thai_kenh)
    profile = toan_bo.get("profile_loai_kenh")
    lk_ctx = _boi_canh_loai_kenh(profile)
    kenh = _gan_dien_giai(chan_doan_kenh(df), user, loai_kenh_ctx=lk_ctx)
    videos = [{"chi_muc": v["chi_muc"], "tieu_de": v["video_title"], "views": v["views"],
               "phan_quyet": v["phan_quyet"], "giai_thich": v["giai_thich"],
               "the_diem": v["the_diem"],
               "tien_nhan": v["truc"]["tien"]["so_lieu"].get("nhan"),
               "tien_ly_do": v["truc"]["tien"]["ly_do"]} for v in toan_bo["videos"]]
    canh_bao_ngay = None
    if ngay:
        _, canh_bao_ngay = doi_chieu_ngay_chay(ngay, None)
    dien_giai_9muc = {}
    try:
        dien_giai_9muc = _dien_giai_9_muc(toan_bo["bao_cao_kenh"], user, loai_kenh_ctx=lk_ctx,
                                          tong_quan=toan_bo.get("tong_quan_danh_muc"))
    except Exception as loi:
        logging.warning("Không sinh diễn giải 9 mục: %s", loi)
    bao_cao_id = None
    ky_dau, ky_cuoi, nguon_ky = _phan_giai_ky_bao_cao(df_chart, ky_bat_dau, ky_ket_thuc)
    try:
        bao_cao_id = _luu_lich_su_bao_cao(user, ten_goc, noi_dung, kenh, dien_giai_9muc,
                                          ten_bao_cao=ten_bao_cao.strip(),
                                          loai_kenh=(loai_kenh or "").strip(),
                                          ten_kenh=ten_kenh.strip(),
                                          ky_bat_dau=ky_dau, ky_ket_thuc=ky_cuoi,
                                          nguon_ky=nguon_ky,
                                          trang_thai_kenh=(trang_thai_kenh or "").strip())
    except Exception as loi:
        logging.warning("Không lưu lịch sử báo cáo: %s", loi)
    _gan_da_co_bao_cao(videos, user["ten"], bao_cao_id)
    return {"loai": "youtube", "kenh": kenh,
            "tong_quan_danh_muc": toan_bo["tong_quan_danh_muc"],
            "bao_cao_kenh": toan_bo["bao_cao_kenh"],
            "canh_bao_anh_xa": toan_bo.get("canh_bao_anh_xa"),
            "loai_kenh": toan_bo.get("loai_kenh"),
            "profile_loai_kenh": profile,
            # Mức 1 (29/08): vòng đời mới chỉ ĐI KÈM kết quả để UI hiện — engine
            # CHƯA đọc (đổi cách đọc số là Mức 2, cần user chốt hệ số).
            "trang_thai_kenh": (trang_thai_kenh or "").strip() or None,
            "videos": videos,
            "canh_bao_ngay": canh_bao_ngay, "bao_cao_id": bao_cao_id}


def _chan_doan_nen(tac_vu_id: str, user: dict, ten_goc: str, noi_dung: bytes, df, df_chart,
                   ngay_chay: str, ten_bao_cao: str, loai_kenh: str = "",
                   ten_kenh: str = "", ky_bat_dau: str = "", ky_ket_thuc: str = "",
                   trang_thai_kenh: str = "") -> None:
    try:
        kq = _chay_chan_doan_youtube(user, ten_goc, noi_dung, df, df_chart, ngay_chay,
                                     ten_bao_cao, loai_kenh, ten_kenh, ky_bat_dau,
                                     ky_ket_thuc, trang_thai_kenh)
        _TAC_VU[tac_vu_id].update(trang_thai="xong", bao_cao_id=kq.get("bao_cao_id"), ket_qua=kq)
    except Exception as loi:
        logging.warning("Chẩn đoán nền lỗi (%s): %s", tac_vu_id, loi)
        _TAC_VU[tac_vu_id].update(trang_thai="loi", loi=str(loi))


@app.get("/chan-doan/kenh-goi-y")
async def chan_doan_kenh_goi_y(user: dict = Depends(yeu_cau_data_analytics)):
    """Gợi ý tên kênh: DANH BẠ thực thể chung đứng TRƯỚC (tên chuẩn — mảnh ④),
    rồi tới tên đã dùng trong lịch sử. Danh bạ đọc không được → chỉ lịch sử."""
    goi_y: list[str] = []
    try:
        from nen.common import danh_ba
        goi_y = [t["ten_chuan"] for t in danh_ba.liet_ke("kenh")]
    except Exception:   # app chạy độc lập thiếu nen → vẫn tự đứng
        pass
    for ten in danh_sach_ten_kenh():
        if ten not in goi_y:
            goi_y.append(ten)
    return goi_y


@app.post("/chan-doan")
async def chan_doan_route(background_tasks: BackgroundTasks,
                          file: UploadFile = File(...), ngay_chay: str = Form(""),
                          ten_bao_cao: str = Form(""), loai_kenh: str = Form(""),
                          ten_kenh: str = Form(""), ky_bat_dau: str = Form(""),
                          ky_ket_thuc: str = Form(""), trang_thai_kenh: str = Form(""),
                          user: dict = Depends(yeu_cau_data_analytics)):
    ten_goc, noi_dung, df, df_chart = await _doc_report_upload(file)
    try:
        dong_total, _ = tach_total_va_video(df)
    except Exception as e:
        raise HTTPException(422, f"Không chẩn đoán được báo cáo: {e}")

    if dong_total is not None:
        tac_vu_id = uuid.uuid4().hex[:12]
        _TAC_VU[tac_vu_id] = {"nguoi": user["ten"], "trang_thai": "dang_chay",
                              "bao_cao_id": None, "loi": None, "ket_qua": None}
        background_tasks.add_task(_chan_doan_nen, tac_vu_id, user, ten_goc, noi_dung, df,
                                  df_chart, ngay_chay, ten_bao_cao, loai_kenh, ten_kenh,
                                  ky_bat_dau, ky_ket_thuc, trang_thai_kenh)
        return {"loai": "nen", "task_id": tac_vu_id}

    try:
        ket_qua = _gan_dien_giai(chan_doan(df), user)
    except Exception as e:
        raise HTTPException(422, f"Không chẩn đoán được báo cáo: {e}")
    ket_qua["loai"] = "cu"
    return ket_qua


@app.get("/chan-doan/trang-thai/{tac_vu_id}")
def chan_doan_trang_thai(tac_vu_id: str, user: dict = Depends(yeu_cau_data_analytics)):
    tv = _TAC_VU.get(tac_vu_id)
    if tv is None or tv["nguoi"] != user["ten"]:
        raise HTTPException(404, "Không thấy tác vụ này.")
    return {"trang_thai": tv["trang_thai"], "bao_cao_id": tv["bao_cao_id"],
            "loi": tv["loi"], "ket_qua": tv["ket_qua"]}


@app.post("/chan-doan/video")
async def chan_doan_video_route(chi_muc: int = Form(...), file: UploadFile = File(None),
                                bao_cao_id: str = Form(""), nguoi: str = Form(""),
                                lam_moi: str = Form(""),
                                user: dict = Depends(yeu_cau_data_analytics)):
    target = nguoi or user["ten"]
    if file is not None:
        _, _, df, _ = await _doc_report_upload(file)
    elif bao_cao_id:
        target, rec = _tim_bao_cao_hoac_404(bao_cao_id, target)
        duong = Path(rec["duong_dan_goc"]) if rec.get("duong_dan_goc") else None
        if duong is None or not duong.is_file():
            raise HTTPException(404, "Không tìm thấy file gốc của báo cáo này.")
        try:
            df = doc_bao_cao(duong)
        except Exception as e:
            raise HTTPException(422, f"Không đọc được file gốc: {e}")
    else:
        raise HTTPException(422, "Cần gửi file hoặc bao_cao_id để chẩn đoán video.")

    try:
        kq = chan_doan_video(df, chi_muc)
    except IndexError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"Không chẩn đoán được video: {e}")

    if bao_cao_id:
        if lam_moi != "1":
            cached = doc_dien_giai_video(target, bao_cao_id, chi_muc)
            if cached is not None:
                kq["message"] = _message_chan_doan(kq)
                kq["dien_giai"] = cached
                return kq
        kq = _gan_dien_giai(kq, user)
        if kq.get("dien_giai") is not None:
            luu_dien_giai_video(target, bao_cao_id, chi_muc, kq["dien_giai"])
        return kq
    return _gan_dien_giai(kq, user)


@app.post("/chan-doan/muc-lam-moi")
async def chan_doan_muc_lam_moi(bao_cao_id: str = Form(...), nguoi: str = Form(""),
                                user: dict = Depends(yeu_cau_data_analytics)):
    target, rec = _tim_bao_cao_hoac_404(bao_cao_id, nguoi or user["ten"])
    duong = Path(rec["duong_dan_goc"]) if rec.get("duong_dan_goc") else None
    if duong is None or not duong.is_file():
        raise HTTPException(404, "Không tìm thấy file gốc của báo cáo này.")
    try:
        df = doc_bao_cao(duong)
        toan_bo = chan_doan_toan_bo(df, df_chart=doc_chart_data(duong),
                                    loai_kenh=rec.get("loai_kenh"),
                                    trang_thai_kenh=rec.get("trang_thai_kenh"))
    except Exception as e:
        raise HTTPException(422, f"Không dựng lại được báo cáo: {e}")
    # Kênh chưa bật kiếm tiền: không có khung 9 mục để diễn giải (chế độ chỉ-số cắt
    # mọi khuyến nghị) → nói thẳng thay vì KeyError.
    if toan_bo.get("che_do") == "chi_so":
        raise HTTPException(422, "Báo cáo của kênh chưa bật kiếm tiền — chế độ chỉ-số "
                                 "không có khung 9 mục để diễn giải.")
    lk_ctx = _boi_canh_loai_kenh(toan_bo.get("profile_loai_kenh"))
    dien_giai_9muc = _dien_giai_9_muc(toan_bo["bao_cao_kenh"], user, loai_kenh_ctx=lk_ctx,
                                      tong_quan=toan_bo.get("tong_quan_danh_muc"))
    luu_dien_giai_9muc(target, bao_cao_id, dien_giai_9muc)
    return {"dien_giai_9muc": dien_giai_9muc}


# ---------- lịch sử báo cáo (dùng chung — 01/08 hệ cũ) ----------

def _tim_bao_cao_hoac_404(bao_cao_id: str, goi_y_nguoi: str = "") -> tuple[str, dict]:
    nguoi, rec = tim_bao_cao(bao_cao_id, goi_y_nguoi)
    if rec is None:
        raise HTTPException(404, "Không thấy báo cáo này.")
    return nguoi, rec


@app.get("/api/bao-cao-lich-su")
def bao_cao_ls_json(user: dict = Depends(yeu_cau_data_analytics)):
    ra = []
    for r in doc_bao_cao_moi_nguoi():
        kenh = r.get("kenh") or {}
        ra.append({"id": r.get("id"), "thoi_gian": r.get("thoi_gian"),
                   "ten": r.get("ten_bao_cao") or r.get("ten_file_goc"),
                   "ten_kenh": r.get("ten_kenh", ""),   # P6: connector khớp kênh theo trường này
                   "tang_vo": kenh.get("tang_vo"),
                   "so_video": kenh.get("so_video"),
                   "nguoi_chay": r.get("nguoi_chay", "")})
    return {"bao_cao": ra}


@app.post("/chan-doan/so-sanh")
async def chan_doan_so_sanh_route(id_a: str = Form(...), id_b: str = Form(...),
                                  user: dict = Depends(yeu_cau_data_analytics)):
    _, rec_a = tim_bao_cao(id_a)
    _, rec_b = tim_bao_cao(id_b)
    if rec_a is None or rec_b is None:
        raise HTTPException(404, "Không tìm thấy một trong hai báo cáo.")
    return so_sanh_ky(rec_a, rec_b)


@app.get("/bao-cao-lich-su", response_class=HTMLResponse)
def bao_cao_ls_trang(request: Request, user: dict = Depends(yeu_cau_data_analytics),
                     nguoi: str = ""):
    return templates.TemplateResponse(request, "bao_cao_lich_su.html", {
        "user": user, "chu_nhan": nguoi, "cua_minh": not nguoi,
        "cac_bao_cao": doc_bao_cao_list(nguoi) if nguoi else doc_bao_cao_moi_nguoi(),
        "mot": None})


@app.get("/bao-cao-lich-su/{bao_cao_id}", response_class=HTMLResponse)
def bao_cao_xem_mot(bao_cao_id: str, request: Request,
                    user: dict = Depends(yeu_cau_data_analytics), nguoi: str = ""):
    target, rec = _tim_bao_cao_hoac_404(bao_cao_id, nguoi or user["ten"])
    kenh = toan_bo = loi_dung_lai = None
    duong = Path(rec.get("duong_dan_goc", ""))
    if duong.is_file():
        try:
            df = doc_bao_cao(duong)
            kenh = chan_doan_kenh(df)
            kenh["message"] = _message_chan_doan(kenh)
            kenh["dien_giai"] = rec.get("dien_giai_kenh")
            toan_bo = chan_doan_toan_bo(df, df_chart=doc_chart_data(duong),
                                        loai_kenh=rec.get("loai_kenh"),
                                        trang_thai_kenh=rec.get("trang_thai_kenh"))
            if toan_bo.get("che_do") == "chi_so":
                # Chế độ chỉ-số: không phán quyết, không khung 9 mục — trang xem lại
                # dựng khối chỉ-số thay bảng 4 trục (template đọc cờ che_do).
                kenh = None
            else:
                _gan_da_co_bao_cao(toan_bo["videos"], target, bao_cao_id)
                _gan_dien_giai_9muc_cache(toan_bo["bao_cao_kenh"], rec.get("dien_giai_9muc"))
        except Exception as e:
            kenh = toan_bo = None
            loi_dung_lai = f"Không dựng lại được chi tiết từ file gốc: {e}"
    else:
        loi_dung_lai = "Không tìm thấy file gốc để dựng lại chi tiết bảng phán quyết."
    return templates.TemplateResponse(request, "bao_cao_lich_su.html", {
        "user": user, "chu_nhan": target, "cua_minh": target == user["ten"],
        "cac_bao_cao": None, "mot": rec, "kenh": kenh, "toan_bo": toan_bo,
        "loi_dung_lai": loi_dung_lai})


@app.get("/bao-cao-goc/{bao_cao_id}")
def bao_cao_tai_goc(bao_cao_id: str, user: dict = Depends(yeu_cau_data_analytics),
                    nguoi: str = ""):
    khong_co = HTTPException(404, "Không có báo cáo này.")
    _, rec = tim_bao_cao(bao_cao_id, nguoi or user["ten"])
    if rec is None:
        raise khong_co
    duong = Path(rec.get("duong_dan_goc", ""))
    if not duong.is_file():
        raise khong_co
    return FileResponse(duong, filename=rec.get("ten_file_goc") or duong.name)


# ---------- dashboard Niche (module gộp — src/dashboard.py) ----------
from src.dashboard import router as _dashboard_router  # noqa: E402
app.include_router(_dashboard_router)
from src.agent_api import router as _agent_router  # noqa: E402 — cau noi AI Agent (phuong an 2)
app.include_router(_agent_router)
