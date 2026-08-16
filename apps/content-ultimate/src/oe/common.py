"""Tiện ích dùng chung: đọc videos.txt, tách video id, quản lý thư mục run."""
from __future__ import annotations

import json
import math
import re
import os
from pathlib import Path

ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2
RUNS = ROOT / "runs"

_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_KEY_RE = re.compile(r"^AIza[A-Za-z0-9_-]{20,}$")


def parse_videos_txt(path: str | Path) -> tuple[list[str], list[str]]:
    """Đọc file trộn API key + URL/ID (convention giống competitors.txt).

    Trả (danh sách video_id theo thứ tự, danh sách API key để xoay quota). Bỏ dòng trống / '#'.
    """
    ids: list[str] = []
    keys: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if _KEY_RE.match(s):
            if s not in keys:
                keys.append(s)
            continue
        vid = extract_video_id(s)
        if vid and vid not in ids:
            ids.append(vid)
    return ids, keys


def extract_video_id(s: str) -> str | None:
    s = s.strip()
    if _BARE_ID_RE.match(s):
        return s
    m = _ID_RE.search(s)
    return m.group(1) if m else None


def source_weight(view_count: int | None, csv_weight: float | None = None) -> float:
    """Trọng số video nguồn cho peak_score.

    Ưu tiên OX/ratio từ tool trước (csv_weight). Fallback: log10(view) chuẩn hoá về ~[0.5, 2].
    """
    if csv_weight is not None:
        return round(float(csv_weight), 3)
    if not view_count or view_count < 1:
        return 0.5
    # 1k view -> ~0.5 ; 1M -> ~1.25 ; 100M -> ~2.0
    return round(min(2.0, max(0.5, math.log10(view_count) / 4)), 3)


def run_dir(name: str, *, create: bool = False) -> Path:
    d = RUNS / _slug(name)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s) or "run"


def read_json(path: Path) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
