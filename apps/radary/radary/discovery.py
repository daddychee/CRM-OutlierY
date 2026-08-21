# -*- coding: utf-8 -*-
"""DISCOVERY — thu tin hieu CAU: nguoi ta dang GO gi tren YouTube quanh mot seed.

Vi sao co module nay (docs/discovery-mapping.md): pipeline lam outline cua Content
Ultimate la INWARD-LOOKING — moi thu deu den tu competitive set da chon, khong co
nguon nao tu ngoai. RadarY giu ve CUNG (31.917 video) nhung chua bao gio hoi ve CAU.

VAN CHONG BIA SO 1 (khong duoc pha): autocomplete chi noi "CO NGUOI GO cum nay",
KHONG noi bao nhieu nguoi. Google khong cong bo con so. Moi "search volume" suy ra
tu day deu la bia. Module nay chi tra ve thu DEM DUOC:
  - do_phu : cum xuat hien o BAO NHIEU bien the seed (a-z, tu de hoi)
  - hang_tb: hang trung binh trong danh sach goi y (1 = dau bang)
  - hn_bai / hn_diem: so bai + diem tren Hacker News (nguon PHU, lech tep)

RATE-LIMIT BAT BUOC: autocomplete dung CHUNG IP voi harvest cua RadarY va voi
youtube-transcript-api cua Content Ultimate. App da tung dinh "Sign in to confirm
you're not a bot" tren VPS. Mac dinh <= 1 loi goi/giay, tran 60 loi goi/phien.
"""
from __future__ import annotations

import json
import re
import statistics
import time
import urllib.parse
import urllib.request

YT_SUGGEST = "https://suggestqueries.google.com/complete/search"
HN_SEARCH = "https://hn.algolia.com/api/v1/search"

NGHI_GIAY = 1.0          # >= 1 loi goi/giay (xem docstring)
TRAN_LOI_GOI = 60        # tran cho mot phien quet
HET_GIO = 10             # timeout moi loi goi
UA = "Mozilla/5.0 (compatible; OUTLIERY-RadarY/1.0)"

# Bien the seed: chu cai + tu de hoi. Do that 21/08: seed HEP ("life in tuvalu")
# chi tra 1 goi y, seed RONG ("life in") tra 10 -> phai mo rong seed moi co tin hieu.
CHU_CAI = "abcdefghijklmnopqrstuvwxyz"
TU_HOI = ("what", "why", "how", "when", "where", "which", "is", "does", "can")


class BoDem:
    """Dem loi goi + gian nhip. Tach ra thanh lop de test khong phai cho that."""

    def __init__(self, tran=TRAN_LOI_GOI, nghi=NGHI_GIAY, dong_ho=time.time, ngu=time.sleep):
        self.tran, self.nghi, self.dong_ho, self.ngu = tran, nghi, dong_ho, ngu
        self.da_goi = 0
        self._lan_cuoi = 0.0

    def xin_phep(self) -> bool:
        if self.da_goi >= self.tran:
            return False
        cho = self.nghi - (self.dong_ho() - self._lan_cuoi)
        if cho > 0:
            self.ngu(cho)
        self._lan_cuoi = self.dong_ho()
        self.da_goi += 1
        return True


def _tai(url: str, doc=None) -> str:
    if doc is not None:
        return doc(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=HET_GIO) as r:
        return r.read().decode("utf-8", "replace")


def chuan_hoa(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def goi_y_youtube(cum: str, doc=None) -> list[str]:
    """Mot loi goi autocomplete -> danh sach goi y (thu tu = hang, 0 la dau bang).

    Endpoint tra JSON dang ["query", ["goi y 1", ...], [], {...}]. Loi mang / JSON
    hong -> tra RONG, khong nem: mot seed chet khong duoc giet ca phien quet.
    """
    url = f"{YT_SUGGEST}?{urllib.parse.urlencode({'client': 'firefox', 'ds': 'yt', 'q': cum})}"
    try:
        d = json.loads(_tai(url, doc))
    except (OSError, ValueError):
        return []
    if not isinstance(d, list) or len(d) < 2 or not isinstance(d[1], list):
        return []
    return [chuan_hoa(x) for x in d[1] if isinstance(x, str) and chuan_hoa(x)]


def bien_the_seed(seed: str, chu_cai=True, tu_hoi=True) -> list[str]:
    """Seed -> danh sach truy van con. Seed tran ludn duoc hoi truoc tien."""
    seed = chuan_hoa(seed)
    if not seed:
        return []
    ra = [seed]
    if chu_cai:
        ra += [f"{seed} {c}" for c in CHU_CAI]
    if tu_hoi:
        ra += [f"{t} {seed}" for t in TU_HOI]
    return ra


def mo_rong(seed: str, dem: BoDem | None = None, doc=None,
            chu_cai=True, tu_hoi=True) -> dict[str, dict]:
    """Seed -> {cum: {do_phu, hang_tb, hang_tot_nhat, tu_bien_the[]}}.

    do_phu = so BIEN THE seed ma cum xuat hien. Day la tin hieu dem duoc thay cho
    "volume" (thu khong ai co). Cum lot ra tu nhieu huong go khac nhau = cum nguoi
    ta go that, khong phai duoi cua mot truy van don le.
    """
    dem = dem or BoDem()
    thu: dict[str, list[int]] = {}
    goc: dict[str, list[str]] = {}
    for bt in bien_the_seed(seed, chu_cai, tu_hoi):
        if not dem.xin_phep():
            break
        for hang, g in enumerate(goi_y_youtube(bt, doc)):
            thu.setdefault(g, []).append(hang + 1)
            goc.setdefault(g, []).append(bt)
    return {
        cum: {
            "do_phu": len(hangs),
            "hang_tb": round(statistics.mean(hangs), 2),
            "hang_tot_nhat": min(hangs),
            "tu_bien_the": sorted(set(goc[cum]))[:5],
        }
        for cum, hangs in thu.items()
    }


def hacker_news(cum: str, doc=None) -> dict:
    """Nguon PHU: so bai + tong diem tren HN. Lech tep (dan cong nghe) — chi tham khao."""
    url = f"{HN_SEARCH}?{urllib.parse.urlencode({'query': cum, 'hitsPerPage': 20})}"
    try:
        d = json.loads(_tai(url, doc))
    except (OSError, ValueError):
        return {"hn_bai": 0, "hn_diem": 0}
    hits = d.get("hits") or []
    return {"hn_bai": int(d.get("nbHits") or len(hits)),
            "hn_diem": sum(int(h.get("points") or 0) for h in hits)}


def loc_nhieu(cums: dict[str, dict], seed: str, chan: tuple[str, ...] = ()) -> dict[str, dict]:
    """Bo cum lac de. Do that 21/08: seed 'life in' tra ve 'life in prison roblox',
    'life incremental roblox' — nhieu game lot vao ngach du lich.

    Luat toi thieu, con lai de user gat tay (A3): (1) phai CHUA seed hoac mot tu cua
    seed; (2) khong chua tu trong danh sach chan cua workspace.
    """
    tu_seed = {t for t in chuan_hoa(seed).split() if len(t) > 2}
    ra = {}
    for cum, v in cums.items():
        tu = set(cum.split())
        if tu_seed and not (tu_seed & tu):
            continue
        if any(chuan_hoa(x) and chuan_hoa(x) in cum for x in chan):
            continue
        ra[cum] = v
    return ra


def quet(seed: str, chan: tuple[str, ...] = (), lay_hn=False, dem: BoDem | None = None,
         doc=None, **kw) -> list[dict]:
    """Mot phien quet cho MOT seed -> danh sach cum kem tin hieu, sap theo do_phu.

    Tra list (khong phai dict) vi day la thu di thang vao bang keyword_stats.
    """
    dem = dem or BoDem()
    cums = loc_nhieu(mo_rong(seed, dem, doc, **kw), seed, chan)
    ra = []
    for cum, v in cums.items():
        muc = {"cum": cum, "seed": chuan_hoa(seed), "nguon": "autocomplete", **v}
        if lay_hn and dem.xin_phep():
            muc.update(hacker_news(cum, doc))
        ra.append(muc)
    ra.sort(key=lambda m: (-m["do_phu"], m["hang_tb"]))
    return ra
