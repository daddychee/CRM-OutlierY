# -*- coding: utf-8 -*-
"""ĐƠN VỊ KINH TẾ (B2) — spec `docs/finance-hub-spec.md` mục 4.

Câu hỏi thật của nghề là "kênh này nuôi tiếp hay bỏ", và nó cần *chi phí một
video* so với *doanh thu một video mang về* — không phải tổng thu trừ tổng chi.

Nguồn (CHỈ ĐỌC, Luật 4):
  sổ thu chi          thu/chi theo kênh (đã quy VND)
  PlannerY plan.json  số video xuất bản trong kỳ (channels[].videos[].publish_date)
  Data Analytics      lượt xem — nối sau, hiện chưa có thì để None

Van chống bịa (giữ nguyên tinh thần engine chẩn đoán): số video = 0 thì KHÔNG
chia (chi_moi_video=None kèm lý do); thu = 0 thì không có biên lãi; nguồn chết
thì nói thẳng `thieu_nguon`, không dựng số.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from nen.common import danh_ba

from src import tai_chinh


def _doc_plan() -> dict | None:
    p = Path(os.getenv("PLANNERY_PLAN", "plan.json"))
    if not p.is_file():
        return None
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, dict) else None
    except ValueError:
        return None


def so_video_trong_ky(thang: str) -> dict[str, int] | None:
    """{kenh_ma: số video xuất bản trong kỳ} từ PlannerY. Đọc không được → None."""
    plan = _doc_plan()
    if plan is None:
        return None
    ra: dict[str, int] = {}
    for du_an in plan.get("projects", []):
        for kenh in du_an.get("channels", []):
            ma = kenh.get("kenh_ma") or ""
            if not ma:
                continue
            dem = sum(1 for v in kenh.get("videos", [])
                      if (v.get("publish_date") or "")[:7] == thang)
            ra[ma] = ra.get(ma, 0) + dem
    return ra


def don_vi_kinh_te(thang: str, luot_xem: dict | None = None) -> dict:
    """Bốn số cho mỗi kênh: chi phí/video · chi phí/1K lượt xem · biên lãi ·
    số video. `luot_xem` truyền từ Data Analytics khi có; chưa có → None."""
    video = so_video_trong_ky(thang)
    if video is None:
        return {"thang": thang, "thieu_nguon": True, "dong": []}

    luot_xem = luot_xem or {}
    pnl = tai_chinh.pnl_theo_kenh(thang)
    ten_kenh = {k["ma"]: k.get("ten_chuan", "") for k in danh_ba.liet_ke("kenh")}
    dong = []
    for ma, m in sorted(pnl.items()):
        if not ma:                                   # 'chung hệ' không phải kênh
            continue
        sv = video.get(ma, 0)
        thu, chi = m["thu"], m["chi"]
        lx = luot_xem.get(ma)
        thieu = []
        if not sv:
            thieu.append("chưa xuất bản video nào trong kỳ")
        if lx is None:
            thieu.append("chưa nối lượt xem")
        dong.append({
            "kenh_ma": ma, "ten": ten_kenh.get(ma, ""), "so_video": sv,
            "thu": thu, "chi": chi,
            "chi_moi_video": round(chi / sv, 2) if sv else None,
            "luot_xem": lx,
            "chi_moi_1k_view": round(chi / lx * 1000, 2) if lx else None,
            "bien_lai": round(100 * (thu - chi) / thu) if thu else None,
            "thieu": " · ".join(thieu)})
    return {"thang": thang, "thieu_nguon": False, "dong": dong}
