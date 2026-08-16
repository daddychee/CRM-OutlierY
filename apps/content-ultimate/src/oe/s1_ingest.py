"""S1 — Ingest. Đọc videos.txt → lấy metadata + heatmap từng video → videos.json.

Chạy:  python3 -m oe.s1_ingest <videos.txt> [--run <tên>]

Idempotent (luật A3): video đã có trong videos.json với heatmap thì bỏ qua, không gọi lại
mạng — thêm link mới rồi chạy lại chỉ tải phần thiếu. Xoá videos.json để ép tải lại toàn bộ.

Transcript & comments KHÔNG lấy ở bước này:
- Video thật (2M view) đo được KHÔNG có caption nào (kể cả auto) → transcript phải qua
  transcriptapi.com (tốn credit) ở stage riêng, không nhét vào S1.
- Comments (5700 cái) lấy ở stage phục vụ cột Hỏi/Trích, cũng tách riêng vì tốn thời gian.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import common
from .heatmap import fetch_info_json, parse_heatmap, HeatmapUnavailable


def ingest(videos_txt: str, run_name: str | None = None) -> Path:
    ids, _key = common.parse_videos_txt(videos_txt)
    if not ids:
        sys.exit(f"Không tìm thấy video id nào trong {videos_txt}")

    run_name = run_name or Path(videos_txt).stem
    rd = common.run_dir(run_name, create=True)
    vpath = rd / "videos.json"
    hpath = rd / "heatmaps.json"

    videos = common.read_json(vpath) if vpath.exists() else {}
    heatmaps = common.read_json(hpath) if hpath.exists() else {}

    for i, vid in enumerate(ids, 1):
        if vid in videos and videos[vid].get("has_heatmap") is not None:
            print(f"[{i}/{len(ids)}] {vid} — đã có, bỏ qua", flush=True)
            continue
        print(f"[{i}/{len(ids)}] {vid} — đang lấy metadata + heatmap…", flush=True)
        try:
            info = fetch_info_json(vid)
        except Exception as e:                       # noqa: BLE001 — log & tiếp tục video khác
            print(f"    LỖI: {e}", flush=True)
            continue

        try:
            buckets = parse_heatmap(info)
            heatmaps[vid] = [b.__dict__ for b in buckets]
            has_hm = True
        except HeatmapUnavailable:
            has_hm = False
            print("    (chưa có heatmap — sẽ chạy bằng comment timestamps ở stage sau)", flush=True)

        vc = info.get("view_count")
        videos[vid] = {
            "video_id": vid,
            "title": info.get("title"),
            "duration": info.get("duration"),
            "view_count": vc,
            "channel": info.get("channel"),
            "channel_id": info.get("channel_id"),
            "upload_date": info.get("upload_date"),
            "comment_count": info.get("comment_count"),
            "source_weight": common.source_weight(vc),
            "has_heatmap": has_hm,
            "has_captions": bool(info.get("subtitles") or info.get("automatic_captions")),
        }
        common.write_json(vpath, videos)             # checkpoint sau mỗi video
        common.write_json(hpath, heatmaps)

    if not videos:
        # Fail TO thay vì "0 video" êm ru rồi S1b chết khó hiểu vì thiếu videos.json
        # (bài học chạy thật trên VPS 2026-07-09).
        sys.exit("S1: không lấy được video nào — link hỏng, hoặc YouTube chặn bot IP "
                 "server (cần cookies.txt ở gốc tool — xem deploy/SETUP-VPS.md).")
    n = len(videos)
    n_hm = sum(1 for v in videos.values() if v["has_heatmap"])
    n_nodur = sum(1 for v in videos.values() if not v.get("duration"))
    print(f"\nS1 xong → {vpath}")
    print(f"  {n} video, {n_hm} có heatmap.")
    # Cảnh báo bị chặn IP / cookies hết hạn: yt-dlp vẫn lấy được title/view nhưng THIẾU
    # duration + heatmap hàng loạt = dấu hiệu 'Sign in to confirm you're not a bot' (2026-07-14).
    if n and (n_nodur >= max(2, n // 2) or n_hm == 0):
        print("⚠ CẢNH BÁO: " + f"{n_nodur}/{n} video THIẾU duration"
              + (f", {n - n_hm}/{n} THIẾU heatmap" if n_hm < n else "") + ".")
        print("  Rất có thể YouTube CHẶN IP máy chủ (metadata nghèo, không có player response).")
        print("  → Bấm nút 🍪 Cookies trên board, dán cookies.txt mới, rồi chạy lại pipeline.")
        print("  (pos/vùng hook-ending sẽ thiếu chính xác cho tới khi có duration đầy đủ.)")
    return rd


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S1 ingest — metadata + heatmap")
    ap.add_argument("videos_txt")
    ap.add_argument("--run", default=None, help="tên run (mặc định = tên file videos.txt)")
    args = ap.parse_args(argv)
    ingest(args.videos_txt, args.run)


if __name__ == "__main__":
    main()
