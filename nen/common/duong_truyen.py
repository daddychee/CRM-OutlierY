# -*- coding: utf-8 -*-
"""Đo đường truyền (P1-M3, 01/09/2026) — Owner đặt hàng vòng mockup 3.

Luật ngoài code nen/rules/duong_truyen.json: {"tuyen": [{ma, ten, kieu, dich}]}
- kieu "tcp": bắt tay TCP tới host:port đo ms — KHÔNG tải nội dung, 0 quota
  (đủ trả lời "Z.ai/YouTube còn với tới không, chậm không").
- kieu "doc": đọc thử file (4KB đầu) hoặc listdir thư mục đo ms — NAS "còn
  mount nhưng đơ" (bệnh SMB kinh điển) lộ ở latency trước khi ai kêu.

Tuyến chết trả ok=False + ms=None (không bịa số); một tuyến nổ không giết lượt
đo. Vòng giám sát gọi mỗi tick, ring buffer nằm bên giam_sat.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_cache: dict = {}


def _duong_luat() -> Path:
    return Path(os.environ.get("DUONG_TRUYEN_LUAT",
                               ROOT / "nen" / "rules" / "duong_truyen.json"))


def doc_luat() -> list[dict]:
    duong = _duong_luat()
    if not duong.exists():
        return []
    khoa = (str(duong), duong.stat().st_mtime)
    if khoa in _cache:
        return _cache[khoa]
    du_lieu = json.loads(duong.read_text(encoding="utf-8-sig"))
    ket = [t for t in du_lieu.get("tuyen", [])
           if all(t.get(k) for k in ("ma", "ten", "kieu", "dich"))]
    _cache.clear()
    _cache[khoa] = ket
    return ket


def _doc_thu(dich: str) -> None:
    p = Path(dich)
    if p.is_dir():
        next(iter(p.iterdir()), None)
    else:
        with open(p, "rb") as f:
            f.read(4096)


async def _do_mot(t: dict) -> dict:
    ket = {"ma": t["ma"], "ten": t["ten"], "kieu": t["kieu"],
           "ok": False, "ms": None}
    t0 = time.perf_counter()
    try:
        if t["kieu"] == "tcp":
            host, cong = t["dich"].rsplit(":", 1)
            _r, w = await asyncio.wait_for(
                asyncio.open_connection(host, int(cong)), timeout=5)
            w.close()
        elif t["kieu"] == "doc":
            await asyncio.wait_for(asyncio.to_thread(_doc_thu, t["dich"]),
                                   timeout=5)
        else:
            return ket
        ket.update(ok=True, ms=round((time.perf_counter() - t0) * 1000))
    except Exception:  # noqa: BLE001 — tuyến chết là dữ liệu, không nổ
        pass
    return ket


async def do_tat_ca() -> list[dict]:
    return list(await asyncio.gather(*(_do_mot(t) for t in doc_luat())))
