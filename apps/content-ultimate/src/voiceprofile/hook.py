"""HOOK: luat rieng + sinh nhieu phuong an, MAY cham roi chon (Dot 3, 23/08/2026).

Vi sao tach: hook dang dung chung cong thuc voi chuong thuong nen no khong bao gio
tot len. Dot 22/08 chung minh dieu do bang so — sua neo giong va prompt lam THAN BAI
tot len, nhung hook lai XAU DI vi khong ai dung toi:

  ban cu:  "The most populous country in Central Asia has no coastline."
           -> mot nghich ly TU DUNG DUOC, nguoi nghe buoc phai hoi "tai sao".
  ban moi: "Uzbekistan. That is the name most people cannot find on a map."
           -> goi ten chu de o TU DAU TIEN, tuc DONG vong lap truoc khi mo.

BON LUAT, deu KIEM DUOC BANG MAY (khong phai loi dan):
  1. Cau DAU khong duoc chua ten chu de / ten rieng chinh cua video.
  2. Cam cau dan bao hieu ("Here is what is surprising...") — bat ngo thi noi thang.
  3. Ba cau dau phai co it nhat mot cot moc: con so, hoac tuong phan (no/not/but/yet).
  4. Do dai trong khuon HOOK_CHARS_MIN..MAX (hop dong san co, khong doi).

Sinh N phuong an roi cham, thay vi sinh 1 dung luon. Hook ngan (~250-500 ky tu) nen
N=3 chi ton them ~2 luot re nhat cua ca bai.
"""
from __future__ import annotations

import re

SO_PHUONG_AN = 3

_TU_HOA = re.compile(r"\b([A-Z][a-z]{2,})\b")
_CAU = re.compile(r"[^.!?]*[.!?]+|\S[^.!?]*$")
_DAN_BAO_HIEU = re.compile(r"\b(?:here(?:'s| is| are)|but here(?:'s| is))\s+(?:what|the|why|how)\b", re.I)
_TUONG_PHAN = re.compile(r"\b(?:no|not|never|but|yet|instead|without|nothing|none)\b", re.I)
_SO = re.compile(r"\b\d[\d,.]*\b|\b(?:one|two|three|five|ten|twenty|thirty|fifty|hundred|thousand|million|billion)\b", re.I)


def _cau(t: str) -> list[str]:
    return [c.strip() for c in _CAU.findall(t) if c.strip()]


def tu_khoa_chu_de(title: str, brief: str = "") -> set[str]:
    """Ten rieng chinh cua video — thu ma cau dau KHONG duoc goi ten."""
    ra = set(_TU_HOA.findall(title or ""))
    if not ra and brief:
        # title rong: lay ten rieng xuat hien nhieu nhat trong brief
        dem: dict[str, int] = {}
        for w in _TU_HOA.findall(brief):
            dem[w] = dem.get(w, 0) + 1
        if dem:
            ra = {max(dem, key=dem.get)}
    return ra


def cham(text: str, title: str = "", brief: str = "",
         chars_min: int = 250, chars_max: int = 500) -> dict:
    """Cham mot hook. Tra {"diem": int, "dat": [...], "truot": [...]} — KHONG co
    diem tong an: 'diem' chi la SO LUAT DAT, de xep hang giua cac phuong an."""
    cau = _cau(text)
    dau = cau[0] if cau else ""
    ba_dau = " ".join(cau[:3])
    khoa = tu_khoa_chu_de(title, brief)

    kiem = [
        ("cau dau khong goi ten chu de",
         not (khoa & set(_TU_HOA.findall(dau)))),
        ("khong co cau dan bao hieu",
         not _DAN_BAO_HIEU.search(text)),
        ("ba cau dau co cot moc (so hoac tuong phan)",
         bool(_SO.search(ba_dau) or _TUONG_PHAN.search(ba_dau))),
        ("do dai trong khuon",
         chars_min <= len(text.strip()) <= chars_max),
    ]
    dat = [t for t, ok in kiem if ok]
    truot = [t for t, ok in kiem if not ok]
    return {"diem": len(dat), "dat": dat, "truot": truot, "so_ky_tu": len(text.strip())}


def chon(ban: list[str], title: str = "", brief: str = "",
         chars_min: int = 250, chars_max: int = 500) -> tuple[str, list[dict]]:
    """Chon ban tot nhat trong cac phuong an. Hoa diem thi lay ban NGAN hon
    (hook dai la loi kinh dien). Danh sach rong -> tra ("", [])."""
    ban = [b for b in ban if b and b.strip()]
    if not ban:
        return "", []
    diem = [dict(cham(b, title, brief, chars_min, chars_max), thu_tu=i) for i, b in enumerate(ban)]
    tot = max(range(len(ban)), key=lambda i: (diem[i]["diem"], -len(ban[i])))
    return ban[tot], diem


def khoi_luat() -> str:
    """Khoi luat cho vao prompt hook. Chu chu KHONG dung em-dash (bai hoc 22/08:
    model bat chuoc hinh thuc cua chinh ban huong dan)."""
    return (
        "HOOK RULES (these are hard):\n"
        "- Do NOT name the country, place, or subject in the FIRST sentence. Naming it "
        "closes the curiosity loop before it opens. Open on the paradox itself.\n"
        "- The first sentence must stand on its own as a contradiction or an impossible "
        "sounding fact, so that the listener has to ask why.\n"
        "- Never announce that something surprising is coming. No 'here is what is "
        "surprising', no 'but here is the strange part'. Say the surprising thing.\n"
        "- Within the first three sentences make it clear why a viewer should care.\n"
        "- No long dashes."
    )
