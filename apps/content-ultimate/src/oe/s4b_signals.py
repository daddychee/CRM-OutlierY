"""S4b — Tín hiệu comment cho mỗi cluster + bảng GAPS/NEXT IDEAS. Ghi bổ sung clusters.json.

Chạy:  .venv/bin/python -m oe.s4b_signals --run <tên> [--match 0.45]

Với mỗi cluster đã có (S4): đếm câu hỏi & trích-thoại khớp cluster (embed-match), giữ 3 câu
tiêu biểu. Câu hỏi không khớp cluster nào → GAPS (nhu cầu bỏ ngỏ). Comment xin nội dung → NEXT
IDEAS. Con số là ước lượng dưới (chỉ match chắc) — A2. Cần fastembed (venv).
"""
from __future__ import annotations

import argparse

from . import common
from . import comment_signals as cs
from .cluster import _unit, _cos


def _embed(texts: list[str], model: str):
    from fastembed import TextEmbedding
    emb = TextEmbedding(model_name=model)
    return [_unit(v.tolist()) for v in emb.embed(texts)]


def run(run_name: str, match_thr: float) -> None:
    from .cluster import EMBED_MODEL
    rd = common.run_dir(run_name)
    clusters = common.read_json(rd / "clusters.json")
    cdir = rd / "comments"
    if not cdir.exists():
        raise SystemExit("Chưa có comments/ — chạy S1c trước.")

    # gom & phân loại comment toàn sóng; quote cần shingle transcript từng video
    questions, quotes, requests = [], [], []
    for vid_file in sorted(cdir.glob("*.json")):
        if vid_file.name == "index.json":
            continue
        vid = vid_file.stem
        tf = rd / "transcripts" / f"{vid}.json"
        shingles = cs.build_transcript_shingles(
            [s["text"] for s in common.read_json(tf)]) if tf.exists() else set()
        for c in common.read_json(vid_file):
            t = c["text"]
            if cs.is_request(t):
                requests.append(c)
            elif cs.is_question(t):
                questions.append(c)
            elif shingles and cs.is_quote(t, shingles):
                quotes.append(c)

    # embed brief cluster + câu hỏi + quote, match về cluster gần nhất
    cvecs = _embed([c["name"] + ". " + c.get("brief", "") for c in clusters], EMBED_MODEL)
    for c in clusters:
        c["questions"] = []
        c["quoted_n"] = 0

    gaps = []
    if questions:
        qvecs = _embed([q["text"] for q in questions], EMBED_MODEL)
        for q, qv in zip(questions, qvecs):
            j, best = _argmax_cluster(qv, cvecs)
            if best >= match_thr:
                clusters[j]["questions"].append({"text": q["text"], "likes": q["likes"]})
            else:
                gaps.append(q)
    if quotes:
        for qv in _embed([q["text"] for q in quotes], EMBED_MODEL):
            j, best = _argmax_cluster(qv, cvecs)
            if best >= match_thr:
                clusters[j]["quoted_n"] += 1

    # giữ 3 câu hỏi tiêu biểu (nhiều like nhất) + đếm
    for c in clusters:
        qs = sorted(c["questions"], key=lambda x: -x["likes"])
        c["questions_n"] = len(qs)
        c["questions"] = [q["text"] for q in qs[:3]]

    gaps_out = [{"text": g["text"], "likes": g["likes"]}
                for g in sorted(gaps, key=lambda x: -x["likes"])[:40]]
    next_out = [{"text": r["text"], "likes": r["likes"]}
                for r in sorted(requests, key=lambda x: -x["likes"])[:30]]

    common.write_json(rd / "clusters.json", clusters)
    common.write_json(rd / "gaps.json", gaps_out)
    common.write_json(rd / "next_ideas.json", next_out)

    print(f"Comment: {len(questions)} hỏi · {len(quotes)} trích · {len(requests)} xin nội dung")
    print(f"  → khớp cluster: {sum(c['questions_n'] for c in clusters)} hỏi, "
          f"{sum(c['quoted_n'] for c in clusters)} trích")
    print(f"  → GAPS (hỏi không khớp cluster): {len(gaps_out)} · NEXT IDEAS: {len(next_out)}")
    top = max(clusters, key=lambda c: c["questions_n"])
    if top["questions_n"]:
        print(f"  cluster nhiều câu hỏi nhất: {top['name'][:40]!r} ({top['questions_n']})")
    print(f"\nS4b xong → clusters.json + gaps.json + next_ideas.json")


def _argmax_cluster(v, cvecs):
    best_j, best = 0, -1.0
    for j, cv in enumerate(cvecs):
        s = _cos(v, cv)
        if s > best:
            best_j, best = j, s
    return best_j, best


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S4b comment signals")
    ap.add_argument("--run", required=True)
    ap.add_argument("--match", type=float, default=0.45)
    a = ap.parse_args(argv)
    run(a.run, a.match)


if __name__ == "__main__":
    main()
