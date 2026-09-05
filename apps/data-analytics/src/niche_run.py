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

import json
import os
from nen.common import token_noi_bo
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
_dang_dong_goi: set[str] = set()    # project đang đóng gói nền (19/08)


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
    r = requests.get(f"{goc}/api/cau-hinh/api-khoa/niche-research", timeout=5,
                     headers=token_noi_bo.header())
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


def _thu_muc(project: str) -> Path:
    return Path(os.environ.get("NICHE_PROJECTS_DIR")
                or _ROOT / "data" / "niche-research" / "projects") / project


def can_dong_goi(project: str) -> bool:
    """Run đã xong nhưng CHƯA đóng gói (writer+builder+snapshot)?

    Sự cố 19/08 (user: 'chạy Space/Spain mà tool không hiện gì'): chuỗi đóng gói
    chỉ chạy khi tab dashboard còn mở để poll — đóng tab là báo cáo nằm trên đĩa
    mà dashboard (đọc theo snapshot) không thấy, cũng không báo vỡ ở đâu. Hàm này
    cho trang tự phát hiện: có file Report mà chưa snapshot / snapshot cũ hơn."""
    d = _thu_muc(project)
    rp = d / "Report"
    if not rp.is_dir():
        return False
    files = [f for f in rp.glob("*") if f.is_file() and not f.name.startswith("~$")]
    if not files:
        return False
    moi_nhat = max(f.stat().st_mtime for f in files)
    idx = d / "snapshots" / "index.json"
    if not idx.is_file():
        return True
    try:
        so = json.loads(idx.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    if not so:
        return True
    thu_muc_snap = d / "snapshots" / so[-1]["id"]
    if not thu_muc_snap.is_dir():
        return True
    return moi_nhat > thu_muc_snap.stat().st_mtime + 1


def dong_goi_nen(project: str) -> None:
    """Đóng gói NỀN (thread) — trang không chờ; chống chạy trùng bằng _dang_dong_goi."""
    with _snapshot_lock:
        if project in _dang_dong_goi:
            return
        _dang_dong_goi.add(project)

    def _chay():
        try:
            _snapshot(project)
        finally:
            with _snapshot_lock:
                _dang_dong_goi.discard(project)

    threading.Thread(target=_chay, daemon=True).start()


def dang_dong_goi(project: str) -> bool:
    with _snapshot_lock:
        return project in _dang_dong_goi


def tinh_trang(project: str, so_dong: int = 12) -> dict:
    """Trạng thái run ĐỌC TỪ ĐĨA (không cần service): đuôi stdout.log + mốc thời
    gian — để trang nói được 'vỡ ở đâu' thay vì im lặng (user 19/08)."""
    d = _thu_muc(project)
    log = d / "niche-data" / "stdout.log"
    if not log.is_file():
        return {"co_log": False}
    try:
        dong = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"co_log": False}
    duoi = [x for x in dong if x.strip()][-so_dong:]
    xong = any("Pipeline done" in x for x in dong[-40:])
    loi = [x for x in dong[-80:]
           if ("Traceback" in x or "ERROR" in x or "LOI" in x or "Error:" in x)]
    from datetime import datetime as _dt
    return {"co_log": True, "xong": xong, "duoi": duoi, "loi": loi[-3:],
            "luc": _dt.fromtimestamp(log.stat().st_mtime).strftime("%d/%m %H:%M")}


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
