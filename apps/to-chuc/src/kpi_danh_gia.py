# -*- coding: utf-8 -*-
"""XẾP LOẠI KPI per người per kỳ (HR Hub, DE.md mục 10).

Sổ data/to-chuc/db/kpi-danh-gia/YYYY-MM.json = DANH SÁCH bản ghi
{nguoi, ky, xep_loai, nhan_xet, nguoi_cham, luc} — mỗi lần lưu APPEND một bản
ghi mới, KHÔNG ghi đè lịch sử chấm cũ (đổi ý vẫn còn vết ai chấm gì lúc nào);
UI hiển thị bản MỚI NHẤT per người. Ghi nguyên tử tmp + os.replace.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

XEP_LOAI = ("A", "B", "C")
_khoa = threading.Lock()


def _thu_muc() -> Path:
    return Path(os.getenv("KPI_DANH_GIA_DIR", "nhan-su/kpi-danh-gia"))


def _duong(ky: str) -> Path:
    return _thu_muc() / f"{ky}.json"


def doc_danh_gia(ky: str) -> list[dict]:
    """Trọn lịch sử chấm của kỳ (thứ tự append). File hỏng/thiếu → [] (đọc khoan dung)."""
    p = _duong(ky)
    if not p.is_file():
        return []
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, list) else []
    except ValueError:
        return []


def moi_nhat_theo_nguoi(ky: str) -> dict[str, dict]:
    """{nguoi: bản ghi chấm MỚI NHẤT} — bản ghi sau đè hiển thị (không đè dữ liệu)."""
    ra: dict[str, dict] = {}
    for b in doc_danh_gia(ky):
        if b.get("nguoi"):
            ra[b["nguoi"]] = b
    return ra


def them_danh_gia(nguoi: str, ky: str, xep_loai: str, nhan_xet: str,
                  nguoi_cham: str) -> dict:
    """Append MỘT bản ghi chấm — validate rồi ghi nguyên tử cả danh sách."""
    nguoi = (nguoi or "").strip()
    if not nguoi:
        raise ValueError("Thiếu người được chấm.")
    if not re.fullmatch(r"\d{4}-\d{2}", ky or ""):
        raise ValueError("Kỳ phải dạng YYYY-MM.")
    if xep_loai not in XEP_LOAI:
        raise ValueError("Xếp loại phải là A/B/C.")
    ban = {"nguoi": nguoi, "ky": ky, "xep_loai": xep_loai,
           "nhan_xet": (nhan_xet or "").strip()[:500], "nguoi_cham": nguoi_cham,
           "luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        ds = doc_danh_gia(ky)
        ds.append(ban)
        p = _duong(ky)
        p.parent.mkdir(parents=True, exist_ok=True)
        tam = p.with_name(p.name + ".tmp")
        tam.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tam, p)
    return ban
