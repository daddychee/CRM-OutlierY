"""Lap rap profile.json theo schema Muc 7 cua BUILD-BRIEF.

Hai che do:
- self_profile (mac dinh, KHONG can baseline): giu dac trung on dinh noi tai tac gia,
  cum tu tai xuat qua nhieu van ban, va reproduction_targets = target +-1 SD vung
  tac gia (tieu chi nghiem thu Muc 9 brief).
- contrast (khi co baseline): tuong phan z-score + n-gram log-likelihood nhu cu.
"""
from __future__ import annotations

import random

from .corpus import Corpus
from .quant import (
    build_quant_features,
    build_self_features,
    extract_distinctive_ngrams,
    extract_recurring_ngrams,
    per_work_feature_values,
    select_exemplars,
)
from .validate import chunk_by_words

# Self-profile do on dinh tren cac DOAN ~CHUNK_WORDS tu (khong theo so file): mot
# quyen sach day (1 file, >4.000 tu) van tu cat ra du nhieu diem de do — user khong
# can chia nho tay. Duoi MIN_STABLE_UNITS doan la corpus that su ngan (canh bao that).
CHUNK_WORDS = 4000
MIN_STABLE_UNITS = 5


def _split_units(units: list[str], heldout_ratio: float = 0.2, seed: int = 42) -> tuple[list[str], list[str]]:
    """Chia cac doan do-on-dinh thanh train/held-out (xac dinh, tai lap) de kiem chung mu."""
    if len(units) < 2:
        return list(units), []
    rng = random.Random(seed)
    idx = list(range(len(units)))
    rng.shuffle(idx)
    n_ho = max(1, round(len(units) * heldout_ratio))
    ho = set(idx[:n_ho])
    train = [u for i, u in enumerate(units) if i not in ho]
    heldout = [u for i, u in enumerate(units) if i in ho]
    return train, heldout


def build_profile(
    author: str,
    source_language: str,
    output_language: str,
    author_corpus: Corpus,
    baseline_corpus: Corpus | None = None,
    z_keep_threshold: float = 1.0,
    stability_cv: float = 0.30,
) -> dict:
    if baseline_corpus is not None:
        mode = "contrast"
        features = build_quant_features(
            author_train=author_corpus.train,
            author_heldout=author_corpus.heldout,
            baseline_texts=baseline_corpus.train,
            z_keep_threshold=z_keep_threshold,
        )
        ngrams = extract_distinctive_ngrams(author_corpus.train, baseline_corpus.train)
        target_texts = author_corpus.works
    else:
        mode = "self_profile"
        # Cat corpus thanh doan ~CHUNK_WORDS tu. Chi doi sang do-theo-doan khi cat ra
        # NHIEU doan hon so file (vd 1 sach day) — luc do do theo file cho 1 diem/1 sach,
        # khong tinh duoc spread. Corpus von nhieu file (hoac qua ngan de cat) giu nguyen
        # cach chia theo file nhu cu.
        chunks = chunk_by_words(author_corpus.works, CHUNK_WORDS)
        if len(chunks) > author_corpus.n_works:
            target_texts = chunks
            train_units, heldout_units = _split_units(chunks)
        else:
            target_texts = author_corpus.works
            train_units, heldout_units = author_corpus.train, author_corpus.heldout
        features = build_self_features(
            author_train=train_units,
            author_heldout=heldout_units,
            stability_cv=stability_cv,
        )
        ngrams = extract_recurring_ngrams(target_texts)

    kept = [f for f in features if f.keep]
    exemplars = select_exemplars(author_corpus.works, kept)

    # Phuong an tai tao: moi dac trung giu lai la mot target do duoc, kem dung sai
    # +-1 SD tinh tren cac don vi do (doan ~4k tu khi self-profile 1 sach day, hoac
    # tung van ban) — Python do, khong uoc luong.
    spreads = per_work_feature_values(target_texts)
    import statistics
    reproduction_targets = {}
    for f in kept:
        vals = spreads.get(f.name, [])
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        reproduction_targets[f.name] = {
            "target": round(f.value, 4),
            "sd": round(sd, 4),
            "range": [round(f.value - sd, 4), round(f.value + sd, 4)],
        }

    return {
        "author": author,
        "source_language": source_language,
        "output_language": output_language,
        "profile_mode": mode,
        "corpus_stats": {
            "n_works": author_corpus.n_works,
            "n_tokens": author_corpus.n_tokens,
            "n_stability_units": len(target_texts),  # so don vi thuc su dung de do on dinh
        },
        "quant_features": [f.to_dict() for f in features],
        "distinctive_ngrams": [n.to_dict() for n in ngrams],
        "reproduction_targets": reproduction_targets,
        "signature_moves": [],  # duoc dien sau boi lenh `rhetoric` (Module 3 + 3b)
        "language_neutral_targets": {},  # Module 4 - chua co
        "exemplars": exemplars,
    }
