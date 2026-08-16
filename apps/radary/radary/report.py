"""Tầng trình bày: board markdown + alerts.log + báo cáo tuần, theo workspace.

Format board giữ NGUYÊN bản cũ (radar_board.md) — vừa để user đọc quen mắt,
vừa để verify_phase1 so parity từng dòng. Output: data/reports/{ws}/.
Phase 3 sẽ thêm renderer JSON cho dashboard React — dữ liệu gốc đã nằm trong DB.
"""
import json, os, re
from datetime import datetime
from . import core, db, series
from .scan import DATA

def report_dir(ws):
    d = os.path.join(DATA, 'reports', str(ws)); os.makedirs(d, exist_ok=True); return d

def fmt_ts(ts, tz): return datetime.fromtimestamp(ts, tz).strftime('%Y-%m-%d %H:%M')

def board_lines(V, cfg, metrics, jobs, api_used, pushes_today, now, tz):
    L = [f"# RADAR BOARD — {fmt_ts(now, tz)}  (heartbeat)", '',
         f"Quota dùng lần chạy này: ~{api_used} units | Push T2 hôm nay: {pushes_today['t2']}/{cfg['T2_daily_cap']} | ntfy: {'BẬT' if cfg.get('ntfy_enabled') else 'TẮT (log-only)'}", '']
    by_cohort = {}
    for vid, m in metrics.items(): by_cohort.setdefault(m['cohort'], []).append((vid, m))
    for d in sorted(by_cohort):
        rowsx = sorted(by_cohort[d], key=lambda t: t[1]['rank'])[:12]
        L.append(f"## Cohort D{d}  ({len(by_cohort[d])} video)")
        L.append('| # | Bậc | VPH | VPD | Views | Tuổi | Kênh | Video |')
        L.append('|---|---|---|---|---|---|---|---|')
        for vid, m in rowsx:
            v = V[vid]; tier = ['—', 'T1', 'T2', 'T3', 'T4'][v['tier']]
            est = '~' if m['est'] else ''
            L.append(f"| {m['rank']} | {tier} | {est}{m['vph']:,.0f} | {m['vpd']:,.0f} | {core.latest_views(v):,} | "
                     f"{core.age_h(v, now)/24:.1f}d | {v['ch'][:18]} | [{v['title'][:55]}](https://youtu.be/{vid}) |")
        L.append('')
    # VPD cao mọi tuổi
    olds = _allages(V, cfg, now)
    L.append(f"## VPD CAO MỌI TUỔI (≥{cfg['allages_vpd_floor']:,}/ngày — 'còn VPD là còn đáng làm')")
    L.append('| VPD | Views | Tuổi | Kênh | Video |'); L.append('|---|---|---|---|---|')
    for vid, v, vpd, est in olds[:15]:
        L.append(f"| {'~' if est else ''}{vpd:,.0f} | {core.latest_views(v):,} | {core.age_h(v, now)/24:.0f}d | {v['ch'][:18]} | [{v['title'][:55]}](https://youtu.be/{vid}) |")
    L.append('')
    nx = {k: fmt_ts(jobs.get(k, 0), tz) for k in ('discover', 'hot', 'd01', 'd26', 'allages', 'weekly')}
    L.append(f"*Lịch kế tiếp: discover {nx['discover']} · hot {nx['hot']} · D0-1 {nx['d01']} · D2-6 {nx['d26']} · all-ages {nx['allages']} · weekly {nx['weekly']}*")
    return L

def _allages(V, cfg, now):
    olds = []
    for vid, v in V.items():
        if v['dead'] or (v['dur'] or 999) <= cfg['min_duration_s'] or core.age_h(v, now) < 168 or len(v['ticks']) < 2: continue
        vpd, est = core.calc_vpd(v, now)
        if vpd >= cfg['allages_vpd_floor']: olds.append((vid, v, vpd, est))
    olds.sort(key=lambda t: -t[2])
    return olds

def board_data(V, cfg, metrics, jobs, api_used, pushes_today, now):
    """HỢP ĐỒNG DỮ LIỆU cho dashboard (Phase 3): board dạng JSON, lưu vào kv sau mỗi chu kỳ.
    Khác board md: không cắt 12 dòng/cohort — UI tự quyết hiển thị bao nhiêu."""
    by_cohort = {}
    for vid, m in metrics.items(): by_cohort.setdefault(m['cohort'], []).append((vid, m))
    cohorts = []
    for d in sorted(by_cohort):
        rows = []
        for vid, m in sorted(by_cohort[d], key=lambda t: t[1]['rank']):
            v = V[vid]
            rows.append({'yt_id': vid, 'title': v['title'], 'channel': v['ch'], 'ch_id': v.get('chId', ''),
                         'tier': v['tier'],
                         'vph': round(m['vph'], 1), 'vpd': round(m['vpd'], 1), 'est': bool(m['est']),
                         'est_vpd': bool(m.get('est_vpd')),      # VPD = vph×24 kỳ vọng — UI gắn dấu ~
                         'views': core.latest_views(v), 'age_h': round(core.age_h(v, now), 1),
                         'rank': m['rank'], 'url': f'https://youtu.be/{vid}'})
        cohorts.append({'day': d, 'size': len(rows), 'videos': rows})
    allages = [{'yt_id': vid, 'title': v['title'], 'channel': v['ch'], 'ch_id': v.get('chId', ''),
                'vpd': round(vpd, 1),
                'est': bool(est), 'views': core.latest_views(v), 'age_d': round(core.age_h(v, now)/24, 1),
                'url': f'https://youtu.be/{vid}'} for vid, v, vpd, est in _allages(V, cfg, now)]
    return {'generated_ts': now, 'quota_used': api_used,
            'push_t2_today': pushes_today['t2'], 'push_t2_cap': cfg['T2_daily_cap'],
            'ntfy_enabled': bool(cfg.get('ntfy_enabled')), 'cohorts': cohorts,
            'allages': allages, 'jobs': jobs}

def render_board(conn, ws, V, cfg, metrics, jobs, api_used, pushes_today, now):
    tz = core.tzinfo(conn.execute('SELECT tz FROM workspaces WHERE id=?', (ws,)).fetchone()['tz'])
    L = board_lines(V, cfg, metrics, jobs, api_used, pushes_today, now, tz)
    open(os.path.join(report_dir(ws), 'radar_board.md'), 'w').write('\n'.join(L))

def append_alerts(ws, events, tz=None):
    if not events: return
    tz = tz or core.tzinfo()
    with open(os.path.join(report_dir(ws), 'alerts.log'), 'a') as f:
        for e in events:
            f.write(f"{fmt_ts(e['ts'], tz)} | T{e['from']}→T{e['to']} | VPH {e['vph']:,} | VPD {e['vpd']:,} | views {e['views']:,} | "
                    f"{e['age_h']/24:.1f}d | rank{e['rank']}/D{e['cohort']} | {e['ch'][:20]} | {e['title'][:60]} | "
                    f"{'PUSHED' if e['pushed'] else e['note']} | https://youtu.be/{e['vid']}\n")

# ---------------- đồ thị SVG cho báo cáo (thuần stdlib, nhúng data-URI, in được nền trắng) ----------------
def _xml(s):
    return (str(s or '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def _svg_md(alt, svg):
    import base64
    return f'![{alt}](data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode() + ')'

def _fmt_v(v, unit):
    return f'{v:.1f}%' if unit == '%' else (f'{v/1e6:.1f}M' if v >= 1e6 else f'{v/1e3:.0f}K' if v >= 1e3 else f'{v:,.0f}')

def _chart_hbar(title, rows, unit=''):
    """rows: [(label, value)] sort giảm dần → thanh ngang.
    Style Tremor/shadcn-charts (lệnh user 22/07/2026): track mờ nền + thanh gradient, nền trắng in được."""
    if not rows: return None
    W, bh, gap, top, left = 660, 22, 8, 40, 195
    H = top + len(rows) * (bh + gap) + 12
    mx = max(v for _, v in rows) or 1
    track_w = W - left - 80
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif">',
         '<defs><linearGradient id="gb" x1="0" y1="0" x2="1" y2="0">'
         '<stop offset="0%" stop-color="#2a78d6"/><stop offset="100%" stop-color="#63a1e8"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff" stroke="#e5e7eb" rx="10"/>',
         f'<text x="14" y="24" font-size="13" font-weight="700" fill="#111827">{_xml(title)}</text>']
    for i, (lab, v) in enumerate(rows):
        y = top + i * (bh + gap)
        w = max(track_w * v / mx, 2)
        p.append(f'<text x="{left-8}" y="{y+15}" font-size="11" fill="#4b5563" text-anchor="end">{_xml(str(lab)[:28])}</text>')
        p.append(f'<rect x="{left}" y="{y}" width="{track_w}" height="{bh}" fill="#f3f4f6" rx="5"/>')
        p.append(f'<rect x="{left}" y="{y}" width="{w:.0f}" height="{bh}" fill="url(#gb)" rx="5"/>')
        p.append(f'<text x="{left+w+7:.0f}" y="{y+15}" font-size="11" font-weight="600" fill="#374151">{_fmt_v(v, unit)}</text>')
    p.append('</svg>')
    return ''.join(p)

def _chart_cols(title, rows):
    """rows: [(label, value)] theo thứ tự thời gian → cột dọc.
    Style Tremor/shadcn-charts: grid ngang chấm mảnh + cột gradient dọc, nền trắng in được."""
    if not rows: return None
    W, H, top, bottom, left = 660, 240, 40, 30, 24
    plot_w, plot_h = W - left - 20, H - top - bottom
    mx = max(v for _, v in rows) or 1
    cw = plot_w / len(rows)
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif">',
         '<defs><linearGradient id="gc" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0%" stop-color="#2a78d6"/><stop offset="100%" stop-color="#7db3ea"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff" stroke="#e5e7eb" rx="10"/>',
         f'<text x="14" y="24" font-size="13" font-weight="700" fill="#111827">{_xml(title)}</text>']
    for fr in (0.25, 0.5, 0.75, 1.0):
        gy = H - bottom - plot_h * fr
        p.append(f'<line x1="{left}" y1="{gy:.0f}" x2="{W-16}" y2="{gy:.0f}" stroke="#e5e7eb" stroke-dasharray="3 4"/>')
    p.append(f'<line x1="{left}" y1="{H-bottom}" x2="{W-16}" y2="{H-bottom}" stroke="#d1d5db"/>')
    for i, (lab, v) in enumerate(rows):
        bw = cw * 0.62
        x = left + i * cw + (cw - bw) / 2
        h = plot_h * v / mx
        y = H - bottom - h
        p.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{max(h,1):.0f}" fill="url(#gc)" rx="{min(4.0, max(h,1)/2):.0f}"/>')
        p.append(f'<text x="{x+bw/2:.0f}" y="{y-5:.0f}" font-size="10" font-weight="600" fill="#374151" text-anchor="middle">{_fmt_v(v, "")}</text>')
        p.append(f'<text x="{x+bw/2:.0f}" y="{H-bottom+16:.0f}" font-size="10" fill="#6b7280" text-anchor="middle">{_xml(lab)}</text>')
    p.append('</svg>')
    return ''.join(p)

def render_weekly(conn, ws, V, cfg, tz):
    """Báo cáo tuần 7 phần (nâng cấp theo lệnh user 12/07/2026): diễn biến tuần qua
    (so tuần trước, theo ngày, kênh tạo sóng) + tiềm năng tuần mới (sóng đang chạy,
    ứng viên chớm nở kèm xu hướng). Trả về path file — mục Nhận định AI chèn sau (nền)."""
    import time
    now = time.time()
    cell = lambda s: (s or '').replace('|', '∣')
    ARROW = {'up': '↗ tăng tốc', 'flat': '→ đi ngang', 'down': '↘ hạ nhiệt'}

    def tier_events(a, b):
        out = []
        for r in conn.execute("SELECT ts, video_yt_id, payload FROM events WHERE workspace_id=? "
                              "AND kind='tier' AND ts>=? AND ts<?", (ws, a, b)):
            e = json.loads(r['payload']); e['ts'] = r['ts']; e['vid'] = r['video_yt_id']; out.append(e)
        return out
    week = tier_events(now - 7*86400, now + 1)
    prev = tier_events(now - 14*86400, now - 7*86400)
    ups = [e for e in week if e.get('to', 0) >= 2 and e.get('to', 0) > e.get('from', 0)]
    prev_ups = [e for e in prev if e.get('to', 0) >= 2 and e.get('to', 0) > e.get('from', 0)]
    cyc = [json.loads(r['payload']) for r in conn.execute(
        'SELECT payload FROM cycles WHERE workspace_id=? AND ts>=?', (ws, now - 7*86400))]
    cyc_prev = [json.loads(r['payload']) for r in conn.execute(
        'SELECT payload FROM cycles WHERE workspace_id=? AND ts>=? AND ts<?', (ws, now - 14*86400, now - 7*86400))]
    pool_n = conn.execute('SELECT COUNT(*) FROM channels WHERE workspace_id=? AND active=1', (ws,)).fetchone()[0]
    d = lambda cur, old: f"**{cur:,}** ({'+' if cur - old >= 0 else ''}{cur - old:,})"

    L = [f"# BÁO CÁO TUẦN — {datetime.now(tz).strftime('%Y-%m-%d')} 08:00", '',
         f"*Kỳ {fmt_ts(now - 7*86400, tz)[:10]} → {fmt_ts(now, tz)[:10]} · pool {pool_n} kênh · trong ngoặc = chênh với tuần trước*", '',
         '## 1. Nhịp tuần qua',
         '| Chỉ số | Tuần này (so tuần trước) |', '|---|---|',
         f"| Sự kiện thăng/hạ bậc | {d(len(week), len(prev))} |",
         f"| Sóng T2+ mới | {d(len(ups), len(prev_ups))} |",
         f"| Push ra điện thoại | {d(sum(1 for e in week if e.get('pushed')), sum(1 for e in prev if e.get('pushed')))} |",
         f"| Video mới vào radar | {d(sum(c.get('new_videos', 0) for c in cyc), sum(c.get('new_videos', 0) for c in cyc_prev))} |",
         f"| Quota đã dùng | {d(sum(c.get('quota', 0) for c in cyc), sum(c.get('quota', 0) for c in cyc_prev))} |"]

    # tăng trưởng views trong tuần: delta giữa các tick, gom theo ngày (địa phương) và theo kênh
    day_growth, ch_growth = {}, {}
    wstart = now - 7*86400
    for vid, v in V.items():
        tk = v['ticks']
        for i in range(1, len(tk)):
            t, val = tk[i]
            if t < wstart: continue
            dlt = max(val - tk[i-1][1], 0)
            if not dlt: continue
            dt = datetime.fromtimestamp(t, tz)
            day_growth.setdefault(dt.strftime('%d/%m'), [dt.timestamp(), 0])
            day_growth[dt.strftime('%d/%m')][1] += dlt
            ch_growth[v['ch']] = ch_growth.get(v['ch'], 0) + dlt

    days = {}
    for e in week:
        key = datetime.fromtimestamp(e['ts'], tz).strftime('%a %d/%m')
        b = days.setdefault(key, {'ev': 0, 'up': 0, 'ts': e['ts']})
        b['ev'] += 1
        if e.get('to', 0) >= 2 and e.get('to', 0) > e.get('from', 0): b['up'] += 1
    L += ['', '## 2. Diễn biến theo ngày', '| Ngày | Sự kiện bậc | Sóng T2+ mới |', '|---|---|---|']
    L += [f"| {k} | {b['ev']} | {b['up'] or '—'} |" for k, b in sorted(days.items(), key=lambda kv: kv[1]['ts'])]
    day_rows = [(k, val) for k, (ts_, val) in sorted(day_growth.items(), key=lambda kv: kv[1][0])]
    svg = _chart_cols('Tăng trưởng pool — views cộng thêm mỗi ngày (toàn bộ video đang theo dõi)', day_rows)
    if svg: L += ['', _svg_md('Tăng trưởng pool theo ngày', svg)]

    L += ['', '## 3. Sổ cái sóng T2+ (số phận đến sáng nay)', '',
          '| Ngày | Bậc | Video | Kênh | VPH lúc alert | Views lúc alert | Views hiện tại | Kết cục |',
          '|---|---|---|---|---|---|---|---|']
    for e in sorted(ups, key=lambda x: -x.get('vph', 0)):
        v = V.get(e['vid'], {})
        cur = core.latest_views(v) if v else 0
        grew = cur / max(e.get('views', 1), 1)
        verdict = 'SÓNG THẬT' if cur >= 300000 or grew >= 3 else ('đang chạy' if grew >= 1.3 else 'xẹp')
        L.append(f"| {fmt_ts(e['ts'], tz)[:10]} | T{e['to']} | {cell(e.get('title', ''))[:45]} | {cell(e.get('ch', ''))[:16]} "
                 f"| {e.get('vph', 0):,} | {e.get('views', 0):,} | {cur:,} | {verdict} |")

    by_ch = {}
    for e in ups:
        b = by_ch.setdefault(e.get('ch', '?'), {'n': 0, 'peak': 0})
        b['n'] += 1; b['peak'] = max(b['peak'], e.get('vph', 0))
    if by_ch:
        L += ['', '## 4. Kênh tạo sóng của tuần', '| Kênh | Sóng T2+ | VPH đỉnh |', '|---|---|---|']
        L += [f"| {cell(ch)[:22]} | {b['n']} | {b['peak']:,} |"
              for ch, b in sorted(by_ch.items(), key=lambda kv: (-kv[1]['n'], -kv[1]['peak']))[:8]]
    total_g = sum(ch_growth.values())
    if total_g > 0:
        top_ch_g = sorted(ch_growth.items(), key=lambda kv: -kv[1])
        share = [(ch, v * 100.0 / total_g) for ch, v in top_ch_g[:7]]
        rest = 100.0 - sum(s for _, s in share)
        if rest > 0.5: share.append(('(các kênh còn lại)', rest))
        svg = _chart_hbar(f'Thị phần tuần — % views cộng thêm theo kênh (tổng {_fmt_v(total_g, "")} views)', share, '%')
        if svg: L += ['', _svg_md('Thị phần tăng trưởng tuần theo kênh', svg)]
        svg = _chart_hbar('Kênh tăng trưởng mạnh nhất tuần — views cộng thêm', top_ch_g[:8])
        if svg: L += ['', _svg_md('Kênh tăng trưởng mạnh nhất', svg)]

    # ---- tiềm năng tuần mới ----
    carry = []
    for vid, v in V.items():
        if v['dead'] or v['tier'] < 2: continue
        s = series.vph_series(v['ticks'], v['pub'])
        t = series.trend(s)
        carry.append((vid, v, s[-1][1] if s else 0, t['dir']))
    carry.sort(key=lambda x: -x[2])
    L += ['', '## 5. Mang sang tuần mới — sóng đang chạy (T2+ còn sống)']
    if carry:
        L += ['| Bậc | Video | Kênh | VPH hiện tại | Xu hướng | Views |', '|---|---|---|---|---|---|']
        L += [f"| T{v['tier']} | [{cell(v['title'])[:42]}](https://youtu.be/{vid}) | {cell(v['ch'])[:16]} "
              f"| {vph:,.0f} | {ARROW.get(tr, tr)} | {core.latest_views(v):,} |" for vid, v, vph, tr in carry[:10]]
    else:
        L.append('*Không có sóng T2+ nào còn sống — tuần mới bắt đầu từ nền phẳng.*')

    cands = []
    for vid, v in V.items():
        if v['dead'] or v['tier'] != 1 or core.age_h(v, now) >= 72: continue
        s = series.vph_series(v['ticks'], v['pub'])
        t = series.trend(s)
        if t['dir'] == 'up':
            cands.append((vid, v, s[-1][1] if s else 0, t.get('pct', 0)))
    cands.sort(key=lambda x: -x[2])
    L += ['', '## 6. Ứng viên chớm nở (T1 dưới 72h tuổi, VPH đang tăng — dễ lên T2 đầu tuần)']
    if cands:
        L += ['| Video | Kênh | VPH hiện tại | Đà tăng | Tuổi |', '|---|---|---|---|---|']
        L += [f"| [{cell(v['title'])[:42]}](https://youtu.be/{vid}) | {cell(v['ch'])[:16]} "
              f"| {vph:,.0f} | +{pct*100:.0f}% | {core.age_h(v, now)/24:.1f}d |" for vid, v, vph, pct in cands[:8]]
    else:
        L.append('*Chưa có ứng viên nào đủ điều kiện lúc chốt báo cáo.*')

    vphs = sorted([e.get('vph', 0) for e in week if e.get('vph', 0) > 0])
    if vphs:
        L += ['', f"## 7. Hiệu chỉnh sàn — phân phối VPH sự kiện tuần: P50={vphs[len(vphs)//2]:,} · P90={vphs[int(len(vphs)*.9)]:,}",
              f"Sàn hiện tại: T1={cfg['T1_vph']} T2={cfg['T2_vph']} T3={cfg['T3_vph']} T4={cfg['T4_vph']} — cân nhắc chỉnh nếu P90 lệch xa (≥2 tuần dữ liệu mới đáng tin)."]
    L += ['', '*Giới hạn: "kết cục" dựa trên snapshot views lúc chốt; radar báo sóng — thẩm định và quyết định thuộc về người.*']
    wk = os.path.join(report_dir(ws), 'weekly'); os.makedirs(wk, exist_ok=True)
    path = os.path.join(wk, datetime.now(tz).strftime('%Y-%m-%d') + '.md')
    open(path, 'w').write('\n'.join(L))
    return path

def spawn_weekly_narrative(ws, path):
    """Chèn mục 'Nhận định AI' vào báo cáo tuần — chạy NỀN, lỗi/thiếu key thì bỏ qua êm."""
    import threading
    threading.Thread(target=_weekly_narrative, args=(ws, path), daemon=True,
                     name=f'weekly-ai-{ws}').start()

def _weekly_narrative(ws, path):
    try:
        from . import llm
        conn = db.connect()
        org = conn.execute('SELECT org_id FROM workspaces WHERE id=?', (ws,)).fetchone()['org_id']
        lcfg = llm.org_llm(conn, org)
        conn.close()
        if not lcfg: return
        md = open(path).read()
        if '## Nhận định AI' in md: return
        user = (md[:20000] + '\n\nDựa DUY NHẤT trên báo cáo trên, viết mục "Nhận định AI" gồm: '
                '(a) **Diễn biến tuần qua** — 3-5 gạch đầu dòng: nhịp sóng so tuần trước, kênh/chủ đề nổi bật, '
                'điểm bất thường nếu có; (b) **Tiềm năng tuần mới** — 2-4 gạch đầu dòng dựa trên mục 5 và 6 '
                '(sóng còn động lượng nào, ứng viên nào đáng để mắt), KHÔNG khuyên "nên đánh"; '
                '(c) chốt 1 dòng "nhận định này sai khi nào". Mọi số phải trích từ báo cáo.')
        text = llm.complete(lcfg, llm.NARRATIVE_SYSTEM, user, max_tokens=1200, timeout=180)
        L = md.split('\n')
        i = next((k for k, ln in enumerate(L) if ln.startswith('## ')), len(L))
        L[i:i] = ['## Nhận định AI', f"*(AI {lcfg['provider']}/{lcfg['model']} — chỉ diễn giải số trong báo cáo)*",
                  '', text, '']
        open(path, 'w').write('\n'.join(L))
    except Exception:
        pass

# ---------------- tab Báo cáo (roadmap Phase 5) ----------------
# Tổng quan ngách = TÀI LIỆU user đưa vào (kiểu niche_analytics.md), lưu kv 'overview_doc',
# GHIM trên đầu danh sách vĩnh viễn (điều chỉnh user 08/07/2026 — không sinh từ data tươi,
# số liệu tươi đã có ở Cài đặt → Căn cứ hiệu chỉnh). Báo cáo tuần xếp dưới, mới nhất trước.
WEEKLY_ID = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def list_reports(conn, ws):
    wk = os.path.join(report_dir(ws), 'weekly')
    files = os.listdir(wk) if os.path.isdir(wk) else []
    weeks = sorted((f[:-3] for f in files if f.endswith('.md') and WEEKLY_ID.match(f[:-3])), reverse=True)
    items = [{'id': 'overview', 'kind': 'overview', 'title': 'Tổng quan ngách', 'date': '',
              'pinned': True, 'empty': not db.kv_get(conn, ws, 'overview_doc', '')}]
    items += [{'id': d, 'kind': 'weekly', 'title': f'Báo cáo tuần {d}', 'date': d,
               'pinned': False, 'empty': False} for d in weeks]
    return items

def read_report(conn, ws, rid):
    """Nội dung 1 báo cáo theo id whitelist — không nhận path tùy ý. None = không tồn tại."""
    if rid == 'overview':
        return {'id': 'overview', 'kind': 'overview', 'md': db.kv_get(conn, ws, 'overview_doc', '')}
    if WEEKLY_ID.match(rid):
        p = os.path.join(report_dir(ws), 'weekly', rid + '.md')
        if os.path.isfile(p):
            return {'id': rid, 'kind': 'weekly', 'md': open(p).read()}
    return None
