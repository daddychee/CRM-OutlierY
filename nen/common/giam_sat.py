# -*- coding: utf-8 -*-
"""Vòng giám sát nền của gateway (B5, 31/08/2026) — "báo ngay khi sai logic".

Tab Applications chỉ đo khi có người mở trang; vòng này đo MỖI CHU KỲ
(GIAM_SAT_CHU_KY giây, mặc định 60) ngay trong event loop gateway: dịch vụ
sống/chết + deep health + heartbeat việc nền. Cảnh báo phát lúc CHUYỂN trạng
thái (edge-trigger — tự nhiên chống spam): chết 2 chu kỳ liên tiếp mới báo
(chống flap), module 'loi' báo một lần, heartbeat trễ báo một lần; hồi phục
đều báo lại. Mỗi cảnh báo = 1 dòng sổ sự cố bền (nhat_ky app=giam-sat) + đẩy
ntfy nếu có topic (canh_bao.gui).

so_sanh() là HÀM THUẦN (trạng thái vào → trạng thái mới + danh sách cảnh báo)
— toàn bộ luật nằm đây, test không cần sleep/mạng; vong() chỉ là vỏ mỏng.
"""
from __future__ import annotations

import asyncio
import logging
import os

from nen.common import canh_bao, nhat_ky, nhip_viec

NGUONG_CHET = 2  # số chu kỳ chết liên tiếp trước khi báo (chống flap 1 nhịp mạng)


def so_sanh(truoc: dict, dich_vu: list[dict], nhip: list[dict]) -> tuple[dict, list[str]]:
    """Trả (trạng_thái_mới, cảnh_báo[]). `truoc` là dict trả ra từ lần trước."""
    moi: dict = {"app": {}, "nhip": {}}
    bao: list[str] = []

    for d in dich_vu:
        cu = truoc.get("app", {}).get(d["ten"], {})
        chet = 0 if d["song"] else cu.get("chet", 0) + 1
        da_bao = cu.get("da_bao_chet", False)
        if not d["song"] and chet >= NGUONG_CHET and not da_bao:
            bao.append(f"🔴 {d['ten']} không trả lời ({chet} chu kỳ liên tiếp)")
            da_bao = True
        if d["song"] and da_bao:
            bao.append(f"🟢 {d['ten']} đã hồi phục")
            da_bao = False

        loi_cu = cu.get("loi_module", False)
        loi_moi = d.get("muc") == "loi"
        if loi_moi and not loi_cu:
            hong = [m for m in d.get("mo_dun", [])
                    if m.get("trang_thai") == "loi"] or [{"ten": "suc-khoe",
                                                          "chi_tiet": "không đọc được"}]
            chi_tiet = "; ".join(f"{m['ten']}: {m.get('chi_tiet', '')}" for m in hong)
            bao.append(f"🟠 {d['ten']} — module lỗi: {chi_tiet}")
        if loi_cu and not loi_moi and d["song"]:
            bao.append(f"🟢 {d['ten']} — module đã hồi phục")
        moi["app"][d["ten"]] = {"chet": chet, "da_bao_chet": da_bao,
                                "loi_module": loi_moi if d["song"] else loi_cu}

    for v in nhip:
        tre_cu = truoc.get("nhip", {}).get(v["ma"], False)
        tre = bool(v.get("tre"))
        if tre and not tre_cu:
            bao.append(f"⏰ Việc nền '{v['ten']}' trễ nhịp "
                       f"(quá {v['chu_ky_phut']} phút không ping)")
        if tre_cu and not tre and v.get("nhip_cuoi"):
            bao.append(f"🟢 Việc nền '{v['ten']}' đã hồi phục nhịp")
        moi["nhip"][v["ma"]] = tre
    return moi, bao


def phat(bao: list[str]) -> None:
    """Mỗi cảnh báo: sổ sự cố bền TRƯỚC (không bao giờ mất), ntfy sau (best-effort)."""
    for b in bao:
        try:
            nhat_ky.ghi("giam-sat", "he-thong", "canh_bao", b)
        except OSError:
            pass
        canh_bao.gui(b)


async def vong(do_dich_vu) -> None:
    """Chạy nền trong event loop gateway. NGỦ TRƯỚC ĐO SAU — app vừa khởi động
    hàng loạt, đo ngay là báo chết oan; và TestClient (startup event) không
    kịp chạy tick nào trong test ngắn. Vòng không bao giờ được chết: mọi lỗi
    một tick chỉ log rồi đi tiếp."""
    trang_thai: dict = {}
    tick = 0
    while True:
        chu_ky = float(os.environ.get("GIAM_SAT_CHU_KY", "60"))
        await asyncio.sleep(chu_ky)
        try:
            tick += 1
            dich_vu = await do_dich_vu()
            nhip = await asyncio.to_thread(nhip_viec.tom_tat)
            trang_thai, bao = so_sanh(trang_thai, dich_vu, nhip)
            # CANARY LOGIC (P1-M2): kiểm ĐỀU ĐẶN tự động — mỗi CANARY_CHU_KY
            # giây (mặc định 1800) chạy toàn bộ kịch bản; cảnh báo edge của
            # canary đi chung kênh phát (sổ sự cố + ntfy).
            moi_tick = max(1, round(float(os.environ.get("CANARY_CHU_KY", "1800")) / chu_ky))
            if tick % moi_tick == 0:
                from nen.common import canary
                bao.extend(await canary.chay_tat_ca())
            if bao:
                await asyncio.to_thread(phat, bao)
        except Exception as e:  # noqa: BLE001 — vòng giám sát phải bất tử
            logging.warning("Vòng giám sát lỗi một tick (đi tiếp): %s", e)
