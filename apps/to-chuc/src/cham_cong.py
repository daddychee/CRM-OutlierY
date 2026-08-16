"""CHẤM CÔNG TỰ ĐỘNG từ hiện diện trên cổng 8000 (01/08/2026, user chốt).

Nguyên lý: mọi công cụ đều đi qua cổng 8000 → MỘT điểm hứng ở auth.lay_user:
  • GIỜ VÀO = tín hiệu ĐẦU TIÊN trong ngày (request bất kỳ, không phụ thuộc sự
    kiện đăng nhập — cookie "duy trì 30 ngày" làm login event biến mất cả tháng).
  • GIỜ RA  = tín hiệu CUỐI trong ngày. Nguồn tín hiệu: request thật + nhịp tim
    5 phút khi tab hiển thị (/api/nhip) + beacon lúc đóng app/tắt máy
    (/api/nhip-thoat, user chốt "agent off tính là giờ out") + nút Đăng xuất.

VAN TRUNG THỰC (như KPI): đây là "hiện diện trên hệ công cụ", KHÔNG phải máy
chấm vân tay — làm việc ngoài hệ (họp, quay ngoài hiện trường) không được đếm;
bảng hiển thị phải ghi chú rõ nguồn số, không giả vờ chính xác tuyệt đối.

Lưu nhan-su/cham-cong/YYYY-MM.json {ngày: {user: {vao, ra, nguon_ra}}} — ghi
NGUYÊN TỬ; throttle bộ nhớ: request thường ghi đĩa tối đa 1 lần/60s mỗi user
(tín hiệu CHỦ ĐÍCH đóng-app/đăng-xuất luôn ghi ngay).
"""

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

_khoa = threading.Lock()
_da_ghi: dict[tuple[str, str], datetime] = {}  # (ngày, user) → lần GHI ĐĨA cuối

NGUON_RA = {"dang_xuat": "Đăng xuất", "dong_app": "Đóng app", "nhip": "Nhịp tim",
            "": "Lần cuối thấy"}


def _thu_muc() -> Path:
    return Path(os.getenv("CHAM_CONG_DIR", "nhan-su/cham-cong"))


def _duong(thang: str) -> Path:
    return _thu_muc() / f"{thang}.json"


def _doc(thang: str) -> dict:
    p = _duong(thang)
    if not p.is_file():
        return {}
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, dict) else {}
    except ValueError:
        return {}


def _ghi(thang: str, du: dict) -> None:
    p = _duong(thang)
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(du, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


def ghi_nhan(ten_user: str, tin_hieu: str = "", luc: datetime | None = None) -> None:
    """Ghi một tín hiệu hiện diện. Lần đầu trong ngày đặt GIỜ VÀO; mọi lần sau chỉ
    đẩy GIỜ RA + nguồn. Không bao giờ ném lỗi ra ngoài quá caller (caller ở auth
    phải bọc try) — chấm công hỏng không được làm hỏng đăng nhập.
    AGENT_LITE (03/08/2026): bản đóng gói không chấm công — hàm được gọi từ
    auth.lay_user MỌI request nên chặn tận gốc ở đây, không chỉ chặn route."""
    if os.getenv("AGENT_LITE", "").strip().lower() in ("1", "true"):
        return
    ten = (ten_user or "").strip()
    if not ten or ten == "khách":          # chế độ mở/dev — không chấm
        return
    luc = luc or datetime.now()
    ngay, thang, gio = luc.strftime("%Y-%m-%d"), luc.strftime("%Y-%m"), luc.strftime("%H:%M:%S")
    chu_dich = tin_hieu in ("dong_app", "dang_xuat")
    with _khoa:
        truoc = _da_ghi.get((ngay, ten))
        if truoc and not chu_dich and (luc - truoc).total_seconds() < 60:
            return                          # throttle: đỡ ghi đĩa mỗi request
        du = _doc(thang)
        n = du.setdefault(ngay, {}).setdefault(ten, {})
        n.setdefault("vao", gio)            # tín hiệu ĐẦU ngày = giờ vào, không đổi nữa
        n["ra"] = gio
        n["nguon_ra"] = NGUON_RA.get(tin_hieu, "Lần cuối thấy")
        _ghi(thang, du)
        _da_ghi[(ngay, ten)] = luc


def doc_ngay(ngay: str) -> dict:
    """{user: {vao, ra, nguon_ra}} của một ngày (YYYY-MM-DD) — cho trang Nhân sự."""
    return _doc(ngay[:7]).get(ngay, {})


def tong_gio(vao: str, ra: str) -> str:
    """'08:02:11'→'17:45:00' = '9g43'. Thiếu/sai dạng → '' (không bịa số)."""
    try:
        a = datetime.strptime(vao, "%H:%M:%S")
        b = datetime.strptime(ra, "%H:%M:%S")
        s = int((b - a).total_seconds())
        if s < 0:
            return ""
        return f"{s // 3600}g{(s % 3600) // 60:02d}"
    except (TypeError, ValueError):
        return ""


def gio_chu(giay: int) -> str:
    """Tổng giây → '112g30' cho bảng công. 0/âm → '' (không bịa số)."""
    if not giay or giay < 0:
        return ""
    return f"{giay // 3600}g{(giay % 3600) // 60:02d}"


# ── BẢNG CÔNG KỲ THÁNG + CHỐT CÔNG (HR Hub, DE.md mục 10) ──────────────────────

def bang_cong_thang(thang: str) -> dict:
    """Gộp file tháng thành bảng công per user:
    {user: {so_ngay, tong_giay, ngay_cuoi}} — chỉ cộng ngày có cặp vào/ra hợp lệ,
    ngày thiếu giờ ra thì vẫn đếm CÓ MẶT nhưng không cộng giờ (không bịa số)."""
    ra: dict[str, dict] = {}
    for ngay, nguoi in sorted(_doc(thang).items()):
        for ten, d in nguoi.items():
            m = ra.setdefault(ten, {"so_ngay": 0, "tong_giay": 0, "ngay_cuoi": ""})
            if d.get("vao"):
                m["so_ngay"] += 1
                m["ngay_cuoi"] = max(m["ngay_cuoi"], ngay)
            try:
                a = datetime.strptime(d.get("vao", ""), "%H:%M:%S")
                b = datetime.strptime(d.get("ra", ""), "%H:%M:%S")
                s = int((b - a).total_seconds())
                if s > 0:
                    m["tong_giay"] += s
            except (TypeError, ValueError):
                pass
    return ra


def _thu_muc_chot() -> Path:
    return Path(os.getenv("CHAM_CONG_CHOT_DIR", "nhan-su/cham-cong-chot"))


def doc_chot(thang: str) -> dict | None:
    """Bản chốt công của kỳ (None = chưa chốt)."""
    p = _thu_muc_chot() / f"{thang}.json"
    if not p.is_file():
        return None
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, dict) else None
    except ValueError:
        return None


def chot_ky(thang: str, nguoi_chot: str) -> dict:
    """CHỐT CÔNG kỳ tháng — file chốt CHỈ-THÊM: mỗi kỳ ghi ĐÚNG MỘT LẦN, đã chốt
    thì từ chối (không ghi đè lịch sử — đúng lệ sổ chỉ-ghi-thêm hệ cũ). Ghi
    nguyên tử tmp + os.replace."""
    if not re.fullmatch(r"\d{4}-\d{2}", thang or ""):
        raise ValueError("Kỳ phải dạng YYYY-MM.")
    if doc_chot(thang) is not None:
        raise ValueError(f"Kỳ {thang} đã chốt rồi — bản chốt không ghi đè được.")
    ban = {"ky": thang, "chot_luc": datetime.now().isoformat(timespec="seconds"),
           "nguoi_chot": nguoi_chot, "bang": bang_cong_thang(thang)}
    p = _thu_muc_chot() / f"{thang}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(ban, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)
    return ban
