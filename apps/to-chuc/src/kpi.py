"""KPI (bước ③ Nhân sự → KPI → Tài chính, 31/07/2026) — số đo TỰ ĐỘNG, di trú v2.

NGUYÊN TẮC (user chốt): TÍCH HỢP kết quả từ các app đang sinh dữ liệu hằng ngày —
KHÔNG nhập tay. Bốn nguồn, tất cả CHỈ ĐỌC:
  • PlannerY  plan.json          → video ĐẾN HẠN theo lịch trong kỳ + ngày nghỉ
  • Content   admin/history.jsonl → script viết XONG (kind=writer, status=done, có user SSO)
  • SpeakY    jobs_log.csv        → voice tạo xong (log mới bật 31/07 — chỉ đếm từ đó)
  • Data Analytics bao-cao-lich-su → số báo cáo đã chạy + tổng video đã phân tích

TIẾN ĐỘ Vận hành = script xong / video đến hạn (PlannerY chưa có cờ "đã xong" —
đối chiếu chéo lịch ↔ sản phẩm thật là cách đo trung thực nhất hiện có).

VAN CHỐNG BỊA SỐ LIỆU: nguồn không đọc được → None (UI hiện "—" kèm lý do),
TUYỆT ĐỐI không hiện 0 giả vờ là "không làm gì".

KHÁC HỆ CŨ (di trú v2, có chủ đích):
- 4 đường nguồn KHÔNG còn default trỏ C:\\OutlierY (hệ thật) — app v2 đặt env
  trong src/main.py; env không trỏ đâu ra file → nguồn chết → "—".
- kpi_bao_cao: hệ cũ import src.bao_cao_lich_su (dữ liệu "nhà" của agent-app);
  ở v2 lịch sử báo cáo là dữ liệu của APP KHÁC (data-analytics) — Luật 4 cấm
  import chéo app → đọc thẳng file JSON trong BAO_CAO_DIR (chỉ-đọc, cùng khuôn
  _ten_file của bao_cao_lich_su.py) và có ca NGUỒN CHẾT: thư mục không tồn tại
  → None (hệ cũ luôn trả 0 vì nguồn nhà không thể chết). tong_hop_kpi vì thế
  thêm khóa thieu["bao_cao"] + bảng KD nhận None.
"""

import csv
import hashlib
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

VAI_CO_NGUON_VH = "Vận hành - Sản xuất"
VAI_CO_NGUON_KD = "Kinh doanh"


def _plan_path() -> Path:
    return Path(os.getenv("PLANNERY_PLAN", "plannery-plan.json"))


def _content_history_path() -> Path:
    return Path(os.getenv("CONTENT_HISTORY", "content-history.jsonl"))


def _speaky_log_path() -> Path:
    return Path(os.getenv("SPEAKY_JOBS_LOG", "speaky-jobs_log.csv"))


def ky_hien_tai(ky: str) -> tuple[str, str]:
    """Cửa sổ kỳ dạng ISO yyyy-mm-dd: 'tuan' = Thứ 2 → Chủ nhật tuần này (chuẩn VN);
    'thang' = ngày 1 → ngày cuối tháng này."""
    hom_nay = date.today()
    if ky == "thang":
        dau = hom_nay.replace(day=1)
        cuoi = (dau + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    else:
        dau = hom_nay - timedelta(days=hom_nay.weekday())
        cuoi = dau + timedelta(days=6)
    return dau.isoformat(), cuoi.isoformat()


def _ngay_nghi(muc) -> str:
    """leaves của PlannerY: phần tử có thể là chuỗi ISO hoặc dict — đọc khoan dung."""
    if isinstance(muc, str):
        return muc[:10]
    if isinstance(muc, dict):
        return str(muc.get("date") or muc.get("ngay") or "")[:10]
    return ""


def _so_ngay_nghi(leaves, dau: str, cuoi: str) -> int:
    """Đếm ngày nghỉ GIAO với kỳ. Định dạng THẬT của PlannerY là khoảng
    {"from","to"} trọn ngày (models.py Person.leaves) — đếm số ngày giao;
    chuỗi ISO/dict một-ngày vẫn đọc được (khoan dung như cũ)."""
    tong = 0
    for muc in leaves or []:
        if isinstance(muc, dict) and muc.get("from") and muc.get("to"):
            a, b = max(str(muc["from"])[:10], dau), min(str(muc["to"])[:10], cuoi)
            if a <= b:
                try:
                    tong += (date.fromisoformat(b) - date.fromisoformat(a)).days + 1
                except ValueError:
                    pass
        else:
            ngay = _ngay_nghi(muc)
            if ngay and dau <= ngay <= cuoi:
                tong += 1
    return tong


def kpi_plannery(dau: str, cuoi: str) -> dict | None:
    """Số đo theo người PlannerY, tra được bằng CẢ HAI khóa: planner_id ("ng_.../ns_...")
    VÀ tên-lower (id có tiền tố nên không đụng tên). Đến hạn = video có publish_date
    trong kỳ, trên kênh thuộc dự án người đó ĐƯỢC PHÂN (assignments) và kênh có stage
    đúng VAI của người đó. None = plan.json không đọc được."""
    try:
        d = json.loads(_plan_path().read_text(encoding="utf-8"))
    except Exception:
        return None
    du_an_cua: dict[str, set] = {}
    for a in d.get("assignments", []):
        du_an_cua.setdefault(a.get("person_id", ""), set()).add(a.get("project_id", ""))
    ra = {}
    for p in d.get("people", []):
        so = 0
        for pr in d.get("projects", []):
            if pr.get("id") not in du_an_cua.get(p.get("id", ""), set()):
                continue
            for ch in pr.get("channels", []):
                if not any(s.get("role") == p.get("role") for s in ch.get("stages", [])):
                    continue
                so += sum(1 for v in ch.get("videos", [])
                          if dau <= (v.get("publish_date") or "") <= cuoi)
        muc = {"video_den_han": so,
               "ngay_nghi": _so_ngay_nghi(p.get("leaves", []), dau, cuoi)}
        ra[(p.get("name") or "").strip().lower()] = muc
        if p.get("id"):
            ra[p["id"]] = muc                     # GĐ3: hồ sơ nối bằng planner_id bền
    return ra


def kpi_content(dau: str, cuoi: str) -> dict | None:
    """{user (log SSO Content): số script viết XONG trong kỳ} — dòng kind=writer,
    status=done trong admin/history.jsonl. None = log không đọc được."""
    p = _content_history_path()
    if not p.is_file():
        return None
    ra: dict[str, int] = {}
    try:
        for dong in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not dong.strip():
                continue
            try:
                d = json.loads(dong)
            except ValueError:
                continue
            if d.get("kind") != "writer" or d.get("status") != "done":
                continue
            ngay = date.fromtimestamp(d.get("ts", 0)).isoformat()
            if dau <= ngay <= cuoi:
                u = (d.get("user") or "").strip()
                ra[u] = ra.get(u, 0) + 1
    except Exception:
        return None
    return ra


def kpi_speaky(dau: str, cuoi: str) -> dict | None:
    """{user: {so_voice, tong_giay}} từ jobs_log.csv (SpeakY ghi mỗi job xong,
    bật 31/07/2026 — trước đó không có dữ liệu). None = chưa có file log."""
    p = _speaky_log_path()
    if not p.is_file():
        return None
    ra: dict[str, dict] = {}
    try:
        for dong in list(csv.reader(p.open(encoding="utf-8-sig")))[1:]:
            if len(dong) < 4 or not (dau <= dong[0][:10] <= cuoi):
                continue
            u = (dong[1] or "").strip()
            g = ra.setdefault(u, {"so_voice": 0, "tong_giay": 0.0})
            g["so_voice"] += 1
            try:
                g["tong_giay"] += float(dong[3])
            except ValueError:
                pass
    except Exception:
        return None
    return ra


# ── đọc lịch sử báo cáo Data Analytics (CHỈ-ĐỌC file — thay import chéo app hệ cũ) ──

def _ten_file_bao_cao(ten_user: str) -> str:
    """Tên file JSON per-user — COPY NGUYÊN khuôn _ten_file của bao_cao_lich_su.py
    (data-analytics) để đọc đúng file app đó ghi. Đổi khuôn bên kia phải đổi đây."""
    sach = re.sub(r"[^0-9A-Za-z_-]", "-", ten_user)
    if sach != ten_user or not sach.strip("-"):
        sach = f"{sach.strip('-') or 'user'}-{hashlib.sha1(ten_user.encode()).hexdigest()[:8]}"
    return f"{sach}.json"


def _doc_bao_cao_list(ten_user: str) -> list[dict]:
    p = Path(os.getenv("BAO_CAO_DIR", "bao-cao-lich-su")) / _ten_file_bao_cao(ten_user)
    if not p.is_file():
        return []
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, list) else []
    except ValueError:
        return []


def kpi_bao_cao(ten_user: str, dau: str, cuoi: str) -> dict | None:
    """Data Analytics của MỘT user trong kỳ: {so_bao_cao, tong_video}.
    V2: nguồn là dữ liệu app data-analytics (BAO_CAO_DIR) — KHÔNG còn là "dữ liệu
    nhà" như hệ cũ, nên có ca nguồn chết: THƯ MỤC không tồn tại → None (van chống
    bịa — không hiện 0 giả). Thư mục có mà user chưa chạy báo cáo → 0 THẬT."""
    if not Path(os.getenv("BAO_CAO_DIR", "bao-cao-lich-su")).is_dir():
        return None
    so, video = 0, 0
    for rec in _doc_bao_cao_list(ten_user):
        if dau <= (rec.get("thoi_gian") or "")[:10] <= cuoi:
            so += 1
            try:
                video += int(rec.get("so_video") or 0)
            except (TypeError, ValueError):
                pass
    return {"so_bao_cao": so, "tong_video": video}


def _khoa_planner(nguoi: dict) -> str:
    """Tên dùng để nối người OUTLIERY ↔ người trong PlannerY: ưu tiên trường hồ sơ
    'planner_ten' (HR điền 1 lần), rồi họ tên, rồi tên tài khoản — so không phân hoa thường."""
    return ((nguoi.get("planner_ten") or nguoi.get("ho_ten") or nguoi.get("ten") or "")
            .strip().lower())


def tong_hop_kpi(ds_nguoi: list[dict], ky: str) -> dict:
    """Bảng KPI cho danh sách người ĐÃ LỌC PHẠM VI (route lo quyền). Trả:
    {"ky": ..., "tu": ..., "den": ..., "vh": [...], "kd": [...],
     "thieu": {"plannery": bool, "content": bool, "speaky": bool, "bao_cao": bool}}.
    Chỉ số None = nguồn tương ứng không đọc được (UI hiện '—')."""
    dau, cuoi = ky_hien_tai(ky)
    planner = kpi_plannery(dau, cuoi)
    content = kpi_content(dau, cuoi)
    speaky = kpi_speaky(dau, cuoi)
    bao_cao_song = Path(os.getenv("BAO_CAO_DIR", "bao-cao-lich-su")).is_dir()

    vh, kd = [], []
    for n in ds_nguoi:
        if n.get("bo_phan") == VAI_CO_NGUON_VH:
            # GĐ3: planner_id (máy gán lúc duyệt) THẮNG; chưa có id mới lùi về so tên
            pl = ((planner or {}).get(n.get("planner_id") or "")
                  or (planner or {}).get(_khoa_planner(n))) if planner is not None else None
            script = (content or {}).get(n["ten"], 0) if content is not None else None
            voice = (speaky or {}).get(n["ten"], {}).get("so_voice", 0) if speaky is not None else None
            den_han = pl["video_den_han"] if pl else (0 if planner is not None else None)
            tien_do = None
            if script is not None and den_han:
                tien_do = round(100 * script / den_han)
            vh.append({"ten": n["ten"], "ho_ten": n.get("ho_ten", ""),
                       "script_xong": script, "so_voice": voice,
                       "video_den_han": den_han,
                       "ngay_nghi": pl["ngay_nghi"] if pl else (0 if planner is not None else None),
                       "tien_do": tien_do,
                       # khau (từ danh mục chức danh) để UI phân biệt 2 ca không nối được:
                       # có khâu mà thiếu → "chưa vào lịch" (bấm đồng bộ); KHÔNG khâu
                       # (Quản lý/SEO...) → "—" vì họ vốn không thuộc lịch sản xuất.
                       # V2: IAM chưa mang trường khâu → luôn "" (UI ghi chú trung thực).
                       "khau": n.get("khau", ""),
                       "chua_noi_planner": planner is not None and pl is None})
        elif n.get("bo_phan") == VAI_CO_NGUON_KD:
            bc = kpi_bao_cao(n["ten"], dau, cuoi)
            kd.append({"ten": n["ten"], "ho_ten": n.get("ho_ten", ""),
                       "so_bao_cao": bc["so_bao_cao"] if bc else None,
                       "tong_video": bc["tong_video"] if bc else None})
    return {"ky": ky, "tu": dau, "den": cuoi, "vh": vh, "kd": kd,
            "thieu": {"plannery": planner is None, "content": content is None,
                      "speaky": speaky is None, "bao_cao": not bao_cao_song}}
