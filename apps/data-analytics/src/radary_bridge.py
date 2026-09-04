# -*- coding: utf-8 -*-
"""Cầu ĐỌC pool đối thủ từ RadarY (:9111) cho New Research.

Phương án 2 user chốt 19/08: nghiên cứu ngách chạy từ POOL SẴN CÓ — workspace
(Data Pool) RadarY đã gắn ngách × thị trường theo mã danh bạ, hết dán tay.
Chỉ ĐỌC qua API loopback kèm claims người dùng (lệ V3: cầu nối API, không import
chéo); RadarY tự kiểm quyền theo vai SSO của chính nó. Mọi lời gọi có timeout.
"""
from __future__ import annotations

import os

import requests


def _api() -> str:
    return os.environ.get("RADARY_API", "http://127.0.0.1:9111").rstrip("/")


def _headers(user: dict) -> dict:
    return {"X-Remote-User": user.get("ten", ""),
            "X-Remote-Level": str(user.get("level", 0)),
            "X-Remote-Role": user.get("vai", "")}


def ds_pool(user: dict, ngach_ma: str, tt_ma: str) -> list[dict]:
    """Pool ĐÚNG ngách × thị trường — [{id, name, channels}] (channels = số kênh
    active RadarY đếm sẵn). Workspace chưa gắn ngách/thị trường không hiện."""
    r = requests.get(f"{_api()}/api/workspaces", headers=_headers(user), timeout=10)
    r.raise_for_status()
    return [{"id": w["id"], "name": w["name"], "channels": w.get("channels", 0)}
            for w in r.json()
            if w.get("ngach") == ngach_ma and w.get("market") == tt_ma]


class LoiPool(Exception):
    """Lỗi đọc pool đã DỊCH sang tiếng Việt — UI in thẳng, không lộ URL nội bộ
    (user 19/08 thấy '403 Client Error ... http://127.0.0.1:9111/...')."""


def kenh_cua_pool(user: dict, ws_id: int) -> list[str]:
    """Dòng competitors từ kênh ACTIVE của pool: 'Title | URL kênh' — đúng khuôn
    competitors.txt pipeline vẫn ăn (kênh tắt active trong RadarY không đưa vào)."""
    r = requests.get(f"{_api()}/api/workspaces/{ws_id}/channels",
                     headers=_headers(user), timeout=15)
    if r.status_code == 403:
        raise LoiPool("Tài khoản của bạn chưa đủ quyền đọc pool này trong RadarY — "
                      "nhờ Owner mở quyền RadarY (hoặc chọn pool khác).")
    if r.status_code == 404:
        raise LoiPool("Pool này không còn trong RadarY (đã xóa hoặc ngoài phạm vi "
                      "niche của bạn) — chọn lại pool.")
    r.raise_for_status()
    return [f"{(k.get('title') or k['yt_id']).strip()} | "
            f"https://www.youtube.com/channel/{k['yt_id']}"
            for k in r.json() if k.get("active", 1) and k.get("yt_id")]
