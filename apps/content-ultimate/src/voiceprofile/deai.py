# -*- coding: utf-8 -*-
"""KIEM CHUNG KICH BAN DAU RA — bo cham 3 nhom TACH BACH (khong gop diem tong).

Vi sao 3 nhom rieng (chot 21/08/2026 sau khi do 38 luot writer that):

  A. DAU VET MAY  — tuyet doi, khong phu thuoc tac gia nao: ky tu an, cum sao,
     mat do em-dash. Khong nguoi viet nao lap deu nhung cum nay. Luat NGOAI CODE
     (rules/deai_en.csv) — them cum moi = them dong Excel.
  B. NHIP         — tuong doi, so voi EXEMPLAR CUA CHINH HO SO. "Cau dai" khong
     phai benh; "lech giong tac gia da chon" moi la benh. Ho so hong -> chi MO TA,
     khong phan benh (van chong bia).
  C. GIONG        — goi validate.evaluate_script (14 target san co cua app). CO CUA:
     ho so khong `do_duoc` (corpus transcript tho) -> tra "khong du co so", KHONG
     phan so. Bat van tren so rac con te hon khong co van.

Bang chung dan den thiet ke nay (do 21/08/2026):
  - 7 ban that ho so A011: em-dash 30-53/bai (~8-13 tren 1000 tu) trong khi van
    nguoi (exemplar A013) chi 1,4/1000 -> mat do em-dash la tin hieu manh.
  - burstiness (cv do dai cau): ban may 0,51-0,67 vs ban da bien tap 1,25 -> cau
    deu tam tap la dau may.
  - A012 54,5% cau cut / A013 36,9% trong khi exemplar goc 8,3% -> nhip lech giong.
  - reproduction_targets cua 4/9 ho so dung tren corpus hong -> BAT BUOC co cua.

Python do — LLM khong tham gia mot dong nao trong file nay (luat A1).
Chi BAO, khong tu sua van ban, khong tu chan (luat A3).
"""
from __future__ import annotations

import csv
import re
import statistics
from pathlib import Path

from .textutils import split_sentences, tokenize_words

DUONG_LUAT = Path(__file__).resolve().parents[2] / "rules" / "deai_en.csv"

# Ky tu vo hinh hay bi nhet vao van ban may sinh (zero-width, word-joiner, BOM).
# Ponytail bac 6: MOT dong regex thay vi chep 724 dong text_unicode.py — kich ban
# do chinh app sinh qua API, do that 21/08 ra 0 carrier. Tran da biet: khong bat
# homoglyph/bidi; gap ca do that thi moi nang cap.
KY_TU_AN = re.compile(r"[​-‏⁠-⁯﻿]")
EM_DASH = re.compile(r"[—–]")

# Nguong nhip — chi dung khi KHONG co exemplar de so (ho so hong). Deu tu so do that.
CAU_CUT_TU = 8          # < 8 tu = cau cut
CAU_DAI_TU = 25         # > 25 tu = cau dai
NHAN_DONG_TAC = "dong tac may"   # nhan trong CSV cho cac cach thuc hien khac
DONG_TAC_SACH = 4.0              # ngan sach GOP /1000 tu (van NGUOI do ra ~0,2)
DONG_TAC_NANG = 8.0
EM_DASH_SACH = 3.0      # <= 3/1000 tu: trong vung van nguoi (do: exemplar A013 = 1,4)
EM_DASH_NANG = 8.0      # > 8/1000: dam dac may (do: ban that A011 = 8-13)
MAT_DO_SACH = 2.0       # tong trong so cum sao tren 1000 tu
MAT_DO_NANG = 6.0
# KHONG co nguong tuyet doi cho burstiness_cv — DA THU VA BAC BO 21/08/2026:
# ban may do duoc 0,51-0,67 nen tuong "cv thap = may", nhung do lai chinh exemplar
# NGUOI viet ra 0,36-0,60 (A004 0,36 · A013 0,42 · A012 0,51 · A011 0,60) — vi mau
# ngan lien mach thi phuong sai von thap. So cv giua mau ngan va bai dai la so sanh
# hai thu khac nhau. cv van duoc BAO CAO nhu so mo ta, KHONG dung de phan benh.


def doc_luat(duong: str | Path | None = None) -> list[dict]:
    """Doc bo luat cum sao tu CSV. Thieu file -> tra rong (chay duoc, chi bao thieu luat)."""
    p = Path(duong or DUONG_LUAT)
    if not p.exists():
        return []
    luat = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for d in csv.DictReader(f):
            mau = (d.get("mau_regex") or "").strip()
            if not mau or mau.startswith("#"):
                continue
            try:
                rx = re.compile(mau, re.IGNORECASE)
            except re.error:
                continue          # dong hong trong Excel khong duoc giet ca bo luat
            luat.append({
                "rx": rx,
                "mau": mau,
                "nhan": (d.get("nhan") or "cum sao").strip(),
                "trong_so": float(d.get("trong_so") or 1),
                "goi_y_sua": (d.get("goi_y_sua") or "").strip(),
            })
    return luat


def _vi_tri_dong(text: str, chi_so: int) -> int:
    return text.count("\n", 0, chi_so) + 1


def cham_dau_vet_may(text: str, luat: list[dict] | None = None) -> dict:
    """NHOM A — dau vet may tuyet doi. Tra mat do tren 1000 tu + tung hit co vi tri.

    KHONG tra "diem 0-100": mat do la so DOC DUOC va so sanh duoc giua cac ban,
    con diem tong hop la con so khong ai kiem chung duoc (bai hoc bang 1 Phu luc C).
    """
    luat = doc_luat() if luat is None else luat
    so_tu = len(tokenize_words(text)) or 1
    ngan = so_tu / 1000

    hits: list[dict] = []
    tong_ts = 0.0
    for l in luat:
        for m in l["rx"].finditer(text):
            hits.append({"nhan": l["nhan"], "cum": m.group(0), "dong": _vi_tri_dong(text, m.start()),
                         "goi_y": l["goi_y_sua"]})
            tong_ts += l["trong_so"]

    an = KY_TU_AN.findall(text)
    n_em = len(EM_DASH.findall(text))
    mat_do = tong_ts / ngan
    md_em = n_em / ngan

    # NGAN SACH DONG TAC (22/08): dem GOP ca ho — em-dash CONG voi cac cach thuc
    # hien khac cua cung mot dong tac tu tu (nhan "dong tac may" trong CSV). Do
    # that: cha em-dash o Dot 1 thi "Here is what" 0->3, "Then there is" 0->2,
    # tuc nang luong chui sang cho khac. Dem tung ky tu thi bao cao thap hon
    # thuc te; dem gop moi kiem duoc.
    n_dt = n_em + sum(1 for h in hits if h["nhan"] == NHAN_DONG_TAC)
    md_dt = n_dt / ngan

    if an or md_dt > DONG_TAC_NANG or mat_do > MAT_DO_NANG:
        muc = "nang"
    elif md_dt > DONG_TAC_SACH or mat_do > MAT_DO_SACH:
        muc = "canh_bao"
    else:
        muc = "dat"

    hits.sort(key=lambda h: h["dong"])
    return {
        "muc": muc,
        "mat_do_cum": round(mat_do, 2),
        "em_dash_tren_1000_tu": round(md_em, 2),
        "em_dash_so_luong": n_em,
        "dong_tac_tren_1000_tu": round(md_dt, 2),
        "dong_tac_so_luong": n_dt,
        "ky_tu_an": len(an),
        "so_hit": len(hits),
        "hits": hits[:200],           # tran payload — bang UI khong can hon
        "so_luat": len(luat),
    }


def do_nhip(text: str) -> dict:
    """Chi so nhip thuan (dung chung cho ban viet va cho exemplar lam chuan)."""
    cau = split_sentences(text)
    do_dai = [len(tokenize_words(c)) for c in cau]
    do_dai = [d for d in do_dai if d]
    if not do_dai:
        return {"so_cau": 0, "tu_moi_cau": 0.0, "ti_le_cut": 0.0, "ti_le_dai": 0.0, "burstiness_cv": 0.0}
    tb = statistics.mean(do_dai)
    return {
        "so_cau": len(do_dai),
        "tu_moi_cau": round(tb, 1),
        "ti_le_cut": round(100 * sum(1 for d in do_dai if d < CAU_CUT_TU) / len(do_dai), 1),
        "ti_le_dai": round(100 * sum(1 for d in do_dai if d > CAU_DAI_TU) / len(do_dai), 1),
        "burstiness_cv": round((statistics.pstdev(do_dai) / tb) if tb else 0.0, 2),
    }


def cham_nhip(text: str, profile: dict | None = None, soi: dict | None = None) -> dict:
    """NHOM B — nhip, so voi exemplar cua CHINH ho so khi con tin duoc.

    Ho so hong (soi['do_duoc'] False) hoac khong co profile -> `chuan=None`:
    tra so do + nhan xet MO TA, tuyet doi khong phan "benh" (khong baseline thi
    khong ket luan — cung luat voi engine chan doan).
    """
    do = do_nhip(text)
    chuan = None
    if profile and (soi is None or soi.get("do_duoc")):
        mau = [e for e in (profile.get("exemplars") or []) if isinstance(e, str)][:3]
        if mau:
            c = do_nhip(" ".join(mau))
            if c["so_cau"] >= 5:      # duoi 5 cau thi chuan khong dang tin
                chuan = c

    nx: list[str] = []
    if chuan:
        lech = do["tu_moi_cau"] - chuan["tu_moi_cau"]
        if chuan["tu_moi_cau"] and abs(lech) / chuan["tu_moi_cau"] >= 0.25:
            huong = "VUN HON" if lech < 0 else "NHOI HON"
            nx.append(f"Cau {huong} giong tac gia: {do['tu_moi_cau']} tu/cau so voi "
                      f"{chuan['tu_moi_cau']} cua exemplar ({lech:+.1f}).")
        if do["ti_le_cut"] > chuan["ti_le_cut"] * 1.5 and do["ti_le_cut"] >= 20:
            nx.append(f"Cau cut {do['ti_le_cut']}% — exemplar chi {chuan['ti_le_cut']}%. "
                      "Day la benh 'doc nhu liet ke'.")
    else:
        nx.append("Chua co chuan giong dang tin de doi chieu — cac so duoi chi la MO TA, "
                  "khong phai ket luan.")

    return {"chi_so": do, "chuan": chuan, "nhan_xet": nx}


def cham_giong(text: str, profile: dict | None = None, soi: dict | None = None) -> dict:
    """NHOM C — % bam giong tac gia, dung evaluate_script san co cua app.

    CUA CHAN (ly do ton tai cua ham nay): ho so dung tren corpus transcript tho co
    reproduction_targets vo nghia (vd sentence_len_mean = 1085). Cham bang no thi
    van "diem khong duoc tut" se phan bay — ban sach bi danh truot, ban vun duoc cho
    dat. Tha khong cham con hon cham bang so rac.
    """
    if not profile:
        return {"trang_thai": "khong_ho_so", "ly_do": "Chua chon ho so giong."}
    if soi is not None and not soi.get("do_duoc"):
        return {"trang_thai": "khong_du_co_so",
                "ly_do": "Ho so nay dung tren corpus thieu dau cau — moi target giong "
                         "deu khong dung. Dung lai ho so roi hay cham."}
    targets = profile.get("reproduction_targets") or {}
    if not targets:
        return {"trang_thai": "khong_du_co_so", "ly_do": "Ho so chua co reproduction_targets."}

    from .validate import evaluate_script
    kq = evaluate_script(text, targets)
    return {"trang_thai": "da_cham", "phan_tram": kq["percent"], "dat": kq["n_pass"],
            "tong": kq["n_total"], "targets": kq["targets"], "so_tu": kq["script_words"]}


def kiem_chung(text: str, profile: dict | None = None, luat: list[dict] | None = None) -> dict:
    """Cham TRON MOT ban -> 3 nhom + ket luan. Day la ham UI/route goi."""
    from .soi_ho_so import soi_profile
    soi = soi_profile(profile) if profile else None

    a = cham_dau_vet_may(text, luat)
    b = cham_nhip(text, profile, soi)
    c = cham_giong(text, profile, soi)

    ket: list[str] = []
    if a["ky_tu_an"]:
        ket.append(f"Co {a['ky_tu_an']} ky tu vo hinh — go truoc khi dang.")
    if a["muc"] == "nang":
        ket.append(f"Dau vet may DAM: {a['so_hit']} cum sao, em-dash {a['em_dash_tren_1000_tu']}/1000 tu.")
    elif a["muc"] == "canh_bao":
        ket.append(f"Con dau vet may: {a['so_hit']} cum sao, em-dash {a['em_dash_tren_1000_tu']}/1000 tu.")
    ket += b["nhan_xet"]
    if c["trang_thai"] == "da_cham":
        ket.append(f"Bam giong tac gia {c['phan_tram']}% ({c['dat']}/{c['tong']} target).")
    else:
        ket.append(c["ly_do"])
    if soi and not soi.get("neo_du"):
        ket.append("Neo giong cua ho so nay mong — van ra de roi ve nhip mac dinh cua model.")

    return {"dau_vet_may": a, "nhip": b, "giong": c, "ho_so": soi, "ket_luan": ket,
            "so_tu": len(tokenize_words(text))}
