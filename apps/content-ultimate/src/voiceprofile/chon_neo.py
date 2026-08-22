"""Chon NEO GIONG day va DUNG NHIP tu corpus tac gia (Dot 2 — C3b, 22/08/2026).

Benh: `build_voice_block` chi nap 3 exemplar (~200-330 tu) lam neo giong, dau voi
ca tram dong luat trong prompt. Con lac 16/07 la hau qua: go luat "viet cau dai"
(tell) roi chuyen sang exemplar (show), nhung "show" qua mong nen van vang sang
thai cuc cau vun.

Do that 22/08 con lo them mot chuyen ngoai "mong": 3 mau hien tai chon LECH.
  A013: mau neo 33,3% cau dai — corpus that chi 9,3%
  A010: mau neo 26,7% cau dai — corpus that 15,0%
Tuc model dang bi chi vao mot cai dich khong phai nhip that cua tac gia. Nen
module nay khong chi lay NHIEU hon, ma chon sao cho NHIP GOP KHOP CORPUS.

BA VAN AN TOAN:
1. Chi lam day khi corpus DOC DUOC (co dau cau). Corpus transcript tho thi giu
   nguyen hanh vi cu — lam day bang transcript tho la day model viet khong dau cau.
2. Khong dung den profile.json. Bai hoc 16/07 da ghi: "DUNG DUNG LAI PROFILE TU
   CORPUS TRANSCRIPT — da thu, USER BAC BO". Day chi THEM mau van that vao prompt
   luc viet, khong ghi de ho so, khong doi mot target nao.
3. Khong goi LLM, khong ton token. Toan bo la do dac Python tat dinh.
"""
from __future__ import annotations

import re
from pathlib import Path

# Muc tieu do day: du de dau lai voi khoi luat, chua du de nuot ca ngan sach ngu canh.
MUC_TIEU_TU = 1800
TRAN_TU = 2600
KHOI_MIN_TU = 60           # duoi nguong nay thi gop voi khoi ke
KHOI_MAX_TU = 400          # tren nguong nay thi cat
DAU_KET_TREN_1K = 4.0      # cung nguong voi corpus.punctuation_density
TRUNG_LAP = 0.30           # ti le shingle chong lan -> coi la mot mau

_CAU = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$")
_TU = re.compile(r"[^\W_]+", re.UNICODE)


def _tu(s: str) -> list[str]:
    return _TU.findall(s)


def _cau(s: str) -> list[str]:
    return [c.strip() for c in _CAU.findall(s) if c.strip()]


def nhip(text: str) -> dict:
    """Ba truc nhip dung de so: tu/cau, % cau cut (<8 tu), % cau dai (>35 tu)."""
    cau = _cau(text)
    if not cau:
        return {"tu_moi_cau": 0.0, "ti_le_cut": 0.0, "ti_le_dai": 0.0, "so_cau": 0}
    do = [len(_tu(c)) for c in cau]
    n = len(do)
    return {"tu_moi_cau": round(sum(do) / n, 1),
            "ti_le_cut": round(100 * sum(1 for d in do if d < 8) / n, 1),
            "ti_le_dai": round(100 * sum(1 for d in do if d > 35) / n, 1),
            "so_cau": n}


def _mat_do_dau_ket(text: str) -> float:
    """So dau ket cau tren 1000 ky tu — thap = transcript chua don dau cau."""
    if not text:
        return 0.0
    return 1000 * sum(text.count(c) for c in ".!?") / len(text)


def doc_corpus(thu_muc: str | Path) -> list[str]:
    """Doc .txt/.md trong thu muc corpus. Thieu thu muc -> danh sach rong, khong vo."""
    goc = Path(thu_muc)
    if not goc.is_dir():
        return []
    ra = []
    for p in sorted(goc.rglob("*")):
        if p.suffix.lower() in (".txt", ".md") and p.is_file():
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(t) >= 500:
                ra.append(t)
    return ra


def cat_khoi(texts: list[str]) -> list[str]:
    """Cat corpus thanh khoi ung vien 60-400 tu, cat o RANH DOAN (khong giua cau)."""
    khoi: list[str] = []
    for t in texts:
        gom: list[str] = []
        for doan in re.split(r"\n\s*\n", t):
            doan = doan.strip()
            if not doan or doan.startswith("#"):
                continue
            gom.append(doan)
            n = len(_tu(" ".join(gom)))
            if n >= KHOI_MIN_TU:
                if n <= KHOI_MAX_TU:
                    khoi.append("\n\n".join(gom))
                    gom = []
                else:
                    # doan qua dai: cat theo cau cho vua tran
                    cau, cum, dem = _cau(" ".join(gom)), [], 0
                    for c in cau:
                        cum.append(c)
                        dem += len(_tu(c))
                        if dem >= KHOI_MAX_TU:
                            khoi.append(" ".join(cum))
                            cum, dem = [], 0
                    if dem >= KHOI_MIN_TU:
                        khoi.append(" ".join(cum))
                    gom = []
        if gom and len(_tu(" ".join(gom))) >= KHOI_MIN_TU:
            khoi.append("\n\n".join(gom))
    return khoi


def _shingle(s: str, n: int = 8) -> set[tuple[str, ...]]:
    tu = [w.lower() for w in _tu(s)]
    return {tuple(tu[i:i + n]) for i in range(max(0, len(tu) - n + 1))}


def _trung(a: str, giu: list[tuple[str, set]]) -> bool:
    sa = _shingle(a)
    if not sa:
        return True
    return any(len(sa & sb) / len(sa) >= TRUNG_LAP for _, sb in giu)


def _lech(a: dict, b: dict) -> float:
    """Khoang cach nhip giua hai van ban — 3 truc, chuan hoa theo thang cua truc."""
    return (abs(a["tu_moi_cau"] - b["tu_moi_cau"]) / 10.0
            + abs(a["ti_le_cut"] - b["ti_le_cut"]) / 20.0
            + abs(a["ti_le_dai"] - b["ti_le_dai"]) / 20.0)


def chon(texts: list[str], muc_tieu_tu: int = MUC_TIEU_TU) -> dict:
    """Chon tap neo giong tu corpus.

    Tra {"neo": [...], "ly_do": str, "nhip_neo": {...}, "nhip_corpus": {...},
         "tong_tu": int} — "neo" rong nghia la KHONG lam day duoc, noi ro ly do.
    """
    if not texts:
        return {"neo": [], "ly_do": "khong doc duoc corpus tac gia", "tong_tu": 0}

    # LOC O MUC KHOI, khong o muc corpus: do GOP che su that. Corpus A003 do gop ra
    # 9,3 dau ket/1000 (qua nguong) nhung thuc ra 2/5 file la transcript tho 0,1 —
    # loc theo khoi thi 2 file do bi bo, 3 file lanh duoc dung (kiem mat 22/08).
    lanh = [t for t in texts if _mat_do_dau_ket(t) >= DAU_KET_TREN_1K]
    if not lanh:
        return {"neo": [], "tong_tu": 0,
                "ly_do": ("moi file corpus deu thieu dau cau (transcript chua don) — lam day "
                          "neo bang van nay la day model viet khong dau cau")}

    chuan = nhip("\n\n".join(lanh))
    khoi = [k for k in cat_khoi(lanh) if _mat_do_dau_ket(k) >= DAU_KET_TREN_1K]
    if not khoi:
        return {"neo": [], "ly_do": "corpus khong cat duoc khoi nao du dai", "tong_tu": 0}
    bo = len(texts) - len(lanh)

    # THAM LAM: moi buoc them khoi lam nhip GOP gan chuan nhat. Khong xep san theo
    # do lech tung khoi — mot khoi "lech" co the keo tap gop ve dung chuan.
    giu: list[tuple[str, set]] = []
    con = list(khoi)
    tong = 0
    while con and tong < muc_tieu_tu:
        tot, diem_tot = None, None
        hien = [g for g, _ in giu]
        for k in con:
            if _trung(k, giu):
                continue
            d = _lech(nhip("\n\n".join(hien + [k])), chuan)
            if diem_tot is None or d < diem_tot:
                tot, diem_tot = k, d
        if tot is None:
            break
        giu.append((tot, _shingle(tot)))
        con.remove(tot)
        tong = len(_tu("\n\n".join(g for g, _ in giu)))
        if tong >= TRAN_TU:
            break

    neo = [g for g, _ in giu]
    if not neo:
        return {"neo": [], "ly_do": "moi khoi deu trung lap nhau", "tong_tu": 0}
    return {"neo": neo, "tong_tu": tong, "ly_do": "", "file_bo_qua": bo,
            "nhip_neo": nhip("\n\n".join(neo)), "nhip_corpus": chuan}


def neo_day(corpus_dir: str | Path | None, muc_tieu_tu: int = MUC_TIEU_TU) -> dict:
    """Cua vao dung chung: thu muc corpus -> tap neo (hoac ly do khong lam duoc)."""
    if not corpus_dir:
        return {"neo": [], "ly_do": "khong biet thu muc corpus tac gia", "tong_tu": 0}
    return chon(doc_corpus(corpus_dir), muc_tieu_tu)
