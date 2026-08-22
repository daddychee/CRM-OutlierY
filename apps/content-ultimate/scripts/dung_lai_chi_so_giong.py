"""Dung lai CHI SO GIONG cho ho so dung tren corpus lan file thieu dau cau.

Boi canh (do 23/08): 3 ho so trong kho — A003 Ventures, A008 Discovery Ventures,
A011 Discover Ventures — deu tro vao CUNG mot corpus 'Ventures' co 2/5 file la
transcript tho. Hau qua do duoc: chung chi co 3 chi so giong (ho so lanh co
7-17), va sentence_len_mean = 1085 — con so khong the co o nguoi viet.

Vi sao khac thi nghiem 16/07 da bi Owner BAC BO: lan do dung lai ho so tu TOAN BO
corpus GOM CA transcript tho nen van ra coc loc. Lan nay du lieu vao da loc: chi
3 file lanh, 14.252 tu sach.

Nguyen tac:
- KHONG ghi de. Ghi ra profile.moi.json canh ban cu; ban cu giu nguyen lam duong lui.
- Chi thay QUANT: quant_features + reproduction_targets + corpus_stats + exemplars.
  Giu nguyen signature_moves va distinctive_ngrams (chung do LLM sinh, khong lien
  quan den chuyen thieu dau cau, va dung lai se ton tien).
- 0 token: toan bo la do dac Python.

Chay:  python scripts/dung_lai_chi_so_giong.py            # xem thu
       python scripts/dung_lai_chi_so_giong.py --ghi      # ghi profile.moi.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voiceprofile.corpus import build_corpus                      # noqa: E402
from voiceprofile.profile import build_profile                    # noqa: E402

KHO = Path(r"D:\AI AGENT OUTLIERY\data\content-ultimate\uploads")
HO_SO = [("A003_Ventures", "Ventures"),
         ("A008_Discovery-Ventures", "Discovery Ventures"),
         ("A011_Discover-Ventures", "Discover Ventures")]
GIU = ("signature_moves", "distinctive_ngrams", "author", "source_language",
       "output_language", "profile_mode", "language_neutral_targets")


def mot_ho_so(ma: str, ten_corpus: str, ghi: bool) -> None:
    thu_muc = KHO / ma
    cu = json.loads((thu_muc / "profile.json").read_text(encoding="utf-8"))
    corpus = build_corpus(KHO / ten_corpus, name=cu.get("author") or ma)

    moi = build_profile(author=cu.get("author") or ma,
                        source_language=cu.get("source_language") or "en",
                        output_language=cu.get("output_language") or "en",
                        author_corpus=corpus)
    for k in GIU:                       # giu phan do LLM sinh, khong dung lai (ton tien)
        if k in cu:
            moi[k] = cu[k]

    def slm(p):
        return next((q["value"] for q in p.get("quant_features", [])
                     if q["name"] == "sentence_len_mean"), None)

    print(f"\n{ma}")
    print(f"   file dung  : {corpus.n_works} · {corpus.n_tokens:,} tu"
          + (f" · DA BO {len(corpus.file_bo)}: {'; '.join(corpus.file_bo)}" if corpus.file_bo else ""))
    print(f"   chi so     : {len(cu.get('reproduction_targets') or {})} -> "
          f"{len(moi.get('reproduction_targets') or {})}")
    print(f"   tu/cau     : {slm(cu)} -> {slm(moi)}")
    ex_cu = sum(len(str(e).split()) for e in (cu.get("exemplars") or []))
    ex_moi = sum(len(str(e).split()) for e in (moi.get("exemplars") or []))
    print(f"   exemplar   : {ex_cu} tu -> {ex_moi} tu")

    if ghi:
        dich = thu_muc / "profile.moi.json"
        dich.write_text(json.dumps(moi, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   DA GHI     : {dich.name} (ban cu GIU NGUYEN)")


if __name__ == "__main__":
    ghi = "--ghi" in sys.argv
    for ma, ten in HO_SO:
        mot_ho_so(ma, ten, ghi)
    if not ghi:
        print("\n(xem thu — them --ghi de ghi ra profile.moi.json canh ban cu)")
