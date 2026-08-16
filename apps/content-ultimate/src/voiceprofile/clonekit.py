"""Clone-kit: file markdown dan-thang-vao-LLM de clone giong van bang prompt (few-shot).

Theo Muc 4 & 5 brief: linh hon nam o exemplar goc -> luon nhung exemplar that.
Chon doan mau tieu bieu, da dang qua cac chuong, do dai vua phai.
"""
from __future__ import annotations

import re

from .clean import Passage, clean_and_segment
from .textutils import tokenize_words

# Dau hieu chu thich anh / credit nhiep anh (van OCR lan vao, KHONG phai van xuoi tac gia)
_CAPTION_MARKERS = re.compile(
    r"\b(courtesy|photographed by|photograph|micrograph|observatory|"
    r"apollo|nasa|jpl|orbiter photo|scanning electron|frontispiece|"
    r"this chapter\)|caltech|institute of technology|"
    r"as seen by|as seen from|close-?up of|at top|at left|at right|"
    r"in the center|in center|upper left|upper right|lower left|lower right)\b",
    re.I,
)

# Chu thich anh thuong mo dau bang cum danh tu khong dong tu roi cham (nhan hinh)
_CAPTION_OPENER = re.compile(
    r"^[A-Z][\w\-]+(\s+[\w\-]+){0,4}\.\s+(at|in|the|this|these|photo|courtesy|note)\b",
    re.I,
)


def _looks_like_caption(text: str) -> bool:
    """Chu thich anh: co tu khoa credit/vi tri, hoac mo dau kieu nhan hinh, hoac dac don vi do."""
    if _CAPTION_MARKERS.search(text):
        return True
    if _CAPTION_OPENER.match(text.strip()):
        return True
    # mat do don vi do luong cao (km, meters, micrometers...) kieu chu thich ky thuat
    units = len(re.findall(r"\b(kilometers?|meters?|micrometers?|millimeters?|centimeters?|µm)\b", text, re.I))
    return units >= 3

# Voice mac dinh TRUNG TINH (tool universal, khong gan tac gia nao): linh hon nam o
# exemplar goc (Muc 4 brief) — mo ta giong cu the do nguoi dung/LLM cung cap qua
# tham so `voice` neu muon, KHONG hard-code san cho mot truong phai.
DEFAULT_VOICE = (
    "You write in the distinctive prose voice of {author}. The exemplar passages "
    "below are the ground truth for this voice. Study them closely:\n"
    "- How sentences breathe: their length, rhythm, and variation.\n"
    "- How images are built and what kinds of detail anchor them.\n"
    "- The stance toward the reader (distance, address, register).\n"
    "- How paragraphs open, escalate, and land.\n"
    "Match this voice in rhythm, imagery, and stance — do not copy its sentences."
)


def select_diverse_exemplars(
    texts: list[str],
    n: int = 5,
    min_words: int = 90,
    max_words: int = 230,
) -> list[str]:
    """Chon n doan mau hoan chinh, do dai dep, uu tien dan deu qua cac van ban (chuong)."""
    out: list[str] = []
    per_source: list[list[Passage]] = []
    for t in texts:
        good = [
            p for p in clean_and_segment([t], min_words=min_words, max_words=max_words)
            if min_words <= p.n_words <= max_words
            and p.text.rstrip().endswith((".", "!", "?", "\""))
            and not _looks_like_caption(p.text)
        ]
        # uu tien doan nhieu cau (giau nhip) va do dai gan giua khoang
        target = (min_words + max_words) / 2
        good.sort(key=lambda p: (-p.n_sentences, abs(p.n_words - target)))
        per_source.append(good)

    # round-robin: lay 1 doan tot nhat tu moi nguon, vong lai cho du n
    idx = 0
    while len(out) < n and any(idx < len(g) for g in per_source):
        for g in per_source:
            if idx < len(g):
                out.append(g[idx].text)
                if len(out) >= n:
                    break
        idx += 1
    return out


def build_clonekit_markdown(
    texts: list[str], author: str, n_exemplars: int = 5, voice: str | None = None
) -> str:
    voice_block = (voice or DEFAULT_VOICE).format(author=author)
    exemplars = select_diverse_exemplars(texts, n=n_exemplars)

    lines = [
        f"# Clone-kit giọng văn: {author}",
        "",
        "> Dán toàn bộ phần dưới vào Claude/ChatGPT, rồi thay `[CHỦ ĐỀ]` ở cuối.",
        "",
        "---",
        "",
        "## SYSTEM / Hướng dẫn giọng",
        "",
        voice_block,
        "",
        "## Đoạn mẫu (exemplars — học nhịp & cách dựng hình, KHÔNG sao chép câu chữ)",
        "",
    ]
    for i, ex in enumerate(exemplars, 1):
        lines += [f"**Mẫu {i}:**", "", f"> {ex}", ""]

    lines += [
        "## YÊU CẦU",
        "",
        "Viết một đoạn (hoặc kịch bản) về chủ đề sau, theo đúng giọng văn và nhịp "
        "trong các đoạn mẫu ở trên. Tuyệt đối không lặp lại nguyên câu nào trong các "
        "đoạn mẫu.",
        "",
        "**CHỦ ĐỀ:** `[CHỦ ĐỀ]`",
        "",
    ]
    return "\n".join(lines)
