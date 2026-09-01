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
import json
import logging
import os
import time
from collections import deque
from pathlib import Path

from nen.common import canh_bao, nhat_ky, nhip_viec

NGUONG_CHET = 2  # số chu kỳ chết liên tiếp trước khi báo (chống flap 1 nhịp mạng)

# Ring buffer lịch sử tick (P1-M3) — 1440 điểm × 60s = 24h; RAM, restart về 0
# (giới hạn đã biết, khuôn dem_loi). UI command center vẽ dòng chảy từ đây.
_LICH_SU: deque = deque(maxlen=1440)


def luu_tick(d: dict) -> None:
    _LICH_SU.append(d)


def lay_lich_su(n: int = 60) -> list[dict]:
    return list(_LICH_SU)[-n:]


def lay_duong_truyen_moi() -> list[dict] | None:
    return _LICH_SU[-1].get("duong_truyen") if _LICH_SU else None


def xoa_lich_su() -> None:
    _LICH_SU.clear()


def doc_su_co(n: int = 200) -> list[dict]:
    """Đọc sổ sự cố bền (data/logs/giam-sat, JSON-lines) — 2 ngày gần nhất,
    mới nhất trước. Sổ hỏng/thiếu → [] (không nổ)."""
    goc = Path(os.environ.get("LOGS_DIR",
                              Path(__file__).resolve().parents[2] / "data" / "logs"))
    dong: list[dict] = []
    files = sorted((goc / "giam-sat").rglob("*.log"))[-8:]  # ~8 ngày gần nhất
    for f in files:
        try:
            for ln in f.read_text(encoding="utf-8").splitlines():
                try:
                    dong.append(json.loads(ln))
                except ValueError:
                    continue
        except OSError:
            continue
    return dong[::-1][:n]


def so_sanh(truoc: dict, dich_vu: list[dict], nhip: list[dict],
            tuyen: list[dict] | None = None) -> tuple[dict, list[str]]:
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

    # đường truyền (P1-M3): tuyến thông→đứt báo một lần, thông lại báo lại
    for t in (tuyen or []):
        cu = truoc.get("tuyen", {}).get(t["ma"], True)
        moi.setdefault("tuyen", {})[t["ma"]] = t["ok"]
        if cu and not t["ok"]:
            bao.append(f"🔴 Đường truyền '{t['ten']}' ĐỨT")
        if not cu and t["ok"]:
            bao.append(f"🟢 Đường truyền '{t['ten']}' đã thông lại ({t['ms']} ms)")
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
            from nen.common import dem_loi, duong_truyen
            tuyen = await duong_truyen.do_tat_ca()
            trang_thai, bao = so_sanh(trang_thai, dich_vu, nhip, tuyen)
            dem = dem_loi.tom_tat()
            p95s = [d["p95"] for d in dem.values() if d["p95"] is not None]
            luu_tick({"ts": round(time.time()),
                      "req": sum(d["yeu_cau"] for d in dem.values()),
                      "loi": sum(d["loi"] + d["nut_chet"] for d in dem.values()),
                      "app_loi": sum(1 for d in dich_vu if not d["song"]),
                      "p95": max(p95s) if p95s else None,
                      "duong_truyen": tuyen})
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
