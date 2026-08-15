"""Lớp LÕI cho tính năng "bổ sung câu trả lời vào tài liệu gốc dưới dạng Q&A".

TRIẾT LÝ: Q&A là TRI THỨC NGANG HÀNG với tài liệu gốc, KHÔNG phải ghi chú phụ.
Mỗi tài liệu gốc có 1 FILE Q&A đi kèm (mã riêng hậu tố -QA), KHÔNG đụng file gốc
một chữ. File Q&A nạp vào Qdrant như mọi tài liệu → câu hỏi về sau tra ra bình
đẳng với tài liệu gốc. File Q&A KẾ THỪA TOÀN BỘ quyền của gốc (department /
access_level / min_level / effective_status) → ai xem được gốc mới xem được Q&A,
không rò quyền. Quyền đọc lại từ catalog gốc MỖI LẦN bổ sung → gốc đổi quyền thì
Q&A theo, luôn nhất quán.

BẤT BIẾN: không đụng file gốc; Q&A kế thừa quyền gốc (không tự đặt khác); doc_code
gốc và doc_code Q&A đều BẤT BIẾN (khóa nối catalog↔Qdrant↔file); ghi file + catalog
NGUYÊN TỬ (file tạm + os.replace) như các chỗ khác trong app.

Chỉ hàm thuần + test — chưa có giao diện/route. Nền tảng cho các lệnh sau (Owner
bấm "Duyệt" sẽ gọi them_cap_qa). Import app helpers TẠI CHỖ như kho_thieu.py để
tránh vòng import.
"""

import os
import re
from pathlib import Path

HAU_TO_QA = "-QA"
# 1 cặp Q&A giữ CẢ hỏi lẫn đáp trong cùng đoạn để _cat_doan cắt không rớt ngữ cảnh
_MAU_CAP = re.compile(r"## Hỏi: (.*?)\n\nĐáp: (.*?)\n\n_\(Bổ sung (.*?)\)_", re.DOTALL)


def ma_qa(doc_code_goc: str) -> str:
    """Mã Q&A = mã gốc + '-QA' (KD-2026-1814CB → KD-2026-1814CB-QA)."""
    return f"{doc_code_goc}{HAU_TO_QA}"


def ma_goc_tu_qa(ma: str) -> str:
    """Trả lại mã gốc từ mã Q&A (bỏ hậu tố '-QA'; mã không phải Q&A → giữ nguyên)."""
    return ma[: -len(HAU_TO_QA)] if la_ma_qa(ma) else ma


def la_ma_qa(doc_code: str) -> bool:
    return doc_code.endswith(HAU_TO_QA)


def dinh_dang_cap_qa(cau_hoi: str, cau_tra_loi: str, thoi_gian_iso: str) -> str:
    """1 khối text cho 1 cặp — định dạng cố định để doc_cap_qa parse lại được."""
    return f"## Hỏi: {cau_hoi.strip()}\n\nĐáp: {cau_tra_loi.strip()}\n\n_(Bổ sung {thoi_gian_iso})_\n\n"


def _ghi_nguyen_tu(path: Path, noi_dung: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tam = path.with_name(path.name + ".tmp")
    tam.write_text(noi_dung, encoding="utf-8")
    os.replace(tam, path)


def them_cap_qa(doc_code_goc: str, cau_hoi: str, cau_tra_loi: str, client,
                thoi_gian_iso: str, kho: Path | None = None) -> dict:
    """HÀM CHÍNH: tạo/nối 1 cặp Q&A cho tài liệu gốc, nạp Qdrant, ghi catalog.

    Lần đầu (chưa có dòng catalog -QA) → tạo file .md (tiêu đề + cặp đầu), nạp mới
    (upload_document), ghi 1 dòng catalog -QA. Lần sau → nối cặp vào cuối file rồi
    cập nhật lại Qdrant (cap_nhat_noi_dung xóa chunk cũ theo doc_code + nạp lại,
    chống mồ côi), KHÔNG ghi thêm dòng catalog. Quyền đọc lại từ gốc mỗi lần."""
    from src.main import (DEPT_FOLDER, doc_catalog, duong_dan_khong_trung, ghi_catalog)

    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    cat = doc_catalog(kho)
    row = next((r for r in cat if r["Mã tài liệu"] == doc_code_goc), None)
    if row is None:
        raise ValueError("Không thấy tài liệu gốc để bổ sung Q&A")

    ma = ma_qa(doc_code_goc)
    tieu_de_goc = row.get("Tiêu đề") or doc_code_goc
    ngan = (row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(row.get("Bộ phận"), "00_Chung")
    thu_muc = kho / ngan
    ten_file = f"{ma}_Q&A-bo-sung.md"

    # "Lần đầu" = CHƯA có dòng catalog Q&A (nguồn sự thật, giữ file↔catalog nhất quán).
    # File hiện có định vị qua tên đã lưu trong catalog (như luồng cập-nhật-nội-dung).
    qa_row = next((r for r in cat if r["Mã tài liệu"] == ma), None)
    lan_dau = qa_row is None
    tieu_de_file = f"# Q&A bổ sung cho: {tieu_de_goc} ({doc_code_goc})\n\n"
    cap = dinh_dang_cap_qa(cau_hoi, cau_tra_loi, thoi_gian_iso)
    if lan_dau:
        file_qa = duong_dan_khong_trung(thu_muc, ten_file)
        _ghi_nguyen_tu(file_qa, tieu_de_file + cap)
    else:
        ten_da_luu = (qa_row.get("Tên file mới") or ten_file).strip() or ten_file
        file_qa = thu_muc / ten_da_luu
        cu = file_qa.read_text(encoding="utf-8") if file_qa.is_file() else tieu_de_file
        _ghi_nguyen_tu(file_qa, cu + cap)

    # Metadata Q&A KẾ THỪA quyền từ dòng GỐC (đọc lại mỗi lần → gốc đổi quyền thì theo)
    ml = (row.get("Level tối thiểu") or "").strip()
    metadata_qa = {
        "title": f"Q&A bổ sung — {tieu_de_goc}",
        "keywords": row.get("Chủ đề/Từ khóa") or "",
        "owner": row.get("Phụ trách") or "",
        "version": "v1",
        "department": row.get("Bộ phận") or "",
        "doc_type": "Khác",
        "effective_status": row.get("Hiệu lực") or "",
        "access_level": row.get("Mức truy cập") or "",
        "min_level": int(ml) if ml.isdigit() else None,
        "doc_code": ma,
        "import_date": thoi_gian_iso[:10],
        "original_filename": file_qa.name,
        # Supervisor: Q&A KẾ THỪA tầng nguồn của gốc (Q&A của tài liệu chuyên gia vẫn tầng đó)
        "tang_nguon": row.get("Tầng nguồn") or "noi_bo",
        "nguon_ten": row.get("Tên nguồn") or "Official",
    }

    if lan_dau:
        doc_id = client.upload_document(str(file_qa), metadata_qa)  # TÁI DÙNG pipeline có sẵn
        ghi_catalog(kho, [
            ma, metadata_qa["import_date"], metadata_qa["title"], metadata_qa["department"],
            metadata_qa["doc_type"], metadata_qa["effective_status"], "v1",
            metadata_qa["access_level"],
            metadata_qa["min_level"] if metadata_qa["min_level"] is not None else "",
            metadata_qa["keywords"], metadata_qa["owner"], file_qa.name, ngan,
            "false", doc_id, "", metadata_qa["tang_nguon"], metadata_qa["nguon_ten"]])
    else:
        client.cap_nhat_noi_dung(str(file_qa), metadata_qa)  # xóa chunk cũ + nạp lại (chống mồ côi)

    return {"ok": True, "ma_qa": ma, "file": file_qa.name, "so_cap_moi_them": 1,
            "lan_dau": lan_dau, "so_chunk": client.dem_chunk_doc_code(ma)}


def doc_cap_qa(doc_code_goc: str, kho: Path | None = None) -> list[dict]:
    """Đọc file Q&A của doc_code_goc → list [{hoi, dap, thoi_gian}]. Chưa có → []."""
    from src.main import DEPT_FOLDER, doc_catalog

    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    ma = ma_qa(doc_code_goc)
    qa_row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == ma), None)
    if qa_row is None:
        return []
    ngan = (qa_row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(qa_row.get("Bộ phận"), "00_Chung")
    file_qa = kho / ngan / ((qa_row.get("Tên file mới") or f"{ma}_Q&A-bo-sung.md").strip())
    if not file_qa.is_file():
        return []
    return [{"hoi": h.strip(), "dap": d.strip(), "thoi_gian": t.strip()}
            for h, d, t in _MAU_CAP.findall(file_qa.read_text(encoding="utf-8"))]
