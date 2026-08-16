"""Lịch sử hội thoại per-user — Mảnh D1 Đợt 2.

Mỗi user một file lich-su/<tên-an-toàn>.json (thư mục LICH_SU_DIR, mặc định ./lich-su —
GITIGNORE vì chứa nội dung hỏi-đáp). Ghi NGUYÊN TỬ: file tạm + os.replace.

Mỗi lượt lưu kèm doc_codes đã trích — D1 chưa dùng nhưng D2 (ẩn lượt theo quyền
tài liệu) cần, nên lưu ngay từ đầu. Thời gian truyền TỪ NGOÀI vào (route tạo bằng
datetime.now) — module KHÔNG gọi now() để test dễ và tái lập được.
"""

import hashlib
import json
import os
import re
from pathlib import Path


def _ten_file(ten_user: str) -> str:
    """An toàn hóa tên file: chỉ giữ chữ/số/gạch (chống path traversal — '.', '/'
    đều bị thay). Tên bị đổi khi lọc → gắn thêm hash ngắn để không đụng độ nhau."""
    sach = re.sub(r"[^0-9A-Za-z_-]", "-", ten_user)
    if sach != ten_user or not sach.strip("-"):
        sach = f"{sach.strip('-') or 'user'}-{hashlib.sha1(ten_user.encode()).hexdigest()[:8]}"
    return f"{sach}.json"


def _duong_dan(ten_user: str) -> Path:
    return Path(os.getenv("LICH_SU_DIR", "lich-su")) / _ten_file(ten_user)


def _nang_cap(tho) -> dict:
    """YC4: mảng lượt PHẲNG (dạng cũ) → {"phien": [{id, ten, thoi_gian_tao, luot}]}
    TRONG BỘ NHỚ. IDEMPOTENT: đã dạng mới → trả nguyên; id phiên gói cố định
    "lich-su-cu" nên chạy lại bao nhiêu lần cũng không nhân đôi."""
    if isinstance(tho, dict) and isinstance(tho.get("phien"), list):
        return tho
    cac_luot = tho if isinstance(tho, list) else []
    if not cac_luot:
        return {"phien": []}
    return {"phien": [{
        "id": "lich-su-cu",
        "ten": "Lịch sử cũ",
        "thoi_gian_tao": cac_luot[0].get("thoi_gian", ""),
        "luot": cac_luot,
    }]}


def _doc_du_lieu(ten_user: str) -> dict:
    p = _duong_dan(ten_user)
    if not p.is_file():
        return {"phien": []}
    try:
        return _nang_cap(json.loads(p.read_text(encoding="utf-8")))
    except ValueError:
        return {"phien": []}  # file hỏng → coi như rỗng, không sập trang


def _ghi_du_lieu(ten_user: str, du_lieu: dict) -> None:
    p = _duong_dan(ten_user)
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(du_lieu, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


def doc_phien(ten_user: str) -> list[dict]:
    """Các PHIÊN trò chuyện của user (dạng mới YC4); file dạng cũ tự nâng trong bộ nhớ."""
    return _doc_du_lieu(ten_user)["phien"]


def danh_sach_nguoi_dung() -> list[str]:
    """(THÊM Ở V2) Người có lịch sử hội thoại — quét LICH_SU_DIR (mỗi user 1 file
    <tên-an-toàn>.json), cùng khuôn doc_bao_cao_moi_nguoi của data-analytics.
    Dùng cho trang /giam-sat: v2 app không còn sổ user riêng (users.txt nghỉ hưu,
    IAM ở tầng nền) nên cây giám sát dựng từ dữ liệu hội thoại có thật.
    Tên trả về là TÊN FILE đã an toàn hóa (stem) — doc_phien(stem) đọc lại đúng file
    vì _ten_file idempotent trên tên đã sạch."""
    tm = Path(os.getenv("LICH_SU_DIR", "lich-su"))
    if not tm.is_dir():
        return []
    return sorted((f.stem for f in tm.glob("*.json")), key=str.lower)


def nang_cap_file(duong_dan: Path) -> bool:
    """Migration ghi XUỐNG ĐĨA một file lịch sử — script dùng, chạy lại vô hại
    (đã dạng mới → False, không ghi gì)."""
    try:
        tho = json.loads(duong_dan.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if isinstance(tho, dict) and isinstance(tho.get("phien"), list):
        return False
    moi = _nang_cap(tho)
    tam = duong_dan.with_name(duong_dan.name + ".tmp")
    tam.write_text(json.dumps(moi, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, duong_dan)
    return True


def doc_lich_su(ten_user: str) -> list[dict]:
    """Mọi lượt PHẲNG cũ → mới (nối các phiên) — GIỮ TƯƠNG THÍCH cho D2/feedback/
    trí nhớ hội thoại; caller cũ không phải đổi."""
    return [luot for ph in doc_phien(ten_user) for luot in ph["luot"]]


def loc_theo_quyen(cac_luot: list[dict], user: dict, rag) -> list[dict]:
    """MẢNH D2: khi CHÍNH CHỦ xem lịch sử của mình — ẨN CẢ LƯỢT nếu có bất kỳ
    doc_code nào user HIỆN TẠI không đủ quyền xem (bị hạ cấp/chuyển bộ phận sau này).
    Ẩn lặng lẽ, không để lại dấu vết (nhất quán tinh thần Rule 2).

    - Lượt doc_codes RỖNG ("tài liệu chưa nêu") → GIỮ (không có gì để chặn).
    - doc_code đã XÓA khỏi kho → coi như không được xem → ẩn an toàn.
    - Tái dùng đúng luật quyền Mảnh B (rag._duoc_xem); metadata tra MỘT lần cả lô.
    - Owner giám sát người khác KHÔNG đi qua hàm này (route giữ nguyên bản)."""
    if not (user and user.get("bo_phan")):
        return cac_luot  # chế độ mở/khách: không có luật quyền để áp

    can_tra = sorted({ma for luot in cac_luot for ma in luot.get("doc_codes", [])})
    metadata = rag.metadata_theo_doc_code(can_tra)  # batch — 1 truy vấn cho mọi lượt

    def xem_duoc_het(luot: dict) -> bool:
        return all(ma in metadata and rag._duoc_xem(metadata[ma], user)
                   for ma in luot.get("doc_codes", []))

    return [luot for luot in cac_luot if xem_duoc_het(luot)]


def luu_luot(ten_user: str, cau_hoi: str, cau_tra_loi: str,
             danh_sach_doc_code: list, thoi_gian_iso: str,
             bi_chan_quyen: bool = False, phien_id: str | None = None) -> None:
    """Ghi thêm 1 lượt hỏi-đáp. Đọc toàn bộ → thêm → ghi file tạm → os.replace.

    Nền YC4/YC7: lượt được đánh dấu chua_tra_loi_duoc=True khi câu trả lời kiểu
    "tài liệu chưa nêu" VÀ không phải bị chặn quyền (kho thiếu THẬT) — để sau này
    nhận ra "câu này giờ đã có tài liệu trả lời" mà highlight phiên."""
    from src.qa_pipeline import la_cau_khong_tra_loi_duoc  # import tại chỗ — tránh vòng

    du_lieu = _doc_du_lieu(ten_user)  # file dạng cũ tự nâng — KHÔNG bao giờ ghi lại dạng cũ
    # YC4 (b): frontend gửi phien_id (crypto.randomUUID; "Cuộc trò chuyện mới" = id
    # mới) → gắn lượt vào ĐÚNG phiên, tạo phiên nếu chưa có — tên mặc định là câu
    # hỏi ĐẦU của phiên. Caller cũ không truyền id → gắn phiên cuối như trước.
    sach = re.sub(r"[^0-9A-Za-z-]", "", str(phien_id or ""))[:36]  # chống id bẩn/dài
    if sach:
        ph = next((p for p in du_lieu["phien"] if p["id"] == sach), None)
        if ph is None:
            ph = {"id": sach, "ten": cau_hoi[:80], "thoi_gian_tao": thoi_gian_iso,
                  "luot": []}
            du_lieu["phien"].append(ph)
    else:
        ph = du_lieu["phien"][-1] if du_lieu["phien"] else None
        if ph is None:
            ph = {"id": "mac-dinh", "ten": cau_hoi[:80], "thoi_gian_tao": thoi_gian_iso,
                  "luot": []}
            du_lieu["phien"].append(ph)
    ph["luot"].append({
        "hoi": cau_hoi,
        "dap": cau_tra_loi,
        "doc_codes": list(danh_sach_doc_code),  # để D2 ẩn lượt theo quyền tài liệu
        "thoi_gian": thoi_gian_iso,
        "chua_tra_loi_duoc": la_cau_khong_tra_loi_duoc(cau_tra_loi) and not bi_chan_quyen,
    })
    _ghi_du_lieu(ten_user, du_lieu)


def doi_ten_phien(ten_user: str, phien_id: str, ten_moi: str) -> bool:
    """YC4 (c): user đổi tên phiên của MÌNH. Trả False nếu không thấy phiên."""
    du_lieu = _doc_du_lieu(ten_user)
    for ph in du_lieu["phien"]:
        if ph["id"] == phien_id:
            ph["ten"] = ten_moi.strip()[:80] or ph["ten"]
            _ghi_du_lieu(ten_user, du_lieu)
            return True
    return False


def phien_co_cau_da_giai(cac_luot: list[dict], user: dict | None, rag) -> bool:
    """Nền YC4/YC7: phiên có câu chưa-trả-lời-được mà GIỜ kho đã trả lời được chưa?

    Với mỗi lượt chua_tra_loi_duoc: chạy lại rag.search (LOCAL, rẻ — TUYỆT ĐỐI
    không gọi LLM). Coi là ĐÃ GIẢI khi search giờ trả về ít nhất 1 doc_code KHÔNG
    nằm trong doc_codes lúc hỏi — tức có TÀI LIỆU MỚI với câu đó. (Không dùng luật
    "search khác rỗng": kho thật luôn trả top-k chunk gần nghĩa kể cả khi không
    trả lời được — chính là bài học bug A bảng kho-thiếu; so-bằng-rỗng sẽ highlight
    bừa mọi phiên.) Lượt cũ không có cờ → bỏ qua, an toàn với dữ liệu cũ. CHỈ tầng
    noi_bo (07/08): câu chỉ tính "đã giải" khi kho CÔNG TY (thứ hỏi–đáp thường thật sự
    dùng) có tài liệu mới, không phải vì có ai thêm một nguồn ngoài trùng chủ đề."""
    for luot in cac_luot:
        if not luot.get("chua_tra_loi_duoc"):
            continue
        chunks = rag.search(luot["hoi"], {"effective_status": "Còn hiệu lực",
                                          "tang_nguon": "noi_bo"}, user=user)
        cu = set(luot.get("doc_codes") or [])
        if any(c["document_metadata"].get("doc_code") not in cu for c in chunks):
            return True
    return False
