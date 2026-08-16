"""Gợi ý outline bằng LLM từ bằng chứng cluster (nút ✨ trên board).

Phân vai giữ đúng kiến trúc (Python đo — LLM sắp): Python chọn BỘ ỨNG VIÊN kèm số
liệu thật (coverage/peak/pos/questions) + top gaps, KHÔNG tính điểm tổng ẩn; LLM chỉ
CHỌN + XẾP THỨ TỰ thành Hook/Chapter/Ending theo cấu trúc YouTube, cân bằng xương sống
phổ biến (coverage/peak cao) với 1-2 câu hỏi chưa ai đáp (gaps) làm điểm khác biệt.

Ba lằn ranh (giữ luật A2/A3):
 - LLM chỉ được tham chiếu TÊN CLUSTER CÓ THẬT — parse_suggestion loại tên bịa
   (như Module 3b xác minh trích dẫn), không để LLM tạo chương không bằng chứng.
 - Gap (câu hỏi chưa đáp) → chương tự viết ✍ (không bằng chứng, đánh dấu rõ ở evidence).
 - Kết quả là GỢI Ý nạp vào panel sửa được, không tự lưu, không chấm điểm.

Logic nhận callback llm_call(system, user) -> str để test offline được.
"""
from __future__ import annotations

import json
import re
from typing import Callable

MAX_CLUSTERS = 24            # trần ứng viên đưa cho LLM (giữ prompt gọn + rẻ)
MAX_GAPS = 8


def build_candidates(clusters: list[dict], max_clusters: int = MAX_CLUSTERS) -> list[dict]:
    """Bộ ứng viên (không điểm tổng ẩn): gộp 3 nhóm rồi cắt trần, giữ tín hiệu thật.

    Xương sống = coverage≥2; giữ chân = top peak_score trong nhóm coverage==1; cầu có
    thật = cluster có questions_n>0. Đưa cả số liệu cho LLM tự cân, Python không xếp hạng.
    """
    backbone = [c for c in clusters if c.get("coverage_k", 0) >= 2]
    singles = sorted((c for c in clusters if c.get("coverage_k", 0) < 2),
                     key=lambda c: -c.get("peak_score", 0))
    with_q = [c for c in singles if c.get("questions_n", 0) > 0]
    # Lưới nhiễu (2026-08-16, sóng Vietnam nhiễm 12 cluster NHẬT từ 1 video lạc sóng —
    # title Vietnam, nội dung Nhật): single peak=0 & q=0 không mang tín hiệu nào, chỉ
    # được lấp khi sóng quá nghèo ứng viên (sóng không-heatmap vẫn chạy như cũ).
    co_tin_hieu = [c for c in singles if c.get("peak_score", 0) > 0]

    picked: dict[str, dict] = {}
    for group in (backbone, with_q, co_tin_hieu):    # xương sống → cầu → giữ chân có đo
        for c in group:
            if len(picked) >= max_clusters:
                break
            picked.setdefault(c["name"], c)
    if len(picked) < 4:                              # dưới mức tối thiểu hook+2ch+end → nới như cũ
        for c in singles:
            if len(picked) >= max_clusters:
                break
            picked.setdefault(c["name"], c)
    return list(picked.values())


def _cluster_line(c: dict) -> str:
    q = (c.get("questions") or [None])[0]
    bits = [f'"{c["name"]}"',
            f'role={c.get("role", "chapters")}',
            f'coverage={c.get("coverage_k", 0)}/{c.get("coverage_n", 0)}',
            f'peak={c.get("peak_score", 0)}',
            f'pos={c.get("pos")}',
            f'answers_questions={c.get("questions_n", 0)}']
    line = " · ".join(bits) + f'\n    brief: {c.get("brief", "").strip()}'
    if q:
        line += f'\n    sample viewer question it answers: {q}'
    return line


def build_suggest_prompt(title: str, candidates: list[dict],
                         gaps: list[dict], n_chapters: int = 7) -> tuple[str, str]:
    system = (
        "You are a YouTube documentary script strategist. You are given EVIDENCE mined "
        "by software from several videos on the same topic/trend: idea-clusters with "
        "real measured signals, plus audience questions that NO video answered.\n"
        "Build ONE outline that will perform on YouTube. Balance two forces:\n"
        "• POPULAR BACKBONE — lead with clusters that have high coverage (shared across "
        "the wave = proven framing) and high peak (Most-Replayed retention). These keep "
        "viewers watching.\n"
        "• DIFFERENTIATION — weave in 1-2 of the UNANSWERED gap questions so the video "
        "stands out from the rest of the wave. Do not overload on gaps (unproven).\n"
        "Structure = YouTube: a HOOK that opens a curiosity loop, ordered CHAPTERS that "
        "build a logical, unbroken narrative (use each cluster's pos 0→1 as an ordering "
        "hint), an ENDING that closes the loop. Prefer a role=hook cluster (or a gap) for "
        "the hook and a role=ending cluster for the ending.\n"
        "PROMISE ROLES (V3): state the title's promise in ONE sentence, then tag each "
        'chapter with "vai": EXACTLY ONE chapter is "tra_hua" (pays the FIRST real '
        "installment of the title promise — place it EARLY, viewers must feel the title "
        'was honest before they leave), AT MOST ONE is "payoff" (the full answer, '
        '~2/3 through the video — never the ending), the rest are "linh_hoat". '
        "If the user-set title promises something NO cluster can pay, set "
        '"khong_du_vat_lieu": true and say what is missing in "ly_do_thieu" — do NOT '
        "invent chapters to fake the promise.\n"
        "HARD RULE: for hook/ending/chapter clusters you may reference ONLY the exact "
        "cluster names given below — never invent a cluster. For a gap, output "
        '{"gap": "<the question text>"} instead of a cluster name.'
    )
    cand_block = "\n".join(f"- {_cluster_line(c)}" for c in candidates)
    gap_block = "\n".join(f'- "{g["text"]}" (♥{g.get("likes", 0)})'
                          for g in gaps[:MAX_GAPS]) or "(none)"
    user = (
        (f'VIDEO TITLE (user-set): "{title}"\n\n' if title.strip() else "")
        + f"EVIDENCE CLUSTERS (choose and order from these ONLY):\n{cand_block}\n\n"
        f"UNANSWERED AUDIENCE QUESTIONS (gaps — pick 1-2 to differentiate):\n{gap_block}\n\n"
        "Return ONLY a JSON object, no prose, of this exact shape:\n"
        "{\n"
        '  "title": "<a high-curiosity YouTube title; keep user title if given>",\n'
        '  "promise": "<ONE sentence — what the title promises the clicker>",\n'
        '  "hook": "<cluster name>"  (or {"gap": "<question>"}),\n'
        f'  "chapters": [ {{"name": "<cluster name>", "vai": "tra_hua"|"payoff"|"linh_hoat", '
        f'"vi_sao": "<=12 words"}} | {{"gap": "<question>", "vai": "linh_hoat"}}, ... ]  '
        f"(EXACTLY {n_chapters} items, ordered),\n"
        '  "ending": "<cluster name>",\n'
        '  "khong_du_vat_lieu": false,  "ly_do_thieu": ""\n'
        "}\n"
        f"Output EXACTLY {n_chapters} chapters — no more. Every cluster name MUST match "
        "one above verbatim."
    )
    return system, user


def _short(text: str, n: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def parse_suggestion(raw: str, clusters: list[dict]) -> dict:
    """Xác minh gợi ý LLM → picks {title, hook, ending, chapters, custom}.

    Loại mọi tên cluster không có thật; gap → chương tự viết ✍ (brief = câu hỏi).
    """
    text = raw.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM trả về JSON không hợp lệ: {text[:200]}") from e

    valid = {c["name"] for c in clusters}
    picks: dict = {"title": str(data.get("title") or "").strip(),
                   "hook": None, "ending": None, "chapters": [], "custom": {}, "extras": {},
                   # V3 (2026-08-16): lời hứa + vai chương — Python kiểm vị trí (ke_hoach)
                   "promise": str(data.get("promise") or "").strip(),
                   "vai": {}, "vi_sao": {},
                   "khong_du_vat_lieu": bool(data.get("khong_du_vat_lieu")),
                   "ly_do_thieu": str(data.get("ly_do_thieu") or "").strip()}
    used: set[str] = set()

    def as_cluster(v):
        if isinstance(v, str) and v in valid and v not in used:
            used.add(v)
            return v
        return None

    def as_gap(v):
        """{"gap": text} → tên chương ✍; brief là chỉ thị trả lời câu hỏi."""
        if isinstance(v, dict) and str(v.get("gap") or "").strip():
            txt = str(v["gap"]).strip()
            name = "✍ " + _short(txt)
            if name in used:
                return None
            used.add(name)
            picks["custom"][name] = f"Answer the viewers' unanswered question: {txt}"
            return name
        return None

    picks["hook"] = as_cluster(data.get("hook"))       # hook chỉ nhận cluster có thật
    picks["ending"] = as_cluster(data.get("ending"))
    da_co_vai: set[str] = set()                        # mỗi vai đặc biệt tối đa MỘT chương
    for item in (data.get("chapters") or []):
        # V3: item có thể là dict {"name"|"gap", "vai", "vi_sao"}; str = hợp đồng cũ.
        vai = vi_sao = ""
        if isinstance(item, dict) and "name" in item:
            vai = str(item.get("vai") or "").strip()
            vi_sao = str(item.get("vi_sao") or "").strip()
            item = item["name"]
        elif isinstance(item, dict) and "gap" in item:
            vai = str(item.get("vai") or "").strip()
        name = as_cluster(item) or as_gap(item)
        if not name:
            continue
        picks["chapters"].append(name)
        if vai in ("tra_hua", "payoff") and vai not in da_co_vai:
            picks["vai"][name] = vai
            da_co_vai.add(vai)
        if vi_sao:
            picks["vi_sao"][name] = vi_sao
    return picks


# Hằng số hệ nguyên liệu — nguồn Python ở ke_hoach.py, GƯƠNG của board.html
# (HOOK_FIXED/MAT_OK/endChars): đổi bên nào phải đổi bên kia.
from .ke_hoach import HOOK_CHARS as _HOOK_FIXED  # noqa: E402
from .ke_hoach import end_chars as _end_chars  # noqa: E402
from .ke_hoach import kiem_lich, sap_theo_vai  # noqa: E402

_MAT_OK = 8            # giãn <8× = đủ nguyên liệu (đo 8 run thật, xem CLAUDE.md)
_MAX_EXTRAS = 3        # trần ý con tự đắp/chương — quá 3 là chương thành danh sách


def _pos(c: dict) -> float:
    return c["pos"] if c.get("pos") is not None else 0.5


def _fill_thin(chosen: list[dict], clusters: list[dict], used: set[str],
               total_chars: int) -> dict:
    """Tự đắp Ý CON cho chương mỏng (2026-07-27, user hỏi '⚡ có tạo thêm ý bị thiếu
    không'): chương giãn ≥8× nhận thêm cụm CHƯA DÙNG gần pos nhất (cùng khúc kể
    chuyện) tới khi đủ hoặc hết trần. Chỉ số đo, không LLM; extras là cơ chế có sẵn
    (compose ghép brief ý con vào chương) — user gỡ từng ý trên panel như thường."""
    per = (total_chars - _HOOK_FIXED - _end_chars(total_chars)) / max(1, len(chosen))
    pool = [c for c in clusters if c["name"] not in used]
    extras: dict[str, list] = {}
    for ch in chosen:                       # chương mỏng nhất xử lý trước? theo thứ tự pos — đủ tốt
        mat = len(ch.get("brief") or "")
        while (pool and per / max(1, mat) >= _MAT_OK
               and len(extras.get(ch["name"], [])) < _MAX_EXTRAS):
            pool.sort(key=lambda c: (abs(_pos(c) - _pos(ch)),) + (c["name"],))
            e = pool.pop(0)
            extras.setdefault(ch["name"], []).append({"cluster": e["name"]})
            used.add(e["name"])
            mat += len(e.get("brief") or "")
    return extras


def py_split(clusters: list[dict], n_chapters: int = 7, total_chars: int = 0) -> dict:
    """Nút ⚡ Chia outline (PY) — tất định, 0 LLM (2026-07-27, user chê nút ✨
    'không hiệu quả': khâu chọn + xếp là thứ ĐO ĐƯỢC, không cần LLM phán).

    Luật chia, mọi tiêu chí là cột số đang hiện trên board (không điểm tổng ẩn):
    - hook / ending = cụm role tương ứng mạnh nhất (coverage giảm dần → peak_score);
    - N chương = cụm role=chapters mạnh nhất theo cùng thứ tự; THIẾU thì bổ sung cụm
      còn lại có câu hỏi khán giả (questions_n>0) trước, rồi tới mạnh nhất;
    - thứ tự chương = pos (vị trí trung vị trong video cùng sóng — trình tự kể chuyện
      của cả sóng); pos=None xếp giữa (0.5).
    Kết quả chỉ ĐIỀN SẴN panel như ✨ (A3 — user toàn quyền sửa), cùng shape picks.
    """
    if not clusters:
        raise ValueError("Chưa có cluster nào — chạy pipeline outline trước.")
    n_chapters = max(1, min(15, int(n_chapters)))

    def strength(c: dict):
        return (-c.get("coverage_k", 0), -c.get("peak_score", 0), c["name"])

    used: set[str] = set()

    def best(role: str) -> str | None:
        pool = sorted((c for c in clusters
                       if c.get("role") == role and c["name"] not in used), key=strength)
        if not pool:
            return None
        used.add(pool[0]["name"])
        return pool[0]["name"]

    hook, ending = best("hook"), best("ending")
    body = sorted((c for c in clusters
                   if c.get("role") == "chapters" and c["name"] not in used), key=strength)
    chosen = body[:n_chapters]
    used.update(c["name"] for c in chosen)
    if len(chosen) < n_chapters:
        rest = sorted((c for c in clusters if c["name"] not in used),
                      key=lambda c: (-(c.get("questions_n", 0) > 0),) + strength(c))
        chosen += rest[:n_chapters - len(chosen)]
    chosen.sort(key=lambda c: c.get("pos") if c.get("pos") is not None else 0.5)
    used.update(c["name"] for c in chosen)
    extras = _fill_thin(chosen, clusters, used, total_chars) if total_chars else {}
    return {"title": "", "hook": hook, "ending": ending,
            "chapters": [c["name"] for c in chosen], "custom": {}, "extras": extras}


def suggest_outline(clusters: list[dict], gaps: list[dict], title: str,
                    llm_call: Callable[[str, str], str], n_chapters: int = 7,
                    total_chars: int = 0, avd_phut: float | None = None) -> dict:
    if not clusters:
        raise ValueError("Chưa có cluster nào — chạy pipeline outline trước.")
    n_chapters = max(1, min(15, int(n_chapters)))
    cands = build_candidates(clusters)
    system, user = build_suggest_prompt(title, cands, gaps, n_chapters)
    picks = parse_suggestion(llm_call(system, user), clusters)
    # Cắt CỨNG nếu LLM vẫn trả dư (yêu cầu user: không chọn quá) + dọn gap-chương thừa.
    if len(picks["chapters"]) > n_chapters:
        picks["chapters"] = picks["chapters"][:n_chapters]
        kept = set(picks["chapters"]) | {picks.get("hook"), picks.get("ending")}
        picks["custom"] = {k: v for k, v in picks["custom"].items() if k in kept}
        picks["vai"] = {k: v for k, v in picks["vai"].items() if k in kept}
        picks["vi_sao"] = {k: v for k, v in picks["vi_sao"].items() if k in kept}
    # V3: Python xếp vị trí theo vai (tra_hua lên đầu, payoff về ~65%) + kiểm lịch.
    # LLM chỉ GẮN vai; vị trí là số học tất định (ke_hoach) — chỉ báo, không chặn.
    if total_chars and picks["vai"]:
        picks["chapters"] = sap_theo_vai(picks["chapters"], picks["vai"], total_chars)
        picks["canh_bao"] = kiem_lich(picks["chapters"], picks["vai"],
                                      total_chars, avd_phut)
    return picks
