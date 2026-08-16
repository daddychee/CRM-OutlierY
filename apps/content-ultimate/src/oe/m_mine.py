"""Đào M (misconception) cho công thức V2: V = (M + (Q→E)) × (A + B).

Python đo thuần (luật A1, không tốn LLM): quét beat + comment + gaps của run tìm
ngôn ngữ đính-chính/niềm-tin-sai, in bảng ứng viên M để NGƯỜI LẮP OUTLINE chọn
(luật A3 — tool trình bằng chứng, user pick).

Bài học 2026-07-26 (thí nghiệm Jupiter): bộ pattern hẹp bắt 0/81 beat — pattern
PHẢI là config nới được, không phải regex chôn trong logic. Sửa/thêm pattern ở
PURE_PATTERNS/SOFT_PATTERNS dưới đây, hoặc tại chỗ bằng --pattern.
Bài học Moscow: sóng không có beat đính-chính thuần → M MỀM từ beat twist
("Despite…") + cộng hưởng comment ("I guess the press was misleading us") vẫn đủ
làm M cho hook — vì vậy bảng luôn in cả ba nguồn.

Chạy:  .venv/bin/python -m oe.m_mine <run> [--top 12] [--pattern REGEX]
"""
from __future__ import annotations

import argparse
import json
import re

from .common import run_dir, read_json

# Ngôn ngữ ĐÍNH CHÍNH thẳng — M thuần (tên, regex). Case-insensitive.
PURE_PATTERNS: list[tuple[str, str]] = [
    ("not-X-but-Y", r"\bnot\b[^.!?]{0,60}\b(?:but|it'?s|it is)\b"),
    ("actually/in-truth", r"\b(?:actually|in (?:truth|fact|reality)|the truth is|turns? out)\b"),
    ("myth/taught", r"\b(?:myth|misconceptions?|everyone (?:thinks|believes|was taught)"
                    r"|commonly (?:believed|thought)|we were (?:taught|told)"
                    r"|you(?:'ve| have)? been (?:taught|told|lied))\b"),
    ("contrary/unlike", r"\b(?:contrary to|unlike what)\b"),
    ("lied/misleading", r"\b(?:lied?(?: to)?|misleading|propaganda|wrong about)\b"),
]

# Ngôn ngữ TWIST — M mềm (chỉ gợi ý, yếu hơn đính chính thẳng).
SOFT_PATTERNS: list[tuple[str, str]] = [
    ("despite/yet", r"\b(?:despite|yet somehow|however)\b"),
    ("surprise", r"\b(?:surprising(?:ly)?|unexpected(?:ly)?|shock(?:ed|ing)?|nobody expected)\b"),
]

# Cộng hưởng trong COMMENT: khán giả tự nói niềm tin của họ vừa vỡ.
RESONANCE_PATTERNS: list[tuple[str, str]] = PURE_PATTERNS + [
    ("i-thought", r"\bi (?:thought|was told|always believed|had no idea)\b"),
    ("press/west", r"\bthe (?:press|media|west|news)\b[^.!?]{0,60}\b(?:misleading|lying|lied|wrong|paint)"),
]


def _compiled(pairs: list[tuple[str, str]], extra: list[str]) -> list[tuple[str, re.Pattern]]:
    out = [(name, re.compile(rx, re.I)) for name, rx in pairs]
    out += [(f"cli:{rx[:20]}", re.compile(rx, re.I)) for rx in extra]
    return out


def _hit(text: str, pats: list[tuple[str, re.Pattern]]) -> str:
    for name, rx in pats:
        if rx.search(text or ""):
            return name
    return ""


def mine(rd, extra: list[str] | None = None) -> dict:
    """Trả {'pure': [...], 'soft': [...], 'resonance': [...], 'top_comments': [...]}.

    pure/soft: beat — {'video','t','type','summary','pattern','z'}
    resonance: comment/gap — {'text','likes','pattern','source'}
    top_comments: comment ❤ cao nhất bất kể pattern (nguyên liệu hook/ending).
    """
    extra = extra or []
    pure_p = _compiled(PURE_PATTERNS, extra)
    soft_p = _compiled(SOFT_PATTERNS, [])
    reso_p = _compiled(RESONANCE_PATTERNS, extra)

    pure, soft = [], []
    beats = read_json(rd / "beats.json") if (rd / "beats.json").is_file() else {}
    for vid, blist in beats.items():
        for b in blist:
            row = {"video": vid, "t": round(b.get("t_start", 0)),
                   "type": b.get("type", ""), "summary": b.get("summary", ""),
                   "z": b.get("peak_z_w", 0)}
            name = _hit(row["summary"], pure_p)
            if name:
                pure.append({**row, "pattern": name})
                continue
            name = _hit(row["summary"], soft_p)
            if name or row["type"] in ("twist", "reveal", "correction"):
                soft.append({**row, "pattern": name or f"type:{row['type']}"})

    resonance, all_comments = [], []
    cdir = rd / "comments"
    for f in sorted(cdir.glob("*.json")) if cdir.is_dir() else []:
        data = json.loads(f.read_text(encoding="utf-8"))
        for c in (data if isinstance(data, list) else data.get("comments", [])):
            if not isinstance(c, dict):
                continue
            row = {"text": (c.get("text") or "").strip(), "likes": c.get("likes", 0),
                   "source": f.stem}
            all_comments.append(row)
            name = _hit(row["text"], reso_p)
            if name:
                resonance.append({**row, "pattern": name})
    if (rd / "gaps.json").is_file():
        for g in read_json(rd / "gaps.json"):
            text = (g.get("text") or "").strip() if isinstance(g, dict) else ""
            name = _hit(text, reso_p)
            if name:
                resonance.append({"text": text, "likes": g.get("likes", 0),
                                  "source": "gaps", "pattern": name})

    pure.sort(key=lambda r: r["z"], reverse=True)
    soft.sort(key=lambda r: r["z"], reverse=True)
    resonance.sort(key=lambda r: r["likes"], reverse=True)
    all_comments.sort(key=lambda r: r["likes"], reverse=True)
    return {"pure": pure, "soft": soft, "resonance": resonance,
            "top_comments": all_comments}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Đào ứng viên M (V2) từ beat + comment của run")
    ap.add_argument("run", help="tên run trong runs/")
    ap.add_argument("--top", type=int, default=12, help="số dòng mỗi bảng (mặc định 12)")
    ap.add_argument("--pattern", action="append", default=[],
                    help="regex bổ sung tại chỗ (lặp được; pattern lâu dài thì thêm vào m_mine.py)")
    args = ap.parse_args(argv)
    rd = run_dir(args.run)
    r = mine(rd, args.pattern)

    def show(title, rows, fmt):
        print(f"\n— {title} ({len(rows)}):")
        if not rows:
            print("  (không có — xem bảng khác; sóng không có M thuần thì dùng M mềm + cộng hưởng)")
        for row in rows[:args.top]:
            print("  " + fmt(row))

    show("M THUẦN từ beat (đính chính trong chính video)", r["pure"],
         lambda b: f"[{b['video']} @{b['t']}s z={b['z']:.1f} {b['pattern']}] {b['summary']}")
    show("M MỀM từ beat twist", r["soft"],
         lambda b: f"[{b['video']} @{b['t']}s z={b['z']:.1f} {b['pattern']}] {b['summary']}")
    show("CỘNG HƯỞNG comment/gaps (niềm tin vỡ trong lời khán giả, sắp theo ❤)", r["resonance"],
         lambda c: f"❤{c['likes']} [{c['pattern']}] {c['text'][:160]}")
    show("TOP COMMENT ❤ (nguyên liệu quote cho hook/ending)", r["top_comments"],
         lambda c: f"❤{c['likes']} {c['text'][:160]}")
    print("\nChọn M rồi ghi vào outline: dòng `Misconception:` ngay dưới HOOK "
          "(Question: giữ NGUYÊN VĂN comment).")


if __name__ == "__main__":
    main()
