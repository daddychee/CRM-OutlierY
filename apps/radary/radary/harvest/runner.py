"""Job nền Harvest — 1 job hiện hành/org: resolve → đo → phân loại / snowball → report.

Checkpoint JSON trong harvest_jobs.checkpoint (resumable), PAUSE khi hết quota (RuntimeError
từ scan.API) hoặc cạn RADAR_BUDGET giây. Read-only tuyệt đối với bảng sống — chỉ ghi harvest_*.
"""
import json, os, re, threading, time
from . import audience, decompose, snowball
from . import fingerprint as fp
from .. import db
from ..scan import API

_threads = {}                      # org -> Thread (1 lượt chạy/org/process)

# Trục MẠNH của luật kép (spec §5 để ngưỡng trùng cổng vào → mọi kênh đều A;
# TODO user hiệu chỉnh sau 2 tuần chạy thật — brief §10: chưa chốt thì config + TODO)
STRONG = {'aud': 2, 'voc': 22, 'subs': 20000, 'long': 0.75}

def current_job(conn, org):
    return conn.execute('SELECT * FROM harvest_jobs WHERE org_id=? ORDER BY id DESC LIMIT 1',
                        (org,)).fetchone()

def parse_lines(text):
    """Thuần, 0 quota: dòng → (kind, value, raw). kind: id|handle|video|bad."""
    out = []
    for ln in (text or '').splitlines():
        s = ln.strip()
        if not s: continue
        m = re.search(r'channel/(UC[\w-]{16,})', s)
        if m: out.append(('id', m.group(1), s)); continue
        if re.fullmatch(r'UC[\w-]{16,}', s): out.append(('id', s, s)); continue
        m = re.search(r'(?:watch\?v=|youtu\.be/|/shorts/|/live/)([\w-]{6,})', s)
        if m: out.append(('video', m.group(1), s)); continue
        m = re.search(r'@([\w.\-]+)', s)
        if m: out.append(('handle', '@' + m.group(1), s)); continue
        out.append(('bad', '', s))
    return out

def _resolve(api, text):
    """→ (list channel_id không trùng, list dòng lỗi). ~1 unit/dòng handle/video."""
    ids, bad = [], []
    for kind, val, raw in parse_lines(text):
        cid = None
        if kind == 'id': cid = val
        elif kind == 'handle':
            d = api.get('channels', {'part': 'id', 'forHandle': val}) or {}
            cid = ((d.get('items') or [{}])[0] or {}).get('id')
        elif kind == 'video':
            d = api.get('videos', {'part': 'snippet', 'id': val}) or {}
            cid = (((d.get('items') or [{}])[0] or {}).get('snippet') or {}).get('channelId')
        if cid and cid not in ids: ids.append(cid)
        elif not cid: bad.append(raw)
    return ids, bad

def start(org, text, mode, audience_on, api_factory=None):
    """Tạo job mới (đè bản nháp cũ — API đã bắt xác nhận) rồi chạy nền."""
    conn = db.connect()
    try:
        with conn:
            old = current_job(conn, org)
            if old: _purge(conn, old['id'])
            n = len([1 for k, *_ in parse_lines(text) if k != 'bad'])
            conn.execute(
                'INSERT INTO harvest_jobs (org_id, mode, status, input_raw, audience, quota_est, created_ts) '
                'VALUES (?,?,?,?,?,?,?)',
                (org, mode, 'RESOLVING', text, int(audience_on), 4 * n + 2500, time.time()))
    finally:
        conn.close()
    spawn(org, api_factory)

def _purge(conn, job_id):
    for t in ('harvest_results', 'harvest_groups'):
        conn.execute(f'DELETE FROM {t} WHERE job_id=?', (job_id,))
    conn.execute('DELETE FROM harvest_jobs WHERE id=?', (job_id,))

def spawn(org, api_factory=None):
    t = _threads.get(org)
    if t and t.is_alive(): return False
    t = threading.Thread(target=_run, args=(org, api_factory), daemon=True, name=f'harvest-{org}')
    _threads[org] = t; t.start()
    return True

def _run(org, api_factory=None):
    conn = db.connect()                                # thread riêng — connection riêng
    try:
        job = current_job(conn, org)
        if not job: return
        keys = db.harvest_keys(conn, org)
        if not keys:
            _set(conn, job['id'], 'ERROR', note='Kho Key Harvest trống — thêm key ở tab Setting trước')
            return
        api = api_factory(keys) if api_factory else API(keys)
        t0 = time.time()
        budget = float(os.environ.get('RADAR_BUDGET', 0) or 0)
        over = lambda: budget and time.time() - t0 > budget
        status = job['status']
        if status in ('PAUSED', 'ERROR'):              # chạy tiếp/THỬ LẠI: suy phase từ tiến độ đã có
            # ERROR resumable (sự cố 24/07/2026: job kẹt ERROR vĩnh viễn dù code đã vá +
            # checkpoint còn nguyên) — thử lại từ chỗ dừng, tệ nhất là ERROR lại với note mới
            picked = conn.execute('SELECT COUNT(*) FROM harvest_groups WHERE job_id=? AND selected=1',
                                  (job['id'],)).fetchone()[0]
            status = 'SNOWBALL' if picked else 'RESOLVING'
            _set(conn, job['id'], status, note='')
            job = current_job(conn, org)
        if status == 'RESOLVING':
            _phase_resolve(conn, job, api, over)
            job = current_job(conn, org)
        if job and job['status'] == 'SNOWBALL':
            _phase_snowball(conn, job, api, over)
    except RuntimeError as e:                          # mọi key 403/hết quota
        job = current_job(conn, org)
        if job: _set(conn, job['id'], 'PAUSED',
                     note='Hết quota — thêm key hoặc chờ 14:00 rồi bấm chạy tiếp. ' + str(e)[:120])
    except Exception as e:
        job = current_job(conn, org)
        if job: _set(conn, job['id'], 'ERROR', note=f'{type(e).__name__}: {e}'[:200])
    finally:
        conn.close()

def _set(conn, job_id, status=None, note=None, quota_add=0, ckpt=None):
    with conn:
        if status is not None:
            conn.execute('UPDATE harvest_jobs SET status=? WHERE id=?', (status, job_id))
        if note is not None:
            conn.execute('UPDATE harvest_jobs SET note=? WHERE id=?', (note, job_id))
        if quota_add:
            conn.execute('UPDATE harvest_jobs SET quota_used=quota_used+? WHERE id=?', (quota_add, job_id))
        if ckpt is not None:
            conn.execute('UPDATE harvest_jobs SET checkpoint=? WHERE id=?', (json.dumps(ckpt), job_id))

def _phase_resolve(conn, job, api, over):
    """Đọc kênh + đo + phân loại. POOL → CLASSIFIED (chờ user cắt); SEED → SNOWBALL luôn."""
    ck = json.loads(job['checkpoint'] or '{}')
    if 'ids' not in ck:
        ids, bad = _resolve(api, job['input_raw'])
        ck = {'ids': ids, 'bad': bad, 'measured': {}}
        _set(conn, job['id'], ckpt=ck, quota_add=api.used); api.used = 0
    for cid in ck['ids']:                              # đo từng kênh, checkpoint mỗi kênh
        if cid in ck['measured']: continue
        if over(): _set(conn, job['id'], 'PAUSED', note='PAUSE — chạy lại để tiếp', ckpt=ck); return
        ch = snowball.measure_channel(api, cid)
        ck['measured'][cid] = ch or {'id': cid, 'dead': True}
        _set(conn, job['id'], ckpt=ck, quota_add=api.used); api.used = 0
    chans = [c for c in ck['measured'].values() if not c.get('dead') and c.get('titles')]
    mode = job['mode']
    with conn:
        if mode == 'POOL':
            for gkey, g in decompose.decompose(chans).items():
                meta = {'desc': g['desc'], 'keywords': g['keywords'], 'reps': g['reps'],
                        'subs_min': g['subs_min'], 'subs_max': g['subs_max'], 'small': g['small'],
                        'channels': [{k: c.get(k) for k in
                                      ('id', 'title', 'subs', 'long_ratio', 'med_s', 'titles', 'durs', 'vids')}
                                     for c in g['channels']]}
                conn.execute('INSERT OR REPLACE INTO harvest_groups VALUES (?,?,?,?,?,0,?)',
                             (job['id'], gkey, g['lang'], g['fmt'], g['n'], json.dumps(meta)))
        else:                                          # SEED: 1 nhóm duy nhất, chọn sẵn
            lang = fp.detect_lang([t for c in chans for t in c['titles']])
            meta = {'desc': f'Seed {len(chans)} kênh', 'keywords': [], 'reps': [c['title'] for c in chans[:3]],
                    'subs_min': 0, 'subs_max': 0, 'small': len(chans) < 3,
                    'channels': [{k: c.get(k) for k in
                                  ('id', 'title', 'subs', 'long_ratio', 'med_s', 'titles', 'durs', 'vids')}
                                 for c in chans]}
            conn.execute('INSERT OR REPLACE INTO harvest_groups VALUES (?,?,?,?,?,1,?)',
                         (job['id'], f'{lang}/seed', lang, 'seed', len(chans), json.dumps(meta)))
    _set(conn, job['id'], 'CLASSIFIED' if mode == 'POOL' else 'SNOWBALL', note='', ckpt=ck)

def _phase_snowball(conn, job, api, over):
    """Snowball tuần tự từng nhóm đã chọn (gộp nếu user tick merge). Checkpoint mỗi vòng."""
    ck = json.loads(job['checkpoint'] or '{}')
    groups = conn.execute('SELECT * FROM harvest_groups WHERE job_id=? AND selected=1 ORDER BY gkey',
                          (job['id'],)).fetchall()
    batches = ([[g for g in groups]] if ck.get('merge') and len(groups) > 1
               else [[g] for g in groups])
    done = set(ck.get('done_batches', []))
    for batch in batches:
        bkey = '+'.join(g['gkey'] for g in batch)
        if bkey in done: continue
        st = ck.get('state') if (ck.get('state') or {}).get('bkey') == bkey else None
        if st is None: st = _new_state(batch, api, job['audience'])
        def on_round(s, _j=job['id'], _b=bkey):
            _set(conn, _j, ckpt={**ck, 'state': _ser(s, _b), 'done_batches': list(done)},
                 quota_add=api.used); api.used = 0
            if over():
                _set(conn, _j, 'PAUSED', note='PAUSE — chạy lại để tiếp'); return False
            return True
        st = _de(st) if isinstance(st.get('seen'), list) else st
        st = snowball.run(api, st, cfg=None, on_round=on_round, audience_on=bool(job['audience']))
        if current_job(conn, job['org_id'])['status'] == 'PAUSED': return
        _write_results(conn, job, bkey, st)
        done.add(bkey)
        ck = {**ck, 'state': None, 'done_batches': list(done)}
        _set(conn, job['id'], ckpt=ck, quota_add=api.used); api.used = 0
    _set(conn, job['id'], 'DONE', note='')

def _new_state(batch, api, audience_on):
    chans = [c for g in batch for c in json.loads(g['meta'])['channels']]
    lang = batch[0]['lang'] if batch[0]['lang'] != 'other' else 'en'
    fps = [fp.fingerprint(c['titles'], lang) for c in chans]
    seed_authors = set()
    if audience_on:
        for c in chans: seed_authors |= audience.channel_authors(api, c.get('vids'), pages=2)
    st = {'pool': {}, 'seen': set(), 'used_queries': set(),
          'centroid': fp.centroid(fps), 'lang': lang,
          'seed_authors': seed_authors, 'pool_authors': set(seed_authors), 'rounds': []}
    for c in chans:
        st['pool'][c['id']] = dict(c, round=0)
        st['seen'].add(c['id'])
    return st

def _ser(s, bkey):
    return {'bkey': bkey, 'pool': s['pool'], 'seen': list(s['seen']),
            'used_queries': list(s['used_queries']), 'centroid': list(s['centroid']),
            'lang': s['lang'], 'seed_authors': list(s['seed_authors']),
            'pool_authors': list(s['pool_authors']), 'rounds': s['rounds']}

def _de(s):
    return {**s, 'seen': set(s['seen']), 'used_queries': set(s['used_queries']),
            'centroid': set(s['centroid']), 'seed_authors': set(s['seed_authors']),
            'pool_authors': set(s['pool_authors'])}

def _grade(ch, audience_on):
    """Luật kép: hạng A khi mạnh ≥2 trục (ngưỡng STRONG). Kèm 'giống vì / có thể sai vì' (TC7)."""
    axes = []
    if (ch.get('core') or 0) >= STRONG['aud']: axes.append(f"khán giả giao {ch['core']} author")
    if (ch.get('voc') or 0) >= STRONG['voc']: axes.append(f"trùng {ch['voc']} từ khóa lõi")
    if (ch.get('subs') or 0) >= STRONG['subs']: axes.append('quy mô lớn')
    if (ch.get('long_ratio') or 0) >= STRONG['long']: axes.append(f"{round(ch['long_ratio']*100)}% long-form")
    tier = 'A' if len(axes) >= 2 else 'B'
    risk = []
    if audience_on and ch.get('thin'): risk.append(f"mẫu comment mỏng (N={ch.get('n_auth', 0)})")
    if not audience_on: risk.append('chưa đo khán giả')
    if tier == 'B': risk.append('mới đạt cổng vào, chưa mạnh ≥2 trục')
    why = ' · '.join(axes) or f"đạt cổng vào (voc {ch.get('voc')}, {round((ch.get('long_ratio') or 0)*100)}% long)"
    return tier, why, ' · '.join(risk) or '—'

def _write_results(conn, job, bkey, st):
    with conn:
        for cid, ch in st['pool'].items():
            tier, why, risk = _grade(ch, bool(job['audience']))
            conn.execute('INSERT OR REPLACE INTO harvest_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (job['id'], bkey, cid, ch.get('title') or cid, ch.get('subs') or 0,
                          ch.get('voc') or 0, ch.get('long_ratio') or 0, ch.get('core') or 0,
                          ch.get('broad') or 0, ch.get('n_auth') or 0, ch.get('round') or 0,
                          tier, why, risk))
        conn.execute("UPDATE harvest_groups SET meta=json_set(meta, '$.rounds', json(?)) "
                     'WHERE job_id=? AND gkey=?', (json.dumps(st['rounds']), job['id'], bkey.split('+')[0]))

def report_md(conn, job):
    """Báo cáo ĐẦY ĐỦ (.md) — bản user tải về là bản lưu."""
    from datetime import datetime
    L = [f"# Harvest — báo cáo đầy đủ (job #{job['id']} · {job['mode']})",
         f"*Sinh {datetime.now().strftime('%H:%M %d/%m/%Y')} · quota đã tiêu {job['quota_used']} units · "
         f"khán giả: {'BẬT' if job['audience'] else 'TẮT'}*", '',
         '> Advisory — Harvest không tự thêm kênh; anh/chị tự áp dụng qua tab Pool.', '']
    for g in conn.execute('SELECT * FROM harvest_groups WHERE job_id=? ORDER BY gkey', (job['id'],)):
        meta = json.loads(g['meta'])
        L += [f"## Nhóm {g['gkey']} — {g['n']} kênh đầu vào" + (' · ĐÃ CHỌN' if g['selected'] else ''),
              meta.get('desc') or '', '']
        if meta.get('rounds'):
            L += [f"Đà hội tụ (kênh mới đạt chuẩn/vòng): {' → '.join(map(str, meta['rounds']))}", '']
        rows = conn.execute('SELECT * FROM harvest_results WHERE job_id=? AND gkey LIKE ? '
                            'ORDER BY tier, voc DESC', (job['id'], f"%{g['gkey']}%")).fetchall()
        if rows:
            L += ['| Hạng | Kênh | Subs | voc | long% | core/broad | N mẫu | Vòng | Giống vì | Có thể sai vì |',
                  '|---|---|---|---|---|---|---|---|---|---|']
            for r in rows:
                L.append(f"| {r['tier']} | [{r['title']}](https://youtube.com/channel/{r['ch_id']}) "
                         f"| {r['subs']:,} | {r['voc']} | {round(r['long_ratio']*100)}% "
                         f"| {r['core']}/{r['broad']} | {r['n_auth']}{' ⚠' if r['n_auth'] < 30 else ''} "
                         f"| {r['round']} | {r['why']} | {r['risk']} |")
            L.append('')
    L += ['---', f"Ngưỡng cổng vào: voc≥{snowball.DEFAULTS['voc_min']} · long≥{snowball.DEFAULTS['long_min']} · "
          f"subs≥{snowball.DEFAULTS['subs_min']:,} · Trục MẠNH luật kép: aud≥{STRONG['aud']} · voc≥{STRONG['voc']} · "
          f"subs≥{STRONG['subs']:,} · long≥{STRONG['long']} (TODO hiệu chỉnh sau 2 tuần chạy thật)"]
    return '\n'.join(L)
