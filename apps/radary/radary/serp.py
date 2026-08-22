# -*- coding: utf-8 -*-
"""SERP — doc trang ket qua tim kiem qua API thue (Owner chot 22/08).

VI SAO CAN: Google Trends dang chay qua trinh duyet (trendspyg) chi thanh cong
43% — do that tren ban luu: 9 co du lieu / 4 rate-limit / 8 loi tren 21 lan goi.
API SERP tra Trends on dinh trong ~2s, va TIEN THE mo them nguon that su moi.

KIEN TRUC 2 LOI GOI MOI CUM (Owner chot — quota free ~100/thang la rang buoc
chinh, phai vat kiet moi lan goi):
  goi 1  engine=google_trends  -> duong quan tam 12 thang + truy van len/pho bien
                                  + interest by region (moi)
  goi 2  engine=google         -> MOT lan lay ba khoi: people_also_ask (cau hoi
                                  that -> y tuong video) + related_searches +
                                  organic_results (dien dan/bao tu lo ra)

NHIEU NHA, MOT GIAO DIEN: serpapi / serper / searchapi tra JSON khac nhau; lop
nay dich ve MOT dang de app khong biet dang goi nha nao. Het quota nha A thi
xoay sang khoa ke tiep (cung khuon scan.API xoay 19 khoa YouTube).

VAN CHONG BIA: khong co khoa / het quota / nha loi -> tra co_du_lieu=False kem
LY DO that, KHONG bao gio tra khoi rong nhu the khong co du lieu.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

# Nha nao goi kieu nao — them nha chi them mot muc o day.
GOC = {
    "serpapi": "https://serpapi.com/search.json",
    "serper": "https://google.serper.dev",
    "searchapi": "https://www.searchapi.io/api/v1/search",
}
HET_QUOTA = (401, 402, 403, 429)     # ma HTTP coi la "khoa nay het/khong dung duoc"


class HetQuota(Exception):
    """Khoa hien tai het han muc — noi goi xoay sang khoa ke tiep."""


def _tai(url: str, than: dict | None = None, dau: dict | None = None,
         timeout: int = 25) -> dict:
    du_lieu = json.dumps(than).encode() if than is not None else None
    req = urllib.request.Request(url, data=du_lieu, headers={
        "User-Agent": "RadarY/1.0", "Content-Type": "application/json", **(dau or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in HET_QUOTA:
            raise HetQuota(f"HTTP {e.code}") from None
        raise RuntimeError(f"SERP lỗi HTTP {e.code}") from None
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError(f"SERP lỗi {type(e).__name__}") from None


# ---- MOT LOI GOI, DICH VE MOT DANG ------------------------------------------

def _goi(nha: str, khoa: str, engine: str, tham_so: dict) -> dict:
    if nha == "serpapi":
        q = {"api_key": khoa, "engine": engine, **tham_so}
        return _tai(f"{GOC['serpapi']}?{urllib.parse.urlencode(q)}")
    if nha == "searchapi":
        q = {"api_key": khoa, "engine": engine, **tham_so}
        return _tai(f"{GOC['searchapi']}?{urllib.parse.urlencode(q)}")
    if nha == "serper":
        # serper khong co engine trends — chi google search; duong dan theo loai
        duong = "/search" if engine == "google" else None
        if not duong:
            raise RuntimeError(f"Serper.dev không có engine '{engine}'")
        than = {"q": tham_so.get("q", ""), "gl": (tham_so.get("gl") or "us").lower()}
        return _tai(GOC["serper"] + duong, than=than, dau={"X-API-KEY": khoa})
    raise RuntimeError(f"chưa hỗ trợ nhà SERP '{nha}'")


def _so_ngay(chuoi: str) -> str:
    return (chuoi or "")[:10]


def _so(x) -> int:
    """Ep ve so nguyen — nha tra LAN so va chuoi ("100", "<1%", "Breakout").

    Do that 22/08: sort theo gia tri no `bad operand type for unary -: str`.
    Khong doc duoc thi 0 (khong doan bua, chi tut xuong cuoi bang).
    """
    if isinstance(x, (int, float)):
        return int(x)
    so = "".join(ch for ch in str(x or "") if ch.isdigit())
    return int(so) if so else 0


def trends(nha: str, khoa: str, cum: str, geo: str = "US",
           timeframe: str = "today 12-m") -> dict:
    """Google Trends: đường quan tâm + truy vấn lên/phổ biến + theo vùng.

    Trả CÙNG DẠNG với tra_cuu.google_trends cũ để UI không phải sửa gì.
    """
    d = _goi(nha, khoa, "google_trends",
             {"q": cum, "geo": geo, "date": timeframe, "data_type": "TIMESERIES"})
    tho = ((d.get("interest_over_time") or {}).get("timeline_data")) or []
    diem = []
    for p in tho:
        gia = (p.get("values") or [{}])[0].get("extracted_value")
        if gia is not None:
            diem.append({"ngay": _so_ngay(p.get("date") or ""), "gia_tri": _so(gia)})
    if not diem:
        return {"co_du_lieu": False, "geo": geo, "timeframe": timeframe,
                "ly_do": "SERP không trả dữ liệu Trends cho từ khoá này"}
    n = max(1, len(diem) // 4)
    dau = sum(p["gia_tri"] for p in diem[:n]) / n
    cuoi = sum(p["gia_tri"] for p in diem[-n:]) / n
    lech = round(100 * (cuoi - dau) / dau) if dau else 0
    return {"co_du_lieu": True, "geo": geo, "timeframe": timeframe, "diem": diem,
            "nguon": f"serp:{nha}",
            "xu_huong": {"phan_tram": lech,
                         "chieu": "lên" if lech > 15 else "xuống" if lech < -15 else "đi ngang"},
            "rising": [], "top": []}


def truy_van_lien_quan(nha: str, khoa: str, cum: str, geo: str = "US") -> dict:
    """Truy vấn ĐANG LÊN / PHỔ BIẾN — SerpAPI tách thành data_type riêng."""
    d = _goi(nha, khoa, "google_trends",
             {"q": cum, "geo": geo, "data_type": "RELATED_QUERIES"})
    rq = d.get("related_queries") or {}
    lay = lambda ds: [{"cum": x.get("query", ""),
                       "gia_tri": _so(x.get("extracted_value") or x.get("value"))}
                      for x in (ds or []) if x.get("query")]
    return {"rising": lay(rq.get("rising")), "top": lay(rq.get("top"))}


def theo_vung(nha: str, khoa: str, cum: str, geo: str = "US") -> list[dict]:
    """Vùng nào quan tâm nhất — dữ kiện chọn thị trường (mới, chưa từng có)."""
    d = _goi(nha, khoa, "google_trends",
             {"q": cum, "geo": geo, "data_type": "GEO_MAP_0"})
    ra = []
    for x in (d.get("interest_by_region") or []):
        gia = _so(x.get("extracted_value") or x.get("value"))
        if x.get("location") and gia:
            ra.append({"vung": x["location"], "gia_tri": gia})
    return sorted(ra, key=lambda r: -r["gia_tri"])[:10]


def google(nha: str, khoa: str, cum: str, geo: str = "US", lang: str = "en") -> dict:
    """MỘT lời gọi lấy BA khối: câu hỏi thật · tìm kiếm liên quan · kết quả web.

    people_also_ask là thứ đáng giá nhất cho ngách documentary: mỗi câu hỏi là
    một ý tưởng video kèm sẵn tiêu đề — autocomplete chỉ cho cụm ngắn.
    """
    d = _goi(nha, khoa, "google", {"q": cum, "gl": geo.lower(), "hl": lang, "num": 10})
    # Ten khoi PAA khac nhau theo nha (do that 22/08 tren phan hoi SerpAPI: khoi
    # nay ten `related_questions`, KHONG phai `people_also_ask` nhu tai lieu
    # thuong ghi) -> nhan het cac ten da biet, thieu ten nao chi mat khoi do.
    hoi = [x.get("question") or x.get("title") or ""
           for x in (d.get("related_questions") or d.get("people_also_ask")
                     or d.get("peopleAlsoAsk") or [])]
    # DA THU `things_to_know` (di kem cung loi goi, 0 quota them) nhung do that
    # 22/08 no tra ra phan tu giao dien ("buttons") chu khong phai goc chu de —
    # bo, khong nhoi du lieu rac vao UI.
    lq = [(x if isinstance(x, str) else (x.get("query") or x.get("title") or ""))
          for x in (d.get("related_searches") or d.get("relatedSearches") or [])]
    web = []
    for x in (d.get("organic_results") or d.get("organic") or [])[:10]:
        link = x.get("link") or ""
        web.append({"tieu_de": x.get("title") or "", "link": link,
                    "mo_ta": (x.get("snippet") or "")[:200],
                    "nguon": urllib.parse.urlparse(link).netloc.replace("www.", "")})
    return {"co_du_lieu": bool(hoi or lq or web),
            "cau_hoi": [h for h in hoi if h][:10],
            "lien_quan": [x for x in lq if x][:10],
            "web": web, "nguon": f"serp:{nha}"}


# ---- XOAY VONG KHOA + DEM QUOTA ---------------------------------------------

class BoKhoa:
    """Danh sách khoá SERP, xoay khi hết quota — khuôn scan.API của YouTube.

    Đếm số lời gọi ĐÃ TIÊU trong phiên để UI cảnh báo trước khi cụt dữ liệu.
    """

    def __init__(self, khoa: list[dict]):
        # khoa = [{'id','key','nha'}] theo thứ tự cấp phát
        self.khoa = [k for k in (khoa or []) if k.get("key")]
        self.i = 0
        self.da_tieu = 0
        self.het = []                       # id các khoá đã báo hết quota

    def con_khoa(self) -> bool:
        return self.i < len(self.khoa)

    def chay(self, ham, *a, **kw):
        """Gọi `ham(nha, khoa, ...)`, hết quota thì tự sang khoá kế tiếp."""
        while self.i < len(self.khoa):
            k = self.khoa[self.i]
            try:
                ra = ham(k.get("nha") or "serpapi", k["key"], *a, **kw)
                self.da_tieu += 1
                return ra
            except HetQuota:
                self.het.append(k.get("id") or "?")
                self.i += 1
        raise RuntimeError(
            "hết hạn mức mọi khoá SERP" + (f" ({', '.join(self.het)})" if self.het else "")
            + " — thêm khoá ở General › API Keys hoặc đợi sang tháng")
