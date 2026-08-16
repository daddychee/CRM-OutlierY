"""Gom cụm beat cross-video. Interface tách riêng để SWAP cách đo tương đồng.

Hai cách hiện có (cùng trả [{name, brief, members:[gid]}]):
- `EmbeddingClusterer` (MẶC ĐỊNH, user chọn 2026-07-04): embedding local multilingual-e5 qua
  fastembed (ONNX, offline, không torch) → cosine + ngưỡng + connected components. TÁI LẬP
  được (đúng A1) + offline (đúng nguyên tắc GUI). LLM chỉ đặt tên + viết brief cho cụm đã gom.
- `GLMClusterer` (dự phòng): GLM chat tự gom. Chạy được khi không cài được fastembed, nhưng
  kém tái lập. Key GLM không có embedding endpoint (đo 2026-07-04: z.ai/bigmodel đều từ chối).

Nguyên tắc A1 giữ nguyên: MỌI con số (coverage, peak, pos) do Python tính ở S4 từ thành viên cụm.
"""
from __future__ import annotations

import math

from .llm import LLM, extract_json

SIM_THRESHOLD = 0.75          # cosine tối thiểu để 2 beat coi là cùng ý (hiệu chỉnh trên
                              # sóng bigbang: 0.75 cho 5 cụm cross-video, cụm lớn trải 4 video;
                              # ≤0.70 single-linkage xâu chuỗi thành 1 khối vô nghĩa)
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384d, 0.22GB, đa ngữ

SYSTEM = (
    "Bạn gom các BEAT (đơn vị nội dung) từ NHIỀU video cùng chủ đề thành các CỤM Ý. Hai beat "
    "vào cùng cụm khi chúng nói CÙNG MỘT Ý (dù khác chữ, khác video). Beat ý riêng lẻ đứng "
    "thành cụm một mình. Mỗi beat chỉ thuộc ĐÚNG MỘT cụm. Chỉ trả JSON."
)


def _prompt(beats: list[dict]) -> str:
    lines = "\n".join(f'{b["gid"]} [{b["type"]}] {b["summary"]}' for b in beats)
    return (
        f"Có {len(beats)} beat, mỗi dòng: <mã beat> [vai trò] tóm tắt.\n"
        "Gom thành các cụm ý. Trả JSON: "
        '[{"name":"<tên cụm ngắn, thành tiêu đề chương>",'
        '"brief":"<2–4 câu chỉ dẫn nội dung: cụm này cần kể gì; giọng \'Introduce/Explain/Reveal\'; '
        'chỉ dựa trên các beat trong cụm, không thêm ý ngoài>",'
        '"members":["<mã beat>", ...]}].\n'
        "Ngôn ngữ name/brief = ngôn ngữ của beat.\n\n" + lines
    )


class GLMClusterer:
    def __init__(self, llm: LLM):
        self.llm = llm

    def cluster(self, beats: list[dict]) -> list[dict]:
        """beats: [{gid, type, summary}] → clusters: [{name, brief, members:[gid]}]."""
        raw = self.llm.complete(SYSTEM, _prompt(beats), max_tokens=8000, temperature=0.1)
        clusters = extract_json(raw)
        valid_gids = {b["gid"] for b in beats}
        out = []
        for c in clusters:
            members = [g for g in c.get("members", []) if g in valid_gids]
            if members:
                out.append({
                    "name": (c.get("name") or "").strip(),
                    "brief": (c.get("brief") or "").strip(),
                    "members": members,
                })
        _attach_orphans(out, valid_gids, beats)
        return out


def _attach_orphans(clusters: list[dict], valid: set, beats: list[dict]) -> None:
    """Beat không được gom vào cụm nào → mỗi cái thành cụm một mình (không mất beat)."""
    seen = {g for c in clusters for g in c["members"]}
    by_gid = {b["gid"]: b for b in beats}
    for g in valid - seen:
        b = by_gid[g]
        clusters.append({"name": b["summary"][:60], "brief": b["summary"], "members": [g]})


# ── Embedding clusterer (mặc định) ──────────────────────────────────────────

NAME_SYSTEM = (
    "Bạn đặt tên và viết brief cho một CỤM Ý gồm các beat cùng nói một ý (từ nhiều video). "
    "Chỉ dựa trên các beat đã cho, không thêm ý ngoài. Chỉ trả JSON."
)


class EmbeddingClusterer:
    """Gom bằng embedding local; LLM chỉ đặt tên + brief cho cụm đã gom (pattern S9/S9b)."""

    def __init__(self, llm: LLM, *, threshold: float = SIM_THRESHOLD, model: str = EMBED_MODEL):
        self.llm = llm
        self.threshold = threshold
        self._model_name = model
        self._embedder = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embedder is None:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=self._model_name)
        vecs = list(self._embedder.embed(texts))
        return [_unit(v.tolist()) for v in vecs]

    def cluster(self, beats: list[dict]) -> list[dict]:
        vecs = self._embed([b["summary"] for b in beats])
        groups = _connected_components(vecs, self.threshold)
        clusters = []
        for grp in groups:
            members = [beats[i] for i in grp]
            name, brief = self._name(members)
            clusters.append({"name": name, "brief": brief, "members": [b["gid"] for b in members]})
        return clusters

    def _name(self, members: list[dict]) -> tuple[str, str]:
        if len(members) == 1:
            return members[0]["summary"][:60], members[0]["summary"]
        lines = "\n".join(f'- [{b["type"]}] {b["summary"]}' for b in members)
        prompt = (
            f"{len(members)} beat cùng một ý:\n{lines}\n\n"
            'Trả JSON: {"name":"<short cluster name, becomes a chapter title>",'
            '"brief":"<2-4 sentences of content direction, Introduce/Explain/Reveal voice, '
            'only from the beats above>"}. Write name AND brief in ENGLISH (outline luôn tiếng Anh).'
        )
        try:
            d = extract_json(self.llm.complete(NAME_SYSTEM, prompt, max_tokens=800, temperature=0.2))
            return (d.get("name") or members[0]["summary"][:60]).strip(), (d.get("brief") or "").strip()
        except Exception:                              # noqa: BLE001 — LLM lỗi thì tên tạm từ beat
            return members[0]["summary"][:60], " ".join(b["summary"] for b in members[:3])


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))            # đã unit-norm → dot = cosine


def _connected_components(vecs: list[list[float]], thr: float) -> list[list[int]]:
    """Nối 2 beat khi cosine ≥ ngưỡng, gom thành thành phần liên thông (union-find)."""
    n = len(vecs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if _cos(vecs[i], vecs[j]) >= thr:
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())
