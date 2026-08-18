"""Đo tương phản WCAG cho TOÀN MA TRẬN màu chữ × màu nền của board.html — dark VÀ light.

    python -m seo.contrastcheck

Vì sao phải có file này: CLAUDE.md chốt "đổi màu trong `:root` phải đo lại toàn bộ ma trận,
đừng chỉ kiểm 1 cặp" — đã cắn 2026-07-28 (chỉ đo trên `panel` nên bỏ sót `raised`). Kiểm bằng
mắt hay bằng trí nhớ đều không đếm được 60 cặp.

Đọc THẲNG `:root` và khối `@media (prefers-color-scheme: light)` trong chính board.html.
Chép màu sang đây rồi đo là đo bản trong đầu, không phải bản đang chạy.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import common

INK = ["text", "muted", "faint", "accent", "ok", "danger", "link",
       "pil-title", "pil-tag", "pil-des"]
BG = ["bg", "panel", "raised"]
# Cặp chữ-trên-nền-đặc nằm NGOÀI ma trận nhưng vẫn là chữ đọc trên nền (nút .newbtn, #exportBtn).
SOLID = [("accent-ink", "accent")]
AA = 4.5

# ── NỀN TRONG SUỐT PHỦ LÊN NỀN ĐẶC — chỗ ma trận thuần TỪNG MÙ ────────────────────────
# Ma trận trên chỉ đo `ink × {bg,panel,raised}`. Nhưng board có hàng loạt nền `rgba(...)`
# phủ lên một mặt đặc: `.card.picked` (--pil-soft trên raised), `.mini.on` / `.re:hover`
# (--accent-soft), `.chip.warn` cũ (--danger-soft). Chữ nằm TRÊN nền đã trộn đó, và tỉ số
# thật thấp hơn hẳn so với trên mặt trần.
# Đo thật 2026-08-01: `faint` trên `.card.picked` = 3.99 (DƯỚI AA) trong khi ma trận báo
# 5.31 trên `raised` → bộ kiểm báo xanh cho một lỗi đang chạy. Đây đúng là kiểu "bộ kiểm
# nói dối" mà CLAUDE.md cấm. Liệt kê tường minh ở đây để nó không mù nữa.
#   (tên nền rgba, nền đặc bên dưới, [các màu chữ nằm lên nó])
TINTS = [
    ("pil-title-soft", "raised", ["text", "muted", "faint", "danger", "ok", "link"]),
    ("pil-tag-soft", "raised", ["text", "muted", "faint", "danger", "ok", "link"]),
    ("pil-des-soft", "raised", ["text", "muted", "faint", "danger", "ok", "link"]),
    ("accent-soft", "panel", ["accent", "text", "muted"]),
    # `faint` thêm vào 2026-08-01 cùng bảng kết quả tìm kiếm: dòng phụ (`.gitem .sub`) dùng
    # `--faint` và nằm trên nền hover `accent-soft` phủ lên `raised`. Thiếu nó thì bộ kiểm
    # báo xanh cho đúng kiểu lỗi đã cắn một lần (`faint` trong thẻ đã chọn đo ra 3.99 trong
    # khi ma trận thuần báo 5.31) — bộ kiểm không nhìn tới thì im lặng, không phải là đạt.
    ("accent-soft", "raised", ["accent", "text", "muted", "faint"]),
    ("danger-soft", "panel", ["danger", "text"]),
]


def _blend(rgba: str, base):
    """`rgba(r,g,b,a)` phủ lên nền đặc → màu MẮT THẬT SỰ NHÌN THẤY."""
    m = re.match(r"rgba?\(([^)]+)\)", (rgba or "").strip())
    if not m:
        return None
    p = [x.strip() for x in m.group(1).split(",")]
    if len(p) < 4:
        return _rgb(rgba)
    r, g, b = (float(x) for x in p[:3])
    a = float(p[3])
    return tuple(round(a * c + (1 - a) * d) for c, d in zip((r, g, b), base))


def _block(css: str, pat: str) -> dict:
    m = re.search(pat, css, re.S)
    if not m:
        raise RuntimeError(f"không thấy khối màu khớp {pat!r} trong board.html")
    return dict(re.findall(r"--([\w-]+)\s*:\s*([^;}]+)", m.group(1)))


def _rgb(v: str):
    v = v.strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.match(r"rgba?\(([^)]+)\)", v)
    if m:
        return tuple(int(float(x)) for x in [p.strip() for p in m.group(1).split(",")][:3])
    return None


def _lum(c) -> float:
    def f(x: float) -> float:
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in c)
    return .2126 * r + .7152 * g + .0722 * b


def ratio(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def themes(css: str) -> dict:
    """Hai bảng màu, mỗi bảng khai ĐÚNG MỘT chỗ (không còn @media nhân đôi)."""
    return {"dark": _block(css, r':root,:root\[data-theme="dark"\]\{(.*?)\n\s*\}'),
            "light": _block(css, r':root\[data-theme="light"\]\{(.*?)\n\s*\}')}


# Dải "dễ nhìn": AA đòi >= 4.5, nhưng chữ thân bài vượt ~14:1 trên nền tối thì loá (halation).
# Cảnh báo thôi, không đánh trượt — vẫn hợp chuẩn, chỉ là mỏi mắt khi đọc lâu.
GLARE_HI = 14.0
BODY = "text"


def run(board: Path | None = None) -> int:
    css = (board or (Path(__file__).parent / "board.html")).read_text(encoding="utf-8")
    ths = themes(css)
    bad = 0
    for th, v in ths.items():
        print(f"\n{'':14}" + "".join(f"{b:>10}" for b in BG) + f"   [{th}]")
        for ink in INK:
            if ink not in v:
                print(f"{ink:14}{'(chưa khai)':>30}")
                continue
            row = f"{ink:14}"
            for b in BG:
                ci, cb = _rgb(v.get(ink, "")), _rgb(v.get(b, ""))
                if not ci or not cb:
                    row += f"{'?':>10}"
                    continue
                r = ratio(ci, cb)
                if r < AA:
                    bad += 1
                    row += f"{r:9.2f}✗"
                else:
                    row += f"{r:10.2f}"
            print(row)
    for th, v in ths.items():                     # chữ thân bài có bị chói không
        ci, cb = _rgb(v.get(BODY, "")), _rgb(v.get("bg", ""))
        if ci and cb:
            r = ratio(ci, cb)
            note = "  ⚠ CHOI (>%.0f:1 tren nen nay de bi loa)" % GLARE_HI if r > GLARE_HI else "  (de nhin)"
            print(f"\n[{th}] chu than bai tren nen: {r:.2f}:1{note}")

    print("\nChữ trên NỀN TRONG SUỐT đã phủ (thẻ đã chọn · nút bật · chip cảnh báo):")
    for th, v in ths.items():
        for tint, base, inks in TINTS:
            if tint not in v or base not in v:
                continue
            mixed = _blend(v[tint], _rgb(v[base]))
            if not mixed:
                continue
            for ink in inks:
                if ink not in v:
                    continue
                r = ratio(_rgb(v[ink]), mixed)
                if r < AA:
                    bad += 1
                    print(f"   [{th:5}] {ink} trên {tint}/{base} = {r:.2f}  ✗")
    print("   (chỉ in cặp KHÔNG đạt — im lặng nghĩa là đủ)")

    print("\nCặp riêng (chữ trên nền đặc):")
    for th, v in ths.items():
        for ink, bg in SOLID:
            if ink in v and bg in v:
                r = ratio(_rgb(v[ink]), _rgb(v[bg]))
                bad += 0 if r >= AA else 1
                print(f"   [{th:5}] {ink} trên {bg:8} {r:6.2f}" + ("" if r >= AA else "  ✗"))
    print(f"\n{'DAT HET (moi cap >= 4.5:1)' if not bad else f'CO {bad} CAP DUOI CHUAN 4.5:1'}")
    return 1 if bad else 0


if __name__ == "__main__":                       # self-test: bộ kiểm phải BẮT được lỗi thật
    import tempfile

    good = Path(__file__).parent / "board.html"
    assert run(good) == 0, "board.html thật phải đạt"

    # trồng một màu hỏng rồi kiểm lại — bộ kiểm luôn báo xanh thì chính nó là lời nói dối
    css = good.read_text(encoding="utf-8")
    broken = re.sub(r"(--faint:)#\w{6}", r"\g<1>#3A3F47", css, count=1)
    assert broken != css, "không thay được --faint để dựng ca hỏng"
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "b.html"
        f.write_text(broken, encoding="utf-8")
        assert run(f) == 1, "phải BẮT được --faint quá tối"
    print("\ncontrastcheck.py self-test OK - bat duoc mau hong, board that dat chuan")
    sys.exit(run(good))
