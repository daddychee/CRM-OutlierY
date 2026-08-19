# -*- coding: utf-8 -*-
"""20_bao_cao_writer.py <project_dir> — TẦNG 2 báo cáo gộp: LLM viết tầng NGHĨA.

User chốt 19/08 "code luôn tầng 2": writer đọc DIGEST artifact (số đã tính sẵn —
không đọc transcript thô, DNA/gaps đã distill hộ) → viết các khối NGHĨA của báo
cáo 8 phase ra JSON THEO SCHEMA vào niche-data/bao_cao_nghia.json; builder
19_build_bao_cao.py đọc file này đổ vào slot (thiếu file → slot giữ nhãn chờ).

LUẬT NEO (van chống bịa tầng NGHĨA): mỗi luận điểm phải neo ít nhất MỘT con số /
chuỗi có thật trong digest (ghi trong ngoặc); cấm sinh số mới. Khóa LLM: KÉT qua
khoa_v3.env_llm (việc phan_tich); KÉT chưa cấp → thử nguồn .env V2 như pipeline
cũ, không có nốt thì lỗi rõ — tuyệt đối không chạy mù.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))            # llm_provider, _common
sys.path.insert(0, str(HERE.parent))     # khoa_v3

from llm_provider import LLMError, call_role, extract_json, validate_json  # noqa: E402

DATA_DIR = "niche-data"
TEN_FILE = "bao_cao_nghia.json"


def _doc(nd: Path, ten: str):
    p = nd / ten
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _digest(nd: Path) -> dict:
    """Bản chắt số cho prompt — chỉ nhặt trường cần, cắt top-n cho gọn token."""
    d1 = _doc(nd, "decision1.json") or {}
    d2 = _doc(nd, "decision2.json") or {}
    demand = _doc(nd, "demand.json") or {}
    crack = _doc(nd, "crackability.json") or {}
    money = _doc(nd, "monetization.json") or {}
    an = _doc(nd, "analysis.json") or {}
    gaps = _doc(nd, "gaps.json") or {}
    bets = (_doc(nd, "bets.json") or {}).get("bets") or []
    dna = _doc(nd, "dna.json")
    plan = _doc(nd, "execution_plan.json")

    def _cat(ds, n, truong):
        return [{t: m.get(t) for t in truong} for m in (ds or [])[:n]]

    return {
        "phan_quyet": {k: d1.get(k) for k in
                       ("decision", "attractiveness", "gate_reason", "pillars",
                        "competition_hhi", "n_channels")},
        "demand": {k: demand.get(k) for k in
                   ("n_matured", "demand_median_views", "reach_p90_views",
                    "supply_per_month", "trend", "trend_strength")},
        "cua_vao": {k: crack.get(k) for k in
                    ("newcomer_rate", "young_months", "authority_dependence",
                     "pattern_replicability", "verdict", "reason")},
        "kiem_tien": {k: money.get(k) for k in
                      ("rpm_band_usd", "category", "sponsor_density", "verdict", "note")},
        "beachhead": {"chon": d2.get("decision"), "ly_do": d2.get("reason"),
                      "cum": _cat(d2.get("ranked"), 8,
                                  ("anchor", "beachhead_score", "competition",
                                   "size", "n_channels", "top_titles"))},
        "bets": _cat(bets, 8, ("term", "kind", "builder_verdict", "lift",
                               "n_channels", "n_outliers", "gap_match")),
        "khuon_thang": {
            "openers": _cat(an.get("openers"), 10, ("key", "freq", "channels")),
            "templates": _cat(an.get("templates"), 8, ("key", "freq")),
            "emphasis": _cat(an.get("emphasis"), 10, ("key", "freq")),
            "lift_sig": [m["key"] for m in
                         (an.get("lift_tags") or []) + (an.get("lift_bigrams") or [])
                         if m.get("sig")][:15],
        },
        "khan_gia": {
            "themes": _cat(gaps.get("themes"), 12, ("theme", "count", "pct")),
            "cau_hoi_top": _cat(gaps.get("top_questions"), 15, ("q", "like")),
            "tong_comment": gaps.get("total_comments"),
            "tong_cau_hoi": gaps.get("total_questions"),
        },
        "dna": dna,                      # agent pipeline distill từ transcripts
        "execution_plan": plan,          # agent plan của pipeline
    }


SYSTEM = """Bạn là nhà chiến lược nội dung YouTube viết TẦNG NGHĨA cho báo cáo
nghiên cứu ngách 8 phase (phương pháp Niche Research & Content GTM của OUTLIERY).
Đầu vào là DIGEST số liệu pipeline đã tính sẵn (JSON). Viết TIẾNG VIỆT, giọng nhà
phân tích nói thẳng, ngắn gọn giàu thông tin.

LUẬT SẮT:
1. CHỈ dựa trên digest. Mỗi luận điểm phải NEO ít nhất một con số hoặc chuỗi có
   thật trong digest, ghi trong ngoặc tròn — ví dụ: (newcomer_rate 33%), (theme
   "surprised most" 20 câu). CẤM sinh con số mới không có trong digest.
2. Điều gì digest không đủ căn cứ → ghi 'GIẢ ĐỊNH:' trước câu đó (đừng bỏ trống).
3. Trả về DUY NHẤT một JSON hợp lệ đúng schema — không markdown, không lời dẫn.

SCHEMA:
{
 "tq": {"headline": "1 câu tít nói bản chất ngách", "doan": "3-5 câu tổng quan"},
 "canvas": {"cot": ["① <nhóm chính> (chính)", "② <nhóm phụ> (phụ, giá trị cao)", "③ <nhóm 3> (cộng đồng)"],
   "hang": [
     {"ten": "Là ai", "o": ["...", "...", "..."]},
     {"ten": "Jobs-to-be-Done", "o": ["...", "...", "..."]},
     {"ten": "Pain hiện tại", "o": ["...", "...", "..."]},
     {"ten": "Desired outcome", "o": ["...", "...", "..."]},
     {"ten": "Đang xem thay thế", "o": ["...", "...", "..."]},
     {"ten": "Ngôn ngữ họ dùng", "o": ["...", "...", "..."]}]},
 "phuong_an": [
   {"ten": "Phương án A — \\"<tên>\\" · Khuyến nghị", "noi_dung": ["Statement: Đối với <khán giả>, kênh <định vị> — khác biệt vì <lý do neo số>.", "Vì sao thắng: ...", "Rủi ro: ..."]},
   {"ten": "Phương án B — \\"<tên>\\"", "noi_dung": ["Statement: ...", "Vì sao đáng cân nhắc: ...", "Rủi ro: ..."]},
   {"ten": "Phương án C — \\"<tên>\\"", "noi_dung": ["Statement: ...", "Vì sao đáng cân nhắc: ...", "Rủi ro: ..."]}],
 "anti": ["✗ Không <điều cấm> — <lý do neo số>", "... 4-6 mục"],
 "winning_format": ["<kết luận khuôn thắng có neo số>", "... 5-8 mục"],
 "tong_hop": {"doan": "5-8 câu GO/NO-GO liền mạch: vào hay không, bằng mũi nhọn nào, điều kiện gì",
              "rut_lui": ["Nếu <falsifier đo được> sau <mốc> → rút", "... 3-5 mục"]}
}"""


def main() -> int:
    if len(sys.argv) < 2:
        print("Cach dung: 20_bao_cao_writer.py <project_dir>")
        return 2
    project_dir = Path(sys.argv[1])
    nd = project_dir / DATA_DIR
    if not nd.is_dir():
        print(f"KHONG THAY {nd} — chua chay pipeline?")
        return 2

    # Khóa LLM: KÉT trước (việc phan_tich); chưa cấp → nguồn .env V2 như pipeline cũ.
    try:
        import khoa_v3
        os.environ.update(khoa_v3.env_llm())
        print("khoa LLM: KET (phan_tich)")
    except Exception as e:
        print(f"KET chua cap khoa LLM ({e}) — thu nguon .env V2 cua pipeline")

    digest = _digest(nd)
    user = ("DIGEST:\n" + json.dumps(digest, ensure_ascii=False, indent=1)
            + "\n\nViết tầng NGHĨA theo schema — JSON duy nhất.")
    try:
        # 8192: đo thật 19/08 — 4096 bị cụt JSON giữa chừng (canvas tiếng Việt dài)
        text, provider = call_role("bao_cao_writer", SYSTEM, user,
                                   work=str(nd), max_tokens=8192)
        obj = extract_json(text)
        validate_json(obj, ["canvas", "phuong_an", "tong_hop"], label="bao_cao_nghia")
    except LLMError as e:
        print(f"LOI LLM: {e}")
        return 3
    if len((obj.get("canvas") or {}).get("hang") or []) < 4 or len(obj.get("phuong_an") or []) < 2:
        print("LOI: JSON thieu canvas/phuong_an toi thieu — khong ghi file")
        return 3

    obj["_meta"] = {"version": 1, "generated": datetime.now().isoformat(timespec="seconds"),
                    "provider": provider,
                    "model": os.environ.get("GLM_MODEL") or os.environ.get("ANTHROPIC_MODEL")
                             or os.environ.get("OPENAI_MODEL") or ""}
    dich = nd / TEN_FILE
    tam = nd / (TEN_FILE + ".tmp")
    tam.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tam.replace(dich)
    print(f"DONE — {dich} (provider={provider})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
