# -*- coding: utf-8 -*-
"""SƠ ĐỒ VẬN HÀNH SỐNG per app (02/09/2026) — luật ngoài code.

nen/rules/so_do/<slug>.json:
  {"nut": [{ma, ten, cot, loai?, ghi_chu?, suc_khoe?|canary?|tuyen?}],
   "canh": [[tu, den, nhan?]]}
- cot 0..n: layout cột trái→phải (người dùng → tính năng → lõi → dịch vụ ngoài).
- loai: nguoi / module (mặc định) / kho / ngoai — đổi hình khối trên UI.
- binding: suc_khoe=<tên module deep health> / canary=<mã kịch bản> /
  tuyen=<mã đường truyền> → UI tô màu trạng thái THẬT (sơ đồ sống).

Nút thiếu ma/ten bỏ qua; cạnh trỏ nút không tồn tại bỏ qua (sửa JSON tay gõ
nhầm không được vỡ UI). Cache theo mtime (khuôn hop_dong).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_cache: dict = {}


def _goc() -> Path:
    return Path(os.environ.get("SO_DO_LUAT_DIR", ROOT / "nen" / "rules" / "so_do"))


def doc(slug: str) -> dict | None:
    duong = _goc() / f"{slug}.json"
    if not duong.exists():
        return None
    khoa = (str(duong), duong.stat().st_mtime)
    if khoa in _cache:
        return _cache[khoa]
    try:
        tho = json.loads(duong.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    nut = [n for n in tho.get("nut", []) if n.get("ma") and n.get("ten")]
    co = {n["ma"] for n in nut}
    canh = [c for c in tho.get("canh", [])
            if len(c) >= 2 and c[0] in co and c[1] in co]
    ket = {"nut": nut, "canh": canh}
    _cache.clear()
    _cache[khoa] = ket
    return ket


def tat_ca() -> dict[str, dict]:
    d = _goc()
    if not d.is_dir():
        return {}
    return {f.stem: sd for f in sorted(d.glob("*.json"))
            if (sd := doc(f.stem))}
