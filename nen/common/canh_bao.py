# -*- coding: utf-8 -*-
"""Kênh cảnh báo đẩy ra ngoài (B5 giám sát, 31/08/2026) — ntfy.sh, stdlib-only.

Lift từ khuôn radary/scan.py::ntfy_send (kênh push duy nhất hệ đã chốt —
roadmap radary: "Push: ntfy duy nhất") nhưng KHÔNG phụ thuộc state radary.
Owner đặt env GIAM_SAT_NTFY_TOPIC (start-all.ps1) + subscribe topic đó trên
điện thoại là nhận; chưa đặt topic → gui() trả False lặng lẽ, cảnh báo vẫn
nằm ở sổ sự cố (nhat_ky app=giam-sat) + tab Applications.

Kênh chết KHÔNG được giết vòng giám sát: mọi lỗi mạng nuốt, trả False.
"""
from __future__ import annotations

import json
import os
import urllib.request

_NTFY = "https://ntfy.sh"


def _post(url: str, body: bytes) -> None:
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5).close()


def gui(tieu_de: str, noi_dung: str = "", muc: str = "high") -> bool:
    topic = os.environ.get("GIAM_SAT_NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        body = json.dumps({"topic": topic, "title": tieu_de,
                           "message": noi_dung or tieu_de,
                           "priority": muc, "tags": ["rotating_light"]},
                          ensure_ascii=False).encode("utf-8")
        _post(f"{_NTFY}/", body)
        return True
    except OSError:
        return False
