"""S1c — Lấy comment top cho mọi video của run (YouTube Data API, xoay key).

Chạy:  python3 -m oe.s1c_comments <videos.txt> --run <tên>

Resumable: video đã có comments/<vid>.json thì bỏ qua. Comment tắt → đánh dấu, không chặn.
Rẻ (~3 unit/video cho 300 comment). Ghi comments/<vid>.json + comments/index.json.
"""
from __future__ import annotations

import argparse

from . import common
from .comments import CommentClient, CommentsDisabled, AllKeysExhausted


def run(videos_txt: str, run_name: str, max_comments: int) -> None:
    _ids, keys = common.parse_videos_txt(videos_txt)
    if not keys:
        raise SystemExit(f"Không có YouTube API key trong {videos_txt}")
    rd = common.run_dir(run_name)
    videos = common.read_json(rd / "videos.json")
    cdir = rd / "comments"
    cdir.mkdir(exist_ok=True)
    index_path = cdir / "index.json"
    index = common.read_json(index_path) if index_path.exists() else {}

    client = CommentClient(keys)
    todo = [v for v in videos if index.get(v, {}).get("status") not in ("ok", "disabled")]
    print(f"{len(todo)} video cần lấy comment; {len(videos) - len(todo)} đã có.", flush=True)

    for i, vid in enumerate(todo, 1):
        title = (videos[vid].get("title") or vid)[:45]
        print(f"[{i}/{len(todo)}] {vid} {title!r}…", flush=True)
        try:
            comments = client.fetch(vid, max_comments=max_comments)
        except CommentsDisabled:
            index[vid] = {"status": "disabled"}
            common.write_json(index_path, index)
            print("    comment bị tắt, bỏ qua", flush=True)
            continue
        except AllKeysExhausted:
            print("    HẾT QUOTA mọi key — dừng, thêm key hoặc chờ rồi chạy lại", flush=True)
            break
        common.write_json(cdir / f"{vid}.json",
                          [{"text": c.text, "likes": c.likes, "replies": c.replies} for c in comments])
        index[vid] = {"status": "ok", "count": len(comments)}
        common.write_json(index_path, index)
        print(f"    ok — {len(comments)} comment", flush=True)

    ok = sum(1 for m in index.values() if m.get("status") == "ok")
    print(f"\nS1c xong → {cdir} ({ok} video có comment)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S1c fetch comments")
    ap.add_argument("videos_txt")
    ap.add_argument("--run", required=True)
    ap.add_argument("--max-comments", type=int, default=300)
    a = ap.parse_args(argv)
    run(a.videos_txt, a.run, a.max_comments)


if __name__ == "__main__":
    main()
