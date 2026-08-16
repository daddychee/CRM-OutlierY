"""Module 3 (Rhetoric Extractor) + 3b (Evidence Grounder) — xem Muc 5 BUILD-BRIEF.

Phan vai (Muc 4 brief): LLM lo phan HIEU — de xuat signature moves tu van ban that;
Python lo phan DEM — kiem chung tung trich dan LLM dua ra co that trong corpus.
Move khong du >= min_evidence trich dan xac minh duoc se bi loai (nguyen tac
"kiem chung, khong tin"): LLM co the bia trich dan nghe rat that.
"""
from __future__ import annotations

import re
from typing import Callable

from .clonekit import select_diverse_exemplars

# Schema JSON cho structured output cua LLM (Module 3).
# additionalProperties=False + required day du de output luon parse duoc.
RHETORIC_SCHEMA = {
    "type": "object",
    "properties": {
        "moves": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "move": {"type": "string"},
                    "type": {"type": "string", "enum": ["signature", "common"]},
                    "transferable": {"type": "boolean"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["move", "type", "transferable", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["moves"],
    "additionalProperties": False,
}

# Trich dan qua ngan khop corpus mot cach tam thuong -> khong tinh la chung cu.
_MIN_QUOTE_SQUASH_CHARS = 20


def build_rhetoric_prompt(passages: list[str], author: str, n_moves: int, min_evidence: int) -> str:
    blocks = "\n\n".join(f"[PASSAGE {i}]\n{p}" for i, p in enumerate(passages, 1))
    return (
        f"You are analyzing the prose style of {author}. Below are {len(passages)} "
        "verbatim passages from their work.\n\n"
        f"{blocks}\n\n"
        f"Identify up to {n_moves} rhetorical \"signature moves\" — recurring, "
        "distinctive techniques of structure, rhythm, imagery, or stance (not generic "
        "good-writing advice). For each move:\n"
        f"- Cite at least {min_evidence} pieces of evidence, each a VERBATIM quote "
        "copied exactly from the passages above (10-40 words). Do not paraphrase, "
        "do not invent, do not stitch fragments together — every quote will be "
        "checked mechanically against the source text and fabricated quotes "
        "disqualify the move.\n"
        "- Prefer evidence drawn from different passages.\n"
        "- Mark type: \"signature\" if distinctive of this author, \"common\" if merely "
        "competent prose technique.\n"
        "- Mark transferable: whether the move survives translation to another "
        "language (structural/stance moves usually do; sound-based wordplay does not)."
    )


def sample_passages(texts: list[str], n: int = 12, min_words: int = 80, max_words: int = 220) -> list[str]:
    """Chon doan dua vao LLM: tai dung bo chon exemplar da co (sach, da dang qua chuong)."""
    return select_diverse_exemplars(texts, n=n, min_words=min_words, max_words=max_words)


def propose_moves(
    texts: list[str],
    author: str,
    llm_json: Callable[[str, dict], dict],
    n_passages: int = 12,
    n_moves: int = 8,
    min_evidence: int = 3,
) -> list[dict]:
    """Module 3: LLM de xuat moves (CHUA kiem chung — phai qua ground_moves truoc khi dung)."""
    passages = sample_passages(texts, n=n_passages)
    if not passages:
        raise ValueError("Khong trich duoc doan van xuoi nao tu corpus de phan tich")
    prompt = build_rhetoric_prompt(passages, author, n_moves=n_moves, min_evidence=min_evidence)
    data = llm_json(prompt, RHETORIC_SCHEMA)
    moves = data.get("moves", [])
    if not isinstance(moves, list):
        raise ValueError(f"LLM tra ve 'moves' khong phai list: {type(moves).__name__}")
    return moves


def _squash(text: str) -> str:
    """Chuan hoa de doi chieu: thuong hoa + bo moi ky tu khong phai chu/so.

    Chong lech vo hai giua trich dan va corpus OCR: khac dau cau, xuong dong,
    ngat tu bang dau gach (vd "oblate¬ ness"), khoang trang thua.
    """
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def ground_moves(moves: list[dict], corpus_texts: list[str], min_evidence: int = 3) -> list[dict]:
    """Module 3b: giu lai move co >= min_evidence trich dan XAC MINH DUOC trong corpus.

    occurrences = so trich dan da xac minh (Python dem), khong phai con so LLM khai.
    """
    corpus_squashed = [_squash(t) for t in corpus_texts]
    grounded = []
    for m in moves:
        verified: list[str] = []
        seen: set[str] = set()
        for quote in m.get("evidence", []):
            key = _squash(quote)
            if len(key) < _MIN_QUOTE_SQUASH_CHARS or key in seen:
                continue
            seen.add(key)
            if any(key in cs for cs in corpus_squashed):
                verified.append(quote)
        if len(verified) >= min_evidence:
            grounded.append({
                "move": str(m.get("move", "")).strip(),
                "evidence": verified,
                "occurrences": len(verified),
                "type": m.get("type", "signature"),
                "transferable": bool(m.get("transferable", True)),
            })
    return grounded
