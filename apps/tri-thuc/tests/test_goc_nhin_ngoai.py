"""Test box gợi ý "🧭 góc nhìn khác" (08/08) — bấm SAU khi đã có câu trả lời công ty, KHÔNG
pin ở ô nhập. Khác hoi_stream_da_chieu: CHỈ tìm/viết tầng "ngoài", câu trả lời công ty được
đưa vào đề bài làm ngữ cảnh đối chiếu (nguyên văn) nhưng prompt cấm lặp lại nó. FakeRag tiêm
chunk theo tang_nguon để test tất định — KHÔNG gọi Qdrant/LLM thật."""

import os

os.environ["MOCK_MODE"] = "true"

from src.llm.base import LLMProvider
from src.qa_pipeline import SYSTEM_CRITIC_GOC_NHIN_NGOAI, SYSTEM_GOC_NHIN_NGOAI, QAPipeline


class DemProvider(LLMProvider):
    def __init__(self, tra_loi="Góc nhìn khác."):
        self.tra_loi = tra_loi
        self.so_lan_goi = 0
        self.cac_lan_goi = []

    def generate(self, system_prompt, user_prompt):
        self.so_lan_goi += 1
        self.cac_lan_goi.append((system_prompt, user_prompt))
        return self.tra_loi


def _chunk(ma, tang, sim=0.9, nguon_ten=""):
    return {"content": f"Nội dung {ma}", "document_id": ma,
            "document_keyword": f"{ma}_x.md", "similarity": sim,
            "document_metadata": {"doc_code": ma, "department": "Kinh doanh",
                                  "effective_status": "Còn hiệu lực",
                                  "access_level": "Công khai nội bộ", "min_level": 1,
                                  "title": ma, "tang_nguon": tang, "nguon_ten": nguon_ten}}


class FakeRag:
    """Trả chunk theo filters['tang_nguon'] — mô phỏng 'tìm tách theo tầng'."""
    def __init__(self, theo_tang):
        self.theo_tang = theo_tang
        self.tang_da_tim = []

    def search(self, query, filters=None, user=None):
        tang = (filters or {}).get("tang_nguon")
        self.tang_da_tim.append(tang)
        return list(self.theo_tang.get(tang, []))

    def search_co_bi_chan(self, query, filters=None, user=None):
        return False


def _gop(su_kien, loai):
    return [s["data"] for s in su_kien if s["type"] == loai]


# ─────────────── goi_y_goc_nhin_khac — kiểm RẺ, không gọi model ───────────────

def test_khong_co_ngoai_tra_ve_rong():
    pipe = QAPipeline(rag=FakeRag({}), writer=DemProvider(), critics=[])
    assert pipe.goi_y_goc_nhin_khac("câu hỏi") == []
    assert pipe.writer.so_lan_goi == 0   # chỉ tìm, không gọi model


def test_duoi_nguong_khong_goi_y():
    pipe = QAPipeline(rag=FakeRag({"ngoai": [_chunk("YT-1", "ngoai", sim=0.1, nguon_ten="Andrew X")]}),
                      writer=DemProvider(), critics=[])
    assert pipe.goi_y_goc_nhin_khac("câu hỏi") == []


def test_vuot_nguong_tra_ten_theo_diem_giam_dan():
    pipe = QAPipeline(rag=FakeRag({"ngoai": [
        _chunk("YT-1", "ngoai", sim=0.5, nguon_ten="Andrew X"),
        _chunk("YT-2", "ngoai", sim=0.9, nguon_ten="Youtube Official"),
    ]}), writer=DemProvider(), critics=[])
    assert pipe.goi_y_goc_nhin_khac("câu hỏi") == ["Youtube Official", "Andrew X"]


# ─────────────── hoi_stream (đường mặc định) — box gợi ý xuất hiện ĐÚNG lúc ───────────────

def test_hoi_stream_khong_co_ngoai_khong_yield_nguon_khac():
    pipe = QAPipeline(rag=FakeRag({"noi_bo": [_chunk("KD-1", "noi_bo")]}),
                      writer=DemProvider("Trả lời công ty."), critics=[])
    su_kien = list(pipe.hoi_stream("câu hỏi"))
    assert _gop(su_kien, "nguon_khac") == []


def test_hoi_stream_co_ngoai_vuot_nguong_yield_nguon_khac():
    pipe = QAPipeline(rag=FakeRag({
        "noi_bo": [_chunk("KD-1", "noi_bo")],
        "ngoai": [_chunk("YT-1", "ngoai", sim=0.8, nguon_ten="Andrew X")],
    }), writer=DemProvider("Trả lời công ty."), critics=[])
    su_kien = list(pipe.hoi_stream("câu hỏi"))
    nguon_khac = _gop(su_kien, "nguon_khac")
    assert nguon_khac == [["Andrew X"]]
    # box gợi ý là kiểm RẺ — KHÔNG tốn thêm lượt gọi model (writer chỉ gọi 1 lần cho câu trả lời)
    assert pipe.writer.so_lan_goi == 1


# ─────────────── hoi_stream_goc_nhin_ngoai — chỉ tầng ngoài, cấm lặp công ty ───────────────

def test_khong_co_ngoai_tra_thong_bao_khong_goi_model():
    pipe = QAPipeline(rag=FakeRag({}), writer=DemProvider(), critics=[])
    su_kien = list(pipe.hoi_stream_goc_nhin_ngoai("câu hỏi", "Trả lời công ty đã có."))
    assert "Không tìm thấy góc nhìn khác" in _gop(su_kien, "token")[0]
    assert pipe.writer.so_lan_goi == 0        # van chống bịa lớp 1: không có gì thì không bịa
    assert not _gop(su_kien, "sources")


def test_de_bai_khong_chua_khoi_cong_ty_nhung_co_cau_tra_loi_de_doi_chieu():
    writer = DemProvider()
    pipe = QAPipeline(rag=FakeRag({"ngoai": [
        _chunk("YT-1", "ngoai", nguon_ten="Andrew X"),
        _chunk("YT-2", "ngoai", nguon_ten="Youtube Official"),
    ]}), writer=writer, critics=[])
    list(pipe.hoi_stream_goc_nhin_ngoai("câu hỏi", "Công ty nói: làm X trước Y sau."))
    sys, de_bai = writer.cac_lan_goi[0]
    assert sys == SYSTEM_GOC_NHIN_NGOAI
    assert "Công ty nói: làm X trước Y sau." in de_bai      # đưa vào làm ngữ cảnh
    assert "KHÔNG lặp lại" in de_bai                         # cấm lặp ngay trong đề bài
    assert "=== TẦNG: 🌐 Andrew X ===" in de_bai
    assert "=== TẦNG: 🌐 Youtube Official ===" in de_bai
    assert "📌 Theo tài liệu công ty" not in de_bai           # KHÔNG có khối công ty


def test_khong_tim_lai_tang_cong_ty():
    """Đường này KHÔNG được đụng tầng công ty — đã trả lời + đã ghi kho-thiếu ở lượt trước."""
    pipe = QAPipeline(rag=FakeRag({"ngoai": [_chunk("YT-1", "ngoai", nguon_ten="Andrew X")]}),
                      writer=DemProvider(), critics=[])
    list(pipe.hoi_stream_goc_nhin_ngoai("câu hỏi", "Công ty nói X."))
    assert pipe.rag.tang_da_tim == ["ngoai"]


def test_critic_dung_prompt_goc_nhin_ngoai():
    critic = DemProvider("LỖI\nLặp lại nguyên câu trả lời công ty.")
    pipe = QAPipeline(rag=FakeRag({"ngoai": [_chunk("YT-1", "ngoai", nguon_ten="Andrew X")]}),
                      writer=DemProvider(), critics=[critic])
    su_kien = list(pipe.hoi_stream_goc_nhin_ngoai("câu hỏi", "Công ty nói X."))
    assert critic.cac_lan_goi[0][0] == SYSTEM_CRITIC_GOC_NHIN_NGOAI
    assert _gop(su_kien, "review")


# ─────────────── ROUTE — wiring + RBAC ───────────────

def test_route_goc_nhin_ngoai_dang_nhap_tra_sse(tmp_path, monkeypatch):
    from src.main import app
    from claims_v2 import client_claims  # V2: claims thay users.txt + đăng nhập

    c = client_claims(app, "nv", "Kinh doanh", 2)
    r = c.post("/hoi-dap/stream-goc-nhin-ngoai",
              data={"question": "quy trình đăng video", "cau_tra_loi_cong_ty": "Công ty đã nói X."})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    # _MOCK_CHUNKS toàn tang_nguon="noi_bo" → tầng "ngoài" luôn rỗng trong mock → fallback đúng
    assert "Không tìm thấy góc nhìn khác" in r.text


def test_route_chua_dang_nhap_bi_chan(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app

    c = TestClient(app)  # V2: KHÔNG claims → 401 (gateway chưa tiêm danh tính)
    r = c.post("/hoi-dap/stream-goc-nhin-ngoai",
              data={"question": "x", "cau_tra_loi_cong_ty": "y"})
    assert r.status_code == 401
