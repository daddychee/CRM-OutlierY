"""Module 6 (phan do) — Validate: kich ban dau ra giong tac gia bao nhieu %.

Do kich ban cuoi bang chinh Quant Engine, so voi reproduction_targets cua tac gia:
moi target dat khi gia tri kich ban nam trong +-1 SD vung tac gia (tieu chi Muc 9).
"Dat X/14 target = Y%" — con so Python do, khong LLM uoc luong.

Cong bang do dai: TTR va vai dac trung nhay do dai, nen khi co corpus tac gia, do
LAI target tren cac cua so bang do dai kich ban (khong dung target do tren ca chuong).
"""
from __future__ import annotations

import statistics

from .quant import _raw_features, compute_features
from .textutils import split_sentences, tokenize_words


def chunk_by_words(texts: list[str], target_words: int) -> list[str]:
    """Cat corpus thanh cac doan ~target_words tu, theo ranh gioi cau (khong vo cau)."""
    chunks: list[str] = []
    buf: list[str] = []
    buf_words = 0
    for text in texts:
        for sent in split_sentences(text):
            buf.append(sent)
            buf_words += len(tokenize_words(sent))
            if buf_words >= target_words:
                chunks.append(" ".join(buf))
                buf, buf_words = [], 0
    if buf and buf_words >= target_words // 2:
        chunks.append(" ".join(buf))
    return chunks


def targets_for_length(texts: list[str], target_words: int) -> dict[str, dict]:
    """Target (mean +-1 SD) do tren cac doan corpus cung co voi kich ban -> cong bang do dai."""
    chunks = chunk_by_words(texts, target_words)
    if len(chunks) < 2:  # corpus qua ngan so voi kich ban -> khong du cua so
        chunks = texts
    per = [_raw_features(c) for c in chunks]
    out = {}
    for name in per[0]:
        vals = [f[name] for f in per]
        mean = statistics.mean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        out[name] = {"target": mean, "sd": sd}
    return out


def strip_front_matter(text: str) -> str:
    """Bo front-matter '---...---' o dau file (header thong tin) truoc khi do."""
    t = text.lstrip()
    if t.startswith("---"):
        end = t.find("\n---", 3)
        if end != -1:
            nl = t.find("\n", end + 1)
            return t[nl + 1:].lstrip() if nl != -1 else ""
    return text


def evaluate_script(script_text: str, targets: dict[str, dict], sd_tol: float = 1.0) -> dict:
    """So kich ban voi cac target. Tra ve verdict + chi tiet tung target.

    targets: {name: {"target": float, "sd": float}} (reproduction_targets hoac
    targets_for_length). Chi cham cac feature co trong `targets`. Header front-matter
    (neu co) duoc bo qua truoc khi do.
    """
    script_text = strip_front_matter(script_text)
    measured = compute_features([script_text])
    rows = []
    n_pass = 0
    n_bo = 0
    for name, t in targets.items():
        val = measured.get(name)
        if val is None:
            continue
        # C1: target dung tren corpus chua du diem do (sd khong do duoc) thi KHONG cham.
        # Cham no bang band 5% la doi tra ket luan cho thu chua he do duoc.
        if t.get("do_duoc") is False:
            n_bo += 1
            continue
        sd = t.get("sd") or 0.0
        target = t["target"]
        # sd=0 (dac trung hang so trong corpus) -> yeu cau khop sat tuong doi
        band = sd * sd_tol if sd > 0 else max(abs(target) * 0.05, 1e-9)
        ok = abs(val - target) <= band
        n_pass += ok
        rows.append({
            "name": name,
            "value": round(val, 4),
            "target": round(target, 4),
            "sd": round(sd, 4),
            "low": round(target - band, 4),
            "high": round(target + band, 4),
            "pass": ok,
        })
    total = len(rows)
    pct = round(100 * n_pass / total) if total else 0
    rows.sort(key=lambda r: (r["pass"], r["name"]))  # truot len dau cho de sua
    return {
        "n_pass": n_pass,
        "n_total": total,
        "n_khong_do_duoc": n_bo,
        "percent": pct,
        "script_words": len(tokenize_words(script_text)),
        "targets": rows,
    }


def format_report(verdict: dict) -> str:
    """Bao cao van ban ngan cho CLI/GUI."""
    lines = [f"Giong tac gia: dat {verdict['n_pass']}/{verdict['n_total']} target "
             f"= {verdict['percent']}%  ({verdict['script_words']} tu)"]
    for r in verdict["targets"]:
        mark = "✓" if r["pass"] else "✗"
        lines.append(f"  {mark} {r['name']:26s} do={r['value']:<10} "
                     f"target {r['target']} ± {r['sd']}  [{r['low']}..{r['high']}]")
    return "\n".join(lines)
