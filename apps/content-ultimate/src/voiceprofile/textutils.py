"""Tien xu ly van ban: tach cau, tach tu. Khong phu thuoc thu vien ngoai (MVP).

Ghi chu: day la tokenizer xap xi bang regex, du cho tieng Anh. Theo Muc 6 cua
brief, ban full nen thay bang spaCy (EN) / underthesea hoac pyvi (VI) de tach
cau/tu chinh xac hon, dac biet voi tieng Viet.
"""
from __future__ import annotations

import re

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ỹ0-9\"'])")
_WORD_RE = re.compile(r"[A-Za-zÀ-Ỹà-ỹ]+(?:'[A-Za-z]+)?")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts = _SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def syllable_estimate(word: str) -> int:
    """Uoc luong so am tiet (heuristic nguyen am lien tiep) — dung cho readability."""
    word = word.lower()
    groups = re.findall(r"[aeiouyàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1:
        n -= 1
    return max(1, n)
