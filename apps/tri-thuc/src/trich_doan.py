"""Module EXTRACT — LÕI của "nạp nguồn DÀI có kiểm soát" (supervisor.md §2b).

Nguồn ngoài/chuyên gia thường rất dài (transcript YouTube, bài viết, report). Không nạp
thô cả khối: LLM ĐỀ XUẤT các đoạn đáng giá → người chốt → mới vào kho (pattern "Duyệt" của Q&A).

NGUYÊN TẮC SỐNG CÒN — EXTRACT = TRÍCH NGUYÊN VĂN, KHÔNG VIẾT LẠI: LLM chỉ ĐÁNH DẤU đoạn đáng
giá (trích Y NGUYÊN chữ + một dòng "vì sao"), tuyệt đối KHÔNG tóm tắt/diễn giải. Nếu lưu bản
LLM viết lại thì cái vào kho là "lời của LLM", không phải lời nguồn → mất xuất xứ, thủng van
chống bịa. VAN TẠI ĐÂY: mỗi đoạn LLM trả về phải là SUBSTRING THẬT của văn bản gốc (kiểm
verbatim, chuẩn hóa khoảng trắng) — đoạn nào LLM bịa/paraphrase → BỎ.

Lệnh này chỉ làm LÕI de_xuat_trich (thuần, writer tiêm vào để test mock). Acquisition
(yt-dlp/transcript) + UI chốt + nạp kho = đợt sau.
"""

import re

# LLM trả về từng đoạn theo khối phân định; đoạn có thể nhiều dòng. KHOAN DUNG số dấu </>
# và khoảng trắng vì LLM hay lệch delimiter (GLM thật viết '<<<LYDO>>' thiếu 1 dấu > — kiểm
# chứng video Danny 24/07); không thể ép LLM đúng tuyệt đối nên parser phải chịu được lệch.
# Khối <<<DICH>>> (bản dịch tiếng Việt) TÙY CHỌN — nguồn vốn tiếng Việt thì LLM để trống,
# parser vẫn khớp đoạn không có DICH (giữ tương thích ngược định dạng cũ).
_MAU = re.compile(
    r"<+\s*TRICH\s*>+(.*?)"
    r"(?:<+\s*DICH\s*>+(.*?))?"
    r"<+\s*LYDO\s*>+(.*?)<+\s*HET\s*>+",
    re.DOTALL | re.IGNORECASE)
DAI_TOI_THIEU = 20   # đoạn quá ngắn thiếu ngữ cảnh cho RAG + dễ khớp verbatim tình cờ → bỏ

SYSTEM_TRICH = (
    "Bạn là người BIÊN TẬP nội dung, KHÔNG phải người viết. Nhiệm vụ: từ văn bản dài được cung "
    "cấp, CHỌN RA các đoạn đáng giá nhất (mẹo/nguyên tắc/kết luận/cách làm cụ thể) để làm nguồn "
    "tham khảo nội bộ.\n"
    "QUY TẮC BẮT BUỘC (vi phạm là hỏng):\n"
    "1) TRÍCH Y NGUYÊN VĂN — chép đúng từng chữ từ văn bản gốc. TUYỆT ĐỐI KHÔNG viết lại, KHÔNG "
    "tóm tắt, KHÔNG diễn giải, KHÔNG thêm chữ của bạn vào đoạn trích.\n"
    "2) Chỉ chọn đoạn có GIÁ TRỊ THẬT; bỏ chào hỏi, quảng cáo, câu lan man, kêu gọi mua hàng.\n"
    "3) Mỗi đoạn kèm bản DỊCH sát nghĩa sang TIẾNG VIỆT của ĐÚNG đoạn trích đó (khối <<<DICH>>>). "
    "Nếu đoạn gốc VỐN đã là tiếng Việt thì để TRỐNG khối <<<DICH>>>. Bản dịch để người đọc hiểu — "
    "KHÔNG thay lời gốc, KHÔNG thêm ý ngoài đoạn.\n"
    "4) Mỗi đoạn kèm MỘT DÒNG ngắn 'vì sao đáng giá' — dòng này là NHẬN XÉT của bạn, tách riêng "
    "khỏi đoạn trích.\n"
    "ĐỊNH DẠNG mỗi đoạn (lặp lại, không thêm gì ngoài các khối này):\n"
    "<<<TRICH>>>\n<đoạn nguyên văn>\n<<<DICH>>>\n<bản dịch tiếng Việt, để trống nếu gốc đã tiếng Việt>\n"
    "<<<LYDO>>>\n<một dòng vì sao>\n<<<HET>>>"
)


def _norm(s: str) -> str:
    """Chuẩn hóa để so verbatim: gộp khoảng trắng + lowercase (khoan dung cách LLM chép lại
    khoảng trắng/hoa-thường, nhưng vẫn bắt được paraphrase/bịa)."""
    return re.sub(r"\s+", " ", s).strip().lower()


def de_xuat_trich(van_ban: str, writer, so_doan: int = 8, nguon: str = "") -> list[dict]:
    """LLM đề xuất tối đa `so_doan` đoạn NGUYÊN VĂN đáng giá từ `van_ban`. Trả về
    [{trich, dich, ly_do}] — CHỈ giữ đoạn kiểm verbatim ĐẠT (thật sự có trong văn bản gốc);
    đoạn LLM bịa/viết lại bị LOẠI. `dich` = bản dịch tiếng Việt (nhãn phụ, KHÔNG kiểm verbatim —
    gốc đã tiếng Việt hoặc LLM bỏ trống → ""). Văn bản rỗng → []."""
    if not van_ban.strip():
        return []
    de_bai = (f"Nguồn: {nguon}\n\n" if nguon else "") + \
             f"Chọn tối đa {so_doan} đoạn đáng giá nhất.\n\nVăn bản:\n{van_ban}"
    tho = writer.generate(SYSTEM_TRICH, de_bai)

    goc = _norm(van_ban)
    ket = []
    for trich, dich, ly_do in _MAU.findall(tho):
        trich, dich, ly_do = trich.strip(), (dich or "").strip(), ly_do.strip()
        # VAN CHỐNG BỊA: chỉ ĐOẠN TRÍCH phải là substring THẬT của gốc (đủ dài) → LLM bịa/paraphrase
        # bị loại. `dich` là bản dịch (nhãn phụ) nên KHÔNG kiểm verbatim, đi kèm đoạn được giữ.
        if len(trich) >= DAI_TOI_THIEU and _norm(trich) in goc:
            ket.append({"trich": trich, "dich": dich, "ly_do": ly_do})
        if len(ket) >= so_doan:
            break
    return ket
