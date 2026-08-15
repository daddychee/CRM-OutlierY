"""Tài liệu liên quan — BẢN RẺ (user chốt 07/08): dùng đúng hạ tầng embedding/search đã có
để, ngay lúc nạp tài liệu MỚI, tìm top tài liệu gần nghĩa nhất trong TOÀN KHO và LƯU LẠI
thành quan hệ BỀN — khác quan hệ NHẤT THỜI lúc trả lời câu hỏi (search kéo nhiều tài liệu
về một câu trả lời rồi biến mất, không ghi lại ở đâu).

Thuần vector similarity, KHÔNG gọi LLM — cùng độ đo + ngưỡng khởi điểm với ung_vien_qa
(qa_pipeline.py, NGUONG_LIEN_QUAN_QA=0.3) để nhất quán trong hệ; "vì sao liên quan" (diễn
giải bằng LLM) là bản ĐẮT, để sau nếu cần (user đã chốt làm bản rẻ trước).

Lưu vào 1 file JSON dùng chung `tai_lieu_lien_quan.json` (khuôn nhom_kho_thieu.json) —
KHÔNG đụng CATALOG_HEADER (đổi schema catalog kéo theo sửa hàng trăm test cố định cột).
RBAC: quan hệ NỘI DUNG là sự thật khách quan (tính không lọc quyền), nhưng khi HIỂN THỊ
cho một người xem thì nơi gọi (route) phải tự lọc theo tài liệu người đó được thấy — hàm
ở đây chỉ trả nguyên danh sách đã lưu, không tự làm RBAC (không có "user" ở tầng lưu trữ).
"""

import json
import os
from pathlib import Path

SO_LUONG_MAC_DINH = 5


def _duong_dan(kho: Path) -> Path:
    return kho / "tai_lieu_lien_quan.json"


def _doc_toan_bo(kho: Path) -> dict:
    f = _duong_dan(kho)
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def doc_lien_quan(doc_code: str, kho: Path | None = None) -> list[dict]:
    """Danh sách tài liệu liên quan ĐÃ LƯU cho doc_code — [{ma, tieu_de, diem}], mới nhất
    theo lần tính gần nhất. Chưa tính bao giờ / không còn liên quan gì → []."""
    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    return _doc_toan_bo(kho).get(doc_code, [])


def _ma_cung_ho(doc_code: str) -> set[str]:
    """Các mã coi là CÙNG một tài liệu với doc_code (gốc + -QA/-PT của chính nó, và ngược
    lại nếu doc_code chính nó là -QA/-PT thì tính cả gốc) — quan hệ này đã TƯỜNG MINH qua
    cấu trúc cha-con, không cần vector 'phát hiện' lại, tránh liệt kê thứ đã biết rồi."""
    from src.qa_bo_sung import ma_goc_tu_qa
    from src.tong_hop_neo import ma_goc_tu_pt

    goc = ma_goc_tu_qa(ma_goc_tu_pt(doc_code))
    return {doc_code, goc, f"{goc}-QA", f"{goc}-PT"}


def tinh_va_luu_lien_quan(doc_code: str, tieu_de: str, keywords: str, client,
                          kho: Path | None = None,
                          so_luong: int = SO_LUONG_MAC_DINH) -> list[dict]:
    """Tìm top tài liệu gần nghĩa nhất trong TOÀN KHO bằng chính câu hỏi = tiêu đề + từ khóa
    của tài liệu vừa nạp (không cần đọc lại nội dung file — tiêu đề/từ khóa đã đủ làm truy
    vấn, giống cách người dùng thật sẽ hỏi). KHÔNG lọc quyền khi TÍNH (quan hệ nội dung là
    sự thật khách quan, không phụ thuộc ai đang xem) — nơi HIỂN THỊ tự lọc theo người xem.

    Ngưỡng NGUONG_LIEN_QUAN_TAI_LIEU (.env, mặc định 0.3 — cùng điểm khởi đầu
    NGUONG_LIEN_QUAN_QA, đo dữ liệu thật rồi chỉnh sau như các ngưỡng khác trong hệ).
    Ghi ĐÈ toàn bộ danh sách cũ của doc_code (không nối dồn — luôn phản ánh lần tính mới
    nhất). Không đủ ngưỡng / query rỗng → ghi rỗng (không bịa quan hệ), KHÔNG raise."""
    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    query = f"{tieu_de.strip()}. {keywords.strip()}".strip(". ")
    loai_tru = _ma_cung_ho(doc_code)
    ds: list[dict] = []
    if query:
        chunks = client.search(query, {"effective_status": "Còn hiệu lực"}, user=None)
        nguong = float(os.getenv("NGUONG_LIEN_QUAN_TAI_LIEU", "0.3"))
        tot: dict[str, dict] = {}
        for c in chunks:
            diem = float(c.get("rerank_score", c.get("similarity", 0.0)) or 0.0)
            if diem < nguong:
                continue
            md = c.get("document_metadata") or {}
            ma = md.get("doc_code") or c.get("document_id")
            if not ma or ma in loai_tru:
                continue
            if ma not in tot or diem > tot[ma]["diem"]:
                tot[ma] = {"ma": ma, "tieu_de": md.get("title") or ma, "diem": round(diem, 4)}
        ds = sorted(tot.values(), key=lambda d: d["diem"], reverse=True)[:so_luong]

    toan_bo = _doc_toan_bo(kho)
    if ds:
        toan_bo[doc_code] = ds
    else:
        toan_bo.pop(doc_code, None)
    kho.mkdir(parents=True, exist_ok=True)
    tam = _duong_dan(kho).with_suffix(".json.tmp")
    tam.write_text(json.dumps(toan_bo, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, _duong_dan(kho))
    return ds
