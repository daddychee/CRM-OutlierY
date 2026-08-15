"""Test Bước 3 Supervisor — TRẢ LỜI ĐA CHIỀU (hoi_stream_da_chieu).

Van chống bịa theo KHỐI: công ty luôn trước; phần "ngoài" chỉ khi vượt ngưỡng, rồi tách MỘT
KHỐI RIÊNG cho MỖI TÊN NGUỒN thật (07/08 user chốt: không phân biệt chuyên gia/ngoài — coi là
MỘT, chỉ cần đưa đúng tên); khối rỗng → bỏ; công ty trống mà nguồn khác có → vẫn trả lời + cảnh
báo (tín hiệu kho-thiếu). FakeRag tiêm chunk theo tang_nguon để test tất định — KHÔNG gọi
Qdrant/LLM thật."""

import os

os.environ["MOCK_MODE"] = "true"

from src.llm.base import LLMProvider
from src.qa_pipeline import (KHONG_CO_TAI_LIEU, SYSTEM_CRITIC_DA_CHIEU,
                             SYSTEM_DA_CHIEU, QAPipeline)


class DemProvider(LLMProvider):
    def __init__(self, tra_loi="Bản tư vấn."):
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
    def __init__(self, theo_tang, bi_chan=False):
        self.theo_tang = theo_tang           # {tang: [chunk]}
        self.bi_chan = bi_chan               # noi_bo trống là vì bị chặn quyền?
        self.tang_da_tim = []

    def search(self, query, filters=None, user=None):
        tang = (filters or {}).get("tang_nguon")
        self.tang_da_tim.append(tang)
        return list(self.theo_tang.get(tang, []))

    def search_co_bi_chan(self, query, filters=None, user=None):
        return self.bi_chan


def _chay(theo_tang, writer=None, critics=None, cau_hoi="nên làm gì", bi_chan=False):
    pipe = QAPipeline(rag=FakeRag(theo_tang, bi_chan=bi_chan), writer=writer or DemProvider(),
                      critics=critics if critics is not None else [])
    su_kien = list(pipe.hoi_stream_da_chieu(cau_hoi))
    return pipe, su_kien


def _gop(su_kien, loai):
    return [s["data"] for s in su_kien if s["type"] == loai]


def test_tim_tach_dung_hai_suat():
    """Công ty vs phần còn lại được TÌM RIÊNG (2 lượt search, không gộp) — nguồn khác không
    đè công ty."""
    pipe, _ = _chay({"noi_bo": [_chunk("KD-1", "noi_bo")]})
    assert pipe.rag.tang_da_tim == ["noi_bo", "ngoai"]


def test_nhieu_nguon_tach_theo_dung_ten_khong_theo_loai():
    """Hai nguồn khác nhau trong CÙNG tầng 'ngoai' (một người, một kênh) → 2 khối RIÊNG mở
    đầu bằng ĐÚNG TÊN — không còn nhãn chung 'chuyên gia'/'nguồn ngoài' (07/08 user chốt)."""
    writer = DemProvider()
    _chay({
        "noi_bo": [_chunk("KD-1", "noi_bo")],
        "ngoai": [_chunk("CG-1", "ngoai", nguon_ten="Andrew X"),
                  _chunk("NG-1", "ngoai", nguon_ten="Youtube Official")],
    }, writer=writer)
    # đề bài writer nhận phải chứa header công ty + ĐÚNG TÊN từng nguồn (writer tự tách khối)
    _, de = writer.cac_lan_goi[0]
    assert "📌 Theo tài liệu công ty" in de
    assert "🌐 Andrew X" in de and "🌐 Youtube Official" in de
    assert "👤 Góc nhìn chuyên gia" not in de and "🌐 Nguồn ngoài\n" not in de  # không nhãn chung
    assert "[KD-1]" in de and "[CG-1]" in de and "[NG-1]" in de


def test_hai_khoi_su_kien_va_khong_canh_bao():
    _, su_kien = _chay({
        "noi_bo": [_chunk("KD-1", "noi_bo")],
        "ngoai": [_chunk("CG-1", "ngoai", nguon_ten="Andrew X"),
                  _chunk("NG-1", "ngoai", nguon_ten="Youtube Official")],
    })
    nguon = _gop(su_kien, "sources")[0]
    assert {s["doc_code"] for s in nguon} == {"KD-1", "CG-1", "NG-1"}
    assert su_kien[-1]["type"] == "done" and su_kien[-1]["data"]["cong_ty_trong"] is False
    assert not any("Công ty chưa có tài liệu" in t for t in _gop(su_kien, "token"))


def test_nguon_khac_duoi_nguong_bi_loai():
    """Công ty giữ luôn; nguồn khác điểm 0.2 < 0.3 → BỎ hẳn khối (chống nhiễu)."""
    writer = DemProvider()
    _chay({
        "noi_bo": [_chunk("KD-1", "noi_bo", sim=0.9)],
        "ngoai": [_chunk("CG-1", "ngoai", sim=0.2, nguon_ten="Andrew X")],
    }, writer=writer)
    _, de = writer.cac_lan_goi[0]
    assert "[KD-1]" in de and "[CG-1]" not in de       # dưới ngưỡng không vào đề bài


def test_cong_ty_giu_ca_khi_diem_thap():
    """PREFER: công ty KHÔNG bị ngưỡng loại — có chunk nào là hiện."""
    writer = DemProvider()
    _chay({"noi_bo": [_chunk("KD-1", "noi_bo", sim=0.05)]}, writer=writer)
    _, de = writer.cac_lan_goi[0]
    assert "[KD-1]" in de


def test_cong_ty_trong_van_tra_loi_kem_canh_bao():
    _, su_kien = _chay({
        "ngoai": [_chunk("CG-1", "ngoai", nguon_ten="Andrew X")],
    })
    tokens = _gop(su_kien, "token")
    assert any("Công ty chưa có tài liệu" in t for t in tokens)   # cảnh báo hiện TRƯỚC
    assert su_kien[-1]["data"]["cong_ty_trong"] is True
    assert {s["doc_code"] for s in _gop(su_kien, "sources")[0]} == {"CG-1"}


def test_cong_ty_trong_do_bi_chan_quyen_khong_bao_kho_thieu():
    """Rule 2 / bug A: công ty trống vì BỊ CHẶN QUYỀN → done.bi_chan_quyen=True để route
    KHÔNG ghi nhầm sổ kho-thiếu (tài liệu đã có, chỉ ngoài quyền user)."""
    _, su_kien = _chay({"ngoai": [_chunk("CG-1", "ngoai")]}, bi_chan=True)
    assert su_kien[-1]["data"]["cong_ty_trong"] is True
    assert su_kien[-1]["data"]["bi_chan_quyen"] is True


def test_cong_ty_co_tai_lieu_khong_kiem_bi_chan():
    """Công ty CÓ chunk → cong_ty_trong False → không tốn truy vấn search_co_bi_chan."""
    _, su_kien = _chay({"noi_bo": [_chunk("KD-1", "noi_bo")]})
    assert su_kien[-1]["data"]["bi_chan_quyen"] is False


def test_khong_tang_nao_co_bao_kho_rong_khong_goi_model():
    writer = DemProvider()
    _, su_kien = _chay({}, writer=writer)
    assert _gop(su_kien, "token") == [KHONG_CO_TAI_LIEU]
    assert su_kien[-1]["data"]["cong_ty_trong"] is True
    assert writer.so_lan_goi == 0                        # van chống bịa: không tài liệu → không bịa
    assert not _gop(su_kien, "sources")


def test_writer_dung_prompt_da_chieu():
    writer = DemProvider()
    _chay({"noi_bo": [_chunk("KD-1", "noi_bo")]}, writer=writer)
    sys, _ = writer.cac_lan_goi[0]
    assert sys == SYSTEM_DA_CHIEU
    assert "KHÔNG viết cho khối nào KHÔNG được cung cấp" in sys   # cấm bịa quan điểm khối rỗng


def test_critic_dung_prompt_sai_khoi_va_phat_review():
    critic = DemProvider("LỖI\nGán ý nguồn ngoài vào khối công ty.")
    _, su_kien = _chay({"noi_bo": [_chunk("KD-1", "noi_bo")]},
                       writer=DemProvider(), critics=[critic])
    assert critic.cac_lan_goi[0][0] == SYSTEM_CRITIC_DA_CHIEU
    assert any("sai" in sys.lower() and "khối" in sys.lower() for sys, _ in critic.cac_lan_goi)
    assert _gop(su_kien, "review")                        # critic báo LỖI → có sự kiện review


# ─────────────── ROUTE — wiring + RBAC + mặc định an toàn ───────────────

def test_route_da_chieu_dang_nhap_tra_sse(tmp_path, monkeypatch):
    from src.main import app
    from claims_v2 import client_claims  # V2: claims thay users.txt + đăng nhập

    c = client_claims(app, "nv", "Kinh doanh", 2)
    r = c.post("/hoi-dap/stream-da-chieu", data={"question": "quy trình đăng video"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    # _MOCK_CHUNKS có tang_nguon="noi_bo" (khớp thật, vá 07/08) → khối công ty CÓ tài liệu
    # công khai của Kinh doanh; "ngoài" vẫn rỗng vì mock không có mục nào tầng đó
    assert "KD-2026-0042" in r.text
