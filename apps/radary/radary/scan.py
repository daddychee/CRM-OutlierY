"""Tầng thu thập: YouTube API client, jobs quét adaptive, kho packaging, push ntfy.

Chu trình 1 workspace = run_cycle(): port từ cmd_run() của daily_radar.py,
state đọc/ghi SQLite thay JSON. Resumable y hệt bản cũ (budget → PAUSE → chạy tiếp).
"""
import hashlib, json, os, re, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
from . import core, db

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get('RADARY_DATA_DIR') or os.path.join(BASE, 'data')

class API:
    def __init__(s, keys): s.keys = keys; s.i = 0; s.used = 0
    def get(s, ep, params, cost=1):
        last = None
        for _ in range(max(len(s.keys)*2, 2)):
            q = dict(params); q['key'] = s.keys[s.i % len(s.keys)]
            url = f'https://www.googleapis.com/youtube/v3/{ep}?' + urllib.parse.urlencode(q)
            try:
                r = json.load(urllib.request.urlopen(url, timeout=20)); s.used += cost; return r
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (403, 429): s.i += 1; continue
                if e.code == 404: return {}
                raise
            except Exception as e:
                last = e; time.sleep(2)
        raise RuntimeError(f'API failed: {last}')

def parse_dur(d):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
    if not m: return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups()); return h*3600 + mi*60 + s

def parse_pub(p):
    try: return datetime.fromisoformat(p.replace('Z', '+00:00')).timestamp()
    except Exception: return 0

def resolve_channels(api, items):
    """Nhận list dạng tự do (URL /channel/UC…, @handle, /user/…, UC-id trần) → {yt_id: {title, uploads}}.
    Port từ load_inputs + cmd_init của engine cũ."""
    ids, handles, users = [], [], []
    for ln in items:
        ln = (ln or '').strip()
        if not ln: continue
        m = re.search(r'/channel/(UC[\w-]{10,})', ln)
        if m: ids.append(m.group(1)); continue
        if re.fullmatch(r'UC[\w-]{10,}', ln): ids.append(ln); continue
        m = re.search(r'@([\w.\-]+)', ln)
        if m: handles.append(m.group(1)); continue
        m = re.search(r'/user/([\w.\-]+)', ln)
        if m: users.append(m.group(1))
    found = {}
    def take(d):
        for it in d.get('items', []):
            found[it['id']] = {'title': it['snippet']['title'],
                               'uploads': it['contentDetails']['relatedPlaylists'].get('uploads', '')}
    for i in range(0, len(ids), 50):
        take(api.get('channels', {'part': 'snippet,contentDetails', 'id': ','.join(ids[i:i+50]), 'maxResults': 50}))
    for h in dict.fromkeys(handles):
        take(api.get('channels', {'part': 'snippet,contentDetails', 'forHandle': h}))
    for u in dict.fromkeys(users):
        take(api.get('channels', {'part': 'snippet,contentDetails', 'forUsername': u}))
    return found

# ---------------- kho packaging ----------------
def thumbs_dir(ws):
    d = os.path.join(DATA, 'thumbs', str(ws)); os.makedirs(d, exist_ok=True); return d

def snap_thumb(cy, yt_id, v, force=False):
    """Lưu ảnh thumbnail khi nội dung ảnh ĐỔI (so hash) — 0 unit quota."""
    hist = cy.thumb_last.get(v.get('_id'))
    due = force or hist is None or (v.get('tier', 0) >= 1 and cy.now - v.get('thumb_ck', 0) > 86400)
    if not due or cy.thumb_n >= cy.cfg.get('thumb_cap', 150) or cy.over_budget(): return
    try:
        data = urllib.request.urlopen(f'https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg', timeout=10).read()
    except Exception: return
    cy.thumb_n += 1; v['thumb_ck'] = cy.now
    h = hashlib.md5(data).hexdigest()[:10]
    if hist != h:
        with open(os.path.join(thumbs_dir(cy.ws), f'{yt_id}_{h}.jpg'), 'wb') as f: f.write(data)
        # with conn: commit NGAY — INSERT trần mở transaction ngầm giữ KHÓA GHI tới tận
        # cuối chu kỳ (nhiều phút gọi YouTube), làm mọi request khác nổ "database is locked"
        with cy.conn:
            cy.conn.execute('INSERT INTO thumb_hist(video_id, ts, hash) VALUES(?,?,?)', (v['_id'], cy.now, h))
        cy.thumb_last[v['_id']] = h
        if hist is not None:
            cy.extra_events.append({'ts': cy.now, 'kind': 'rethumb', 'vid': yt_id, 'ch': v['ch'], 'title': v['title']})

# ---------------- push ----------------
def ntfy_send(topic, title, message, priority=4, tags=('rotating_light',)):
    """Publish JSON lên ntfy — header HTTP chỉ nhận latin-1 nên title tiếng Việt PHẢI đi qua JSON body."""
    payload = json.dumps({'topic': topic, 'title': title, 'message': message,
                          'priority': priority, 'tags': list(tags)}, ensure_ascii=False)
    req = urllib.request.Request('https://ntfy.sh', data=payload.encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=10)

def make_push_fn(cfg, now):
    def push(tier, v, m, vid=''):
        if not cfg.get('ntfy_enabled') or not cfg.get('ntfy_topic'): return False
        names = {2: 'T2 ỨNG VIÊN', 3: 'T3 SÓNG — SẢN XUẤT', 4: 'T4 BÙNG NỔ'}
        body = (f"{v['title'][:90]}\n{v['ch']} | VPH {m['vph']:,.0f} | VPD {m['vpd']:,.0f} | "
                f"tuổi {core.age_h(v, now)/24:.1f}d | hạng {m['rank']} cohort D{m['cohort']}\nhttps://youtu.be/{vid}")
        try:
            ntfy_send(cfg['ntfy_topic'], names[tier], body, priority=5 if tier == 4 else 4)
            return True
        except Exception: return False
    return push

# ---------------- chu trình 1 workspace ----------------
class Cycle:
    """Gom context 1 lần chạy: kết nối, config, budget, bộ đếm — để jobs dùng chung."""
    def __init__(s, conn, ws, budget_s=9999.0):
        s.conn = conn; s.ws = ws
        s.cfg = db.get_config(conn, ws)
        s.now = time.time(); s.t0 = time.time(); s.budget = budget_s
        s.thumb_n = 0; s.extra_events = []
        s.ch_scanned = 0; s.ch_fail = []           # nhật ký quét: kênh đọc được / hỏng
        s.refreshed = 0; s.new_videos = 0
        s.dirty_ticks = set()
        s.thumb_last = {r['video_id']: r['hash'] for r in conn.execute(
            'SELECT video_id, hash FROM thumb_hist WHERE video_id IN '
            '(SELECT id FROM videos WHERE workspace_id=?) ORDER BY ts', (ws,))}
    def over_budget(s): return time.time() - s.t0 > s.budget

def refresh_videos(cy, api, V, vids):
    # bỏ qua video vừa tick <15 phút (resume sau PAUSE không fetch lại phần đã làm)
    vids = [x for x in vids if x in V and not V[x]['dead']
            and not (V[x]['ticks'] and cy.now - V[x]['ticks'][-1][0] < 900)]
    for i in range(0, len(vids), 50):
        if cy.over_budget(): return False
        batch = vids[i:i+50]
        d = api.get('videos', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(batch), 'maxResults': 50})
        got = set()
        for it in d.get('items', []):
            v = V[it['id']]; got.add(it['id'])
            if v['dur'] is None:
                # livestream/premiere chưa kết thúc KHÔNG có trường duration — giữ None (chưa biết),
                # lần quét sau khi video chốt sẽ điền; sự cố thật 12/07/2026 làm Space đứng 2.7h
                d_raw = it.get('contentDetails', {}).get('duration')
                if d_raw: v['dur'] = parse_dur(d_raw)
            new_title = it.get('snippet', {}).get('title', '')
            if new_title and new_title != v['title']:
                with cy.conn:   # commit ngay — cùng lý do thumb_hist (không găm khóa ghi cả chu kỳ)
                    cy.conn.execute('INSERT INTO title_hist(video_id, ts, old_title) VALUES(?,?,?)',
                                    (v['_id'], cy.now, v['title']))
                cy.extra_events.append({'ts': cy.now, 'kind': 'retitle', 'vid': it['id'],
                                        'old': v['title'], 'new': new_title, 'ch': v['ch']})
                v['title'] = new_title
                snap_thumb(cy, it['id'], v, force=True)
            else:
                snap_thumb(cy, it['id'], v)
            views = int(it.get('statistics', {}).get('viewCount') or 0)
            if not v['ticks'] or views != v['ticks'][-1][1] or cy.now - v['ticks'][-1][0] > 1800:
                v['ticks'].append([cy.now, views]); cy.dirty_ticks.add(it['id'])
        cy.refreshed += len(got)
        for x in batch:
            if x not in got and not V[x]['dead']:
                V[x]['dead'] = True
                cy.extra_events.append({'ts': cy.now, 'kind': 'dead', 'vid': x, 'ch': V[x]['ch'], 'title': V[x]['title']})
    return True

def job_discover(cy, api, V, prog):
    channels = {r['yt_id']: dict(r) for r in cy.conn.execute(
        'SELECT * FROM channels WHERE workspace_id=? AND active=1', (cy.ws,))}
    done = prog.get('discover_done', [])
    for cid, info in channels.items():
        if cid in done or not info.get('uploads_playlist'): continue
        if cy.over_budget(): prog['discover_done'] = done; return False
        d = api.get('playlistItems', {'part': 'contentDetails,snippet', 'playlistId': info['uploads_playlist'], 'maxResults': 20})
        if not d:
            cy.ch_fail.append(info.get('title') or cid)        # 404 — kênh xóa/đổi playlist?
        else:
            cy.ch_scanned += 1
        for it in d.get('items', []):
            vid = it['contentDetails']['videoId']
            if vid not in V:
                sn = it['snippet']
                V[vid] = {'ch': sn.get('channelTitle', info['title']), 'chId': cid, 'title': sn.get('title', ''),
                          'pub': parse_pub(it['contentDetails'].get('videoPublishedAt', sn.get('publishedAt', ''))),
                          'dur': None, 'ticks': [], 'tier': 0, 'fail': 0, 'pushed': 0,
                          'last_vph': 0.0, 'confirm_due': 0, 'dead': False}
                db.upsert_video(cy.conn, cy.ws, vid, V[vid])   # cấp _id ngay để thumb/title_hist trỏ được
                cy.new_videos += 1
        done.append(cid)
    prog['discover_done'] = []
    new = [vid for vid, v in V.items() if not v['ticks'] and not v['dead']]
    return refresh_videos(cy, api, V, new)

def select_ids(V, pred): return [vid for vid, v in V.items() if not v['dead'] and pred(v)]

def purge_events(extra_events, now, purge_min=3):
    """Gộp các video Xóa/Ẩn CÙNG KÊNH trong một chu kỳ thành tín hiệu cấp kênh
    (dọn kho / đổi chiến lược / strike). Chỉ ghi Alerts — không push."""
    by_ch = {}
    for e in extra_events:
        if e.get('kind') == 'dead':
            by_ch.setdefault(e.get('ch', '?'), []).append(e)
    return [{'ts': now, 'kind': 'channel_purge', 'ch': ch, 'count': len(evs),
             'vids': [e.get('vid', '') for e in evs][:20]}
            for ch, evs in by_ch.items() if len(evs) >= purge_min]

def next_sunday_8am(tz):
    n = datetime.now(tz)
    days = (6 - n.weekday()) % 7
    cand = (n + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
    if cand <= n: cand += timedelta(days=7)
    return cand.timestamp()

def pool_pulse(conn, ws, V, now, tz):
    """Phase 3.13: nén nhịp pool + kênh thành bucket 6h CĂN GIỜ ĐỊA PHƯƠNG (00-06-12-18 VN)
    vào pool_stats/channel_stats — GIỮ VĨNH VIỄN. Views cộng thêm giữa 2 tick được PHÂN BỔ
    TUYẾN TÍNH lên các bucket chồng lấn (ước lượng phân bổ — video nguội quét thưa được trải
    đều thay vì dồn cục vào lần quét; user duyệt 23/07/2026 qua bản xem trước).
    14 ngày gần (tick thô còn): xóa + ghi lại mỗi chu kỳ (idempotent, dọn luôn bucket căn
    UTC của bản cũ). Cũ hơn: INSERT OR IGNORE — backfill 1 lần từ nến ngày rồi hóa thạch."""
    B = 6 * 3600
    off = datetime.fromtimestamp(now, tz).utcoffset().total_seconds()
    cut = now - 14 * 86400
    P, C = {}, {}                    # bucket -> {'dv','young':{vid:[dv,dt]}} · (bucket, kênh) -> dv
    for vid, v in V.items():
        ts, ch = v['ticks'], v['ch']
        for i in range(1, len(ts)):
            t0, v0 = ts[i-1]; t1, v1 = ts[i]
            dv = v1 - v0
            if dv <= 0 or t1 <= t0: continue
            young = v['pub'] and 0 <= t1 - v['pub'] <= 6 * 86400   # video 0-6 ngày tuổi
            bs = int((t0 + off) // B) * B - off
            while bs < t1:
                ov = min(t1, bs + B) - max(t0, bs)
                if ov > 0:
                    share = dv * ov / (t1 - t0)
                    cell = P.setdefault(bs, {'dv': 0.0, 'young': {}})
                    cell['dv'] += share
                    C[(bs, ch)] = C.get((bs, ch), 0.0) + share
                    if young:
                        y = cell['young'].setdefault(vid, [0.0, 0.0]); y[0] += share; y[1] += ov
                bs += B
    prow = []
    for bs, cell in P.items():
        vphs = [d / (t / 3600) for d, t in cell['young'].values() if t > 0]
        prow.append((ws, bs, round(cell['dv']), round(sum(vphs) / len(vphs), 1) if vphs else 0, len(vphs)))
    crow = [(ws, bs, ch, round(dv)) for (bs, ch), dv in C.items() if dv >= 1]
    conn.execute('DELETE FROM pool_stats WHERE workspace_id=? AND bucket_ts>=?', (ws, cut))
    conn.execute('DELETE FROM channel_stats WHERE workspace_id=? AND bucket_ts>=?', (ws, cut))
    conn.executemany('INSERT OR REPLACE INTO pool_stats VALUES (?,?,?,?,?)', [r for r in prow if r[1] >= cut])
    conn.executemany('INSERT OR IGNORE INTO pool_stats VALUES (?,?,?,?,?)', [r for r in prow if r[1] < cut])
    conn.executemany('INSERT OR REPLACE INTO channel_stats VALUES (?,?,?,?)', [r for r in crow if r[1] >= cut])
    conn.executemany('INSERT OR IGNORE INTO channel_stats VALUES (?,?,?,?)', [r for r in crow if r[1] < cut])

def snap_channels(conn, api, ws, tz, now):
    """Metrics (user duyệt mockup 23/07/2026): chụp hồ sơ kênh (subs/viewCount/videoCount)
    1 lần/ngày theo tz workspace — channels.list ~1 unit/50 kênh. Đã có bản hôm nay → [] (0 quota).
    Mọi trường statistics coi như CÓ THỂ THIẾU (bài học KeyError 'duration') — thiếu để NULL."""
    day = datetime.fromtimestamp(now, tz).strftime('%Y-%m-%d')
    if conn.execute('SELECT 1 FROM channel_snap WHERE workspace_id=? AND day=? LIMIT 1', (ws, day)).fetchone():
        return []
    ids = [r['yt_id'] for r in conn.execute('SELECT yt_id FROM channels WHERE workspace_id=? AND active=1', (ws,))]
    def num(st, k):
        try: return int(st[k])
        except (KeyError, TypeError, ValueError): return None
    rows = []
    for i in range(0, len(ids), 50):
        d = api.get('channels', {'part': 'statistics', 'id': ','.join(ids[i:i+50]), 'maxResults': 50})
        for it in d.get('items', []):
            st = it.get('statistics') or {}
            subs = None if st.get('hiddenSubscriberCount') else num(st, 'subscriberCount')
            rows.append((ws, day, it.get('id', ''), subs, num(st, 'viewCount'), num(st, 'videoCount'), now))
    return rows

def run_cycle(conn, ws, budget_s=9999.0):
    """Một chu kỳ quét cho 1 workspace. Trả dict tóm tắt (tag, jobs chạy, events, quota)."""
    from . import report
    cy = Cycle(conn, ws, budget_s)
    keys = db.api_keys(conn, ws)
    if not keys: return {'tag': 'NO-KEY', 'ran': [], 'events': 0, 'quota': 0}
    api = API(keys)
    tz = core.tzinfo(conn.execute('SELECT tz FROM workspaces WHERE id=?', (ws,)).fetchone()['tz'])
    V = db.load_videos(conn, ws)
    jobs = db.get_jobs(conn, ws)
    prog = db.kv_get(conn, ws, 'progress', {})
    today = datetime.now(tz).strftime('%Y-%m-%d')
    pc = db.kv_get(conn, ws, 'push_count', {'date': today, 't2': 0})
    if pc['date'] != today: pc = {'date': today, 't2': 0}
    CAD = cy.cfg['cadence']
    now, cfg = cy.now, cy.cfg
    ran = []
    def due(j): return now >= jobs.get(j, 0)
    def ah(v): return core.age_h(v, now)
    ok = True
    if due('discover'):
        ok = job_discover(cy, api, V, prog); ran.append('discover')
        if ok: jobs['discover'] = now + CAD['discover']
    if ok and due('hot'):
        ok = refresh_videos(cy, api, V, select_ids(V, lambda v: v['tier'] >= 2 or v['confirm_due'])); ran.append('hot')
        if ok: jobs['hot'] = now + CAD['hot']
    if ok and due('t1'):
        ok = refresh_videos(cy, api, V, select_ids(V, lambda v: v['tier'] == 1)); ran.append('t1')
        if ok: jobs['t1'] = now + CAD['t1']
    if ok and due('d01'):
        ok = refresh_videos(cy, api, V, select_ids(V, lambda v: ah(v) < 48 and v['tier'] < 2)); ran.append('d01')
        if ok: jobs['d01'] = now + CAD['d01']
    if ok and due('d26'):
        ok = refresh_videos(cy, api, V, select_ids(V, lambda v: 48 <= ah(v) < 168 and v['tier'] < 1)); ran.append('d26')
        if ok: jobs['d26'] = now + CAD['d26']
    if ok and due('allages'):
        ok = refresh_videos(cy, api, V, select_ids(V, lambda v: ah(v) >= 168 and (v['dur'] or 999) > cfg['min_duration_s']))
        ran.append('allages')
        if ok:
            jobs['allages'] = now + CAD['allages']
            cy.dirty_ticks.update(core.prune(V, now))
    events, metrics = core.evaluate(V, cfg, pc, now, make_push_fn(cfg, now))
    cy.extra_events += purge_events(cy.extra_events, now, cfg.get('purge_min', 3))
    if due('weekly'):
        wpath = report.render_weekly(conn, ws, V, cfg, tz); jobs['weekly'] = next_sunday_8am(tz); ran.append('weekly')
        report.spawn_weekly_narrative(ws, wpath)     # Nhận định AI chèn nền, không chặn chu kỳ
    report.render_board(conn, ws, V, cfg, metrics, jobs, api.used, pc, now)
    report.append_alerts(ws, events)
    # ---- nhật ký quét: 1 dòng/chu kỳ — số liệu + bất ổn (⚠) + đặc biệt (★) ----
    cnt = lambda k: sum(1 for e in cy.extra_events if e['kind'] == k)
    dead_n, ret_n, reth_n, purge_n = cnt('dead'), cnt('retitle'), cnt('rethumb'), cnt('channel_purge')
    up2 = sum(1 for e in events if e['to'] >= 2 and e['to'] > e['from'])
    pool_n = conn.execute('SELECT COUNT(*) FROM channels WHERE workspace_id=? AND active=1', (ws,)).fetchone()[0]
    notes, special = [], []
    if not ok: notes.append('chưa xong (hết budget) — chu kỳ sau chạy nốt')
    if cy.ch_fail: notes.append(f"{len(cy.ch_fail)} kênh không đọc được: " + ', '.join(cy.ch_fail[:3]))
    if api.i > 0: notes.append('đã phải xoay API key (403/quota)')
    if up2: special.append(f'{up2} video lên T2+')
    if purge_n: special.append(f'{purge_n} kênh ẩn hàng loạt')
    if dead_n: special.append(f'{dead_n} video Xóa/Ẩn')
    if ret_n or reth_n: special.append(f'đối thủ đổi packaging ({ret_n} title, {reth_n} thumb)')
    if cy.new_videos: special.append(f'{cy.new_videos} video mới vào radar')
    snap_rows = []
    if ok:                               # snapshot lỗi chỉ làm thiếu Metrics hôm đó, KHÔNG giết chu kỳ
        try: snap_rows = snap_channels(conn, api, ws, tz, now)
        except Exception as e: notes.append(f'snapshot kênh lỗi ({type(e).__name__}) — chu kỳ sau thử lại')
    summary = {'ts': now, 'tag': 'DONE' if ok else 'PAUSE', 'ran': ran, 'quota': api.used,
               'pool': pool_n, 'ch_scanned': cy.ch_scanned, 'refreshed': cy.refreshed,
               'new_videos': cy.new_videos, 'events': len(events), 'notes': notes, 'special': special}
    with conn:
        db.save_state(conn, ws, V, cy.dirty_ticks)
        pool_pulse(conn, ws, V, now, tz)
        if snap_rows:
            conn.executemany('INSERT OR IGNORE INTO channel_snap VALUES (?,?,?,?,?,?,?)', snap_rows)
        db.set_jobs(conn, ws, jobs)
        db.kv_set(conn, ws, 'progress', prog)
        db.kv_set(conn, ws, 'push_count', pc)
        db.kv_set(conn, ws, 'board', report.board_data(V, cfg, metrics, jobs, api.used, pc, now))
        db.kv_set(conn, ws, 'heartbeat', now)
        db.append_events(conn, ws, [dict(e, kind='tier') for e in events] + cy.extra_events)
        db.append_cycle(conn, ws, summary)
    return dict(summary, videos=len(V))
