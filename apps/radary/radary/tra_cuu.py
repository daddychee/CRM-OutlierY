# -*- coding: utf-8 -*-
"""TRA CUU MOT TU KHOA -> hai bao cao, theo THI TRUONG cua pool dang mo.

Thay cho ban do 4 o + 300 cum (user bo 21/08: "chi la duplicate cua radary, khong co
gi de make decision"). Mo hinh moi do user chot:

  KHOI A — TRONG POOL (0 quota, doc SQLite):
     xu huong that cua thi truong minh dang theo doi ve tu khoa nay.
  KHOI B — NGOAI (Google Trends + YouTube):
     thien ha dang thinh hanh gi quanh tu khoa nay.

GIOI HAN DU LIEU phai noi truoc (do 21/08): `ticks` chi co 46 ngay, KHONG dung duoc
duong view lich su. Nen "xu huong" khoi A dung theo LUA DANG: video ve tu khoa dang
thang nao an bao nhieu view/ngay — pub_ts co tu 2009 nen nhin duoc 12-24 thang.
Kem velocity 46 ngay cho ngan han (user chot "ca hai").
"""
from __future__ import annotations

import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone

from . import mapping

SO_THANG = 18            # cua so lua dang mac dinh
TOI_THIEU_LUA = 2        # duoi 2 video/thang thi khong lay trung vi (mau qua nho)
MOI_NGAY_B = 90          # "video noi gan day" = dang trong 90 ngay
KENH_NHO_SUBS = 50_000
SHORT_TOI_DA_S = 180     # <= 3 phut coi la Shorts/clip — ngach nay lam video DAI


def _thang(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")


def _view_moi_ngay(v: dict, bay_gio: float) -> float | None:
    """View/ngay ca doi video — cach duy nhat so cong bang giua cac lua khi khong co
    lich su view. Video duoi 7 ngay tuoi bi bo (chua on dinh)."""
    tuoi = (bay_gio - (v.get("pub_ts") or 0)) / 86400
    if tuoi < 7 or not v.get("views"):
        return None
    return v["views"] / tuoi


# Mỗi kênh chỉ đính tối đa ngần này video (bản tra cứu được LƯU vào tra_cuu_log —
# đính hết là sổ phình theo số video của pool).
SO_VIDEO_MOI_KENH = 8


def xu_huong_pool(kho: list[dict], cum: str, so_thang: int = SO_THANG,
                  bay_gio: float | None = None) -> dict:
    """KHOI A — pool dang theo doi lam gi voi tu khoa nay, va xu huong ra sao."""
    bay_gio = bay_gio or time.time()
    rx = mapping._rx(cum)
    khop = [v for v in kho if rx.search(v["title_l"])]
    if not khop:
        return {"co_du_lieu": False,
                "ly_do": "Pool đang mở chưa có video nào khớp từ khoá này."}

    moc = bay_gio - so_thang * 30 * 86400
    lua: dict[str, list[dict]] = {}
    for v in khop:
        if (v.get("pub_ts") or 0) >= moc:
            lua.setdefault(_thang(v["pub_ts"]), []).append(v)

    dong_lua = []
    for th in sorted(lua):
        vs = lua[th]
        vpd = [x for x in (_view_moi_ngay(v, bay_gio) for v in vs) if x]
        dong_lua.append({
            "thang": th, "so_video": len(vs),
            "view_moi_ngay": round(statistics.median(vpd)) if len(vpd) >= TOI_THIEU_LUA else None,
            "du_mau": len(vpd) >= TOI_THIEU_LUA,
        })

    # velocity ngan han (ticks 46 ngay) — so voi TOAN POOL de biet nhanh/cham tuong doi
    vph_cum = [v["vph"] for v in khop if v.get("vph")]
    vph_pool = [v["vph"] for v in kho if v.get("vph")]
    # Kênh nào đẩy chủ đề này — kèm LUÔN video của kênh đó nói về từ khoá. Danh sách
    # video đã nằm sẵn trong `khop` nên đính vào là 0 quota, không thêm lời gọi nào.
    kenh: dict[str, dict] = {}
    for v in khop:
        if (v.get("pub_ts") or 0) >= bay_gio - 365 * 86400:
            k = kenh.setdefault(v["kenh"] or v["kenh_yt"],
                                {"kenh": v["kenh"], "kenh_yt": v.get("kenh_yt") or "",
                                 "so_video": 0, "views": 0, "video": []})
            k["so_video"] += 1
            k["views"] += v.get("views") or 0
            k["video"].append({"yt_id": v["yt_id"], "title": v["title"],
                               "views": v.get("views") or 0, "pub_ts": v.get("pub_ts") or 0})
    for k in kenh.values():
        k["video"].sort(key=lambda x: -x["views"])
        k["video"] = k["video"][:SO_VIDEO_MOI_KENH]        # chặn payload phình
        k["view_tb"] = round(k["views"] / max(1, k["so_video"]))

    moi_nhat = max(khop, key=lambda v: v.get("pub_ts") or 0)
    tong_view_pool = sum(v.get("views") or 0 for v in kho) or 1
    return {
        "co_du_lieu": True,
        "so_video": len(khop),
        "so_kenh": len({v["kenh_yt"] or v["kenh"] for v in khop}),
        "lua": dong_lua,
        "vph_giua": round(statistics.median(vph_cum), 2) if vph_cum else None,
        "vph_giua_pool": round(statistics.median(vph_pool), 2) if vph_pool else None,
        "top_kenh": sorted(kenh.values(), key=lambda k: -k["so_video"])[:6],
        "moi_nhat": {"title": moi_nhat["title"], "kenh": moi_nhat["kenh"],
                     "kenh_yt": moi_nhat.get("kenh_yt") or "",
                     "yt_id": moi_nhat["yt_id"], "pub_ts": moi_nhat["pub_ts"],
                     "views": moi_nhat.get("views") or 0},
        "ti_trong_video": round(100 * len(khop) / max(1, len(kho)), 1),
        "ti_trong_view": round(100 * sum(v.get("views") or 0 for v in khop) / tong_view_pool, 1),
    }


def google_trends(cum: str, geo: str = "US", timeframe: str = "today 12-m",
                  gprop: str = "") -> dict:
    """Interest 12 thang + truy van lien quan (top/rising) tu Google Trends.

    trendspyg 1.6.0 — thu vien MOI (phat hanh 19/08/2026), va no chay qua trinh duyet
    (~17s/tu khoa). Loi -> tra co_du_lieu=False kem ly do, KHONG nem: mat Trends thi
    van con khoi A + YouTube.
    """
    try:
        from trendspyg import download_google_trends_explore as ex
    except ImportError:
        return {"co_du_lieu": False, "ly_do": "chưa cài trendspyg trên máy này"}
    # cookies="disk" (trendspyg 1.6.0): giữ session cookie của Google giữa các lần gọi
    # nên trông như KHÁCH QUAY LẠI. Tài liệu thư viện (đo 19/08/2026): sau một đợt gọi
    # dồn, Google chặn khách MỚI bằng trang 429 cứng nhưng phiên mang jar đã thiết lập
    # vẫn được phục vụ. Đây là cookie ẩn danh do thư viện tạo — KHÔNG phải tài khoản
    # Google của ai, nên không có rủi ro khoá tài khoản.
    # LƯU Ý ĐO THẬT 21/08: bật lúc ĐANG bị chặn thì không cứu được (không lập nổi jar
    # mới); nó chỉ có tác dụng phòng, từ lần chạy sạch trở đi.
    os.environ.setdefault("TRENDSPYG_COOKIES",
                          os.path.join(os.environ.get("RADARY_DATA_DIR", "."), "trends_cookies.json"))
    try:
        d = ex(cum, geo=geo or "US", timeframe=timeframe, include_related=True,
               cookies="disk", **({"gprop": gprop} if gprop else {}))
    except Exception as e:                                  # noqa: BLE001 — thư viện non
        ten = type(e).__name__
        if "RateLimit" in ten or "429" in str(e):
            return {"co_du_lieu": False, "rate_limit": True,
                    "ly_do": "Google Trends đang chặn tạm (hỏi quá nhiều trong ngày). "
                             "Kết quả đã hỏi hôm nay vẫn xem lại được; từ khoá mới thì "
                             "chờ ~30-60 phút. Các nguồn khác vẫn chạy bình thường."}
        return {"co_du_lieu": False, "ly_do": f"Google Trends lỗi: {ten}"}
    if not d or d.get("is_empty"):
        return {"co_du_lieu": False, "ly_do": "Google Trends không có dữ liệu cho từ khoá này"}
    iot = [p for p in (d.get("interest_over_time") or []) if not p.get("is_partial")]
    rq = d.get("related_queries") or {}
    xu_huong = None
    if len(iot) >= 8:            # so 1/4 dau voi 1/4 cuoi -> len/xuong/di ngang
        n = len(iot) // 4
        dau = statistics.mean([p["value"] for p in iot[:n]])
        cuoi = statistics.mean([p["value"] for p in iot[-n:]])
        if dau:
            lech = 100 * (cuoi - dau) / dau
            xu_huong = {"phan_tram": round(lech), "chieu":
                        "lên" if lech > 15 else "xuống" if lech < -15 else "đi ngang"}
    return {
        "co_du_lieu": True, "geo": d.get("geo"), "timeframe": d.get("timeframe"),
        "diem": [{"ngay": p["date"][:10], "gia_tri": p["value"]} for p in iot],
        "xu_huong": xu_huong,
        "rising": [{"cum": r.get("query"), "gia_tri": r.get("value")}
                   for r in (rq.get("rising") or [])[:10]],
        "top": [{"cum": r.get("query"), "gia_tri": r.get("value")}
                for r in (rq.get("top") or [])[:10]],
    }


def _iso_truoc(ngay: int) -> str:
    return datetime.fromtimestamp(time.time() - ngay * 86400, timezone.utc)\
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def ngoai_youtube(api, cum: str, vung: dict | None = None, so_kq: int = 20) -> dict:
    """KHOI B/YouTube — video NOI trong 90 ngay + kenh moi noi cho tu khoa nay.

    Mot lan search (order=viewCount + publishedAfter) roi tan dung cho ca hai muc:
    ~102 units. Khac `thi_truong.do_mot_cum` (order=relevance, khong gioi han ngay).
    """
    tham = {"part": "snippet", "q": cum, "type": "video", "order": "viewCount",
            "maxResults": so_kq, "publishedAfter": _iso_truoc(MOI_NGAY_B)}
    for k in ("regionCode", "relevanceLanguage"):
        if (vung or {}).get(k):
            tham[k] = vung[k]
    r = api.get("search", tham, cost=100)
    ids = [it["id"]["videoId"] for it in (r.get("items") or [])
           if isinstance(it.get("id"), dict) and it["id"].get("videoId")]
    if not ids:
        return {"co_du_lieu": False,
                "ly_do": f"YouTube không có video nào về từ khoá này trong {MOI_NGAY_B} ngày qua"}

    v = api.get("videos", {"part": "statistics,snippet,contentDetails",
                           "id": ",".join(ids)}, cost=1)
    from . import scan
    ma_tt = (vung or {}).get("relevanceLanguage")     # 'en' / 'es' / ...
    vids, bo_ngon_ngu, bo_short = [], 0, 0
    for it in v.get("items") or []:
        sn, st = it.get("snippet") or {}, it.get("statistics") or {}
        pub = scan.parse_pub(sn.get("publishedAt"))
        tuoi = max(1.0, (time.time() - pub) / 86400)
        views = int(st.get("viewCount") or 0)
        dai = scan.parse_dur((it.get("contentDetails") or {}).get("duration"))

        # LOC NGON NGU (user 21/08: pool US van ra video tieng Viet/Indonesia). YouTube
        # CO tra defaultAudioLanguage/defaultLanguage — chinh xac hon doan tu title;
        # thieu ca hai thi moi doan tu title; van khong ro thi GIU (khong loai oan).
        cua_vid = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "").split("-")[0].lower()
        if not cua_vid:
            cua_vid = mapping.nhan_dien_ngon_ngu(sn.get("title") or "") or ""
        if ma_tt and cua_vid and cua_vid != ma_tt:
            bo_ngon_ngu += 1
            continue
        if dai and dai <= SHORT_TOI_DA_S:
            bo_short += 1
            continue

        vids.append({"yt_id": it.get("id"), "title": sn.get("title") or "",
                     "kenh": sn.get("channelTitle") or "", "kenh_id": sn.get("channelId") or "",
                     "views": views, "pub_ts": pub, "tuoi_ngay": round(tuoi),
                     "ngon_ngu": cua_vid or None, "duration_s": dai,
                     "view_moi_ngay": round(views / tuoi)})
    ch_ids = list({x["kenh_id"] for x in vids if x["kenh_id"]})[:50]
    subs = {}
    if ch_ids:
        c = api.get("channels", {"part": "statistics,snippet", "id": ",".join(ch_ids)}, cost=1)
        for it in c.get("items") or []:
            st = it.get("statistics") or {}
            subs[it.get("id")] = {
                "subs": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount") or 0),
                "tong_view": int(st.get("viewCount") or 0),
                "so_video": int(st.get("videoCount") or 0),
                "lap_luc": (it.get("snippet") or {}).get("publishedAt", "")[:10],
            }
    for x in vids:
        x.update(subs.get(x["kenh_id"]) or {"subs": None})

    # LUONG (user 21/08: "chua dua ra duoc quantity cua tu khoa"). Khong ai co search
    # volume cua YouTube — `pageInfo.totalResults` do that tra 1.000.000 cho MOI truy
    # van (cat tran, so gia). Con so THAT duy nhat lay duoc la VIEW: tong luot xem ma
    # thi truong tra cho chu de nay trong 90 ngay, tren top ket qua.
    tong_view = sum(x["views"] for x in vids)

    # KENH MOI NOI: kenh nho ma video van len top view trong 90 ngay = dang thang
    nho = {}
    for x in vids:
        if x.get("subs") is not None and x["subs"] < KENH_NHO_SUBS:
            k = nho.setdefault(x["kenh_id"], {"kenh": x["kenh"], "kenh_id": x["kenh_id"],
                                              "subs": x["subs"], "lap_luc": x.get("lap_luc"),
                                              "so_video_top": 0, "view_tot_nhat": 0,
                                              "video_tot_nhat": ""})
            k["so_video_top"] += 1
            if x["views"] >= k["view_tot_nhat"]:
                k["view_tot_nhat"], k["video_tot_nhat"] = x["views"], x["yt_id"]
    return {
        "co_du_lieu": True,
        "so_ket_qua": len(vids),
        "da_bo": {"khac_ngon_ngu": bo_ngon_ngu, "shorts": bo_short},
        "view_giua": statistics.median([x["views"] for x in vids]) if vids else 0,
        "tong_view_90n": tong_view,
        "view_moi_thang": round(tong_view / 3),          # 90 ngay ~ 3 thang
        "view_moi_ngay_tong": round(sum(x["view_moi_ngay"] for x in vids)),
        "top_video": sorted(vids, key=lambda x: -x["views"])[:8],
        "kenh_moi_noi": sorted(nho.values(), key=lambda k: -k["view_tot_nhat"])[:6],
    }


# ---- NGUON NGOAI BO SUNG (21/08, sau khi user hoi "co nguon nao khac Google Trends") --
# Da KIEM THAT tu may nay:
#   Reddit .json VA .rss  -> 403 Blocked (ca hai). Chi con duong OAuth (PRAW) — can
#     client_id/secret do Owner tao o reddit.com/prefs/apps. Chua lam.
#   X / Twitter           -> API free tier khong cho doc search; ban Basic ~100$/thang.
#   Google News RSS       -> 200, khong key. Tin dang nong ve chu de.
#   Wikipedia pageviews   -> 200, khong key, lich su theo THANG nhieu nam. Rat hop ngach
#     dia danh ("life in <noi>"): do muc quan tam THAT, doc lap YouTube.
import re as _re
import urllib.parse as _up
import urllib.request as _ur
import xml.etree.ElementTree as _ET

GNEWS = "https://news.google.com/rss/search"
WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
WIKI_PV = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           "{lang}.wikipedia/all-access/user/{bai}/monthly/{tu}/{den}")
_UA = {"User-Agent": "OUTLIERY-RadarY/1.0 (noi bo; lien he Owner)"}


def _tai_text(url: str, doc=None, het_gio: int = 12) -> str:
    if doc is not None:
        return doc(url)
    with _ur.urlopen(_ur.Request(url, headers=_UA), timeout=het_gio) as r:
        return r.read().decode("utf-8", "replace")


def google_news(cum: str, geo: str = "US", lang: str = "en", doc=None, tran: int = 8) -> dict:
    """Tin bao moi ve tu khoa — 0 key. Cho biet chu de co dang duoc noi den ngoai doi
    khong (khac voi 'co video tren YouTube khong')."""
    q = _up.urlencode({"q": f'"{cum}"', "hl": f"{lang}-{geo}", "gl": geo,
                       "ceid": f"{geo}:{lang}"})
    try:
        xml = _tai_text(f"{GNEWS}?{q}", doc)
        goc = _ET.fromstring(xml)
    except Exception as e:                                   # noqa: BLE001
        return {"co_du_lieu": False, "ly_do": f"Google News lỗi: {type(e).__name__}"}
    bai = []
    for it in goc.iterfind(".//item"):
        tieu_de = (it.findtext("title") or "").strip()
        if not tieu_de:
            continue
        nguon = (it.findtext("source") or "").strip()
        bai.append({"tieu_de": tieu_de.rsplit(" - ", 1)[0] if " - " in tieu_de else tieu_de,
                    "nguon": nguon or (tieu_de.rsplit(" - ", 1)[-1] if " - " in tieu_de else ""),
                    "link": (it.findtext("link") or "").strip(),
                    "ngay": (it.findtext("pubDate") or "")[:16]})
        if len(bai) >= tran:
            break
    return ({"co_du_lieu": True, "so_bai": len(bai), "bai": bai} if bai
            else {"co_du_lieu": False, "ly_do": "không có bài báo nào về từ khoá này"})


def wikipedia(cum: str, lang: str = "en", doc=None, so_thang: int = 13) -> dict:
    """Muc quan tam THAT theo thang, tu luot xem Wikipedia — 0 key, doc lap YouTube.

    Hai buoc: tim bai khop tu khoa, roi lay pageviews cua bai dau. Bai khong khop chu
    de thi so lieu vo nghia, nen tra ca TEN BAI de nguoi tu danh gia (luat A3).
    """
    try:
        q = _up.urlencode({"action": "query", "list": "search", "srsearch": cum,
                           "format": "json", "srlimit": 3})
        d = json.loads(_tai_text(WIKI_API.format(lang=lang) + "?" + q, doc))
        hits = (d.get("query") or {}).get("search") or []
    except Exception as e:                                   # noqa: BLE001
        return {"co_du_lieu": False, "ly_do": f"Wikipedia lỗi: {type(e).__name__}"}
    if not hits:
        return {"co_du_lieu": False, "ly_do": "Wikipedia không có bài nào khớp từ khoá"}

    bai = hits[0]["title"]
    den = datetime.now(timezone.utc).replace(day=1)
    tu = den - timedelta(days=so_thang * 31)
    url = WIKI_PV.format(lang=lang, bai=_up.quote(bai.replace(" ", "_"), safe=""),
                         tu=tu.strftime("%Y%m0100"), den=den.strftime("%Y%m0100"))
    try:
        pv = json.loads(_tai_text(url, doc))
    except Exception as e:                                   # noqa: BLE001
        return {"co_du_lieu": False, "bai": bai, "ly_do": f"pageviews lỗi: {type(e).__name__}"}
    diem = [{"ngay": i["timestamp"][:6], "gia_tri": i["views"]}
            for i in (pv.get("items") or [])]
    # THANG HIEN TAI chua tron — bo khoi chuoi va phep tinh, khong thi xu huong luon
    # bao "xuong" oan (do that tajikistan 22/08: thang cut 2.524 vs thang tron ~90k
    # -> -42% gia; bo thang cut con -14% that). Cung ho bai hoc khung-chua-chot.
    thang_nay = datetime.now(timezone.utc).strftime("%Y%m")
    if diem and diem[-1]["ngay"] == thang_nay:
        diem = diem[:-1]
    if len(diem) < 4:
        return {"co_du_lieu": False, "bai": bai, "ly_do": "chưa đủ tháng để nói xu hướng"}
    n = max(1, len(diem) // 4)
    dau = statistics.mean([p["gia_tri"] for p in diem[:n]])
    cuoi = statistics.mean([p["gia_tri"] for p in diem[-n:]])
    lech = round(100 * (cuoi - dau) / dau) if dau else 0
    return {"co_du_lieu": True, "bai": bai,
            "link": f"https://{lang}.wikipedia.org/wiki/{_up.quote(bai.replace(' ', '_'))}",
            "bai_lien_quan": [h["title"] for h in hits[1:3]],
            "diem": diem, "xem_thang_cuoi": diem[-1]["gia_tri"],
            "xu_huong": {"phan_tram": lech,
                         "chieu": "lên" if lech > 15 else "xuống" if lech < -15 else "đi ngang"}}


# ---- TU KHOA DANG NOI trong pool (21/08, user hoi "co tracking realtime khong") ----
# CO — va khong phai cho tich luy: pub_ts cua video trong pool co tu 2009, nen mat do
# cua mot cum theo thang dung duoc NGAY. Pool lai duoc scheduler quet lien tuc nen so
# tu cap nhat moi vong quet. Day la "realtime" theo nhip pool, khong phai tung giay.
#
# Do HAI CHIEU de khong nham "nhieu nguoi lam" voi "dang an":
#   LUONG  — so video moi dung cum do trong 30 ngay qua, so voi 30 ngay lien truoc
#   CHAT   — view/ngay trung vi cua video 90 ngay gan day dung cum do
CUA_SO_NGAY = 30
TOI_THIEU_SO_SANH = 3        # duoi 3 video/cua so thi khong tinh % (mau qua nho)
# CUA SO DO cua ban do bong bong (22/08, user chot bo mau: 7 / 28 / 90 / toan thoi
# gian, kieu YouTube Studio — thay cho thanh truot thoi gian va cua so 180 co dinh):
# xu huong = W ngay qua so W ngay lien truoc; canh tranh = so video trong W ngay.
# W=0 (toan thoi gian): canh tranh = tron doi, xu huong giu cua so 30 mac dinh.
CUA_SO_HOP_LE = (0, 7, 28, 90)


def xu_huong_cum(kho: list[dict], cums: list[str], bay_gio: float | None = None,
                 so_thang: int = 12, cua_so: int | None = None) -> list[dict]:
    """Cum nao trong pool dang LEN / DANG GIAM. 0 quota, doc du lieu san co.

    cua_so: 7/28/90 = do xu huong VA canh tranh trong W ngay; 0 = canh tranh tron
    doi (xu huong giu 30 ngay); None = 30 ngay (tuong thich cu).
    """
    bay_gio = bay_gio or time.time()
    cs = cua_so if cua_so else CUA_SO_NGAY
    m30, m60 = bay_gio - cs * 86400, bay_gio - 2 * cs * 86400
    m90 = bay_gio - 90 * 86400
    moc_thang = bay_gio - so_thang * 30 * 86400
    ra = []
    for cum in cums:
        rx = mapping._rx(cum)
        # pub_ts <= bay_gio: khi dung lai ban do TAI MOT MOC QUA KHU, video dang sau
        # moc do chua ton tai — de lot vao la "nhin thay tuong lai" (22/08).
        khop = [v for v in kho
                if (v.get("pub_ts") or 0) <= bay_gio and rx.search(v["title_l"])]
        if not khop:
            continue
        nay = [v for v in khop if (v.get("pub_ts") or 0) >= m30]
        truoc = [v for v in khop if m60 <= (v.get("pub_ts") or 0) < m30]
        vpd = [x for x in (_view_moi_ngay(v, bay_gio) for v in khop
                           if (v.get("pub_ts") or 0) >= m90) if x]
        # Chi can KY TRUOC du mau (no la mau so). Ban dau doi ca hai ky >= 3 nen cum
        # dang CHET han (truoc 6 video, nay 0) bi xep "it mau" — mat dung tin hieu
        # giam manh nhat. Do that 21/08: '15 mind' 6 -> 0.
        du = len(truoc) >= TOI_THIEU_SO_SANH
        pt = round(100 * (len(nay) - len(truoc)) / len(truoc)) if du else None

        thang: dict[str, int] = {}
        for v in khop:
            if (v.get("pub_ts") or 0) >= moc_thang:
                thang[_thang(v["pub_ts"])] = thang.get(_thang(v["pub_ts"]), 0) + 1
        ra.append({
            "cum": cum, "tong_video": len(khop),
            # canh tranh: tron doi khi cua_so=0, con lai = so video trong W ngay
            "video_cua_so": len(khop) if cua_so == 0 else len(nay),
            "video_30n": len(nay), "video_30n_truoc": len(truoc),
            "phan_tram": pt,
            "chieu": None if pt is None else ("lên" if pt > 15 else "xuống" if pt < -15 else "đi ngang"),
            "du_mau": du,
            "view_moi_ngay": round(statistics.median(vpd)) if len(vpd) >= 2 else None,
            "chuoi": [{"ngay": k, "gia_tri": thang[k]} for k in sorted(thang)],
        })
    # dang len truoc, roi toi cum nhieu video — cum khong du mau xuong duoi cung
    ra.sort(key=lambda r: (r["phan_tram"] is None, -(r["phan_tram"] or 0), -r["tong_video"]))
    return ra
