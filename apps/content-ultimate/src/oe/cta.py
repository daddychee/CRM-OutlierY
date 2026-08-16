"""Sinh 1 câu CTA bám nội dung một chương (LLM). Gọi từ /oe/api/cta khi user bấm
'✨ Sinh CTA từ nội dung chapter' trong dropdown CTA của board.

Ràng buộc (từ luật content YouTube của user): TIẾNG ANH; đúng MỘT lời kêu gọi; advertiser-
friendly; KHÔNG câu 'hết video'; KHÔNG in hoa cả câu; chọn loại hợp vị trí (giữa → retention/
comment; cuối → subscribe/watch-next).
"""
from __future__ import annotations

from .llm import LLM, extract_json

SYSTEM = (
    "Bạn viết MỘT câu CTA (call-to-action) cho một chương video YouTube. Yêu cầu: TIẾNG ANH; "
    "tự nhiên, GẮN với nội dung chương; đúng MỘT lời kêu gọi (không nhồi like+sub+comment); "
    "advertiser-friendly; KHÔNG câu kiểu 'that's all/thanks for watching/see you next time'; "
    "KHÔNG viết IN HOA cả câu. Chọn loại theo vị trí: giữa video → retention hoặc comment; "
    "cuối video → subscribe hoặc watch-next. Chỉ trả JSON."
)


def generate_cta(llm: LLM, brief: str, angle: str = "", position: str = "giữa") -> str:
    pos = {"đầu": "đầu video", "cuối": "cuối video"}.get(position, "giữa video")
    user = (f"Nội dung chương:\nBrief: {brief.strip()}\n"
            + (f"Angle (điểm nhấn): {angle.strip()}\n" if angle.strip() else "")
            + f"Vị trí trong video: {pos}.\n\n"
            'Viết 1 CTA gắn với nội dung này. Trả JSON: {"cta":"<một câu tiếng Anh>"}.')
    d = extract_json(llm.complete(SYSTEM, user, max_tokens=200, temperature=0.6))
    return str(d.get("cta", "")).strip()
