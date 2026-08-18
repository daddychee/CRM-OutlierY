"""Đối chiếu DESIGN.md với board.html — bắt lệch giữa TÀI LIỆU và thứ ĐANG CHẠY.

    python -m seo.designcheck

Vì sao phải có: dự án đã dính lỗi "hai nguồn sự thật cho cùng một thứ" ba lần (`siblings` ·
`#profSel` · textarea-vs-danh-sách) và lần nào cũng lệch. DESIGN.md là nguồn thứ hai cho bảng
màu + thang chữ + breakpoint. Không có hàng rào thì nó sẽ nói dối trong im lặng — mà tài liệu
nói dối còn tệ hơn không có tài liệu, vì người đọc TIN nó.

Chỉ kiểm thứ ĐỐI CHIẾU ĐƯỢC (token, con số, luật đếm được). Phần văn xuôi giải thích "vì sao"
không kiểm máy móc được — đó là lý do CLAUDE.md vẫn là nguồn gốc.

Chạy sau MỌI lần đụng `:root` hoặc bố cục, cùng hạng với `boardcheck` / `contrastcheck`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import contrastcheck as cc

ROOT = Path(__file__).parent.parent
BOARD = Path(__file__).parent / "board.html"
DOC = ROOT / "DESIGN.md"

# Token nào PHẢI xuất hiện đúng giá trị trong DESIGN.md. Không kiểm hết mọi token: bảng trong
# tài liệu cố ý gọn, nhưng cái nào đã CHÉP vào thì phải đúng.
MUST = ["bg", "panel", "raised", "border", "border-soft", "edge", "text", "muted", "faint",
        "accent", "accent-ink", "link", "ok", "danger", "scrim",
        "pil-title", "pil-tag", "pil-des"]


def _norm(v: str) -> str:
    """`rgba(217, 179, 108, .08)` và `rgba(217,179,108,.08)` là MỘT — bỏ khoảng trắng, hạ chữ."""
    return re.sub(r"\s+", "", (v or "")).lower()


def run(board: Path | None = None, doc: Path | None = None) -> int:
    css = (board or BOARD).read_text(encoding="utf-8")
    md = (doc or DOC).read_text(encoding="utf-8")
    ths = cc.themes(css)
    bad = []

    # ── 1. token: giá trị trong DESIGN.md phải KHỚP board ─────────────────────────────
    # Tài liệu khai 2 khối `:root`; tách ra để không lẫn giá trị dark sang light.
    blocks = {}
    m = re.search(r':root,:root\[data-theme="dark"\]\{(.*?)\n\}', md, re.S)
    if m:
        blocks["dark"] = m.group(1)
    m = re.search(r':root\[data-theme="light"\]\{(.*?)\n\}', md, re.S)
    if m:
        blocks["light"] = m.group(1)
    if len(blocks) != 2:
        bad.append(f"DESIGN.md thiếu khối :root ({sorted(blocks)}) — không đối chiếu được token")

    for th, body in blocks.items():
        doc_tok = {k: _norm(v) for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", body)}
        real = ths[th]
        for k in MUST:
            if k not in real:
                bad.append(f"[{th}] board KHÔNG có --{k} (tên token đổi rồi?)")
                continue
            if k not in doc_tok:                       # tài liệu được phép không chép hết
                continue
            if doc_tok[k] != _norm(real[k]):
                bad.append(f"[{th}] --{k}: DESIGN.md ghi {doc_tok[k]} · board đang {_norm(real[k])}")

    # ── 2. thang chữ ──────────────────────────────────────────────────────────────────
    scale = dict(re.findall(r"--(t-[a-z]+|lbl)\s*:\s*(\d+)px", css))
    for tok, px in scale.items():
        # tài liệu ghi dạng `| --t-md | **15px** |` hoặc `| `--t-xs` | 12px |`
        if f"`--{tok}`" in md or f"--{tok}" in md:
            near = re.search(rf"--{re.escape(tok)}`?\s*\|[^|]*\|\s*\*{{0,2}}(\d+)px", md)
            if near and near.group(1) != px:
                bad.append(f"thang chữ --{tok}: DESIGN.md ghi {near.group(1)}px · board {px}px")
    if scale and min(int(v) for v in scale.values()) < 12:
        bad.append("có font-size < 12px trong board — DESIGN.md khai SÀN là 12px")

    # ── 3. breakpoint ─────────────────────────────────────────────────────────────────
    bps = sorted({int(x) for x in re.findall(r"@media\s*\(max-width:(\d+)px\)", css)})
    for b in bps:
        if str(b) not in md:
            bad.append(f"breakpoint {b}px có trong board nhưng KHÔNG có trong DESIGN.md")
    # `.cols` và `.side` phải gãy ở CÙNG một ngưỡng — sticky chỉ có nghĩa khi còn 2 cột.
    cols = re.search(r"@media\s*\(max-width:(\d+)px\)\{\.cols\{", css)
    side = re.search(r"@media\s*\(max-width:(\d+)px\)\{\.side\{", css)
    if cols and side and cols.group(1) != side.group(1):
        bad.append(f".cols gãy ở {cols.group(1)}px nhưng .side hết sticky ở {side.group(1)}px "
                   f"— phải khớp nhau (xếp 1 cột rồi mà cột phải vẫn dính là vô nghĩa)")

    # ── 4. luật đếm được mà DESIGN.md tuyên bố ────────────────────────────────────────
    # MỌI phép soi "có/không có X" phải chạy trên bản ĐÃ BỎ CHÚ THÍCH. Board ghi rất nhiều bài
    # học dạng "KHÔNG dùng @media prefers-color-scheme nữa" ngay trong chú thích — soi thô là
    # bắt trúng chính câu cấm và báo hỏng. Đã cắn ngay lần chạy đầu.
    style = css[css.index("<style>"):css.index("</style>")]
    clean = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
    # Luật là "thẻ dữ liệu KHÔNG nhấc lên KHI HOVER", không phải "cấm translateY ở mọi nơi".
    # Bản đầu quét cả file ⇒ báo oan keyframe `panein` và `.toast` trượt lên.
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", clean):
        if ":hover" in sel and "translateY" in body.replace(" ", ""):
            bad.append(f"lift khi hover ở `{sel.strip()[:44]}` — DESIGN.md khai đổi VIỀN, không nhấc")
    # Thứ bị cấm là @media trong CSS nhân đôi bảng màu. `matchMedia('(prefers-color-scheme…)')`
    # trong JS là ĐÚNG cơ chế — nó đọc cài đặt hệ thống cho chế độ "Tự động".
    if re.search(r"@media[^{]*prefers-color-scheme", clean):
        bad.append("có @media prefers-color-scheme — DESIGN.md khai theme đặt bằng data-theme")
    if re.search(r"@import\s+url|fonts\.googleapis", css):
        bad.append("có webfont/CDN — DESIGN.md khai chạy offline, font hệ thống")
    if re.search(r"\bIntersectionObserver\b|ScrollTrigger|\bgsap\b", css):
        bad.append("có scroll-reveal/GSAP — DESIGN.md khai tier L1, CSS thuần")
    if "prefers-reduced-motion" not in css:
        bad.append("thiếu prefers-reduced-motion — DESIGN.md khai có")
    dur = re.search(r"--dur\s*:\s*\.?(\d+)s", css)
    if dur and f".{dur.group(1)}s" not in md:
        bad.append(f"--dur=.{dur.group(1)}s trong board nhưng DESIGN.md không nhắc")

    # ── 5. hex hardcode ngoài :root (luật màu số 1 của DESIGN.md) ─────────────────────
    style = css[css.index("<style>"):css.index("</style>")]
    rest = style
    for blk in re.findall(r":root[^{]*\{.*?\n\s*\}", style, re.S):
        rest = rest.replace(blk, "")
    rest = re.sub(r"/\*.*?\*/", "", rest, flags=re.S)          # bỏ chú thích — hex ở đó là ghi chú
    stray = re.findall(r"#[0-9A-Fa-f]{3,8}\b", rest)
    if stray:
        bad.append(f"hex hardcode ngoài :root: {sorted(set(stray))[:6]}")

    for b in bad:
        print("  ✗", b)
    print(f"\n{'DESIGN.md KHOP board.html' if not bad else f'CO {len(bad)} CHO LECH'}")
    return 1 if bad else 0


if __name__ == "__main__":                    # self-test: bộ kiểm phải BẮT được lệch thật
    import tempfile

    assert run() == 0, "DESIGN.md thật phải khớp board thật"

    md = DOC.read_text(encoding="utf-8")
    css = BOARD.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        # ca 1: tài liệu ghi sai một token. LẤY accent HIỆN HÀNH bằng regex thay vì ghim
        # hex cứng — ghim #D9B36C là ca thử tự vỡ ngay lần đổi bảng màu đầu tiên (dính
        # thật 04/08/2026 khi chuyển sang bảng Breakout Signal của OUTLIERY).
        import re as _re
        f = Path(tmp) / "d.md"
        _ac = _re.search(r"--accent:#[0-9A-Fa-f]{6};", md)
        assert _ac, "DESIGN.md không còn dòng --accent nào để dựng ca thử"
        broken = md.replace(_ac.group(0), "--accent:#FF0000;", 1)
        assert broken != md, "không dựng được ca token sai"
        f.write_text(broken, encoding="utf-8")
        assert run(doc=f) == 1, "phải BẮT được token lệch"

        # ca 2: board lệch hai ngưỡng breakpoint của .cols và .side
        g = Path(tmp) / "b.html"
        b2 = css.replace("@media (max-width:1372px){.side{position:static}}",
                         "@media (max-width:1160px){.side{position:static}}", 1)
        assert b2 != css, "không dựng được ca breakpoint lệch"
        g.write_text(b2, encoding="utf-8")
        assert run(board=g) == 1, "phải BẮT được .cols/.side lệch ngưỡng"

    print("designcheck.py self-test OK - bat duoc ca token lech lan breakpoint lech")
    sys.exit(run())
