# -*- coding: utf-8 -*-
"""Soi ho so giong: ho so nao dung tu corpus HONG thi moi so do giong deu la rac.

Boi canh (do that 21/08/2026 tren 9 ho so trong kho): 4 ho so co
`sentence_len_mean = 1085` — dau van tay cua transcript YouTube chua don dau cau
(ca van ban bi do nhu MOT cau). Ho so do van duoc dung de viet suot 3 tuan, va moi
thuoc do giong dua tren no deu vo nghia. App da co canh bao transcript tho tu 16/07
nhung "chi bao, khong chan" nen bi bo qua 100%.

Hai cau hoi TACH BIET (dung gop lam mot):
  1. `do_duoc`  — co tin duoc SO DO giong cua ho so nay khong? (corpus co dau cau khong)
  2. `neo_du`   — neo giong co DU DAY de model bam theo khong? (exemplar bao nhieu tu)

Python do — khong LLM (luat A1). Chi BAO, khong tu sua ho so (luat A3).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .textutils import split_sentences, tokenize_words

# --- Nguong: deu tu so DO THAT ngay 21/08/2026, khong phai con so cam tinh --------
# Van nguoi viet (exemplar corpus sach A013_Derek-Muller): 20,7 tu/cau.
# Corpus transcript tho (A003/A008/A011): sentence_len_mean = 1085 — khong the co that.
CAU_QUA_DAI = 60.0      # > nguong nay = gan nhu chac chan thieu dau ket cau
CAU_QUA_NGAN = 8.0      # < nguong nay = van ban vun bat thuong (hoac tach cau hong)
NEO_DU_TU = 800         # tong tu exemplar toi thieu de goi la neo day
NGUONG_TRUNG = 0.30     # >=30% shingle cua mau nay nam trong mau kia = ke lai cung mot doan
# generator.build_voice_block chi lay 3 exemplar dau -> do dung 3 mau do, khong do ca kho
SO_EXEMPLAR_VAO_PROMPT = 3


def _chi_so_profile(profile: dict) -> dict[str, float]:
    """quant_features luu dang list[{name, value, baseline}] -> map ten->gia tri."""
    qf = profile.get("quant_features") or []
    out: dict[str, float] = {}
    for f in qf:
        if isinstance(f, dict) and "name" in f and isinstance(f.get("value"), (int, float)):
            out[str(f["name"])] = float(f["value"])
    return out


def _chuan(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _shingle(s: str, n: int = 8) -> set[tuple[str, ...]]:
    """Bo n-gram de do chong lan giua 2 exemplar (re, khong can thu vien)."""
    tu = tokenize_words(_chuan(s))
    return {tuple(tu[i:i + n]) for i in range(max(0, len(tu) - n + 1))}


def _do_exemplar(exemplars: list) -> dict:
    """Do chinh cai NEO di vao prompt: 3 mau dau (dung nhu build_voice_block)."""
    mau = [e for e in exemplars if isinstance(e, str)][:SO_EXEMPLAR_VAO_PROMPT]
    gop = " ".join(mau)
    cau = split_sentences(gop)
    do_dai = [len(tokenize_words(c)) for c in cau if tokenize_words(c)]
    tb = (sum(do_dai) / len(do_dai)) if do_dai else 0.0

    # Trung lap: do CHONG LAN bang shingle 8 tu, khong doi "chua tron" — A011 that
    # co 2 mau ke chung mot doan St.Petersburg lech nhau vai chu, "chua tron" khong bat duoc.
    trung = False
    bo = [_shingle(m) for m in mau]
    for i in range(len(bo)):
        for j in range(len(bo)):
            if i != j and bo[i] and len(bo[i] & bo[j]) / len(bo[i]) >= NGUONG_TRUNG:
                trung = True
    return {
        "so_mau": len(mau),
        "tong_tu": len(tokenize_words(gop)),
        "tu_moi_cau": round(tb, 1),
        "trung_lap": trung,
    }


def soi_profile(profile: dict) -> dict:
    """Soi MOT ho so -> co + chi so + cau chu de hien thang len UI.

    Tra ve: {ten, do_duoc, neo_du, co[], chi_so{}, canh_bao[]}
    `co` la ma may doc (test ghim), `canh_bao` la cau tieng Viet cho nguoi doc.
    """
    ten = str(profile.get("author") or "?")
    cs = _chi_so_profile(profile)
    ex = _do_exemplar(profile.get("exemplars") or [])
    slm = cs.get("sentence_len_mean")

    co: list[str] = []
    canh_bao: list[str] = []

    if slm is not None and slm > CAU_QUA_DAI:
        co.append("corpus_thieu_dau_cau")
        canh_bao.append(
            f"Corpus do ra {slm:.0f} tu/cau — khong the co that o nguoi viet. "
            "Gan nhu chac chan la transcript chua don dau cau; moi so do giong cua "
            "ho so nay (do dai cau, nhip, Flesch) deu khong dung."
        )
    elif slm is not None and 0 < slm < CAU_QUA_NGAN:
        co.append("corpus_cau_qua_vun")
        canh_bao.append(f"Corpus do ra {slm:.1f} tu/cau — vun bat thuong, nen kiem lai nguon.")

    if ex["so_mau"] and ex["tu_moi_cau"] > CAU_QUA_DAI:
        co.append("exemplar_thieu_dau_cau")
        canh_bao.append(
            f"Exemplar do ra {ex['tu_moi_cau']:.0f} tu/cau — mau neo giong cung thieu "
            "dau cau; model se hoc thanh cau dai vo tan."
        )

    if ex["tong_tu"] < NEO_DU_TU:
        co.append("neo_mong")
        canh_bao.append(
            f"Neo giong chi {ex['tong_tu']} tu ({ex['so_mau']} mau) — qua mong so voi "
            "ca tram dong luat trong prompt; model se roi ve nhip mac dinh cua no."
        )
    if ex["trung_lap"]:
        co.append("exemplar_trung_lap")
        canh_bao.append("Cac mau exemplar trung noi dung nhau — neo thuc te con mong hon so tu.")

    return {
        "ten": ten,
        "do_duoc": not any(c.startswith("corpus_") or c == "exemplar_thieu_dau_cau" for c in co),
        "neo_du": "neo_mong" not in co and "exemplar_trung_lap" not in co,
        "co": co,
        "chi_so": {
            "sentence_len_mean": round(slm, 1) if isinstance(slm, (int, float)) else None,
            "exemplar_so_mau": ex["so_mau"],
            "exemplar_tong_tu": ex["tong_tu"],
            "exemplar_tu_moi_cau": ex["tu_moi_cau"],
            "so_target": len(profile.get("reproduction_targets") or {}),
        },
        "canh_bao": canh_bao,
    }


def soi_kho(thu_muc_uploads: str | Path) -> list[dict]:
    """Soi moi ho so trong kho -> bang cho UI. Ho so doc khong duoc thi bo qua, khong vo."""
    goc = Path(thu_muc_uploads)
    ket: list[dict] = []
    for p in sorted(goc.glob("*/profile.json")):
        try:
            pf = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        r = soi_profile(pf)
        r["thu_muc"] = p.parent.name
        ket.append(r)
    return ket
