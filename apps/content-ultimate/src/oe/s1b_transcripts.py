"""S1b — Lấy transcript có timestamp cho mọi video của run (transcriptapi.com).

Chạy:  python3 -m oe.s1b_transcripts --run <tên>

Tách khỏi S1 vì TỐN CREDIT (1/video). Resumable: transcript đã có trên đĩa thì bỏ qua,
in COST GUARD trước khi tải. 404 (không transcript) đánh dấu để không gọi lại. 402/401 dừng batch.
"""
from __future__ import annotations

import argparse

from . import common
from . import transcript as T


def run(run_name: str) -> None:
    rd = common.run_dir(run_name)
    videos = common.read_json(rd / "videos.json")
    tdir = rd / "transcripts"
    tdir.mkdir(exist_ok=True)
    index_path = tdir / "index.json"
    index = common.read_json(index_path) if index_path.exists() else {}

    key = T.load_key(common.ROOT / ".env")
    todo = [v for v in videos if index.get(v, {}).get("status") not in ("ok", "no_transcript")]
    print(f"COST GUARD — {len(todo)} transcript cần tải (~{len(todo)} credit); "
          f"{len(videos) - len(todo)} đã có.", flush=True)

    for i, vid in enumerate(todo, 1):
        title = (videos[vid].get("title") or vid)[:45]
        print(f"[{i}/{len(todo)}] {vid} {title!r}…", flush=True)
        try:
            segs = T.fetch(vid, key)
        except T.NoTranscript:
            index[vid] = {"status": "no_transcript"}
            common.write_json(index_path, index)
            print("    404 — không có transcript, đánh dấu bỏ qua", flush=True)
            continue
        except T.TranscriptBillingError as e:
            print(f"    DỪNG: {e}", flush=True)
            break
        common.write_json(tdir / f"{vid}.json",
                          [{"idx": s.idx, "start": s.start, "end": s.end, "text": s.text} for s in segs])
        index[vid] = {"status": "ok", "segments": len(segs)}
        common.write_json(index_path, index)          # checkpoint sau mỗi video
        print(f"    ok — {len(segs)} đoạn", flush=True)

    ok = sum(1 for m in index.values() if m.get("status") == "ok")
    print(f"\nS1b xong → {tdir} ({ok} transcript ok)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S1b fetch transcripts")
    ap.add_argument("--run", required=True)
    main_args = ap.parse_args(argv)
    run(main_args.run)


if __name__ == "__main__":
    main()
