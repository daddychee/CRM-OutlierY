"""S3b — Chia transcript thành beat (LLM). Neo theo chỉ số dòng, Python quy đổi ra giây.

Chạy:  python3 -m oe.s3_beats --run <tên>

LLM chia mỗi video thành các beat (hook/setup/luận điểm/ví dụ/twist/payoff/CTA), mỗi beat
neo bằng seg_start_idx/seg_end_idx (KHÔNG để LLM tự viết mm:ss). Python quy đổi ra t_start/t_end
từ transcript, và join peak (đã label ở S3a) vào beat theo max overlap. Ghi: beats.json.
"""
from __future__ import annotations

import argparse

from . import common
from .llm import LLM, extract_json

BEAT_TYPES = "hook, setup, luận điểm, ví dụ, twist, payoff, CTA, chuyển ý"
SYSTEM = (
    "Bạn chia transcript video thành các BEAT — đơn vị kể chuyện liền mạch. Mỗi beat là một "
    f"khối nội dung có vai trò ({BEAT_TYPES}). Dùng đúng chỉ số dòng [idx] đã cho để đánh dấu "
    "beat bắt đầu/kết thúc ở dòng nào. KHÔNG bịa nội dung ngoài transcript. "
    "IMPORTANT: write every `summary` in ENGLISH regardless of the video language "
    "(outline luôn tiếng Anh). Chỉ trả JSON."
)


def _prompt(title: str, segs: list[dict]) -> str:
    lines = "\n".join(f'[{s["idx"]}] {s["text"]}' for s in segs)
    return (
        f'Video: "{title}". Transcript đánh số dòng bên dưới. Chia thành 8–20 beat theo mạch kể. '
        f'Trả JSON: [{{"seg_start_idx":<int>,"seg_end_idx":<int>,"type":"<vai trò>",'
        f'"summary":"<1 câu: beat này nói gì>"}}]. Beat phải phủ liên tục, không chồng lấn.\n\n'
        f"{lines}"
    )


def _seg_time(segs: list[dict], idx: int, which: str) -> float:
    for s in segs:
        if s["idx"] == idx:
            return s["start"] if which == "start" else s["end"]
    return 0.0


def extract_beats(llm: LLM, title: str, segs: list[dict]) -> list[dict]:
    raw = llm.complete(SYSTEM, _prompt(title, segs), max_tokens=6000)
    beats = extract_json(raw)
    out = []
    for b in beats:
        try:
            i0, i1 = int(b["seg_start_idx"]), int(b["seg_end_idx"])
        except (KeyError, ValueError, TypeError):
            continue
        out.append({
            "seg_start_idx": i0, "seg_end_idx": i1,
            "t_start": round(_seg_time(segs, i0, "start"), 2),
            "t_end": round(_seg_time(segs, i1, "end"), 2),
            "type": (b.get("type") or "").strip(),
            "summary": (b.get("summary") or "").strip(),
        })
    return out


def _join_peaks(beats: list[dict], peaks: list[dict]) -> None:
    """Gán mỗi peak value vào beat overlap lớn nhất (tất định)."""
    for b in beats:
        b["peak_types"] = []
        b["peak_z_w"] = 0.0
    for p in peaks:
        best, best_ov = None, 0.0
        for b in beats:
            ov = min(p["t_end"], b["t_end"]) - max(p["t_start"], b["t_start"])
            if ov > best_ov:
                best, best_ov = b, ov
        if best is not None:
            best["peak_types"].append(p.get("peak_type", "value"))
            if p.get("peak_type") == "value":
                best["peak_z_w"] = max(best["peak_z_w"], p["intensity_z"])


def run(run_name: str) -> None:
    rd = common.run_dir(run_name)
    videos = common.read_json(rd / "videos.json")
    peaks_by_vid = common.read_json(rd / "peaks.json")
    llm = LLM(common.ROOT / ".env")

    all_beats: dict[str, list[dict]] = {}
    for vid in videos:
        tf = rd / "transcripts" / f"{vid}.json"
        if not tf.exists():
            print(f"  {vid}: chưa có transcript, bỏ qua", flush=True)
            continue
        segs = common.read_json(tf)
        title = videos[vid].get("title") or vid
        beats = extract_beats(llm, title, segs)
        _join_peaks(beats, peaks_by_vid.get(vid, []))
        all_beats[vid] = beats
        withpeak = sum(1 for b in beats if b["peak_z_w"] > 0)
        print(f"  {title[:45]!r}: {len(beats)} beat ({withpeak} trùng đỉnh value)", flush=True)

    common.write_json(rd / "beats.json", all_beats)
    tot = sum(len(v) for v in all_beats.values())
    print(f"\nS3b xong → {rd/'beats.json'} ({tot} beat / {len(all_beats)} video)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S3b beat extraction")
    ap.add_argument("--run", required=True)
    run(ap.parse_args(argv).run)


if __name__ == "__main__":
    main()
