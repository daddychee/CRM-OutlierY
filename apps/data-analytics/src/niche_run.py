# -*- coding: utf-8 -*-
"""Cầu CHẠY pipeline ngách qua service niche-research (:9113) + snapshot khi xong.

Tính năng 2 user chốt 18/08: "báo cáo mới sinh ra được cập nhật trên dashboard".
Luồng: nút Run → POST resume tới service (key YouTube service tự lấy từ KÉT) →
dashboard poll /niche/chay/<project>/trang-thai → thấy chạy xong thì bridge tự
ĐÓNG BĂNG snapshot (gọi scripts/snapshot.py của niche-research như CLI độc lập —
`ponytail:` chuyển thành endpoint /api/snapshot khi niche server được restart kèm
code mới) → trả done=true → JS reload trang, số mới hiện.

Mọi lời gọi HTTP có timeout (bài học SDK-600s hệ cũ); service chết → lỗi rõ.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import requests

_APP_DIR = Path(__file__).resolve().parents[1]
_ROOT = _APP_DIR.parents[1]
_SNAPSHOT_PY = _ROOT / "apps" / "niche-research" / "scripts" / "snapshot.py"

# chống snapshot đúp khi nhiều tab cùng poll thấy "vừa xong"
_snapshot_lock = threading.Lock()
_da_snapshot: set[str] = set()      # project đã snapshot cho lần-xong hiện tại


def _api() -> str:
    return os.environ.get("NICHE_API", "http://127.0.0.1:9113").rstrip("/")


def _headers(user: dict) -> dict:
    """Chuyển claims của user hiện tại sang service (loopback, cùng khuôn gateway)."""
    return {"X-Remote-User": user.get("ten", ""),
            "X-Remote-Level": str(user.get("level", 0)),
            "X-Remote-Role": user.get("vai", "")}


def chay_lai(project: str, user: dict) -> dict:
    """Resume/chạy lại project đã có pool — service tự lo key từ KÉT."""
    r = requests.post(f"{_api()}/api/resume/{project}", headers=_headers(user), timeout=15)
    r.raise_for_status()
    with _snapshot_lock:
        _da_snapshot.discard(project)      # lần chạy mới → cho phép snapshot mới
    return r.json()


def trang_thai(project: str, user: dict) -> dict:
    """Trạng thái từ service; khi vừa chạy xong + có report → snapshot MỘT lần.
    Trả {running, has_report, done_moi (vừa đóng băng snapshot xong)}."""
    r = requests.get(f"{_api()}/api/status/{project}", headers=_headers(user), timeout=10)
    r.raise_for_status()
    st = r.json()
    done_moi = False
    if not st.get("running") and st.get("has_report"):
        with _snapshot_lock:
            if project not in _da_snapshot:
                _da_snapshot.add(project)
                done_moi = _snapshot(project)
    return {"running": bool(st.get("running")), "has_report": bool(st.get("has_report")),
            "done_moi": done_moi}


def _snapshot(project: str) -> bool:
    """Đóng băng lần chạy hiện tại bằng script CLI của niche-research (best-effort)."""
    duong = Path(os.environ.get("NICHE_PROJECTS_DIR")
                 or _ROOT / "data" / "niche-research" / "projects") / project
    try:
        cp = subprocess.run([sys.executable, str(_SNAPSHOT_PY), str(duong)],
                            capture_output=True, timeout=120,
                            env={**os.environ, "PYTHONUTF8": "1"})
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
