# -*- coding: utf-8 -*-
"""Hợp đồng app — đọc nen/rules/apps.json (mảnh nền, khuôn manifest).

Gateway proxy/menu/sức-khỏe đều đi theo hợp đồng này; app không khai = không tồn tại
với tầng nền. Đổi hợp đồng không cần sửa code gateway.
"""
from __future__ import annotations

import json
from pathlib import Path

DUONG_MAC_DINH = Path(__file__).resolve().parents[1] / "rules" / "apps.json"

_BAT_BUOC = ("slug", "ten", "cong", "health")


def doc_hop_dong(duong: Path | str | None = None) -> list[dict]:
    """Đọc danh sách app. App thiếu trường bắt buộc → bỏ qua kèm lý do in kèm
    (không chết cả gateway vì một mục hỏng)."""
    duong = Path(duong) if duong else DUONG_MAC_DINH
    if not duong.exists():
        return []
    du_lieu = json.loads(duong.read_text(encoding="utf-8-sig"))
    ket_qua = []
    for muc in du_lieu.get("apps", []):
        if all(muc.get(k) for k in _BAT_BUOC):
            muc.setdefault("tien_to", [])
            muc.setdefault("du_lieu", [])
            ket_qua.append(muc)
    return ket_qua


def tim_app(slug: str, duong: Path | str | None = None) -> dict | None:
    for app in doc_hop_dong(duong):
        if app["slug"] == slug:
            return app
    return None
