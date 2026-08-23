# -*- coding: utf-8 -*-
"""KHUON VAN: cach mo dau · cach chuyen doan · cach ket · tu dac trung (24/08).

Owner: "phan mo ta giong va cach dung van chua du chi tiet". Thieu that su khong phai
la chu, ma la NGUYEN LIEU: mo ta cu chi doc so nhip va so ngoi, trong khi thu nguoi
viet can biet de viet duoc theo giong la — tac gia nay MO BAI kieu gi, CHUYEN DOAN
bang gi, KET ra sao, hay dung nhung cum tu nao.

Bon thu do deu DO DUOC bang Python tren corpus that, khong can model:
  mo_dau      cau dau tien cua tung van ban (hoac tung chuong)
  chuyen_doan tu mo dau cua cac doan giua bai
  ket         cau cuoi cung cua tung van ban
  tu_dac_trung cum tu lap lai QUA NHIEU van ban, da bo hu tu va cum pho thong

VI SAO KHONG DUNG `distinctive_ngrams` san co: do that tren A014 no cho ra "one of",
"the world", "the most", "percent of" — cum pho thong cua moi van ban tieng Anh, khong
noi gi ve tac gia. O day loc bang hai cua: bo cum toan hu tu, va bo cum nam trong danh
sach pho thong.

Van: cau mau la TRICH NGUYEN VAN tu corpus (co test ghim), va duoi MIN_MAU van ban thi
khai du_mau=False — ba bai mo bang cau hoi moi goi la thoi quen, mot bai thi khong.
"""
from __future__ import annotations

import re
from collections import Counter

from .textutils import split_sentences, tokenize_words

MIN_MAU = 3               # duoi nguong nay: co mau nhung KHONG khai la khuon
SO_MAU_HIEN = 4           # so cau mau moi muc dua ra
TRAN_CAU = 240            # cau qua dai thi cat cho de doc

# Hu tu + cum pho thong: khong mang tin hieu tac gia (do that: distinctive_ngrams cu
# tra ve toan nhung cum nay).
HU_TU = {
    "the", "a", "an", "and", "but", "or", "so", "yet", "for", "nor", "of", "in", "on",
    "at", "by", "with", "about", "into", "through", "to", "from", "as", "if", "is",
    "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these",
    "those", "there", "here", "not", "no", "than", "then", "when", "while", "have",
    "has", "had", "do", "does", "did", "can", "could", "would", "will", "you", "we",
    "they", "he", "she", "i", "his", "her", "their", "our", "your", "my", "one", "more",
    "most", "very", "just", "only", "also", "all", "any", "some", "out", "up", "down",
    "over", "after", "before", "because", "what", "which", "who", "how", "why",
}
CUM_PHO_THONG = {
    "one of", "the most", "more than", "the world", "the first", "the same", "the only",
    "part of", "kind of", "a lot", "the end", "the same time", "at the", "in the",
    "of the", "to the", "on the", "for the", "and the", "it is", "there is", "this is",
}

# Tu CHUYEN doan that su — do that 24/08 khong loc thi 'the' chiem 17-21% va bang
# xep hang thanh vo nghia: moi van ban tieng Anh deu co doan mo bang mao tu.
TU_CHUYEN = {"but", "and", "so", "yet", "then", "now", "still", "however", "though",
             "meanwhile", "instead", "besides", "because", "although", "eventually",
             "finally", "today", "later", "soon", "when", "while", "after", "before",
             "that", "this", "these", "those", "it", "there", "what", "why", "how"}


MIN_TU_CAU = 5            # duoi nguong nay thuong la TIEU DE file, khong phai cau van


def _cau_sach(c: str) -> str:
    c = re.sub(r"\s+", " ", (c or "").strip())
    return c[:TRAN_CAU]


def _cau_that(text: str, nguoc: bool = False) -> str:
    """Cau van THAT dau (hoac cuoi) mot van ban.

    Hai bay tu corpus that (do 24/08):
      - "Real Life in Sweden ." la TIEU DE file nam o dong dau, khong phai cau mo bai
        => bo qua cac cau duoi MIN_TU_CAU tu.
      - Tieu de thuong KHONG co dau cham, nen split_sentences dinh no vao cau sau
        ("Real Life in Sweden Why does a river run black?") => phai tach theo DOAN
        truoc roi moi tach cau trong tung doan.
    """
    cs = [c for d in _doan(text) for c in split_sentences(d)]
    if not cs:
        return ""
    for c in (reversed(cs) if nguoc else cs):
        if _la_cau_van(c):
            return _cau_sach(c)
    return _cau_sach(cs[-1] if nguoc else cs[0])


def _la_cau_van(c: str) -> bool:
    """Loai ba thu KHONG phai cau van, gap that trong corpus cua kho (do 24/08):

      "15 Facts About the Perfect Country..."          tieu de — khong co dau ket cau
      "[a]Hien thi nut Like va Subscriber"             chu thich Google Docs
      "Real Life in Sweden"                            tieu de ngan
    """
    c = (c or "").strip()
    if c.startswith("["):
        return False
    if not c.rstrip().endswith((".", "!", "?", '"', "'", "…")):
        return False
    return len(tokenize_words(c)) >= MIN_TU_CAU


def _doan(text: str) -> list[str]:
    return [d.strip() for d in re.split(r"\n\s*\n", text or "") if d.strip()]


def _mo_dau(texts: list[str]) -> dict:
    cau = [c for c in (_cau_that(t) for t in texts) if c]
    hoi = sum(1 for c in cau if c.rstrip().endswith("?"))
    so = sum(1 for c in cau if re.search(r"\d", c))
    return {
        "so_mau": len(cau),
        "du_mau": len(cau) >= MIN_MAU,
        "cau": cau[:SO_MAU_HIEN],
        "ti_le_cau_hoi": round(100 * hoi / len(cau), 1) if cau else 0.0,
        "ti_le_co_so": round(100 * so / len(cau), 1) if cau else 0.0,
        "tu_moi_cau": round(sum(len(tokenize_words(c)) for c in cau) / len(cau), 1) if cau else 0.0,
    }


def _ket(texts: list[str]) -> dict:
    cau = [c for c in (_cau_that(t, nguoc=True) for t in texts) if c]
    return {"so_mau": len(cau), "du_mau": len(cau) >= MIN_MAU, "cau": cau[:SO_MAU_HIEN]}


def _chuyen_doan(texts: list[str]) -> dict:
    """Tu mo dau cac doan GIUA bai — doan dau khong tinh (no la mo bai)."""
    dem: Counter = Counter()
    mau: dict[str, str] = {}
    tong = 0
    for t in texts:
        for d in _doan(t)[1:]:
            cs = split_sentences(d)
            if not cs:
                continue
            w = tokenize_words(cs[0])
            if not w:
                continue
            tong += 1
            k = w[0].lower()
            if k not in TU_CHUYEN:      # mao tu / gioi tu mo doan khong noi len dieu gi
                continue
            dem[k] += 1
            mau.setdefault(k, _cau_sach(cs[0]))
    hay = [{"tu": k, "so_lan": n, "phan_tram": round(100 * n / tong) if tong else 0,
            "vi_du": mau[k]}
           for k, n in dem.most_common(5) if n >= 2]
    return {"so_doan": tong, "du_mau": tong >= MIN_MAU, "hay_dung": hay}


def _tu_dac_trung(texts: list[str], n_max: int = 3, top_k: int = 10) -> list[dict]:
    """Cum 2-3 tu lap lai qua NHIEU van ban, da bo hu tu va cum pho thong."""
    if not texts:
        return []
    can_mat = 2 if len(texts) > 1 else 1
    tong: Counter = Counter()
    co_mat: Counter = Counter()
    for t in texts:
        w = [x.lower() for x in tokenize_words(t)]
        thay = set()
        for n in (2, 3)[:max(1, n_max - 1)]:
            for i in range(len(w) - n + 1):
                cum = " ".join(w[i:i + n])
                tong[cum] += 1
                thay.add(cum)
        for c in thay:
            co_mat[c] += 1
    ra = []
    for cum, sl in tong.most_common():
        tu = cum.split()
        if all(x in HU_TU for x in tu) or cum in CUM_PHO_THONG:
            continue
        if tu[0] in HU_TU and tu[-1] in HU_TU:      # "of the world", "in the same"
            continue
        # Cum HAI tu mo bang hu tu ("the country", "a country", "the us") gan nhu luon
        # la cum pho thong; cum BA tu thi ho tu dau con mang nghia ("parts per billion").
        if len(tu) == 2 and tu[0] in HU_TU:
            continue
        if sl < 3 or co_mat[cum] < can_mat:
            continue
        ra.append({"cum": cum, "so_lan": sl, "so_van_ban": co_mat[cum]})
        if len(ra) >= top_k:
            break
    return ra


def khuon(texts: list[str]) -> dict:
    """Bon muc khuon van tu corpus. Corpus rong -> cac muc rong, khong vo."""
    texts = [t for t in (texts or []) if (t or "").strip()]
    return {
        "mo_dau": _mo_dau(texts),
        "chuyen_doan": _chuyen_doan(texts),
        "ket": _ket(texts),
        "tu_dac_trung": _tu_dac_trung(texts),
    }
