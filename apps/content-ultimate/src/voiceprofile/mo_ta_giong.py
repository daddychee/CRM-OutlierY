# -*- coding: utf-8 -*-
"""MO TA GIONG VAN + HUONG DAN DUNG (24/08/2026 — Owner yeu cau).

Owner: "can mot doan mo ta giong van, va huong dan su dung: dung de cho noi dung gi,
set up mood gi, atmosphere ra sao."

Bao cao extract tra loi duoc "giong nay do ra bao nhieu" nhung KHONG tra loi duoc
"nen dung giong nay cho viec gi" — con so 14,3 tu moi cau khong noi cho nguoi bien
tap biet ho nen giao kich ban tu lieu hay kich ban quang cao cho giong nay. Do la
viec cua chu, khong phai cua so, nen day la cho DUY NHAT trong author extract ma LLM
duoc noi thanh loi.

Vi the van o day phai chat hon moi cho khac:
  1. Ho so CHUA DO DUOC (corpus mong) -> khong goi model. Mo ta dua tren so do chua
     tin duoc thi cung khong tin duoc, ma no lai doc nhu mot ket luan chac chan.
  2. LLM chi duoc nhan SO DA DO + DOAN VAN THAT + signature moves da kiem chung.
     Prompt cam bia so; bao cao luu kem `so_do_neo` de nguoi doc doi chieu tung con
     so trong loi van voi so Python da do.
  3. Phan nao LLM tra ve rong thi BO HAN, khong giu chu lung lo cho du khuon.
  4. Loi goi model KHONG duoc lam hong extract — tra ly do, ho so van dung duoc.
"""
from __future__ import annotations

from typing import Callable

TRAN_KY_TU = 600          # moi phan la mot doan cho nguoi doc, khong phai bai luan
SO_DOAN_MAU = 3
TRAN_DOAN_MAU = 900       # ky tu moi doan mau gui kem

PHAN = ("tom_tat", "dung_cho", "mood", "atmosphere", "khong_hop")

SCHEMA = {
    "type": "object",
    "properties": {p: {"type": "string"} for p in PHAN},
    "required": list(PHAN),
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

    Do that 24/08: ban dau tien cho ra cau "Cau trung binh 14,2936 tu nhung bien thien
    manh (9,1934)" — bon chu so thap phan trong mot doan van la rac, va no di thang vao
    bao cao cho nguoi bien tap doc.
    """
    if x is None:
        return None
    return round(x * 100) if phan_tram else round(x, n)


def du_lieu_neo(profile: dict) -> dict:
    """Nhung gi LLM duoc nhin: so DA DO, doan van THAT, moves DA KIEM CHUNG."""
    cs = profile.get("corpus_stats") or {}
    mau = [e for e in (profile.get("exemplars") or []) if isinstance(e, str)][:SO_DOAN_MAU]
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
        "moves": [str(m.get("move", "")).strip()
                  for m in (profile.get("signature_moves") or []) if isinstance(m, dict)],
    }


def build_prompt(d: dict, author: str) -> str:
    so = "\n".join(f"- {k}: {v}" for k, v in d["so_do"].items() if v is not None)
    mau = "\n\n".join(f"[{i}] {m}" for i, m in enumerate(d["doan_mau"], 1))
    moves = "\n".join(f"- {m}" for m in d["moves"] if m)
    return (
        f"You are briefing an editor who has to decide what kind of script to hand to "
        f"the writing voice of {author}.\n\n"
        "MEASURED NUMBERS (computed by our own code over this author's corpus — these "
        "are the ONLY numbers that exist; do not invent, round differently, or add any "
        "figure that is not in this list):\n"
        f"{so}\n\n"
        "VERBATIM PASSAGES from the author's real work:\n"
        f"{mau}\n\n"
        + (f"VERIFIED RHETORICAL MOVES:\n{moves}\n\n" if moves else "")
        + "Numbers named phan_tram_* are percentages, and moi_1000_tu are counts "
        "per 1000 words. Quote a number only where it explains something, and always "
        "write it in DIGITS exactly as given (14.3, 26%) — never spell a number out in "
        "words.\n\n"
        + "Write a short brief IN VIETNAMESE with exactly these five fields:\n"
        "- tom_tat: what this voice sounds like, 2-3 sentences. Ground every claim in "
        "the numbers or the passages above.\n"
        "- dung_cho: what kind of content this voice fits — genre, format, subject "
        "matter. Be concrete (\"tư liệu địa lý, kể chuyện có mốc thời gian\"), not vague "
        "(\"nội dung chất lượng cao\").\n"
        "- mood: the emotional register to set up when writing in this voice.\n"
        "- atmosphere: the sensory world it builds — light, space, pace, distance from "
        "the subject.\n"
        "- khong_hop: what this voice is a bad fit for, and why.\n\n"
        "Rules: write for a working editor, not a critic. No praise, no adjectives that "
        "could describe any competent writer. If the numbers do not support a claim, "
        "leave it out. Use only the numbers given above, and only where they actually "
        "explain something."
    )


def chuan_hoa(raw: dict) -> dict:
    """Giu cac phan CO NOI DUNG; cat theo tran. Phan rong -> bo han (khong giu chu
    lung lo cho du khuon: mot dong 'mood: —' trong bao cao chi lam nguoi doc mat thi gio)."""
    ra = {}
    for p in PHAN:
        v = raw.get(p)
        if isinstance(v, str) and v.strip():
            ra[p] = _cat_gon(v.strip())
    return ra


def _cat_gon(v: str) -> str:
    """Cat theo tran nhung o RANH GIOI CAU, lui ve ranh gioi TU neu khong co cau nao.

    Van PHONG NGUA: 12 ban sinh that 24/08 deu duoi tran (dai nhat 291 ky tu) nen chua
    ai cham vao no. Nhung `[:600]` tho thi khi cham se cat giua tu, va doan mo ta cut
    giua tu doc nhu loi hong chu khong nhu chu y cat ngan.
    """
    if len(v) <= TRAN_KY_TU:
        return v
    dau = max(v.rfind(c, 0, TRAN_KY_TU + 1) for c in ".!?")
    if dau >= TRAN_KY_TU // 2:
        return v[:dau + 1]
    cach = v.rfind(" ", 0, TRAN_KY_TU)
    return (v[:cach] if cach > 0 else v[:TRAN_KY_TU]).rstrip(" ,;:-") + "…"


def du_co_so(profile: dict) -> tuple[bool, str]:
    """Co du can cu de noi gi ve giong nay khong (van chong bia)."""
    cs = profile.get("corpus_stats") or {}
    if (cs.get("n_stability_units") or 0) < 3:
        return False, ("Hồ sơ chưa đủ điểm đo (corpus mỏng) — số đo chưa chứng minh được "
                       "là ổn định, nên chưa mô tả giọng. Nạp thêm tác phẩm rồi chạy lại.")
    if not [e for e in (profile.get("exemplars") or []) if isinstance(e, str)]:
        return False, "Hồ sơ chưa có đoạn văn mẫu nào để dẫn chứng."
    if _gia_tri(profile, "sentence_len_mean") is None:
        return False, "Hồ sơ chưa đo được nhịp câu."
    return True, ""


def sinh_mo_ta(profile: dict, llm_json: Callable[[str, dict], dict]) -> dict:
    """Tra {"mo_ta": {...}} hoac {"ly_do": "..."} — KHONG bao gio nem ra ngoai.

    Loi goi model khong duoc lam hong extract: ho so van dung duoc de viet, chi thieu
    doan mo ta (cung luat voi tao_ban_dep ben ai-agent).
    """
    ok, ly_do = du_co_so(profile)
    if not ok:
        return {"ly_do": ly_do}
    d = du_lieu_neo(profile)
    try:
        raw = llm_json(build_prompt(d, profile.get("author") or "this author"), SCHEMA)
    except Exception as e:  # noqa: BLE001 — moi loi model deu chi lam MAT doan mo ta
        return {"ly_do": f"Không sinh được mô tả giọng: {e}"}
    mo_ta = chuan_hoa(raw if isinstance(raw, dict) else {})
    if not mo_ta:
        return {"ly_do": "Model trả về rỗng — chưa có mô tả giọng."}
    # So do di KEM loi van: nguoi doc doi chieu duoc tung con so trong doan mo ta voi
    # so Python da do, khong phai tin suong.
    mo_ta["so_do_neo"] = {k: v for k, v in d["so_do"].items() if v is not None}
    return {"mo_ta": mo_ta}


NHAN_VIET = {
    "tom_tat": "Giọng này nghe thế nào",
    "dung_cho": "Dùng cho nội dung gì",
    "mood": "Mood cần set",
    "atmosphere": "Atmosphere",
    "khong_hop": "Không hợp với",
}


def dong_markdown(mo_ta: dict) -> list[str]:
    """Doan mo ta cho bao cao .md."""
    ra = []
    for k, nhan in NHAN_VIET.items():
        if mo_ta.get(k):
            ra.append(f"**{nhan}.** {mo_ta[k]}")
    return ra
