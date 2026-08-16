"""Lấy transcript có timestamp qua transcriptapi.com — MODULE DUY NHẤT chạm API này.

Vì sao transcriptapi.com là đường CHÍNH (không phải fallback): đo thực tế 2026-07-03 thấy
video 2M view KHÔNG có caption nào (kể cả auto) → không thể dựa vào caption track.

API (giống Niche Research S15, nhưng BẬT timestamp vì ta cần map peak↔đoạn + neo beat):
  GET https://transcriptapi.com/api/v2/youtube/transcript?video_url=<id>&format=json&include_timestamp=true
  Header: Authorization: Bearer <key>              (1 credit / call thành công)
  Format trả:  {"video_id","language","transcript":[{"text","start","duration"}, ...]}
  200 ok · 404 không có transcript (skip) · 402 hết credit (dừng) · 401 key sai (dừng) · 429/503 retry.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import urllib.request
import urllib.error
import json as _json

ENDPOINT = "https://transcriptapi.com/api/v2/youtube/transcript"


class NoTranscript(Exception):
    """404 — video không có transcript."""


class TranscriptBillingError(Exception):
    """402/401 — hết credit hoặc key sai; dừng cả batch."""


@dataclass(frozen=True)
class Segment:
    idx: int          # chỉ số dòng — dùng để NEO beat (LLM không tự viết timestamp)
    start: float
    end: float
    text: str


def load_key(env_path: str | Path) -> str:
    """Đọc TRANSCRIPT_API_KEY: env thật ưu tiên, rồi tới file .env (giống get_env Niche Research)."""
    import os
    if os.environ.get("TRANSCRIPT_API_KEY"):
        return os.environ["TRANSCRIPT_API_KEY"]
    p = Path(env_path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TRANSCRIPT_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("Không có TRANSCRIPT_API_KEY (env hoặc .env).")


def fetch(video_id: str, key: str, *, timeout: int = 90) -> list[Segment]:
    url = f"{ENDPOINT}?video_url={video_id}&format=json&include_timestamp=true"
    # User-Agent BẮT BUỘC: transcriptapi.com trả 403 cho request thiếu UA (đo 2026-07-03).
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}",
        "User-Agent": "outline-extractor/1.0",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = _json.loads(r.read().decode("utf-8"))
            return _to_segments(data)
        except urllib.error.HTTPError as e:
            code = e.code
            if code == 404:
                raise NoTranscript(video_id)
            if code in (401, 402):
                raise TranscriptBillingError(f"HTTP {code} — xem https://transcriptapi.com/billing")
            if code in (429, 408, 503) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"transcript {video_id}: hết retry")


def _to_segments(data: dict) -> list[Segment]:
    out = []
    for i, s in enumerate(data.get("transcript", [])):
        start = float(s["start"])
        out.append(Segment(i, start, start + float(s.get("duration", 0.0)), s["text"].strip()))
    return out


def excerpt_for_window(segs: list[Segment], t_start: float, t_end: float) -> tuple[str, int, int]:
    """Đoạn transcript trong cửa sổ [t_start, t_end] quanh một đỉnh.

    Trả (text ghép, seg_idx_đầu, seg_idx_cuối). Dùng để gắn transcript_excerpt cho peak
    và cho S3 neo beat theo chỉ số dòng.
    """
    hit = [s for s in segs if s.end >= t_start and s.start <= t_end]
    if not hit:
        return "", -1, -1
    return " ".join(s.text for s in hit), hit[0].idx, hit[-1].idx
