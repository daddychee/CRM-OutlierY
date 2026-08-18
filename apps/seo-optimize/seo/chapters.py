"""SRT → chapters cho Description. Python trích timestamp (chính xác), LLM đặt tiêu đề (describe.py).

Luật chapter YouTube: bắt đầu 00:00 · ≥3 chapter · mỗi chapter ≥10 giây · thứ tự tăng dần.
"""
from __future__ import annotations

import re

_TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def _to_sec(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(text: str) -> list[dict]:
    """Parse SRT → [{start, end, text}] (giây). Bỏ qua block hỏng."""
    cues: list[dict] = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        ts_line = next((ln for ln in lines if "-->" in ln), None)
        if not ts_line:
            continue
        m = _TS.findall(ts_line)
        if len(m) < 2:
            continue
        start, end = _to_sec(*m[0]), _to_sec(*m[1])
        body = " ".join(ln for ln in lines if "-->" not in ln and not ln.strip().isdigit())
        cues.append({"start": start, "end": end, "text": body.strip()})
    return cues


def sec_to_ts(sec: float) -> str:
    """Giây → '0:00' hoặc 'H:MM:SS' (định dạng chapter YouTube)."""
    sec = int(max(0, sec))
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


TARGET_SEC = 180        # ~3 phút/chapter — trong dải 1-4 phút YouTube khuyến nghị
MIN_CH, MAX_CH = 3, 12  # <3 là YouTube không nhận; >12 thì danh sách dài hơn cả description


def auto_n(cues: list[dict]) -> int:
    """Số chapter SUY TỪ ĐỘ DÀI VIDEO, không phải hằng số.

    Trước đây cứng `n=5`: video 8 phút cũng 5 mục, video 31 phút cũng 5 mục → mỗi mục 6 phút,
    quá thô để người xem nhảy đúng chỗ (đo trên tập FINLAND thật của user). Tập là BIẾN SỐ nên
    số chapter phải bám theo chính nó.

    Chặn dưới 3 vì `validate_chapters` (luật YouTube) đòi ≥3. Chặn trên 12 để không đẻ ra danh
    sách timestamp dài hơn cả phần nội dung. Cũng không vượt quá số dòng SRT có thật.
    """
    if not cues:
        return 0
    total = cues[-1]["end"]
    n = round(total / TARGET_SEC) if total > 0 else MIN_CH
    return max(MIN_CH, min(MAX_CH, n, len(cues)))


def segment_cues(cues: list[dict], n: int = 5) -> list[dict]:
    """Chia cues thành ~n đoạn đều theo thời gian → [{start, ts, text}] (neo timestamp thật).

    Đoạn đầu ép start=0 (luật YouTube). Dùng cho LLM đặt tiêu đề mỗi đoạn.
    """
    if not cues:
        return []
    total = cues[-1]["end"]
    n = max(1, min(n, len(cues)))
    bounds = [total * i / n for i in range(n)]
    segs: list[dict] = []
    for i, b in enumerate(bounds):
        start = 0.0 if i == 0 else next((c["start"] for c in cues if c["start"] >= b), b)
        segs.append({"start": start, "ts": sec_to_ts(start), "text": ""})
    # gom text mỗi đoạn để cấp ngữ cảnh cho LLM
    for c in cues:
        idx = max(i for i, s in enumerate(segs) if c["start"] >= s["start"] - 0.001)
        segs[idx]["text"] = (segs[idx]["text"] + " " + c["text"]).strip()
    return segs


def validate_chapters(chaps: list[dict]) -> tuple[bool, list[str]]:
    """chaps = [{start(sec), label}]. Trả (hợp_lệ, danh_sách_lỗi) theo luật YouTube."""
    issues: list[str] = []
    if len(chaps) < 3:
        issues.append(f"cần ≥3 chapter (có {len(chaps)})")
    if chaps and chaps[0]["start"] > 0.5:
        issues.append("chapter đầu phải ở 00:00")
    for a, b in zip(chaps, chaps[1:]):
        if b["start"] <= a["start"]:
            issues.append("timestamp không tăng dần")
            break
        if b["start"] - a["start"] < 10:
            issues.append("có chapter < 10 giây")
            break
    return (not issues, issues)


if __name__ == "__main__":                             # self-test offline (seed giả)
    srt = """1
00:00:00,000 --> 00:00:04,000
Look up at the night sky.

2
00:00:04,000 --> 00:03:40,000
A monster of four million suns.

3
00:03:40,000 --> 00:09:40,000
Spaghettification and the event horizon."""
    cues = parse_srt(srt)
    assert len(cues) == 3 and cues[0]["start"] == 0.0 and cues[-1]["end"] == 580.0, cues
    assert sec_to_ts(0) == "0:00" and sec_to_ts(72) == "1:12" and sec_to_ts(3670) == "1:01:10"
    segs = segment_cues(cues, n=3)
    assert segs[0]["start"] == 0.0 and len(segs) == 3, segs
    ok, iss = validate_chapters([{"start": 0, "label": "a"}, {"start": 60, "label": "b"}, {"start": 120, "label": "c"}])
    assert ok, iss
    ok2, iss2 = validate_chapters([{"start": 5, "label": "a"}, {"start": 8, "label": "b"}])
    assert not ok2 and len(iss2) >= 1, iss2
    # ── số chapter SUY TỪ ĐỘ DÀI, không phải hằng số ──
    def fake(mins, step=10):
        return [{"start": t, "end": t + step, "text": "x"} for t in range(0, mins * 60, step)]
    assert auto_n([]) == 0
    assert auto_n(fake(8)) == 3, auto_n(fake(8))          # 8 phút → 3 (chặn dưới, luật YouTube)
    assert auto_n(fake(31)) == 10, auto_n(fake(31))       # 31 phút → ~10 mục, mỗi mục ~3 phút
    assert auto_n(fake(60)) == 12, auto_n(fake(60))       # 60 phút → chặn trên 12
    assert auto_n(fake(2)) == 3, auto_n(fake(2))          # video rất ngắn vẫn phải đủ 3
    # SRT thưa: KHÔNG đòi nhiều chapter hơn số dòng có thật (30 phút nhưng chỉ 4 dòng → tối đa 4)
    sparse = [{"start": t, "end": t + 450, "text": "x"} for t in (0, 450, 900, 1350)]
    assert auto_n(sparse) == len(sparse) == 4, auto_n(sparse)
    segs = segment_cues(fake(31), n=auto_n(fake(31)))
    ok, iss = validate_chapters([{"start": s["start"], "label": "x"} for s in segs])
    assert ok, iss                                         # phải qua chính luật YouTube của mình

    print("chapters.py self-test OK")
