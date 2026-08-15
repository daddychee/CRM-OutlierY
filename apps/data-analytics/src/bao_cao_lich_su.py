"""Lịch sử báo cáo chẩn đoán per-user — Tầng 1 (song song src/lich_su.py, cùng khuôn).

Mỗi user một file bao-cao-lich-su/<tên-an-toàn>.json (BAO_CAO_DIR, mặc định
./bao-cao-lich-su — GITIGNORE vì chứa dữ liệu vận hành). File report GỐC lưu riêng
ở bao-cao-goc/ (BAO_CAO_GOC_DIR) để Tầng 2 (LLM neo nguyên tắc data-analytics đưa
tóm tắt vào Qdrant) đọc lại + để chạy lại bằng luật mới sau này.

Ghi NGUYÊN TỬ (file tạm + os.replace), an-toàn-hóa tên chống path traversal, thời
gian TRUYỀN TỪ NGOÀI vào (route tạo bằng datetime.now) — y hệt lich_su.py.
"""

import hashlib
import json
import os
import re
from pathlib import Path


def _ten_file(ten_user: str) -> str:
    """An toàn hóa tên file JSON per-user (chống path traversal — copy nguyên lich_su)."""
    sach = re.sub(r"[^0-9A-Za-z_-]", "-", ten_user)
    if sach != ten_user or not sach.strip("-"):
        sach = f"{sach.strip('-') or 'user'}-{hashlib.sha1(ten_user.encode()).hexdigest()[:8]}"
    return f"{sach}.json"


def _ten_goc_an_toan(ten_file: str) -> str:
    """An toàn hóa tên file GỐC (giữ đuôi để tải lại). Chỉ giữ chữ/số/._-, diệt '..'."""
    sach = re.sub(r"[^0-9A-Za-z._-]", "-", Path(ten_file).name).replace("..", "-")
    return sach.strip("-.") or "report.csv"


def _duong_dan(ten_user: str) -> Path:
    return Path(os.getenv("BAO_CAO_DIR", "bao-cao-lich-su")) / _ten_file(ten_user)


def _ghi_nguyen_tu(p: Path, du_lieu) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(du_lieu, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


def doc_bao_cao_list(ten_user: str) -> list[dict]:
    """Danh sách bản ghi báo cáo của user (mới nhất TRƯỚC). Chưa có/hỏng → [] (không sập)."""
    p = _duong_dan(ten_user)
    if not p.is_file():
        return []
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, list) else []
    except ValueError:
        return []


def luu_bao_cao(ten_user: str, ban_ghi: dict, thoi_gian_iso: str) -> dict:
    """Thêm 1 bản ghi vào ĐẦU danh sách (mới nhất lên trên). Module gắn thoi_gian +
    nguoi_chay (bất biến) từ tham số; phần còn lại (id/ten_file_goc/duong_dan_goc/kenh)
    do route dựng. Ghi nguyên tử."""
    rec = {**ban_ghi, "thoi_gian": thoi_gian_iso, "nguoi_chay": ten_user}
    ds = doc_bao_cao_list(ten_user)
    ds.insert(0, rec)
    _ghi_nguyen_tu(_duong_dan(ten_user), ds)
    return rec


def doc_mot_bao_cao(ten_user: str, bao_cao_id: str) -> dict | None:
    """1 bản ghi theo id trong danh sách của user, hoặc None."""
    return next((r for r in doc_bao_cao_list(ten_user) if r.get("id") == bao_cao_id), None)


def doc_bao_cao_moi_nguoi() -> list[dict]:
    """LỊCH SỬ DÙNG CHUNG (01/08/2026, user chốt 'các user khác không xem được lịch
    sử cũ'): gộp báo cáo của MỌI người trong BAO_CAO_DIR, mới nhất trước. Bản ghi
    sẵn nguoi_chay (luu_bao_cao gắn bất biến từ đầu) nên luôn biết ai chạy."""
    thu_muc = Path(os.getenv("BAO_CAO_DIR", "bao-cao-lich-su"))
    if not thu_muc.is_dir():
        return []
    tat_ca: list[dict] = []
    for f in thu_muc.glob("*.json"):
        try:
            du = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(du, list):
            tat_ca.extend(r for r in du if isinstance(r, dict))
    tat_ca.sort(key=lambda r: r.get("thoi_gian") or "", reverse=True)
    return tat_ca


def danh_sach_ten_kenh() -> list[str]:
    """Tên kênh đã dùng (Issue 2 §1 — định danh nối nhiều báo cáo cùng kênh qua thời gian),
    DÙNG CHUNG mọi người đúng khuôn doc_bao_cao_moi_nguoi(). Nguồn đã sort mới nhất trước nên
    chỉ cần giữ lần gặp ĐẦU TIÊN mỗi tên → danh sách tự xếp theo lần dùng gần nhất trước, hợp
    gợi ý dropdown lúc nạp báo cáo mới."""
    thay, da_thay = [], set()
    for r in doc_bao_cao_moi_nguoi():
        ten = str(r.get("ten_kenh") or "").strip()
        if ten and ten not in da_thay:
            da_thay.add(ten)
            thay.append(ten)
    return thay


def tim_bao_cao(bao_cao_id: str, goi_y_nguoi: str = "") -> tuple[str | None, dict | None]:
    """Tìm 1 báo cáo theo id trong lịch sử DÙNG CHUNG: thử người gợi ý trước (rẻ —
    link cũ ?nguoi= vẫn nhanh), không thấy mới quét mọi người. Trả (nguoi_chay,
    bản_ghi) — cache diễn giải luôn ghi về ĐÚNG file người chạy, ai xem không đổi
    chỗ lưu. Không thấy → (None, None)."""
    if goi_y_nguoi:
        rec = doc_mot_bao_cao(goi_y_nguoi, bao_cao_id)
        if rec is not None:
            return goi_y_nguoi, rec
    for rec in doc_bao_cao_moi_nguoi():
        if rec.get("id") == bao_cao_id:
            return rec.get("nguoi_chay") or "", rec
    return None, None


def _cap_nhat_bao_cao(ten_user: str, bao_cao_id: str, sua_fn) -> bool:
    """Tìm bản ghi theo id trong list của user, áp sua_fn(rec) TẠI CHỖ, ghi nguyên tử.
    Trả True nếu tìm thấy. Dùng cho cache diễn giải (cập nhật lười 1 ô của bản ghi có sẵn)."""
    ds = doc_bao_cao_list(ten_user)
    for rec in ds:
        if rec.get("id") == bao_cao_id:
            sua_fn(rec)
            _ghi_nguyen_tu(_duong_dan(ten_user), ds)
            return True
    return False


def luu_dien_giai_video(ten_user: str, bao_cao_id: str, chi_muc: int, dien_giai: dict) -> bool:
    """Cache diễn giải LLM 1 video vào bản ghi báo cáo. KHÓA = (bao_cao_id, chi_muc) — KHÔNG
    chỉ theo video: cùng video ở 2 report khác kỳ có số liệu khác → diễn giải khác. Ghi nguyên tử."""
    def sua(rec):
        rec.setdefault("dien_giai_video", {})[str(chi_muc)] = dien_giai
    return _cap_nhat_bao_cao(ten_user, bao_cao_id, sua)


def doc_dien_giai_video(ten_user: str, bao_cao_id: str, chi_muc: int) -> dict | None:
    """Đọc cache diễn giải 1 video theo (bao_cao_id, chi_muc). Chưa có → None."""
    rec = doc_mot_bao_cao(ten_user, bao_cao_id)
    if rec is None:
        return None
    return (rec.get("dien_giai_video") or {}).get(str(chi_muc))


def luu_dien_giai_9muc(ten_user: str, bao_cao_id: str, dg_map: dict) -> bool:
    """Ghi/GHI ĐÈ cache diễn giải LLM khung 9 mục ({ma: dien_giai}) vào bản ghi báo cáo. Dùng
    khi Phân tích lại (làm mới) — xem lại đọc thẳng rec['dien_giai_9muc'], không gọi API."""
    return _cap_nhat_bao_cao(ten_user, bao_cao_id,
                             lambda rec: rec.__setitem__("dien_giai_9muc", dg_map))


def luu_file_goc(bao_cao_id: str, ten_file: str, noi_dung_bytes: bytes) -> str:
    """Copy report GỐC vào bao-cao-goc/<id>__<tên-an-toàn>. Tên có tiền tố id nên tra
    lại chỉ cần id (không đoán được user). Ghi nguyên tử; trả đường dẫn (str)."""
    thu_muc = Path(os.getenv("BAO_CAO_GOC_DIR", "bao-cao-goc"))
    thu_muc.mkdir(parents=True, exist_ok=True)
    p = thu_muc / f"{bao_cao_id}__{_ten_goc_an_toan(ten_file)}"
    tam = p.with_name(p.name + ".tmp")
    tam.write_bytes(noi_dung_bytes)
    os.replace(tam, p)
    return str(p)
