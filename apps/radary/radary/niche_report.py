"""Báo cáo ngách TỰ SINH (Phase 6) — đóng gói pipeline `Niche Report` đã kiểm chứng.

User bấm refresh trên tab Báo cáo → quét pool (chạy NỀN, resumable) → OX v3 age-adjusted
+ keyword LIFT/FDR + bảng cược candidate → render markdown ghi đè kv `overview_doc`
(mục ghim đầu tab Báo cáo). Độc lập với radar: KHÔNG ghi vào bảng videos/ticks.
Spec: docs/niche_report_spec.md. Work dir: data/niche/{ws}/ — competitors.txt trong đó
chứa API key (chmod 600, data/ vốn không commit).
"""
import json, os, subprocess, sys, threading, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from . import db, llm
from .scan import DATA

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'niche')
STEP_TIMEOUT = 1200        # giây/lượt subprocess; scan lưu state từng trang nên timeout không mất dữ liệu
_threads = {}              # ws -> Thread (guard: 1 lượt chạy / workspace / process)


def status(conn, ws):
    return db.kv_get(conn, ws, 'niche_report_status', None)


def start(ws):
    """Khởi động chạy nền. False nếu workspace này đang có lượt chạy."""
    t = _threads.get(ws)
    if t and t.is_alive(): return False
    t = threading.Thread(target=_run, args=(ws,), daemon=True, name=f'niche-report-{ws}')
    _threads[ws] = t; t.start()
    return True


def _set(conn, ws, st):
    with conn: db.kv_set(conn, ws, 'niche_report_status', st)


def _run(ws):
    conn = db.connect()
    try:
        _set(conn, ws, {'state': 'running', 'step': 'chuẩn bị', 'ts': time.time()})
        keys = db.api_keys(conn, ws)
        chans = [r['yt_id'] for r in conn.execute(
            'SELECT yt_id FROM channels WHERE workspace_id=? AND active=1', (ws,))]
        name = conn.execute('SELECT name FROM workspaces WHERE id=?', (ws,)).fetchone()['name']
        work = os.path.join(DATA, 'niche', str(ws)); os.makedirs(work, exist_ok=True)
        for f in os.listdir(work):     # báo cáo định kỳ = chụp mới toàn bộ, không incremental
            os.remove(os.path.join(work, f))
        comp = os.path.join(work, 'competitors.txt')
        open(comp, 'w', encoding='utf-8').write('\n'.join(keys) + '\n' + '\n'.join(chans) + '\n')
        os.chmod(comp, 0o600)

        def step(script, args, label):
            _set(conn, ws, {'state': 'running', 'step': label, 'ts': time.time()})
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + args,
                               capture_output=True, text=True, timeout=STEP_TIMEOUT)
            if r.returncode != 0:
                raise RuntimeError(f'{script} lỗi: {(r.stderr or r.stdout)[-300:]}')
            return r.stdout

        for i in range(40):            # scan resumable — lặp đến khi in DONE
            try:
                out = step('1_scan.py', [comp, work], f'quét pool (lượt {i + 1})')
            except subprocess.TimeoutExpired:
                continue               # state đã lưu từng trang — lượt kế chạy tiếp
            if 'DONE' in out: break
        else:
            raise RuntimeError('quét không xong sau 40 lượt — pool quá lớn hoặc mạng/quota kẹt')
        videos = json.load(open(os.path.join(work, 'videos.json'), encoding='utf-8'))
        chinfo = json.load(open(os.path.join(work, 'channels.json'), encoding='utf-8'))
        if not videos:
            raise RuntimeError(f'quét được 0 video ({len(chinfo)} kênh resolve được) — kiểm tra API key/quota')
        step('2_keywords.py', [work], 'phân tích keyword + outlier LIFT')
        step('5_synthesize_bets.py', [work], 'tổng hợp bảng cược')
        md = render_md(work, name)
        # Phase 7: lớp tường thuật AI — chỉ khi org có cấu hình LLM; lỗi thì báo cáo thuần số vẫn ra
        note = ''
        org = conn.execute('SELECT org_id FROM workspaces WHERE id=?', (ws,)).fetchone()['org_id']
        lcfg = llm.org_llm(conn, org)
        if lcfg:
            _set(conn, ws, {'state': 'running', 'step': f"viết tường thuật ({lcfg['provider']})", 'ts': time.time()})
            try:
                nar = llm.report_narrative(lcfg, md)
                L = md.split('\n')
                i = next((k for k, ln in enumerate(L) if ln.startswith('## ')), len(L))
                L[i:i] = ['## Tóm tắt điều hành',
                          f"*(AI {lcfg['provider']}/{lcfg['model']} diễn giải — mọi số liệu gốc nằm ở các bảng bên dưới)*",
                          '', nar, '']
                md = '\n'.join(L)
            except Exception as e:
                note = f'tường thuật AI lỗi (báo cáo vẫn đủ bảng số): {str(e)[:150]}'
        with conn:
            db.kv_set(conn, ws, 'overview_doc', md)
            db.kv_set(conn, ws, 'niche_report_status',
                      {'state': 'done', 'ts': time.time(), 'videos': len(videos), 'channels': len(chinfo),
                       **({'note': note} if note else {})})
    except Exception as e:
        _set(conn, ws, {'state': 'error', 'ts': time.time(), 'error': str(e)[:300]})
    finally:
        conn.close()


def render_md(work, ws_name):
    """JSON work-dir → markdown tường thuật. Phủ 3.1 / 3.2 / 3.9 / 3.10 của spec;
    hạng mục chưa làm được in rõ trong 'Giới hạn dữ liệu' — không overclaim."""
    from .niche._common import compute_outliers
    P = lambda f: os.path.join(work, f)
    videos = json.load(open(P('videos.json'), encoding='utf-8'))
    chinfo = json.load(open(P('channels.json'), encoding='utf-8'))
    ana = json.load(open(P('analysis.json'), encoding='utf-8'))
    bets = json.load(open(P('bets.json'), encoding='utf-8'))
    now = datetime.now(timezone.utc)
    compute_outliers(videos, now)
    cell = lambda s: (s or '').replace('|', '∣')   # title/kênh không được phá bảng md

    per_q, fmt_q = Counter(), defaultdict(Counter)
    per_ch = defaultdict(lambda: {'n': 0, 'views': 0})
    for x in videos:
        c = per_ch[x.get('channelTitle') or x.get('channelId')]
        c['n'] += 1; c['views'] += x['viewCount']
        pa = x.get('publishedAt') or ''
        if len(pa) >= 7:
            q = f"{pa[:4]}-Q{(int(pa[5:7]) - 1) // 3 + 1}"
            per_q[q] += 1; fmt_q[q][x['fmt']] += 1
    quarters = sorted(per_q)[-8:]
    top_ch = sorted(per_ch.items(), key=lambda t: -t[1]['views'])[:10]
    outs = sorted((x for x in videos if x.get('valid') and x['ox'] >= 3), key=lambda x: -x['ox'])

    L = [f"# BÁO CÁO NGÁCH (tự sinh) — {ws_name}", '',
         f"*Sinh {now.strftime('%Y-%m-%d %H:%M')} UTC · {len(chinfo)} kênh · {len(videos):,} video "
         f"(tối đa 300 video gần nhất/kênh) · OUTLIER MODEL v3 age-adjusted*", '',
         '## Giới hạn dữ liệu (đọc trước khi tin số)',
         '- Views là SNAPSHOT lúc quét, không phải quỹ đạo — mô hình đã age-adjust nhưng video rất mới vẫn thiệt.',
         '- Survivorship: video/kênh đã xóa không đo được; tầm quét = đúng pool đối thủ đã nhập, không rộng hơn.',
         '- Hạng mục 3.3-3.8 của spec (theme matrix, vòng đời, adopter, HHI theme, comment, burst half-life) CHƯA có trong v1.',
         '- Bảng cược cuối là CANDIDATE theo luật cứng (chưa qua vòng Auditor) — dùng như shortlist, không phải quyết định.', '',
         '## 3.1 Cấu trúc niche', '',
         '| Quý | Video đăng | Short | Mid | Long |', '|---|---|---|---|---|']
    for q in quarters:
        L.append(f"| {q} | {per_q[q]} | {fmt_q[q].get('Short', 0)} | {fmt_q[q].get('Mid', 0)} | {fmt_q[q].get('Long', 0)} |")
    L += ['', '**Top kênh theo tổng views trong tầm quét:**', '',
          '| Kênh | Video | Tổng views |', '|---|---|---|']
    for nm, d in top_ch:
        L.append(f"| {cell(nm)[:24]} | {d['n']} | {d['views']:,} |")
    L += ['', f"## 3.2 Outlier age-adjusted (OX v3) — {len(outs)} video hợp lệ đạt ≥3×", '',
          '| OX | Bracket | Views | Excess | Tuổi | Tin cậy | Kênh | Video |', '|---|---|---|---|---|---|---|---|']
    for x in outs[:20]:
        L.append(f"| {x['ox']} | {x['bracket']} | {x['viewCount']:,} | {x['excess']:,} | {int(x['age'])}d "
                 f"| {x['confidence']} | {cell(x.get('channelTitle'))[:16]} "
                 f"| [{cell(x.get('title'))[:50]}](https://youtu.be/{x['videoId']}) |")
    if not outs:
        L.append('| — | *chưa có outlier hợp lệ (pool nhỏ hoặc baseline chưa đủ 8 video/kênh/format)* | | | | | | |')
    sig = [r for r in ana.get('lift_bigrams', []) if r.get('sig')][:12] + \
          [r for r in ana.get('lift_unigrams', []) if r.get('sig')][:12]
    L += ['', '## 3.9 Packaging — keyword LIFT (over-index trong outlier, kiểm định FDR q=0.10)', '']
    if sig:
        L += ['| Cụm từ | Lift | Trong outlier | Ngoài | Số kênh |', '|---|---|---|---|---|']
        L += [f"| {cell(r['key'])} | {r['lift']}× | {r['out']} | {r['non']} | {r['channels']} |" for r in sig]
    else:
        L.append('*Chưa keyword nào qua kiểm định FDR — corpus còn nhỏ hoặc outlier quá ít.*')
    tpl = ana.get('templates', [])[:8]
    if tpl:
        L += ['', '**Title template phổ biến:**', '', '| Template | Số video | Số kênh |', '|---|---|---|']
        L += [f"| {cell(r['key'])[:60]} | {r['freq']} | {r['channels']} |" for r in tpl]
    L += ['', f"## 3.10 BẢNG CƯỢC — {bets.get('n_candidates', 0)} candidate (luật cứng, chưa qua Auditor)", '']
    for b in bets.get('bets', [])[:15]:
        ev = ' · '.join(f"{cell(e.get('channel'))}: “{cell(e.get('title'))[:40]}” ({e.get('ox')}×)"
                        for e in b.get('evidence', [])[:2])
        L += [f"**[{b['builder_verdict']}] {b['term']}** — lift {b['lift']}× · {b['n_channels']} kênh · "
              f"Σexcess {b['sum_excess']:,} · tuổi trung vị {b['median_age_days']}d",
              f"- Căn cứ: {ev}",
              f"- ĐIỀU KIỆN SAI: {b['falsifier']}", '']
    if not bets.get('bets'):
        L.append('*Chưa đủ tín hiệu để ra cược — thêm đối thủ vào pool rồi bấm refresh lại.*')
    return '\n'.join(L)
