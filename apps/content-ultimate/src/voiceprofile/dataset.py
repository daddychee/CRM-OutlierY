"""Dung dataset JSONL de fine-tune LLM hoc giong van tac gia.

Hai che do:
- continuation: prompt = vai cau dau cua doan, completion = phan con lai (offline, khong can LLM).
- instruction:  prompt = lenh do LLM tom tat tu doan, completion = ca doan goc (can callback LLM).

Dinh dang ghi ra: chat messages (system/user/assistant) — chuan cho fine-tune chat model.
Kem bao cao trung lap de tranh model hoc vet (nhac lai nguyen van).
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from .clean import Passage, clean_and_segment
from .textutils import split_sentences, tokenize_words

# System prompt mac dinh TRUNG TINH (tool universal): khong mo ta san dac diem giong
# cua mot tac gia/truong phai cu the — model hoc giong tu chinh cac completion.
DEFAULT_SYSTEM = (
    "You write in the distinctive prose voice of {author}. Match that voice in "
    "rhythm, imagery, and stance."
)


@dataclass
class Pair:
    system: str
    user: str
    assistant: str

    def to_chat(self) -> dict:
        return {"messages": [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user},
            {"role": "assistant", "content": self.assistant},
        ]}


def build_continuation_pairs(
    passages: list[Passage], author: str, seed_sentences: int = 2, system: str | None = None
) -> list[Pair]:
    sys = (system or DEFAULT_SYSTEM).format(author=author)
    pairs = []
    for p in passages:
        sents = split_sentences(p.text)
        if len(sents) <= seed_sentences:
            continue
        seed = " ".join(sents[:seed_sentences])
        rest = " ".join(sents[seed_sentences:])
        if len(tokenize_words(rest)) < 15:
            continue
        user = f"Continue this passage in the same voice:\n\n{seed}"
        pairs.append(Pair(system=sys, user=user, assistant=rest))
    return pairs


def build_instruction_pairs(
    passages: list[Passage],
    author: str,
    llm_summarize: Callable[[str], str],
    system: str | None = None,
) -> list[Pair]:
    """llm_summarize(passage_text) -> mot cau lenh ngan (vd 'Viet ve quy mo vu tru...')."""
    sys = (system or DEFAULT_SYSTEM).format(author=author)
    pairs = []
    for p in passages:
        instruction = llm_summarize(p.text).strip()
        if not instruction:
            continue
        pairs.append(Pair(system=sys, user=instruction, assistant=p.text))
    return pairs


def dedup_report(pairs: list[Pair], ngram_n: int = 5) -> dict:
    """Bao cao trung lap: cap completion giong het, va 5-gram lap nhieu (nguy co hoc vet)."""
    completions = [p.assistant for p in pairs]
    exact_dups = len(completions) - len(set(completions))

    gram_counter: Counter = Counter()
    for c in completions:
        words = [w.lower() for w in tokenize_words(c)]
        for i in range(len(words) - ngram_n + 1):
            gram_counter[" ".join(words[i:i + ngram_n])] += 1
    repeated = sum(1 for g, n in gram_counter.items() if n >= 3)

    wc = [len(tokenize_words(p.assistant)) for p in pairs]
    return {
        "n_pairs": len(pairs),
        "exact_duplicate_completions": exact_dups,
        f"repeated_{ngram_n}grams_ge3": repeated,
        "completion_words_min": min(wc) if wc else 0,
        "completion_words_mean": round(sum(wc) / len(wc)) if wc else 0,
        "completion_words_max": max(wc) if wc else 0,
    }


def write_jsonl(pairs: list[Pair], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p.to_chat(), ensure_ascii=False) + "\n")


def build_dataset(
    texts: list[str],
    author: str,
    mode: str = "continuation",
    seed_sentences: int = 2,
    llm_summarize: Callable[[str], str] | None = None,
    min_words: int = 60,
    max_words: int = 350,
) -> tuple[list[Pair], dict]:
    passages = clean_and_segment(texts, min_words=min_words, max_words=max_words)
    if mode == "continuation":
        pairs = build_continuation_pairs(passages, author, seed_sentences=seed_sentences)
    elif mode == "instruction":
        if llm_summarize is None:
            raise ValueError("mode='instruction' can callback llm_summarize")
        pairs = build_instruction_pairs(passages, author, llm_summarize)
    else:
        raise ValueError(f"mode khong hop le: {mode}")
    return pairs, dedup_report(pairs)
