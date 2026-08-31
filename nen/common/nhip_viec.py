# -*- coding: utf-8 -*-
"""Heartbeat việc nền (B4 giám sát, 31/08/2026) — dead-man's switch.

Đảo chiều giám sát cho loại lỗi nguy hiểm nhất: job nền chết IM LẶNG (RadarY
scheduler chết theo app 07/2026; kho Qdrant rỗng 3 ngày 31/07). Job chạy xong
tự ping POST /api/nhip-viec/<ma> (loopback); quá `chu_ky_phut` không thấy nhịp
→ tab Applications báo trễ, vòng giám sát nền (B5) cảnh báo.

Luật NGOÀI code: nen/rules/nhip_viec.json — {"viec": [{ma, ten, chu_ky_phut}]}
(thêm việc = thêm dòng). Nhịp ghi data/nhip_viec.json nguyên tử (tmp+replace),
sống qua restart — khác bộ đếm lỗi RAM của dem_loi.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_gio = time.time  # tách để test tua đồng hồ
_cache_luat: dict = {}


def _duong_luat() -> Path:
    return Path(os.environ.get("NHIP_VIEC_LUAT", ROOT / "nen" / "rules" / "nhip_viec.json"))


def _duong_data() -> Path:
    return Path(os.environ.get("NHIP_VIEC_DATA", ROOT / "data" / "nhip_viec.json"))


def doc_luat() -> list[dict]:
    """Đọc danh sách việc; mục thiếu trường bắt buộc → bỏ qua (khuôn hop_dong).
    Cache theo mtime — sửa luật là ăn ngay, không mở file mỗi request."""
    duong = _duong_luat()
    if not duong.exists():
        return []
    khoa = (str(duong), duong.stat().st_mtime)
    if khoa in _cache_luat:
        return _cache_luat[khoa]
    du_lieu = json.loads(duong.read_text(encoding="utf-8-sig"))
    ket = [v for v in du_lieu.get("viec", [])
           if all(v.get(k) for k in ("ma", "ten", "chu_ky_phut"))]
    _cache_luat.clear()
    _cache_luat[khoa] = ket
    return ket


def ghi_nhip(ma: str) -> bool:
    """Ghi nhịp cho việc ĐÃ KHAI trong luật; mã lạ → False (fail-closed)."""
    if not any(v["ma"] == ma for v in doc_luat()):
        return False
    duong = _duong_data()
    duong.parent.mkdir(parents=True, exist_ok=True)
    du_lieu = {}
    if duong.exists():
        try:
            du_lieu = json.loads(duong.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            du_lieu = {}  # file hỏng → làm lại, nhịp là dữ liệu tái tạo được
    du_lieu[ma] = datetime.fromtimestamp(_gio()).isoformat(timespec="seconds")
    tmp = duong.with_suffix(".tmp")
    tmp.write_text(json.dumps(du_lieu, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(duong)
    return True


def tom_tat() -> list[dict]:
    """[{ma, ten, chu_ky_phut, nhip_cuoi, tre}] — chưa từng có nhịp → tre=None
    ('chưa có nhịp', nói thẳng — không đoán ok/trễ)."""
    duong = _duong_data()
    nhip = {}
    if duong.exists():
        try:
            nhip = json.loads(duong.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            nhip = {}
    bay_gio = _gio()
    ket = []
    for v in doc_luat():
        cuoi = nhip.get(v["ma"])
        tre = None
        if cuoi:
            try:
                phut = (bay_gio - datetime.fromisoformat(cuoi).timestamp()) / 60
                tre = phut > v["chu_ky_phut"]
            except ValueError:
                cuoi, tre = None, None
        ket.append({"ma": v["ma"], "ten": v["ten"],
                    "chu_ky_phut": v["chu_ky_phut"],
                    "nhip_cuoi": cuoi, "tre": tre})
    return ket
