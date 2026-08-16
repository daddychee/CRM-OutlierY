"""Lam sach va cat doan corpus tac gia cho viec dung dataset fine-tune.

Van ban OCR (vd Cosmos) lan nhieu rac: so trang, tieu de chuong, chu thich hinh,
bang so lieu, cong thuc toan, epigraph. Module nay cat theo DOAN (block ngan cach
boi dong trong), noi cac dong bi xuong hang cung, roi cham diem "do giong van xuoi"
de loai rac.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .quant import FUNCTION_WORDS
from .textutils import split_sentences, tokenize_words

# Mau dong rac thuong gap (header/footer/caption)
_JUNK_LINE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                       # dong chi co so (so trang)
    re.compile(r"^\s*[ivxlcdm]+\s*[-–]\s*\w", re.I),  # "xii - Introduction"
    re.compile(r"^\s*(source|painting by|photo|figure|plate|frontispiece)\b", re.I),
    re.compile(r"^\s*chapter\s+[ivxlcdm0-9]+\s*$", re.I),
    re.compile(r"^\s*\(?\s*(see\s+)?(figure|fig\.|plate|p\.|pp\.)\s", re.I),
    re.compile(r"^\s*[A-Z][A-Z\s]{6,}\s*$"),          # dong TOAN CHU HOA (tieu de)
]


@dataclass
class Passage:
    text: str
    n_words: int
    n_sentences: int


def _is_junk_line(line: str) -> bool:
    return any(p.match(line) for p in _JUNK_LINE_PATTERNS)


def _split_blocks(raw: str) -> list[str]:
    """Cat thanh block theo dong trong; trong moi block noi cac dong xuong-hang-cung."""
    blocks = re.split(r"\n\s*\n", raw)
    out = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines()]
        lines = [ln for ln in lines if ln and not _is_junk_line(ln)]
        if not lines:
            continue
        out.append(re.sub(r"\s+", " ", " ".join(lines)).strip())
    return out


def _prose_score(text: str) -> dict[str, float]:
    words = tokenize_words(text)
    n_words = len(words) or 1
    func_ratio = sum(1 for w in words if w.lower() in FUNCTION_WORDS) / n_words
    digit_chars = sum(1 for c in text if c.isdigit())
    digit_ratio = digit_chars / (len(text) or 1)
    sentences = split_sentences(text)
    end_punct = text.count(".") + text.count("!") + text.count("?")
    return {
        "n_words": n_words,
        "func_ratio": func_ratio,
        "digit_ratio": digit_ratio,
        "n_sentences": len(sentences),
        "end_punct": end_punct,
    }


def is_prose(text: str, min_words: int = 20, min_func_ratio: float = 0.25,
             max_digit_ratio: float = 0.06) -> bool:
    """Heuristic: van xuoi that co nhieu hu tu, it chu so, co dau ket cau."""
    s = _prose_score(text)
    if s["n_words"] < min_words:
        return False
    if s["func_ratio"] < min_func_ratio:   # bang/danh sach/cong thuc -> hu tu thap
        return False
    if s["digit_ratio"] > max_digit_ratio:  # bang so lieu -> chu so cao
        return False
    if s["end_punct"] == 0:
        return False
    return True


def clean_and_segment(
    texts: list[str],
    min_words: int = 60,
    max_words: int = 350,
    keep_block_min_words: int = 20,
) -> list[Passage]:
    """Lam sach + cat thanh cac doan (Passage) co do dai hop ly de lam mau fine-tune.

    Block van xuoi ngan duoc gop voi block ke tiep cho du dai; block qua dai cat
    theo ranh gioi cau.
    """
    passages: list[Passage] = []
    for raw in texts:
        blocks = [b for b in _split_blocks(raw) if is_prose(b, min_words=keep_block_min_words)]
        buf: list[str] = []
        buf_words = 0
        for block in blocks:
            bw = len(tokenize_words(block))
            buf.append(block)
            buf_words += bw
            if buf_words >= min_words:
                merged = " ".join(buf)
                passages.extend(_split_long(merged, max_words, min_words))
                buf, buf_words = [], 0
        if buf and buf_words >= min_words // 2:
            passages.extend(_split_long(" ".join(buf), max_words, min_words))
    return passages


def _split_long(text: str, max_words: int, min_words: int) -> list[Passage]:
    sentences = split_sentences(text)
    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_w = 0
    for s in sentences:
        sw = len(tokenize_words(s))
        if cur_w + sw > max_words and cur:
            chunks.append(cur)
            cur, cur_w = [], 0
        cur.append(s)
        cur_w += sw
    if cur:
        chunks.append(cur)
    out = []
    for ch in chunks:
        joined = " ".join(ch)
        wc = len(tokenize_words(joined))
        if wc >= min_words // 2:
            out.append(Passage(text=joined, n_words=wc, n_sentences=len(ch)))
    return out
