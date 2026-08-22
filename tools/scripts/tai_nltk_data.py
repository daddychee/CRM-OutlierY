# -*- coding: utf-8 -*-
"""Tai du lieu nltk cho phan loai tu loai cua RadarY Mapping (22/08/2026).

data/ nam ngoai git nen may moi (hoac sau khi don data) chay script nay MOT lan:
    .venv/Scripts/python.exe tools/scripts/tai_nltk_data.py
Thieu data khong lam app chet — mapping.bang_pos co van an toan tu ve luat
sau-gioi-tu cu — nhung phan loai doi-tuong/mau-cau se kem hon han o ngach
khong-phai-Life-in-X (vi du SPACE).
"""
import os
import sys

import nltk

GOC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICH = os.path.join(GOC, "data", "nltk_data")

os.makedirs(DICH, exist_ok=True)
for goi in ("averaged_perceptron_tagger_eng", "words", "punkt_tab"):
    ok = nltk.download(goi, download_dir=DICH, quiet=True)
    print(("  OK  " if ok else "  LOI ") + goi)

nltk.data.path.insert(0, DICH)
from nltk import pos_tag                                    # noqa: E402
from nltk.corpus import words                               # noqa: E402

assert pos_tag(["replace"])[0][1].startswith("VB"), "tagger hong"
assert len(words.words()) > 200_000, "tu dien hong"
print(f"kiem chung OK — {DICH}")
sys.exit(0)
