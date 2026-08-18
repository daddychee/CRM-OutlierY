# -*- coding: utf-8 -*-
"""Gate ký duyệt 8 phase — trạng thái SỐNG cấp niche×thị trường (chốt 18/08).

Luật phương pháp: không đạt gate không đi tiếp; máy KHÔNG tự phán ĐẠT gate của
người. Gate 'auto' (P1/P2/P7) đạt khi có báo cáo; gate 'business' (P0/P3/P6) cần
Manager+ (L4); gate 'production' (P4/P5) cần Leader+ (L3) — bảng quyền mockup v3.
Chữ ký ghi ai/lúc nào, SỐNG QUA các lần chạy lại pipeline (không gắn snapshot).
Sổ: data/data-analytics/gates/<ngach>__<tt>.json (env GATES_DIR), ghi nguyên tử.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
_ROOT = _APP_DIR.parents[1]

GATES = [
    ("p0", "P0 Foundation", "business"),
    ("p1", "P1 Audience", "auto"),
    ("p2", "P2 Gap", "auto"),
    ("p3", "P3 Positioning", "business"),
    ("p4", "P4 Format", "production"),
    ("p5", "P5 Packaging", "production"),
    ("p6", "P6 Launch", "business"),
    ("p7", "P7 KPI", "auto"),
]
_LOAI = {ma: loai for ma, _, loai in GATES}
MUC_LEVEL = {"business": 4, "production": 3}


def _duong(ngach_ma: str, tt_ma: str) -> Path:
    goc = Path(os.environ.get("GATES_DIR") or _ROOT / "data" / "data-analytics" / "gates")
    ten = re.sub(r"[^\w\-]", "_", f"{ngach_ma}__{tt_ma}")
    return goc / f"{ten}.json"


def doc(ngach_ma: str, tt_ma: str) -> dict:
    p = _duong(ngach_ma, tt_ma)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def ky(ngach_ma: str, tt_ma: str, gate: str, user: dict,
       phuong_an: str = "", ghi_chu: str = "") -> dict:
    loai = _LOAI.get(gate)
    if loai is None:
        raise KeyError(gate)
    if loai == "auto":
        raise ValueError("Gate này máy tự chấm theo báo cáo — không ký tay.")
    if user.get("level", 0) < MUC_LEVEL[loai]:
        can = "Manager trở lên" if loai == "business" else "Leader trở lên"
        raise PermissionError(f"Gate {gate.upper()} cần {can} ký.")
    ds = doc(ngach_ma, tt_ma)
    ds[gate] = {"boi": user.get("ten", "?"),
                "luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "phuong_an": phuong_an.strip(), "ghi_chu": ghi_chu.strip()}
    p = _duong(ngach_ma, tt_ma)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    return ds[gate]


def trang_thai(ngach_ma: str, tt_ma: str, co_bao_cao: bool, level: int) -> list[dict]:
    """Danh sách 8 gate cho template: da_ky / dat (auto) / cho + cờ ky_duoc theo level."""
    ds = doc(ngach_ma, tt_ma)
    out = []
    for ma, nhan, loai in GATES:
        chu_ky = ds.get(ma)
        if chu_ky:
            tt = "da_ky"
        elif loai == "auto":
            tt = "dat" if co_bao_cao else "cho"
        else:
            tt = "cho"
        out.append({"ma": ma, "nhan": nhan, "loai": loai, "trang_thai": tt,
                    "ky_duoc": loai != "auto" and not chu_ky and level >= MUC_LEVEL[loai],
                    **({"boi": chu_ky["boi"], "luc": chu_ky["luc"],
                        "phuong_an": chu_ky.get("phuong_an", "")} if chu_ky else {})})
    return out
