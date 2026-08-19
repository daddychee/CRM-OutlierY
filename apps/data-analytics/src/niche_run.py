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
_BUILD_BC_PY = _ROOT / "apps" / "niche-research" / "scripts" / "19_build_bao_cao.py"
_WRITER_PY = _ROOT / "apps" / "niche-research" / "scripts" / "20_bao_cao_writer.py"

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


def kiem_khoa(llm: bool = False, deepdive: bool = False) -> dict:
    """Bước 'check API' TRƯỚC Researching (user chốt 19/08): đọc cấp phát KÉT của
    niche-research qua gateway loopback — đúng nguồn service sẽ dùng lúc chạy
    (khoa_v3), CHỈ trả boolean từng việc, tuyệt đối không lộ key ra response."""
    goc = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000").rstrip("/")
    r = requests.get(f"{goc}/api/cau-hinh/api-khoa/niche-research", timeout=5)
    r.raise_for_status()
    cap = r.json() or {}

    def _co(viec: str) -> bool:
        return any(k.get("key") for k in (cap.get(viec) or {}).get("khoa", []))

    kq = {"youtube": _co("quet_kenh")}
    if llm:
        kq["llm"] = _co("phan_tich")
    if deepdive:
        kq["transcript"] = _co("lay_transcript")
    return {"ok": all(kq.values()), "chi_tiet": kq,
            "thieu": [v for v, ok in kq.items() if not ok]}


def chay_lai(project: str, user: dict) -> dict:
    """Resume/chạy lại project đã có pool — service tự lo key từ KÉT."""
    r = requests.post(f"{_api()}/api/resume/{project}", headers=_headers(user), timeout=15)
    r.raise_for_status()
    with _snapshot_lock:
        _da_snapshot.discard(project)      # lần chạy mới → cho phép snapshot mới
    return r.json()


def chay_moi(project: str, competitors_text: str, user: dict, *,
             skip_comments: bool = False, force: bool = False,
             deepdive: bool = False, llm: bool = False) -> dict:
    """Chạy project với pool (mới/cộng dồn) — upload competitors.txt cho service,
    service tự lo key từ KÉT (thiếu key → service 503 rõ). 4 cờ = TOÀN BỘ tùy chọn
    /api/run của service (kiểm 18/08 theo yêu cầu user: pipeline không cần nhập
    liệu dữ liệu nào khác ngoài pool — niche/thị trường lấy từ danh bạ)."""
    data = {"name": project, "skip_comments": str(skip_comments).lower(),
            "force": str(force).lower(), "deepdive": str(deepdive).lower(),
            "llm": str(llm).lower()}
    r = requests.post(f"{_api()}/api/run", data=data,
                      files={"competitors": ("competitors.txt", competitors_text.encode("utf-8"))},
                      headers=_headers(user), timeout=30)
    r.raise_for_status()
    with _snapshot_lock:
        _da_snapshot.discard(project)
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
    """Đóng băng lần chạy hiện tại bằng script CLI của niche-research (best-effort).
    TRƯỚC snapshot: build BÁO CÁO GỘP HTML (19_build_bao_cao.py — tầng 1, 19/08)
    để mọi run tự có HTML trong Report/; build hỏng chỉ mất HTML, không chặn snapshot."""
    duong = Path(os.environ.get("NICHE_PROJECTS_DIR")
                 or _ROOT / "data" / "niche-research" / "projects") / project
    try:
        # tầng 2 TRƯỚC (writer LLM sinh bao_cao_nghia.json — 1 lời gọi/run, key KÉT;
        # hỏng chỉ mất tầng NGHĨA, builder giữ slot chờ) rồi tầng 1 render HTML.
        subprocess.run([sys.executable, str(_WRITER_PY), str(duong)],
                       capture_output=True, timeout=300,
                       env={**os.environ, "PYTHONUTF8": "1"})
        subprocess.run([sys.executable, str(_BUILD_BC_PY), str(duong)],
                       capture_output=True, timeout=120,
                       env={**os.environ, "PYTHONUTF8": "1"})
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        cp = subprocess.run([sys.executable, str(_SNAPSHOT_PY), str(duong)],
                            capture_output=True, timeout=120,
                            env={**os.environ, "PYTHONUTF8": "1"})
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
