# -*- coding: utf-8 -*-
"""MO TA GIONG VAN + HUONG DAN DUNG (24/08/2026 — Owner yeu cau).

Owner vong 1: "can mot doan mo ta giong van, va huong dan su dung: dung de cho noi
dung gi, set up mood gi, atmosphere ra sao."
Owner vong 2: "phan mo ta giong va cach dung van chua du chi tiet."

Thieu that su o vong 1 khong phai la CHU ma la NGUYEN LIEU: ban do chi doc so nhip va
so ngoi, trong khi ho so da san co 8 signature moves KEM TRICH DAN DA KIEM CHUNG va ca
tap doan van that — khong cai nao duoc dung. Vong 2 nay dung BA KHOI theo ba nguoi doc
khac nhau (Owner chot):

  A. NHAN RA GIONG   (nguoi CHON giong)   dinh danh + ky thuat co dan chung + nghe thu
  B. GIAO VIEC       (nguoi BIEN TAP)     dung cho / khong hop / mood / atmosphere
  C. VIET THEO GIONG (nguoi VIET)         cach mo · chuyen doan · ket · von tu · chi lenh

VAN — chat hon moi cho khac trong app, vi day la cho DUY NHAT LLM noi thanh loi:
  1. Ho so chua du diem do -> KHONG goi model.
  2. LLM chi nhan SO DA DO + CAU VAN THAT (moves evidence, khuon van, exemplar).
  3. Moi vi du trong phan "ky thuat" bi Python DOI CHIEU voi kho cau da cung cap —
     vi du bia bi loai khoi ky thuat do (khuon ground_moves cua rhetoric.py).
  4. Phan nao rong thi bo han; loi goi model khong duoc lam hong extract.
"""
from __future__ import annotations

import re
from typing import Callable

TRAN_KY_TU = 600          # muc dai (dung_cho, khong_hop...) — mot doan cho nguoi doc
TRAN_NGAN = 200           # muc mot dong (chi lenh, ten ky thuat...)
SO_DOAN_MAU = 3
TRAN_DOAN_MAU = 900
SO_KY_THUAT = 5
MIN_KY_TU_TRICH = 20      # trich qua ngan thi khop tam thuong, khong tinh la dan chung

PHAN_VAN = ("dinh_danh", "dung_cho", "khong_hop", "mood", "atmosphere",
            "cach_mo", "cach_chuyen", "cach_ket", "tu_nen_dung")
PHAN_DAI = ("dinh_danh", "dung_cho", "khong_hop")

SCHEMA = {
    "type": "object",
    "properties": {
        **{p: {"type": "string"} for p in PHAN_VAN},
        "ky_thuat": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ten": {"type": "string"}, "vi_du": {"type": "string"}},
                "required": ["ten", "vi_du"],
                "additionalProperties": False,
            },
        },
        "chi_lenh": {"type": "array", "items": {"type": "string"}},
    },
    "required": list(PHAN_VAN) + ["ky_thuat", "chi_lenh"],
    "additionalProperties": False,
}


def _gia_tri(profile: dict, ten: str):
    for f in profile.get("quant_features") or []:
        if isinstance(f, dict) and f.get("name") == ten:
            return f.get("value")
    return None


def _chieu(profile: dict, ten: str):
    c = ((profile.get("discourse_features") or {}).get("chieu") or {}).get(ten) or {}
    return c.get("target")


def _lam_tron(x, n=1, phan_tram=False):
    """So dua cho LLM phai o dang NGUOI DOC duoc.

    Do that 24/08: ban dau tien cho ra "Cau trung binh 14,2936 tu nhung bien thien
    manh (9,1934)" — bon chu so thap phan trong mot doan van la rac, va no di thang
    vao bao cao cho nguoi bien tap doc.
    """
    if x is None:
        return None
    return round(x * 100) if phan_tram else round(x, n)


def du_lieu_neo(profile: dict, kv: dict | None = None) -> dict:
    """Nhung gi LLM duoc nhin: so DA DO + cau van THAT + moves DA KIEM CHUNG.

    `kv` la ket qua khuon_van.khuon(corpus) — cach mo/chuyen/ket/cum tu do tren corpus
    that. Khong co thi khoi C thieu nguyen lieu va cac muc do se bi bo.
    """
    cs = profile.get("corpus_stats") or {}
    mau = [e for e in (profile.get("exemplars") or []) if isinstance(e, str)][:SO_DOAN_MAU]
    moves = []
    for m in profile.get("signature_moves") or []:
        if isinstance(m, dict) and str(m.get("move", "")).strip():
            moves.append({"move": str(m["move"]).strip(),
                          "evidence": [str(e) for e in (m.get("evidence") or [])[:2]]})
    return {
        "so_do": {
            "tu_moi_cau": _lam_tron(_gia_tri(profile, "sentence_len_mean")),
            "do_gian_cau": _lam_tron(_gia_tri(profile, "sentence_len_stdev")),
            "phan_tram_cau_ngan": _lam_tron(_gia_tri(profile, "sentence_short_ratio"), phan_tram=True),
            "phan_tram_cau_dai": _lam_tron(_gia_tri(profile, "sentence_long_ratio"), phan_tram=True),
            "da_dang_tu_vung": _lam_tron(_gia_tri(profile, "ttr"), 2),
            "de_doc_flesch": _lam_tron(_gia_tri(profile, "flesch_reading_ease"), 0),
            "goi_ban_doc_moi_1000_tu": _lam_tron(_chieu(profile, "ngoi_thu_hai")),
            "xung_toi_moi_1000_tu": _lam_tron(_chieu(profile, "ngoi_thu_nhat_it")),
            "xung_chung_ta_moi_1000_tu": _lam_tron(_chieu(profile, "ngoi_thu_nhat_nhieu")),
            "phan_tram_cau_hoi": _lam_tron(_chieu(profile, "cau_hoi"), phan_tram=True),
            "phan_tram_cau_mo_bang_lien_tu": _lam_tron(_chieu(profile, "lien_tu_mo_cau"), phan_tram=True),
            "so_tu_corpus": cs.get("n_tokens"),
        },
        "doan_mau": [m[:TRAN_DOAN_MAU] for m in mau],
        "moves": moves,
        "khuon": kv or {},
    }


def _khoi_khuon(kv: dict) -> str:
    """Nguyen lieu cho khoi C — toan cau van THAT do Python rut tu corpus."""
    if not kv:
        return ""
    ra = []
    m = kv.get("mo_dau") or {}
    if m.get("du_mau") and m.get("cau"):
        ra.append("OPENING SENTENCES actually used by this author (one per work; "
                  f"{m.get('ti_le_cau_hoi', 0)}% are questions, "
                  f"{m.get('ti_le_co_so', 0)}% contain a number):\n"
                  + "\n".join(f"- {c}" for c in m["cau"]))
    cd = kv.get("chuyen_doan") or {}
    if cd.get("du_mau") and cd.get("hay_dung"):
        ra.append("PARAGRAPH-OPENING WORDS, with share of paragraphs and a real example:\n"
                  + "\n".join(f'- "{x["tu"]}" ({x["phan_tram"]}%): {x["vi_du"]}'
                              for x in cd["hay_dung"]))
    k = kv.get("ket") or {}
    if k.get("du_mau") and k.get("cau"):
        ra.append("CLOSING SENTENCES actually used:\n"
                  + "\n".join(f"- {c}" for c in k["cau"]))
    td = kv.get("tu_dac_trung") or []
    if td:
        ra.append("RECURRING PHRASES (times used / works they appear in): "
                  + ", ".join(f'"{x["cum"]}" ({x["so_lan"]}/{x["so_van_ban"]})' for x in td))
    return "\n\n".join(ra)


def build_prompt(d: dict, author: str) -> str:
    so = "\n".join(f"- {k}: {v}" for k, v in d["so_do"].items() if v is not None)
    mau = "\n\n".join(f"[{i}] {m}" for i, m in enumerate(d["doan_mau"], 1))
    moves = "\n".join(
        f"- {m['move']}"
        + "".join(f"\n    evidence: {e}" for e in m["evidence"])
        for m in d["moves"])
    khuon = _khoi_khuon(d.get("khuon") or {})
    return (
        f"You are writing the working brief for the prose voice of {author}. Two people "
        "read it: an editor deciding what to commission, and a writer who must produce a "
        "script in this voice without opening the corpus.\n\n"
        "MEASURED NUMBERS (computed by our own code over this author's corpus — the ONLY "
        "numbers that exist; never invent one, never re-round):\n"
        f"{so}\n\n"
        "VERBATIM PASSAGES from the real work:\n"
        f"{mau}\n\n"
        + (f"RHETORICAL MOVES already verified against the corpus:\n{moves}\n\n" if moves else "")
        + (f"{khuon}\n\n" if khuon else "")
        + "Numbers named phan_tram_* are percentages, moi_1000_tu are counts per 1000 "
        "words. Write every number in DIGITS exactly as given — never spell one out. "
        "NEVER print a field name (phan_tram_cau_hoi, da_dang_tu_vung, de_doc_flesch…) "
        "in the Vietnamese text: say what it means (\"chỉ 2% số câu là câu hỏi\"), not "
        "what our code calls it.\n\n"
        "Write the brief IN VIETNAMESE, as JSON with these fields:\n"
        "A. RECOGNISING THE VOICE\n"
        "- dinh_danh: one sentence naming what this voice IS. No praise words.\n"
        f"- ky_thuat: up to {SO_KY_THUAT} techniques. Each has `ten` (the technique in "
        "Vietnamese, concrete enough that a writer can follow it) and `vi_du` — a "
        "sentence COPIED EXACTLY from the material above. Every example is checked "
        "mechanically against the source; an invented one disqualifies its technique.\n"
        "B. COMMISSIONING\n"
        "- dung_cho: genre, format and subject matter this voice fits. Concrete.\n"
        "- khong_hop: what it is a bad fit for, and the number that says so.\n"
        "- mood: the emotional register to set up.\n"
        "- atmosphere: the sensory world — light, space, pace, distance from subject.\n"
        "C. WRITING IN IT\n"
        "- cach_mo: how this author opens a piece, drawn from the opening sentences above.\n"
        "- cach_chuyen: how paragraphs are joined.\n"
        "- cach_ket: how a piece ends.\n"
        "- tu_nen_dung: vocabulary and phrasing to lean on, and what to avoid.\n"
        "- chi_lenh: exactly 3 short imperative rules a writer can follow, each carrying "
        "a measured number (rhythm, person, density).\n\n"
        "Rules: write for working colleagues, not critics. No adjective that could "
        "describe any competent writer. If a claim is not supported by a number or a "
        "passage above, leave it out."
    )


def _squash(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def _kho_cau(d: dict) -> list[str]:
    """Moi cau van THAT da dua cho model — de doi chieu vi du no tra ve."""
    ra = list(d.get("doan_mau") or [])
    for m in d.get("moves") or []:
        ra += list(m.get("evidence") or [])
    kv = d.get("khuon") or {}
    ra += list((kv.get("mo_dau") or {}).get("cau") or [])
    ra += list((kv.get("ket") or {}).get("cau") or [])
    ra += [x.get("vi_du", "") for x in ((kv.get("chuyen_doan") or {}).get("hay_dung") or [])]
    return [x for x in ra if x]


def _cat_gon(v: str, tran: int = TRAN_KY_TU) -> str:
    """Cat theo tran nhung o RANH GIOI CAU, lui ve ranh gioi TU neu khong co cau nao.

    Van PHONG NGUA: cac ban sinh that 24/08 deu duoi tran (dai nhat 291 ky tu) nen chua
    ai cham vao no. Nhung `[:600]` tho thi khi cham se cat giua tu.
    """
    v = (v or "").strip()
    if len(v) <= tran:
        return v
    dau = max(v.rfind(c, 0, tran + 1) for c in ".!?")
    if dau >= tran // 2:
        return v[:dau + 1]
    cach = v.rfind(" ", 0, tran)
    return (v[:cach] if cach > 0 else v[:tran]).rstrip(" ,;:-") + "…"


def chuan_hoa(raw: dict, kho_cau: list[str] | None = None) -> dict:
    """Giu phan CO NOI DUNG, cat gon, va LOAI ky thuat co vi du khong doi chieu duoc."""
    raw = raw if isinstance(raw, dict) else {}
    ra: dict = {}
    for p in PHAN_VAN:
        v = raw.get(p)
        if isinstance(v, str) and v.strip():
            ra[p] = _cat_gon(v, TRAN_KY_TU if p in PHAN_DAI else TRAN_NGAN * 2)

    nguon = [_squash(c) for c in (kho_cau or [])]
    ky = []
    for m in raw.get("ky_thuat") or []:
        if not isinstance(m, dict):
            continue
        ten, vd = str(m.get("ten") or "").strip(), str(m.get("vi_du") or "").strip()
        if not ten or not vd:
            continue
        k = _squash(vd)
        # Van chong bia: vi du phai la van THAT da nam trong tap gui cho model.
        if nguon and (len(k) < MIN_KY_TU_TRICH or not any(k in n for n in nguon)):
            continue
        ky.append({"ten": _cat_gon(ten, TRAN_NGAN), "vi_du": _cat_gon(vd, TRAN_NGAN + 100)})
        if len(ky) >= SO_KY_THUAT:
            break
    if ky:
        ra["ky_thuat"] = ky

    cl = [_cat_gon(str(x).strip(), TRAN_NGAN) for x in (raw.get("chi_lenh") or [])
          if str(x).strip()]
    if cl:
        ra["chi_lenh"] = cl[:3]
    return ra


# CUA VAO (Owner 24/08: "neu ho so nao khong du dieu kien, dung chay. Bao toi bo sung
# them mau."). Hai nguong, moi cai co ly do do duoc:
#   MIN_TU_MO_TA  duoi 12.000 tu thi so chi so ON DINH rot xuong con 5-6/20 (do that
#                 tren kho 24/08) — mo ta dung tren nen do la mo ta mot phong doan.
#   MIN_DIEM_DO   duoi 3 diem do thi khong noi duoc gi ve do on dinh (luat C1).
# Thieu TAC PHAM thi KHONG chan: A002 co 1 tac pham nhung 53.530 tu / 14 diem do — so
# do rat tin duoc, chi thieu khuon mo bai va ket bai. Chan han la phi mot ho so tot;
# chay nhung bao ro muc nao se khuyet.
MIN_TU_MO_TA = 12000
MIN_DIEM_DO = 3
MIN_TAC_PHAM_KHUON = 3


def du_co_so(profile: dict) -> tuple[bool, str]:
    """Co du can cu de noi gi ve giong nay khong (van chong bia)."""
    cs = profile.get("corpus_stats") or {}
    tu = cs.get("n_tokens") or 0
    if (cs.get("n_stability_units") or 0) < MIN_DIEM_DO:
        return False, ("Hồ sơ chưa đủ điểm đo — số đo chưa chứng minh được là ổn định, "
                       "nên chưa mô tả giọng. Nạp thêm tác phẩm rồi chạy lại.")
    if tu < MIN_TU_MO_TA:
        return False, (f"Corpus mới {tu:,} từ — cần thêm khoảng {MIN_TU_MO_TA - tu:,} từ "
                       f"nữa mới đủ để mô tả giọng. Dưới {MIN_TU_MO_TA:,} từ thì chỉ "
                       "khoảng 5-6 trên 20 chỉ số đạt ngưỡng ổn định, mô tả dựng trên nền "
                       "đó là mô tả một phỏng đoán.").replace(",", ".")
    if not [e for e in (profile.get("exemplars") or []) if isinstance(e, str)]:
        return False, "Hồ sơ chưa có đoạn văn mẫu nào để dẫn chứng."
    if _gia_tri(profile, "sentence_len_mean") is None:
        return False, "Hồ sơ chưa đo được nhịp câu."
    return True, ""


def sinh_mo_ta(profile: dict, llm_json: Callable[[str, dict], dict],
               kv: dict | None = None) -> dict:
    """Tra {"mo_ta": {...}} hoac {"ly_do": "..."} — KHONG bao gio nem ra ngoai.

    Loi goi model khong duoc lam hong extract: ho so van dung duoc de viet, chi thieu
    doan mo ta (cung luat voi tao_ban_dep ben ai-agent).
    """
    ok, ly_do = du_co_so(profile)
    if not ok:
        # Khai RO thieu gi va thieu bao nhieu — de goi ben ngoai bao thang cho nguoi
        # dung "bo sung them mau", khong bat ho tu doan tu mot cau van.
        cs = profile.get("corpus_stats") or {}
        tu = cs.get("n_tokens") or 0
        ra = {"ly_do": ly_do}
        if tu < MIN_TU_MO_TA and (cs.get("n_stability_units") or 0) >= MIN_DIEM_DO:
            ra["thieu"], ra["can_them_tu"] = "so_tu", MIN_TU_MO_TA - tu
        elif (cs.get("n_stability_units") or 0) < MIN_DIEM_DO:
            ra["thieu"] = "diem_do"
        return ra
    d = du_lieu_neo(profile, kv)
    try:
        raw = llm_json(build_prompt(d, profile.get("author") or "this author"), SCHEMA)
    except Exception as e:  # noqa: BLE001 — moi loi model deu chi lam MAT doan mo ta
        return {"ly_do": f"Không sinh được mô tả giọng: {e}"}
    mo_ta = chuan_hoa(raw, _kho_cau(d))
    if not mo_ta:
        return {"ly_do": "Model trả về rỗng — chưa có mô tả giọng."}
    # So do di KEM loi van: nguoi doc doi chieu duoc tung con so trong doan mo ta voi
    # so Python da do, khong phai tin suong.
    mo_ta["so_do_neo"] = {k: v for k, v in d["so_do"].items() if v is not None}
    ra = {"mo_ta": mo_ta}
    # Du tu nhung it tac pham: chay duoc, nhung khuon mo bai / ket bai khong co nghia
    # (mot tac pham thi khong goi la thoi quen) — bao ro thay vi de nguoi doc tu hoi
    # sao muc do bien mat.
    n_tp = (profile.get("corpus_stats") or {}).get("n_works") or 0
    if n_tp < MIN_TAC_PHAM_KHUON:
        ra["khuyet"] = (f"Corpus chỉ có {n_tp} tác phẩm — mục Cách mở bài và Cách kết bị "
                        f"bỏ (cần từ {MIN_TAC_PHAM_KHUON} tác phẩm mới gọi là thói quen). "
                        "Các mục khác không bị ảnh hưởng.")
    return ra


# Ba khoi, dung thu tu nguoi doc gap: nhan ra giong -> giao viec -> viet theo giong.
KHOI = (
    ("Nhận ra giọng", ("dinh_danh", "ky_thuat")),
    ("Giao việc", ("dung_cho", "khong_hop", "mood", "atmosphere")),
    ("Viết theo giọng", ("cach_mo", "cach_chuyen", "cach_ket", "tu_nen_dung", "chi_lenh")),
)
NHAN_VIET = {
    "dinh_danh": "Giọng này là gì",
    "ky_thuat": "Kỹ thuật đặc trưng",
    "dung_cho": "Dùng cho nội dung gì",
    "khong_hop": "Không hợp với",
    "mood": "Mood cần set",
    "atmosphere": "Atmosphere",
    "cach_mo": "Cách mở bài",
    "cach_chuyen": "Cách chuyển đoạn",
    "cach_ket": "Cách kết",
    "tu_nen_dung": "Vốn từ nên dùng",
    "chi_lenh": "Ba chỉ lệnh khi viết",
}


def dong_markdown(mo_ta: dict) -> list[str]:
    """Ba khoi cho bao cao .md."""
    ra: list[str] = []
    for ten_khoi, khoa in KHOI:
        than: list[str] = []
        for k in khoa:
            v = mo_ta.get(k)
            if not v:
                continue
            if k == "ky_thuat":
                than.append(f"- **{NHAN_VIET[k]}:**")
                than += [f"    - {x['ten']} — *“{x['vi_du']}”*" for x in v]
            elif k == "chi_lenh":
                than.append(f"- **{NHAN_VIET[k]}:**")
                than += [f"    {i}. {x}" for i, x in enumerate(v, 1)]
            else:
                than.append(f"- **{NHAN_VIET[k]}.** {v}")
        if than:
            ra.append(f"### {ten_khoi}")
            ra += than
    return ra
