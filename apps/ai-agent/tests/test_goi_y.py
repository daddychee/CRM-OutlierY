"""Test gợi ý câu hỏi tiếp theo (Ý 3 Đợt 3) — parse, công tắc, thứ tự sự kiện stream.
Toàn bộ dùng writer GIẢ — không gọi API thật (bài học: test âm thầm gọi GLM trả tiền)."""

import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import — rag không cần Qdrant thật

import pytest

from src.qa_pipeline import QAPipeline


@pytest.fixture(autouse=True)
def bat_goi_y(monkeypatch):
    """conftest tắt GOI_Y_CAU_HOI cho test cũ (đếm lời gọi model) — file này bật lại."""
    monkeypatch.setenv("GOI_Y_CAU_HOI", "true")


class WriterGia:
    """Writer giả đếm số lần gọi — generate() cho gợi ý, generate_stream() cho trả lời."""

    def __init__(self, tra="Câu A?\nCâu B?\nCâu C?"):
        self.tra = tra
        self.so_lan_generate = 0

    def generate(self, system, de_bai):
        self.so_lan_generate += 1
        return self.tra

    def generate_stream(self, system, de_bai):
        yield "câu trả lời "
        yield "mock"


def _qa(writer):
    return QAPipeline(writer=writer, critics=[])  # rag mặc định = mock wrapper


def _chunks(qa):
    return qa.rag.search("video", user=None)  # chunks mẫu từ kho mock


def test_parse_bo_so_thu_tu_va_dong_rong():
    w = WriterGia("1. Câu A?\n\n- Câu B?\n• Câu C?\n4) Câu D thừa?")
    qa = _qa(w)
    assert qa.goi_y_cau_hoi("hỏi gì tiếp?", _chunks(qa)) == ["Câu A?", "Câu B?", "Câu C?"]
    assert w.so_lan_generate == 1


def test_chunks_rong_khong_goi_model():
    w = WriterGia()
    assert _qa(w).goi_y_cau_hoi("câu hỏi", []) == []
    assert w.so_lan_generate == 0


def test_cong_tac_tat_khong_goi_model(monkeypatch):
    monkeypatch.setenv("GOI_Y_CAU_HOI", "false")
    w = WriterGia()
    qa = _qa(w)
    assert qa.goi_y_cau_hoi("câu hỏi", _chunks(qa)) == []
    assert w.so_lan_generate == 0


def test_writer_loi_thi_im_lang():
    class WriterHong(WriterGia):
        def generate(self, system, de_bai):
            raise RuntimeError("model sập")

    qa = _qa(WriterHong())
    assert qa.goi_y_cau_hoi("câu hỏi", _chunks(qa)) == []  # tính năng phụ — không ném lỗi


def test_stream_goi_y_sau_token_truoc_done():
    su_kien = list(_qa(WriterGia()).hoi_stream("quy trình đăng video?"))
    loai = [s["type"] for s in su_kien]
    assert loai == ["sources", "token", "token", "goi_y", "done"]  # gợi ý SAU token, TRƯỚC done
    assert su_kien[-2]["data"] == ["Câu A?", "Câu B?", "Câu C?"]
    assert "bi_chan_quyen" in su_kien[-1]["data"]  # done giữ nguyên cờ Rule 2 — luồng không hỏng


def test_stream_kho_rong_khong_co_goi_y():
    qa = _qa(WriterGia())
    su_kien = list(qa.hoi_stream("x", filters={"department": "IT"}))  # mock lọc → rỗng
    assert [s["type"] for s in su_kien] == ["token", "done"]  # van chống bịa giữ, không goi_y


def test_hoi_khong_stream_co_khoa_goi_y():
    kq = _qa(WriterGia()).hoi("quy trình đăng video?")
    assert kq["goi_y"] == ["Câu A?", "Câu B?", "Câu C?"]
