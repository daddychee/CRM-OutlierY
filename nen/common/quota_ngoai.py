# -*- coding: utf-8 -*-
"""Quota dịch vụ ngoài TRA ĐƯỢC THẬT (01/09/2026).

Apify là dịch vụ hiếm hoi CHO TRA credit còn lại (/users/me) — khác YouTube
(chỉ ước từ sổ gọi). Nền tự hỏi bằng khóa apify trong két; khóa trần chỉ nằm
trong request tới Apify, không bao giờ vào JSON/UI.

Cache TTL 1800s — UI poll 15 giây không được dội Apify (credit đổi chậm).
Không khóa / mạng chết / trả dạng lạ → None (van chống bịa: '—' chứ không 0 giả).
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

TTL = 1800.0
_CACHE: dict = {"luc": 0.0, "kq": None}


def xoa_cache() -> None:
    _CACHE.update(luc=0.0, kq=None)


def apify_credit() -> dict | None:
    """{"goi", "tran_usd", "da_dung_usd", "con_usd", "luc"} hoặc None."""
    if time.time() - _CACHE["luc"] < TTL:
        return _CACHE["kq"]
    kq = None
    try:
        from nen.ket_cau_hinh import ket
        conn = ket.ket_noi()
        try:
            kid = next((k["id"] for k in ket.liet_ke_api_keys(conn)
                        if k["loai"] == "apify"), None)
            token = ket.lay_bi_mat(conn, f"api.{kid}.key") if kid else None
        finally:
            conn.close()
        if token:
            url = ("https://api.apify.com/v2/users/me?token="
                   + urllib.parse.quote(token))
            with urllib.request.urlopen(url, timeout=8) as r:
                d = (json.loads(r.read().decode()) or {}).get("data") or {}
            ky = d.get("currentBillingPeriod") or {}
            tran = (d.get("plan") or {}).get("monthlyUsageCreditsUsd")
            # Kỳ chưa tiêu đồng nào → Apify trả currentBillingPeriod RỖNG
            # (đo thật 01/09) — vắng usageUsd nghĩa là 0, không phải không biết.
            dung = ky.get("usageUsd", 0) or 0
            if tran is not None:
                kq = {"goi": (d.get("plan") or {}).get("id") or "",
                      "tran_usd": tran, "da_dung_usd": round(dung, 2),
                      "con_usd": round(tran - dung, 2),
                      "luc": time.strftime("%H:%M")}
    except Exception:  # noqa: BLE001 — quota ngoài chết không được hỏng tổng hợp
        kq = None
    _CACHE.update(luc=time.time(), kq=kq)
    return kq
