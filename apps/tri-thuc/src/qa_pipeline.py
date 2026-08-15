"""Vòng hỏi–đáp 4 bước: TÌM → TRẢ LỜI → PHẢN BIỆN → CHỐT.

Chống "nghe hợp lý mà sai" (CLAUDE.md — vòng phân tích–phản biện):
  B1 TÌM       : lõi vector Qdrant search → các đoạn tài liệu liên quan
  B2 TRẢ LỜI   : writer CHỈ dựa trên tài liệu, kèm trích nguồn; không có → không bịa
  B3 PHẢN BIỆN : từng critic soi lỗi (bịa? sai nguồn? nhảy cóc?)
  B4 CHỐT      : có lỗi → writer viết lại theo góp ý

Vòng B2→B4 (_sinh_va_phan_bien) dùng chung cho cả hỏi–đáp và diễn giải chẩn đoán số liệu.
Trung lập nhà cung cấp: writer/critics lấy qua factory — đổi model chỉ sửa .env.
"""

import csv
import os
import re
import time
from pathlib import Path

from src.llm.factory import get_critics, get_provider
from src.vector_client import QdrantClientWrapper

KHONG_CO_TAI_LIEU = "Chưa có thông tin này trong kho tài liệu."
GIOI_HAN_LUOT = 4  # chỉ giữ 4 lượt hỏi–đáp gần nhất làm ngữ cảnh — đủ hiểu, không phình token

# Các cụm writer dùng khi tài liệu không trả lời được (theo prompt chống bịa bên dưới).
# KHONG_CO_TAI_LIEU chứa "chưa có thông tin" nên ca kho-0-chunk cũng khớp tự nhiên.
_CUM_KHONG_TRA_LOI = ("chưa nêu", "chưa có thông tin", "không nêu", "chưa đề cập")

# ==== Nhận diện câu hỏi PHỤ THUỘC NGỮ CẢNH (05/08/2026 — sửa bug lạc đề nhiều lượt) ====
# Đo thật: "Ngâm kênh là gì?" -> "Thường kéo dài bao lâu?" — ghép chuỗi (cách cũ) bị chính
# cụm "kéo dài bao lâu" kéo sang tài liệu KHÁC có nhiều mốc thời gian hơn (kháng Vàng tiền:
# "10-15 phút", "2-3 phút"), mất hẳn ngữ cảnh "ngâm kênh" -> trả lời hoàn toàn lạc đề.
# Câu NGẮN + có đại từ/cụm hỏi cụt không nêu chủ đề mới cần viết lại; câu đã tự đủ nghĩa
# (dài, có chủ đề rõ) vẫn đi đường ghép chuỗi cũ, không tốn thêm lời gọi model.
_TU_THAM_CHIEU = ("nó", "đó", "cái này", "cái đó", "việc này", "việc đó", "điều này",
                  "điều đó", "cái trên", "như trên", "vừa nãy", "vừa rồi")
_HOI_CUT_KHONG_CHU_DE = re.compile(
    r"^(thế |vậy |thì |còn |sao |tại sao|khi nào|bao lâu|bao nhiêu|ở đâu|làm sao|"
    r"như thế nào|thường)", re.IGNORECASE)


def la_cau_khong_tra_loi_duoc(answer: str) -> bool:
    """Nhận diện câu trả lời kiểu "tài liệu không nói điều này" — dùng cho sổ kho-thiếu.
    KHÔNG so bằng tuyệt đối với hằng KHONG_CO_TAI_LIEU: hằng chỉ trả khi search về
    0 chunk, còn kho thật gần như luôn có chunk gần nghĩa → writer tự viết
    "Tài liệu chưa nêu cụ thể X" (bug A bảng /kho-thieu, điều tra 19/07)."""
    thap = answer.lower()
    return any(cum in thap for cum in _CUM_KHONG_TRA_LOI)

SYSTEM_WRITER = (
    "Bạn là trợ lý tri thức nội bộ. Trả lời TRỰC TIẾP và ĐẦY ĐỦ để GIẢI QUYẾT TRỌN VẸN vấn "
    "đề người hỏi — nêu đủ các bước, điều kiện, lý do cần thiết LẤY TỪ tài liệu; dùng gạch "
    "đầu dòng/đánh số nếu câu hỏi cần nhiều bước. SÚC TÍCH nghĩa là KHÔNG lặp lại, KHÔNG kể "
    "lể, KHÔNG bê nguyên đoạn tài liệu dài — KHÔNG đồng nghĩa với cắt ngắn tới mức thiếu ý "
    "khiến người hỏi phải hỏi lại. Bằng tiếng Việt dễ hiểu. "
    "Van chống bịa: CHỈ được dùng thông tin CÓ trong các đoạn tài liệu được cung cấp — "
    "không dùng kiến thức ngoài, không suy đoán cho gọn. Nếu tài liệu không nêu rõ điều "
    "được hỏi, nói thẳng phần đó: 'Tài liệu chưa nêu cụ thể điều này' (phần nào tài liệu "
    "CÓ trả lời được thì vẫn trả lời đầy đủ phần đó). "
    "Cuối câu trả lời ghi nguồn dạng [Mã tài liệu] — nguồn là phần phụ để kiểm chứng, "
    "câu trả lời đích xác mới là phần chính."
)
SYSTEM_CRITIC = (
    "Bạn là người phản biện khó tính. So câu trả lời với dữ kiện gốc được cung cấp, kiểm: "
    "(1) có bịa thông tin ngoài dữ kiện không? (2) có gán sai nguồn không? "
    "(3) có nhảy cóc kết luận không? (4) có ĐÚNG TRỌNG TÂM câu hỏi không — "
    "hay lan man, kể lể, đổ nguyên đoạn tài liệu dài thay vì trả lời? "
    "(5) có ĐẦY ĐỦ để người hỏi THỰC SỰ GIẢI QUYẾT được vấn đề không — hay cắt ngắn tới mức "
    "thiếu bước/thiếu điều kiện quan trọng MÀ TÀI LIỆU ĐÃ CÓ? Lan man LẪN thiếu ý đều tính "
    "là LỖI. DÒNG ĐẦU TIÊN chỉ ghi đúng một từ: 'ĐẠT' hoặc 'LỖI'. Từ dòng sau liệt kê từng vấn đề."
)
# ======== Bước 3 Supervisor — TRẢ LỜI ĐA CHIỀU (tách khối theo TỪNG NGUỒN) ========
# Thứ tự CỐ ĐỊNH: công ty (noi_bo) LUÔN trước → prefer. Khối "ngoài công ty" KHÔNG còn nhãn
# tầng chung (07/08 user chốt: không phân biệt chuyên gia/nguồn ngoài — coi là MỘT) mà tách
# MỘT KHỐI RIÊNG cho MỖI TÊN NGUỒN thật (vd "Andrew X", "Youtube Official") — xem
# _nhom_theo_nguon. Đề bài gửi cho LLM luôn có nhãn khối SẴN đúng tên; writer chỉ viết theo
# khối được cho, không tự đặt tên/nhãn.
NHAN_CONG_TY = "📌 Theo tài liệu công ty (Official)"

SYSTEM_DA_CHIEU = (
    "Bạn là CỐ VẤN đa chiều. Người dùng hỏi một câu; bạn được cung cấp các đoạn tài liệu ĐÃ "
    "CHIA SẴN THEO TỪNG KHỐI — mỗi khối '=== TẦNG: <nhãn> ===' là MỘT nguồn (tài liệu công ty, "
    "hoặc một người/nguồn cụ thể đã ghi ĐÚNG TÊN ngay trong nhãn). Nhiệm vụ: soạn một bản tư "
    "vấn TÁCH KHỐI, giúp người đọc thấy nhiều góc nhìn có nguồn rõ ràng.\n"
    "QUY TẮC BẮT BUỘC (vi phạm là hỏng):\n"
    "1) Van chống bịa: CHỈ dùng thông tin CÓ trong các đoạn được cung cấp — không kiến thức "
    "ngoài, không suy đoán.\n"
    "2) MỖI khối được cung cấp → viết MỘT đoạn riêng, mở đầu ĐÚNG NGUYÊN nhãn của khối đó (đã "
    "ghi sẵn tên tài liệu công ty hoặc tên chính xác của người/nguồn — KHÔNG đổi tên, KHÔNG gộp "
    "khối, KHÔNG tự thêm nhãn chung chung kiểu 'chuyên gia'/'nguồn ngoài'). Ghi mã nguồn [MÃ] "
    "ĐÚNG MỘT LẦN ở cuối mỗi đoạn để kiểm chứng — KHÔNG lặp lại mã sau mỗi câu/mỗi ý trong đoạn; "
    "đoạn dùng nhiều mã thì liệt kê chung ở cuối, ví dụ [MÃ1][MÃ2].\n"
    "3) TUYỆT ĐỐI KHÔNG viết cho khối nào KHÔNG được cung cấp — không có dữ liệu thì không được "
    "bịa quan điểm.\n"
    "4) Nếu từ HAI khối trở lên cùng bàn một vấn đề, thêm khối cuối '⚖️ Đồng thuận / Mâu thuẫn:' "
    "nêu chỗ giống/khác — CHỈ khi thật sự nói cùng điểm; không thì bỏ khối này.\n"
    "5) Cô đọng, tiếng Việt, đúng trọng tâm — KHÔNG bê nguyên đoạn dài."
)
SYSTEM_CRITIC_DA_CHIEU = (
    "Bạn là người phản biện khó tính cho một bản tư vấn ĐA CHIỀU (tách khối theo từng nguồn). "
    "So bản tư vấn với dữ kiện gốc TỪNG KHỐI, kiểm: (1) có bịa thông tin ngoài dữ kiện không? "
    "(2) có GÁN SAI ý cho SAI KHỐI / SAI NGUỒN không? (3) có BỊA QUAN ĐIỂM cho khối KHÔNG có dữ "
    "liệu không? (4) có gán sai mã nguồn [MÃ] không? (5) có lan man/lạc trọng tâm không? "
    "DÒNG ĐẦU TIÊN chỉ ghi đúng một từ: 'ĐẠT' hoặc 'LỖI'. Từ dòng sau liệt kê từng vấn đề."
)

# ==== Nút gợi ý "🧭 góc nhìn khác" SAU khi đã có câu trả lời công ty (rẻ hơn đa chiều đủ
# 2 khối): CHỈ tìm/viết tầng "ngoài" — câu trả lời công ty được ĐƯA VÀO đề bài làm ngữ cảnh
# đối chiếu (nguyên văn, không tự suy từ chunk) nhưng CẤM lặp lại, nên vẫn so sánh được mà
# không tốn chữ nhắc lại phần đã hiện ở trên (user chốt 08/08 sau khi phản biện qua lại).
SYSTEM_GOC_NHIN_NGOAI = (
    "Bạn là CỐ VẤN đa chiều. Câu trả lời từ tài liệu công ty ĐÃ được đưa ra cho người đọc ở "
    "TRÊN rồi — bạn TUYỆT ĐỐI KHÔNG lặp lại hay tóm tắt lại nó. Nhiệm vụ ở đây: giới thiệu góc "
    "nhìn từ các nguồn KHÁC (đã chia sẵn theo khối '=== TẦNG: <tên nguồn> ===', mỗi khối là một "
    "nguồn cụ thể), rồi đối chiếu với câu trả lời công ty đã có.\n"
    "QUY TẮC BẮT BUỘC (vi phạm là hỏng):\n"
    "1) Van chống bịa: CHỈ dùng thông tin CÓ trong các đoạn được cung cấp — không kiến thức "
    "ngoài, không suy đoán.\n"
    "2) MỖI khối nguồn → viết MỘT đoạn riêng, mở đầu ĐÚNG NGUYÊN tên nguồn (KHÔNG đổi tên, "
    "KHÔNG gộp khối). Ghi mã nguồn [MÃ] ĐÚNG MỘT LẦN ở cuối mỗi đoạn để kiểm chứng — KHÔNG lặp "
    "lại mã sau mỗi câu/mỗi ý trong đoạn; đoạn dùng nhiều mã thì liệt kê chung ở cuối, ví dụ "
    "[MÃ1][MÃ2].\n"
    "3) TUYỆT ĐỐI KHÔNG viết cho khối nào KHÔNG được cung cấp — không có dữ liệu thì không bịa.\n"
    "4) TUYỆT ĐỐI KHÔNG lặp lại/diễn giải lại câu trả lời công ty đã cho — chỉ dùng nó để SO "
    "SÁNH ở quy tắc 5.\n"
    "5) Thêm khối cuối '⚖️ Đồng thuận / Mâu thuẫn với câu trả lời công ty:' nêu chỗ giống/khác "
    "giữa (các) nguồn ngoài và câu trả lời công ty đã có — chỉ khi thật sự liên quan; không thì "
    "bỏ khối này.\n"
    "6) Đầy đủ để giải quyết trọn vẹn phần góc nhìn khác, không lan man, tiếng Việt dễ hiểu."
)
SYSTEM_CRITIC_GOC_NHIN_NGOAI = (
    "Bạn là người phản biện khó tính cho phần 'góc nhìn khác' (đối chiếu nguồn ngoài với câu "
    "trả lời công ty ĐÃ có sẵn, không được lặp lại). Kiểm: (1) có bịa thông tin ngoài dữ kiện "
    "không? (2) có gán sai nguồn/sai khối không? (3) có LẶP LẠI/tóm tắt lại câu trả lời công ty "
    "(bị cấm) không? (4) có bịa quan điểm cho khối không có dữ liệu không? (5) so sánh đồng "
    "thuận/mâu thuẫn có đúng với câu trả lời công ty đã cho không? "
    "DÒNG ĐẦU TIÊN chỉ ghi đúng một từ: 'ĐẠT' hoặc 'LỖI'. Từ dòng sau liệt kê từng vấn đề."
)

SYSTEM_VIET_LAI_CAU_HOI = (
    "Viết lại CÂU HỎI MỚI thành một câu hỏi ĐỘC LẬP, đầy đủ chủ đề — dựa vào lịch sử hội "
    "thoại để biết nó đang hỏi tiếp về điều gì. CHỈ trả về ĐÚNG MỘT câu hỏi đã viết lại, "
    "không giải thích, không thêm ký tự nào khác. Giữ NGUYÊN ý định của câu hỏi mới — chỉ "
    "bổ sung chủ đề còn thiếu (lấy từ lịch sử), KHÔNG tự thêm chi tiết ngoài những gì được hỏi."
)

SYSTEM_GOI_Y = (
    "Dựa CHỈ trên các đoạn tài liệu được cung cấp, sinh ĐÚNG 3 câu hỏi ngắn gọn mà "
    "người dùng có thể muốn hỏi tiếp, và tài liệu NÀY có thể trả lời được. "
    "KHÔNG bịa câu hỏi ngoài phạm vi tài liệu. "
    "Mỗi câu một dòng, không đánh số, không giải thích."
)
# Q&A bổ sung — soạn NHÁP câu trả lời để Owner DUYỆT rồi bổ sung vào kho. Van chống bịa nhiều
# lớp (analytic_methodology): chỉ dùng tài liệu được cung cấp; thiếu thì ghi rõ "⚠️ Cần bổ sung
# dữ kiện:"; hoàn toàn không có cơ sở → đúng một dòng "KHÔNG ĐỦ CƠ SỞ" để giao diện cảnh báo Owner.
SYSTEM_SOAN_QA = (
    "Bạn soạn NHÁP câu trả lời cho một câu hỏi nội bộ, để người quản lý duyệt rồi bổ sung vào "
    "kho tri thức. CHỈ dùng thông tin CÓ trong các đoạn tài liệu được cung cấp — không dùng "
    "kiến thức ngoài, không suy đoán. Nếu tài liệu CHƯA đủ để trả lời trọn vẹn, nêu rõ phần trả "
    "lời được và ghi '⚠️ Cần bổ sung dữ kiện:' cho phần thiếu — KHÔNG bịa cho đủ. Nếu các đoạn "
    "tài liệu HOÀN TOÀN không chứa thông tin trả lời được câu hỏi, ghi đúng một dòng: "
    "'KHÔNG ĐỦ CƠ SỞ' và KHÔNG viết gì thêm. Tiếng Việt, cô đọng, đúng trọng tâm."
)
SYSTEM_DIEN_GIAI = (
    "Bạn diễn giải kết quả chẩn đoán số liệu cho người không chuyên kỹ thuật. "
    "CHỈ được dựa trên danh sách LUẬT ĐÃ KHỚP và đoạn tài liệu/playbook được cung cấp — "
    "tuyệt đối KHÔNG tự suy diễn nguyên nhân mới ngoài các luật đã khớp. "
    "Với mỗi luật: giải thích ngắn vì sao số liệu khớp luật đó và việc cần làm, theo thứ tự ưu tiên."
)


# Tầng 2 — diễn giải MỘT mục báo cáo kênh (có neo bối cảnh các mục khác). Prompt ghi RÕ luật
# chống bịa: LLM chỉ diễn giải số Python đã tính, không tạo số, không suy nhân quả không có, không
# đảo chiều kết luận engine. (Kiến trúc 2 tầng + van chống bịa — analytic_methodology mục 2, 5, 8.)
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


class QAPipeline:
    def __init__(self, rag=None, writer=None, critics=None):
        self.rag = rag or QdrantClientWrapper()
        self.writer = writer or get_provider("writer")
        self.critics = critics if critics is not None else get_critics()

    # ---- vòng B2→B4 dùng chung ----
    def _sinh_va_phan_bien(self, system_prompt: str, de_bai: str):
        answer = self.writer.generate(system_prompt, de_bai)
        reviews = [
            critic.generate(SYSTEM_CRITIC, f"{de_bai}\n\nCâu trả lời cần kiểm tra:\n{answer}")
            for critic in self.critics
        ]
        loi = [r for r in reviews
               if "LỖI" in (r.strip().splitlines() or [""])[0].upper()]
        if loi:
            answer = self.writer.generate(
                system_prompt,
                f"{de_bai}\n\nBản trả lời trước:\n{answer}\n\n"
                f"Phản biện đã chỉ ra lỗi:\n" + "\n\n".join(loi) +
                "\n\nViết lại câu trả lời, sửa hết các lỗi trên, vẫn CHỈ dựa trên dữ kiện đã cho.",
            )
        return answer, reviews, bool(loi)

    @staticmethod
    def _ban_dep_theo_ma() -> dict[str, str]:
        """doc_code → tên PDF bản đẹp (cột 16 _catalog.csv, dòng mới nhất thắng).
        Catalog thiếu/hỏng → {} — gợi ý tải chỉ là phụ, không được làm hỏng hỏi-đáp."""
        so = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "_catalog.csv"
        if not so.is_file():
            return {}
        ket_qua = {}
        try:
            for d in list(csv.reader(so.open(encoding="utf-8-sig")))[1:]:
                if len(d) >= 16 and d[0]:
                    ket_qua[d[0]] = d[15]
        except Exception:
            return {}
        return ket_qua

    @staticmethod
    def _gom_nguon(chunks: list[dict]) -> list[dict]:
        # YC3: thêm cho frontend gợi-ý-tải — diem_lien_quan TÁI DÙNG điểm search có
        # sẵn (rerank_score nếu có, else similarity; lấy MAX các chunk cùng tài liệu),
        # co_ban_dep tra catalog, goi_y_tai = vượt ngưỡng NGUONG_GOI_Y_TAI (.env —
        # khởi điểm 0.5, PHẢI đo dữ liệu thật rồi chỉnh như NGUONG_BI_CHAN).
        # doc_code giữ nguyên cho các cơ chế ngầm (lịch sử D1/D2, Rule 2, kho-thiếu).
        diem_max: dict = {}
        for c in chunks:
            diem = float(c.get("rerank_score", c.get("similarity", 0.0)) or 0.0)
            diem_max[c["document_id"]] = max(diem_max.get(c["document_id"], 0.0), diem)

        ban_dep = QAPipeline._ban_dep_theo_ma()
        nguong = float(os.getenv("NGUONG_GOI_Y_TAI", "0.5"))
        sources, da_thay = [], set()
        for c in chunks:
            if c["document_id"] in da_thay:
                continue
            da_thay.add(c["document_id"])
            md = c["document_metadata"]
            ma = md.get("doc_code", "")
            diem = diem_max[c["document_id"]]
            sources.append({
                "doc_code": ma,
                "title": md.get("title") or c["document_keyword"],
                "department": md.get("department", ""),
                "effective_status": md.get("effective_status", ""),
                "diem_lien_quan": round(diem, 4),
                "co_ban_dep": bool(ban_dep.get(ma)),
                "goi_y_tai": diem >= nguong,
            })
        return sources

    @staticmethod
    def _boi_canh(chunks: list[dict]) -> str:
        return "\n\n".join(
            f"[{c['document_metadata'].get('doc_code', c['document_id'])}] "
            f"({c['document_keyword']})\n{c['content']}"
            for c in chunks
        )

    @staticmethod
    def _hoi_thoai(lich_su: list[dict]) -> str:
        return "\n".join(f"Người dùng: {l['hoi']}\nTrợ lý: {l['dap']}" for l in lich_su)

    @staticmethod
    def _can_viet_lai_cau_hoi(cau_hoi: str) -> bool:
        """Câu NGẮN + có dấu hiệu phụ thuộc ngữ cảnh (đại từ tham chiếu / hỏi cụt không nêu
        chủ đề) → cần viết lại thành câu độc lập trước khi tìm. Câu đã tự đủ nghĩa (dài, có
        chủ đề rõ) → False, giữ đường ghép chuỗi cũ (không tốn thêm lời gọi model)."""
        if len(cau_hoi.split()) > 12:
            return False
        thap = cau_hoi.strip().lower()
        return (any(t in thap for t in _TU_THAM_CHIEU)
                or bool(_HOI_CUT_KHONG_CHU_DE.match(thap)))

    def _cau_tim_theo_ngu_canh(self, cau_hoi: str, lich_su: list[dict]) -> tuple[str, bool]:
        """Câu dùng để TÌM tài liệu khi có lịch sử — trả (câu_tìm, đã_viết_lại_bằng_model).
        MỘT NGUỒN DÙNG CHUNG cho mọi đường hỏi (thường/đa chiều/góc nhìn khác) — sửa một
        chỗ, khỏi lặp lại kiểu lỗ hổng 07/08 (4 chỗ copy cùng logic, sửa sót chỗ nào là
        chỗ đó vẫn giữ bug cũ)."""
        if not lich_su:
            return cau_hoi, False
        if self._can_viet_lai_cau_hoi(cau_hoi):
            try:
                viet_lai = self.writer.generate(
                    SYSTEM_VIET_LAI_CAU_HOI,
                    f"{self._hoi_thoai(lich_su)}\n\nCâu hỏi mới: {cau_hoi}").strip()
            except Exception:
                viet_lai = ""
            if viet_lai:
                return viet_lai, True
        return " ; ".join([l["hoi"] for l in lich_su[-2:]] + [cau_hoi]), False

    # ---- B1 dùng chung cho hoi() và hoi_stream(): viết lại câu hỏi → TÌM → soạn đề bài ----
    # Trả thêm dict đo thời gian từng chặng (chỉ hoi_stream dùng để in [PERF]).
    def _tim_va_soan_de_bai(self, cau_hoi: str, filters: dict | None,
                            lich_su: list[dict] | None, user: dict | None = None):
        do_tg = {}
        # Mặc định chỉ tra tài liệu còn hiệu lực — "trường hay quên & hối tiếc nhất".
        # LỖ HỔNG VÁ 07/08: thiếu "tang_nguon": "noi_bo" ở đây từ khi module EXTRACT
        # (bài học kinh nghiệm nguồn ngoài) ra đời — hỏi–đáp THƯỜNG (không bật 🧭 Đa chiều)
        # đã âm thầm trộn LẪN tài liệu tầng chuyên gia/ngoài vào MỌI câu trả lời, không gắn
        # nhãn tầng, phá đúng bất biến "mặc định giữ nguyên chỉ tầng noi_bo" (supervisor.md
        # §3.1) — khiến nút Đa chiều thành vô nghĩa vì việc nó làm đã xảy ra sẵn ở đây rồi.
        if filters is None:
            filters = {"effective_status": "Còn hiệu lực", "tang_nguon": "noi_bo"}
        lich_su = (lich_su or [])[-GIOI_HAN_LUOT:]

        # 05/08/2026: viết lại CÓ ĐIỀU KIỆN thay ghép chuỗi mù quáng — sửa bug lạc đề nhiều
        # lượt (xem chú thích _cau_tim_theo_ngu_canh đầu file cho ca thật đã đo).
        cau_tim, da_viet_lai = self._cau_tim_theo_ngu_canh(cau_hoi, lich_su)
        if lich_su:
            do_tg["viet_lai_cau_hoi" if da_viet_lai else "ghep_truy_van"] = True

        # Van chống bịa: LƯỢT NÀO cũng phải tìm tài liệu thật, không trả lời từ trí nhớ model.
        # user truyền xuống để lõi LỌC QUYỀN lặng lẽ (Mảnh B) — bị chặn thì như kho không có
        t0 = time.perf_counter()
        chunks = self.rag.search(cau_tim, filters, user=user)
        do_tg["tim"] = time.perf_counter() - t0

        # RULE 2 (sửa bug): kiểm bị-chặn-quyền trên MỌI câu có user thật, KHÔNG chỉ khi
        # rỗng — bug cũ bỏ sót ca "tìm thấy tài liệu được phép NHƯNG kho còn tài liệu
        # bị chặn cùng khớp" (vd nv level 2 hỏi AdSense: thấy MMO, sót AdSense level 4).
        # User None/khách → hàm tự trả False ngay, không tốn truy vấn thứ hai.
        bi_chan = self.rag.search_co_bi_chan(cau_tim, filters, user)
        if not chunks:
            return [], "", do_tg, bi_chan, cau_tim

        ngu_canh = (f"Hội thoại trước đó (để hiểu câu hỏi, KHÔNG phải nguồn dữ kiện):\n"
                    f"{self._hoi_thoai(lich_su)}\n\n") if lich_su else ""
        de_bai = (f"{ngu_canh}Câu hỏi: {cau_hoi}\n\n"
                  f"Các đoạn tài liệu:\n{self._boi_canh(chunks)}")
        # cau_tim trả kèm để hoi_stream() TÁI DÙNG cho goi_y_goc_nhin_khac — tránh viết lại
        # câu hỏi HAI LẦN cho cùng một lượt (mỗi lần viết lại tốn 1 lời gọi model).
        return chunks, de_bai, do_tg, bi_chan, cau_tim

    # ---- Ý 3 Đợt 3: gợi ý câu hỏi tiếp theo (kiểu NotebookLM) ----
    def goi_y_cau_hoi(self, cau_hoi: str, chunks: list[dict]) -> list[str]:
        """Sinh tối đa 3 câu hỏi tiếp theo TỪ tài liệu đã trích — chunks đã qua lọc
        quyền nên gợi ý tự nhiên nằm trong phạm vi user thấy được, không vẽ đường
        tới tài liệu bị chặn. Tính năng PHỤ: tắt qua .env GOI_Y_CAU_HOI=false;
        kho rỗng không gợi ý; model lỗi thì im lặng — không hỏng câu trả lời chính.
        (Option 2 — chèn thêm câu phổ biến từ lịch sử/kho-thiếu: để sau.)"""
        if not chunks or os.getenv("GOI_Y_CAU_HOI", "true").strip().lower() != "true":
            return []
        de_bai = (f"Câu hỏi người dùng vừa hỏi: {cau_hoi}\n\n"
                  f"Các đoạn tài liệu:\n{self._boi_canh(chunks)}")
        try:
            tho = self.writer.generate(SYSTEM_GOI_Y, de_bai)
        except Exception:
            return []
        cau = []
        for dong in tho.splitlines():
            dong = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", dong).strip()  # bỏ số/gạch đầu dòng
            if dong:
                cau.append(dong)
            if len(cau) == 3:
                break
        return cau

    # ---- hỏi–đáp tài liệu (nhiều lượt) — đường KHÔNG stream, giữ nguyên cho
    # chẩn đoán / fallback / viết lại ----
    def hoi(self, cau_hoi: str, filters: dict | None = None,
            lich_su: list[dict] | None = None, user: dict | None = None) -> dict:
        chunks, de_bai, _, bi_chan, _ = self._tim_va_soan_de_bai(cau_hoi, filters, lich_su, user)
        if not chunks:
            return {"answer": KHONG_CO_TAI_LIEU, "sources": [],
                    "critic_count": len(self.critics), "reviews": [], "rewritten": False,
                    "bi_chan_quyen": bi_chan, "goi_y": []}

        answer, reviews, rewritten = self._sinh_va_phan_bien(SYSTEM_WRITER, de_bai)
        return {"answer": answer, "sources": self._gom_nguon(chunks),
                "critic_count": len(self.critics), "reviews": reviews,
                "rewritten": rewritten, "bi_chan_quyen": bi_chan,
                "goi_y": self.goi_y_cau_hoi(cau_hoi, chunks)}

    # ======== Bước 3 Supervisor — TRẢ LỜI ĐA CHIỀU (đường RIÊNG, không đụng hoi/hoi_stream) ========
    @staticmethod
    def _boi_canh_tang(chunks: list[dict]) -> str:
        """Bối cảnh 1 tầng: mỗi đoạn kèm [MÃ] + tên nguồn (nếu có) để writer trích + gán tầng."""
        dong = []
        for c in chunks:
            md = c["document_metadata"]
            ma = md.get("doc_code", c["document_id"])
            ten = md.get("nguon_ten")
            dau = f"[{ma}]" + (f" (nguồn: {ten})" if ten and ten != "Official" else "")
            dong.append(f"{dau}\n{c['content']}")
        return "\n\n".join(dong)

    @classmethod
    def _de_bai_da_chieu(cls, cau_hoi: str, theo_tang: list) -> str:
        """Đề bài tách khối theo từng nguồn — CHỈ gồm khối CÓ chunk (khối rỗng đã bị loại ở
        caller → writer không có cớ bịa khối). theo_tang = [(khoa, nhan, chunks)] giữ thứ tự
        công-ty-trước."""
        khoi = [f"=== TẦNG: {nhan} ===\n{cls._boi_canh_tang(chunks)}"
                for _, nhan, chunks in theo_tang if chunks]
        return f"Câu hỏi: {cau_hoi}\n\n" + "\n\n".join(khoi)

    def _nhom_theo_nguon(self, chunks: list[dict]) -> list[tuple]:
        """Gom chunk NGOÀI công ty theo TÊN NGUỒN thật (nguon_ten) — mỗi tên một khối riêng,
        KHÔNG còn nhãn chung 'chuyên gia'/'nguồn ngoài' (07/08 user chốt: coi là MỘT, chỉ cần
        đưa đúng tên người/nguồn, vd "Andrew X", "Youtube Official"). Nguồn có điểm liên quan
        cao nhất lên khối trước (sau công ty); thiếu tên (dữ liệu cũ) → gom vào 'Nguồn khác'."""
        theo_ten: dict[str, list[dict]] = {}
        for c in chunks:
            ten = (c["document_metadata"].get("nguon_ten") or "").strip() or "Nguồn khác"
            theo_ten.setdefault(ten, []).append(c)
        thu_tu = sorted(theo_ten,
                        key=lambda t: max(self._diem_chunk(c) for c in theo_ten[t]),
                        reverse=True)
        return [(f"ngoai:{ten}", f"🌐 {ten}", theo_ten[ten]) for ten in thu_tu]

    def hoi_stream_da_chieu(self, cau_hoi: str, lich_su: list[dict] | None = None,
                            user: dict | None = None):
        """TÌM RIÊNG công ty vs phần còn lại (2 suất — nguồn khác điểm cao KHÔNG đè tài liệu
        công ty ra khỏi kết quả). Công ty (noi_bo) có chunk nào là hiện (PREFER, luôn trước);
        phần còn lại chỉ hiện khi vượt NGUONG_DA_CHIEU, rồi TÁCH MỘT KHỐI RIÊNG cho MỖI TÊN
        NGUỒN thật (không phân biệt chuyên gia/ngoài — 07/08); khối rỗng → bỏ (van chống bịa).
        Công ty trống mà nguồn khác có → vẫn trả lời + cảnh báo (tín hiệu kho-thiếu). Lọc quyền
        giữ nguyên qua rag.search(user=...). SSE giống hoi_stream: sources → token* → (review?) → done."""
        lich_su = (lich_su or [])[-GIOI_HAN_LUOT:]
        cau_tim, _ = self._cau_tim_theo_ngu_canh(cau_hoi, lich_su)  # 05/08: viết lại có điều kiện

        base = {"effective_status": "Còn hiệu lực"}
        nguong = float(os.getenv("NGUONG_DA_CHIEU", "0.3"))
        cty = self.rag.search(cau_tim, {**base, "tang_nguon": "noi_bo"}, user=user)
        ngoai = self.rag.search(cau_tim, {**base, "tang_nguon": "ngoai"}, user=user)
        if not (ngoai and max(self._diem_chunk(c) for c in ngoai) >= nguong):
            ngoai = []
        # [(khoa, nhan, chunks)] — công ty LUÔN đầu (prefer); phần còn lại tách theo tên nguồn
        theo_tang = [("noi_bo", NHAN_CONG_TY, cty)] + self._nhom_theo_nguon(ngoai)

        cong_ty_trong = not theo_tang[0][2]
        # RULE 2 (bug A): công ty "trống" có thể vì BỊ CHẶN QUYỀN, không phải kho thiếu thật —
        # tách ra để route không ghi nhầm sổ kho-thiếu. Chỉ tốn 1 truy vấn KHI công ty trống.
        bi_chan = bool(cong_ty_trong and self.rag.search_co_bi_chan(
            cau_tim, {**base, "tang_nguon": "noi_bo"}, user))
        tat_ca = [c for _, _, giu in theo_tang for c in giu]
        if not tat_ca:  # không tầng nào có → như kho rỗng, KHÔNG gọi model (van chống bịa lớp 1)
            yield {"type": "token", "data": KHONG_CO_TAI_LIEU}
            yield {"type": "done", "data": {"critic_count": len(self.critics),
                                            "cong_ty_trong": True, "bi_chan_quyen": bi_chan}}
            return

        yield {"type": "sources", "data": self._gom_nguon(tat_ca)}
        if cong_ty_trong:  # deterministic — không nhờ writer, để tín hiệu luôn hiện đúng
            yield {"type": "token",
                   "data": "⚠️ Công ty chưa có tài liệu về việc này — dưới đây là góc nhìn "
                           "tham khảo từ nguồn ngoài/chuyên gia.\n\n"}

        de_bai = self._de_bai_da_chieu(cau_hoi, theo_tang)
        cac_mau = []
        for mau in self.writer.generate_stream(SYSTEM_DA_CHIEU, de_bai):
            cac_mau.append(mau)
            yield {"type": "token", "data": mau}
        answer = "".join(cac_mau)

        if self.critics:  # critic có tiêu chí "sai tầng/bịa quan điểm cho tầng rỗng"
            reviews = [critic.generate(SYSTEM_CRITIC_DA_CHIEU,
                                       f"{de_bai}\n\nBản tư vấn cần kiểm tra:\n{answer}")
                       for critic in self.critics]
            loi = [r for r in reviews
                   if "LỖI" in (r.strip().splitlines() or [""])[0].upper()]
            if loi:
                yield {"type": "review",
                       "data": "Phản biện phát hiện vấn đề trong bản tư vấn:\n" + "\n\n".join(loi)}
        yield {"type": "done", "data": {"critic_count": len(self.critics),
                                        "cong_ty_trong": cong_ty_trong, "bi_chan_quyen": bi_chan}}

    # ======== Nút gợi ý "🧭 góc nhìn khác" — chốt 08/08 sau khi phản biện qua lại về việc lặp
    # lại câu trả lời công ty. Rẻ hơn hoi_stream_da_chieu: hiện dưới dạng box gợi ý SAU khi câu
    # trả lời công ty (đường /hoi-dap/stream mặc định) đã stream xong, chỉ bấm mới tốn thêm 1
    # lượt tìm + 1 lượt gọi model — không đụng route/luồng mặc định. ========
    def goi_y_goc_nhin_khac(self, cau_hoi: str, lich_su: list[dict] | None = None,
                            user: dict | None = None, cau_tim: str | None = None) -> list[str]:
        """Kiểm RẺ sau khi câu trả lời công ty đã chảy hết chữ (không chặn TTFT, cùng chỗ với
        goi_y_cau_hoi): tầng 'ngoài' có gì đủ liên quan không — CHỈ trả TÊN nguồn để frontend
        hiện box gợi ý, KHÔNG sinh câu trả lời ở đây (bấm vào mới gọi hoi_stream_goc_nhin_ngoai).
        Rỗng/dưới ngưỡng NGUONG_DA_CHIEU → [] (không hiện gì — đúng triết lý 01/08 chỉ khi có thật).

        cau_tim: truyền SẴN nếu caller (hoi_stream) đã tính rồi — khỏi viết lại câu hỏi LẦN
        THỨ HAI cho cùng một lượt. Gọi độc lập (không qua hoi_stream) thì để None, tự tính."""
        lich_su = (lich_su or [])[-GIOI_HAN_LUOT:]
        if cau_tim is None:
            cau_tim, _ = self._cau_tim_theo_ngu_canh(cau_hoi, lich_su)  # 05/08: viết lại có điều kiện
        nguong = float(os.getenv("NGUONG_DA_CHIEU", "0.3"))
        ngoai = self.rag.search(cau_tim, {"effective_status": "Còn hiệu lực",
                                          "tang_nguon": "ngoai"}, user=user)
        if not ngoai or max(self._diem_chunk(c) for c in ngoai) < nguong:
            return []
        return [ma.split(":", 1)[1] for ma, _, _ in self._nhom_theo_nguon(ngoai)]

    @classmethod
    def _de_bai_goc_nhin_ngoai(cls, cau_hoi: str, cau_tra_loi_cong_ty: str,
                               theo_nguon: list) -> str:
        """Đề bài CHỈ gồm khối nguồn ngoài (không có khối công ty) — câu trả lời công ty được
        đưa vào làm NGỮ CẢNH ĐỌC-ĐỂ-SO (nguyên văn, không tự suy từ chunk), prompt cấm lặp lại."""
        khoi = [f"=== TẦNG: {nhan} ===\n{cls._boi_canh_tang(chunks)}"
                for _, nhan, chunks in theo_nguon if chunks]
        return (f"Câu hỏi: {cau_hoi}\n\n"
                f"Câu trả lời công ty ĐÃ đưa ra ở trên (chỉ để đối chiếu, KHÔNG lặp lại):\n"
                f"{cau_tra_loi_cong_ty.strip()}\n\n" + "\n\n".join(khoi))

    def hoi_stream_goc_nhin_ngoai(self, cau_hoi: str, cau_tra_loi_cong_ty: str,
                                  lich_su: list[dict] | None = None, user: dict | None = None):
        """Bấm box gợi ý → CHỈ tìm/viết tầng 'ngoài' (1 lượt tìm, không đụng tầng công ty —
        đã trả lời + đã ghi kho-thiếu ở lượt trước, không ghi lại ở đây). Đối chiếu được với
        công ty vì đề bài mang nguyên văn câu trả lời đó vào làm ngữ cảnh (xem
        _de_bai_goc_nhin_ngoai). SSE: sources → token* → (review?) → done."""
        lich_su = (lich_su or [])[-GIOI_HAN_LUOT:]
        cau_tim, _ = self._cau_tim_theo_ngu_canh(cau_hoi, lich_su)  # 05/08: viết lại có điều kiện

        nguong = float(os.getenv("NGUONG_DA_CHIEU", "0.3"))
        ngoai = self.rag.search(cau_tim, {"effective_status": "Còn hiệu lực",
                                          "tang_nguon": "ngoai"}, user=user)
        if not ngoai or max(self._diem_chunk(c) for c in ngoai) < nguong:
            yield {"type": "token",
                   "data": "Không tìm thấy góc nhìn khác phù hợp cho câu hỏi này."}
            yield {"type": "done", "data": {"critic_count": len(self.critics)}}
            return

        theo_nguon = self._nhom_theo_nguon(ngoai)
        yield {"type": "sources", "data": self._gom_nguon(ngoai)}
        de_bai = self._de_bai_goc_nhin_ngoai(cau_hoi, cau_tra_loi_cong_ty, theo_nguon)

        cac_mau = []
        for mau in self.writer.generate_stream(SYSTEM_GOC_NHIN_NGOAI, de_bai):
            cac_mau.append(mau)
            yield {"type": "token", "data": mau}
        answer = "".join(cac_mau)

        if self.critics:
            reviews = [critic.generate(SYSTEM_CRITIC_GOC_NHIN_NGOAI,
                                       f"{de_bai}\n\nBản góc nhìn khác cần kiểm tra:\n{answer}")
                       for critic in self.critics]
            loi = [r for r in reviews
                   if "LỖI" in (r.strip().splitlines() or [""])[0].upper()]
            if loi:
                yield {"type": "review",
                       "data": "Phản biện phát hiện vấn đề:\n" + "\n\n".join(loi)}
        yield {"type": "done", "data": {"critic_count": len(self.critics)}}

    # ======== Q&A BỔ SUNG — cơ chế 2 bước (Owner chọn đích, van chống bịa nhiều lớp) ========
    @staticmethod
    def _diem_chunk(c: dict) -> float:
        """Điểm liên quan của 1 chunk: rerank_score nếu rerank bật (thang cross-encoder),
        else similarity — CÙNG cách _gom_nguon chấm điểm."""
        return float(c.get("rerank_score", c.get("similarity", 0.0)) or 0.0)

    def ung_vien_qa(self, cau_hoi: str, filters: dict | None = None,
                    user: dict | None = None) -> dict:
        """BƯỚC 1: tìm top tài liệu ỨNG VIÊN để Owner chọn đích bổ sung Q&A. Lọc quyền
        giữ nguyên (Owner cũng bị áp luật xem). CHỈ tầng noi_bo (07/08 — cùng lỗ hổng đã
        vá ở _tim_va_soan_de_bai): Q&A bổ sung là bù KHO CÔNG TY, không phải chỗ đính câu
        trả lời lên tài liệu chuyên gia/nguồn ngoài. Kho rỗng / điểm cao nhất DƯỚI ngưỡng →
        báo không có tài liệu, KHÔNG gọi LLM (van chống bịa lớp 1)."""
        if filters is None:
            filters = {"effective_status": "Còn hiệu lực", "tang_nguon": "noi_bo"}
        chunks = self.rag.search(cau_hoi, filters, user=user)
        # Ngưỡng để dành chỉnh khi kho lớn, giống NGUONG_BI_CHAN (đo dữ liệu thật rồi mới chỉnh)
        nguong = float(os.getenv("NGUONG_LIEN_QUAN_QA", "0.3"))
        if not chunks or max(self._diem_chunk(c) for c in chunks) < nguong:
            return {"co_tai_lieu": False,
                    "message": "Kho chưa có tài liệu nào đủ liên quan để bổ sung — "
                               "có thể cần nạp tài liệu mới cho chủ đề này."}
        # Gom theo doc_code (1 tài liệu nhiều chunk) → giữ chunk điểm cao nhất mỗi tài liệu
        tot: dict[str, dict] = {}
        for c in chunks:
            md = c["document_metadata"]
            ma = md.get("doc_code") or c["document_id"]
            diem = self._diem_chunk(c)
            if ma not in tot or diem > tot[ma]["diem"]:
                tot[ma] = {"doc_code_goc": ma,
                           "tieu_de_goc": md.get("title") or c["document_keyword"],
                           "diem": round(diem, 4),
                           "doan_trich": c["content"]}   # đoạn tiêu biểu để Owner nhận ra tài liệu
        so = int(os.getenv("SO_UNG_VIEN_QA", "3"))
        ung_vien = sorted(tot.values(), key=lambda u: u["diem"], reverse=True)[:so]
        return {"co_tai_lieu": True, "ung_vien": ung_vien}

    def soan_nhap_qa(self, cau_hoi: str, doc_code_goc: str,
                     user: dict | None = None) -> dict:
        """BƯỚC 2: soạn NHÁP trên tài liệu Owner ĐÃ CHỌN (không để máy tự chọn liều —
        van chống bịa lớp 2). Lọc quyền giữ nguyên: nếu tài liệu vượt quyền xem thì
        không còn chunk → báo lỗi rõ. KHÔNG ghi kho (ghi để lệnh Duyệt sau). CHỈ tầng
        noi_bo — khớp ung_vien_qa (07/08), Q&A bổ sung không đính lên tài liệu ngoài."""
        chunks = self.rag.search(cau_hoi, {"effective_status": "Còn hiệu lực",
                                           "tang_nguon": "noi_bo"}, user=user)
        cua_tl = [c for c in chunks
                  if (c["document_metadata"].get("doc_code") or c["document_id"]) == doc_code_goc]
        if not cua_tl:
            return {"ok": False,
                    "message": "Không lấy được nội dung tài liệu đã chọn (có thể ngoài quyền xem)."}
        md0 = cua_tl[0]["document_metadata"]
        tieu_de = md0.get("title") or cua_tl[0]["document_keyword"]
        de_bai = f"Câu hỏi: {cau_hoi}\n\nCác đoạn tài liệu:\n{self._boi_canh(cua_tl)}"
        nhap = self.writer.generate(SYSTEM_SOAN_QA, de_bai)   # van chống bịa lớp 3 = prompt
        return {"ok": True, "doc_code_goc": doc_code_goc, "tieu_de_goc": tieu_de,
                "nhap": nhap, "cac_nguon": self._gom_nguon(cua_tl),
                "khong_du_co_so": nhap.strip().startswith("KHÔNG ĐỦ CƠ SỞ")}

    # ---- hỏi–đáp bản STREAM: yield sự kiện {"type", "data"} theo thứ tự
    # sources → token* → (review?) → done ----
    def hoi_stream(self, cau_hoi: str, filters: dict | None = None,
                   lich_su: list[dict] | None = None, user: dict | None = None):
        """Đường stream SONG SONG với hoi(), không thay thế.

        Khác hoi() đúng một điểm: critic chạy SAU khi đã stream xong toàn bộ câu
        trả lời (không chặn chữ chảy). Nếu critic báo LỖI → chỉ yield thêm sự kiện
        "review" cảnh báo ở cuối, KHÔNG viết lại giữa chừng stream. CRITICS rỗng
        (đang tắt trong .env) → bỏ qua bước phản biện.
        """
        t_bat_dau = time.perf_counter()  # [PERF] chỉ đo + in ra terminal, không đổi logic
        chunks, de_bai, do_tg, bi_chan, cau_tim = self._tim_va_soan_de_bai(
            cau_hoi, filters, lich_su, user)

        # Van chống bịa lớp 1 GIỮ NGUYÊN: kho rỗng → trả lời thẳng, KHÔNG gọi model.
        # bi_chan_quyen đi NGẦM trong done — text hiển thị không đổi (không lộ tài liệu)
        if not chunks:
            yield {"type": "token", "data": KHONG_CO_TAI_LIEU}
            yield {"type": "done", "data": {"critic_count": len(self.critics),
                                            "bi_chan_quyen": bi_chan}}
            self._in_perf(do_tg, None, None, time.perf_counter() - t_bat_dau)
            return

        # Nguồn đẩy TRƯỚC để frontend hiện ngay trong lúc chờ chữ
        yield {"type": "sources", "data": self._gom_nguon(chunks)}

        # Van chống bịa lớp 2 = SYSTEM_WRITER (chỉ dùng tài liệu, không nêu → nói thẳng)
        cac_mau = []
        t_goi_writer = time.perf_counter()
        ttft = None  # thời gian tới token đầu tiên — số quan trọng nhất với người dùng
        for mau in self.writer.generate_stream(SYSTEM_WRITER, de_bai):
            if ttft is None:
                ttft = time.perf_counter() - t_goi_writer
            cac_mau.append(mau)
            yield {"type": "token", "data": mau}
        t_writer = time.perf_counter() - t_goi_writer
        answer = "".join(cac_mau)

        if self.critics:
            reviews = [
                critic.generate(SYSTEM_CRITIC,
                                f"{de_bai}\n\nCâu trả lời cần kiểm tra:\n{answer}")
                for critic in self.critics
            ]
            loi = [r for r in reviews
                   if "LỖI" in (r.strip().splitlines() or [""])[0].upper()]
            if loi:
                yield {"type": "review",
                       "data": "Phản biện phát hiện vấn đề trong câu trả lời:\n"
                               + "\n\n".join(loi)}
        # Ý 3: gợi ý sinh NGẦM SAU khi chữ đã chảy hết (+critic) — không chặn TTFT;
        # người dùng đang đọc câu trả lời, gợi ý đến trễ 1-2s là chấp nhận được
        goi_y = self.goi_y_cau_hoi(cau_hoi, chunks)
        if goi_y:
            yield {"type": "goi_y", "data": goi_y}
        # 08/08: box gợi ý "🧭 góc nhìn khác" — CÙNG CHỖ, không chặn TTFT. Chỉ 1 lượt tìm rẻ
        # (không gọi model) để biết tầng "ngoài" có gì đủ liên quan không; bấm mới tốn model.
        # 05/08: truyền SẴN cau_tim đã tính ở trên — khỏi viết lại câu hỏi LẦN THỨ HAI cho
        # cùng một lượt (mỗi lần viết lại tốn 1 lời gọi model, đắt hơn hẳn phần còn lại của hàm này).
        nguon_khac = self.goi_y_goc_nhin_khac(cau_hoi, lich_su, user, cau_tim=cau_tim)
        if nguon_khac:
            yield {"type": "nguon_khac", "data": nguon_khac}
        yield {"type": "done", "data": {"critic_count": len(self.critics),
                                        "bi_chan_quyen": bi_chan}}
        self._in_perf(do_tg, ttft, t_writer, time.perf_counter() - t_bat_dau)

    @staticmethod
    def _in_perf(do_tg: dict, ttft, t_writer, tong: float) -> None:
        """In số đo [PERF] ra terminal server — KHÔNG gửi ra frontend."""
        if do_tg.get("viet_lai_cau_hoi"):
            nhan_viet_lai = "CÓ (câu ngắn/phụ thuộc ngữ cảnh — gọi model viết lại độc lập)"
        elif do_tg.get("ghep_truy_van"):
            nhan_viet_lai = "không (câu tự đủ nghĩa — ghép chuỗi ~0s, không gọi model)"
        else:
            nhan_viet_lai = "bỏ qua (không có lịch sử)"
        print(f"[PERF] viết lại câu hỏi: {nhan_viet_lai}")
        print(f"[PERF] embedding + tìm Qdrant (đo gộp quanh search): {do_tg.get('tim', 0):.2f}s")
        if ttft is not None:
            print(f"[PERF] TTFT (tới token đầu tiên của writer): {ttft:.2f}s")
            print(f"[PERF] writer sinh xong toàn bộ: {t_writer:.2f}s")
        print(f"[PERF] TỔNG: {tong:.2f}s", flush=True)

    # ---- diễn giải kết quả chẩn đoán số liệu (luật đã khớp do diagnosis_engine đưa sang) ----
    def dien_giai_chan_doan(self, ket_qua: dict, user: dict | None = None,
                            loai_kenh_ctx: str = "") -> dict:
        matched = ket_qua["matched"]
        if not matched:
            return {"answer": "", "sources": [],
                    "critic_count": len(self.critics), "reviews": [], "rewritten": False}

        # Tra kho playbook/tài liệu liên quan tới các nguyên nhân đã khớp (lọc quyền theo user).
        # CHỈ tầng noi_bo (07/08 — cùng lỗ hổng đã vá ở _tim_va_soan_de_bai): playbook "đã đúc
        # kết" nghĩa là CỦA CÔNG TY; không để một video/bài viết nguồn ngoài lẫn vào đây mà
        # không ghi rõ của ai — muốn tham khảo góc nhìn ngoài thì qua đường /hoi-dap/stream-da-chieu.
        query = " ; ".join(r["nguyen_nhan"] for r in matched)
        chunks = self.rag.search(query, {"effective_status": "Còn hiệu lực",
                                         "tang_nguon": "noi_bo"}, user=user)

        luat_txt = "\n".join(
            f"- [{r['ma_luat']}] Tầng {r['tang_pheu']}: {r['nguyen_nhan']} "
            f"→ Cách sửa: {r['cach_sua']} (độ tin cậy: {r['do_tin_cay']})"
            for r in matched
        )
        so_lieu = ", ".join(f"{k}={v}" for k, v in ket_qua["metrics"].items())
        # 08/08 (§12.1): khi chẩn đoán TỪNG VIDEO, baseline mỗi biến có thể là nhóm độ dài
        # riêng (không phải toàn kênh) — nói rõ để diễn giải không mập mờ "so với kênh".
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
            f"Tài liệu/playbook liên quan trong kho:\n{self._boi_canh(chunks) or '(không có)'}"
        )
        answer, reviews, rewritten = self._sinh_va_phan_bien(SYSTEM_DIEN_GIAI, de_bai)

        return {"answer": answer, "sources": self._gom_nguon(chunks),
                "critic_count": len(self.critics), "reviews": reviews,
                "rewritten": rewritten}

    def dien_giai_muc_kenh(self, muc: dict, boi_canh_khac: str, user: dict | None = None,
                           loai_kenh_ctx: str = "") -> dict | None:
        """Tầng 2 — diễn giải 1 MỤC báo cáo kênh có NEO bối cảnh các mục khác. CHỈ gọi cho mục
        'co_ket_qua'; mục chưa đủ/chưa có số liệu → None (không có số thì diễn giải là bịa).
        de_bai gồm: (1) số liệu THÔ của chính mục (Python đã tính), (2) tóm tắt số các mục KHÁC,
        (3) loai_kenh_ctx (nếu có) để đọc số theo bối cảnh loại kênh — KHÔNG bịa/đảo chiều."""
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
        answer, reviews, rewritten = self._sinh_va_phan_bien(SYSTEM_DIEN_GIAI_MUC, de_bai)
        return {"answer": answer, "critic_count": len(self.critics), "reviews": reviews,
                "rewritten": rewritten}
