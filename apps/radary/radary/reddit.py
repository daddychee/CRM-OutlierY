# -*- coding: utf-8 -*-
"""Reddit DUNG NGHIA qua Apify (Owner chot 22/08 — "toi muon reddit du nghia").

VI SAO KHONG GOI THANG: IP server bi Reddit chan MOI duong (do 22/08 —
www json 403, oauth.reddit.com 403, old.reddit tra HTML login-wall). SERP chi
cho biet "Google thay gi ve Reddit" — tieu de + snippet, KHONG co upvote. Apify
la nen chay scraper thue nen no goi Reddit tu IP cua no, tra du lieu THAT.

ACTOR: clearpath/reddit-search-scraper — chon sau khi DO ba actor that:
  trudax/reddit-scraper-lite      $0.004/item · 36s · KHONG tra upvote (None)
  practicaltools/apify-reddit-api $0.004/item
  clearpath/reddit-search-scraper $0.00099/item · 9s · CO score + commentCount
Re gap 4 lan, nhanh gap 4, va la actor duy nhat trong ba cai tra dung thu can:
so upvote va so binh luan.

NGAN SACH: goi FREE cua Apify cho $5 credit/thang. Moi lan tra mot cum =
1 lan chay ($0.00099) + N ket qua ($0.00099 moi cai) -> mac dinh 15 ket qua
= ~$0.016/cum, tuc ~300 cum/thang. Rong rai, nhung van dem va canh bao.

VAN CHONG BIA: khong co token / het credit / actor loi -> co_du_lieu=False kem
LY DO that, KHONG bao gio tra khoi rong nhu the khong ai ban gi.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

ACTOR = "clearpath~reddit-search-scraper"
GOC = "https://api.apify.com/v2"
SO_KET_QUA = 15                     # can bang giua du mau va tien
HET_CREDIT = (401, 402, 403)


class HetCredit(Exception):
    """Token khong dung duoc hoac het credit thang."""


def _goi(duong: str, token: str, than: dict | None = None, timeout: int = 180) -> list | dict:
    url = f"{GOC}{duong}{'&' if '?' in duong else '?'}token={urllib.parse.quote(token)}"
    du_lieu = json.dumps(than).encode() if than is not None else None
    req = urllib.request.Request(url, data=du_lieu,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in HET_CREDIT:
            raise HetCredit(f"HTTP {e.code}") from None
        raise RuntimeError(f"Apify lỗi HTTP {e.code}") from None
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError(f"Apify lỗi {type(e).__name__}") from None


def tim(token: str, cum: str, sap_xep: str = "top", ky: str = "year",
        so_ket_qua: int = SO_KET_QUA) -> dict:
    """Bài Reddit nói về cụm này — kèm upvote, số bình luận, subreddit, thời gian."""
    tho = _goi(f"/acts/{ACTOR}/run-sync-get-dataset-items", token,
               {"query": cum, "sort": sap_xep, "time": ky, "limit": so_ket_qua})
    if not isinstance(tho, list):
        return {"co_du_lieu": False, "ly_do": "Apify trả dạng lạ"}

    bai = []
    for x in tho:
        if x.get("_type") != "post" or not x.get("title"):
            continue
        pl = x.get("permalink") or ""
        bai.append({
            "tieu_de": x["title"],
            "sub": x.get("subreddit") or "",
            "upvote": x.get("score") or 0,
            "binh_luan": x.get("commentCount") or 0,
            "ngay": (x.get("createdAt") or "")[:10],
            "link": ("https://www.reddit.com" + pl) if pl.startswith("/") else (x.get("url") or ""),
        })
    bai.sort(key=lambda b: -b["upvote"])
    if not bai:
        return {"co_du_lieu": False,
                "ly_do": f"Reddit không có bài nào về “{cum}” trong {ky} qua"}

    # Cong dong nao ban chu de nay nhieu nhat — de biet nen doc o dau
    sub: dict[str, dict] = {}
    for b in bai:
        s = sub.setdefault(b["sub"], {"sub": b["sub"], "so_bai": 0, "upvote": 0})
        s["so_bai"] += 1
        s["upvote"] += b["upvote"]
    return {"co_du_lieu": True, "bai": bai[:so_ket_qua],
            "sub": sorted(sub.values(), key=lambda s: -s["upvote"])[:6],
            "tong_upvote": sum(b["upvote"] for b in bai),
            "tong_binh_luan": sum(b["binh_luan"] for b in bai),
            "ky": ky, "nguon": f"apify:{ACTOR}"}


def du_credit(token: str) -> dict:
    """Còn bao nhiêu credit tháng — để cảnh báo TRƯỚC khi cụt giữa chừng."""
    try:
        d = (_goi("/users/me", token) or {}).get("data") or {}
    except Exception:                                        # noqa: BLE001
        return {}
    ky = d.get("currentBillingPeriod") or {}
    return {"goi": (d.get("plan") or {}).get("id") or "",
            "tran_usd": (d.get("plan") or {}).get("monthlyUsageCreditsUsd"),
            "da_dung_usd": ky.get("usageUsd")}
