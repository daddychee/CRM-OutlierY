"""Quant Engine (Python) — do dac trung phong cach, xac dinh, tai lap duoc.

Theo nguyen tac bat bien Muc 3 cua brief: moi con so o day do Python tinh,
KHONG bao gio de LLM "uoc luong" thay.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field

from .textutils import char_count, split_sentences, syllable_estimate, tokenize_words

# Hu tu tieng Anh thuong dung de do "tic" phong cach (lien tu, gioi tu, mao tu...)
FUNCTION_WORDS = {
    "the", "a", "an", "and", "but", "or", "so", "yet", "for", "nor",
    "of", "in", "on", "at", "by", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "to", "from", "up", "down", "as", "if", "because", "while", "although",
    "we", "our", "us", "i", "you", "it", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being",
}

PUNCT_CHARS = [",", ";", ":", "—", "-", "(", ")", "!", "?", "..."]

# Nguong cau cut / cau dai — GIU BANG deai.CAU_CUT_TU / CAU_DAI_TU va chon_neo.nhip
# de thuoc do (cham) va neo giong (viet) noi cung mot thu tieng.
CAU_CUT_TU = 8
CAU_DAI_TU = 35

# CHIEU NHIP (C2, 24/08) — luon co mat trong ho so, du cua on dinh co loai hay khong.
# Do that: A014 co sentence_len_mean keep=False vi cv cao qua 6 van ban, ma
# select_exemplars chi nhin tap keep=True => no chon doan mau bang hu tu va TTR,
# KHONG nhin nhip cau. Do la goc cua bang 22/08 (mau neo A013 33,3% cau dai trong
# khi van that 9,3%). cv cao o nhip khong phai nhieu: no la dac diem cua nguoi viet
# (luc dai luc ngan). Loai chieu nay di la vut mat dung thu quan trong nhat.
CHIEU_NHIP = ("sentence_len_mean", "sentence_len_stdev",
              "sentence_short_ratio", "sentence_long_ratio")


@dataclass
class QuantFeature:
    name: str
    value: float
    baseline: float | None = None
    zscore: float | None = None
    spread: float | None = None  # do lech chuan qua cac van ban tac gia (self-profile mode)
    stable_on_heldout: bool | None = None
    keep: bool = True
    do_duoc: bool = True         # co DU diem do de noi duoc gi ve do on dinh khong (C1)
    bat_buoc: bool = False       # chieu nhip: giu lai du cv cao (C2)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "baseline": round(self.baseline, 4) if self.baseline is not None else None,
            "zscore": round(self.zscore, 3) if self.zscore is not None else None,
            "spread": round(self.spread, 4) if self.spread is not None else None,
            "stable_on_heldout": self.stable_on_heldout,
            "keep": self.keep,
            "do_duoc": self.do_duoc,
            "bat_buoc": self.bat_buoc,
        }


@dataclass
class NgramStat:
    ngram: str
    loglik: float

    def to_dict(self) -> dict:
        return {"ngram": self.ngram, "loglik": round(self.loglik, 2)}


def _raw_features(text: str) -> dict[str, float]:
    """Tinh cac dac trung tho tu mot khoi van ban (khong so sanh baseline)."""
    sentences = split_sentences(text)
    words = tokenize_words(text)
    n_words = len(words) or 1
    n_sents = len(sentences) or 1
    lower_words = [w.lower() for w in words]

    sent_lens = [len(tokenize_words(s)) for s in sentences] or [0]
    func_word_freq = sum(1 for w in lower_words if w in FUNCTION_WORDS) / n_words

    n_chars = char_count(text) or 1
    punct_freq = {p: text.count(p) / n_words for p in PUNCT_CHARS}
    punct_total = sum(text.count(p) for p in PUNCT_CHARS) / n_words

    ttr = len(set(lower_words)) / n_words  # type-token ratio

    syllables = sum(syllable_estimate(w) for w in words)
    # Flesch Reading Ease (xap xi, tieng Anh): 206.835 - 1.015*(words/sent) - 84.6*(syll/words)
    flesch = 206.835 - 1.015 * (n_words / n_sents) - 84.6 * (syllables / n_words)

    # Proxy "do cu the danh tu": ty le tu viet hoa khong o dau cau (proper-noun-ish).
    # Phai loai tu dau MOI cau (khong chi dau van ban), neu khong tin hieu do-dai-cau
    # se tron vao proxy nay (cau cang ngan -> cang nhieu tu dau cau viet hoa).
    cap_count = 0
    for s in sentences:
        sw = tokenize_words(s)
        cap_count += sum(1 for w in sw[1:] if w[0].isupper())
    cap_proxy = cap_count / n_words

    n_s = len(sent_lens) or 1
    feats = {
        "sentence_len_mean": statistics.mean(sent_lens),
        "sentence_len_stdev": statistics.pstdev(sent_lens) if len(sent_lens) > 1 else 0.0,
        "sentence_short_ratio": sum(1 for d in sent_lens if d < CAU_CUT_TU) / n_s,
        "sentence_long_ratio": sum(1 for d in sent_lens if d > CAU_DAI_TU) / n_s,
        "function_word_freq": func_word_freq,
        "punct_freq_total": punct_total,
        "ttr": ttr,
        "flesch_reading_ease": flesch,
        "noun_specificity_proxy": cap_proxy,
        "avg_word_len_chars": n_chars / n_words,
    }
    for p, v in punct_freq.items():
        key = {",": "comma", ";": "semicolon", ":": "colon", "—": "em_dash", "-": "hyphen",
               "(": "paren", ")": "paren_close", "!": "exclaim", "?": "question", "...": "ellipsis"}[p]
        feats[f"punct_{key}_freq"] = v
    return feats


def compute_features(texts: list[str]) -> dict[str, float]:
    """Gop dac trung tho tren nhieu van ban (trung binh co trong so theo so tu)."""
    per_text = []
    weights = []
    for t in texts:
        per_text.append(_raw_features(t))
        weights.append(len(tokenize_words(t)) or 1)
    keys = per_text[0].keys()
    total_w = sum(weights)
    return {
        k: sum(f[k] * w for f, w in zip(per_text, weights)) / total_w
        for k in keys
    }


def zscore_against_baseline(
    author_value: float, baseline_texts: list[str], feature_name: str
) -> tuple[float, float]:
    """Tra ve (baseline_mean, zscore). Do lech chuan tu phan bo tung-van-ban cua baseline."""
    per_text_values = [_raw_features(t)[feature_name] for t in baseline_texts]
    if len(per_text_values) < 2:
        mean = per_text_values[0] if per_text_values else 0.0
        return mean, 0.0
    mean = statistics.mean(per_text_values)
    stdev = statistics.pstdev(per_text_values)
    z = (author_value - mean) / stdev if stdev > 0 else 0.0
    return mean, z


def cross_validate_stability(
    author_train: list[str], author_heldout: list[str], feature_name: str, z_threshold: float = 1.0
) -> bool | None:
    """Kiem tra dac trung co on dinh tren held-out khong (gia tri gan voi train, khong 'chap chon').

    Tra ve None khi khong co held-out — khong duoc bao cao True cho thu chua do
    (nguyen tac "do, khong cam").
    """
    if not author_heldout:
        return None
    train_val = compute_features(author_train)[feature_name]
    heldout_val = compute_features(author_heldout)[feature_name]
    all_vals = [_raw_features(t)[feature_name] for t in author_train]
    spread = statistics.pstdev(all_vals) if len(all_vals) > 1 else abs(train_val) * 0.2 or 1.0
    if spread == 0:
        spread = abs(train_val) * 0.2 or 1.0
    return abs(heldout_val - train_val) / spread <= z_threshold * 2


def build_quant_features(
    author_train: list[str],
    author_heldout: list[str],
    baseline_texts: list[str],
    z_keep_threshold: float = 1.0,
) -> list[QuantFeature]:
    """Pipeline day du: tinh dac trung tac gia, tuong phan baseline, giu cai lech ro ret,
    kiem tra on dinh tren held-out. Chi dac trung dat ca hai dieu kien moi `keep=True`.
    """
    author_vals = compute_features(author_train)
    features = []
    for name, value in author_vals.items():
        baseline_mean, z = zscore_against_baseline(value, baseline_texts, name)
        stable = cross_validate_stability(author_train, author_heldout, name)
        # stable=None (khong co held-out de do) khong loai dac trung; chi False moi loai.
        keep = abs(z) >= z_keep_threshold and stable is not False
        features.append(QuantFeature(
            name=name, value=value, baseline=baseline_mean, zscore=z,
            stable_on_heldout=stable, keep=keep, bat_buoc=name in CHIEU_NHIP,
        ))
    return features


def per_work_feature_values(texts: list[str]) -> dict[str, list[float]]:
    """Gia tri tung dac trung tren TUNG van ban — nen tang cho spread/tolerance band."""
    per_text = [_raw_features(t) for t in texts]
    return {k: [f[k] for f in per_text] for k in per_text[0]}


# Duoi nguong nay "spread = 0" khong phai on dinh ma la CHUA DO DUOC (C1).
MIN_DON_VI_DO = 3


def build_self_features(
    author_train: list[str],
    author_heldout: list[str],
    stability_cv: float = 0.30,
    min_units: int = MIN_DON_VI_DO,
) -> list[QuantFeature]:
    """Self-profile mode (KHONG can baseline): giu dac trung ON DINH noi tai tac gia.

    Thay the tuong phan baseline khi khong co corpus doi chung: mot dac trung dai
    dien cho tac gia neu no nhat quan qua cac van ban (he so bien thien
    cv = spread/|mean| <= stability_cv) va ben tren held-out. Target tai tao la
    "nam trong +-1 SD vung tac gia" (dung tieu chi nghiem thu Muc 9 brief).
    """
    values = per_work_feature_values(author_train)
    # MOT diem do khong tao ra phuong sai, va pstdev tra 0.0 — con so do khong co nghia
    # "khong bien thien", no co nghia "chua biet". Giu cach cu thi corpus cang mong cang
    # giu duoc nhieu dac trung (do that: A013 3.726 tu giu 17/17; A014 25.392 tu giu 7/17).
    du = len(author_train) >= min_units
    features = []
    for name, vals in values.items():
        mean = statistics.mean(vals)
        spread = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        cv = spread / abs(mean) if mean else float("inf")
        stable = cross_validate_stability(author_train, author_heldout, name)
        keep = du and cv <= stability_cv and stable is not False
        features.append(QuantFeature(
            name=name, value=mean, spread=spread if du else None,
            stable_on_heldout=stable, keep=keep, do_duoc=du,
            bat_buoc=name in CHIEU_NHIP,
        ))
    return features


@dataclass
class RecurringNgram:
    ngram: str
    count: int
    n_works: int  # xuat hien trong bao nhieu van ban

    def to_dict(self) -> dict:
        return {"ngram": self.ngram, "count": self.count, "n_works": self.n_works}


def extract_recurring_ngrams(
    author_texts: list[str], n: int = 2, top_k: int = 15, min_count: int = 5
) -> list[RecurringNgram]:
    """Cum tu tai xuat (self-profile mode): n-gram noi dung lap lai QUA NHIEU van ban.

    Khong co baseline de tinh log-likelihood, nen tin hieu "dac trung" la su tai
    xuat: cum phai xuat hien trong >= 1/2 so van ban (khong phai tic cua 1 chuong)
    va khong phai cum toan hu tu.
    """
    min_works = max(2, len(author_texts) // 2) if len(author_texts) > 1 else 1
    total_counts: Counter = Counter()
    work_presence: Counter = Counter()
    for t in author_texts:
        words = [w.lower() for w in tokenize_words(t)]
        grams_in_work = set()
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i:i + n])
            total_counts[gram] += 1
            grams_in_work.add(gram)
        for g in grams_in_work:
            work_presence[g] += 1

    results = []
    for gram, count in total_counts.items():
        if count < min_count or work_presence[gram] < min_works:
            continue
        if all(tok in FUNCTION_WORDS for tok in gram.split()):
            continue
        results.append(RecurringNgram(ngram=gram, count=count, n_works=work_presence[gram]))
    results.sort(key=lambda x: x.count, reverse=True)
    return results[:top_k]


def extract_distinctive_ngrams(
    author_texts: list[str], baseline_texts: list[str], n: int = 2, top_k: int = 15, min_count: int = 3
) -> list[NgramStat]:
    """N-gram dac trung theo log-likelihood ratio (Dunning) so voi baseline."""
    def ngram_counts(texts: list[str]) -> tuple[Counter, int]:
        counter = Counter()
        total = 0
        for t in texts:
            words = [w.lower() for w in tokenize_words(t)]
            for i in range(len(words) - n + 1):
                gram = " ".join(words[i:i + n])
                counter[gram] += 1
                total += 1
        return counter, total

    a_counts, a_total = ngram_counts(author_texts)
    b_counts, b_total = ngram_counts(baseline_texts)

    results = []
    for gram, a_count in a_counts.items():
        if a_count < min_count:
            continue
        # Bo cum toan hu tu (vd "of the", "on the") — khong mang tin hieu phong
        # cach huu ich cho signature moves, du co the lech thong ke.
        if all(tok in FUNCTION_WORDS for tok in gram.split()):
            continue
        b_count = b_counts.get(gram, 0)
        # G2 la doi xung (do do lech o CA HAI huong) — phai loc theo huong rieng,
        # chi giu cum co ty le o tac gia CAO HON o baseline, neu khong se lan ca
        # cum dac trung cua baseline (vi baseline nho, mot vai lan xuat hien da
        # tao ty le cao gia tao).
        a_rate = a_count / a_total if a_total else 0.0
        b_rate = b_count / b_total if b_total else 0.0
        if a_rate <= b_rate:
            continue
        ll = _log_likelihood_ratio(a_count, a_total, b_count, b_total)
        results.append(NgramStat(ngram=gram, loglik=ll))
    results.sort(key=lambda x: x.loglik, reverse=True)
    return results[:top_k]


def _log_likelihood_ratio(a: int, a_total: int, b: int, b_total: int) -> float:
    """Dunning's log-likelihood ratio cho 2x2 contingency (a vs rest-of-a) vs (b vs rest-of-b)."""
    a1, a2 = a, max(a_total - a, 0)
    b1, b2 = b, max(b_total - b, 0)
    e1 = (a1 + b1) * a_total / (a_total + b_total) if (a_total + b_total) else 0
    e2 = (a1 + b1) * b_total / (a_total + b_total) if (a_total + b_total) else 0
    ll = 0.0
    for observed, expected in [(a1, e1), (b1, e2)]:
        if observed > 0 and expected > 0:
            ll += observed * math.log(observed / expected)
    return 2 * ll


def select_exemplars(
    texts: list[str], kept_features: list[QuantFeature], top_k: int = 3, min_words: int = 25, max_words: int = 120
) -> list[str]:
    """Chon doan van tieu bieu nhat: cau/doan co dac trung gan nhat voi trung binh tac gia
    tren tap dac trung da giu lai (kept=True)."""
    if not kept_features:
        kept_features = []
    target = {f.name: f.value for f in kept_features}
    candidates = []
    for text in texts:
        for sent_window in _sliding_paragraphs(text, min_words, max_words):
            wc = len(tokenize_words(sent_window))
            if wc < min_words:
                continue
            feats = _raw_features(sent_window)
            # Chuan hoa moi chieu theo do lon cua target: cac feature co scale rat khac
            # nhau (flesch ~50 vs freq ~0.05); khong chuan hoa thi khoang cach bi mot
            # feature scale lon thong tri, cac feature con lai vo tac dung.
            dist = math.sqrt(sum(
                ((feats.get(k, 0) - v) / (abs(v) or 1.0)) ** 2 for k, v in target.items()
            )) if target else 0.0
            candidates.append((dist, sent_window))
    candidates.sort(key=lambda x: x[0])
    seen = set()
    out = []
    for _, snippet in candidates:
        key = snippet[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(snippet)
        if len(out) >= top_k:
            break
    return out


def _sliding_paragraphs(text: str, min_words: int, max_words: int) -> list[str]:
    """Cua so truot min_words..max_words TU. Cua so vuot max_words bi BO, khong phun ra.

    Bug da sua 2026-07-16: truoc day `out.append` chay TRUOC khi kiem max_words nen gioi
    han khong bao gio co hieu luc. Voi transcript YouTube khong dau cham, split_sentences
    tra ve DUNG MOT "cau" = ca file => cua so dau tien la nguyen cuc 14.799 ky tu (~2.500
    tu, gap 20 lan gioi han 120) va no duoc phun ra lam exemplar. LLM duoc xem cuc do va
    bao "day la giong tac gia" => viet 271-307 ky tu/cau trong khi tac gia that viet 78-92.
    Do la loi "cau van phang va qua dai" user bao.
    """
    sentences = split_sentences(text)
    out = []
    buf: list[str] = []
    buf_words = 0
    for s in sentences:
        buf.append(s)
        buf_words += len(tokenize_words(s))
        if buf_words < min_words:
            continue
        if buf_words <= max_words:
            out.append(" ".join(buf))
            buf, buf_words = buf[1:], buf_words - len(tokenize_words(buf[0])) if buf else 0
        else:
            # Vuot tran: KHONG phun. Truot bo cau dau roi thu lai; mot cau don da dai hon
            # max_words (vd transcript khong cham) thi khong the tao cua so hop le -> bo.
            while buf and buf_words > max_words:
                buf_words -= len(tokenize_words(buf[0]))
                buf = buf[1:]
    if buf and min_words // 2 <= buf_words <= max_words:
        out.append(" ".join(buf))
    return out
