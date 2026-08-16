"""Phân loại comment: câu hỏi / xin nội dung / trích thoại / nhắc timestamp. Thuần, test offline.

Con số đếm được là ƯỚC LƯỢNG DƯỚI (chỉ đếm cái match chắc) — trình bày đúng như vậy (A2).
"""
from __future__ import annotations

import re

_Q_WORDS = ("how", "why", "what", "when", "where", "who", "which", "is ", "are ", "do ",
            "does ", "did ", "can ", "could ", "would ", "will ", "should ")
# Câu hỏi TU TỪ / TỰ TRÀO (về trải nghiệm người xem, không phải nhu cầu nội dung) — loại khỏi
# questions/GAPS. Nhiều like nhất nhưng vô nghĩa với dàn ý (đo thực tế trên sóng bigbang).
_RHETORICAL = ("who else", "anyone else", "did anyone else", "am i the only", "is it just me",
               "who gets", "why did i", "why do i", "who's here", "whos here", "who is here",
               "why am i", "am i the", "anybody else", "does anyone else")
_REQ = ("make a video", "do a video", "can you cover", "please cover", "please do",
        "next video", "video about", "video on", "you should cover", "cover the",
        "do an episode", "make an episode")
_TS_RE = re.compile(r"\b\d{1,2}:\d{2}\b")


def is_rhetorical(text: str) -> bool:
    """Câu hỏi tu từ/tự trào về trải nghiệm người xem — không phải nhu cầu nội dung."""
    t = text.strip().lower()
    return any(p in t for p in _RHETORICAL)


def is_question(text: str) -> bool:
    t = text.strip().lower()
    if not t or is_rhetorical(t):
        return False
    if "?" in t:
        return True
    return any(t.startswith(w) for w in _Q_WORDS)


def is_request(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _REQ)


def has_timestamp(text: str) -> bool:
    return bool(_TS_RE.search(text))


def _norm_words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9\s]", " ", s.lower()).split()


def build_transcript_shingles(seg_texts: list[str], n: int = 8) -> set:
    """Tập n-gram từ (8 từ) của toàn transcript — để bắt comment trích nguyên văn."""
    words = []
    for t in seg_texts:
        words += _norm_words(t)
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def is_quote(text: str, shingles: set, n: int = 8) -> bool:
    """Comment trích thoại: có ≥1 cụm 8-từ trùng transcript."""
    w = _norm_words(text)
    if len(w) < n:
        return False
    return any(tuple(w[i:i + n]) in shingles for i in range(len(w) - n + 1))
