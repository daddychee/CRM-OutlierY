# -*- coding: utf-8 -*-
"""Diễn giải LLM cho chẩn đoán số liệu — TRÍCH từ qa_pipeline hệ cũ (2 hàm
dien_giai_chan_doan / dien_giai_muc_kenh + vòng _sinh_va_phan_bien + 3 prompt),
để app data-analytics TỰ ĐỦ không vác cả pipeline RAG 51KB (Luật 4: không import
chéo app).

KHÁC hệ cũ đúng MỘT điểm: dien_giai_chan_doan không còn tra kho playbook
(rag.search thuộc app ai-agent).
ponytail: phần "playbook liên quan trong kho" tạm là "(không có)" — trần: diễn
giải thiếu bối cảnh playbook công ty; nâng cấp: gọi API search của app ai-agent
qua gateway (mạch cầu nối P6/B3), KHÔNG import chéo.

Cấu hình LLM: nạp từ KÉT qua gateway loopback lúc khởi động (nap_cau_hinh_llm) →
đổ vào env đúng khuôn {VAI}_* mà llm/factory hệ cũ đã đọc — factory + provider
GIỮ NGUYÊN KHÔNG SỬA. Gateway chết/chưa khai vai → env giữ nguyên (mock mặc định).
"""
from __future__ import annotations

import logging
import os

import httpx

from src.llm.factory import get_critics, get_provider

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000")

SYSTEM_CRITIC = (
    "Bạn là người phản biện khó tính. So câu trả lời với dữ kiện gốc được cung cấp, kiểm: "
    "(1) có bịa thông tin ngoài dữ kiện không? (2) có gán sai nguồn không? "
    "(3) có nhảy cóc kết luận không? (4) có ĐÚNG TRỌNG TÂM câu hỏi không — "
    "hay lan man, kể lể, đổ nguyên đoạn tài liệu dài thay vì trả lời? "
    "(5) có ĐẦY ĐỦ để người hỏi THỰC SỰ GIẢI QUYẾT được vấn đề không — hay cắt ngắn tới mức "
    "thiếu bước/thiếu điều kiện quan trọng MÀ TÀI LIỆU ĐÃ CÓ? Lan man LẪN thiếu ý đều tính "
    "là LỖI. DÒNG ĐẦU TIÊN chỉ ghi đúng một từ: 'ĐẠT' hoặc 'LỖI'. Từ dòng sau liệt kê từng vấn đề."
)
SYSTEM_DIEN_GIAI = (
    "Bạn diễn giải kết quả chẩn đoán số liệu cho người không chuyên kỹ thuật. "
    "CHỈ được dựa trên danh sách LUẬT ĐÃ KHỚP và đoạn tài liệu/playbook được cung cấp — "
    "tuyệt đối KHÔNG tự suy diễn nguyên nhân mới ngoài các luật đã khớp. "
    "Với mỗi luật: giải thích ngắn vì sao số liệu khớp luật đó và việc cần làm, theo thứ tự ưu tiên."
)
SYSTEM_DIEN_GIAI_MUC = (
    "Bạn là NHÀ PHÂN TÍCH YouTube. Nhiệm vụ: diễn giải Ý NGHĨA của các con số ĐÃ ĐƯỢC TÍNH SẴN "
    "cho MỘT mục phân tích kênh, và chỉ ra HÀM Ý HÀNH ĐỘNG cho người làm YouTube.\n"
    "QUY TẮC BẮT BUỘC (vi phạm là sai):\n"
    "1) CHỈ dựa trên số liệu được cung cấp. TUYỆT ĐỐI KHÔNG tạo ra con số nào không có trong dữ liệu.\n"
    "2) KHÔNG suy ra quan hệ nhân quả mà số liệu không chứng minh.\n"
    "3) KHÔNG đảo chiều/mâu thuẫn với kết luận và trạng thái mà engine đã xác định.\n"
    "4) Được tham chiếu mục KHÁC chỉ khi có liên hệ số THẬT (vd nhịp đăng ở tuổi thọ + tập trung "
    "Pareto cùng cho thấy phụ thuộc một video); KHÔNG bịa liên hệ nếu số không cho thấy.\n"
    "5) Viết 1–2 câu NGẮN, giọng nhà phân tích: con số NGHĨA LÀ GÌ + MỘT hành động nên làm. "
    "KHÔNG lặp lại y nguyên con số (đã hiện ở ô số) — giải thích nó.\n"
    "6) Nếu đề bài có LOẠI KÊNH: đọc con số theo ĐẶC THÙ loại kênh đó (vd retention thấp ở kênh "
    "trẻ em là bình thường), nhưng VẪN không bịa số và không đảo chiều kết luận/trạng thái engine."
)

_writer = None
_critics = None


# Việc trong CONTRACT data-analytics (apps.json viec_api) → prefix env cục bộ
# của factory hệ cũ (WRITER_*/CRITIC_* — khuôn nội bộ KHÔNG đổi). Bug đã sửa
# 18/08: bản cũ gọi thẳng vai "writer"/"critic" TRÙNG TÊN việc của ai-agent →
# gateway (hardcode ai-agent) trả nhầm khóa Writer ai-agent, bỏ qua cấp phát
# data-analytics trên UI Per-app config.
ANH_XA_VAI = {"dien_giai": "writer", "phan_bien": "critic"}


def nap_cau_hinh_llm() -> None:
    """Nạp cấu hình writer/critic từ KÉT (gateway loopback) vào env đúng khuôn
    factory hệ cũ — xin theo APP data-analytics + việc trong contract (ANH_XA_VAI).
    Việc chưa khai (provider rỗng) / gateway chết → env giữ nguyên."""
    try:
        with httpx.Client(timeout=3) as c:
            for vai_gateway, env_prefix in ANH_XA_VAI.items():
                ch = c.get(f"{GATEWAY_URL}/api/cau-hinh/llm/{vai_gateway}",
                           params={"app": "data-analytics"}).json()
                if not ch.get("provider"):
                    continue
                v = env_prefix.upper()
                os.environ[f"{v}_PROVIDER"] = ch["provider"]
                os.environ[f"{v}_MODEL"] = ch["model"]
                os.environ[f"{v}_BASE_URL"] = ch["base_url"]
                os.environ[f"{v}_API_KEY"] = ch["api_key"]
                os.environ[f"{v}_MOCK_MODE"] = "false"
                os.environ.setdefault("LLM_TIMEOUT", str(ch["timeout"]))
                os.environ.setdefault("LLM_RETRY", str(ch["retry"]))
    except httpx.HTTPError as e:
        logging.warning("Không nạp được cấu hình LLM từ gateway (%s) — dùng env/mock.", e)


def _lay_writer():
    global _writer, _critics
    if _writer is None:
        _writer = get_provider("writer")
        _critics = get_critics()
    return _writer, _critics


def _sinh_va_phan_bien(system_prompt: str, de_bai: str):
    """Vòng writer → critics → viết lại nếu LỖI — copy nguyên hệ cũ (van hệ thống)."""
    writer, critics = _lay_writer()
    answer = writer.generate(system_prompt, de_bai)
    reviews = [
        critic.generate(SYSTEM_CRITIC, f"{de_bai}\n\nCâu trả lời cần kiểm tra:\n{answer}")
        for critic in critics
    ]
    loi = [r for r in reviews
           if "LỖI" in (r.strip().splitlines() or [""])[0].upper()]
    if loi:
        answer = writer.generate(
            system_prompt,
            f"{de_bai}\n\nBản trả lời trước:\n{answer}\n\n"
            f"Phản biện đã chỉ ra lỗi:\n" + "\n\n".join(loi) +
            "\n\nViết lại câu trả lời, sửa hết các lỗi trên, vẫn CHỈ dựa trên dữ kiện đã cho.",
        )
    return answer, reviews, bool(loi)


def dien_giai_chan_doan(ket_qua: dict, user: dict | None = None,
                        loai_kenh_ctx: str = "") -> dict:
    """Diễn giải kết quả chẩn đoán (luật đã khớp) — van chống bịa giữ nguyên:
    không luật khớp → không gọi LLM."""
    matched = ket_qua["matched"]
    _, critics = _lay_writer()
    if not matched:
        return {"answer": "", "sources": [],
                "critic_count": len(critics), "reviews": [], "rewritten": False}
    luat_txt = "\n".join(
        f"- [{r['ma_luat']}] Tầng {r['tang_pheu']}: {r['nguyen_nhan']} "
        f"→ Cách sửa: {r['cach_sua']} (độ tin cậy: {r['do_tin_cay']})"
        for r in matched
    )
    so_lieu = ", ".join(f"{k}={v}" for k, v in ket_qua["metrics"].items())
    nguon_bl = ket_qua.get("nguon_baseline")
    dong_nguon = (f"Baseline đang so cho mỗi chỉ số (không phải luôn là toàn kênh): "
                  + ", ".join(f"{k}={v}" for k, v in nguon_bl.items()) + "\n"
                  if nguon_bl else "")
    de_bai = (
        (loai_kenh_ctx + "\n\n" if loai_kenh_ctx else "")
        + f"Số liệu hiện tại: {so_lieu}\n"
        + dong_nguon
        + f"Tầng phễu vỡ đầu tiên: {ket_qua.get('tang_vo') or '(không rõ)'}\n\n"
        f"Các luật chẩn đoán ĐÃ KHỚP (chỉ được diễn giải trong phạm vi này):\n{luat_txt}\n\n"
        f"Tài liệu/playbook liên quan trong kho:\n(không có)"
    )
    answer, reviews, rewritten = _sinh_va_phan_bien(SYSTEM_DIEN_GIAI, de_bai)
    return {"answer": answer, "sources": [],
            "critic_count": len(critics), "reviews": reviews, "rewritten": rewritten}


def dien_giai_muc_kenh(muc: dict, boi_canh_khac: str, user: dict | None = None,
                       loai_kenh_ctx: str = "") -> dict | None:
    """Tầng 2 — diễn giải 1 MỤC báo cáo kênh có NEO bối cảnh — copy nguyên hệ cũ."""
    if muc.get("trang_thai") != "co_ket_qua":
        return None
    so_lieu = muc.get("noi_dung") or ""
    if muc.get("so_video") is not None:
        so_lieu += f"\n- Số video làm căn cứ: {muc['so_video']}"
    if muc.get("ma_tran"):
        so_lieu += f"\n- Ma trận CTR×Retention (số video mỗi ô): {muc['ma_tran']}"
    if muc.get("chieu_phu"):
        so_lieu += "\n- Chiều phụ: " + "; ".join(
            f"{c['ten']}: {c.get('noi_dung') or c.get('ghi_chu')}" for c in muc["chieu_phu"])
    de_bai = (
        (loai_kenh_ctx + "\n\n" if loai_kenh_ctx else "")
        + f"MỤC ĐANG DIỄN GIẢI: [{muc['ma']}] {muc['ten']}\n"
        f"Số liệu/kết quả của mục này (Python đã tính sẵn — GIỮ NGUYÊN, KHÔNG tạo số mới):\n{so_lieu}\n\n"
        f"BỐI CẢNH — số liệu khác của kênh (mục khác + tương quan/xu hướng nếu có, đều do "
        f"Python tính sẵn; chỉ số, KHÔNG diễn giải; nối ý CHỈ khi có liên hệ số thật):\n"
        f"{boi_canh_khac}"
    )
    answer, reviews, rewritten = _sinh_va_phan_bien(SYSTEM_DIEN_GIAI_MUC, de_bai)
    _, critics = _lay_writer()
    return {"answer": answer, "critic_count": len(critics), "reviews": reviews,
            "rewritten": rewritten}
