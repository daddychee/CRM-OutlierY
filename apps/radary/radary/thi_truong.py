# -*- coding: utf-8 -*-
"""DO THI TRUONG THAT cho mot cum tu khoa — tang thieu cua Mapping ban dau.

Vi sao phai co (user chi ra 21/08, dung): ban Mapping dau tien lay CA HAI ve tu thu
RadarY da biet — cau tu autocomplete (khong co so) va cung tu POOL cua chinh minh.
Ket qua tat yeu la "ban sao cua RadarY + mot danh sach chuoi ky tu": khong co byte du
lieu nao tu thi truong, nen khong co gi de quyet dinh.
  - `life in rio: 0 video` KHONG co nghia la chua ai lam. No co nghia la 803 kenh
    minh dang theo doi chua lam. Gan nhan "khoang trong" cho du kien do la SAI.
  - do_phu do duoc 324/332 cum = 1 -> truc cau la BIT, khong phai thang.

Tang nay tra loi 3 cau hoi de QUYET DINH, bang so that tren toan YouTube:
  1. Thi truong tra bao nhieu view cho mot video MOI ve cum nay?
  2. Cum dang song hay da nguoi? (ti le video top dang trong 90 ngay)
  3. MINH CO CUA KHONG? (kenh nho co lot top khong) — chi so quan trong nhat

Khoa lay tu KET OUTLIERY (General › API Keys) qua khoa_v3 — moi khoa deu o General,
khong phai "quota cua bo phan nao". scan.API tu xoay khoa khi 403/429.
Chi phi: search.list 100 units + videos.list 1 + channels.list 1 = ~102 units/cum.
"""
from __future__ import annotations

import statistics
import time

from . import scan

VIEC_KHOA = "quet_dinh_ky"      # viec da duoc cap khoa san; tach han muc rieng thi khai viec moi
MOI_NGAY = 90                   # "video moi" = dang trong 90 ngay
KENH_NHO_SUBS = 50_000          # nguong "kenh nho" — co lot top = minh co cua
SO_KQ = 20                      # video lay moi cum (search.list tra toi da 50)
TRAN_CUM = 30                   # tran cung: 30 cum ~ 3.060 units


def _tuoi_ngay(pub_ts: float, bay_gio: float) -> float:
    return max(0.0, (bay_gio - pub_ts) / 86400)


def do_mot_cum(api, cum: str, so_kq: int = SO_KQ, bay_gio: float | None = None,
               vung: dict | None = None) -> dict:
    """Do THI TRUONG cho mot cum. Tra so + danh sach video that de nguoi soi.

    Khong ket luan "nen lam hay khong" — chi trinh so (luat A3). Cum khong co ket qua
    -> tra `co_du_lieu=False`, KHONG tra 0 (0 view khac voi khong do duoc).
    """
    bay_gio = bay_gio or time.time()
    # regionCode/relevanceLanguage = thi truong cua pool. Thieu -> YouTube xep theo IP
    # may chu (Viet Nam), so lieu "thi truong" thanh so lieu thi truong VN.
    tham = {"part": "snippet", "q": cum, "type": "video",
            "order": "relevance", "maxResults": so_kq}
    for k in ("regionCode", "relevanceLanguage"):
        if (vung or {}).get(k):
            tham[k] = vung[k]
    r = api.get("search", tham, cost=100)
    ids = [it["id"]["videoId"] for it in (r.get("items") or [])
           if isinstance(it.get("id"), dict) and it["id"].get("videoId")]
    if not ids:
        return {"co_du_lieu": False, "ly_do": "YouTube không trả kết quả nào cho cụm này"}

    v = api.get("videos", {"part": "statistics,snippet,contentDetails",
                           "id": ",".join(ids)}, cost=1)
    vids = []
    for it in v.get("items") or []:
        sn, st = it.get("snippet") or {}, it.get("statistics") or {}
        pub = scan.parse_pub(sn.get("publishedAt"))
        vids.append({
            "yt_id": it.get("id"), "title": sn.get("title") or "",
            "kenh": sn.get("channelTitle") or "", "kenh_id": sn.get("channelId") or "",
            "views": int(st.get("viewCount") or 0), "pub_ts": pub,
            "tuoi_ngay": round(_tuoi_ngay(pub, bay_gio), 1),
            "duration_s": scan.parse_dur((it.get("contentDetails") or {}).get("duration")),
        })
    if not vids:
        return {"co_du_lieu": False, "ly_do": "không đọc được số liệu video"}

    # subs cua cac kenh trong top — de biet KENH NHO co cua khong (1 unit cho ca lo)
    ch_ids = list({x["kenh_id"] for x in vids if x["kenh_id"]})[:50]
    subs = {}
    if ch_ids:
        c = api.get("channels", {"part": "statistics", "id": ",".join(ch_ids)}, cost=1)
        for it in c.get("items") or []:
            st = it.get("statistics") or {}
            subs[it.get("id")] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount") or 0)
    for x in vids:
        x["subs"] = subs.get(x["kenh_id"])

    moi = [x for x in vids if x["tuoi_ngay"] <= MOI_NGAY]
    nho = [x for x in vids if x["subs"] is not None and x["subs"] < KENH_NHO_SUBS]
    views = sorted(x["views"] for x in vids)
    return {
        "co_du_lieu": True,
        "so_ket_qua": len(vids),
        "view_giua": views[len(views) // 2],
        "view_giua_moi": (statistics.median([x["views"] for x in moi]) if moi else None),
        "so_video_moi": len(moi),
        "ti_le_moi": round(100 * len(moi) / len(vids)),
        "tuoi_giua_ngay": round(statistics.median([x["tuoi_ngay"] for x in vids])),
        "kenh_nho_lot_top": len(nho),
        "kenh_nho_view_giua": (statistics.median([x["views"] for x in nho]) if nho else None),
        "subs_giua": (statistics.median([x["subs"] for x in vids if x["subs"] is not None])
                      if any(x["subs"] is not None for x in vids) else None),
        "top": sorted(vids, key=lambda x: -x["views"])[:8],
    }


def do_nhieu_cum(cums: list[str], lay_khoa=None, tran: int = TRAN_CUM,
                 api=None, bay_gio: float | None = None, vung: dict | None = None) -> dict:
    """Do nhieu cum trong MOT phien, dung chung bo khoa + dem quota that da tieu."""
    if api is None:
        lay = lay_khoa or (lambda viec: __import__("radary.khoa_v3", fromlist=["x"]).lay_khoa(viec))
        api = scan.API(lay(VIEC_KHOA))
    ra, loi = {}, {}
    for cum in cums[:tran]:
        try:
            ra[cum] = do_mot_cum(api, cum, bay_gio=bay_gio, vung=vung)
        except (RuntimeError, OSError) as e:      # het quota / mang -> dung, giu phan da do
            loi[cum] = str(e)
            break
    return {"ket_qua": ra, "loi": loi, "quota_da_tieu": getattr(api, "used", 0),
            "da_do": len(ra), "bo_qua": max(0, len(cums) - len(ra) - len(loi))}
