"""Lấy & chuẩn hoá heatmap Most Replayed — MODULE DUY NHẤT chạm tới heatmap.

Luật A3 (CLAUDE.md): heatmap là API undocumented, dễ vỡ khi YouTube đổi format.
Mọi việc lấy/parse heatmap phải nằm ở đây — vỡ thì sửa đúng một chỗ.

Format thực đo trên video thật (yt-dlp, 2026-07-03, id TGRxwskKn10):
    d["heatmap"] = [ {"start_time": float, "end_time": float, "value": float 0..1}, ... ]
    - luôn 100 bucket khi có; bucket = duration/100 giây.
    - value đã normalize 0..1; bucket đầu thường cao nhất (ai cũng xem từ đầu).
    - field vắng (None) ở video thiếu view/mới → caller tự fallback sang comment timestamps.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# Lỗi chập chờn của YouTube (đo thực tế: ~2/6 video mỗi lần chạy) — retry thường khỏi.
_TRANSIENT = ("page needs to be reloaded", "Sign in to confirm", "HTTP Error 429")

# Chống bot-check trên IP datacenter (VPS, đo 2026-07-09: "Sign in to confirm you're
# not a bot" hàng loạt): nếu có cookies.txt ở gốc tool thì mọi lượt yt-dlp tự kèm
# --cookies. Xuất file này từ trình duyệt — xem deploy/SETUP-VPS.md.
_COOKIES_FILE = Path(__file__).resolve().parents[2] / "cookies.txt"


class HeatmapUnavailable(Exception):
    """Video không có heatmap (chưa đủ view / YouTube không trả field)."""


@dataclass(frozen=True)
class Bucket:
    start: float
    end: float
    value: float


def _yt_dlp_bin() -> str:
    # Máy công ty (Windows, 03/08/2026): tác vụ nền chạy python của .venv TRỰC TIẾP —
    # PATH của SYSTEM không có .venv\Scripts nên shutil.which không thấy yt-dlp dù đã
    # pip install vào venv. Tìm CẠNH python đang chạy trước, PATH sau (VPS cũ vẫn chạy).
    import sys
    canh_python = Path(sys.executable).parent / ("yt-dlp.exe" if sys.platform == "win32"
                                                 else "yt-dlp")
    if canh_python.is_file():
        return str(canh_python)
    exe = shutil.which("yt-dlp")
    if not exe:
        raise RuntimeError("Không tìm thấy yt-dlp (cạnh python venv lẫn PATH) — "
                           "pip install yt-dlp vào .venv của tool.")
    return exe


def fetch_info_json(url_or_id: str, *, timeout: int = 120) -> dict:
    """Gọi yt-dlp một lần, trả nguyên info-json (chứa cả heatmap + metadata).

    Tách riêng để S1 tái dùng: một lần gọi mạng lấy được cả metadata lẫn heatmap.
    Dùng `--write-info-json` ra file tạm (KHÔNG dùng `--dump-single-json`: đo thực tế
    2026-07-03 thấy dump-single-json bị YouTube trả "page needs to be reloaded" trong khi
    write-info-json chạy ổn trên cùng video).
    """
    exe = _yt_dlp_bin()
    # ID trần bắt đầu bằng '-' (hợp lệ với YouTube, ~1/64 video) bị yt-dlp đọc thành
    # CỜ: '-ujJNlvFCxM' → '-u …' = --username → treo chờ mật khẩu tới TimeoutExpired,
    # cả run chết với thông báo bot-check gây hiểu nhầm (bug thật 06/08/2026, run
    # "Hinge is Completely F*cked"). Chuẩn hoá mọi ID trần thành URL đầy đủ.
    url = url_or_id if "://" in url_or_id else f"https://www.youtube.com/watch?v={url_or_id}"
    last_msg = "?"
    for attempt in range(3):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "info"
            # --ignore-no-formats-error: ta chỉ cần metadata + heatmap trong info.json,
            # KHÔNG tải video. YouTube đổi player API (2026-07) khiến yt-dlp không khớp
            # format và bỏ luôn info.json nếu không có cờ này (đo thật trên VPS 2026-07-10).
            cmd = [exe, "--skip-download", "--write-info-json", "--no-warnings",
                   "--ignore-no-formats-error", "-o", str(out)]
            if _COOKIES_FILE.exists():
                cmd += ["--cookies", str(_COOKIES_FILE)]
            proc = subprocess.run(
                [*cmd, url],
                capture_output=True, text=True, timeout=timeout,
            )
            info_file = out.with_suffix(".info.json")
            if info_file.exists():
                return json.loads(info_file.read_text(encoding="utf-8"))
            err = (proc.stderr or "").strip().splitlines()
            last_msg = next((l for l in reversed(err) if l.startswith("ERROR")),
                            err[-1] if err else "?")
        if any(t in last_msg for t in _TRANSIENT) and attempt < 2:
            time.sleep(2 * (attempt + 1))            # backoff cho lỗi chập chờn
            continue
        break
    raise RuntimeError(f"yt-dlp lỗi cho {url_or_id!r}: {last_msg[:300]}")


def parse_heatmap(info: dict) -> list[Bucket]:
    """Rút heatmap từ info-json. Raise HeatmapUnavailable nếu không có."""
    raw = info.get("heatmap")
    if not raw:
        raise HeatmapUnavailable(info.get("id", "?"))
    out = [
        Bucket(float(b["start_time"]), float(b["end_time"]), float(b["value"]))
        for b in raw
        if b.get("value") is not None
    ]
    if not out:
        raise HeatmapUnavailable(info.get("id", "?"))
    return out


def fetch_heatmap(url_or_id: str, *, timeout: int = 120) -> list[Bucket]:
    """Tiện ích: lấy info-json rồi parse heatmap trong một bước."""
    return parse_heatmap(fetch_info_json(url_or_id, timeout=timeout))
