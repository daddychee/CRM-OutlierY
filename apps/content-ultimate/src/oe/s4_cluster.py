"""S4 — Gom cụm beat cross-video + tính các cột bằng chứng. Ghi clusters.json.

Chạy:  python3 -m oe.s4_cluster --run <tên> [--threshold 0.82]

Embedding local gom cụm (LLM chỉ đặt tên/brief); Python tính MỌI con số từ thành viên cụm:
coverage k/N · peak_score (z×w) · pos (median vị trí tương đối) · top-video.
"""
from __future__ import annotations

import argparse
from collections import Counter
from statistics import median

from . import common
from .cluster import EmbeddingClusterer, SIM_THRESHOLD
from .llm import LLM


def _beat_role(beat_type: str) -> str:
    """Beat type (S3b) → section của outline. hook→hook; payoff/CTA→ending; còn lại→chapters."""
    t = (beat_type or "").lower()
    if "hook" in t:
        return "hook"
    if "cta" in t or "payoff" in t or "outro" in t or "ending" in t or "kết" in t:
        return "ending"
    return "chapters"


def _collect_beats(beats_by_vid: dict) -> tuple[list[dict], dict]:
    """Phẳng hoá beat, gắn gid = '<vid>#<i>'. Trả (danh sách gid+summary+type, map gid→beat)."""
    refs, index = [], {}
    for vid, beats in beats_by_vid.items():
        for i, b in enumerate(beats):
            if not b.get("summary"):
                continue
            gid = f"{vid}#{i}"
            refs.append({"gid": gid, "type": b.get("type", ""), "summary": b["summary"]})
            index[gid] = dict(b, video_id=vid)
    return refs, index


def _score(cluster: dict, index: dict, videos: dict, top_vid: str) -> dict:
    members = [index[g] for g in cluster["members"]]
    vids = {m["video_id"] for m in members}
    n = len(videos)

    peak = 0.0
    for m in members:
        w = videos[m["video_id"]].get("source_weight", 1.0)
        peak = max(peak, m.get("peak_z_w", 0.0) * w)

    # ANGLE GỐC = summary của beat có peak value mạnh nhất (câu khiến khán giả tua lại). Giữ
    # góc nhìn/lập luận cụ thể của nguồn để outline không mất, brief tổng hợp có thể làm mượt.
    peak_beat = max(members, key=lambda m: m.get("peak_z_w", 0.0))
    angle = peak_beat.get("summary", "") if peak_beat.get("peak_z_w", 0.0) > 0 else ""

    positions = []
    for m in members:
        dur = videos[m["video_id"]].get("duration") or 0
        if dur:
            positions.append(m.get("t_start", 0.0) / dur)
    pos = round(median(positions), 3) if positions else None

    # role = section theo loại beat (đa số quyết) + chốt vị trí: hook phải ở đầu, ending ở nửa
    # sau — payoff/CTA giữa video (vd đoạn sponsor) là cao trào chương, không phải kết bài.
    # CHỐT VỊ TRÍ CHỈ ÁP DỤNG KHI BIẾT pos; pos=None (video thiếu duration) → tin beat type,
    # KHÔNG demote (nếu không mọi cụm dồn về chapters, không có vùng hook/ending — bug 2026-07-14).
    votes = Counter(_beat_role(m.get("type")) for m in members)
    role = max(("chapters", "hook", "ending"), key=lambda r: (votes.get(r, 0), r == "chapters"))
    if role == "hook" and pos is not None and pos > 0.30:
        role = "chapters"
    elif role == "ending" and pos is not None and pos < 0.55:
        role = "chapters"

    return {
        "name": cluster["name"],
        "brief": cluster["brief"],
        "angle": angle,
        "role": role,
        "coverage_k": len(vids),
        "coverage_n": n,
        "peak_score": round(peak, 2),
        "pos": pos,
        "top_video": top_vid in vids,
        "member_gids": cluster["members"],
        "videos": sorted(vids),
    }


def run(run_name: str, threshold: float) -> None:
    rd = common.run_dir(run_name)
    videos = common.read_json(rd / "videos.json")
    beats_by_vid = common.read_json(rd / "beats.json")

    refs, index = _collect_beats(beats_by_vid)
    print(f"Gom {len(refs)} beat từ {len(beats_by_vid)} video (ngưỡng cosine {threshold})…", flush=True)

    top_vid = max(videos, key=lambda v: videos[v].get("source_weight", 0))
    clusterer = EmbeddingClusterer(LLM(common.ROOT / ".env"), threshold=threshold)
    raw_clusters = clusterer.cluster(refs)

    scored = [_score(c, index, videos, top_vid) for c in raw_clusters]
    scored.sort(key=lambda c: (-c["coverage_k"], -c["peak_score"]))   # sort mặc định chỉ để đọc log
    common.write_json(rd / "clusters.json", scored)

    multi = [c for c in scored if c["coverage_k"] >= 2]
    print(f"\n{len(scored)} cụm ({len(multi)} cụm ≥2 video = khung sóng). Top theo coverage:")
    for c in scored[:12]:
        star = "★" if c["top_video"] else " "
        print(f"  {star} {c['coverage_k']}/{c['coverage_n']}  peak={c['peak_score']:4.1f}  "
              f"pos={c['pos'] if c['pos'] is not None else '--'}  {c['name'][:52]}", flush=True)
    print(f"\nS4 xong → {rd/'clusters.json'}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S4 cluster + score")
    ap.add_argument("--run", required=True)
    ap.add_argument("--threshold", type=float, default=SIM_THRESHOLD)
    a = ap.parse_args(argv)
    run(a.run, a.threshold)


if __name__ == "__main__":
    main()
