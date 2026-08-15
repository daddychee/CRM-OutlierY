"""Test vòng hỏi–đáp 4 bước + factory trung lập nhà cung cấp (mock hết) — chạy: pytest"""

import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

import pytest

from src.llm.anthropic_provider import AnthropicProvider
from src.llm.base import LLMProvider
from src.llm.factory import get_critics, get_provider
from src.llm.openai_compatible import OpenAICompatibleProvider
from src.qa_pipeline import (KHONG_CO_TAI_LIEU, SYSTEM_CRITIC,
                             SYSTEM_VIET_LAI_CAU_HOI, SYSTEM_WRITER, QAPipeline)
from src.vector_client import QdrantClientWrapper


class DemProvider(LLMProvider):
    """Provider giả: trả lời cố định + đếm số lần được gọi."""

    def __init__(self, tra_loi="ĐẠT\nKhông thấy lỗi."):
        self.tra_loi = tra_loi
        self.so_lan_goi = 0

    def generate(self, system_prompt, user_prompt):
        self.so_lan_goi += 1
        return self.tra_loi


class GhiAmProvider(LLMProvider):
    """Provider giả: ghi lại (system, user) của từng lần gọi."""

    def __init__(self, tra_loi="ĐẠT\nKhông thấy lỗi."):
        self.tra_loi = tra_loi
        self.cac_lan_goi = []

    def generate(self, system_prompt, user_prompt):
        self.cac_lan_goi.append((system_prompt, user_prompt))
        return self.tra_loi


class RagDem(QdrantClientWrapper):
    """RAG giả: đếm số lần search — kiểm van 'lượt nào cũng tìm tài liệu thật'."""

    def __init__(self):
        super().__init__(mock=True)
        self.so_lan_tim = 0
        self.query_cuoi = None

    def search(self, query, filters=None, user=None):
        self.so_lan_tim += 1
        self.query_cuoi = query
        return super().search(query, filters, user=user)


def _pipeline(writer, critics):
    return QAPipeline(rag=QdrantClientWrapper(mock=True), writer=writer, critics=critics)


def test_co_tai_lieu_tra_loi_kem_nguon_va_goi_du_critics():
    writer = DemProvider("Đăng video khung 19h-21h [KD-2026-0042]")
    critics = [DemProvider(), DemProvider()]
    kq = _pipeline(writer, critics).hoi("quy trình đăng video")

    assert kq["answer"].startswith("Đăng video")
    assert kq["sources"] and all(s["doc_code"] for s in kq["sources"])
    assert kq["critic_count"] == 2 and len(kq["reviews"]) == 2
    assert all(c.so_lan_goi == 1 for c in critics)  # gọi ĐỦ các critic
    assert writer.so_lan_goi == 1 and kq["rewritten"] is False  # ĐẠT → không viết lại


def test_critic_bao_loi_thi_writer_viet_lai():
    writer = DemProvider("Trả lời lần đầu")
    critics = [DemProvider("LỖI\nLan man, đổ nguyên đoạn tài liệu thay vì trả lời.")]
    kq = _pipeline(writer, critics).hoi("đăng video")

    assert kq["rewritten"] is True
    assert writer.so_lan_goi == 2  # trả lời + viết lại cho cô đọng


def test_prompt_yeu_cau_day_du_nhung_giu_van_chong_bia():
    """Ghim yêu cầu A + sửa 07/08 (user chê 'trả lời ngắn quá, không thực sự giải đáp'):
    writer phải nhận chỉ dẫn ĐẦY ĐỦ/giải quyết trọn vẹn (không còn ép CÔ ĐỌNG thành cụt lủn)
    + van chống bịa; critic kiểm cả lan man LẪN thiếu ý."""
    writer, critic = GhiAmProvider("Khung 19h-21h [KD-2026-0042]"), GhiAmProvider()
    _pipeline(writer, [critic]).hoi("đăng video khung giờ nào?")

    system_writer = writer.cac_lan_goi[0][0]
    assert "ĐẦY ĐỦ" in system_writer and "TRỰC TIẾP" in system_writer
    assert "GIẢI QUYẾT TRỌN VẸN" in system_writer
    assert "CHỈ được dùng thông tin CÓ trong các đoạn tài liệu" in system_writer
    assert "Tài liệu chưa nêu cụ thể điều này" in system_writer  # không nêu → nói thẳng, không bịa

    system_critic = critic.cac_lan_goi[0][0]
    assert "TRỌNG TÂM" in system_critic       # tiêu chí cũ: lan man vẫn là LỖI
    assert "THỰC SỰ GIẢI QUYẾT" in system_critic  # tiêu chí mới: thiếu ý cũng là LỖI


def test_hoi_tiep_ngan_phu_thuoc_ngu_canh_goi_model_viet_lai():
    """05/08/2026 — sửa bug LẠC ĐỀ đo được thật: "Ngâm kênh là gì?" -> "Thường kéo dài bao
    lâu?" ghép chuỗi mù quáng bị chính cụm "kéo dài bao lâu" kéo sang tài liệu KHÁC hẳn chủ
    đề. Câu hỏi tiếp NGẮN + có dấu hiệu phụ thuộc ngữ cảnh ("thế còn...") giờ được VIẾT LẠI
    thành câu độc lập trước khi tìm (thêm 1 lần gọi model, rẻ) thay vì ghép chuỗi thô."""
    writer = GhiAmProvider("Trả lời theo ngữ cảnh [KD-2026-0042]")
    rag = RagDem()
    pipe = QAPipeline(rag=rag, writer=writer, critics=[GhiAmProvider()])

    lich_su = [{"hoi": "Quy trình đăng video thế nào?", "dap": "Gồm 3 bước... [KD-2026-0042]"}]
    kq = pipe.hoi("thế còn khung giờ?", lich_su=lich_su)

    # 2 lần gọi writer: 1 viết lại câu hỏi độc lập + 1 trả lời
    assert len(writer.cac_lan_goi) == 2
    he_thong_viet_lai, de_bai_viet_lai = writer.cac_lan_goi[0]
    assert he_thong_viet_lai == SYSTEM_VIET_LAI_CAU_HOI
    assert "Quy trình đăng video thế nào?" in de_bai_viet_lai  # thấy lịch sử để hiểu ngữ cảnh
    assert "thế còn khung giờ?" in de_bai_viet_lai              # thấy câu hỏi mới cần viết lại
    assert writer.cac_lan_goi[1][0] == SYSTEM_WRITER
    assert "Hội thoại trước đó" in writer.cac_lan_goi[1][1]     # ngữ cảnh vẫn vào đề bài trả lời
    assert "Các đoạn tài liệu" in writer.cac_lan_goi[1][1]      # vẫn kèm tài liệu thật

    # Truy vấn search = CÂU ĐÃ VIẾT LẠI (provider giả trả cố định) — không còn chuỗi ghép thô
    assert rag.query_cuoi == "Trả lời theo ngữ cảnh [KD-2026-0042]"
    assert rag.so_lan_tim == 1          # lượt này VẪN tìm tài liệu, không trả lời từ trí nhớ
    assert kq["sources"]                # vẫn có nguồn kiểm chứng


def test_hoi_tiep_tu_du_nghia_khong_can_viet_lai():
    """Câu hỏi tiếp DÀI/tự đủ nghĩa (không đại từ tham chiếu, không mở đầu hỏi cụt) vẫn đi
    đường ghép chuỗi cũ ~0s — không tốn thêm lời gọi model cho đa số câu hỏi bình thường."""
    writer = GhiAmProvider("Trả lời [KD-2026-0042]")
    rag = RagDem()
    pipe = QAPipeline(rag=rag, writer=writer, critics=[GhiAmProvider()])

    lich_su = [{"hoi": "Quy trình đăng video thế nào?", "dap": "Gồm 3 bước... [KD-2026-0042]"}]
    kq = pipe.hoi("Quy trình đăng video áp dụng cho kênh tiếng Anh có khác gì không?",
                  lich_su=lich_su)

    assert len(writer.cac_lan_goi) == 1               # KHÔNG viết lại — câu đã tự đủ nghĩa
    assert writer.cac_lan_goi[0][0] == SYSTEM_WRITER
    assert "kênh tiếng Anh" in rag.query_cuoi
    assert "Quy trình đăng video thế nào?" in rag.query_cuoi   # vẫn ghép câu cũ vào truy vấn
    assert rag.so_lan_tim == 1
    assert kq["sources"]


def test_hoi_khong_lich_su_tim_bang_dung_cau_hoi():
    writer = GhiAmProvider("Trả lời [KD-2026-0042]")
    rag = RagDem()
    QAPipeline(rag=rag, writer=writer, critics=[]).hoi("quy trình đăng video")
    assert len(writer.cac_lan_goi) == 1  # chỉ 1 lần: trả lời
    assert writer.cac_lan_goi[0][0] == SYSTEM_WRITER
    assert rag.query_cuoi == "quy trình đăng video"  # không ghép gì khi không có lịch sử


def test_search_rong_khong_bia():
    writer = DemProvider()
    kq = _pipeline(writer, [DemProvider()]).hoi("x", filters={"department": "IT"})

    assert kq["answer"] == KHONG_CO_TAI_LIEU
    assert kq["sources"] == []
    assert writer.so_lan_goi == 0  # không gọi model → không thể bịa
    assert kq["bi_chan_quyen"] is False  # kho thiếu thật (không có user → không thể bị chặn)


def test_hoi_co_ket_qua_van_ganh_co_bi_chan_khi_kho_co_tai_lieu_bi_loc():
    """CA BUG CŨ ở mức pipeline: câu trả lời bình thường (không rỗng) nhưng kho có
    tài liệu bị chặn cùng khớp → bi_chan_quyen = True để feedback không loạn."""
    nv2 = {"ten": "nv", "bo_phan": "Kinh doanh", "level": 2}
    kq = _pipeline(DemProvider("Trả lời từ MMO [KD-2026-0042]"), []).hoi(
        "cách tạo google adsense", user=nv2)

    assert kq["answer"] != KHONG_CO_TAI_LIEU  # tìm thấy tài liệu được phép, trả lời thật
    assert kq["sources"]
    assert kq["bi_chan_quyen"] is True        # nhưng vẫn ghi ngầm: có tài liệu bị chặn


def test_hoi_kho_rong_do_quyen_tra_co_bi_chan():
    """RULE 2: rỗng DO LỌC QUYỀN → answer vẫn 'chưa có' (không lộ) nhưng cờ ngầm = True."""
    user_thap = {"ten": "vh1", "bo_phan": "Vận hành - Sản xuất", "level": 1}
    kq = _pipeline(DemProvider(), []).hoi(
        "xuất video", filters={"department": "Vận hành - Sản xuất"}, user=user_thap)
    # VH-2026-0007 (min 2, Giới hạn) bị chặn với level 1 → rỗng
    assert kq["answer"] == KHONG_CO_TAI_LIEU  # text hiển thị KHÔNG đổi
    assert kq["bi_chan_quyen"] is True        # metadata ngầm cho feedback/log


def test_mac_dinh_chi_tra_tai_lieu_con_hieu_luc():
    kq = _pipeline(DemProvider("ok"), []).hoi("đăng video")  # không truyền filters
    assert all(s["effective_status"] == "Còn hiệu lực" for s in kq["sources"])


def test_factory_doi_provider_qua_env(monkeypatch):
    monkeypatch.setenv("WRITER_PROVIDER", "openai_compatible")
    monkeypatch.setenv("WRITER_MODEL", "glm-4-plus")
    monkeypatch.setenv("WRITER_MOCK_MODE", "true")
    p = get_provider("writer")
    assert isinstance(p, OpenAICompatibleProvider) and p.model == "glm-4-plus"

    monkeypatch.setenv("WRITER_PROVIDER", "anthropic")
    p2 = get_provider("writer")
    assert isinstance(p2, AnthropicProvider)  # đổi .env → đổi nhà, không sửa code

    monkeypatch.setenv("WRITER_PROVIDER", "nha-la")
    with pytest.raises(ValueError):
        get_provider("writer")


def test_danh_sach_critics_tu_env(monkeypatch):
    monkeypatch.setenv("CRITICS", "critic,critic2")
    monkeypatch.setenv("CRITIC_PROVIDER", "openai_compatible")
    monkeypatch.setenv("CRITIC_MOCK_MODE", "true")
    monkeypatch.setenv("CRITIC2_PROVIDER", "anthropic")
    monkeypatch.setenv("CRITIC2_MOCK_MODE", "true")

    cs = get_critics()
    assert len(cs) == 2
    assert isinstance(cs[0], OpenAICompatibleProvider)
    assert isinstance(cs[1], AnthropicProvider)  # "hội đồng" trộn nhiều nhà được


def test_route_hoi_dap_va_hoi():
    from src.main import app
    from claims_v2 import client_khach

    tc = client_khach(app)  # V2: claims thiếu bộ phận ≈ chế độ mở hệ cũ
    assert tc.get("/hoi-dap").status_code == 200

    r = tc.post("/hoi", data={"question": "quy trình đăng video"})
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body and "sources" in body and "critic_count" in body

    # Gửi kèm lịch sử hội thoại → vẫn 200; lịch sử hỏng → coi như hội thoại mới, không sập
    import json as json_mod
    lich_su = json_mod.dumps([{"hoi": "Quy trình đăng video?", "dap": "3 bước..."}])
    assert tc.post("/hoi", data={"question": "thế còn khung giờ?",
                                 "history": lich_su}).status_code == 200
    assert tc.post("/hoi", data={"question": "x", "history": "hong-json"}).status_code == 200


# ─────────── 08/08 (analytic_methodology.md §12.1): dien_giai_chan_doan khai rõ nguồn baseline ───────────

def _ket_qua_chan_doan(nguon_baseline=None):
    matched = [{"ma_luat": "YT-02", "tang_pheu": "retention", "nguyen_nhan": "giật tít",
               "cach_sua": "sửa hook", "do_tin_cay": "cao"}]
    kq = {"matched": matched, "tang_vo": "retention", "metrics": {"retention": 0.13}}
    if nguon_baseline is not None:
        kq["nguon_baseline"] = nguon_baseline
    return kq


def test_dien_giai_chan_doan_video_khai_ro_nguon_baseline():
    """chan_doan_video() giờ có thể so theo nhóm độ dài — đề bài phải nói rõ baseline nào,
    không mập mờ 'so với kênh' khi thực ra đang so nhóm."""
    writer = GhiAmProvider("Diễn giải mẫu.")
    pipe = _pipeline(writer, [])
    pipe.dien_giai_chan_doan(_ket_qua_chan_doan(
        nguon_baseline={"retention": "nhóm độ dài 'ngắn'", "ctr": "toàn kênh"}))
    _, de_bai = writer.cac_lan_goi[0]
    assert "Baseline đang so cho mỗi chỉ số" in de_bai
    assert "nhóm độ dài 'ngắn'" in de_bai


def test_dien_giai_chan_doan_kenh_khong_co_dong_nguon_baseline():
    """chan_doan_kenh() không có nguon_baseline (luôn so toàn kênh) → KHÔNG thêm dòng thừa."""
    writer = GhiAmProvider("Diễn giải mẫu.")
    pipe = _pipeline(writer, [])
    pipe.dien_giai_chan_doan(_ket_qua_chan_doan(nguon_baseline=None))
    _, de_bai = writer.cac_lan_goi[0]
    assert "Baseline đang so cho mỗi chỉ số" not in de_bai
