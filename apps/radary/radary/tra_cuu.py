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

import statistics
import time
from datetime import datetime, timezone

from . import mapping

SO_THANG = 18            # cua so lua dang mac dinh
TOI_THIEU_LUA = 2        # duoi 2 video/thang thi khong lay trung vi (mau qua nho)
MOI_NGAY_B = 90          # "video noi gan day" = dang trong 90 ngay
KENH_NHO_SUBS = 50_000


def _thang(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")


def _view_moi_ngay(v: dict, bay_gio: float) -> float | None:
    """View/ngay ca doi video — cach duy nhat so cong bang giua cac lua khi khong co
    lich su view. Video duoi 7 ngay tuoi bi bo (chua on dinh)."""
    tuoi = (bay_gio - (v.get("pub_ts") or 0)) / 86400
    if tuoi < 7 or not v.get("views"):
        return None
    return v["views"] / tuoi


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
    kenh: dict[str, dict] = {}
    for v in khop:
        if (v.get("pub_ts") or 0) >= bay_gio - 365 * 86400:
            k = kenh.setdefault(v["kenh"] or v["kenh_yt"], {"kenh": v["kenh"], "so_video": 0, "views": 0})
            k["so_video"] += 1
            k["views"] += v.get("views") or 0

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
                     "yt_id": moi_nhat["yt_id"], "pub_ts": moi_nhat["pub_ts"],
                     "views": moi_nhat.get("views") or 0},
        "ti_trong_video": round(100 * len(khop) / max(1, len(kho)), 1),
        "ti_trong_view": round(100 * sum(v.get("views") or 0 for v in khop) / tong_view_pool, 1),
    }


def google_trends(cum: str, geo: str = "US", timeframe: str = "today 12-m") -> dict:
    """Interest 12 thang + truy van lien quan (top/rising) tu Google Trends.

    trendspyg 1.6.0 — thu vien MOI (phat hanh 19/08/2026), va no chay qua trinh duyet
    (~17s/tu khoa). Loi -> tra co_du_lieu=False kem ly do, KHONG nem: mat Trends thi
    van con khoi A + YouTube.
    """
    try:
        from trendspyg import download_google_trends_explore as ex
    except ImportError:
        return {"co_du_lieu": False, "ly_do": "chưa cài trendspyg trên máy này"}
    try:
        d = ex(cum, geo=geo or "US", timeframe=timeframe, include_related=True)
    except Exception as e:                                  # noqa: BLE001 — thư viện non
        return {"co_du_lieu": False, "ly_do": f"Google Trends lỗi: {type(e).__name__}"}
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

    v = api.get("videos", {"part": "statistics,snippet", "id": ",".join(ids)}, cost=1)
    from . import scan
    vids = []
    for it in v.get("items") or []:
        sn, st = it.get("snippet") or {}, it.get("statistics") or {}
        pub = scan.parse_pub(sn.get("publishedAt"))
        tuoi = max(1.0, (time.time() - pub) / 86400)
        views = int(st.get("viewCount") or 0)
        vids.append({"yt_id": it.get("id"), "title": sn.get("title") or "",
                     "kenh": sn.get("channelTitle") or "", "kenh_id": sn.get("channelId") or "",
                     "views": views, "pub_ts": pub, "tuoi_ngay": round(tuoi),
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

    # KENH MOI NOI: kenh nho ma video van len top view trong 90 ngay = dang thang
    nho = {}
    for x in vids:
        if x.get("subs") is not None and x["subs"] < KENH_NHO_SUBS:
            k = nho.setdefault(x["kenh_id"], {"kenh": x["kenh"], "subs": x["subs"],
                                              "lap_luc": x.get("lap_luc"), "so_video_top": 0,
                                              "view_tot_nhat": 0})
            k["so_video_top"] += 1
            k["view_tot_nhat"] = max(k["view_tot_nhat"], x["views"])
    return {
        "co_du_lieu": True,
        "so_ket_qua": len(vids),
        "view_giua": statistics.median([x["views"] for x in vids]) if vids else 0,
        "top_video": sorted(vids, key=lambda x: -x["views"])[:8],
        "kenh_moi_noi": sorted(nho.values(), key=lambda k: -k["view_tot_nhat"])[:6],
    }
