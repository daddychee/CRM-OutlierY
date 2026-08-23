# -*- coding: utf-8 -*-
"""Ba tang do con thieu cua author extract: LAP TRUONG, DIEN NGON, CU PHAP (C5, 24/08).

Quant Engine do tu vung (TTR, hu tu, do dai tu) va nhip cau. No KHONG do:
  - lap truong voi nguoi doc: Derek Muller noi "you", Attenborough khong bao gio noi;
    day la thu phan biet hai giong ro nhat ma khong thuoc nao cua app dang nhin;
  - dien ngon: bao nhieu cau moi doan, co hay mo cau bang lien tu ("But...", "And...");
  - cu phap: cau hoi truc tiep, the bi dong, tu chi xuat hien mot lan (hapax).

TAI SAO O MODULE RIENG, khong nhet vao _raw_features:
moi chieu them vao quant_features se TU DONG chay vao reproduction_targets roi vao
thang cham giong. Bai hoc 23/08 (punct_freq_total dem ca em-dash nen ban sach dau van
tay may bi cham la "kem giong tac gia") noi ro: thang cham cang nhieu chieu tap nham
thi cang de doc nguoc. Tang nay la CHAN DOAN va NGUYEN LIEU cho prompt (C3), khong
phai tieu chi cham. Ho so ghi no o khoa `discourse_features`, tach bach.

Python do het, 0 token. The bi dong la PROXY bang regex (khong co POS tagger trong
app) — khai ro chu khong giau: no bat "was destroyed", khong bat moi the bi dong.
"""
from __future__ import annotations

import re
import statistics

from .textutils import split_sentences, tokenize_words

NGOI_2 = {"you", "your", "yours", "yourself", "yourselves"}
NGOI_1_IT = {"i", "me", "my", "mine", "myself"}
NGOI_1_NHIEU = {"we", "us", "our", "ours", "ourselves"}

# Lien tu mo cau — dau hieu van noi, nhip keo (khac han van viet hoc thuat).
LIEN_TU_MO_CAU = {"but", "and", "so", "yet", "or", "because", "then", "now", "still",
                  "however", "though", "besides", "meanwhile", "instead", "except"}

# Proxy the bi dong: to be + phan tu qua khu. Bat duoc dang pho bien nhat; dong tu bat
# quy tac liet ke tay vi khong co POS tagger (app khong keo them thu vien — Ponytail).
_BE = r"(?:is|are|was|were|be|been|being|am)"
_PP_BAT_QUY_TAC = ("born|done|made|given|taken|seen|known|found|written|held|kept|left|"
                   "told|shown|built|brought|caught|sold|lost|sent|put|set|driven|"
                   "grown|thrown|drawn|broken|chosen|forgotten|hidden|beaten")
_BI_DONG = re.compile(rf"\b{_BE}\s+(?:\w+ed|{_PP_BAT_QUY_TAC})\b", re.IGNORECASE)

_CHU_SO = re.compile(r"\d")

TEN_CHIEU = (
    "ngoi_thu_hai", "ngoi_thu_nhat_it", "ngoi_thu_nhat_nhieu",   # lap truong
    "cau_moi_doan", "lien_tu_mo_cau", "cau_hoi",                 # dien ngon
    "bi_dong", "hapax", "mat_do_so",                             # cu phap / tu vung
)


def dac_trung(text: str) -> dict[str, float]:
    """Chin chieu, tren MOT khoi van ban. Van rong -> tat ca 0.0 (khong vo, khong None).

    Don vi: ba chieu ngoi + mat_do_so tinh tren 1.000 TU (con so doc duoc bang mat);
    cac chieu con lai la ti le 0..1, rieng cau_moi_doan la so cau.
    """
    tu = [w.lower() for w in tokenize_words(text)]
    cau = split_sentences(text)
    n_tu = len(tu) or 1
    n_cau = len(cau) or 1

    doan = [d for d in re.split(r"\n\s*\n", text or "") if d.strip()]
    so_cau_doan = [len(split_sentences(d)) for d in doan] or [n_cau]

    mo_lien_tu = 0
    for c in cau:
        w = tokenize_words(c)
        if w and w[0].lower() in LIEN_TU_MO_CAU:
            mo_lien_tu += 1

    dem_tu: dict[str, int] = {}
    for w in tu:
        dem_tu[w] = dem_tu.get(w, 0) + 1

    return {
        "ngoi_thu_hai": 1000 * sum(1 for w in tu if w in NGOI_2) / n_tu,
        "ngoi_thu_nhat_it": 1000 * sum(1 for w in tu if w in NGOI_1_IT) / n_tu,
        "ngoi_thu_nhat_nhieu": 1000 * sum(1 for w in tu if w in NGOI_1_NHIEU) / n_tu,
        "cau_moi_doan": float(statistics.mean(so_cau_doan)),
        "lien_tu_mo_cau": mo_lien_tu / n_cau,
        "cau_hoi": sum(1 for c in cau if c.rstrip().endswith("?")) / n_cau,
        "bi_dong": len(_BI_DONG.findall(text or "")) / n_cau,
        "hapax": sum(1 for _, n in dem_tu.items() if n == 1) / n_tu,
        "mat_do_so": 1000 * len(_CHU_SO.findall(text or "")) / n_tu,
        # Khong phai chieu phong cach (khong nam trong TEN_CHIEU): dung de biet
        # cau_moi_doan co nghia hay khong — xem ho_so().
        "so_doan": float(len(doan) or 1),
    }


def ho_so(don_vi_do: list[str], min_don_vi: int = 3,
          van_goc: list[str] | None = None) -> dict:
    """Gop chin chieu tren cac don vi do cua corpus -> target + sai so.

    Dung dung luat C1: duoi min_don_vi diem do thi sd = None va do_duoc = False —
    gia tri van do duoc, chi la chua chung minh duoc no on dinh.

    `van_goc` (bug sua 24/08): don vi do do `chunk_by_words` cat ra duoc NOI BANG DAU
    CACH, tuc ranh gioi doan bi xoa sach. Do "so cau moi doan" tren do thi ho so nao
    du lon de phai cat chunk cung bi bao "file khong co mot dong trong nao" — canh bao
    oan cho phan lon kho (A001 co 2.693 doan that, sau khi cat chi con 37). Chieu do
    doan phai do tren VAN GOC; cac chieu khac khong bi anh huong nen van do tren don vi.
    """
    khoi = [t for t in don_vi_do if (t or "").strip()] or [""]
    per = [dac_trung(t) for t in khoi]
    goc = [t for t in (van_goc or []) if (t or "").strip()]
    if goc:
        per_goc = [dac_trung(t) for t in goc]
        for i, p_ in enumerate(per):
            g = per_goc[min(i, len(per_goc) - 1)]
            p_["cau_moi_doan"], p_["so_doan"] = g["cau_moi_doan"], g["so_doan"]
    du = len(khoi) >= min_don_vi
    chieu = {}
    for ten in TEN_CHIEU:
        vals = [p[ten] for p in per]
        sd = statistics.pstdev(vals) if du and len(vals) > 1 else None
        chieu[ten] = {
            "target": round(statistics.mean(vals), 4),
            "sd": round(sd, 4) if sd is not None else None,
        }
    # Do that 24/08: A007/A012 ra 786 cau/doan va A010 ra 426 — khong phai van phong,
    # ma vi file KHONG CO DONG TRONG nao (ca file la mot doan). Con so do la do dai FILE.
    # Bao thang thay vi de nguoi doc tuong tac gia viet doan 786 cau.
    canh_bao = []
    if statistics.mean([p["so_doan"] for p in per]) <= 1.05:
        canh_bao.append("File corpus không có một dòng trống nào — 'số câu mỗi đoạn' ở đây "
                        "là độ dài FILE, không phải độ dài đoạn. Chiều này không dùng được "
                        "cho hồ sơ này (các chiều khác không bị ảnh hưởng).")
        chieu["cau_moi_doan"]["do_duoc"] = False
    return {"do_duoc": du, "n_don_vi": len(khoi), "chieu": chieu, "canh_bao": canh_bao}


def mo_ta(hs: dict) -> list[str]:
    """Vai cau tieng Viet cho nguoi doc bao cao — chi MO TA, khong phan hay/do.

    Nguong o day la de PHAN LOAI cho de doc (nhieu/it), khong phai tieu chi dat/truot:
    khong co "lap truong dung", chi co lap truong khac nhau.
    """
    c = {k: v["target"] for k, v in hs["chieu"].items()}
    ra = []
    if c["ngoi_thu_hai"] >= 5:
        ra.append(f"Nói THẲNG với người đọc: {c['ngoi_thu_hai']:.1f} lần \"you\" mỗi 1.000 từ.")
    elif c["ngoi_thu_hai"] < 0.5:
        ra.append("Gần như không bao giờ gọi \"you\" — giọng giảng giải, không đối thoại.")
    if c["ngoi_thu_nhat_it"] >= 5:
        ra.append(f"Kể ở ngôi thứ nhất: {c['ngoi_thu_nhat_it']:.1f} lần \"I\" mỗi 1.000 từ.")
    if c["ngoi_thu_nhat_nhieu"] >= 5:
        ra.append(f"Kéo người đọc về cùng phía: {c['ngoi_thu_nhat_nhieu']:.1f} lần \"we\" mỗi 1.000 từ.")
    if hs["chieu"]["cau_moi_doan"].get("do_duoc") is not False:
        ra.append(f"Đoạn dài trung bình {c['cau_moi_doan']:.1f} câu.")
    if c["lien_tu_mo_cau"] >= 0.15:
        ra.append(f"{100 * c['lien_tu_mo_cau']:.0f}% số câu mở bằng liên từ (But/And/So) — nhịp văn nói.")
    if c["cau_hoi"] >= 0.05:
        ra.append(f"{100 * c['cau_hoi']:.0f}% số câu là câu hỏi trực tiếp.")
    if c["bi_dong"] >= 0.20:
        ra.append(f"Thể bị động dày: {100 * c['bi_dong']:.0f}% số câu (đo bằng mẫu regex, là ước lượng).")
    return ra
