"""BẢN ĐẸP PDF từ .docx — Ý 4 Đợt 3.

Tài liệu team nạp là Word chữ thô. Module này sinh thêm một bản PDF trình bày
đẹp NẰM CẠNH bản gốc: cùng nội dung y hệt (van chống bịa — chỉ chia mục + tô
vàng <mark> chỗ quan trọng, không thêm/bớt/tóm tắt), qua vòng phản biện critic
glm-5 đối chiếu gốc↔đẹp trước khi lưu (chốt với user 19/07: ~99đ/tài liệu).

Tính năng PHỤ: lỗi bất kỳ (không phải .docx, thiếu GTK/WeasyPrint, model sập)
→ trả None và bỏ qua, KHÔNG BAO GIỜ chặn upload. Công tắc .env REMAKE_DEP.
"""

import html as html_lib
import logging
import os
import re
from pathlib import Path

from src.llm.factory import get_provider

GHI_CHU = "Bản trình bày lại từ tài liệu gốc — nội dung giữ nguyên"

SYSTEM_REMAKE = (
    "Bạn trình bày lại tài liệu nội bộ thành HTML đẹp, tiếng Việt. LUẬT SẮT (van "
    "chống bịa): giữ ĐỦ MỌI Ý của bản gốc, KHÔNG thêm thông tin mới, KHÔNG tóm tắt, "
    "KHÔNG suy diễn — chỉ được chia mục, đặt tiêu đề phụ sát nội dung, và bọc <mark> "
    "quanh những câu/cụm QUAN TRỌNG NHẤT (quy tắc, con số, cảnh báo). "
    "Chỉ trả về HTML phần thân dùng các thẻ h2/h3/p/ul/ol/li/table/tr/td/th/mark/b — "
    "KHÔNG <html>/<head>/<body>, KHÔNG CSS, KHÔNG <script>, không lời dẫn."
)
SYSTEM_CRITIC_REMAKE = (
    "Bạn đối chiếu BẢN TRÌNH BÀY LẠI với BẢN GỐC của một tài liệu nội bộ. Kiểm: "
    "(1) có Ý nào của bản gốc bị MẤT/tóm lược không? (2) có thông tin bị THÊM/bịa "
    "không? (3) số liệu, tên riêng, các bước có bị đổi không? "
    "DÒNG ĐẦU TIÊN chỉ ghi đúng một từ: 'ĐẠT' hoặc 'LỖI'. Từ dòng sau liệt kê từng vấn đề."
)

# CSS in PDF — nền chữ dễ đọc, mark vàng, tiêu đề có gạch nhấn
CSS_DEP = """
@page { size: A4; margin: 2cm 1.8cm; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; font-size: 11pt;
       line-height: 1.55; color: #1a1a2e; }
h1 { font-size: 17pt; color: #1d4ed8; border-bottom: 2.5pt solid #1d4ed8;
     padding-bottom: 6pt; margin-bottom: 4pt; }
.ghi-chu { font-size: 8.5pt; color: #64748b; font-style: italic; margin: 0 0 14pt; }
h2 { font-size: 13pt; color: #1e40af; border-left: 4pt solid #3b82f6;
     padding-left: 7pt; margin: 14pt 0 6pt; }
h3 { font-size: 11.5pt; color: #334155; margin: 10pt 0 4pt; }
mark { background: #fde047; padding: 0 2pt; border-radius: 2pt; }
ul, ol { margin: 4pt 0 8pt; padding-left: 18pt; }
li { margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 10pt; }
th, td { border: .7pt solid #cbd5e1; padding: 4pt 6pt; text-align: left; }
th { background: #eff6ff; }
"""


def lam_sach_html(tho: str) -> str:
    """Model hay bọc ```html``` và thi thoảng chèn thẻ thừa — cắt sạch trước khi render.
    Bỏ <script> (an toàn), bỏ vỏ html/head/body nếu model bướng trả cả trang."""
    sach = re.sub(r"^```[a-zA-Z]*\s*|```\s*$", "", tho.strip())
    sach = re.sub(r"<script\b.*?</script>", "", sach, flags=re.S | re.I)
    sach = re.sub(r"</?(?:html|head|body)[^>]*>", "", sach, flags=re.I)
    return sach.strip()


def dung_trang_html(title: str, doc_code: str, than: str) -> str:
    """Ghép trang hoàn chỉnh: tiêu đề + DÒNG GHI CHÚ BẮT BUỘC + thân đã trình bày lại."""
    return (f"<style>{CSS_DEP}</style>"
            f"<h1>{html_lib.escape(title)}</h1>"
            f"<p class='ghi-chu'>{GHI_CHU} · {html_lib.escape(doc_code)}</p>"
            f"{than}")


def tao_ban_dep(duong_dan_goc: Path, title: str, doc_code: str,
                writer=None, critic=None) -> Path | None:
    """Sinh <tên-gốc>_ban-dep.pdf cạnh bản gốc. None = bỏ qua (tắt công tắc /
    không phải .docx / lỗi bất kỳ) — người gọi không cần xử lý gì thêm."""
    if os.getenv("REMAKE_DEP", "true").strip().lower() != "true":
        return None
    duong_dan_goc = Path(duong_dan_goc)
    if duong_dan_goc.suffix.lower() != ".docx":
        return None
    try:
        from src.vector_client import _doc_file  # một nguồn sự thật đọc file với lõi

        chu_goc = _doc_file(duong_dan_goc).strip()
        if not chu_goc:
            return None

        writer = writer or get_provider("writer")
        de_bai = f"Tài liệu gốc:\n\n{chu_goc}"
        than = lam_sach_html(writer.generate(SYSTEM_REMAKE, de_bai))

        # Vòng phản biện (chốt: critic glm-5 — get_provider('critic') độc lập với
        # công tắc CRITICS của hỏi-đáp): LỖI → writer sửa lại 1 vòng rồi lưu
        critic = critic or get_provider("critic")
        review = critic.generate(
            SYSTEM_CRITIC_REMAKE,
            f"BẢN GỐC:\n{chu_goc}\n\nBẢN TRÌNH BÀY LẠI (HTML):\n{than}")
        if "LỖI" in (review.strip().splitlines() or [""])[0].upper():
            than = lam_sach_html(writer.generate(
                SYSTEM_REMAKE,
                f"{de_bai}\n\nBản trình bày trước:\n{than}\n\n"
                f"Phản biện đã chỉ lỗi:\n{review}\n\n"
                "Trình bày lại, sửa hết các lỗi trên — vẫn giữ đủ ý, không thêm bớt."))

        from weasyprint import HTML  # import tại chỗ — máy thiếu GTK không chết app

        duong_dan_pdf = duong_dan_goc.with_name(duong_dan_goc.stem + "_ban-dep.pdf")
        HTML(string=dung_trang_html(title, doc_code, than)).write_pdf(str(duong_dan_pdf))
        return duong_dan_pdf
    except Exception as loi:  # tính năng phụ — không bao giờ chặn upload
        logging.warning("Bỏ qua bản đẹp cho %s: %s", duong_dan_goc.name, loi)
        return None
