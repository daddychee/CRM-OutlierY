"""S3a — Phân loại peak (LLM đề xuất + Python verify trích dẫn).

Chạy:  python3 -m oe.s3_label_peaks --run <tên>

Mỗi peak → 1 trong 4 loại: value / confusion / navigation / sponsor (METHODOLOGY §S3).
LLM phải kèm `quote` nguyên văn từ transcript làm bằng chứng; Python kiểm quote có thật trong
đoạn quanh peak — verify fail thì default `value` (không tin nhãn không có bằng chứng).
Ghi đè peaks.json với field `peak_type`, `why`, `quote`, `quote_verified`.
"""
from __future__ import annotations

import argparse
import re

from . import common
from .llm import LLM, extract_json

SYSTEM = (
    "Bạn phân loại các đỉnh 'Most Replayed' của video YouTube. Mỗi đỉnh là đoạn khán giả tua "
    "lại xem nhiều. Nhiệm vụ: gán MỖI đỉnh đúng MỘT loại và trích MỘT câu nguyên văn từ chính "
    "đoạn transcript đã cho làm bằng chứng.\n"
    "Loại:\n"
    "- value: tua lại vì nội dung HAY (câu chuyện, con số sốc, ý tưởng, cú lật, hình ảnh ấn tượng).\n"
    "- confusion: tua lại vì KHÓ HIỂU, phải nghe lại mới nắm.\n"
    "- navigation: điểm nhảy mục / mở chương, không phải nội dung thực chất.\n"
    "- sponsor: đoạn QUẢNG CÁO TÀI TRỢ (nhắc nhãn hàng, mã giảm giá, 'thanks to ... for "
    "supporting', kêu gọi dùng dịch vụ). Đây KHÔNG phải nội dung, phải loại.\n"
    "Chỉ trả JSON, không giải thích ngoài JSON."
)


def _prompt(video_title: str, peaks: list[dict]) -> str:
    items = []
    for i, p in enumerate(peaks):
        items.append(f'[{i}] t={p["t_center"]}s z={p["intensity_z"]}\n'
                     f'transcript: "{(p.get("transcript_excerpt") or "")[:600]}"')
    body = "\n\n".join(items)
    return (
        f'Video: "{video_title}".\nPhân loại {len(peaks)} đỉnh dưới đây. '
        f'Trả JSON: [{{"i":<số>,"type":"value|confusion|navigation|sponsor",'
        f'"why":"<lý do ngắn>","quote":"<câu nguyên văn lấy từ transcript của đỉnh đó>"}}].\n\n'
        f"{body}"
    )


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def label_video(llm: LLM, title: str, peaks: list[dict]) -> list[dict]:
    if not peaks:
        return peaks
    raw = llm.complete(SYSTEM, _prompt(title, peaks), max_tokens=4000)
    labels = extract_json(raw)
    by_i = {int(x["i"]): x for x in labels if "i" in x}
    for i, p in enumerate(peaks):
        lab = by_i.get(i, {})
        typ = lab.get("type", "value")
        quote = (lab.get("quote") or "").strip()
        verified = bool(quote) and _norm(quote)[:40] in _norm(p.get("transcript_excerpt", ""))
        # không tin nhãn 'loại bỏ' nếu quote không verify được -> giữ value cho an toàn
        if typ != "value" and not verified:
            p["peak_type"] = "value"
            p["why"] = f"(LLM gán {typ} nhưng quote không verify — giữ value)"
        else:
            p["peak_type"] = typ if typ in ("value", "confusion", "navigation", "sponsor") else "value"
            p["why"] = (lab.get("why") or "").strip()
        p["quote"] = quote
        p["quote_verified"] = verified
    return peaks


def run(run_name: str) -> None:
    rd = common.run_dir(run_name)
    videos = common.read_json(rd / "videos.json")
    peaks_by_vid = common.read_json(rd / "peaks.json")
    llm = LLM(common.ROOT / ".env")

    counts: dict[str, int] = {}
    for vid, peaks in peaks_by_vid.items():
        title = videos.get(vid, {}).get("title") or vid
        labeled = label_video(llm, title, peaks)
        for p in labeled:
            counts[p["peak_type"]] = counts.get(p["peak_type"], 0) + 1
        kept = sum(1 for p in labeled if p["peak_type"] == "value")
        drop = [f'{p["peak_type"]}@{int(p["t_center"])}s' for p in labeled if p["peak_type"] != "value"]
        print(f"  {title[:45]!r}: {kept}/{len(labeled)} value"
              + (f" · loại: {', '.join(drop)}" if drop else ""), flush=True)

    common.write_json(rd / "peaks.json", peaks_by_vid)
    print(f"\nS3a xong → {rd/'peaks.json'} · tổng: {counts}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S3a label peaks")
    ap.add_argument("--run", required=True)
    run(ap.parse_args(argv).run)


if __name__ == "__main__":
    main()
