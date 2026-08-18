"""Brief kịch bản — nén MỘT lần, dùng chung cho cả 3 trụ cột (tiết kiệm token).

Trước: mỗi run gửi kịch bản thô 3 lần (tags 2.000 + titles 3.000 + describe 3.000 ký tự)
→ ~2.000 token input lặp lại vô ích, và kịch bản dài bị cắt cụt nên LLM chỉ thấy phần đầu.

Giờ: 1 call nén thành brief cô đọng (temperature thấp → llm.py tự cache trên đĩa, chạy lại =
0 token) rồi 3 stage dùng chung. Riêng Description được kèm ĐOẠN MỞ ĐẦU nguyên văn vì hook/summary
cần giọng văn thật của kịch bản, brief không thay thế được.
"""
from __future__ import annotations

import json

from . import llm

OPENING_CHARS = 900          # đoạn mở đầu nguyên văn cấp cho Description (giữ chất văn)
SAMPLE_BUDGET = 4000         # ngân sách ký tự đưa vào call nén
# Kịch bản ngắn hơn ngưỡng này: KHÔNG nén — gửi thẳng cho từng stage còn rẻ hơn (và không mất
# chi tiết). Nén chỉ có lãi khi kịch bản đủ dài để việc cắt cụt gây mất nội dung.
MIN_CHARS = 2500

_SYS = (
    "Bạn nén kịch bản video thành BRIEF cô đọng để các bước SEO sau dùng lại (không cần đọc lại "
    "kịch bản gốc). Bám sát nội dung, KHÔNG bịa chi tiết không có trong kịch bản. "
    + llm.OUTPUT_LANG_RULE +
    " Trả JSON: {\"topic\":<chủ đề chính, 1 câu>,"
    "\"entities\":[<tên riêng/thuật ngữ quan trọng, tối đa 10>],"
    "\"beats\":[<diễn biến chính theo thứ tự, mỗi beat 1 câu ngắn, tối đa 8>],"
    "\"desires\":[<nhu cầu/cảm xúc THẬT mà video chạm tới, tối đa 4>],"
    "\"keywords\":[<cụm từ người xem có thể search, tối đa 10>],"
    "\"promise\":<lời hứa video giao cho người xem, 1 câu>}."
)


def sample(text: str, budget: int = SAMPLE_BUDGET) -> str:
    """Kịch bản dài → lấy ĐẦU + GIỮA + CUỐI thay vì cắt cụt.

    Cùng ngân sách ký tự nhưng phủ được cả video (cắt prefix phẳng làm LLM không thấy
    phần kết — nơi thường nằm payoff/CTA).
    """
    t = (text or "").strip()
    if len(t) <= budget:
        return t
    k = budget // 3
    mid = len(t) // 2
    return t[:k] + "\n[…]\n" + t[mid - k // 2: mid + k // 2] + "\n[…]\n" + t[-k:]


def opening(script: str) -> str:
    """Đoạn mở đầu nguyên văn — chỉ Description dùng (hook/summary cần giọng gốc)."""
    return (script or "").strip()[:OPENING_CHARS]


def build(script: str) -> dict:
    """Kịch bản → brief. Rỗng hoặc ngắn (< MIN_CHARS) thì trả {} — KHÔNG tốn call nén."""
    s = (script or "").strip()
    if len(s) < MIN_CHARS:
        return {}
    out = llm.call_json(_SYS, json.dumps({"script": sample(s)}, ensure_ascii=False),
                        max_tokens=900, temperature=0.2)     # temp thấp → được cache
    return out if isinstance(out, dict) else {}


def payload(brief: dict, script: str = "") -> dict:
    """Nội dung gửi cho stage sau: ưu tiên brief; không có brief thì gửi kịch bản (ngắn → nguyên văn)."""
    if brief:
        return {"content_brief": brief}
    return {"script": sample(script, MIN_CHARS)} if script else {}


if __name__ == "__main__":                                   # self-test offline
    long_script = ("MO DAU " * 200) + ("GIUA " * 200) + ("KET THUC " * 200)
    s = sample(long_script, 900)
    assert len(s) <= 960, len(s)                             # ~budget (cộng 2 dấu […])
    assert "MO DAU" in s and "GIUA" in s and "KET THUC" in s, s   # phủ đủ đầu/giữa/cuối
    assert sample("ngắn", 900) == "ngắn"
    assert opening(long_script).startswith("MO DAU") and len(opening(long_script)) == OPENING_CHARS

    n_calls = []
    llm.set_hook(lambda sy, u: (n_calls.append(1),
                                '{"topic":"Sgr A*","entities":["Sagittarius A*"],"beats":["b1"],'
                                '"desires":["dread"],"keywords":["black hole"],"promise":"p"}')[1])
    b = build("x" * 5000)
    assert b["topic"] == "Sgr A*" and b["keywords"] == ["black hole"], b
    assert build("") == {} and build("kịch bản ngắn") == {}   # rỗng/ngắn → KHÔNG tốn call nén
    assert len(n_calls) == 1, n_calls
    llm.set_hook(None)
    assert payload(b) == {"content_brief": b}
    assert payload({}, "kịch bản ngắn") == {"script": "kịch bản ngắn"}   # ngắn → gửi nguyên văn
    assert payload({}, "") == {}
    print("digest.py self-test OK - sample dau/giua/cuoi, bo qua khi kich ban ngan, fallback nguyen van")
