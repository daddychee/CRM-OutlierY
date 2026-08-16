"""Gộp cluster theo yêu cầu (user chọn nhiều cluster → bấm Generate). LLM tổng hợp giữ sắc thái,
Python hợp nhất bằng chứng. KHÔNG tự động — chỉ chạy khi user chủ động gộp (giữ luật A3).

Server (`/api/merge`) gọi `merge_clusters` khi user bấm Generate trên board.
"""
from __future__ import annotations

from statistics import median

from .llm import LLM, extract_json

MERGE_SYSTEM = (
    "Bạn gộp NHIỀU mô tả (từ nhiều video) thành MỘT ý duy nhất. QUY TẮC QUAN TRỌNG: giữ MỌI "
    "sắc thái — nếu các video nhấn góc khác nhau, nêu ĐỦ các góc, KHÔNG lược bỏ; thà dài hơn là "
    "mất ý. Viết TIẾNG ANH. Chỉ trả JSON."
)


def merge_clusters(llm: LLM, members: list[dict]) -> dict:
    """Hợp nhất các cluster user chọn: LLM viết brief giữ sắc thái, Python union bằng chứng."""
    lines = "\n".join(f'- {m["name"]}: {m.get("brief", "")}' for m in members)
    prompt = (f'{len(members)} mô tả cần gộp thành một (giữ mọi góc):\n{lines}\n\n'
              'Trả JSON: {"name":"<tên gộp ngắn>","brief":"<2–5 câu tiếng Anh, giữ đủ các góc>"}')
    try:
        d = extract_json(llm.complete(MERGE_SYSTEM, prompt, max_tokens=1200, temperature=0.2))
        name = (d.get("name") or members[0]["name"]).strip()
        brief = (d.get("brief") or "").strip()
    except Exception:                                   # noqa: BLE001 — LLM lỗi → nối thô, không mất ý
        name = members[0]["name"]
        brief = " ".join(m.get("brief", "") for m in members)

    videos, gids, questions, sources = set(), [], [], []
    for m in members:
        videos.update(m.get("videos", []))
        gids += m.get("member_gids", [])
        questions += m.get("questions", [])
        # tên cụm GỐC (gộp cụm-đã-gộp → kế thừa nguồn của nó, không lấy tên trung gian)
        sources += m.get("merged_sources") or [m["name"]]
    uq = list(dict.fromkeys(questions))
    poss = [m["pos"] for m in members if m.get("pos") is not None]
    roles = [m.get("role", "chapters") for m in members]
    # angle giữ của cluster peak mạnh nhất (góc gốc tại điểm tua-lại nhiều nhất)
    angle = max(members, key=lambda m: m.get("peak_score", 0) or 0).get("angle", "")
    return {
        "name": name, "brief": brief, "angle": angle,
        "role": max(set(roles), key=roles.count) if roles else "chapters",
        "coverage_k": len(videos), "coverage_n": members[0].get("coverage_n", len(videos)),
        "peak_score": round(max((m.get("peak_score") or 0) for m in members), 2),
        "pos": round(median(poss), 3) if poss else None,
        "top_video": any(m.get("top_video") for m in members),
        "member_gids": gids, "videos": sorted(videos),
        "questions": uq[:3], "questions_n": sum(m.get("questions_n", 0) for m in members),
        "quoted_n": sum(m.get("quoted_n", 0) for m in members),
        # cộng dồn: gộp một cụm-gộp với cụm khác → đếm đúng tổng cụm gốc (gộp-chồng)
        "merged_from": sum(m.get("merged_from", 1) for m in members),
        # tên các cụm gốc — board hiện "Gộp từ: A · B · C" (2026-07-22); run cũ không có
        "merged_sources": list(dict.fromkeys(sources)),
    }
