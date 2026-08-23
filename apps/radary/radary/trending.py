# -*- coding: utf-8 -*-
"""TRENDING — do THI TRUONG tu nguon NGOAI pool (Owner chot 23/08/2026).

Phuong phap luan day du: `trending_methodology.md`. Tom tat vi sao module nay ton tai:

  Pool KHONG do nhu cau khan gia — no do QUYET DINH cua doi thu. Mot video trong
  pool la bang chung ai do da quyet dinh lam no vai tuan truoc. Do la gioi han CAU
  TRUC, khong tham so nao chinh duoc. Nen muon biet "nen lam de gi" thi phai nhin
  ra NGOAI YouTube.

Phan vai voi mapping.py:
  Trending  -> "CO NEN LAM DE NAY KHONG"      (thi truong)
  Mapping   -> "DOI THU DANG LAM THE NAO"     (pool)

BA LUAT cua module nay:
  1. TU DIEN THUC THE THUOC VE TUNG POOL, khong dung chung. Cung mot chuoi mang
     nghia khac nhau tuy pool ("georgia" = quoc gia hay tieu bang? "jordan" =
     quoc gia hay ten nguoi?). Dung chung la mang nghia pool nay ap len pool kia
     — dung ho su co 21/08 "tu khoa thi truong US lot sang Spain".
  2. NGUONG LAY TU PHAN VI CUA CHINH POOL, khong phai hang so. Do that 23/08:
     nguong co dinh "<=10 video" om 36% thuc the o LIFE IN nhung 60% o TRAVEL DOC
     — cung mot con so noi nguoc nhau.
  3. KHONG LOAI UNG VIEN NAO theo nguong. Bon o chi la THU TU DOC; moi tu khoa la
     mot y tuong rieng (Owner 23/08). Nguoi quyet, may bay bang chung (Nguyen tac 5).

Moi loi goi mang deu qua tham so `doc`/`tai` -> test khong cham mang.
"""
from __future__ import annotations

import json
import re
import statistics
import time
import urllib.error as _ue
import urllib.parse as _up
import urllib.request as _ur
from datetime import datetime, timezone

_UA = {"User-Agent": "OUTLIERY-RadarY/1.0 (nghien cuu noi bo; lien he Owner)"}
WIKI_API = "https://en.wikipedia.org/w/api.php"
GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT DOC API: 1 loi goi / 5 giay (12/phut), va co bao cao bi chan khi goi ~60 lan
# trong 90 phut. Vi vay TUYET DOI khong quet ca tu dien qua duong nay — chi hoi cho
# ung vien NGUOI DUNG BAM. Muon quet hang loat thi phai dung ban tai file tho 15
# phut/lan cua GDELT, va do la ha tang khac.
GDELT_GIAN_CACH = 5.0

O_THIEU_CUNG = "thieu_cung"          # it video, chay tot  -> dang nhin
O_DA_KHAI_THAC = "da_khai_thac"      # nhieu video, chay tot
O_DA_THU = "da_thu"                  # it video, chay kem  -> pool da thu va chet
O_BAO_HOA = "bao_hoa"                # nhieu video, chay kem
O_CHUA_DU = "chua_du"                # duoi MAU_TOI_THIEU video -> khong ket luan
MAU_TOI_THIEU = 5

NHAN_O = {
    O_THIEU_CUNG: ("THIẾU CUNG", "ít video · chạy tốt"),
    O_DA_KHAI_THAC: ("ĐÃ KHAI THÁC", "nhiều video · chạy tốt"),
    O_DA_THU: ("ĐÃ THỬ, KHÔNG ĂN", "ít video · chạy kém"),
    O_BAO_HOA: ("BÃO HOÀ", "nhiều video · chạy kém"),
    O_CHUA_DU: ("CHƯA ĐỦ DẤU VẾT", f"dưới {MAU_TOI_THIEU} video"),
}


def _mien(a: dict) -> str:
    """Ten mien cua bai bao. `toparts` cua timelinevolinfo KHONG luon co khoa
    'domain' (do that 23/08: nguon ra None het) -> rut tu chinh URL."""
    d = a.get("domain") or a.get("sourcecountry_domain") or ""
    if d:
        return d
    try:
        return _up.urlparse(a.get("url") or "").netloc.removeprefix("www.")
    except Exception:                                            # noqa: BLE001
        return ""


_lan_goi_gdelt = [0.0]           # moc lan goi GDELT gan nhat (trong tien trinh)


def _giu_nhip(gian_cach: float = GDELT_GIAN_CACH) -> None:
    """Tu giu khoang cach giua hai loi goi GDELT. Khong co cho nay thi hai lan bam
    lien nhau la an 429 — do that 23/08."""
    cho = gian_cach - (time.time() - _lan_goi_gdelt[0])
    if cho > 0:
        time.sleep(cho)
    _lan_goi_gdelt[0] = time.time()


def _tai_text(url: str, doc=None, het_gio: int = 20) -> str:
    if doc is not None:
        return doc(url)
    with _ur.urlopen(_ur.Request(url, headers=_UA), timeout=het_gio) as r:
        return r.read().decode("utf-8", "replace")


# ==================================================================== TU DIEN
def tu_dien_pool(kho: list[dict], ngon_ngu: str | None = "en",
                 toi_thieu_video: int = 2) -> list[str]:
    """Thuc the ma CHINH POOL NAY dang lam. Tai dung mapping.doi_tuong (luat tu-loai).

    `so_muc` de rat cao co chu dinh: cat danh sach o day la loai truoc mot tu khoa
    co the la mot y tuong (luat 3).
    """
    from . import mapping
    ds = mapping.doi_tuong(kho, so_muc=100000, toi_thieu_video=toi_thieu_video,
                           ngon_ngu=ngon_ngu)
    return [r["cum"] for r in ds]


# Mo ta Wikipedia phai chua mot trong cac tu nay thi moi coi la THUC THE co the lam
# video ve noi chon. Danh sach nay la LUAT NGOAI CODE trong tuong lai (moi ngach mot
# bo); hien de mac dinh cho ngach noi-chon.
LA_NOI_CHON = re.compile(
    r"\b(country|island|city|nation|state|region|territory|republic|archipelago|"
    r"province|peninsula|capital|town|district|sovereign|municipality|county|"
    r"prefecture|emirate|kingdom|village|commune|atoll)\b", re.I)


def xac_minh_loai(ten_ds: list[str], doc=None, gop: int = 40) -> dict[str, str]:
    """Mo ta ngan cua Wikipedia cho tung ten -> de biet no la LOAI thuc the gi.

    Khong co buoc nay thi tu dien pool lot day DANH TU CHUNG (fire, car, dream,
    price) va moi trend chua mot tu thuong deu khop — da dinh that khi dung thu
    23/08. Gop 40 ten mot loi goi.

    Tra {ten_thuong: mo_ta}; ten khong tra duoc -> khong co khoa (KHAC voi mo_ta rong).
    """
    ra: dict[str, str] = {}
    for i in range(0, len(ten_ds), gop):
        lo = [t for t in ten_ds[i:i + gop] if t]
        if not lo:
            continue
        q = _up.urlencode({"action": "query", "format": "json", "prop": "pageterms",
                           "redirects": "1", "titles": "|".join(x.title() for x in lo)})
        try:
            d = json.loads(_tai_text(f"{WIKI_API}?{q}", doc))
        except Exception:                                    # noqa: BLE001
            continue                                         # mat mot lo, khong sap ca ham
        chuan = {v.get("to", "").lower(): v.get("from", "").lower()
                 for v in (d.get("query", {}).get("normalized") or [])}
        for pg in (d.get("query", {}).get("pages") or {}).values():
            t = (pg.get("title") or "").lower()
            ra[chuan.get(t, t)] = " ".join((pg.get("terms") or {}).get("description") or [])
    return ra


def loc_thuc_the(ten_ds: list[str], mo_ta: dict[str, str],
                 luat: re.Pattern = LA_NOI_CHON) -> tuple[list[str], list[tuple[str, str]]]:
    """Tach (giu, bo). `bo` kem mo ta de nguoi doc hieu vi sao bi loai — khong im lang."""
    giu, bo = [], []
    for t in ten_ds:
        m = mo_ta.get(t) or ""
        if m and luat.search(m):
            giu.append(t)
        else:
            bo.append((t, m))
    return giu, bo


# ============================================================ HO SO TRONG POOL
def ho_so_pool(kho: list[dict], cum: str, bay_gio: float | None = None,
               so_thang: int = 12) -> dict | None:
    """Pool nay noi ve `cum` bao nhieu, chay the nao, nhip theo thang.

    Doi hoi moi ban ghi co `title_l`, `pub_ts`, `vpd` (view/ngay) — dung
    chuan_hoa_kho() de dung. Duoi 2 video -> None (khong du de noi gi).
    """
    bay_gio = bay_gio or time.time()
    rx = re.compile(r"\b" + re.escape(cum) + r"\b", re.I)
    hit = [r for r in kho if rx.search(r["title_l"])]
    if len(hit) < 2:
        return None
    moc = [datetime.fromtimestamp(bay_gio - i * 30.4 * 86400, timezone.utc).strftime("%Y-%m")
           for i in range(so_thang - 1, -1, -1)]
    dem: dict[str, int] = {}
    for r in hit:
        k = datetime.fromtimestamp(r["pub_ts"], timezone.utc).strftime("%Y-%m")
        dem[k] = dem.get(k, 0) + 1
    return {"cum": cum, "n": len(hit),
            "vpd": statistics.median(r["vpd"] for r in hit),
            "nhip": [dem.get(k, 0) for k in moc],
            "moi_nhat_ngay": int((bay_gio - max(r["pub_ts"] for r in hit)) / 86400)}


def chuan_hoa_kho(kho: list[dict], bay_gio: float | None = None) -> list[dict]:
    """Them title_l + vpd. Bo ban ghi thieu view hoac thieu ngay dang (KHONG coi la 0)."""
    bay_gio = bay_gio or time.time()
    ra = []
    for r in kho:
        if not r.get("title") or not r.get("views") or not r.get("pub_ts"):
            continue
        tuoi = max(1.0, (bay_gio - r["pub_ts"]) / 86400)
        ra.append({**r, "title_l": r["title"].lower(), "vpd": r["views"] / tuoi})
    return ra


def nguong_pool(ho_so_ds: list[dict], tv_pool: float) -> dict:
    """Nguong bon o = PHAN VI CUA CHINH POOL (luat 2), khong phai hang so.

    Tra ca cac phan vi khac de UI hien duoc "can cu vao dau" — nguoi doc phai thay
    duong nguong den tu dau chu khong phai tin loi may.
    """
    if not ho_so_ds:
        return {"du_mau": False, "ly_do": "Pool chưa có thực thể nào đủ 2 video."}
    sv = sorted(h["n"] for h in ho_so_ds)
    bs = sorted(h["vpd"] / tv_pool for h in ho_so_ds if tv_pool)
    q = lambda a, p: a[int(p * (len(a) - 1))]                     # noqa: E731
    return {"du_mau": True, "so_thuc_the": len(ho_so_ds), "tv_pool": tv_pool,
            "video_tv": q(sv, .5), "video_p25": q(sv, .25), "video_p75": q(sv, .75),
            "boi_tv": round(q(bs, .5), 2), "boi_p75": round(q(bs, .75), 2),
            "boi_p90": round(q(bs, .90), 2)}


def xep_o(h: dict, ng: dict) -> str:
    """Bon o + o 'chua du dau vet'. KHONG loai gi — day chi la thu tu doc (luat 3)."""
    if h["n"] < MAU_TOI_THIEU:
        return O_CHUA_DU
    it = h["n"] <= ng["video_tv"]
    tot = (h["vpd"] / ng["tv_pool"]) >= ng["boi_p75"] if ng.get("tv_pool") else False
    if it:
        return O_THIEU_CUNG if tot else O_DA_THU
    return O_DA_KHAI_THAC if tot else O_BAO_HOA


# ================================================================ QUET NGOAI
def khop_tu_dien(trends: list[dict], tu_dien: list[str]) -> dict[str, dict]:
    """Trend nao nhac toi thuc the pool nay dang lam. Uu tien ban ghi CON MO CUA SO.

    `trends`: [{'cum':..., 'luong':..., 'bat_dau':..., 'con_mo':bool, 'breakdown':[...]}]
    """
    rx = {t: re.compile(r"\b" + re.escape(t) + r"\b", re.I) for t in tu_dien}
    ra: dict[str, dict] = {}
    for tr in trends:
        kw = (tr.get("cum") or "").lower()
        for t, r in rx.items():
            if not r.search(kw):
                continue
            # DO CHAC CUA PHEP NOI: thuc the chiem bao nhieu phan cua cum trend.
            #   "guyana"       trong "guyana"                    -> 1.00  chac
            #   "dream"        trong "atlanta dream"             -> 0.50  ngo
            #   "jordan"       trong "jordan spieth comments..." -> 0.20  gan chac la nham
            # KHONG loai (luat 3) — phoi ra de nguoi doc tu thay, vi cung mot chuoi
            # co the la ten nuoc that trong mot trend khac.
            do_chac = round(len(t) / max(1, len(kw)), 2)
            muc = {**tr, "khop_voi": tr.get("cum"), "do_chac": do_chac}
            if t not in ra or tr.get("con_mo") or do_chac > ra[t].get("do_chac", 0):
                ra[t] = muc
            break
    return ra


def doc_trending_csv(dong: list[dict]) -> list[dict]:
    """Dich CSV 'Trending Now' cua Google ve dang trong nha.

    Cot Ended rong/'nan' = CUA SO CON MO — doc thang, khong phai tu suy.
    Cot Trend breakdown = truy van con, tuc NGUYEN NHAN: `peru` -> 'picchu' (to mo
    du lich) khac han `oman` -> 'trump oman' (dia chinh tri).
    """
    ra = []
    for r in dong:
        cum = (r.get("Trends") or "").strip()
        if not cum:
            continue
        bd = [x.strip() for x in (r.get("Trend breakdown") or "").split(",") if x.strip()]
        ra.append({"cum": cum, "luong": (r.get("Search volume") or "").strip(),
                   "bat_dau": (r.get("Started") or "").strip(),
                   "con_mo": (r.get("Ended") or "nan").strip().lower() in ("nan", ""),
                   "breakdown": bd[1:]})            # bo phan tu dau = chinh cum do
    return ra


# ======================================================= VI SAO NONG (GDELT)
def vi_sao_nong(cum: str, doc=None, ngay: int = 30, tran_bai: int = 8) -> dict:
    """Vi sao thuc the nay dang nong — hoi GDELT DOC API (0 khoa, 0 dong).

    Lap chinh cho lo hong da do 23/08: trend ten-nuoc-tro-troi khong kem breakdown
    nen KHONG biet nguyen nhan (`guyana` dang mo cua so ma mu tit).

    Mot loi goi duy nhat, mode=timelinevolinfo: vua duong khoi luong tin theo ngay
    VUA top bai bao tao ra cu nho — vat kiet moi lan goi (cung tinh than serp.py).
    Loi/khong co du lieu -> tra co_du_lieu=False KEM LY DO, tuyet doi khong tra rong
    de nguoi (hay AI) doc nham thanh "khong co tin gi".
    """
    q = _up.urlencode({"query": f'"{cum}"', "mode": "timelinevolinfo",
                       "format": "json", "timespan": f"{ngay}d"})
    if doc is None:
        _giu_nhip()
    try:
        raw = _tai_text(f"{GDELT_DOC}?{q}", doc)
    except _ue.HTTPError as e:
        # 429 la ca RAT hay gap (do that 23/08: ba loi goi lien tiep -> 429 het).
        # Phai noi RO la bi chan nhip, khong duoc gop chung vao "loi HTTP" —
        # nguoi doc se di sua nham cho, dung ho su co 29/07 "Z.ai het tien bi bao
        # nham la khong lay duoc phu de".
        if e.code == 429:
            return {"co_du_lieu": False, "bi_chan_nhip": True,
                    "ly_do": f"GDELT chặn nhịp gọi (1 lời gọi/{GDELT_GIAN_CACH:.0f} giây) "
                             "— chờ rồi bấm lại"}
        return {"co_du_lieu": False, "ly_do": f"GDELT lỗi HTTP {e.code}"}
    except Exception as e:                                       # noqa: BLE001
        return {"co_du_lieu": False, "ly_do": f"GDELT lỗi: {type(e).__name__}"}
    try:
        d = json.loads(raw)
    except Exception:                                            # noqa: BLE001
        # GDELT tra HTML khi bi chan nhip — noi thang thay vi im lang
        return {"co_du_lieu": False,
                "ly_do": "GDELT trả về không phải JSON (thường là bị chặn nhịp gọi)"}
    loat = (d.get("timeline") or [{}])[0].get("data") or []
    if not loat:
        return {"co_du_lieu": False, "ly_do": f"GDELT không có tin nào về “{cum}” trong {ngay} ngày"}
    # LUU Y DON VI: timelinevolinfo tra khoi luong duoi dang PHAN TRAM tong tin GDELT
    # theo doi, KHONG phai so bai. Goi no la "tin" la ghi nhan sai — do that 23/08
    # thay 0.6547 bi in ra thanh "0.6547 tin".
    diem = [{"ngay": (x.get("date") or "")[:8], "phan_tram": x.get("value") or 0} for x in loat]
    dinh = max(loat, key=lambda x: x.get("value") or 0)
    bai = [{"tieu_de": a.get("title"), "nguon": _mien(a), "link": a.get("url")}
           for a in (dinh.get("toparts") or [])[:tran_bai]]
    return {"co_du_lieu": True, "diem": diem, "so_ngay": ngay, "don_vi": "phần trăm tổng tin",
            "dinh_ngay": (dinh.get("date") or "")[:8],
            "dinh_phan_tram": round(dinh.get("value") or 0, 4), "bai": bai,
            "ghi_chu": None if bai else "GDELT có đường khối lượng nhưng không kèm bài báo nào"}


# =========================================================== VIEC CHAY NEN
# Khuon giong niche_report.py: trang thai trong kv (khong de bang moi), mot luong
# moi workspace, dang chay thi tu choi luot moi.
import threading                                                 # noqa: E402

_luong: dict[int, threading.Thread] = {}
KHOA_KQ = "trending_ket_qua"
KHOA_TT = "trending_trang_thai"
KHOA_CHON = "trending_da_chon"


def trang_thai(conn, ws: int) -> dict | None:
    from . import db
    return db.kv_get(conn, ws, KHOA_TT, None)


def ket_qua(conn, ws: int) -> dict | None:
    from . import db
    return db.kv_get(conn, ws, KHOA_KQ, None)


def da_chon(conn, ws: int) -> dict:
    """So ghi §10 methodology: ung vien nao NGUOI DA CHON lam. Vế nay khong tu suy
    duoc — phai co nguoi tick. Sau vai thang no la thu duy nhat tra loi duoc cau
    "di som co thang khong" bang du lieu nha."""
    from . import db
    return db.kv_get(conn, ws, KHOA_CHON, {})


def dat_chon(conn, ws: int, cum: str, chon: bool, boi_canh: dict | None = None) -> dict:
    from . import db
    s = da_chon(conn, ws)
    if chon:
        s[cum] = {"luc": time.time(), **(boi_canh or {})}
    else:
        s.pop(cum, None)
    with conn:
        db.kv_set(conn, ws, KHOA_CHON, s)
    return s


def _ghi_tt(conn, ws, **kw):
    from . import db
    with conn:
        db.kv_set(conn, ws, KHOA_TT, {"ts": time.time(), **kw})


def bat_dau(ws: int, geo: str, gio: int = 168) -> bool:
    """Khoi dong quet nen. False neu workspace nay dang co luot chay."""
    t = _luong.get(ws)
    if t and t.is_alive():
        return False
    t = threading.Thread(target=_chay, args=(ws, geo, gio), daemon=True,
                         name=f"trending-{ws}")
    _luong[ws] = t
    t.start()
    return True


def tai_trending_now(geo: str = "US", gio: int = 168) -> list[dict]:
    """Danh sach DANG LEN cua Google. Tach rieng de test thay duoc bang ham gia.

    trendspyg doc endpoint khong co tai lieu chinh thuc nen fragile (do that trong
    serp.py: 43% thanh cong). Loi -> nem, de tang tren ghi ly do that vao trang thai
    chu KHONG tra danh sach rong (rong se bi doc nham thanh 'khong co trend nao').
    """
    from trendspyg import download_google_trends_csv
    d = download_google_trends_csv(geo=geo, hours=gio, category="all",
                                   output_format="dict", headless=True)
    ds = d if isinstance(d, list) else (d.get("trends") or d.get("data") or [])
    return doc_trending_csv(ds)


def _chay(ws: int, geo: str, gio: int, tai=None, doc=None) -> None:
    from . import db
    conn = db.connect()
    try:
        _ghi_tt(conn, ws, state="running", buoc="đọc pool")
        tho = [dict(r) for r in conn.execute(
            """SELECT v.title, v.pub_ts,
                 (SELECT views FROM ticks t WHERE t.video_id=v.id ORDER BY ts DESC LIMIT 1) views
               FROM videos v WHERE v.workspace_id=?""", (ws,))]
        kho = chuan_hoa_kho(tho)
        if len(kho) < 50:
            _ghi_tt(conn, ws, state="error",
                    ly_do=f"Pool chỉ có {len(kho)} video đủ số liệu — chưa đủ để dựng từ điển.")
            return
        tv_pool = statistics.median(r["vpd"] for r in kho)

        _ghi_tt(conn, ws, state="running", buoc="dựng từ điển thực thể của pool")
        td = tu_dien_pool(kho)

        _ghi_tt(conn, ws, state="running", buoc=f"quét Google Trending Now ({geo})")
        trends = (tai or tai_trending_now)(geo, gio)

        _ghi_tt(conn, ws, state="running", buoc="khớp từ điển + xác minh loại")
        ung = khop_tu_dien(trends, td)
        mo_ta = xac_minh_loai(sorted(ung), doc=doc)
        giu, bo = loc_thuc_the(sorted(ung), mo_ta)

        _ghi_tt(conn, ws, state="running", buoc="đối chiếu pool")
        may = [h for h in (ho_so_pool(kho, t) for t in td) if h]
        ng = nguong_pool(may, tv_pool)
        uv = []
        for t in giu:
            h = ho_so_pool(kho, t)
            if not h:
                continue
            tr_ = ung[t]
            h.update({"o": xep_o(h, ng), "boi": round(h["vpd"] / tv_pool, 2),
                      "mo": tr_.get("con_mo"), "luong": tr_.get("luong", ""),
                      "bat_dau": tr_.get("bat_dau", ""), "vi_sao": tr_.get("breakdown", [])[:3],
                      "do_chac": tr_.get("do_chac", 1.0), "khop_voi": tr_.get("khop_voi", t),
                      "mo_ta": mo_ta.get(t, "")})
            uv.append(h)

        from . import db as _db
        with conn:
            _db.kv_set(conn, ws, KHOA_KQ, {
                "luc": time.time(), "geo": geo, "gio": gio,
                "so_tho": len(trends), "so_khop": len(ung), "so_may": len(may),
                "tv_pool": round(tv_pool, 2), "nguong": ng,
                "dam_may": [{"n": m["n"], "boi": round(m["vpd"] / tv_pool, 3)} for m in may],
                "ung_vien": uv,
                "da_loai": [{"cum": t, "mo_ta": m} for t, m in bo]})
        _ghi_tt(conn, ws, state="done", so_ung_vien=len(uv), so_loai=len(bo))
    except Exception as e:                                       # noqa: BLE001
        # Ly do THAT vao trang thai — khong nuot thanh "khong co trend nao"
        _ghi_tt(conn, ws, state="error", ly_do=f"{type(e).__name__}: {e}"[:300])
    finally:
        conn.close()
