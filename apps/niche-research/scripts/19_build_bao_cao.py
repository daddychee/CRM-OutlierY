# -*- coding: utf-8 -*-
"""19_build_bao_cao.py <project_dir> — render BÁO CÁO GỘP 8 PHASE (HTML) từ artifact.

Tầng 1 (PY, deterministic — user chốt 19/08 "hãy code"): dựng HTML theo đúng khuôn
bản mẫu LifeIn_US đã duyệt 18/08 (anchor id tq/p0..p8/honesty, mỗi phase 3 lớp
SỐ → NGHĨA → GATE, bảng dài thu gọn <details>). Tầng SỐ lấy NGUYÊN từ JSON
niche-data (van chống bịa: thiếu nguồn → ghi "nguồn thiếu", không số giả);
tầng NGHĨA là SLOT gắn nhãn GIẢ ĐỊNH/chờ `bao_cao_writer` [LLM] — trừ các artifact
LLM pipeline ĐÃ sinh khi chạy --llm (execution_plan/dna/SUMMARY) thì nhúng nguyên
văn kèm nhãn nguồn. Chạy cuối mỗi run (bridge data-analytics gọi trước snapshot).
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "niche-data"
REPORT_DIR = "Report"
TEN_FILE = "BAO-CAO-8-PHASE.html"


def _doc(nd: Path, ten: str) -> dict:
    p = nd / ten
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"_list": d}
    except (json.JSONDecodeError, OSError):
        return {}


def e(x) -> str:
    return html.escape(str(x if x is not None else "—"))


def f_vn(n, mac_dinh="—") -> str:
    """Số VN 1.234; None/lỗi → mặc định (không bịa 0)."""
    try:
        return "{:,}".format(round(float(n))).replace(",", ".")
    except (TypeError, ValueError):
        return mac_dinh


def f_pt(x, mac_dinh="—") -> str:
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return mac_dinh


def f_so(x, ch=2, mac_dinh="—") -> str:
    try:
        return f"{float(x):.{ch}f}".replace(".", ",")
    except (TypeError, ValueError):
        return mac_dinh


def bang(cot: list[str], hang: list[list[str]], can_phai: set[int] | None = None) -> str:
    can_phai = can_phai or set()
    th = "".join(f"<th{' class=num' if i in can_phai else ''}>{c}</th>" for i, c in enumerate(cot))
    tr = "".join(
        "<tr>" + "".join(
            f"<td{' class=num' if i in can_phai else ''}>{o}</td>" for i, o in enumerate(h))
        + "</tr>" for h in hang)
    return f"<div class='tblwrap'><table><tr>{th}</tr>{tr}</table></div>"


def gon(tieu_de: str, noi_dung: str, mo: bool = False) -> str:
    return (f"<details{' open' if mo else ''}><summary>{tieu_de}</summary>"
            f"{noi_dung}</details>")


def lop_so(nhan="Số liệu") -> str:
    return f"<div class='layer l-so'>{nhan}</div>"


def lop_nghia(nhan: str) -> str:
    return f"<div class='layer l-nghia'>{nhan}</div>"


def lop_gate(nhan: str) -> str:
    return f"<div class='layer l-gate'>{nhan}</div>"


def cho_writer(mo_ta: str) -> str:
    """Slot NGHĨA chờ bao_cao_writer — nhãn rõ, KHÔNG nội dung bịa."""
    return (f"<div class='card cho'><span class='as'>GIẢ ĐỊNH / CHỜ WRITER</span> "
            f"{mo_ta} — tầng NGHĨA sinh bởi <code>bao_cao_writer</code> [LLM] "
            f"(chưa chạy cho bản này); số bên trên là nguồn neo.</div>")


def khoi_canvas(nghia: dict, nhan: str) -> str:
    """Audience Profile Canvas từ bao_cao_writer — markup NHÁY KÉP + <table> trần
    đúng khuôn bản mẫu US để dashboard trich_nghia cắt được."""
    cv = nghia.get("canvas") or {}
    cot, hang = cv.get("cot") or [], cv.get("hang") or []
    if not (cot and hang):
        return ""
    th = "<th></th>" + "".join(f"<th>{e(c)}</th>" for c in cot)
    tr = "".join("<tr><td>" + e(h.get("ten")) + "</td>"
                 + "".join(f"<td>{e(o)}</td>" for o in (h.get("o") or []))
                 + "</tr>" for h in hang)
    return (f'<div class="card"><h4>Audience Profile Canvas '
            f'<span class="as">DIỄN GIẢI — {nhan}</span></h4>'
            f"<div class='tblwrap'><table><tr>{th}</tr>{tr}</table></div></div>")


def khoi_phuong_an(nghia: dict, nhan: str) -> str:
    """Card Phương án A/B/C + Anti-positioning — h4 bắt đầu 'Phương án'/'Anti-'
    đúng khuôn extractor dashboard."""
    ds = nghia.get("phuong_an") or []
    if not ds:
        return ""
    ra = [f'<div class="card"><span class="as">DIỄN GIẢI — {nhan}</span></div>']
    for pa in ds:
        muc = "".join(f"<li>{e(x)}</li>" for x in (pa.get("noi_dung") or []))
        ra.append(f'<div class="card"><h4>{e(pa.get("ten"))}</h4><ul>{muc}</ul></div>')
    anti = nghia.get("anti") or []
    if anti:
        muc = "".join(f"<li>{e(x)}</li>" for x in anti)
        ra.append('<div class="card"><h4>Anti-positioning — những điều KHÔNG làm'
                  f"</h4><ul>{muc}</ul></div>")
    return "".join(ra)


def khoi_muc_list(ds, tieu_de: str, nhan: str) -> str:
    if not ds:
        return ""
    muc = "".join(f"<li>{e(x)}</li>" for x in ds)
    return (f'<div class="card"><h4>{e(tieu_de)} '
            f'<span class="as">DIỄN GIẢI — {nhan}</span></h4><ul>{muc}</ul></div>')


def khoi_tong_hop(nghia: dict, nhan: str) -> str:
    th = nghia.get("tong_hop") or {}
    if not th.get("doan"):
        return ""
    rut = "".join(f"<li>{e(x)}</li>" for x in (th.get("rut_lui") or []))
    return (f'<div class="card"><h4>Tổng hợp chiến lược '
            f'<span class="as">DIỄN GIẢI — {nhan}</span></h4>'
            f"<p style='margin:.4em 0'>{e(th.get('doan'))}</p>"
            + (f"<b style='font-size:12px'>Điều kiện rút lui (falsifiers):</b><ul>{rut}</ul>" if rut else "")
            + "</div>")


def thieu(nguon: str) -> str:
    return f"<div class='card cho'>Nguồn thiếu — pipeline chưa sinh <code>{nguon}</code> cho run này.</div>"


CSS = """
:root{--bg:#090C12;--panel:#121826;--raised:#182233;--line:#243149;--ink:#E8EDF4;
  --muted:#8B96A8;--accent:#4C8FE0;--gold:#C9A35A;--bad:#D97C6C;--ok:#83A96F}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.6 Inter,"Segoe UI",system-ui,sans-serif;padding:28px 20px 60px}
.wrap{max-width:1060px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:17px;margin:0 0 10px;padding-top:6px}
h4{margin:0 0 8px;font-size:14.5px}
a{color:var(--accent);text-decoration:none}
.eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:22px}
.chip{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;
  border:1px solid var(--gold);color:var(--gold);border-radius:7px;padding:2px 10px}
.chip.go{border-color:var(--accent);color:var(--accent)}
.chip.nogo{border-color:var(--bad);color:var(--bad)}
section{border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:0 0 18px;
  background:var(--panel)}
.layer{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
  border-top:1px solid var(--line);padding:10px 0 6px;margin-top:10px}
.layer.l-so{color:var(--accent)}
.layer.l-nghia{color:#A78BC8}
.layer.l-gate{color:var(--gold)}
.card{background:var(--raised);border:1px solid var(--line);border-radius:10px;
  padding:11px 13px;margin:8px 0;font-size:13px}
.card.cho{color:var(--muted);border-style:dashed}
.as{font-size:10px;font-weight:700;background:#3A2E19;color:var(--gold);
  border-radius:5px;padding:1px 6px;letter-spacing:.06em}
.tblwrap{overflow-x:auto;margin:6px 0}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
  text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:5px 8px;border-bottom:1px solid #182233;vertical-align:top}
th.num,td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
details{margin:8px 0}
details summary{cursor:pointer;font-size:12.5px;color:var(--accent);padding:4px 0}
.pillar{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:13px}
.pillar .ten{width:150px;color:var(--muted)}
.pillar .thanh{flex:1;height:9px;background:var(--raised);border-radius:99px;overflow:hidden}
.pillar .thanh i{display:block;height:100%;background:var(--accent);border-radius:99px}
.pillar .diem{width:36px;text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
pre{background:var(--raised);border:1px solid var(--line);border-radius:10px;
  padding:12px;font-size:12px;overflow-x:auto;white-space:pre-wrap}
.sig{color:var(--accent);font-weight:700}
.toc{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 22px}
.toc a{border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-size:12px}
"""

_NHAN_QD = {"GO": ("VÀO", "go"), "CONDITIONAL": ("VÀO CÓ ĐIỀU KIỆN", ""),
            "NO-GO": ("KHÔNG VÀO", "nogo")}
_HEADLINE = {"GO": "Vào — ngách đạt chuẩn theo trọng số 5 trụ.",
             "CONDITIONAL": "Vào có điều kiện — vào bằng một mũi nhọn, không dàn hàng ngang.",
             "NO-GO": "Không vào — điểm dưới ngưỡng theo trọng số 5 trụ."}
_TRU = [("demand", "Nhu cầu"), ("monetization", "Kiếm tiền"),
        ("crackability", "Độ mở cửa vào"), ("competition", "Phân mảnh cạnh tranh"),
        ("trend", "Xu hướng")]


def build(project_dir: Path) -> Path:
    nd = project_dir / DATA_DIR
    d1 = _doc(nd, "decision1.json")
    d2 = _doc(nd, "decision2.json")
    demand = _doc(nd, "demand.json")
    crack = _doc(nd, "crackability.json")
    money = _doc(nd, "monetization.json")
    an = _doc(nd, "analysis.json")
    gaps = _doc(nd, "gaps.json")
    sub = _doc(nd, "subniche.json")
    bets = (_doc(nd, "bets.json").get("bets")) or []
    kenh = _doc(nd, "channels.json")
    plan = _doc(nd, "execution_plan.json")
    dna = _doc(nd, "dna.json")
    summary_md = ""
    p_sum = project_dir / REPORT_DIR / "SUMMARY.md"
    if p_sum.is_file():
        summary_md = p_sum.read_text(encoding="utf-8", errors="replace")
    # tầng 2 (19/08): NGHĨA do bao_cao_writer [LLM] sinh — có file thì đổ vào slot,
    # không có thì slot giữ nhãn chờ (builder không bịa)
    nghia = _doc(nd, "bao_cao_nghia.json")
    meta_w = nghia.get("_meta") or {}
    nhan_writer = (f"bao_cao_writer [LLM] · {e(meta_w.get('provider') or '?')}"
                   f"{' · ' + e(meta_w.get('model')) if meta_w.get('model') else ''}"
                   f" · {e((meta_w.get('generated') or '')[:16])}")

    qd = d1.get("decision") or "?"
    nhan_qd, lop_qd = _NHAN_QD.get(qd, (qd, ""))
    diem = d1.get("attractiveness")
    ten_du_an = project_dir.name

    # ---------- TỔNG QUAN ----------
    tru = d1.get("pillars") or {}
    thanh_tru = "".join(
        f"<div class='pillar'><span class='ten'>{nhan}</span>"
        f"<span class='thanh'><i style='width:{max(0, min(100, tru.get(ma) or 0))}%'></i></span>"
        f"<span class='diem'>{e(tru.get(ma, '—'))}</span></div>"
        for ma, nhan in _TRU)
    pipeline_hang = [[
        f"{len(kenh) or '—'}", f_vn(an.get("total_videos")), f_vn(demand.get("n_matured")),
        f_vn(an.get("n_winners")), f_vn(an.get("n_early_confirmed")),
        f_vn(gaps.get("total_comments")), f_vn(gaps.get("total_questions")),
        f_so(d1.get("competition_hhi"), 3), f_vn(demand.get("supply_per_month")),
    ]]
    tq = f"""
<section id="tq">
  <span class="chip {lop_qd}">PHÁN QUYẾT — {nhan_qd}{f' · {diem}/100' if diem is not None else ''}</span>
  <h2 style="margin-top:10px">{e((nghia.get('tq') or {}).get('headline') or _HEADLINE.get(qd, qd))}</h2>
  <div class="card">Pipeline: <b>{e(d1.get('gate_reason'))}</b></div>
  {f"<div class='card'><span class='as'>DIỄN GIẢI — {nhan_writer}</span><br>{e(nghia['tq'].get('doan'))}</div>" if nghia.get('tq', {}).get('doan') else ''}
  {lop_so('5 trụ điểm — trọng số ' + e(d1.get('weights')))}
  {thanh_tru}
  {lop_so('Tổng quan số của pipeline')}
  {bang(['Kênh', 'Video quét', 'Trưởng thành', 'Outlier (thắng)', 'Tín hiệu sớm',
         'Comment', 'Câu hỏi', 'HHI', 'Cung/tháng'], pipeline_hang,
        can_phai=set(range(9)))}
</section>"""

    # ---------- P0 — Pool & phạm vi ----------
    ds_kenh = sorted(kenh.values(), key=lambda c: -int(c.get("subs") or 0)) if kenh else []
    hang_kenh = [[e(c.get("title")), f_vn(c.get("subs")), f_vn(c.get("videoCount")),
                  e((c.get("publishedAt") or "")[:10])] for c in ds_kenh]
    p0 = f"""
<section id="p0"><h2>PHASE 0 · Pool &amp; phạm vi</h2>
  {lop_so()}
  <div class="card">Pool resolve <b>{len(kenh) or '—'}</b> kênh · quét <b>{f_vn(an.get('total_videos'))}</b> video
    (thắng {f_vn(an.get('n_winners'))} · thường {f_vn(an.get('n_normal'))} · tín hiệu sớm {f_vn(an.get('n_early_confirmed'))}).
    Nguồn: channels.json · analysis.json.</div>
  {gon(f'Danh sách {len(hang_kenh)} kênh trong pool',
       bang(['Kênh', 'Subs', 'Video', 'Lập kênh'], hang_kenh, {1, 2})) if hang_kenh else thieu('channels.json')}
</section>"""

    # ---------- P1 — Audience & Demand ----------
    med, p90 = demand.get("demand_median_views"), demand.get("reach_p90_views")
    chenh = None
    try:
        chenh = round(float(p90) / float(med))
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    hang_bc = [
        [f"View trung vị video trưởng thành (n={f_vn(demand.get('n_matured'))})",
         f_vn(med), "Mức nền của ngách", "demand.json"],
        ["Top 10% (p90) — mốc video “trúng”", f_vn(p90),
         (f"Chênh {chenh}× trung vị → thị trường ăn theo cú trúng" if chenh and chenh >= 5
          else (f"Chênh {chenh}× trung vị" if chenh else "")), "demand.json"],
        ["Nguồn cung", f"{f_vn(demand.get('supply_per_month'))} video/tháng",
         "Mật độ ra bài của ngách", "demand.json"],
        ["Xu hướng 12 tháng (OX slope, khử tuổi video)",
         f"{e(demand.get('trend'))} ({f_so(demand.get('trend_strength'))})",
         {"FLAT": "Thị trường trưởng thành — giành phần, không đón sóng",
          "RISING": "Sóng đang lên — cửa sổ vào sớm",
          "DECLINING": "Nhu cầu đang co — thận trọng"}.get(demand.get("trend"), ""),
         "demand.json"],
    ]
    cau_hoi = gaps.get("top_questions") or []
    hang_ch = [[f_vn(q.get("like")), e(q.get("q")), e((q.get("video") or "")[:60])]
               for q in cau_hoi]
    theme = gaps.get("themes") or []
    hang_theme = [[e(t.get("theme")), f_vn(t.get("count")), f_so(t.get("pct"), 1) + "%"]
                  for t in theme]
    p1 = f"""
<section id="p1"><h2>PHASE 1 · Audience &amp; Demand</h2>
  {lop_so('Số liệu — demand evidence')}
  {bang(['Bằng chứng', 'Số', 'Đọc ra điều gì', 'Nguồn'], hang_bc, {1})}
  {gon(f'Toàn bộ {len(hang_ch)} câu hỏi khán giả được like nhiều nhất',
       bang(['Like', 'Câu hỏi', 'Dưới video'], hang_ch, {0})) if hang_ch else thieu('gaps.json')}
  {gon(f'{len(hang_theme)} theme comment', bang(['Theme', 'Số câu', '% câu hỏi'], hang_theme, {1, 2})) if hang_theme else ''}
  {lop_nghia('Diễn giải — Audience Profile Canvas')}
  {khoi_canvas(nghia, nhan_writer) or cho_writer('Chân dung 3 nhóm khán giả (Là ai · Jobs-to-be-Done · Pain · Desired outcome · Đang xem thay thế · Ngôn ngữ họ dùng)')}
  {lop_gate('Gate P1 — đủ bằng chứng demand mới sang Phase 2 (ký trên dashboard)')}
</section>"""

    # ---------- P2 — Cạnh tranh & phân mảnh ----------
    ranked = d2.get("ranked") or []
    hang_cum = [[e(r.get("rank")), e(r.get("anchor")), f_vn(r.get("beachhead_score")),
                 f_so(r.get("competition")), f_vn(r.get("size")), f_vn(r.get("n_channels")),
                 f_vn(r.get("n_outliers") or r.get("n_outlier_channels")),
                 f_vn(r.get("sum_excess"))] for r in ranked]
    p2 = f"""
<section id="p2"><h2>PHASE 2 · Cạnh tranh &amp; phân mảnh</h2>
  {lop_so()}
  <div class="card">HHI toàn ngách <b>{f_so(d1.get('competition_hhi'), 3)}</b> trên {f_vn(d1.get('n_channels'))} kênh
    — càng thấp càng phân mảnh (không ai độc quyền). Cụm: {f_vn(sub.get('n_clusters'))} ·
    video gán cụm {f_vn(sub.get('n_assigned'))}/{f_vn(sub.get('n_pool'))}. Nguồn: decision1.json · subniche.json.</div>
  {gon(f'Bảng {len(hang_cum)} cụm sub-niche theo điểm beachhead',
       bang(['#', 'Cụm', 'Điểm', 'Cạnh tranh', 'Video', 'Kênh', 'Outlier', 'Σexcess'],
            hang_cum, {0, 2, 3, 4, 5, 6, 7}), mo=True) if hang_cum else thieu('decision2.json')}
</section>"""

    # ---------- P3 — Positioning ----------
    hang_bet = [[e(b.get("term")), e(b.get("kind")), e(b.get("builder_verdict")),
                 f_so(b.get("lift"), 1) + "×", f_vn(b.get("n_channels")),
                 f_vn(b.get("n_outliers")), f_vn(b.get("sum_excess")),
                 f_so(b.get("concentration")), f_vn(b.get("median_age_days"))]
                for b in bets]
    khoi_plan = ""
    if plan:
        khoi_plan = (f"<div class='card'>Agent <code>plan</code> (LLM pipeline): "
                     f"<b>{e(plan.get('verdict', '(xem JSON)'))}</b></div>"
                     + gon("execution_plan.json (nguyên văn)",
                           f"<pre>{e(json.dumps(plan, ensure_ascii=False, indent=1)[:6000])}</pre>"))
    p3 = f"""
<section id="p3"><h2>PHASE 3 · Positioning</h2>
  {lop_so()}
  <div class="card">Beachhead pipeline chọn: <b>{e(d2.get('decision'))}</b> — {e(d2.get('reason'))}</div>
  {gon(f'{len(hang_bet)} bets — mũi nhọn đặt cược',
       bang(['Term', 'Loại', 'Verdict', 'Lift', 'Kênh', 'Outlier', 'Σexcess', 'Tập trung', 'Tuổi (ngày)'],
            hang_bet, {3, 4, 5, 6, 7, 8}), mo=True) if hang_bet else thieu('bets.json')}
  {lop_nghia('Ba phương án + Anti-positioning')}
  {khoi_plan}
  {khoi_phuong_an(nghia, nhan_writer) or cho_writer('Positioning options A/B/C + Anti-positioning (những điều KHÔNG làm)')}
  {lop_gate('Gate P3 — chốt phương án positioning TRƯỚC khi sản xuất hàng loạt (ký trên dashboard)')}
</section>"""

    # ---------- P4 — Winning Format ----------
    def _mau(ds, n):
        return (ds or [])[:n]
    hang_mo = [[e(m.get("key")), f_vn(m.get("freq")), f_vn(m.get("channels")),
                e((m.get("examples") or [""])[0][:70])] for m in _mau(an.get("openers"), 20)]
    hang_khuon = [[f"<code>{e(m.get('key'))}</code>", f_vn(m.get("freq")),
                   e((m.get("examples") or [""])[0][:70])] for m in _mau(an.get("templates"), 15)]
    hang_caps = [[e(m.get("key")), f_vn(m.get("freq"))] for m in _mau(an.get("emphasis"), 20)]
    lift_gop = []
    for loai, khoa in (("tag", "lift_tags"), ("cụm", "lift_bigrams"), ("từ", "lift_unigrams")):
        for m in (an.get(khoa) or []):
            lift_gop.append((not m.get("sig"), -(m.get("lift") or 0), m, loai))
    lift_gop.sort(key=lambda x: (x[0], x[1]))
    hang_lift = [[e(m.get("key")), loai, f_so(m.get("lift"), 1) + "×",
                  "<span class='sig'>✓ FDR</span>" if m.get("sig") else "·",
                  f_vn(m.get("channels"))] for _, _, m, loai in lift_gop[:25]]
    khoi_dna = ""
    if dna:
        khoi_dna = gon("dna.json — DNA ngách từ 30 transcript (agent LLM pipeline)",
                       f"<pre>{e(json.dumps(dna, ensure_ascii=False, indent=1)[:6000])}</pre>")
    p4 = f"""
<section id="p4"><h2>PHASE 4 · Winning Format</h2>
  {lop_so()}
  {gon(f'{len(hang_mo)} câu mở đầu title thắng', bang(['Mở đầu', 'Lần', 'Kênh', 'Ví dụ'], hang_mo, {1, 2}), mo=True) if hang_mo else thieu('analysis.json')}
  {gon(f'{len(hang_khuon)} khuôn title', bang(['Khuôn', 'Lần', 'Ví dụ'], hang_khuon, {1})) if hang_khuon else ''}
  {gon(f'{len(hang_caps)} từ CAPS nhấn mạnh', bang(['Từ', 'Lần'], hang_caps, {1})) if hang_caps else ''}
  {gon(f'Top {len(hang_lift)} từ/cụm/tag LIFT cao (thắng vs thường)',
       bang(['Từ khóa', 'Loại', 'Lift', 'Kiểm định', 'Kênh'], hang_lift, {2, 4}), mo=True) if hang_lift else ''}
  {lop_nghia('Diễn giải khuôn thắng')}
  {khoi_dna}
  {khoi_muc_list(nghia.get('winning_format'), 'Winning Format tổng hợp', nhan_writer)
   or cho_writer('Winning Format tổng hợp (độ dài · nhịp · hook · thumbnail grammar)')}
</section>"""

    # ---------- P5 — Monetization ----------
    rpm = money.get("rpm_band_usd")
    p5 = f"""
<section id="p5"><h2>PHASE 5 · Monetization</h2>
  {lop_so()}
  {bang(['RPM band (heuristic)', 'Category', 'Tin cậy', 'Runner-up', 'Sponsor density', 'Điểm', 'Verdict'],
        [[f"${rpm[0]}–{rpm[1]}" if isinstance(rpm, list) and len(rpm) == 2 else '—',
          e(money.get('category')), e(money.get('category_confidence')),
          e(', '.join(map(str, money.get('category_runners_up') or [])) or '—'),
          e(money.get('sponsor_density')), e(money.get('score')), e(money.get('verdict'))]],
        {5}) if money else thieu('monetization.json')}
  <div class="card cho">{e(money.get('note') or 'Heuristic — chưa phải doanh thu đo.')}</div>
</section>"""

    # ---------- P6 — Crackability ----------
    p6 = f"""
<section id="p6"><h2>PHASE 6 · Cửa vào (crackability)</h2>
  {lop_so()}
  {bang(['Newcomer rate', 'Kênh "trẻ" ≤ (tháng)', 'Phụ thuộc authority', 'Tính lặp lại khuôn',
         'Median subs', 'Điểm', 'Verdict'],
        [[f_pt(crack.get('newcomer_rate')), e(crack.get('young_months')),
          e(crack.get('authority_dependence')), e(crack.get('pattern_replicability')),
          f_vn(crack.get('median_subs')), e(crack.get('score')), e(crack.get('verdict'))]],
        {0, 4, 5}) if crack else thieu('crackability.json')}
  <div class="card">{e(crack.get('reason') or '')}</div>
</section>"""

    # ---------- P7 — Trend & velocity ----------
    p7 = f"""
<section id="p7"><h2>PHASE 7 · Trend &amp; theo dõi tuần</h2>
  {lop_so()}
  <div class="card">Trend 12 tháng: <b>{e(demand.get('trend'))}</b> ({f_so(demand.get('trend_strength'))})
    · cung {f_vn(demand.get('supply_per_month'))} video/tháng · tín hiệu sớm {f_vn(an.get('n_early_confirmed'))} video.
    Phase 7 là NHỊP TUẦN của team (đánh giá ban đầu ở đây, theo dõi chạy trong tool — chốt 18/08).</div>
  {lop_gate('Gate P7 — lịch theo dõi tuần thuộc vận hành, không chặn phát hành báo cáo')}
</section>"""

    # ---------- P8 — Bets & falsifiers + tổng hợp ----------
    khoi_summary = (gon("SUMMARY.md — agent summary của pipeline (nguyên văn)",
                        f"<pre>{e(summary_md[:12000])}</pre>") if summary_md else "")
    p8 = f"""
<section id="p8"><h2>PHASE 8 · Bets, falsifiers &amp; tổng hợp</h2>
  {lop_so()}
  <div class="card">Đặt cược theo bảng bets Phase 3 (falsifier = điều kiện chứng minh SAI để rút lui sớm).
    Gate ký từng phase nằm TRÊN DASHBOARD (sống qua các lần chạy lại) — báo cáo này là bản đóng băng theo snapshot.</div>
  {khoi_summary}
  {lop_nghia('Tổng hợp chiến lược')}
  {khoi_tong_hop(nghia, nhan_writer) or cho_writer('Bản tổng hợp GO/NO-GO viết liền mạch + điều kiện rút lui')}
</section>"""

    honesty = f"""
<section id="honesty"><h2>Van chống bịa — nguồn từng mục</h2>
  <div class="card">Mọi con số trong báo cáo lấy NGUYÊN từ artifact pipeline
    (decision1/decision2/demand/crackability/monetization/analysis/gaps/subniche/bets/channels
    trong <code>niche-data/</code>); mục thiếu nguồn ghi rõ "nguồn thiếu", không có số thay thế.
    Khối GIẢ ĐỊNH/CHỜ WRITER là tầng NGHĨA chưa sinh — không phải kết luận.
    Khối execution_plan/dna/SUMMARY là artifact LLM pipeline (--llm) nhúng nguyên văn kèm nhãn.</div>
</section>"""

    toc = "".join(f"<a href='#{ma}'>{nhan}</a>" for ma, nhan in [
        ("tq", "Tổng quan"), ("p0", "P0 Pool"), ("p1", "P1 Audience"), ("p2", "P2 Cạnh tranh"),
        ("p3", "P3 Positioning"), ("p4", "P4 Winning Format"), ("p5", "P5 Monetization"),
        ("p6", "P6 Cửa vào"), ("p7", "P7 Trend"), ("p8", "P8 Tổng hợp"), ("honesty", "Nguồn")])

    trang = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(ten_du_an)} — Báo cáo ngách 8 phase</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<div class="eyebrow">Niche Research · OUTLIERY</div>
<h1>{e(ten_du_an)} — Báo cáo ngách 8 phase</h1>
<div class="sub">Bản dựng tự động từ artifact pipeline · {datetime.now().strftime('%d/%m/%Y %H:%M')}
 · tầng SỐ deterministic, tầng NGHĨA chờ bao_cao_writer</div>
<div class="toc">{toc}</div>
{tq}{p0}{p1}{p2}{p3}{p4}{p5}{p6}{p7}{p8}{honesty}
</div></body></html>"""

    ra = project_dir / REPORT_DIR
    ra.mkdir(exist_ok=True)
    dich = ra / TEN_FILE
    tam = ra / (TEN_FILE + ".tmp")
    tam.write_text(trang, encoding="utf-8")
    tam.replace(dich)
    return dich


def main() -> int:
    if len(sys.argv) < 2:
        print("Cach dung: 19_build_bao_cao.py <project_dir>")
        return 2
    project_dir = Path(sys.argv[1])
    if not (project_dir / DATA_DIR).is_dir():
        print(f"KHONG THAY {project_dir / DATA_DIR} — chua chay pipeline?")
        return 2
    dich = build(project_dir)
    print(f"DONE — {dich}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
