"""Test nền YC4/YC7 — đánh dấu lượt kho-thiếu-thật + nhận biết phiên đã-có-lời-giải.
Chỉ rag.search (giả), TUYỆT ĐỐI không LLM."""

import os

os.environ["MOCK_MODE"] = "true"

from types import SimpleNamespace

from src.lich_su import doc_lich_su, luu_luot, phien_co_cau_da_giai


def _chunk(ma):
    return {"content": "x", "document_id": ma, "document_keyword": f"{ma}.docx",
            "similarity": 0.9, "document_metadata": {"doc_code": ma}}


def _rag_tra(cac_ma):
    """rag giả: search luôn trả các doc_code này; đếm để chắc KHÔNG gọi thừa."""
    rag = SimpleNamespace(so_lan=0)
    def search(cau, filters=None, user=None):
        rag.so_lan += 1
        return [_chunk(m) for m in cac_ma]
    rag.search = search
    return rag


def test_luu_luot_danh_dau_kho_thieu_that():
    luu_luot("u1", "lịch nghỉ?", "Tài liệu chưa nêu cụ thể điều này.", [], "T1")
    luu_luot("u1", "ngâm kênh?", "Tài liệu chưa nêu cụ thể.", [], "T2",
             bi_chan_quyen=True)                       # bị chặn quyền → KHÔNG đánh dấu
    luu_luot("u1", "đăng video?", "Đăng khung 19h-21h [KD-1].", ["KD-1"], "T3")
    cac_luot = doc_lich_su("u1")
    assert [l["chua_tra_loi_duoc"] for l in cac_luot] == [True, False, False]


def test_phien_da_giai_khi_co_tai_lieu_moi():
    """Câu kho-thiếu lúc hỏi trích KD-1 (không trả lời được) — giờ search ra thêm
    KD-2 (tài liệu MỚI) → phiên coi như đã có lời giải."""
    luu_luot("u2", "lịch nghỉ?", "Tài liệu chưa nêu cụ thể điều này.", ["KD-1"], "T1")
    assert phien_co_cau_da_giai(doc_lich_su("u2"), None, _rag_tra(["KD-1", "KD-2"])) is True


def test_khong_highlight_khi_van_la_tai_lieu_cu():
    """Search vẫn trả đúng các doc_code cũ (kho chưa thêm gì) → KHÔNG highlight —
    tránh vết xe bug A: kho thật luôn trả top-k nên 'khác rỗng' là vô nghĩa."""
    luu_luot("u3", "lịch nghỉ?", "Tài liệu chưa nêu cụ thể điều này.", ["KD-1"], "T1")
    assert phien_co_cau_da_giai(doc_lich_su("u3"), None, _rag_tra(["KD-1"])) is False


def test_phien_khong_co_cau_kho_thieu_khong_ton_search():
    luu_luot("u4", "đăng video?", "Đăng khung 19h [KD-1].", ["KD-1"], "T1")
    rag = _rag_tra(["KD-9"])
    assert phien_co_cau_da_giai(doc_lich_su("u4"), None, rag) is False
    assert rag.so_lan == 0                             # không có gì để chạy lại


def test_luot_cu_thieu_co_khong_vo():
    """Dữ liệu cũ (trước nền này) không có khóa chua_tra_loi_duoc → bỏ qua an toàn."""
    assert phien_co_cau_da_giai([{"hoi": "x", "dap": "y", "doc_codes": []}],
                                None, _rag_tra(["KD-1"])) is False
