"""S2 — Peak detection. Đọc run của S1 → phát hiện đỉnh mỗi video → peaks.json.

Chạy:  python3 -m oe.s2_peaks --run <tên>

Đọc heatmaps.json (S1 ghi), chạy detect_peaks (thuần, đã test), ghi peaks.json.
Video không có heatmap → bỏ qua ở đây, chờ fallback comment-timestamps stage sau.
"""
from __future__ import annotations

import argparse

from . import common
from .heatmap import Bucket
from .peaks import detect_peaks
from .transcript import Segment, excerpt_for_window


def _load_segments(rd, vid) -> list[Segment]:
    f = rd / "transcripts" / f"{vid}.json"
    if not f.exists():
        return []
    return [Segment(s["idx"], s["start"], s["end"], s["text"]) for s in common.read_json(f)]


def run_s2(run_name: str) -> None:
    rd = common.run_dir(run_name)
    hpath = rd / "heatmaps.json"
    if not hpath.exists():
        raise SystemExit(f"Chưa có {hpath} — chạy S1 trước.")

    videos = common.read_json(rd / "videos.json")
    heatmaps = common.read_json(hpath)

    out: dict[str, list[dict]] = {}
    for vid, raw in heatmaps.items():
        buckets = [Bucket(b["start"], b["end"], b["value"]) for b in raw]
        peaks = detect_peaks(buckets)
        segs = _load_segments(rd, vid)
        rows = []
        for p in peaks:
            d = p.as_dict()
            if segs:                                  # gắn đoạn transcript quanh đỉnh
                text, i0, i1 = excerpt_for_window(segs, p.t_start, p.t_end)
                d["transcript_excerpt"] = text
                d["seg_start_idx"] = i0
                d["seg_end_idx"] = i1
            rows.append(d)
        out[vid] = rows
        title = (videos.get(vid, {}).get("title") or vid)[:45]
        print(f"  {vid} {title!r}: {len(peaks)} đỉnh"
              + (f", mạnh nhất z={peaks[0].intensity_z}" if peaks else "")
              + (" +transcript" if segs else " (chưa có transcript)"), flush=True)

    common.write_json(rd / "peaks.json", out)
    total = sum(len(v) for v in out.values())
    print(f"\nS2 xong → {rd/'peaks.json'} ({total} đỉnh / {len(out)} video có heatmap)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S2 peak detection")
    ap.add_argument("--run", required=True)
    args = ap.parse_args(argv)
    run_s2(args.run)


if __name__ == "__main__":
    main()
