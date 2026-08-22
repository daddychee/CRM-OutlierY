"""Vong SUA O CAP CAU sau khi sinh (Dot 3, 23/08/2026).

Vi sao khong siet bang loi dan nua: do 22/08 cho thay luat "moi doan toi da mot
em-dash" bi vi pham 26-59% — model KHONG tuan luat dem duoc. Nguoc lai, doi thu
model NHIN THAY (go em-dash khoi prompt) thi an ngay 46%. Ket luan: chan bang
LOI thi khong an, do bang MAY sau khi sinh moi kiem duoc.

Vi sao sua o CAP CAU chu khong viet lai ca chuong: dot truoc viet lai TU DAU nen
van muot hon nhung du kien loang di (mat "hon hai nghin tan vang", mat ten Ulugh
Beg, thay so do bang loi khen chung chung, va de ra mot loi sai that ve
Afghanistan). Sua tung cau giu duoc phan con lai nguyen ven.

VAN NHAN (khong qua thi GIU NGUYEN CAU GOC — khong bao gio tra ban hong):
  1. Moi CON SO trong cau goc phai con nguyen trong ban sua.
  2. Moi DANH TU RIENG trong cau goc phai con nguyen.
  3. Do dai chenh khong qua NGUONG_DAI.
  4. Ngan sach dong tac phai GIAM that.
"""
from __future__ import annotations

import re

NGUONG_DAI = 0.35          # ban sua duoc dai/ngan hon toi da 35%
TOI_DA_CAU = 12            # moi luot gui toi da bao nhieu cau (giu prompt gon)

_CAU = re.compile(r"[^.!?]*[.!?]+(?:[\"')\]]+)?|\S[^.!?]*$")
_SO = re.compile(r"\b\d[\d,.]*\b")
# danh tu rieng: chu hoa giua cau (bo tu dau cau va tu sau dau ket)
_HOA = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,})\b", re.M)


def tach_cau(text: str) -> list[str]:
    return [c for c in (m.group(0) for m in _CAU.finditer(text)) if c.strip()]


def _so_trong(s: str) -> set[str]:
    return {x.rstrip(".,") for x in _SO.findall(s)}


def _rieng_trong(s: str) -> set[str]:
    return set(_HOA.findall(s))


def cau_vi_pham(text: str, luat: list[dict], nhan_dong_tac: str = "dong tac may",
                em_dash: str = "—") -> list[tuple[int, str, list[str]]]:
    """Cac cau mang dong tac may. Tra [(chi_so, cau, [ten dong tac])]."""
    ra = []
    for i, c in enumerate(tach_cau(text)):
        vi = []
        if em_dash in c:
            vi.append("dau gach ngang dai")
        for l in luat:
            if l.get("nhan") == nhan_dong_tac and l["rx"].search(c):
                vi.append(l.get("ghi_chu") or l["nhan"])
        if vi:
            ra.append((i, c, vi))
    return ra


def dung_prompt(cau: list[str], giong: str = "") -> tuple[str, str]:
    """Prompt sua cau. CO Y khong dua khoi luat/exemplar vao: viec o day la SUA
    DAU va CAU TRUC cua dung cau nay, khong phai viet lai theo giong."""
    system = (
        "You are a line editor. You are given numbered sentences from a finished "
        "script. Each one leans on a mannerism that makes prose read as machine "
        "written: a long dash splice, a sentence fragment used to flip the previous "
        "claim, or an announcing clause that tells the listener something surprising "
        "is coming.\n"
        "Rewrite each sentence so the mannerism is gone.\n"
        "HARD RULES:\n"
        "- Keep every fact, every number, every proper name exactly as given. Do not "
        "add a fact, do not drop one, do not round a number.\n"
        "- Keep roughly the same length. This is a repair, not a rewrite.\n"
        "- Do not use a long dash. Do not open with an announcing clause.\n"
        "- Return exactly one line per input sentence, numbered the same way, nothing else."
        + (f"\nThe surrounding prose is in this voice: {giong}." if giong else "")
    )
    user = "\n".join(f"{i + 1}. {c.strip()}" for i, c in enumerate(cau))
    return system, user


def doc_tra_loi(raw: str, n: int) -> dict[int, str]:
    """Doc ban sua theo so thu tu. Khoan dung: chap nhan '1.', '1)', '1 -'."""
    ra: dict[int, str] = {}
    for dong in raw.splitlines():
        m = re.match(r"\s*(\d{1,2})\s*[.)\-:]\s*(.+)", dong.strip())
        if m:
            k = int(m.group(1))
            if 1 <= k <= n:
                ra[k - 1] = m.group(2).strip()
    return ra


def nhan_duoc(goc: str, moi: str) -> tuple[bool, str]:
    """Van nhan cho MOT cau. Tra (co_nhan, ly_do_neu_tu_choi)."""
    if not moi or not moi.strip():
        return False, "rong"
    thieu_so = _so_trong(goc) - _so_trong(moi)
    if thieu_so:
        return False, f"roi con so {sorted(thieu_so)}"
    thieu_ten = _rieng_trong(goc) - _rieng_trong(moi)
    if thieu_ten:
        return False, f"roi ten rieng {sorted(thieu_ten)}"
    if abs(len(moi) - len(goc)) / max(1, len(goc)) > NGUONG_DAI:
        return False, f"lech do dai {len(goc)}->{len(moi)}"
    return True, ""


def sua(text: str, llm_text, luat: list[dict], giong: str = "",
        on_progress=None) -> tuple[str, dict]:
    """Sua cac cau mang dong tac may. Tra (van_moi, bao_cao).

    llm_text(system, user, max_tokens) -> str. Loi LLM thi GIU NGUYEN van goc.
    """
    vi_pham = cau_vi_pham(text, luat)
    bao = {"so_cau_vi_pham": len(vi_pham), "so_cau_sua": 0, "tu_choi": []}
    if not vi_pham:
        return text, bao

    lo = vi_pham[:TOI_DA_CAU]
    system, user = dung_prompt([c for _, c, _ in lo], giong)
    try:
        raw = llm_text(system, user, max(1024, sum(len(c) for _, c, _ in lo) * 3))
    except Exception as e:  # noqa: BLE001
        bao["loi"] = str(e)[:200]
        return text, bao

    ban_sua = doc_tra_loi(raw or "", len(lo))
    cau = tach_cau(text)
    for vi, (chi_so, goc, _) in enumerate(lo):
        moi = ban_sua.get(vi)
        if moi is None:
            bao["tu_choi"].append((goc[:60], "khong co ban sua"))
            continue
        ok, ly_do = nhan_duoc(goc.strip(), moi)
        if not ok:
            bao["tu_choi"].append((goc[:60], ly_do))
            continue
        # giu khoang trang dau/cuoi cua cau goc de khong dinh chu
        dau = goc[:len(goc) - len(goc.lstrip())]
        cuoi = goc[len(goc.rstrip()):]
        cau[chi_so] = dau + moi + cuoi
        bao["so_cau_sua"] += 1

    if not bao["so_cau_sua"]:
        return text, bao
    return "".join(cau), bao
