"""Test đường STREAMING (mock hết): generate_stream + hoi_stream + route SSE — chạy: pytest"""

import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from src.llm.anthropic_provider import AnthropicProvider
from src.llm.base import LLMProvider
from src.llm.openai_compatible import OpenAICompatibleProvider
from src.qa_pipeline import KHONG_CO_TAI_LIEU, QAPipeline
from src.vector_client import QdrantClientWrapper


class StubWriter(LLMProvider):
    """Không override generate_stream → dùng bản fallback mặc định của LLMProvider."""

    def __init__(self, tra_loi="Đăng video khung 19h-21h [KD-2026-0042]"):
        self.tra_loi = tra_loi
        self.so_lan_goi = 0

    def generate(self, system_prompt, user_prompt):
        self.so_lan_goi += 1
        return self.tra_loi


def _pipe(writer, critics):
    return QAPipeline(rag=QdrantClientWrapper(mock=True), writer=writer, critics=critics)


def test_generate_stream_mock_chay_thanh_nhieu_mau():
    for provider in (OpenAICompatibleProvider(mock=True, model="model-test"),
                     AnthropicProvider(mock=True)):
        cac_mau = list(provider.generate_stream("sys", "user"))
        assert len(cac_mau) > 1                     # chia nhỏ thật sự, không trả 1 cục
        assert "[MOCK" in "".join(cac_mau)          # ghép lại vẫn thành câu đầy đủ


def test_generate_stream_fallback_mac_dinh_mot_mau():
    w = StubWriter()
    assert list(w.generate_stream("s", "u")) == [w.tra_loi]  # provider không stream vẫn chạy


def test_hoi_stream_du_su_kien_dung_thu_tu():
    kq = list(_pipe(StubWriter(), []).hoi_stream("quy trình đăng video"))
    loai = [e["type"] for e in kq]

    assert loai[0] == "sources"                     # nguồn đẩy TRƯỚC chữ
    assert "token" in loai and loai[-1] == "done"
    nguon = kq[0]["data"]
    assert nguon and all(s["doc_code"] for s in nguon)  # đủ dữ liệu trích nguồn


def test_hoi_stream_kho_rong_khong_goi_model():
    """Van chống bịa lớp 1 giữ nguyên trên đường stream."""
    w = StubWriter()
    kq = list(_pipe(w, []).hoi_stream("x", filters={"department": "IT"}))

    assert [e["type"] for e in kq] == ["token", "done"]
    assert kq[0]["data"] == KHONG_CO_TAI_LIEU
    assert w.so_lan_goi == 0  # không gọi model → không thể bịa


def test_hoi_stream_co_lich_su_cau_ngan_goi_model_viet_lai():
    """05/08/2026 — câu hỏi tiếp NGẮN + phụ thuộc ngữ cảnh ("thế còn...") giờ được viết lại
    thành câu độc lập trước khi tìm (sửa bug lạc đề đo được thật ở đường /hoi-dap/stream).
    StubWriter không override generate_stream → fallback mặc định gọi qua generate() nên
    CẢ hai bước (viết lại + trả lời) đều tính vào so_lan_goi: 2 lần."""
    w = StubWriter()
    lich_su = [{"hoi": "Quy trình đăng video?", "dap": "3 bước [KD-2026-0042]"}]
    kq = list(_pipe(w, []).hoi_stream("thế còn khung giờ?", lich_su=lich_su))
    assert w.so_lan_goi == 2                          # viết lại + trả lời
    assert kq[0]["type"] == "sources" and kq[0]["data"]  # trí nhớ + tìm tài liệu vẫn chạy


def test_hoi_stream_co_lich_su_cau_du_nghia_khong_viet_lai():
    """Câu hỏi tiếp DÀI/tự đủ nghĩa vẫn đi đường ghép chuỗi cũ ~0s — writer KHÔNG bị gọi
    thêm lần viết lại nào, chỉ đúng 1 lần cho phần trả lời."""
    w = StubWriter()
    lich_su = [{"hoi": "Quy trình đăng video?", "dap": "3 bước [KD-2026-0042]"}]
    kq = list(_pipe(w, []).hoi_stream(
        "Quy trình đăng video áp dụng cho kênh tiếng Anh có khác gì không?", lich_su=lich_su))
    assert w.so_lan_goi == 1                          # chỉ trả lời — câu đã tự đủ nghĩa
    assert kq[0]["type"] == "sources" and kq[0]["data"]


def test_hoi_stream_critic_bao_loi_chi_canh_bao_cuoi_khong_viet_lai():
    w = StubWriter()
    critic = StubWriter("LỖI\nGán sai nguồn tài liệu.")
    kq = list(_pipe(w, [critic]).hoi_stream("đăng video"))
    loai = [e["type"] for e in kq]

    assert "review" in loai
    assert loai.index("review") > loai.index("token")  # cảnh báo nằm SAU chữ, ở cuối
    assert loai[-1] == "done"
    assert w.so_lan_goi == 1  # KHÔNG viết lại giữa chừng stream
    assert critic.so_lan_goi == 1


def test_hoi_stream_critics_rong_bo_qua_phan_bien():
    kq = list(_pipe(StubWriter(), []).hoi_stream("đăng video"))
    assert "review" not in [e["type"] for e in kq]
    assert kq[-1]["data"]["critic_count"] == 0


def test_route_stream_sse():
    from src.main import app
    from claims_v2 import client_khach

    tc = client_khach(app)  # V2: claims thiếu bộ phận ≈ chế độ mở hệ cũ
    r = tc.post("/hoi-dap/stream",
                data={"question": "quy trình đăng video", "history": "[]"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: sources" in r.text
    assert "event: token" in r.text
    assert "event: done" in r.text

    # Endpoint cũ /hoi vẫn nguyên vẹn (đường song song, không thay thế)
    r2 = tc.post("/hoi", data={"question": "quy trình đăng video"})
    assert r2.status_code == 200 and "answer" in r2.json()


def test_trang_kiem_stream_va_data():
    """Công cụ tự chẩn đoán streaming (điều tra 20/07) — trang mở được, data phát đủ 5 số."""
    from src.main import app
    from claims_v2 import client_khach

    c = client_khach(app)  # V2: claims thiếu bộ phận ≈ khách hệ cũ
    assert c.get("/kiem-stream").status_code == 200
    r = c.get("/kiem-stream/data")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    for so in range(1, 6):
        assert f"data: {so}" in r.text
