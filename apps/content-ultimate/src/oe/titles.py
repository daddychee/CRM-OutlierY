"""Sinh + chấm TITLE từ bằng chứng sóng (V3, 2026-08-16) — nút "Sinh title" trên board.

Board hiển thị 3 nguồn title (user quyết, máy không tự chọn):
  1. Title GỐC của sóng — videos.json có sẵn (title + view), 0 LLM;
  2. 5 title máy sinh từ bằng chứng (cluster/M/gaps), MỖI title kèm điểm vật liệu;
  3. Ô điền tay — title gõ tay chấm qua CÙNG máy chấm (cham_title_tay).

VAN CHỐNG BỊA 3 TẦNG (khuôn "Python đo — LLM sắp" + van verbatim của Q-verify):
  1. LLM chỉ TÁCH Ý lời hứa + TRỎ (tên cluster, trích nguyên văn) — KHÔNG phát ra số;
  2. Python xác minh tên cluster CÓ THẬT + trích VERBATIM trong brief/angle
     (KHÔNG tính tên cluster vào kho xác minh — chặn đường lười trích ngay tên);
  3. Điểm = số học thuần từ tín hiệu đo được (coverage/peak/questions) — chạy lại
     ra đúng số đó, không phải "cảm tính LLM".
"""
from __future__ import annotations

import re
from typing import Callable

from .llm import extract_json
from .suggest import MAX_GAPS, _cluster_line, build_candidates

NGUONG_THIEU = 40      # điểm vật liệu <40% → cờ "thiếu vật liệu" (chỉ báo, không chặn)
_MAX_TITLES = 7


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


def suc_manh(c: dict) -> float:
    """Trọng số vật liệu từ tín hiệu ĐO ĐƯỢC của cluster (không điểm ẩn):
    xương sống ≥2 video = 1.0 · đơn lẻ có peak/câu hỏi = 0.7 · đơn lẻ trơ = 0.4."""
    if c.get("coverage_k", 0) >= 2:
        return 1.0
    if c.get("peak_score", 0) > 0 or c.get("questions_n", 0) > 0:
        return 0.7
    return 0.4


def _kho_xac_minh(c: dict) -> str:
    # CHỈ brief + angle — không lấy tên cluster (LLM lười sẽ trích ngay tên để luôn đậu)
    return _norm((c.get("brief") or "") + " " + (c.get("angle") or ""))


def cham_y(y_loi_hua: list[dict], clusters: list[dict]) -> tuple[int, list[dict]]:
    """Chấm danh sách ý lời hứa đã map → (điểm %, chi tiết từng ý). Python thuần."""
    cm = {c["name"]: c for c in clusters}
    chi_tiet, tong = [], 0.0
    for y in y_loi_hua:
        muc = {"y": str(y.get("y") or "").strip(), "cluster": y.get("cluster"),
               "diem": 0.0, "note": ""}
        c = cm.get(str(y.get("cluster") or ""))
        trich = str(y.get("trich") or "").strip()
        if not muc["y"]:
            continue
        if c is None or not trich:
            muc["cluster"] = None
            muc["note"] = "sóng KHÔNG có vật liệu"
        elif _norm(trich) not in _kho_xac_minh(c):
            muc["diem"] = 0.0
            muc["note"] = "trích không có trong brief (bịa/paraphrase) — loại"
        else:
            muc["diem"] = suc_manh(c)
            muc["note"] = (f"cov {c.get('coverage_k', 0)}/{c.get('coverage_n', 0)}"
                           + (f" · peak {c.get('peak_score', 0):.1f}"
                              if c.get("peak_score") else ""))
            tong += muc["diem"]
        chi_tiet.append(muc)
    if not chi_tiet:
        return 0, []
    return round(tong / len(chi_tiet) * 100), chi_tiet


_HOP_DONG_Y = (
    'Each item of "y_loi_hua" (the promise, split into 2-4 checkable components):\n'
    '  {"y": "<component of the promise>",\n'
    '   "cluster": "<EXACT cluster name from the list that can PAY this component, '
    "or null if none>\",\n"
    '   "trich": "<a VERBATIM contiguous fragment (<=15 words) COPIED from that '
    "cluster's brief/angle text proving it, or null>\"}\n"
    "HARD RULES: cluster names verbatim from the list only — never invent; the "
    '"trich" must be copy-paste from the brief text (it will be machine-verified: '
    "a paraphrase counts as fabrication and the component scores 0)."
)


def build_titles_prompt(candidates: list[dict], gaps: list[dict],
                        titles_goc: list[dict], n: int = 5) -> tuple[str, str]:
    system = (
        "You are a YouTube packaging strategist. You get EVIDENCE mined from a wave "
        "of successful videos: idea-clusters with real measured signals, the wave's "
        "ORIGINAL titles (with view counts), and unanswered audience questions.\n"
        f"Propose {n} ENGLISH video titles for a NEW video built from this material. "
        "Mix two families: (a) light variations riffing on the original titles "
        "(cross-feed effect when published next to them), (b) fresh curiosity-driven "
        "angles — a specific belief to break or a secret to reveal beats a generic "
        "listicle promise. Every title must be a promise this wave's clusters can "
        "actually PAY.\n" + _HOP_DONG_Y
    )
    goc = "\n".join(f'- "{t["title"]}" ({t.get("views", 0):,} views)'
                    for t in titles_goc) or "(none)"
    cand = "\n".join(f"- {_cluster_line(c)}" for c in candidates)
    gap = "\n".join(f'- "{g["text"]}" (♥{g.get("likes", 0)})'
                    for g in gaps[:MAX_GAPS]) or "(none)"
    user = (
        f"ORIGINAL TITLES OF THE WAVE:\n{goc}\n\n"
        f"EVIDENCE CLUSTERS (the ONLY allowed cluster names):\n{cand}\n\n"
        f"UNANSWERED AUDIENCE QUESTIONS:\n{gap}\n\n"
        "Return ONLY a JSON array, no prose:\n"
        '[{"title": "<the title>", "promise": "<ONE sentence — what this title '
        'promises the clicker>", "y_loi_hua": [ ... ]}, ...]\n'
        f"EXACTLY {n} items."
    )
    return system, user


def _parse_mot(item: dict, clusters: list[dict]) -> dict | None:
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    diem, chi_tiet = cham_y(list(item.get("y_loi_hua") or []), clusters)
    return {"title": title, "promise": str(item.get("promise") or "").strip(),
            "diem": diem, "thieu": diem < NGUONG_THIEU, "y": chi_tiet}


def parse_titles(raw: str, clusters: list[dict]) -> list[dict]:
    data = extract_json(raw)
    if isinstance(data, dict):                          # model bọc {"titles": [...]}
        data = data.get("titles") or []
    if not isinstance(data, list):
        raise ValueError("LLM không trả JSON array title")
    out = [t for t in (_parse_mot(x, clusters) for x in data if isinstance(x, dict)) if t]
    if not out:
        raise ValueError("LLM không trả được title hợp lệ nào")
    return out[:_MAX_TITLES]


def sinh_titles(clusters: list[dict], gaps: list[dict], videos: dict,
                llm_call: Callable[[str, str], str], n: int = 5) -> list[dict]:
    titles_goc = titles_goc_cua_song(videos)
    system, user = build_titles_prompt(build_candidates(clusters), gaps, titles_goc, n)
    return parse_titles(llm_call(system, user), clusters)


def titles_goc_cua_song(videos: dict) -> list[dict]:
    """Title gốc + view thật của các video nguồn, view cao trước — board hiện, 0 LLM."""
    out = [{"video_id": vid, "title": (v.get("title") or "").strip(),
            "views": v.get("view_count") or 0}
           for vid, v in (videos or {}).items() if (v.get("title") or "").strip()]
    return sorted(out, key=lambda t: -t["views"])


def build_cham_prompt(title: str, candidates: list[dict]) -> tuple[str, str]:
    system = (
        "You are auditing whether a YouTube title's promise can be PAID by the "
        "evidence clusters of a video wave.\n" + _HOP_DONG_Y
    )
    cand = "\n".join(f"- {_cluster_line(c)}" for c in candidates)
    user = (
        f'TITLE TO AUDIT: "{title}"\n\n'
        f"EVIDENCE CLUSTERS (the ONLY allowed cluster names):\n{cand}\n\n"
        "Return ONLY a JSON object, no prose:\n"
        '{"promise": "<ONE sentence — what this title promises the clicker>",\n'
        ' "y_loi_hua": [ ... ]}'
    )
    return system, user


def cham_title_tay(title: str, clusters: list[dict],
                   llm_call: Callable[[str, str], str]) -> dict:
    """Chấm title người dùng gõ tay — đi qua ĐÚNG máy chấm của title máy sinh."""
    system, user = build_cham_prompt(title, build_candidates(clusters))
    data = extract_json(llm_call(system, user))
    if not isinstance(data, dict):
        raise ValueError("LLM không trả JSON object")
    out = _parse_mot({"title": title, **data}, clusters)
    if out is None:
        raise ValueError("không chấm được title")
    return out
