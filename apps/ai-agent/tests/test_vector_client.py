"""Test lõi vector Qdrant chế độ mock + hàm cắt đoạn (thuần, không cần Qdrant) — chạy: pytest"""

import re

import pytest

from src.vector_client import QdrantClientWrapper, _cat_doan


@pytest.fixture
def client():
    return QdrantClientWrapper(mock=True)


def test_upload_tra_ve_document_id(client, tmp_path):
    f = tmp_path / "KD-2026-0099_Test.docx"
    # utf-8 tường minh — baseline hệ cũ: thiếu encoding làm cp1252 chết dấu tiếng Việt
    f.write_text("nội dung thử", encoding="utf-8")
    doc_id = client.upload_document(str(f), {"department": "Kinh doanh",
                                             "effective_status": "Còn hiệu lực"})
    assert isinstance(doc_id, str) and doc_id.startswith("doc-mock-")


def test_upload_bao_loi_khi_file_khong_ton_tai(client):
    with pytest.raises(FileNotFoundError):
        client.upload_document("khong-co-file-nay.docx", {})


def test_search_tra_ve_dung_cau_truc_chunk(client):
    chunks = client.search("quy trình đăng video")
    assert chunks
    for c in chunks:
        assert {"content", "document_id", "document_keyword",
                "similarity", "document_metadata"} <= set(c)
        assert "department" in c["document_metadata"]


def test_search_loc_theo_bo_phan(client):
    kd = client.search("video", filters={"department": "Kinh doanh"})
    assert kd and all(c["document_metadata"]["department"] == "Kinh doanh" for c in kd)

    vh = client.search("video", filters={"department": "Vận hành - Sản xuất"})
    assert vh and all(c["document_metadata"]["department"] == "Vận hành - Sản xuất" for c in vh)


def test_search_loc_ket_hop_hieu_luc(client):
    hits = client.search("video", filters={"department": "Kinh doanh",
                                           "effective_status": "Còn hiệu lực"})
    assert hits
    assert all(c["document_metadata"]["effective_status"] == "Còn hiệu lực" for c in hits)


def test_rerank_cau_hinh_mac_dinh_TAT(monkeypatch):
    """Rerank mặc định TẮT theo CODE (đổi từ BẬT ngày 03/09).

    ĐO THẬT trên kho 157 point / 19 tài liệu, 5 câu hỏi thật: BẬT 15,4–22,9s vs
    TẮT 0,12–0,25s — chậm hơn ~100 lần, mà 2/4 câu ra kết quả Y HỆT. Hệ quả khi
    bật: mỗi câu hỏi của nhân viên chờ ~20s, VÀ cứ 10 phút (cache canary hết hạn)
    health vượt trần 10s của vòng giám sát → sổ sự cố đầy cảnh báo giả.

    Đặt trong CODE chứ không chỉ .env vì .env bị gitignore, không theo repo sang
    máy khác — đúng bài học 19/07 đã áp cho HYBRID_SEARCH. Bật lại khi kho lên
    hàng trăm–nghìn chunk, và ĐO LẠI trước khi tin.

    Xóa biến env trước khi tạo client — test default trong CODE, không phụ thuộc
    .env của máy đang chạy."""
    monkeypatch.delenv("RERANK_SEARCH", raising=False)
    monkeypatch.delenv("RERANK_LAY_RONG", raising=False)
    c = QdrantClientWrapper(mock=True)
    assert c.rerank_search is False
    assert c.rerank_lay_rong == 20


def test_rerank_bat_lai_duoc_bang_env(monkeypatch):
    """Tắt là MẶC ĐỊNH, không phải gỡ tính năng — kho lớn bật lại bằng 1 dòng
    .env, không sửa code."""
    monkeypatch.setenv("RERANK_SEARCH", "true")
    assert QdrantClientWrapper(mock=True).rerank_search is True


def test_mock_khong_rerank_giu_nguyen_duong_cu(client):
    """Đường mock KHÔNG rerank (không tải model) — kết quả y hệt hành vi cũ."""
    chunks = client.search("quy trình đăng video")
    assert chunks
    assert all("rerank_score" not in c for c in chunks)  # mock không chấm lại
    assert chunks[0]["document_metadata"]["doc_code"] == "KD-2026-0042"  # thứ tự mẫu giữ nguyên


# ---- Cắt đoạn: hàm thuần, test không cần Qdrant ----

def _van_ban(so_cau: int) -> str:
    return " ".join(f"Câu thứ {i} có nội dung riêng biệt để kiểm tra cắt đoạn."
                    for i in range(so_cau))


def test_cat_doan_khong_cat_giua_cau_va_dung_co():
    chunks = _cat_doan(_van_ban(300))  # ~3000 từ → nhiều chunk
    assert len(chunks) > 1
    for c in chunks:
        assert c.rstrip().endswith(".")          # kết thúc đúng ranh giới câu
        assert len(c.split()) <= 600             # trong khoảng 400-600 từ yêu cầu


def test_cat_doan_co_chong_lan():
    chunks = _cat_doan(_van_ban(300))
    so_cau = lambda c: set(re.findall(r"Câu thứ (\d+)", c))
    # câu cuối của chunk trước xuất hiện lại ở đầu chunk sau
    assert so_cau(chunks[0]) & so_cau(chunks[1])


# ══ 01/08/2026 — VAN AN TOÀN: Qdrant chết không được giết cả app ══

class _EmbedStub:
    def __init__(self, *a, **k): pass
    def embed(self, xs): return iter([[0.0] * 8 for _ in xs])


class _QdrantChet:
    """Mọi lời gọi đều 'connection refused' — mô phỏng Docker/Qdrant sập."""
    def __init__(self, *a, **k): pass
    def __getattr__(self, ten):
        def _no(*a, **k):
            raise ConnectionError("refused")
        return _no


class _QdrantSong:
    def __init__(self, *a, **k): pass
    def collection_exists(self, *a, **k): return True
    def create_payload_index(self, *a, **k): return None
    def get_aliases(self):
        class _A:
            aliases = [type("X", (), {"alias_name": "kho_tri_thuc"})]
        return _A()


def _co_fastembed():
    try:
        import fastembed  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _co_fastembed(),
                    reason="Thiếu fastembed — gói nặng chỉ cần khi chạy thật (embedding "
                           "local); venv test v2 không cài, test này chạy ở máy chạy thật")
def test_qdrant_chet_khong_giet_app_va_tu_noi_lai(monkeypatch):
    """Sự cố 14:57 01/08 (Docker Desktop sập): Qdrant chết lúc khởi động từng giết
    CẢ app thành crash loop ~20 phút — cổng 8000 gánh login + proxy 6 app + chấm
    công cũng chết oan. Ghim: (1) init sống sót khi Qdrant chết; (2) search báo
    lỗi rõ nghĩa thay vì 500 mù; (3) Qdrant sống dậy là kho TỰ NỐI LẠI không cần
    restart app."""
    import fastembed
    import pytest as _pytest
    import qdrant_client as _qc

    from src import vector_client as vc

    monkeypatch.setenv("RERANK_SEARCH", "false")
    monkeypatch.setattr(fastembed, "TextEmbedding", _EmbedStub)
    monkeypatch.setattr(fastembed, "SparseTextEmbedding", _EmbedStub)
    monkeypatch.setattr(_qc, "QdrantClient", _QdrantChet)

    c = vc.QdrantClientWrapper(mock=False)      # KHÔNG ném — app vẫn lên được
    assert c._kho_ok is False
    with _pytest.raises(ConnectionError) as loi:
        c.search("adsense")                     # dùng kho lúc chết → lỗi rõ nghĩa
    assert "Qdrant" in str(loi.value)

    c.client = _QdrantSong()                    # Qdrant sống dậy
    c._dam_bao_kho()                            # lượt dùng kế tiếp tự nối lại
    assert c._kho_ok is True


def test_doc_file_html_go_the_giu_chu_viet(tmp_path):
    """02/08/2026: 'file thường quy' của user là trang HTML — bản in PDF là ảnh
    (0 chữ, OCR local rụng dấu) nên nạp thẳng .html gốc: gỡ sạch script/style/thẻ,
    giữ nguyên chữ Việt đủ dấu."""
    from src.vector_client import _doc_file
    f = tmp_path / "trang.html"
    f.write_text("<html><head><style>p{color:red}</style>"
                 "<script>var bi_go = 1;</script></head>"
                 "<body><h1>Bảng lệnh tạo ổ chia sẻ</h1>"
                 "<p>Điền các ô bên dưới &amp; bấm Copy.</p></body></html>",
                 encoding="utf-8")
    chu = _doc_file(f)
    assert "Bảng lệnh tạo ổ chia sẻ" in chu and "Điền các ô bên dưới & bấm Copy." in chu
    assert "bi_go" not in chu and "color:red" not in chu    # script/style gỡ sạch
