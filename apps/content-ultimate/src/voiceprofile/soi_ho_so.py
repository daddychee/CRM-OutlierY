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
# C1 (24/08): duoi 3 diem do thi do on dinh CHUA DO DUOC (xem profile.MIN_DON_VI_DO).
# Diem do nho nhat la 800 tu, nen corpus duoi 2.400 tu khong the co 3 diem do.
MIN_DON_VI_DO = 3
CORPUS_DU_TU = 2400

# Co nao lam SO DO SAI (khong tin duoc mot con so nao) — liet ke TUONG MINH thay vi
# do tien to "corpus_": cua so mong (corpus_mong, C1) cung bat dau bang "corpus_" nhung
# so do cua no VAN DUNG, chi la chua chung minh duoc on dinh. Gop hai chuyen do lam mot
# thi ho so mong bi coi nhu ho so transcript hong.
CO_LAM_SO_DO_SAI = {"corpus_thieu_dau_cau", "corpus_cau_qua_vun", "exemplar_thieu_dau_cau"}
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
            f"Corpus đo ra {slm:.0f} từ mỗi câu — không thể có thật ở người viết. "
            "Gần như chắc chắn là transcript chưa chấm câu; mọi số đo giọng của "
            "hồ sơ này (độ dài câu, nhịp, Flesch) đều không dùng được."
        )
    elif slm is not None and 0 < slm < CAU_QUA_NGAN:
        co.append("corpus_cau_qua_vun")
        canh_bao.append(f"Corpus đo ra {slm:.1f} từ mỗi câu — vụn bất thường, nên kiểm lại nguồn.")

    if ex["so_mau"] and ex["tu_moi_cau"] > CAU_QUA_DAI:
        co.append("exemplar_thieu_dau_cau")
        canh_bao.append(
            f"Đoạn mẫu đo ra {ex['tu_moi_cau']:.0f} từ mỗi câu — mẫu neo giọng cũng thiếu "
            "dấu câu; model sẽ học thành câu dài vô tận."
        )

    if ex["tong_tu"] < NEO_DU_TU:
        co.append("neo_mong")
        canh_bao.append(
            f"Neo giọng chỉ {ex['tong_tu']} từ ({ex['so_mau']} mẫu) — quá mỏng so với "
            "cả trăm dòng luật trong prompt; model sẽ rơi về nhịp mặc định của nó."
        )
    # Corpus mong: SO DO van dung (van ban co dau cau), nhung KHONG the noi dac trung
    # nao la on dinh — mot diem do khong co phuong sai. Bao rieng, khong lam do_duoc
    # False: hai chuyen khac nhau (so do sai vs so do dung nhung chua chung minh duoc).
    cs = profile.get("corpus_stats") or {}
    n_units = cs.get("n_stability_units")
    n_tu = cs.get("n_tokens")
    if isinstance(n_units, int) and n_units < MIN_DON_VI_DO:
        co.append("corpus_mong")
        thieu = (f", nạp thêm khoảng {CORPUS_DU_TU - n_tu:,} từ nữa".replace(",", ".")
                 if isinstance(n_tu, int) and n_tu < CORPUS_DU_TU else "")
        canh_bao.append(
            f"Corpus chỉ cắt được {n_units} điểm đo"
            + (f" ({n_tu:,} từ)".replace(",", ".") if isinstance(n_tu, int) else "")
            + f" — dưới {MIN_DON_VI_DO} điểm thì độ ổn định CHƯA đo được, mọi con số "
            f"'sai số 0' đều là giả. Số đo vẫn đúng, nhưng đừng tin là chắc chắn{thieu}."
        )

    if ex["trung_lap"]:
        co.append("exemplar_trung_lap")
        canh_bao.append("Các đoạn mẫu trùng nội dung nhau — neo thực tế còn mỏng hơn số từ.")

    return {
        "ten": ten,
        "do_duoc": not (set(co) & CO_LAM_SO_DO_SAI),
        "neo_du": "neo_mong" not in co and "exemplar_trung_lap" not in co,
        "co": co,
        "chi_so": {
            "sentence_len_mean": round(slm, 1) if isinstance(slm, (int, float)) else None,
            "exemplar_so_mau": ex["so_mau"],
            "exemplar_tong_tu": ex["tong_tu"],
            "exemplar_tu_moi_cau": ex["tu_moi_cau"],
            "so_target": len(profile.get("reproduction_targets") or {}),
            "n_stability_units": n_units,
            "corpus_tu": n_tu,
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

# ── Yeu cau hoan thien ho so (24/08) ─────────────────────────────────────────────────
# Owner: "phan luu y nay can dua ra yeu cau de hoan thien ho so (neu co)".
# Canh bao MO TA van de; yeu cau noi NGUOI DUNG PHAI LAM GI. Hai viec khac nhau, va
# "(neu co)" la phan quan trong: van de nao khong sua duoc thi KHONG bia ra viec —
# mot danh sach viec ma lam xong van khong het canh bao thi con te hon khong co.
TU_DU_MO_TA = 12000       # giu bang mo_ta_giong.MIN_TU_MO_TA


def yeu_cau_hoan_thien(soi: dict, canh_bao_them: list[str] | None = None) -> list[str]:
    """Viec cu the de ho so nay day len — rong khi khong con gi de lam."""
    co = set(soi.get("co") or [])
    cs = soi.get("chi_so") or {}
    ra: list[str] = []

    if "corpus_thieu_dau_cau" in co or "exemplar_thieu_dau_cau" in co:
        ra.append("Chấm câu lại file transcript rồi nạp lại, hoặc bỏ file đó khỏi tác "
                  "phẩm — mọi số đo nhịp câu hiện tại đều không dùng được.")
    if "corpus_cau_qua_vun" in co:
        ra.append("Kiểm lại nguồn văn bản: câu vụn bất thường thường là do tách dòng sai "
                  "khi chuyển từ PDF hoặc phụ đề.")

    tu = cs.get("corpus_tu")
    if isinstance(tu, int) and tu < TU_DU_MO_TA:
        ra.append(f"Bổ sung thêm khoảng {TU_DU_MO_TA - tu:,} từ tác phẩm của tác giả này "
                  f"(đang có {tu:,} từ) — đủ {TU_DU_MO_TA:,} từ mới mô tả được giọng."
                  .replace(",", "."))
    elif "corpus_mong" in co:
        ra.append("Bổ sung thêm tác phẩm: corpus chưa cắt được 3 điểm đo nên chưa nói "
                  "được đặc trưng nào là ổn định.")

    for c in (canh_bao_them or []):
        if "dòng trống" in c:
            ra.append("Nạp lại bản thảo có giữ dòng trống giữa các đoạn — bản hiện tại là "
                      "một khối liền nên không đo được độ dài đoạn và cách chuyển đoạn.")
    return ra
